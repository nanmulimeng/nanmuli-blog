"""异步任务执行器（爬取 + AI 整理）

职责：任务路由 + 通用流程（状态管理/回调/质量过滤）
关键词任务 → KeywordTaskHandler
日报后处理 → DigestPostProcessor
"""

import asyncio
import json
import logging
import os
import re
import time
import uuid
from typing import Dict
from urllib.parse import urlsplit

from config import settings
from standalone.models import TaskStatus
from standalone import repository as repo
from standalone.db import task_scoped_db

logger = logging.getLogger(__name__)


async def _fire_callback(task_id: int, status: int):
    """任务完成/失败后通知调用方（任务级 callback 优先，配置级 callback 兜底）。"""
    task = await repo.get_task(task_id)
    task_callback_url = task.get("callback_url") if task else None
    url = task_callback_url or settings.callback_url
    if not url:
        return
    if not task_callback_url and _should_skip_global_callback(task, url):
        logger.info("Global callback skipped: task_id=%d task_type=%s url=%s",
                    task_id, task.get("task_type") if task else None, url)
        return

    payload = {"python_task_id": task_id, "status": status}
    headers = {"Content-Type": "application/json"}
    task_headers = _parse_callback_headers(task.get("callback_headers") if task else None)
    headers.update(task_headers)
    if settings.callback_api_key:
        headers.setdefault("X-Callback-Key", settings.callback_api_key)

    import httpx
    async with httpx.AsyncClient(timeout=settings.callback_timeout) as client:
        for attempt in range(3):
            try:
                resp = await client.post(url, json=payload, headers=headers)
                if 200 <= resp.status_code < 300 and _is_callback_success(resp):
                    logger.info("Callback fired: task_id=%d status=%d -> %d (attempt=%d)",
                                task_id, status, resp.status_code, attempt + 1)
                    return
                if 200 <= resp.status_code < 300:
                    logger.warning("Callback rejected (unrecoverable): task_id=%d -> body=%s",
                                   task_id, getattr(resp, "text", "")[:200])
                    return
                if 400 <= resp.status_code < 500:
                    logger.warning("Callback rejected (unrecoverable): task_id=%d -> %d",
                                   task_id, resp.status_code)
                    return
                # 5xx: retry
                logger.warning("Callback server error: task_id=%d status=%d -> %d (attempt=%d)",
                               task_id, status, resp.status_code, attempt + 1)
            except Exception as e:
                logger.warning("Callback attempt %d failed: task_id=%d error=%s",
                               attempt + 1, task_id, e)
            if attempt < 2:
                await asyncio.sleep(2 ** attempt)
    logger.warning("Callback failed after 3 retries: task_id=%d status=%d", task_id, status)


def _should_skip_global_callback(task: dict | None, url: str) -> bool:
    """Digest trigger is Python-native; Java's task callback has no matching task row."""
    if not task or task.get("task_type") != "digest":
        return False
    try:
        path = urlsplit(url).path.rstrip("/")
    except Exception:
        return False
    return path.endswith("/api/internal/collector/callback")


def _is_callback_success(resp) -> bool:
    try:
        data = resp.json()
    except Exception:
        return True
    if not isinstance(data, dict) or "code" not in data:
        return True
    return int(data.get("code") or 0) == 200


def _parse_callback_headers(raw_headers: str | None) -> dict[str, str]:
    """解析任务级 callback headers，过滤协议敏感头。"""
    if not raw_headers:
        return {}
    try:
        data = json.loads(raw_headers)
    except Exception:
        logger.warning("Invalid callback_headers JSON ignored")
        return {}
    if not isinstance(data, dict):
        return {}

    blocked = {"host", "content-length", "transfer-encoding", "connection"}
    headers: dict[str, str] = {}
    for key, value in data.items():
        key_str = str(key).strip()
        if not key_str or key_str.lower() in blocked:
            continue
        headers[key_str] = str(value)
    return headers


