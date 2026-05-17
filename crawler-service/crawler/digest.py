"""
日报爬取逻辑

从 TaskExecutor 提取的日报专用爬取、去重和优化逻辑。
"""

import asyncio
import copy
import logging

from config import settings

logger = logging.getLogger(__name__)


async def execute_digest_crawl(task: dict, config, task_executor) -> list:
    """日报板块爬取（并行板块 + 跨日去重，复用浏览器实例）

    支持 keyword（搜索引擎）、url（直爬）、rss（Feed 解析 + 爬取）三种板块类型。

    Args:
        task: 任务字典
        config: 爬取配置
        task_executor: TaskExecutor 实例（用于调用 _filter_low_quality 等方法）

    Returns:
        去重后的 CrawlResult 列表
    """
    from crawler.search import crawl_by_keyword
    from crawler.dedup import dedup_results, DedupEngine
    from crawler.config import get_browser_config, RunParams
    from standalone.task_executor import repo, get_digest_sections
    from crawl4ai import AsyncWebCrawler

    sections = await get_digest_sections()
    if not sections:
        raise ValueError("日报功能未配置")

    history_engine = await build_digest_history_engine()

    seen_urls: set[str] = set()
    all_results: list = []
    lock = asyncio.Lock()
    engine = settings.digest_search_engine
    max_parallel = getattr(settings, "digest_parallel_sections", 2)
    sem = asyncio.Semaphore(max_parallel)

    # 板块间内容相似度去重（汉明距离 ≤ 5 视为重复，与板块内阈值一致）
    content_dedup = DedupEngine(simhash_threshold=5)

    # 板块执行状态追踪
    section_status: dict[str, str] = {}

    params = RunParams(config)
    browser_config = await get_browser_config(
        text_mode=params.text_mode, light_mode=params.light_mode,
        proxy=settings.proxy_url,
    )

    async with AsyncWebCrawler(config=browser_config) as shared_crawler:

        async def crawl_section(i: int, section: dict):
            name = section.get("name", f"section_{i}")
            source_type = section.get("source_type", "keyword")
            async with sem:
                if i > 0:
                    await asyncio.sleep(i * settings.digest_inter_section_delay)
                config_copy = _copy_config(config)
                try:
                    # 根据板块类型分发爬取
                    results = []

                    # keyword 搜索（keyword 或 mixed 板块）
                    if source_type in ("keyword", "mixed") and section.get("keyword"):
                        kw_results = await crawl_by_keyword(
                            keyword=section["keyword"],
                            engine=engine,
                            max_results=section.get("max_items", 5) * settings.digest_section_result_multiplier,
                            time_range=section.get("time_range", "week"),
                            config=config_copy,
                            crawler=shared_crawler,
                        )
                        results.extend(kw_results)

                    # URL 直爬（url 或 mixed 板块）
                    if source_type in ("url", "mixed") and section.get("url_sources"):
                        url_results = await _crawl_url_sources(
                            section, config_copy, shared_crawler,
                        )
                        results.extend(url_results)

                    # RSS Feed（rss 板块）
                    if source_type == "rss" and section.get("rss_sources"):
                        rss_results = await _crawl_rss_sources(
                            section, config_copy, shared_crawler,
                        )
                        results.extend(rss_results)

                    results = dedup_results(results, history_engine=history_engine)

                    async with lock:
                        # URL 去重 + 板块间 SimHash 去重
                        added = 0
                        for r in results:
                            url = (r.get('url', '') if isinstance(r, dict)
                                   else getattr(r, 'url', ''))
                            success = (r.get('success', True) if isinstance(r, dict)
                                       else getattr(r, 'success', True))
                            if not url or url in seen_urls or not success:
                                continue
                            # SimHash 去重
                            content = (r.get('markdown', '') if isinstance(r, dict)
                                       else getattr(r, 'markdown', ''))
                            title = (r.get('title', '') if isinstance(r, dict)
                                     else getattr(r, 'title', ''))
                            # 取正文核心段：跳过头部导航区
                            skip = settings.filter_skip_header_chars
                            plen = settings.filter_content_preview_length
                            preview = content[skip:skip + plen] if len(content) > skip else content[:plen]
                            dup = content_dedup.is_duplicate(url, title, preview)
                            if dup["is_duplicate"]:
                                continue
                            seen_urls.add(url)
                            all_results.append(r)
                            content_dedup.add(url, title, preview)
                            added += 1

                        await repo.update_task_progress(task["id"], len(all_results))

                    section_status[name] = f"ok ({added} new, total={len(all_results)})"
                    logger.info("Digest section '%s' [%s] added %d new URLs (total=%d)",
                                name, source_type, added, len(all_results))
                except asyncio.CancelledError:
                    section_status[name] = "cancelled"
                    raise
                except Exception as e:
                    section_status[name] = f"failed: {e}"
                    logger.warning("Digest section '%s' failed: %s", name, e)

        # 全局超时保护：超时后取消未完成板块，返回已有结果
        try:
            await asyncio.wait_for(
                asyncio.gather(*[crawl_section(i, s) for i, s in enumerate(sections)]),
                timeout=settings.digest_global_timeout,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "[Digest] Global timeout (%ds) reached, returning %d results collected so far",
                settings.digest_global_timeout, len(all_results),
            )

        # 板块执行汇总日志
        ok_count = sum(1 for v in section_status.values() if v.startswith("ok"))
        fail_count = sum(1 for v in section_status.values() if v.startswith("failed"))
        cancel_count = sum(1 for v in section_status.values() if v.startswith("cancelled"))
        logger.info(
            "[Digest] Section summary: %d total, %d ok, %d failed, %d cancelled → %d results",
            len(sections), ok_count, fail_count, cancel_count, len(all_results),
        )
        if fail_count > 0:
            for name, status in section_status.items():
                if status.startswith("failed"):
                    logger.warning("[Digest] Section '%s': %s", name, status)

        # 日报自动优化（可选，需显式启用）
        if (settings.optimization_enabled
                and settings.optimization_mode in ("digest", "both")
                and settings.digest_optimization_enabled
                and len(all_results) >= settings.digest_optimization_min_sections * settings.digest_optimization_min_results_per_section):
            try:
                all_results = await run_digest_optimization(
                    task=task, all_results=all_results, seen_urls=seen_urls,
                    engine=engine, config=config, crawler=shared_crawler,
                    sections=sections, history_engine=history_engine,
                )
            except Exception as e:
                logger.warning("Digest optimization failed (non-critical): %s", e)

    return all_results


