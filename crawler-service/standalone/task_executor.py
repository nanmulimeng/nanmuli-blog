"""异步任务执行器（爬取 + AI 整理）"""

import asyncio
import json
import logging
import os
import re
import time
import uuid
from typing import Dict

from config import settings
from ai.config import ai_settings
from standalone.models import TaskStatus
from standalone import repository as repo
from standalone.db import task_scoped_db

logger = logging.getLogger(__name__)


async def _fire_callback(task_id: int, status: int):
    """任务完成/失败后通知 Java 后端（指数退避重试，最多 3 次）"""
    url = settings.callback_url
    if not url:
        return

    payload = {"python_task_id": task_id, "status": status}
    headers = {"Content-Type": "application/json"}
    if settings.callback_api_key:
        headers["X-Callback-Key"] = settings.callback_api_key

    import httpx
    async with httpx.AsyncClient(timeout=settings.callback_timeout) as client:
        for attempt in range(3):
            try:
                resp = await client.post(url, json=payload, headers=headers)
                if 200 <= resp.status_code < 300:
                    logger.info("Callback fired: task_id=%d status=%d -> %d (attempt=%d)",
                                task_id, status, resp.status_code, attempt + 1)
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
                await _fire_callback(task_id, TaskStatus.FAILED)
                return

            # 质量过滤（所有任务类型，日报使用宽松阈值）
            # 日报任务已在 execute_digest_crawl() 内做过去重，跳过 SimHash 二次去重
            is_digest = task["task_type"] == "digest"
            # 日报任务：预热来源可信度缓存，避免后续同步 HTTP 阻塞事件循环
            if is_digest:
                try:
                    from crawler.quality import SourceAuthority
                    await SourceAuthority.preload_authority_cache()
                except Exception:
                    pass
            from crawler.dedup import DedupEngine
            if is_digest:
                dedup_engine = None
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
        finally:
            # 通知信息源调度器：任务已完成（无论成功/失败）
            try:
                from standalone.scheduler import notify_task_completion
                notify_task_completion(task_id)
            except Exception:
                pass

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
        """先广后深优化：广度扩展 → 深度优化"""
        from ai import content_organizer as organizer
        from optimization.evaluator import CoverageEvaluator
        from optimization.strategy import DepthStrategyGen, BreadthStrategyGen
        from optimization.feedback import FeedbackLoop
        from optimization.bubble_breaker import BreadthExpander, BubbleBreaker
        from optimization.knowledge_base import KnowledgeBase
        from crawler.search import crawl_by_keyword
        from crawler.config import get_browser_config
        from crawl4ai import AsyncWebCrawler

        evaluator = CoverageEvaluator(organizer if organizer.is_available else None)
        depth_gen = DepthStrategyGen()
        breadth_gen = BreadthStrategyGen()
        kb = KnowledgeBase()
        breaker = BubbleBreaker(organizer if organizer.is_available else None)

        browser_config = await get_browser_config(
            text_mode=True, light_mode=True, proxy=settings.proxy_url,
        )
        async with AsyncWebCrawler(config=browser_config) as shared_crawler:
            ctx = {"engine": engine, "time_range": time_range, "config": config, "crawler": shared_crawler}
            deadline = time.monotonic() + settings.optimization_total_budget_seconds

            # Phase 1: 广度扩展（先广）
            breadth_expander = BreadthExpander(
                evaluator=evaluator,
                strategy_gen=breadth_gen,
                knowledge_base=kb,
                bubble_breaker=breaker,
            )
            results, breadth_rounds = await breadth_expander.execute(
                keyword=keyword,
                initial_results=initial_results,
                crawl_fn=crawl_by_keyword,
                task_id=task["id"],
                context=ctx,
                deadline=deadline,
            )
            if breadth_rounds:
                last = breadth_rounds[-1]
                logger.info(
                    "[Optimization] Breadth: %d rounds, breadth_score=%.2f, total URLs=%d",
                    len(breadth_rounds), BreadthExpander._breadth_score(last.evaluation), last.urls_after,
                )

            # Phase 2: 深度优化（后深）
            last_breadth_eval = breadth_rounds[-1].evaluation if breadth_rounds else None

            depth_loop = FeedbackLoop(
                evaluator=evaluator,
                strategy_gen=depth_gen,
                knowledge_base=kb,
            )
            final_results, depth_rounds = await depth_loop.execute(
                keyword=keyword,
                initial_results=results,
                crawl_fn=crawl_by_keyword,
                task_id=task["id"],
                context=ctx,
                initial_evaluation=last_breadth_eval,
                deadline=deadline,
            )

            if depth_rounds:
                last = depth_rounds[-1]
                logger.info(
                    "[Optimization] Depth: %d rounds, final score=%.2f, total URLs=%d",
                    len(depth_rounds), last.evaluation.overall_score, last.urls_after,
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
                # 截断不等于失败——增大 max_tokens 重试一次（直接传参，不修改全局状态）
                logger.warning("Task %d AI truncated, retrying with larger max_tokens: %s",
                               task_id, e)
                try:
                    original_max = ai_settings.ai_digest_max_tokens
                    retry_max_tokens = int(original_max * 1.5)
                    if task_type == "digest":
                        result = await organize_digest_and_save(
                            task_id, task, pages, organizer,
                            max_tokens_override=retry_max_tokens,
                        )
                    else:
                        result = await organize_content_and_save(
                            task_id, task, pages, organizer,
                            max_tokens_override=retry_max_tokens,
                        )
                    logger.info("Task %d AI re-organized after truncation recovery: title='%s'",
                                task_id, result.title)
                    return True
                except Exception as retry_err:
                    msg = f"AI 输出被截断且重试失败，原始爬取结果已保留：{retry_err}"
                    logger.warning("Task %d AI truncation retry also failed: %s", task_id, retry_err)
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
                backoff = settings.ai_rate_limit_backoff_ms / 1000.0 * (attempt + 1)
                logger.warning("Task %d AI rate limited, retry in %.1fs (attempt %d/%d)",
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
        page_classifier = None
        if settings.page_classifier_enabled:
            from crawler.page_classifier import classify_page as _classify
            page_classifier = _classify

        is_deep = (task_type == "deep")
        is_digest = (task_type == "digest")
        deep_min_score = settings.deep_eval_review_threshold
        # 日报独立质量阈值：比 deep 更严格，避免低质量内容浪费 AI token
        digest_min_score = getattr(settings, 'digest_eval_reject_threshold', 35)

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
                if source_level == "spam":
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
    """将 Java 订阅源转换为日报 section 格式，支持 keyword/url/rss 三种类型。

    按 contentCategory 分组：同分类的多源合并为一个 section。
    """
    # 1. 按 contentCategory 分组
    groups: dict[str, dict] = {}
    freshness_hours_list: dict[str, list[int]] = {}
    max_pages_list: dict[str, list[int]] = {}

    for src in sources:
        cat = src.get("contentCategory") or "tech_article"
        group = groups.setdefault(cat, {"keywords": [], "url_sources": [], "rss_sources": []})
        freshness_hours_list.setdefault(cat, [])
        max_pages_list.setdefault(cat, [])

        src_type = src.get("type", "keyword")
        effectiveness = {
            "source_id": src.get("id"),
            "success_count": src.get("successCount", 0) or 0,
            "fail_count": src.get("failCount", 0) or 0,
            "avg_quality_score": src.get("avgQualityScore", 0) or 0,
            "last_result_count": src.get("lastResultCount", 0) or 0,
        }
        if src_type == "keyword":
            group["keywords"].append(src["value"])
        elif src_type == "url":
            group["url_sources"].append({
                "url": src["value"],
                "crawl_mode": src.get("crawlMode", "single"),
                "max_depth": src.get("maxDepth", 1),
                "max_pages": src.get("maxPages", 10),
                "source_id": src.get("id"),
                "source_name": src.get("name", ""),
                "effectiveness": effectiveness,
            })
        elif src_type == "rss":
            group["rss_sources"].append({
                "feed_url": src["value"],
                "freshness_hours": src.get("freshnessHours", 24),
                "max_entries": src.get("maxPages", 10) or 10,
                "source_id": src.get("id"),
                "source_name": src.get("name", ""),
                "effectiveness": effectiveness,
            })

        fh = src.get("freshnessHours", 24)
        if fh:
            freshness_hours_list[cat].append(fh)
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
        if has_url and has_kw or has_url and has_rss or has_kw and has_rss:
            source_type = "mixed"
        elif has_url:
            source_type = "url"
        elif has_rss:
            source_type = "rss"

        section: dict = {
            "name": cat,
            "source_type": source_type,
            "max_items": max(max_pages_list.get(cat, [5])) if max_pages_list.get(cat) else 5,
        }

        if has_kw:
            section["keyword"] = " OR ".join(group["keywords"])

        if freshness_hours_list.get(cat):
            min_fh = min(freshness_hours_list[cat])
            section["time_range"] = _freshness_to_time_range(min_fh)

        if has_url:
            section["url_sources"] = group["url_sources"]
        if has_rss:
            section["rss_sources"] = group["rss_sources"]

        section["effectiveness"] = _compute_section_effectiveness(group)
        sections.append(section)
    return sections


def _compute_section_effectiveness(group: dict) -> dict:
    """从板块内各信息源聚合效能数据。"""
    all_sources = group.get("url_sources", []) + group.get("rss_sources", [])
    if not all_sources:
        return {"avg_quality": 0, "success_rate": 0, "total_runs": 0, "dead": True}

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