class TaskExecutor:
    """管理异步爬取 + AI 整理任务"""

    def __init__(self, max_concurrent: int = 3):
        self._running: Dict[int, asyncio.Task] = {}
        self._execution_ids: Dict[int, str] = {}  # task_id -> execution_id
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def submit(self, task_id: int):
        if task_id in self._running:
            raise ValueError(f"Task {task_id} is already running")

        execution_id = uuid.uuid4().hex
        async_task = asyncio.create_task(self._execute_with_semaphore(task_id, execution_id))
        self._running[task_id] = async_task
        self._execution_ids[task_id] = execution_id

        def _on_done(t, tid=task_id, eid=execution_id):
            if self._execution_ids.get(tid) == eid:
                self._running.pop(tid, None)
                self._execution_ids.pop(tid, None)

        async_task.add_done_callback(_on_done)

    async def _execute_with_semaphore(self, task_id: int, execution_id: str):
        async with self._semaphore:
            # 任务级别的数据库连接复用：整个任务流程共享一个连接
            async with task_scoped_db():
                try:
                    await self._execute(task_id)
                finally:
                    if self._execution_ids.get(task_id) == execution_id:
                        self._running.pop(task_id, None)
                        self._execution_ids.pop(task_id, None)

    async def shutdown(self):
        """取消所有运行中的任务，将其标记为 FAILED"""
        task_ids = list(self._running.keys())
        for tid in task_ids:
            task = self._running.get(tid)
            if task and not task.done():
                task.cancel()
        if task_ids:
            await asyncio.gather(*[self._running.pop(tid, asyncio.sleep(0)) for tid in task_ids], return_exceptions=True)
            self._execution_ids.clear()
            for tid in task_ids:
                try:
                    await repo.fail_task(tid, "Service shutting down")
                except Exception:
                    pass
        logger.info("TaskExecutor shutdown: %d tasks cancelled", len(task_ids))

    async def _execute(self, task_id: int):
        from crawler.single import crawl_single_page
        from crawler.deep import crawl_deep_pages
        from crawler.search import crawl_by_keyword
        from crawler.config import get_browser_config, RunParams
        from crawler.dependencies import get_async_web_crawler
        from api.crawl import CrawlConfig

        task = await repo.get_task(task_id)
        if not task:
            return

        try:
            await repo.update_task_status(task_id, TaskStatus.CRAWLING)

            # source_url 校验：single/deep 任务必须有 URL
            if task["task_type"] in ("single", "deep"):
                if not task.get("source_url"):
                    await repo.fail_task(task_id, f"source_url is required for {task['task_type']} tasks")
                    await _fire_callback(task_id, TaskStatus.FAILED)
                    return

            # 从 DB 恢复用户提交的 config
            config_json = task.get("crawl_config")
            if config_json:
                config = CrawlConfig.model_validate_json(config_json)
            else:
                config = CrawlConfig()

            params = RunParams(config)

            # 日报 orchestrator 引用（同一 _execute 内跨阶段传递）
            _digest_orchestrator = None

            # ========== Phase 1: 爬取 ==========
            if task["task_type"] == "single":
                AsyncWebCrawler = get_async_web_crawler()
                browser_config = await get_browser_config(
                    text_mode=params.text_mode, light_mode=params.light_mode,
                    proxy=settings.proxy_url,
                )
                async with AsyncWebCrawler(config=browser_config) as crawler:
                    result = await crawl_single_page(url=task["source_url"], config=config, crawler=crawler)
                results = [result]

            elif task["task_type"] == "deep":
                AsyncWebCrawler = get_async_web_crawler()
                browser_config = await get_browser_config(
                    text_mode=params.text_mode, light_mode=params.light_mode,
                    proxy=settings.proxy_url,
                )
                async with AsyncWebCrawler(config=browser_config) as crawler:
                    results = await crawl_deep_pages(
                        url=task["source_url"],
                        max_depth=task["max_depth"],
                        max_pages=task["max_pages"],
                        config=config,
                        crawler=crawler
                    )

            elif task["task_type"] == "keyword":
                from standalone.keyword_handler import KeywordTaskHandler
                results = await KeywordTaskHandler(repository=repo).execute(task, config)

            elif task["task_type"] == "digest":
                from crawler.digest_orchestrator import DigestOrchestrator
                _digest_orchestrator = DigestOrchestrator()
                results = await _digest_orchestrator.execute(task, config, self)
                # 保存规划日志 + 板块清洗文档到 task metadata
                plan = _digest_orchestrator.get_plan()
                metadata_update = {}
                if plan and plan.plan_log:
                    metadata_update["orchestrator_plan"] = plan.plan_log
                section_docs = _digest_orchestrator.get_section_documents()
                if section_docs:
                    metadata_update["section_documents"] = [
                        {
                            "section_name": doc.section_name,
                            "source_count": doc.source_count,
                            "cleaned_count": doc.cleaned_count,
                            "total_word_count": doc.total_word_count,
                            "cleanup_method": doc.cleanup_method,
                            "cleanup_tokens_used": doc.cleanup_tokens_used,
                            "cleanup_duration_ms": doc.cleanup_duration_ms,
                            "merged_content": doc.merged_content[:50000],
                        }
                        for doc in section_docs
                    ]
                if metadata_update:
                    await repo.update_task_metadata(task_id, metadata_update)

            else:
                await repo.fail_task(task_id, f"Unknown task type: {task['task_type']}")
                await _fire_callback(task_id, TaskStatus.FAILED)
                return

            # 质量过滤（所有任务类型，日报使用宽松阈值）
            # 日报任务已在 DigestOrchestrator 内做过板块间去重，这里做最终质量筛选
            is_digest = task["task_type"] == "digest"
            # 日报任务：预热来源可信度缓存，避免后续同步 HTTP 阻塞事件循环
            if is_digest:
                try:
                    from crawler.quality import SourceAuthority
                    await SourceAuthority.preload_authority_cache()
                except Exception as e:
                    logger.warning("[Digest] SourceAuthority preload failed (fallback to hardcoded): %s", e)
            from crawler.dedup import DedupEngine
            if is_digest:
                dedup_engine = None  # DigestOrchestrator 已经做过完整去重，不再重复
            else:
                sim_threshold = settings.content_dedup_deep_threshold if task["task_type"] == "deep" else settings.content_dedup_simhash_threshold
                dedup_engine = DedupEngine(simhash_threshold=sim_threshold) if settings.content_dedup_enabled else None
            results = self._filter_low_quality(results, task["task_type"], dedup_engine=dedup_engine)

            # 保存爬取结果
            total_words = await repo.save_pages(task_id, results)

            success_count = sum(1 for r in results if r.success)
            crawl_duration = sum(r.crawl_time_ms for r in results if r.success)

            if success_count == 0:
                error = next((r.error_message for r in results if r.error_message), None)
                if not error or not error.strip():
                    error = "所有页面爬取失败，未返回任何成功结果"
                await repo.fail_task(task_id, error)
                await _fire_callback(task_id, TaskStatus.FAILED)
                return

            # 更新爬取统计（不改变状态，进入 AI 阶段）
            await repo.complete_crawl(
                task_id,
                total_pages=len(results),
                completed_pages=success_count,
                crawl_duration=crawl_duration,
                total_word_count=total_words
            )

            logger.info("Task %d crawl done: %d/%d pages, %d words. Starting AI organization.",
                        task_id, success_count, len(results), total_words)

            # ========== Phase 2: AI 整理 ==========
            if settings.ai_organization_enabled:
                await repo.update_task_status(task_id, TaskStatus.PROCESSING)

                from standalone.digest_post_processor import DigestPostProcessor
                processor = DigestPostProcessor(repository=repo)

                # 日报任务：优先使用 Orchestrator 预生成的日报
                pre_generated = None
                if task["task_type"] == "digest" and _digest_orchestrator:
                    pre_generated = _digest_orchestrator.get_digest_result()

                if pre_generated and pre_generated.digest_content:
                    ai_success = await processor.save_pre_generated(
                        task_id, task, pre_generated,
                    )
                    if not ai_success:
                        logger.warning("Task %d pre-generated digest save failed, falling back.", task_id)
                        ai_success = await processor.organize_with_ai(task_id, task)
                else:
                    ai_success = await processor.organize_with_ai(task_id, task)

                if not ai_success:
                    logger.warning("Task %d AI organization failed, task still marked complete with raw content.", task_id)
                    await repo.save_ai_error(task_id, "AI 整理失败，内容为原始 Markdown")
            else:
                logger.info("Task %d AI organization disabled, skipping.", task_id)

            await repo.complete_task(task_id)
            logger.info("Task %d completed.", task_id)
            await _fire_callback(task_id, TaskStatus.COMPLETED)

        except Exception as e:
            logger.error("Task %d failed: %s", task_id, e, exc_info=True)
            error_msg = str(e).strip() if str(e).strip() else f"未知错误: {type(e).__name__}"
            await repo.fail_task(task_id, error_msg)
            await _fire_callback(task_id, TaskStatus.FAILED)
        finally:
            # 通知信息源调度器：任务已完成（无论成功/失败）
            try:
                from standalone.scheduler import notify_task_completion
                notify_task_completion(task_id)
            except Exception:
                pass

    def is_running(self, task_id: int) -> bool:
        return task_id in self._running

    @property
    def running_count(self) -> int:
        return len(self._running)

    def _filter_low_quality(self, results: list, task_type: str = None,
                            dedup_engine=None) -> list:
        """过滤低质量/垃圾内容，避免浪费 AI token

        深度爬取使用更宽松的阈值：用户主动选择了目标域名，域内页面默认可信，
        仅过滤内容过短或明显为垃圾的页面。
        """
        from crawler.quality import evaluate_content
        page_classifier = None
        if settings.page_classifier_enabled:
            from crawler.page_classifier import classify_page as _classify
            page_classifier = _classify

        is_deep = (task_type == "deep")
        is_digest = (task_type == "digest")
        deep_min_score = settings.deep_eval_review_threshold
        # 日报独立质量阈值：比 deep 更严格，避免低质量内容浪费 AI token
        digest_min_score = settings.digest_eval_reject_threshold

        # 过滤统计
        stats = {"total": len(results), "too_short": 0, "non_article": 0,
                 "duplicate": 0, "low_quality": 0, "passed": 0}

        filtered = []
        for r in results:
            if not getattr(r, "success", False):
                # 日报任务直接丢弃失败结果（不需要保留错误记录）
                if is_digest:
                    continue
                filtered.append(r)
                continue

            url = getattr(r, "url", "")
            title = getattr(r, "title", "") or ""
            markdown = getattr(r, "markdown", "") or ""

            # [1] 内容太短直接标记失败
            if is_deep:
                min_content = settings.filter_deep_min_content
            elif is_digest:
                min_content = settings.digest_filter_min_content
            else:
                min_content = settings.min_content_length
            if len(markdown) < min_content:
                r.success = False
                r.error_message = f"Content too short ({len(markdown)} chars)"
                filtered.append(r)
                stats["too_short"] += 1
                continue

            # [2] 页面类型分类器（P5）：SERP/列表/论坛 → 直接拒绝
            if page_classifier is not None:
                classification = page_classifier(markdown, url, title)
                if classification.is_non_article:
                    r.success = False
                    r.error_message = f"Non-article page: {classification.page_type} (confidence={classification.confidence:.0%})"
                    filtered.append(r)
                    stats["non_article"] += 1
                    logger.debug("Filtered non-article: %s type=%s conf=%.0f signals=%s",
                                 url, classification.page_type, classification.confidence,
                                 classification.signals)
                    continue

            # [3] 内容去重（P6）：跳过头部导航区，取中间段做指纹
            if dedup_engine is not None and len(markdown) >= 100:
                skip_header = settings.filter_skip_header_chars
                content_preview = markdown[skip_header:skip_header + settings.filter_content_preview_length] if len(markdown) > skip_header else markdown[:settings.filter_content_preview_length]
                dup = dedup_engine.is_duplicate(url, title, content_preview)
                if dup["is_duplicate"]:
                    r.success = False
                    r.error_message = f"Duplicate: {dup['reason']} (confidence={dup['confidence']:.0%})"
                    filtered.append(r)
                    stats["duplicate"] += 1
                    logger.debug("Filtered duplicate: %s reason=%s conf=%.0f",
                                 url, dup["reason"], dup["confidence"])
                    continue

            # [4] 质量评分
            evaluation = evaluate_content(url, title, markdown, task_type=task_type)
            verdict = evaluation["verdict"]
            final_score = evaluation["final_score"]

            should_reject = False
            if is_digest:
                # 日报：使用独立阈值，spam 直接拒绝
                source_level = evaluation["source"]["level"]
                content_score = evaluation["quality"]["total_score"]
                if source_level == "spam":
                    should_reject = True
                elif content_score < 25 and source_level != "official":
                    # 内容质量绝对值过低，不论来源可信度直接拒绝
                    should_reject = True
                elif final_score < digest_min_score and source_level != "official":
                    should_reject = True
            elif is_deep:
                source_level = evaluation["source"]["level"]
                if source_level == "spam" and final_score < deep_min_score:
                    should_reject = True
                elif final_score < (deep_min_score - 10) and source_level != "official":
                    should_reject = True
            else:
                should_reject = (verdict == "reject")

            if should_reject:
                r.success = False
                r.error_message = f"Low quality content (score={final_score:.0f}, verdict={verdict})"
                stats["low_quality"] += 1
                logger.info("Filtered low-quality: %s (score=%.0f, reason=%s)",
                            url, final_score, evaluation["source"]["reason"])
            else:
                # 附加评估信息到 metadata
                metadata = getattr(r, "metadata", {}) or {}
                metadata["quality_score"] = final_score
                metadata["quality_verdict"] = verdict if not is_deep else (
                    "pass" if verdict == "pass" else "review"
                )
                r.metadata = metadata
                stats["passed"] += 1

                # [5] 注册去重指纹（质量通过后）
                if dedup_engine is not None and len(markdown) >= 100:
                    skip_header = settings.filter_skip_header_chars
                    content_preview = markdown[skip_header:skip_header + settings.filter_content_preview_length] if len(markdown) > skip_header else markdown[:settings.filter_content_preview_length]
                    dedup_engine.add(url, title, content_preview)

            filtered.append(r)

        # 过滤统计日志
        logger.info("Task filter stats: total=%d, too_short=%d, non_article=%d, "
                    "duplicate=%d, low_quality=%d, passed=%d",
                    stats["total"], stats["too_short"], stats["non_article"],
                    stats["duplicate"], stats["low_quality"], stats["passed"])

        return filtered


