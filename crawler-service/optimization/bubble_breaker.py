"""信息茧房突破模块

BubbleBreaker: 跨语言翻译组件（内部组件）
BreadthExpander: 广度扩展编排器 — 突破信息茧房的主循环
"""

import asyncio
import copy
import logging
import random
import time
from collections.abc import Callable
from dataclasses import dataclass

from config import settings
from optimization.evaluator import CoverageEvaluator, CoverageEvaluation
from optimization.strategy import BreadthStrategyGen, SearchStrategy
from optimization.knowledge_base import KnowledgeBase
from optimization.utils import save_optimization_round
from crawler.utils import get_result_url, get_result_success, dedup_results_into, normalize_url

logger = logging.getLogger(__name__)

# ============== 跨语言翻译组件 ==============

TRANSLATE_SYSTEM_PROMPT = """你是搜索关键词翻译专家。
将给定的中文搜索关键词翻译为最适合搜索引擎的英文搜索词。
规则：
1. 只输出英文关键词，不要解释
2. 保留技术专有名词（如 React、Kubernetes）
3. 使用搜索引擎友好的短语格式（如 "Spring Boot tutorial" 而非完整句子）
4. 如果关键词已经是英文，原样返回"""

TRANSLATE_TO_CN_PROMPT = """你是搜索关键词翻译专家。
将给定的英文搜索关键词翻译为最适合搜索引擎的中文搜索词。
规则：
1. 只输出中文关键词，不要解释
2. 保留技术专有名词（如 React、Kubernetes）
3. 使用搜索引擎友好的短语格式
4. 如果关键词已经是中文，原样返回"""


class BubbleBreaker:
    """跨语言翻译组件

    注：check_and_expand() 已废弃，跨语言搜索由 BreadthExpander 直接编排。
    """

    def __init__(self, organizer=None):
        self._organizer = organizer
        self._evaluator = CoverageEvaluator(organizer=organizer)

    # deprecated: 保留以兼容旧测试，新代码使用 BreadthExpander 直接编排
    async def check_and_expand(
        self,
        keyword: str,
        results: list,
        crawl_fn: Callable,
        context: dict,
    ) -> list:
        if not settings.bubble_breaker_enabled:
            return results

        expanded = list(results)
        seen_urls = {
            normalize_url(url)
            for r in results
            if get_result_success(r)
            for url in [get_result_url(r) or ""]
            if url
        }

        if settings.bubble_cross_language and self._needs_cross_language(results):
            translated = await self.translate_keyword(keyword)
            if translated:
                logger.info(
                    "[BubbleBreaker] Cross-language: '%s' -> '%s'", keyword, translated,
                )
                try:
                    new = await crawl_fn(
                        keyword=translated,
                        engine=context.get("engine", "bing"),
                        max_results=10,
                        time_range=context.get("time_range", "week"),
                        config=context.get("config"),
                        crawler=context.get("crawler"),
                    )
                    added = dedup_results_into(new, seen_urls, expanded)
                    logger.info(
                        "[BubbleBreaker] Added %d cross-language results", added,
                    )
                except Exception as e:
                    logger.warning("[BubbleBreaker] Cross-language search failed: %s", e)

        return expanded

    async def translate_keyword(self, keyword: str) -> str | None:
        if not self._organizer or not self._organizer.is_available:
            return None
        try:
            from crawler.utils import detect_cjk
            is_cn = detect_cjk(keyword)
            prompt = TRANSLATE_SYSTEM_PROMPT if is_cn else TRANSLATE_TO_CN_PROMPT

            response = await self._organizer._call_ai(prompt, keyword, max_tokens=settings.bubble_max_translate_tokens)
            translated = response.get("content", "").strip()

            if not translated or translated == keyword:
                return None
            import re
            if is_cn and re.search(r"[a-zA-Z]{2,}", translated):
                return translated
            if not is_cn and re.search(r"[一-鿿]", translated):
                return translated
            return None
        except Exception as e:
            logger.debug("[BubbleBreaker] Translation failed: %s", e)
            return None

    def _needs_cross_language(self, results: list) -> bool:
        titles = []
        for r in results:
            rdict = r if isinstance(r, dict) else (r.__dict__ if hasattr(r, "__dict__") else {})
            if rdict.get("success", False):
                titles.append(rdict.get("title", "") or "")
        if not titles:
            return False
        language_mix = CoverageEvaluator._calc_language_mix(titles)
        return language_mix < 0.5