async def build_digest_history_engine():
    """从最近几次成功日报中加载 URL/标题/内容指纹，用于跨日去重"""
    from crawler.dedup import DedupEngine
    from standalone import repository as repo

    engine = DedupEngine()
    try:
        pages = await repo.get_history_digest_pages(count=settings.digest_history_load_count)
        for p in pages:
            url = p.get("url", "")
            title = p.get("page_title", "")
            content = p.get("raw_markdown", "")
            if url:
                engine.add_reference(url, title=title, content=content)
        if pages:
            logger.info("Digest history engine: %d reference pages loaded", len(pages))
    except Exception as e:
        logger.warning("Failed to load digest history for dedup: %s", e)
    return engine


async def run_digest_optimization(
    task: dict, all_results: list, seen_urls: set,
    engine: str, config, crawler, sections: list | None = None,
    history_engine=None,
) -> list:
    """日报优化：先广度扩展（突破信息茧房），再深度优化（深入挖掘）。

    广度和深度各有独立的 round 预算，互不抢占。
    板块关键词轮流用于策略生成，避免合并关键词产生无意义查询。
    """
    from ai import content_organizer as organizer
    from optimization.evaluator import CoverageEvaluator
    from optimization.strategy import DepthStrategyGen, BreadthStrategyGen
    from optimization.feedback import FeedbackLoop
    from optimization.bubble_breaker import BreadthExpander, BubbleBreaker
    from optimization.knowledge_base import KnowledgeBase
    from crawler.search import crawl_by_keyword

    evaluator = CoverageEvaluator(organizer if organizer.is_available else None)
    depth_gen = DepthStrategyGen()
    breadth_gen = BreadthStrategyGen()
    kb = KnowledgeBase()
    breaker = BubbleBreaker(organizer if organizer.is_available else None)

    ctx = {"engine": engine, "time_range": "week", "config": config, "crawler": crawler}

    # === Phase 1: 广度扩展（先广）===
    breadth_expander = BreadthExpander(
        evaluator=evaluator,
        strategy_gen=breadth_gen,
        knowledge_base=kb,
        bubble_breaker=breaker,
        target_score=settings.digest_optimization_target_score,
    )
    results, breadth_rounds = await breadth_expander.execute(
        keyword="digest",
        initial_results=all_results,
        crawl_fn=crawl_by_keyword,
        task_id=task["id"],
        context=ctx,
        sections=sections,
    )

    if breadth_rounds:
        last = breadth_rounds[-1]
        logger.info(
            "[DigestOptimization] Breadth done: %d rounds, breadth_score=%.2f, URLs=%d",
            len(breadth_rounds), BreadthExpander._breadth_score(last.evaluation), last.urls_after,
        )

    # === Phase 2: 深度优化（后深）===
    depth_loop = FeedbackLoop(
        evaluator=evaluator,
        strategy_gen=depth_gen,
        knowledge_base=kb,
        target_score=settings.digest_optimization_target_score,
    )
    final_results, depth_rounds = await depth_loop.execute(
        keyword="digest",
        initial_results=results,
        crawl_fn=crawl_by_keyword,
        task_id=task["id"],
        context=ctx,
    )

    total_rounds = len(breadth_rounds) + len(depth_rounds)
    final_eval = depth_rounds[-1].evaluation if depth_rounds else (
        breadth_rounds[-1].evaluation if breadth_rounds else None
    )
    logger.info(
        "[DigestOptimization] Done: %d rounds (breadth=%d, depth=%d), final score=%.2f, total URLs=%d",
        total_rounds, len(breadth_rounds), len(depth_rounds),
        final_eval.overall_score if final_eval else 0, len(seen_urls),
    )
    return final_results