# ============== Helpers ==============

_FRIENDLY_SOURCE_NAMES: dict[str, str] = {
    # 官方文档
    "docs.spring.io": "Spring", "spring.io": "Spring",
    "docs.python.org": "Python", "python.org": "Python",
    "developer.mozilla.org": "MDN",
    "kubernetes.io": "Kubernetes", "istio.io": "Istio",
    "react.dev": "React", "vuejs.org": "Vue.js",
    "docs.github.com": "GitHub Docs", "github.blog": "GitHub Blog",
    "aws.amazon.com": "AWS", "cloud.google.com": "Google Cloud",
    "azure.microsoft.com": "Azure",
    "docs.oracle.com": "Oracle", "dev.mysql.com": "MySQL",
    "postgresql.org": "PostgreSQL", "redis.io": "Redis",
    "mongodb.com": "MongoDB",
    "openai.com": "OpenAI", "anthropic.com": "Anthropic",
    "huggingface.co": "Hugging Face",
    # 技术社区
    "news.ycombinator.com": "Hacker News",
    "stackoverflow.com": "Stack Overflow",
    "infoq.com": "InfoQ", "infoq.cn": "InfoQ中文",
    "juejin.cn": "掘金", "segmentfault.com": "思否",
    "csdn.net": "CSDN", "blog.csdn.net": "CSDN",
    "zhihu.com": "知乎", "v2ex.com": "V2EX",
    "lobste.rs": "Lobsters",
    "reddit.com": "Reddit",
    "producthunt.com": "Product Hunt",
    "techcrunch.com": "TechCrunch",
    "theverge.com": "The Verge",
    "arstechnica.com": "Ars Technica",
    "medium.com": "Medium", "dev.to": "DEV Community",
    "freecodecamp.org": "freeCodeCamp",
    "baeldung.com": "Baeldung",
    "martinfowler.com": "Martin Fowler",
    "ruanyifeng.com": "阮一峰",
    # 开源平台
    "github.com": "GitHub", "gitlab.com": "GitLab",
    "gitee.com": "Gitee", "npmjs.com": "npm",
    "pypi.org": "PyPI", "crates.io": "crates.io",
    "pkg.go.dev": "Go Packages",
    "deno.land": "Deno", "bun.sh": "Bun",
    "rust-lang.org": "Rust",
    "nodejs.org": "Node.js",
    # 学术
    "arxiv.org": "arXiv", "paperswithcode.com": "Papers With Code",
    "scholar.google.com": "Google Scholar",
    # 工具
    "jetbrains.com": "JetBrains",
    "code.visualstudio.com": "VS Code",
    "docker.com": "Docker",
    "postman.com": "Postman",
    "figma.com": "Figma",
    "vercel.com": "Vercel", "vercel.app": "Vercel",
    "netlify.app": "Netlify",
    # 中文资讯
    "36kr.com": "36氪", "ithome.com": "IT之家",
    "sspai.com": "少数派",
    "thenewstack.io": "The New Stack",
}


