"""关键词任务处理器 — 关键词搜索 + AI 优化 + 自动优化循环

从 TaskExecutor 拆分，负责关键词类型任务的完整处理流程。
"""

import asyncio
import logging

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

        # C06-07: 已废弃 keyword 自动优化循环（与 digest OptimizationAgent 双轨漂移；
        # optimization 默认关 + keyword 为辅助能力，废弃消除漂移，回退为单次搜索采集）
        return all_results[:max_pages]

    # C06-08: _run_optimization_loop 已删除（keyword 优化循环 C06-07 废弃，
    # FeedbackLoop 死代码清理；digest 的 OptimizationAgent 保留独立编排）