async def _save_optimization_round(
    task_id: int, round_num: int, evaluation, strategy,
    urls_before: int, urls_after: int, score_delta: float,
):
    """保存优化轮次到 DB"""
    if task_id <= 0:
        return
    try:
        from standalone import repository as repo
        await repo.save_optimization_round(
            task_id=task_id,
            round_num=round_num,
            angle_coverage=evaluation.angle_coverage,
            source_diversity=evaluation.source_diversity,
            depth_coverage=evaluation.depth_coverage,
            temporal_coverage=evaluation.temporal_coverage,
            perspective_balance=evaluation.perspective_balance,
            language_coverage=evaluation.language_coverage,
            overall_score=evaluation.overall_score,
            search_keyword=strategy.keyword,
            search_engine=strategy.engine,
            time_range=strategy.time_range,
            strategy_type=strategy.strategy_type,
            strategy_detail=strategy.reason,
            weaknesses=evaluation.weaknesses,
            suggestions=evaluation.suggestions,
            urls_before=urls_before,
            urls_after=urls_after,
            score_delta=round(score_delta, 4),
        )
    except Exception as e:
        logger.warning("[DigestOptimization] Failed to save round: %s", e)


async def _crawl_url_sources(section: dict, config, crawler) -> list:
    """爬取板块中所有 URL 类型的信息源。

    对每个 URL 源根据 crawlMode 选择 single 或 deep 爬取。
    单个源失败不阻断其他源。
    """
    from crawler.single import crawl_single_page
    from crawler.deep import crawl_deep_pages
    from crawler.models import CrawlResult

    results: list[CrawlResult] = []
    url_sources = section.get("url_sources", [])
    max_items = section.get("max_items", 5)

    for src in url_sources[:max_items]:
        url = src.get("url", "")
        if not url:
            continue
        # 跳过效能差的死源（成功率 < 20% 且运行 ≥ 3 次）
        eff = src.get("effectiveness", {})
        if eff.get("dead"):
            logger.debug("Skipping dead URL source: url=%s success_rate=%.0f%%",
                         url, eff.get("success_rate", 0) * 100)
            continue
        try:
            src_name = src.get("source_name", "")
            source_id = src.get("source_id")
            if src.get("crawl_mode", "single") == "deep":
                pages = await crawl_deep_pages(
                    url=url,
                    max_depth=src.get("max_depth", 1),
                    max_pages=src.get("max_pages", 10),
                    config=config,
                    crawler=crawler,
                )
                for p in pages:
                    if src_name:
                        p.metadata["source_name"] = src_name
                    if source_id is not None:
                        p.metadata["source_id"] = source_id
                results.extend(pages)
            else:
                result = await crawl_single_page(url=url, config=config, crawler=crawler)
                if src_name:
                    result.metadata["source_name"] = src_name
                if source_id is not None:
                    result.metadata["source_id"] = source_id
                results.append(result)
        except Exception as e:
            logger.warning("URL source crawl failed: url=%s error=%s", url, e)

    return results


