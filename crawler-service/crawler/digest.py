"""
日报爬取逻辑

从 TaskExecutor 提取的日报专用爬取、去重和优化逻辑。
"""

import asyncio
import logging

from config import settings

logger = logging.getLogger(__name__)


async def execute_digest_crawl(task: dict, config, task_executor) -> list:
    """日报板块爬取（含跨日去重，复用浏览器实例）

    Args:
        task: 任务字典
        config: 爬取配置
        task_executor: TaskExecutor 实例（用于调用 _filter_low_quality 等方法）

    Returns:
        去重后的 CrawlResult 列表
    """
    from crawler.search import crawl_by_keyword
    from crawler.dedup import dedup_results
    from crawler.config import get_browser_config, RunParams
    from standalone.task_executor import repo, get_digest_sections
    from crawl4ai import AsyncWebCrawler

    sections = await get_digest_sections()
    if not sections:
        raise ValueError("日报功能未配置")

    history_engine = await build_digest_history_engine()

    seen_urls = set()
    all_results = []
    engine = settings.digest_search_engine
    completed_count = 0

    params = RunParams(config)
    browser_config = await get_browser_config(
        text_mode=params.text_mode, light_mode=params.light_mode,
        proxy=settings.proxy_url,
    )
    async with AsyncWebCrawler(config=browser_config) as shared_crawler:
        for i, section in enumerate(sections):
            config_copy = _copy_config(config)

            try:
                results = await crawl_by_keyword(
                    keyword=section["keyword"],
                    engine=engine,
                    max_results=section.get("max_items", 5) * settings.digest_section_result_multiplier,
                    time_range=section.get("time_range", "week"),
                    config=config_copy,
                    crawler=shared_crawler,
                )

                results = dedup_results(results, history_engine=history_engine)

                from crawler.utils import dedup_results_into
                new = dedup_results_into(results, seen_urls, all_results)

                completed_count += new
                logger.info("Digest section '%s' added %d new URLs (total=%d)",
                            section["name"], new, len(all_results))

                await repo.update_task_progress(task["id"], completed_count)

                if i < len(sections) - 1:
                    await asyncio.sleep(settings.digest_inter_section_delay)

            except Exception as e:
                logger.warning("Digest section '%s' failed: %s", section["name"], e)

        # 日报自动优化（可选）
        if settings.optimization_enabled and settings.optimization_mode in ("digest", "both"):
            try:
                all_results = await run_digest_optimization(
                    task=task, all_results=all_results, seen_urls=seen_urls,
                    engine=engine, config=config, crawler=shared_crawler,
                )
            except Exception as e:
                logger.warning("Digest optimization failed (non-critical): %s", e)

    return all_results


async def build_digest_history_engine():
    """从最近几次成功日报中加载 URL/标题/内容指纹，用于跨日去重"""
    from crawler.dedup import DedupEngine
    from standalone.task_executor import repo
    from standalone.models import TaskStatus

    engine = DedupEngine()
    try:
        records, _ = await repo.list_tasks(task_type="digest", page=1, size=5)
        loaded = 0
        for r in records:
            if r.get("status") != TaskStatus.COMPLETED:
                continue
            pages = await repo.get_pages_by_task(r["id"])
            for p in pages:
                url = p.get("url", "")
                title = p.get("page_title", "")
                content = p.get("raw_markdown", "")
                if url:
                    engine.add_reference(url, title=title, content=content)
            logger.info("Loaded %d history URLs from digest task %d", len(pages), r["id"])
            loaded += 1
            if loaded >= settings.digest_history_load_count:
                break
        if loaded:
            logger.info("Digest history engine: %d reference records loaded", loaded)
    except Exception as e:
        logger.warning("Failed to load digest history for dedup: %s", e)
    return engine


async def run_digest_optimization(
    task: dict, all_results: list, seen_urls: set,
    engine: str, config, crawler,
) -> list:
    """对日报整体结果执行覆盖度评估和补充搜索"""
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
    loop = FeedbackLoop(evaluator, strategy_gen, kb, bubble_breaker=breaker)

    final_results, rounds = await loop.execute(
        keyword=task.get("keyword", "digest"),
        initial_results=all_results,
        crawl_fn=crawl_by_keyword,
        task_id=task["id"],
        context={
            "engine": engine,
            "time_range": "week",
            "config": config,
            "crawler": crawler,
        },
    )

    if rounds:
        last = rounds[-1]
        logger.info(
            "[DigestOptimization] %d rounds, final score=%.2f",
            len(rounds), last.evaluation.overall_score,
        )

    return final_results


def _copy_config(config):
    """复制配置对象"""
    from api.crawl import CrawlConfig
    if hasattr(config, 'model_dump'):
        return CrawlConfig(**config.model_dump())
    elif hasattr(config, '__dict__'):
        return CrawlConfig(**{k: v for k, v in config.__dict__.items()
                              if k in CrawlConfig.model_fields})
    return CrawlConfig()