def extract_source_name(url: str) -> str:
    if not url:
        return "未知来源"
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        # 精确匹配
        if domain in _FRIENDLY_SOURCE_NAMES:
            return _FRIENDLY_SOURCE_NAMES[domain]
        # 后缀匹配（如 myproject.github.io → GitHub Pages）
        for suffix, name in _FRIENDLY_SOURCE_NAMES.items():
            if domain.endswith("." + suffix):
                return name
        return domain or "未知来源"
    except Exception:
        return "未知来源"


# ============ 分类推断（基于域名优先 + 标题词边界匹配） ============

_SOURCE_CATEGORY_MAP: dict[str, str] = {
    # 开源项目
    "github.com": "open_source",
    "gitlab.com": "open_source",
    "gitee.com": "open_source",
    "npmjs.com": "open_source",
    "pypi.org": "open_source",
    "pkg.go.dev": "open_source",
    "crates.io": "open_source",
    "gitlab.io": "open_source",
    "netlify.app": "open_source",
    "vercel.app": "open_source",
    "huggingface.co": "open_source",
    "ossinsight.io": "open_source",
    "openjsf.org": "open_source",
    "apache.org": "open_source",
    "cncf.io": "open_source",
    "rust-lang.org": "open_source",
    "python.org": "open_source",
    "nodejs.org": "open_source",
    "deno.land": "open_source",
    "bun.sh": "open_source",
    "dev.to": "open_source",
    # 学术论文
    "arxiv.org": "paper",
    "paperswithcode.com": "paper",
    "dl.acm.org": "paper",
    "ieeexplore.ieee.org": "paper",
    "scholar.google.com": "paper",
    "academic.microsoft.com": "paper",
    "semanticscholar.org": "paper",
    "openreview.net": "paper",
    "dblp.org": "paper",
    # 开发工具
    "producthunt.com": "dev_tool",
    "jetbrains.com": "dev_tool",
    "code.visualstudio.com": "dev_tool",
    "marketplace.visualstudio.com": "dev_tool",
    "docker.com": "dev_tool",
    "postman.com": "dev_tool",
    "figma.com": "dev_tool",
    "notion.so": "dev_tool",
    "linear.app": "dev_tool",
    "vercel.com": "dev_tool",
    "render.com": "dev_tool",
    "fly.io": "dev_tool",
    # 热点动态
    "hackernewsletter.com": "hot_trend",
    "hnrss.org": "hot_trend",
    "news.ycombinator.com": "hot_trend",
    "github.blog": "hot_trend",
    "techcrunch.com": "hot_trend",
    "thenewstack.io": "hot_trend",
    "infoq.com": "hot_trend",
    "infoq.cn": "hot_trend",
    "36kr.com": "hot_trend",
    "ithome.com": "hot_trend",
    "sspai.com": "hot_trend",
    "theverge.com": "hot_trend",
    "arstechnica.com": "hot_trend",
    "wired.com": "hot_trend",
    "bleepingcomputer.com": "hot_trend",
    "thehackernews.com": "hot_trend",
    "openai.com": "hot_trend",
    "anthropic.com": "hot_trend",
    "blog.google": "hot_trend",
    "blogs.microsoft.com": "hot_trend",
    "aws.amazon.com": "hot_trend",
    "cloud.google.com": "hot_trend",
    "meta.ai": "hot_trend",
    # 技术文章
    "lobste.rs": "tech_article",
    "stackoverflow.com": "tech_article",
    "juejin.cn": "tech_article",
    "segmentfault.com": "tech_article",
    "csdn.net": "tech_article",
    "blog.csdn.net": "tech_article",
    "zhihu.com": "tech_article",
    "v2ex.com": "tech_article",
    "ruanyifeng.com": "tech_article",
    "martinfowler.com": "tech_article",
    "medium.com": "tech_article",
    "towardsdatascience.com": "tech_article",
    "freecodecamp.org": "tech_article",
    "baeldung.com": "tech_article",
    "digginginto.dev": "tech_article",
    "iximiuz.com": "tech_article",
    "mysql.com": "tech_article",
    "redis.io": "tech_article",
    "postgresql.org": "tech_article",
    "docs.spring.io": "tech_article",
    "kubernetes.io": "tech_article",
}

