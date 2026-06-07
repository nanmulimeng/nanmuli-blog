"""关键词任务处理器 — 关键词搜索 + AI 优化 + 自动优化循环

从 TaskExecutor 拆分，负责关键词类型任务的完整处理流程。
"""

import asyncio
import logging
import time

from config import settings
from standalone import repository as repo

logger = logging.getLogger(__name__)


class KeywordTaskHandler:
    """关键词任务处理器：搜索 + AI 关键词优化/扩展 + 优化循环"""

    def __init__(self, repository=None):
        self.repo = repository

    def _repo(self):
        return self.repo or repo

    async def execute(self, task: dict, config) -> list:
        """执行关键词搜索爬取（含 AI 关键词优化/扩展 + 自动优化）"""
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
        await self._repo().save_ai_search_metadata(task["id"], {
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
        from crawler.dependencies import get_async_web_crawler

        evaluator = CoverageEvaluator(organizer if organizer.is_available else None)
        depth_gen = DepthStrategyGen()
        breadth_gen = BreadthStrategyGen()
        kb = KnowledgeBase()
        breaker = BubbleBreaker(organizer if organizer.is_available else None)

        browser_config = await get_browser_config(
            text_mode=True, light_mode=True, proxy=settings.proxy_url,
        )
        AsyncWebCrawler = get_async_web_crawler()
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
