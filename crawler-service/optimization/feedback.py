"""反馈循环控制器 — 编排搜索→评估→策略→再搜索的迭代"""

import asyncio
import logging
import random
from collections.abc import Callable
from dataclasses import dataclass

from config import settings
from optimization.evaluator import CoverageEvaluator, CoverageEvaluation
from crawler.utils import get_result_url, get_result_success, dedup_results_into
from optimization.strategy import StrategyGenerator, SearchStrategy
from optimization.knowledge_base import KnowledgeBase

logger = logging.getLogger(__name__)


@dataclass
class OptimizationRound:
    round_num: int
    evaluation: CoverageEvaluation
    strategy: SearchStrategy
    urls_before: int
    urls_after: int
    score_delta: float


class FeedbackLoop:
    """反馈循环控制器"""

    def __init__(
        self,
        evaluator: CoverageEvaluator,
        strategy_gen: StrategyGenerator,
        knowledge_base: KnowledgeBase,
        max_rounds: int | None = None,
        target_score: float | None = None,
        min_improvement: float | None = None,
        bubble_breaker=None,
    ):
        self._evaluator = evaluator
        self._strategy_gen = strategy_gen
        self._kb = knowledge_base
        self._bubble_breaker = bubble_breaker
        self._max_rounds = max_rounds or settings.optimization_max_rounds
        self._target_score = target_score or settings.optimization_target_score
        self._min_improvement = min_improvement or settings.optimization_min_improvement

    async def execute(
        self,
        keyword: str,
        initial_results: list,
        crawl_fn: Callable,
        task_id: int = 0,
        context: dict | None = None,
    ) -> tuple[list, list[OptimizationRound]]:
        ctx = context or {}
        engine = ctx.get("engine", "bing")
        time_range = ctx.get("time_range", "week")

        # 从知识库获取策略提示
        kb_hint = None
        try:
            kb_hint = await self._kb.get_strategy_hint(keyword, engine, time_range)
            if kb_hint:
                logger.info(
                    "[Optimization] KB hint: recommended_engine=%s, recommended_type=%s",
                    kb_hint.get("recommended_engine"),
                    kb_hint.get("recommended_strategy_type"),
                )
        except Exception as e:
            logger.debug("[Optimization] KB hint unavailable: %s", e)

        all_results = list(initial_results)
        rounds: list[OptimizationRound] = []
        seen_urls = set()
        for r in initial_results:
            url = get_result_url(r)
            success = get_result_success(r)
            if url and success:
                seen_urls.add(url)

        # === Round 1: 评估初始结果 ===
        eval_result = await self._evaluator.evaluate(keyword, all_results, ctx)

        initial_strategy = SearchStrategy(
            keyword=keyword, engine=engine,
            time_range=time_range, site_scope=None,
            strategy_type="initial", reason="初始搜索",
        )
        rounds.append(OptimizationRound(
            round_num=1,
            evaluation=eval_result,
            strategy=initial_strategy,
            urls_before=0,
            urls_after=len(seen_urls),
            score_delta=eval_result.overall_score,
        ))

        logger.info(
            "[Optimization] Round 1: overall=%.2f, weaknesses=%s",
            eval_result.overall_score, eval_result.weaknesses,
        )

        await self._save_round(task_id, rounds[-1])

        if eval_result.overall_score >= self._target_score:
            logger.info("[Optimization] Target reached in round 1: %.2f", eval_result.overall_score)
            return all_results, rounds

        # === Round 2+: 反馈循环 ===
        strategy_history: list[SearchStrategy] = [initial_strategy]
        consecutive_failures = 0

        for round_num in range(2, self._max_rounds + 1):
            strategy = self._strategy_gen.generate(
                keyword=keyword,
                evaluation=eval_result,
                current_engine=engine,
                current_time_range=time_range,
                round_num=round_num,
                history=strategy_history,
                kb_hint=kb_hint,
            )

            if strategy is None:
                logger.info("[Optimization] No strategy available, stopping at round %d", round_num - 1)
                break

            strategy_history.append(strategy)

            logger.info(
                "[Optimization] Round %d: type=%s keyword='%s' engine=%s",
                round_num, strategy.strategy_type, strategy.keyword, strategy.engine,
            )

            # 跨语言策略：翻译关键词后搜索
            if strategy.strategy_type == "cross_language" and self._bubble_breaker:
                translated = await self._bubble_breaker.translate_keyword(strategy.keyword)
                if translated:
                    strategy = SearchStrategy(
                        keyword=translated, engine=strategy.engine,
                        time_range=strategy.time_range, strategy_type="cross_language",
                        reason=strategy.reason, site_scope=None,
                    )
                    logger.info("[Optimization] Cross-language translated: '%s'", translated)

            try:
                new_results = await crawl_fn(
                    keyword=strategy.keyword,
                    engine=strategy.engine,
                    max_results=10,
                    time_range=strategy.time_range,
                    config=ctx.get("config"),
                    crawler=ctx.get("crawler"),
                )
                consecutive_failures = 0
            except Exception as e:
                consecutive_failures += 1
                logger.warning("[Optimization] Round %d search failed (%d consecutive): %s",
                               round_num, consecutive_failures, e)
                if consecutive_failures >= 2:
                    logger.warning("[Optimization] 2 consecutive search failures, stopping")
                    break
                continue

            added = dedup_results_into(new_results, seen_urls, all_results)

            prev_score = eval_result.overall_score
            eval_result = await self._evaluator.evaluate(keyword, all_results, ctx)
            score_delta = eval_result.overall_score - prev_score

            rounds.append(OptimizationRound(
                round_num=round_num,
                evaluation=eval_result,
                strategy=strategy,
                urls_before=len(seen_urls) - added,
                urls_after=len(seen_urls),
                score_delta=round(score_delta, 4),
            ))

            logger.info(
                "[Optimization] Round %d: overall=%.2f (delta=%.3f), added=%d URLs",
                round_num, eval_result.overall_score, score_delta, added,
            )

            await self._save_round(task_id, rounds[-1])

            if eval_result.overall_score >= self._target_score:
                logger.info("[Optimization] Target reached: %.2f", eval_result.overall_score)
                break

            if round_num >= 2 and score_delta < self._min_improvement:
                logger.info(
                    "[Optimization] Diminishing returns: delta=%.3f < min=%.3f",
                    score_delta, self._min_improvement,
                )
                break

            await asyncio.sleep(random.uniform(settings.optimization_round_delay_min, settings.optimization_round_delay_max))

        return all_results, rounds

    async def _save_round(self, task_id: int, r: OptimizationRound):
        if task_id <= 0:
            return
        try:
            from standalone import repository as repo
            await repo.save_optimization_round(
                task_id=task_id,
                round_num=r.round_num,
                angle_coverage=r.evaluation.angle_coverage,
                source_diversity=r.evaluation.source_diversity,
                depth_coverage=r.evaluation.depth_coverage,
                temporal_coverage=r.evaluation.temporal_coverage,
                perspective_balance=r.evaluation.perspective_balance,
                language_coverage=r.evaluation.language_coverage,
                overall_score=r.evaluation.overall_score,
                search_keyword=r.strategy.keyword,
                search_engine=r.strategy.engine,
                time_range=r.strategy.time_range,
                strategy_type=r.strategy.strategy_type,
                strategy_detail=r.strategy.reason,
                weaknesses=r.evaluation.weaknesses,
                suggestions=r.evaluation.suggestions,
                urls_before=r.urls_before,
                urls_after=r.urls_after,
                score_delta=r.score_delta,
            )
        except Exception as e:
            logger.warning("[Optimization] Failed to save round: %s", e)
