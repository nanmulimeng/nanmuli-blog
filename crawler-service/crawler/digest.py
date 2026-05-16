"""
日报爬取逻辑

从 TaskExecutor 提取的日报专用爬取、去重和优化逻辑。
"""

import asyncio
import logging

from config import settings

logger = logging.getLogger(__name__)


async def execute_digest_crawl(task: dict, config, task_executor) -> list:
    """日报板块爬取（并行板块 + 跨日去重，复用浏览器实例）

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

    # 板块间内容相似度去重（宽松阈值，汉明距离 ≤ 8 视为重复）
    content_dedup = DedupEngine(simhash_threshold=8)

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
            async with sem:
                if i > 0:
                    await asyncio.sleep(i * settings.digest_inter_section_delay)
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
                            preview = content[200:1000] if len(content) > 200 else content
                            dup = content_dedup.is_duplicate(url, title, preview)
                            if dup["is_duplicate"]:
                                continue
                            seen_urls.add(url)
                            all_results.append(r)
                            content_dedup.add(url, title, preview)
                            added += 1

                        await repo.update_task_progress(task["id"], len(all_results))

                    section_status[name] = f"ok ({added} new, total={len(all_results)})"
                    logger.info("Digest section '%s' added %d new URLs (total=%d)",
                                name, added, len(all_results))
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
                    sections=sections,
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
) -> list:
    """对日报按板块独立执行覆盖度评估和补充搜索。

    核心设计：每个板块用各自的 keyword 进行策略生成和搜索，
    避免合并关键词（如 "AI|Python|前端"）被追加修饰词后产生无意义查询。
    """
    import asyncio
    import random
    from ai import content_organizer as organizer
    from optimization.evaluator import CoverageEvaluator
    from optimization.strategy import StrategyGenerator
    from optimization.knowledge_base import KnowledgeBase
    from optimization.bubble_breaker import BubbleBreaker
    from crawler.search import crawl_by_keyword
    from crawler.utils import dedup_results_into

    evaluator = CoverageEvaluator(organizer if organizer.is_available else None)
    strategy_gen = StrategyGenerator()
    kb = KnowledgeBase()
    breaker = BubbleBreaker(organizer if organizer.is_available else None)

    max_rounds = settings.optimization_max_rounds
    target_score = settings.digest_optimization_target_score
    min_improvement = settings.optimization_min_improvement

    # === Step 1: 整体覆盖度评估 ===
    combined_keyword = "digest"
    if sections:
        combined_keyword = " | ".join(
            s.get("keyword", s.get("name", "")) for s in sections if s.get("keyword") or s.get("name")
        )
    ctx = {"engine": engine, "time_range": "week"}
    eval_result = await evaluator.evaluate(combined_keyword, all_results, ctx)

    logger.info(
        "[DigestOptimization] Initial: overall=%.2f angle=%.2f diversity=%.2f depth=%.2f "
        "temporal=%.2f perspective=%.2f language=%.2f",
        eval_result.overall_score, eval_result.angle_coverage,
        eval_result.source_diversity, eval_result.depth_coverage,
        eval_result.temporal_coverage, eval_result.perspective_balance,
        eval_result.language_coverage,
    )

    if eval_result.overall_score >= target_score:
        logger.info("[DigestOptimization] Target reached: %.2f", eval_result.overall_score)
        return all_results

    # === Step 2: 按板块独立优化 ===
    # 识别板块关键词列表，每个板块用原始 keyword 做策略生成
    section_keywords = []
    if sections:
        for s in sections:
            kw = s.get("keyword", "").strip()
            if kw:
                section_keywords.append(kw)

    # 如果没有板块关键词，回退到整体 keyword
    if not section_keywords:
        fallback_kw = task.get("keyword", "digest")
        if fallback_kw and len(fallback_kw) == 10 and fallback_kw[4] == "-":
            fallback_kw = "digest"
        section_keywords = [fallback_kw]

    total_rounds = 0
    prev_score = eval_result.overall_score
    consecutive_no_improve = 0

    for round_num in range(2, max_rounds + 1):
        # 轮流选择板块关键词，确保每个板块都有机会被优化
        section_kw = section_keywords[(round_num - 2) % len(section_keywords)]

        # 为当前板块关键词查询知识库提示（板块关键词在不同日报中重复出现）
        kb_hint = None
        try:
            kb_hint = await kb.get_strategy_hint(section_kw, engine, "week")
        except Exception as e:
            logger.debug("[DigestOptimization] KB hint unavailable: %s", e)

        # 为当前板块关键词生成策略
        strategy = strategy_gen.generate(
            keyword=section_kw,
            evaluation=eval_result,
            current_engine=engine,
            current_time_range="week",
            round_num=round_num,
            history=[],
            kb_hint=kb_hint,
        )

        if strategy is None:
            consecutive_no_improve += 1
            if consecutive_no_improve >= 2:
                logger.info("[DigestOptimization] No strategy available, stopping at round %d", round_num)
                break
            continue

        # 跨语言策略：翻译关键词后搜索，翻译失败则跳过
        if strategy.strategy_type == "cross_language" and breaker:
            translated = await breaker.translate_keyword(strategy.keyword)
            if translated:
                from optimization.strategy import SearchStrategy
                strategy = SearchStrategy(
                    keyword=translated, engine=strategy.engine,
                    time_range=strategy.time_range, strategy_type="cross_language",
                    reason=strategy.reason, site_scope=None,
                )
            else:
                logger.info("[DigestOptimization] Cross-language failed, skipping round %d", round_num)
                continue
        elif strategy.strategy_type == "cross_language" and not breaker:
            continue

        logger.info(
            "[DigestOptimization] Round %d: section='%s' type=%s keyword='%s' engine=%s",
            round_num, section_kw, strategy.strategy_type, strategy.keyword, strategy.engine,
        )

        try:
            new_results = await crawl_by_keyword(
                keyword=strategy.keyword,
                engine=strategy.engine,
                max_results=10,
                time_range=strategy.time_range,
                config=config,
                crawler=crawler,
            )
        except Exception as e:
            logger.warning("[DigestOptimization] Round %d search failed: %s", round_num, e)
            consecutive_no_improve += 1
            if consecutive_no_improve >= 2:
                break
            continue

        added = dedup_results_into(new_results, seen_urls, all_results)
        total_rounds += 1

        # 重新评估整体覆盖度
        prev_score = eval_result.overall_score
        eval_result = await evaluator.evaluate(combined_keyword, all_results, ctx)
        score_delta = eval_result.overall_score - prev_score

        # 保存优化轮次记录
        await _save_optimization_round(
            task_id=task["id"], round_num=round_num,
            evaluation=eval_result, strategy=strategy,
            urls_before=len(seen_urls) - added,
            urls_after=len(seen_urls),
            score_delta=score_delta,
        )

        logger.info(
            "[DigestOptimization] Round %d: overall=%.2f (delta=%.3f), added=%d URLs",
            round_num, eval_result.overall_score, score_delta, added,
        )

        if eval_result.overall_score >= target_score:
            logger.info("[DigestOptimization] Target reached: %.2f", eval_result.overall_score)
            break

        if score_delta < min_improvement:
            consecutive_no_improve += 1
            if consecutive_no_improve >= 2:
                logger.info(
                    "[DigestOptimization] Diminishing returns: delta=%.3f", score_delta,
                )
                break
        else:
            consecutive_no_improve = 0

        await asyncio.sleep(random.uniform(settings.optimization_round_delay_min, settings.optimization_round_delay_max))

    logger.info(
        "[DigestOptimization] Done: %d rounds, final score=%.2f, total URLs=%d",
        total_rounds, eval_result.overall_score, len(seen_urls),
    )
    return all_results


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


def _copy_config(config):
    """复制配置对象"""
    from api.crawl import CrawlConfig
    if hasattr(config, 'model_dump'):
        return CrawlConfig(**config.model_dump())
    elif hasattr(config, '__dict__'):
        return CrawlConfig(**{k: v for k, v in config.__dict__.items()
                              if k in CrawlConfig.model_fields})
    return CrawlConfig()