# ============== 广度轮次数据 ==============

@dataclass
class BreadthRound:
    round_num: int
    evaluation: CoverageEvaluation
    strategy: SearchStrategy
    urls_before: int
    urls_after: int
    score_delta: float


# ============== 广度扩展编排器 ==============

class BreadthExpander:
    """广度扩展编排器 — 突破信息茧房

    关注 source_diversity / perspective / language 三个广度维度，
    独立于深度循环运行，有自己的 round 预算。
    """

    def __init__(
        self,
        evaluator: CoverageEvaluator,
        strategy_gen: BreadthStrategyGen,
        knowledge_base: KnowledgeBase,
        bubble_breaker: BubbleBreaker | None = None,
        max_rounds: int | None = None,
        target_score: float | None = None,
        min_improvement: float | None = None,
    ):
        self._evaluator = evaluator
        self._strategy_gen = strategy_gen
        self._kb = knowledge_base
        self._breaker = bubble_breaker
        self._max_rounds = max_rounds if max_rounds is not None else settings.breadth_max_rounds
        self._target_score = target_score if target_score is not None else settings.optimization_breadth_target_score
        self._min_improvement = min_improvement if min_improvement is not None else settings.optimization_min_improvement

    @staticmethod
    def _breadth_score(evaluation: CoverageEvaluation) -> float:
        """广度三维的加权平均分"""
        return (
            evaluation.source_diversity * settings.optimization_breadth_weight_primary
            + evaluation.perspective_balance * settings.optimization_breadth_weight_secondary
            + evaluation.language_coverage * settings.optimization_breadth_weight_tertiary
        )

    async def execute(
        self,
        keyword: str,
        initial_results: list,
        crawl_fn: Callable,
        task_id: int = 0,
        context: dict | None = None,
        sections: list[dict] | None = None,
        source_crawl_fn: Callable | None = None,
        deadline: float | None = None,
    ) -> tuple[list, list[BreadthRound]]:
        ctx = context or {}
        engine = ctx.get("engine", "bing")
        time_range = ctx.get("time_range", "week")
        budget_start = time.monotonic()
        effective_deadline = deadline or (budget_start + settings.optimization_total_budget_seconds)

        # source_crawl_fn 默认实现：从 digest 模块爬取 URL/RSS 源
        if source_crawl_fn is None:
            async def _default_source_crawl(section, config, crawler, overrides=None):
                from crawler.digest import _apply_overrides, _crawl_url_sources, _crawl_rss_sources
                sec = _apply_overrides(section, overrides)
                results = []
                if sec.get("url_sources"):
                    results.extend(await _crawl_url_sources(sec, config, crawler))
                if sec.get("rss_sources"):
                    results.extend(await _crawl_rss_sources(sec, config, crawler))
                return results
            source_crawl_fn = _default_source_crawl

        all_results = list(initial_results)
        rounds: list[BreadthRound] = []
        seen_urls = set()
        for r in initial_results:
            url = get_result_url(r)
            success = get_result_success(r)
            if url and success:
                seen_urls.add(normalize_url(url))

        # === Round 1: 基线评估 ===
        eval_result = await self._evaluator.evaluate(keyword, all_results, ctx)

        initial_strategy = SearchStrategy(
            keyword=keyword, engine=engine,
            time_range=time_range, site_scope=None,
            strategy_type="breadth_initial", reason="广度基线评估",
        )
        rounds.append(BreadthRound(
            round_num=1,
            evaluation=eval_result,
            strategy=initial_strategy,
            urls_before=len(seen_urls),
            urls_after=len(seen_urls),
            score_delta=0.0,
        ))

        breadth_base = self._breadth_score(eval_result)
        logger.info(
            "[BreadthExpander] Round 1: breadth=%.2f (diversity=%.2f perspective=%.2f language=%.2f)",
            breadth_base, eval_result.source_diversity,
            eval_result.perspective_balance, eval_result.language_coverage,
        )

        await save_optimization_round(task_id, rounds[-1])

        if breadth_base >= self._target_score:
            logger.info("[BreadthExpander] Target reached in round 1: %.2f", breadth_base)
            return all_results, rounds

        # === Round 2+: 广度循环 ===
        strategy_history: list[SearchStrategy] = [initial_strategy]
        search_failures = 0
        source_failures = 0

        for round_num in range(2, self._max_rounds + 1):
            # 知识库提示
            kb_hint = None
            try:
                kb_hint = await self._kb.get_strategy_hint(keyword, engine, time_range)
            except Exception as e:
                logger.debug("[BreadthExpander] KB hint unavailable: %s", e)

            strategy = self._strategy_gen.generate(
                keyword=keyword,
                evaluation=eval_result,
                current_engine=engine,
                current_time_range=time_range,
                round_num=round_num,
                history=strategy_history,
                kb_hint=kb_hint,
                sections=sections,
            )

            if strategy is None:
                logger.info("[BreadthExpander] No strategy available, stopping at round %d", round_num - 1)
                break

            strategy_history.append(strategy)

            logger.info(
                "[BreadthExpander] Round %d: type=%s keyword='%s' engine=%s",
                round_num, strategy.strategy_type, strategy.keyword, strategy.engine,
            )

            # 跨语言策略
            if strategy.strategy_type == "cross_language" and self._breaker:
                translated = await self._breaker.translate_keyword(strategy.keyword)
                if translated:
                    strategy = SearchStrategy(
                        keyword=translated, engine=strategy.engine,
                        time_range=strategy.time_range, strategy_type="cross_language",
                        reason=strategy.reason, site_scope=None,
                    )
                    logger.info("[BreadthExpander] Cross-language translated: '%s'", translated)
                else:
                    logger.info("[BreadthExpander] Cross-language translation failed, skipping round %d", round_num)
                    continue
            elif strategy.strategy_type == "cross_language" and not self._breaker:
                logger.info("[BreadthExpander] Cross-language requested but BubbleBreaker unavailable, skipping round %d", round_num)
                continue

            # === 执行搜索/爬取 ===
            if strategy.strategy_type == "source_expand" and strategy.source_expand_section:
                try:
                    new_results = await source_crawl_fn(
                        strategy.source_expand_section,
                        ctx.get("config"),
                        ctx.get("crawler"),
                        strategy.source_expand_overrides,
                    )
                    source_failures = 0
                except Exception as e:
                    source_failures += 1
                    logger.warning("[BreadthExpander] Source expand failed (%d consecutive): %s",
                                   source_failures, e)
                    if source_failures >= 2:
                        break
                    continue
            else:
                try:
                    new_results = await crawl_fn(
                        keyword=strategy.keyword,
                        engine=strategy.engine,
                        max_results=10,
                        time_range=strategy.time_range,
                        config=ctx.get("config"),
                        crawler=ctx.get("crawler"),
                    )
                    search_failures = 0
                except Exception as e:
                    search_failures += 1
                    logger.warning("[BreadthExpander] Round %d search failed (%d consecutive): %s",
                                   round_num, search_failures, e)
                    if search_failures >= 2:
                        logger.warning("[BreadthExpander] 2 consecutive search failures, stopping")
                        break
                    continue

            added = dedup_results_into(new_results, seen_urls, all_results,
                                       min_content_length=settings.min_content_length)

            # === 评估 + 保存 + 检查 ===
            prev_score = self._breadth_score(eval_result)
            eval_result = await self._evaluator.evaluate(keyword, all_results, ctx)
            score_delta = self._breadth_score(eval_result) - prev_score

            rounds.append(BreadthRound(
                round_num=round_num,
                evaluation=eval_result,
                strategy=strategy,
                urls_before=len(seen_urls) - added,
                urls_after=len(seen_urls),
                score_delta=round(score_delta, 4),
            ))

            breadth_now = self._breadth_score(eval_result)
            logger.info(
                "[BreadthExpander] Round %d: breadth=%.2f (delta=%.3f), added=%d URLs",
                round_num, breadth_now, score_delta, added,
            )

            await save_optimization_round(task_id, rounds[-1])

            if breadth_now >= self._target_score:
                logger.info("[BreadthExpander] Target reached: %.2f", breadth_now)
                break

            if round_num >= 3 and score_delta < self._min_improvement:
                logger.info(
                    "[BreadthExpander] Diminishing returns: delta=%.3f < min=%.3f",
                    score_delta, self._min_improvement,
                )
                break

            # 总时间预算检查
            if time.monotonic() > effective_deadline:
                elapsed_total = time.monotonic() - budget_start
                logger.info("[BreadthExpander] Deadline exceeded (%.0fs), stopping", elapsed_total)
                break

            await asyncio.sleep(random.uniform(settings.optimization_round_delay_min, settings.optimization_round_delay_max))

        return all_results, rounds