# URL 路径级分类规则（优先于域名级匹配）
_PATH_CATEGORY_RULES: list[tuple[re.Pattern, str]] = [
    # GitHub：博客/文档 → 技术文章
    (re.compile(r'github\.com/[^/]+/[^/]+/(?:blob|tree)/main/(?:docs?|blog|posts?|_posts)'), "tech_article"),
    # GitHub：Issues/Discussions → 技术文章
    (re.compile(r'github\.com/[^/]+/[^/]+/(?:issues|discussions)/\d+'), "tech_article"),
    # GitHub：Releases → 开源项目
    (re.compile(r'github\.com/[^/]+/[^/]+/releases/tag/'), "open_source"),
    # Medium：文章 → 技术文章
    (re.compile(r'medium\.com/[^/]+/(?:[^/]+-)?[a-f0-9]{8,}'), "tech_article"),
    # Reddit：帖子 → 热点动态
    (re.compile(r'reddit\.com/r/\w+/comments/'), "hot_trend"),
]

_TITLE_PATTERNS: list[tuple] = [
    # 学术论文（优先匹配，避免 "paper" 出现在其他上下文被误匹配）
    (re.compile(r'(?:论文|(?:paper|arxiv)\b)'), "paper"),
    # 开源项目（版本发布归入开源而非热点）
    (re.compile(r'(?:开源|open[- ]?source)\s*(?:项目|库|工具|release|发布)'), "open_source"),
    (re.compile(r'(?:github\s+(?:trending|starred|release)|awesome\s+\w+|(?:npm|pypi|cargo)\s+(?:publish|release))'), "open_source"),
    # 版本发布归入开源（v?\d+\.\d+ 版本号模式）
    (re.compile(r'(?:release[d]?|发布|launch|新版本|新功能)\b.*?(?:v?\d+\.\d+)'), "open_source"),
    # AI 相关动态（精确边界匹配，避免 "动态规划" 误匹配；注意 title 已 .lower()）
    (re.compile(r'(?:\b(?:llm|gpt|claude|gemini|qwen|sora|ai\s*agent|rag|embedding|transformer|diffusion|multimodal|agi|o1|o3|o4|deepseek|qwen2|mistral|llama)\b|大\s*模型|语言模型|深度学习|机器学习|神经网络)'), "hot_trend"),
    # 开发工具（title 已 .lower()，所有英文模式用小写）
    (re.compile(r'(?:工具推荐|开发工具|(?:devtool|插件|extension|vscode|编辑器|ide|终端|shell|docker|k8s|kubernetes)\b)'), "dev_tool"),
    # 技术文章（放后面，避免抢先匹配 "教程" 等泛词）
    (re.compile(r'(?:教程|指南|(?:best\s*practice)\b|入门|进阶|原理分析|源码解析|实战|踩坑|避坑)'), "tech_article"),
    # 创意发现（"有趣" 需搭配名词，避免 "有趣的现象" 等泛用误匹配）
    (re.compile(r'(?:创意|有趣\s*(?:项目|工具|实验|应用|想法|发现|库)|(?:hackathon)\b)'), "creative"),
]