async def _crawl_rss_sources(section: dict, config, crawler) -> list:
    """解析板块中所有 RSS Feed，爬取每篇文章。

    1. parse_feed() 提取文章 URL 列表
    2. 逐篇 crawl_single_page() 获取 markdown
    """
    from crawler.feed import parse_feed
    from crawler.single import crawl_single_page
    from crawler.models import CrawlResult

    results: list[CrawlResult] = []
    rss_sources = section.get("rss_sources", [])
    max_items = section.get("max_items", 5)
    page_sem = asyncio.Semaphore(settings.max_concurrent_crawls)

    async def _crawl_feed_entry(entry_url: str, feed_title: str = "") -> CrawlResult | None:
        async with page_sem:
            try:
                result = await crawl_single_page(url=entry_url, config=config, crawler=crawler)
                if result and feed_title:
                    result.metadata["feed_title"] = feed_title
                    if not result.title:
                        result.title = feed_title
                return result
            except Exception as e:
                logger.debug("RSS article crawl failed: url=%s error=%s", entry_url, e)
                return None

    for rss_src in rss_sources:
        feed_url = rss_src.get("feed_url", "")
        freshness_hours = rss_src.get("freshness_hours", 24)
        src_name = rss_src.get("source_name", "")
        source_id = rss_src.get("source_id")
        rss_max = rss_src.get("max_entries", max_items)
        if not feed_url:
            continue
        # 跳过效能差的死源
        eff = rss_src.get("effectiveness", {})
        if eff.get("dead"):
            logger.debug("Skipping dead RSS source: feed=%s", feed_url)
            continue

        try:
            entries = await parse_feed(
                feed_url=feed_url,
                freshness_hours=freshness_hours,
                max_entries=rss_max,
                proxy=settings.proxy_url,
            )
        except Exception as e:
            logger.warning("RSS feed parse failed: url=%s error=%s", feed_url, e)
            continue

        if not entries:
            continue

        logger.info("RSS feed '%s': %d fresh entries to crawl", feed_url, len(entries))

        # 并发爬取文章页面
        tasks = [_crawl_feed_entry(e.url, e.title) for e in entries]
        page_results = await asyncio.gather(*tasks, return_exceptions=True)

        for r in page_results:
            if isinstance(r, CrawlResult):
                if src_name:
                    r.metadata["source_name"] = src_name
                if source_id is not None:
                    r.metadata["source_id"] = source_id
                results.append(r)

    return results


def _copy_config(config):
    """复制配置对象"""
    from api.crawl import CrawlConfig
    if hasattr(config, 'model_dump'):
        return CrawlConfig(**config.model_dump())
    elif hasattr(config, '__dict__'):
        return CrawlConfig(**{k: v for k, v in config.__dict__.items()
                              if k in CrawlConfig.model_fields})
    return CrawlConfig()


def _apply_overrides(section: dict, overrides: dict | None) -> dict:
    """根据自适应参数覆盖修改 section 副本。"""
    if not overrides:
        return section

    sec = copy.deepcopy(section)

    freshness_mult = overrides.get("freshness_multiplier", 1.0)
    if freshness_mult != 1.0:
        for rss_src in sec.get("rss_sources", []):
            original = rss_src.get("freshness_hours", 24)
            rss_src["freshness_hours"] = int(original * freshness_mult)

    items_mult = overrides.get("max_items_multiplier", 1.0)
    if items_mult != 1.0:
        original_max = sec.get("max_items", 5)
        sec["max_items"] = max(int(original_max * items_mult), original_max)

    skip_ids = set(overrides.get("skip_source_ids", []))
    if skip_ids:
        sec["url_sources"] = [
            s for s in sec.get("url_sources", [])
            if s.get("source_id") not in skip_ids
        ]
        sec["rss_sources"] = [
            s for s in sec.get("rss_sources", [])
            if s.get("source_id") not in skip_ids
        ]

    return sec
