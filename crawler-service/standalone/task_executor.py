"""异步任务执行器（爬取 + AI 整理）"""

import asyncio
import json
import logging
import os
import uuid
from typing import Dict

from config import settings
from ai.config import ai_settings
from standalone.models import TaskStatus
from standalone import repository as repo
from standalone.db import task_scoped_db

logger = logging.getLogger(__name__)


async def _fire_callback(task_id: int, status: int):
    """任务完成/失败后通知 Java 后端（fire-and-forget）"""
    url = settings.callback_url
    if not url:
        return

    payload = {"python_task_id": task_id, "status": status}
    headers = {"Content-Type": "application/json"}
    if settings.callback_api_key:
        headers["X-Callback-Key"] = settings.callback_api_key

    try:
        import httpx
        async with httpx.AsyncClient(timeout=settings.callback_timeout) as client:
            resp = await client.post(url, json=payload, headers=headers)
            logger.info("Callback fired: task_id=%d status=%d -> %d", task_id, status, resp.status_code)
    except Exception as e:
        logger.warning("Callback failed (non-critical): task_id=%d error=%s", task_id, e)


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
        from api.crawl import CrawlConfig
        from crawl4ai import AsyncWebCrawler

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

            # ========== Phase 1: 爬取 ==========
            if task["task_type"] == "single":
                browser_config = await get_browser_config(
                    text_mode=params.text_mode, light_mode=params.light_mode,
                    proxy=settings.proxy_url,
                )
                async with AsyncWebCrawler(config=browser_config) as crawler:
                    result = await crawl_single_page(url=task["source_url"], config=config, crawler=crawler)
                results = [result]

            elif task["task_type"] == "deep":
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
                results = await self._execute_keyword_crawl(task, config)

            elif task["task_type"] == "digest":
                from crawler.digest import execute_digest_crawl
                results = await execute_digest_crawl(task, config, self)

            else:
                await repo.fail_task(task_id, f"Unknown task type: {task['task_type']}")
                return

            # 质量过滤（日报跳过：来源已由搜索结果保证质量）
            if task["task_type"] != "digest":
                from crawler.dedup import DedupEngine
                sim_threshold = settings.content_dedup_deep_threshold if task["task_type"] == "deep" else settings.content_dedup_simhash_threshold
                dedup_engine = DedupEngine(simhash_threshold=sim_threshold) if settings.content_dedup_enabled else None
                results = self._filter_low_quality(results, task["task_type"], dedup_engine=dedup_engine)

            # 保存爬取结果
            total_words = await repo.save_pages(task_id, results)

            success_count = sum(1 for r in results if r.success)
            crawl_duration = sum(r.crawl_time_ms for r in results)

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
                ai_success = await self._organize_with_ai(task_id, task)
                if not ai_success:
                    logger.warning("Task %d AI organization failed, task still marked complete with raw content.", task_id)
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

    async def _execute_keyword_crawl(self, task: dict, config) -> list:
        """关键词搜索爬取（含 AI 关键词优化/扩展）"""
        from ai import content_organizer as organizer
        from crawler.search import crawl_by_keyword

        keyword = task["keyword"]
        engine = task.get("search_engine", "sogou")
        max_pages = task.get("max_pages", 10)
        time_range = task.get("time_range", "week")

        keywords = [keyword]
        optimized_keyword = None

        # AI 关键词优化
        if organizer.is_available:
            try:
                optimized = await organizer.optimize_keyword(keyword)
                if optimized and optimized != keyword:
                    optimized_keyword = optimized
                    keywords = [optimized]
                    logger.info("Keyword optimized: '%s' -> '%s'", keyword, optimized)
            except Exception as e:
                logger.warning("Keyword optimization failed: %s", e)

            # AI 关键词扩展
            try:
                expanded = await organizer.expand_keywords(keywords[0])
                for kw in expanded:
                    if kw.lower() not in {k.lower() for k in keywords}:
                        keywords.append(kw)
                        if len(keywords) >= settings.keyword_max_variants:
                            break
                logger.info("Keywords expanded to %d variants: %s", len(keywords), keywords)
            except Exception as e:
                logger.warning("Keyword expansion failed: %s", e)

        # 保存 AI 搜索元数据
        await repo.save_ai_search_metadata(task["id"], {
            "originalKeyword": keyword,
            "optimizedKeyword": optimized_keyword,
            "searchVariants": keywords,
        })

        # 对每个关键词搜索，合并去重
        seen_urls = set()
        all_results = []
        consecutive_no_new = 0

        for kw in keywords:
            before = len(all_results)
            try:
                results = await crawl_by_keyword(
                    keyword=kw, engine=engine,
                    max_results=max(8, max_pages),
                    time_range=time_range, config=config
                )
                from crawler.utils import dedup_results_into
                dedup_results_into(results, seen_urls, all_results)

                new = len(all_results) - before
                logger.info("Keyword '%s' added %d new URLs (total=%d/%d)",
                            kw, new, len(all_results), max_pages)

                if len(keywords) > 1 and new == 0:
                    consecutive_no_new += 1
                    if consecutive_no_new >= settings.keyword_max_consecutive_empty:
                        break
                else:
                    consecutive_no_new = 0

                if len(all_results) >= max_pages:
                    break

                if len(keywords) > 1:
                    await asyncio.sleep(settings.keyword_inter_search_delay)

            except Exception as e:
                logger.warning("Keyword search failed for '%s': %s", kw, e)

        # === 自动优化循环 ===
        if settings.optimization_enabled and settings.optimization_mode in ("keyword", "both"):
            all_results = await self._run_optimization_loop(
                task=task,
                initial_results=all_results,
                keyword=keywords[0],
                engine=engine,
                time_range=time_range,
                config=config,
            )

        return all_results[:max_pages]

    async def _run_optimization_loop(
        self, task: dict, initial_results: list,
        keyword: str, engine: str, time_range: str, config,
    ) -> list:
        """执行自动优化反馈循环"""
        from ai import content_organizer as organizer
        from optimization.evaluator import CoverageEvaluator
        from optimization.strategy import StrategyGenerator
        from optimization.feedback import FeedbackLoop
        from optimization.knowledge_base import KnowledgeBase
        from optimization.bubble_breaker import BubbleBreaker
        from crawler.search import crawl_by_keyword

        evaluator = CoverageEvaluator(organizer if organizer.is_available else None)
        strategy_gen = StrategyGenerator()
        kb = KnowledgeBase()
        breaker = BubbleBreaker(organizer if organizer.is_available else None)

        loop = FeedbackLoop(
            evaluator=evaluator,
            strategy_gen=strategy_gen,
            knowledge_base=kb,
            bubble_breaker=breaker,
        )

        final_results, rounds = await loop.execute(
            keyword=keyword,
            initial_results=initial_results,
            crawl_fn=crawl_by_keyword,
            task_id=task["id"],
            context={
                "engine": engine,
                "time_range": time_range,
                "config": config,
            },
        )

        if rounds:
            last = rounds[-1]
            logger.info(
                "[Optimization] Completed: %d rounds, final score=%.2f, total URLs=%d",
                len(rounds), last.evaluation.overall_score, last.urls_after,
            )

        return final_results

    async def _organize_with_ai(self, task_id: int, task: dict) -> bool:
        """AI 内容整理（含重试）"""
        from ai import content_organizer as organizer
        from ai.organizer import (
            OrganizerError, RateLimitError, TruncatedError, UnrecoverableError, InvalidOutputError,
        )
        from standalone.organizer_helper import organize_content_and_save, organize_digest_and_save

        if not organizer.is_available:
            logger.info("AI not configured, skipping organization for task %d", task_id)
            await repo.save_ai_error(task_id, "AI 未配置")
            return False

        task_type = task["task_type"]
        max_retries = ai_settings.ai_max_retries

        pages = await repo.get_pages_by_task(task_id)
        if not pages or not any(p.get("crawl_status") == 2 and p.get("raw_markdown") for p in pages):
            await repo.save_ai_error(task_id, "没有成功的页面可供 AI 整理")
            return False

        for attempt in range(max_retries + 1):
            try:
                if task_type == "digest":
                    result = await organize_digest_and_save(task_id, task, pages, organizer)
                else:
                    result = await organize_content_and_save(task_id, task, pages, organizer)

                logger.info("Task %d AI organized: title='%s', duration=%dms, tokens=%d",
                            task_id, result.title, result.duration_ms, result.tokens_used)
                return True

            except TruncatedError as e:
                msg = f"AI 输出被截断，请调整内容长度或增加 max_tokens：{e}"
                logger.warning("Task %d AI truncated: %s, skipping retry", task_id, e)
                await repo.save_ai_error(task_id, msg)
                return False

            except UnrecoverableError as e:
                msg = f"AI API 请求被拒绝：{e}"
                logger.warning("Task %d AI unrecoverable: %s, skipping retry", task_id, e)
                await repo.save_ai_error(task_id, msg)
                return False

            except InvalidOutputError as e:
                msg = f"AI 输出格式校验失败：{e}"
                logger.warning("Task %d AI invalid output: %s, skipping retry", task_id, e)
                await repo.save_ai_error(task_id, msg)
                return False

            except RateLimitError as e:
                backoff = 10.0
                logger.warning("Task %d AI rate limited, retry in %.0fs (attempt %d/%d)",
                               task_id, backoff, attempt + 1, max_retries + 1)
                if attempt < max_retries:
                    await asyncio.sleep(backoff)
                    continue
                await repo.save_ai_error(task_id, "AI API 频率限制，已重试仍失败，请稍后再试")

            except OrganizerError as e:
                backoff = 2 ** attempt
                logger.warning("Task %d AI error, retry in %ds (attempt %d/%d): %s",
                               task_id, backoff, attempt + 1, max_retries + 1, e)
                if attempt < max_retries:
                    await asyncio.sleep(backoff)
                    continue
                await repo.save_ai_error(task_id, f"AI 整理失败 (已重试 {max_retries} 次)：{e}")

            except Exception as e:
                logger.error("Task %d AI unexpected error: %s", task_id, e, exc_info=True)
                if attempt < max_retries:
                    await asyncio.sleep(2 ** attempt)
                    continue
                await repo.save_ai_error(task_id, f"AI 整理异常：{e}")

        return False

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

        is_deep = (task_type == "deep")
        deep_min_score = settings.deep_eval_review_threshold

        # 过滤统计
        stats = {"total": len(results), "too_short": 0, "non_article": 0,
                 "duplicate": 0, "low_quality": 0, "passed": 0}

        filtered = []
        for r in results:
            if not getattr(r, "success", False):
                filtered.append(r)
                continue

            url = getattr(r, "url", "")
            title = getattr(r, "title", "") or ""
            markdown = getattr(r, "markdown", "") or ""

            # [1] 内容太短直接标记失败
            min_content = settings.min_content_length if not is_deep else settings.filter_deep_min_content
            if len(markdown) < min_content:
                r.success = False
                r.error_message = f"Content too short ({len(markdown)} chars)"
                filtered.append(r)
                stats["too_short"] += 1
                continue

            # [2] 页面类型分类器（P5）：SERP/列表/论坛 → 直接拒绝
            if settings.page_classifier_enabled:
                from crawler.page_classifier import classify_page
                classification = classify_page(markdown, url, title)
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
            evaluation = evaluate_content(url, title, markdown)
            verdict = evaluation["verdict"]
            final_score = evaluation["final_score"]

            should_reject = False
            if is_deep:
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

def extract_source_name(url: str) -> str:
    if not url:
        return "未知来源"
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain or "未知来源"
    except Exception:
        return "未知来源"


def infer_category(url: str, title: str) -> str:
    lower = (url + " " + title).lower()
    if "github" in lower or "开源" in lower:
        return "open_source"
    if "arxiv" in lower or "论文" in lower or "paper" in lower:
        return "paper"
    if "tool" in lower or "工具" in lower:
        return "dev_tool"
    if "news" in lower or "新闻" in lower or "动态" in lower:
        return "hot_trend"
    if "creative" in lower or "创意" in lower or "有趣" in lower or "hackathon" in lower:
        return "creative"
    return "tech_article"


async def get_digest_sections() -> list[dict]:
    """获取日报板块配置（优先 Java 订阅源 API，回退到本地配置）"""
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
    """将 Java 订阅源转换为日报 section 格式（仅 keyword 类型）"""
    sections = []
    for src in sources:
        if src.get("type") != "keyword":
            continue
        category = src.get("contentCategory") or "tech_article"
        sections.append({
            "name": category,
            "keyword": src["value"],
            "time_range": _freshness_to_time_range(src.get("freshnessHours", 24)),
            "max_items": src.get("maxPages", 10),
        })
    return sections


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