def _extract_domain(url: str) -> str:
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return ""


def infer_category(url: str, title: str) -> str:
    """基于 URL 路径 → 域名 → 标题词边界匹配的分类推断

    优先级：路径级匹配 > 域名精确匹配 > 标题正则匹配。
    避免"动态规划"→hot_trend、"toolbar"→dev_tool 等误分类。
    """
    # 0. URL 路径级匹配（最高优先）
    for pattern, category in _PATH_CATEGORY_RULES:
        if pattern.search(url):
            return category

    # 1. 域名精确匹配
    domain = _extract_domain(url)
    if domain in _SOURCE_CATEGORY_MAP:
        return _SOURCE_CATEGORY_MAP[domain]

    # 2. 标题正则匹配（带词边界）
    title_lower = (title or "").lower()
    for pattern, category in _TITLE_PATTERNS:
        if pattern.search(title_lower):
            return category

    return "tech_article"


# 板块配置内存缓存（TTL=5分钟，避免每次日报任务重复 HTTP 请求）
_sections_cache: dict = {"data": None, "expires": 0.0}
_SECTIONS_CACHE_TTL = 300
_DIGEST_SECTION_MAX_ITEMS_CAP = 6
_DIGEST_RSS_MAX_ENTRIES_CAP = 3

_DIGEST_KEYWORD_EXPANSIONS: dict[tuple[str, str], list[str]] = {
    ("hot_trend", "ai llm news today"): [
        "AI security vulnerability developer impact",
        "LLM model release API developer update",
        "GitHub Copilot coding agent developer news",
    ],
    ("tech_article", "tech blog deep dive engineering"): [
        "site:github.blog/engineering architecture performance",
        "site:cloudflare.com/blog reliability performance engineering",
        "site:netflixtechblog.com architecture scalability",
        "software architecture scalability performance engineering case study",
    ],
}

_DIGEST_CATEGORY_FALLBACK_KEYWORDS: dict[str, str] = {
    "hot_trend": "AI OR LLM OR developer news OR technology trend",
    "open_source": "GitHub trending OR open source release OR developer tool",
    "tech_article": "engineering deep dive OR architecture performance OR best practice",
    "dev_tool": "developer tool OR productivity tool OR IDE extension",
    "creative": "creative coding OR interesting developer project OR AI experiment",
    "paper": "AI paper OR systems paper OR machine learning research",
}


def _fallback_section_keyword(category: str) -> str:
    """URL/RSS-only sections still need a keyword for planning/evaluation fallback."""
    return _DIGEST_CATEGORY_FALLBACK_KEYWORDS.get(
        category,
        f"{category} technology update",
    )


def _expand_digest_keyword(category: str, keyword: str) -> list[str]:
    """Expand known overly broad digest keywords into high-signal queries."""
    normalized = re.sub(r"\s+", " ", (keyword or "").strip().lower())
    expanded = _DIGEST_KEYWORD_EXPANSIONS.get((category or "", normalized))
    if expanded:
        return expanded
    return [keyword]


def invalidate_digest_sections_cache():
    """清空日报板块配置缓存。"""
    global _sections_cache
    _sections_cache = {"data": None, "expires": 0.0}


async def get_digest_sections(force_refresh: bool = False) -> list[dict]:
    """获取日报板块配置（优先 Java 订阅源 API，回退到本地配置，带 TTL 缓存）"""
    global _sections_cache
    if (
        not force_refresh
        and _sections_cache["data"] is not None
        and time.time() < _sections_cache["expires"]
    ):
        return _sections_cache["data"]

    result = await _fetch_digest_sections()
    if result:
        _sections_cache = {"data": result, "expires": time.time() + _SECTIONS_CACHE_TTL}
    return result


async def _fetch_digest_sections() -> list[dict]:
    """实际获取日报板块配置（无缓存）"""
    # 1. 尝试从 Java 后端拉取活跃订阅源
    java_url = settings.java_api_url
    if java_url:
        try:
            import httpx
            headers = {"Content-Type": "application/json"}
            if settings.callback_api_key:
                headers["X-Callback-Key"] = settings.callback_api_key
            async with httpx.AsyncClient(timeout=settings.sources_api_timeout) as client:
                resp = await client.get(f"{java_url}/api/internal/collector/sources", headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    sources = data.get("data", [])
                    if sources:
                        sections = _sources_to_sections(sources)
                        if sections:
                            logger.info("Loaded %d sections from Java sources API", len(sections))
                            return sections
        except Exception as e:
            logger.warning("Failed to fetch sources from Java API: %s", e)

    # 2. 回退到本地配置
    config_str = os.getenv("DIGEST_SECTIONS", "") or settings.digest_sections
    if config_str:
        try:
            return json.loads(config_str)
        except Exception as e:
            logger.warning("Failed to parse DIGEST_SECTIONS JSON: %s", e)
    return []


def _sources_to_sections(sources: list[dict]) -> list[dict]:
    """将 Java 订阅源转换为日报 section 格式，支持 keyword/url/rss 三种类型。

    按 contentCategory 分组：同分类的多源合并为一个 section。
    """
    # 1. 按 contentCategory 分组
    groups: dict[str, dict] = {}
    kw_freshness: dict[str, list[int]] = {}      # keyword 源的 freshness（独立计算 time_range）
    all_freshness: dict[str, list[int]] = {}      # 所有源的 freshness
    max_pages_list: dict[str, list[int]] = {}

    for src in sources:
        src_value = src.get("value")
        if not src_value:
            logger.debug("Skipping source %s: missing 'value' field", src.get("id", "?"))
            continue
        cat = src.get("contentCategory") or infer_category(src_value, src.get("name", ""))
        group = groups.setdefault(cat, {"keywords": [], "url_sources": [], "rss_sources": []})
        kw_freshness.setdefault(cat, [])
        all_freshness.setdefault(cat, [])
        max_pages_list.setdefault(cat, [])

        src_type = src.get("type", "keyword")
        sc = src.get("successCount", 0) or 0
        fc = src.get("failCount", 0) or 0
        total_runs = sc + fc
        src_dead = total_runs >= 3 and (sc / total_runs if total_runs > 0 else 0) < 0.2
        effectiveness = {
            "success_count": sc,
            "fail_count": fc,
            "avg_quality_score": src.get("avgQualityScore", 0) or 0,
            "last_result_count": src.get("lastResultCount", 0) or 0,
            "last_run_at": src.get("lastRunAt"),
            "success_rate": round(sc / total_runs, 2) if total_runs > 0 else 0,
            "dead": src_dead,
        }
        if src_type == "keyword":
            for keyword_value in _expand_digest_keyword(cat, src_value):
                group["keywords"].append({
                    "value": keyword_value,
                    "source_id": src.get("id"),
                    "source_name": src.get("name", ""),
                    "effectiveness": effectiveness,
                })
        elif src_type == "url":
            group["url_sources"].append({
                "url": src_value,
                "crawl_mode": src.get("crawlMode", "single"),
                "max_depth": src.get("maxDepth", 1),
                "max_pages": src.get("maxPages", 10),
                "source_id": src.get("id"),
                "source_name": src.get("name", ""),
                "effectiveness": effectiveness,
            })
        elif src_type == "rss":
            max_entries = src.get("maxPages", 10) or 10
            group["rss_sources"].append({
                "feed_url": src_value,
                "freshness_hours": src.get("freshnessHours", 24),
                "max_entries": min(max_entries, _DIGEST_RSS_MAX_ENTRIES_CAP),
                "source_id": src.get("id"),
                "source_name": src.get("name", ""),
                "effectiveness": effectiveness,
            })

        fh = src.get("freshnessHours", 24)
        if fh:
            all_freshness[cat].append(fh)
            if src_type == "keyword":
                kw_freshness[cat].append(fh)
        mp = src.get("maxPages", 10)
        if mp:
            max_pages_list[cat].append(mp)

    # 2. 每组生成一个 section
    sections = []
    for cat, group in groups.items():
        if not group["keywords"] and not group["url_sources"] and not group["rss_sources"]:
            continue

        has_kw = bool(group["keywords"])
        has_url = bool(group["url_sources"])
        has_rss = bool(group["rss_sources"])

        source_type = "keyword"
        if (has_url and has_kw) or (has_url and has_rss) or (has_kw and has_rss):
            source_type = "mixed"
        elif has_url:
            source_type = "url"
        elif has_rss:
            source_type = "rss"

        section: dict = {
            "name": cat,
            "source_type": source_type,
            "max_items": min(
                max(max_pages_list.get(cat, [5])),
                _DIGEST_SECTION_MAX_ITEMS_CAP,
            ) if max_pages_list.get(cat) else 5,
        }

        if has_kw:
            kw_parts = [k["value"] for k in group["keywords"]]
            merged = " OR ".join(kw_parts)
            # 搜索引擎查询长度限制：超过 500 字符截断到前 N 个关键词
            if len(merged) > 500:
                truncated = []
                total_len = 0
                for kw in kw_parts:
                    if total_len + len(kw) + (4 if truncated else 0) > 480:
                        break
                    truncated.append(kw)
                    total_len += len(kw) + 4
                merged = " OR ".join(truncated)
                logger.info("Keyword merge truncated for section '%s': %d -> %d chars", cat, len(" OR ".join(kw_parts)), len(merged))
            section["keyword"] = merged
        else:
            section["keyword"] = _fallback_section_keyword(cat)

        # keyword 板块的 time_range 从 keyword 源独立计算（不受 RSS/URL freshness 影响）
        if has_kw and kw_freshness.get(cat):
            min_kw_fh = min(kw_freshness[cat])
            section["time_range"] = _freshness_to_time_range(min_kw_fh)
        elif all_freshness.get(cat):
            min_fh = min(all_freshness[cat])
            section["time_range"] = _freshness_to_time_range(min_fh)

        if has_url:
            section["url_sources"] = group["url_sources"]
        if has_rss:
            section["rss_sources"] = group["rss_sources"]
        if has_kw:
            section["keyword_details"] = group["keywords"]

        section["effectiveness"] = _compute_section_effectiveness(group)
        sections.append(section)
    return sections


def _compute_section_effectiveness(group: dict) -> dict:
    """从板块内各信息源聚合效能数据（含 keyword/url/rss）。"""
    kw_sources = group.get("keywords", [])
    all_sources = (
        [{"effectiveness": k.get("effectiveness", {})} for k in kw_sources if isinstance(k, dict)]
        + group.get("url_sources", [])
        + group.get("rss_sources", [])
    )
    if not all_sources:
        return {"avg_quality": 0, "success_rate": 0, "total_runs": 0, "dead": False}

    qualities = []
    successes = 0
    failures = 0
    for src in all_sources:
        eff = src.get("effectiveness", {})
        q = eff.get("avg_quality_score", 0)
        if q > 0:
            qualities.append(q)
        successes += eff.get("success_count", 0)
        failures += eff.get("fail_count", 0)

    avg_quality = sum(qualities) / len(qualities) if qualities else 0
    total = successes + failures
    success_rate = successes / total if total > 0 else 0
    dead = total >= 3 and success_rate < 0.2

    return {
        "avg_quality": round(avg_quality, 1),
        "success_rate": round(success_rate, 2),
        "total_runs": total,
        "dead": dead,
    }


def _freshness_to_time_range(hours: int) -> str:
    if hours <= 24:
        return "day"
    if hours <= 168:
        return "week"
    if hours <= 720:
        return "month"
    return "year"


def copy_config(config):
    """深拷贝 CrawlConfig"""
    from api.crawl import CrawlConfig
    if config is None:
        return CrawlConfig()
    return config.model_copy(deep=True)


# 全局单例
executor = TaskExecutor(max_concurrent=settings.max_concurrent_tasks)
