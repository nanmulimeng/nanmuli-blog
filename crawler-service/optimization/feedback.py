"""深度优化反馈循环 — 编排搜索→评估→深度策略→再搜索的迭代

只关注 depth/angle/temporal 三个深度维度。
广度维度由 BreadthExpander 处理。
"""

import asyncio
import logging
import random
import time
from collections.abc import Callable
from dataclasses import dataclass

from config import settings
from optimization.evaluator import CoverageEvaluator, CoverageEvaluation
from optimization.strategy import DepthStrategyGen, SearchStrategy
from optimization.knowledge_base import KnowledgeBase
from optimization.utils import save_optimization_round
from crawler.utils import get_result_url, get_result_success, dedup_results_into, normalize_url

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
    """深度优化反馈循环"""

    def __init__(
        self,
        evaluator: CoverageEvaluator,
        strategy_gen: DepthStrategyGen,
        knowledge_base: KnowledgeBase,
        max_rounds: int | None = None,
        target_score: float | None = None,
        min_improvement: float | None = None,
    ):
        self._evaluator = evaluator
        self._strategy_gen = strategy_gen
        self._kb = knowledge_base
        self._max_rounds = max_rounds if max_rounds is not None else settings.optimization_max_rounds
        self._target_score = target_score if target_score is not None else settings.optimization_depth_target_score
        self._min_improvement = min_improvement if min_improvement is not None else settings.optimization_min_improvement

    @staticmethod
    def _depth_score(evaluation: CoverageEvaluation) -> float:
        """深度三维的加权平均分"""
        return (
            evaluation.depth_coverage * settings.optimization_depth_weight_primary
            + evaluation.angle_coverage * settings.optimization_depth_weight_secondary
            + evaluation.temporal_coverage * settings.optimization_depth_weight_tertiary
        )

    async def execute(
        self,
        keyword: str,
        initial_results: list,
        crawl_fn: Callable,
        task_id: int = 0,
        context: dict | None = None,
        initial_evaluation: CoverageEvaluation | None = None,
        deadline: float | None = None,
        **kwargs,
    ) -> tuple[list, list[OptimizationRound]]:
        ctx = context or {}
        engine = ctx.get("engine", "bing")
        time_range = ctx.get("time_range", "week")
        budget_start = time.monotonic()
        effective_deadline = deadline or (budget_start + settings.optimization_total_budget_seconds)

        all_results = list(initial_results)
        rounds: list[OptimizationRound] = []
        seen_urls = set()
        for r in initial_results:
            url = get_result_url(r)
            success = get_result_success(r)
            if url and success:
                seen_urls.add(normalize_url(url))

        # === Round 1: 评估初始结果 ===
        if initial_evaluation is not None:
            eval_result = initial_evaluation
        else:
            eval_result = await self._evaluator.evaluate(keyword, all_results, ctx)

        initial_strategy = SearchStrategy(
            keyword=keyword, engine=engine,
            time_range=time_range, site_scope=None,
            strategy_type="depth_initial", reason="深度基线评估",
        )
        rounds.append(OptimizationRound(
            round_num=1,
            evaluation=eval_result,
            strategy=initial_strategy,
            urls_before=len(seen_urls),
            urls_after=len(seen_urls),
            score_delta=0.0,
        ))

        depth_base = self._depth_score(eval_result)
        logger.info(
            "[DepthOptimization] Round 1: depth=%.2f (depth=%.2f angle=%.2f temporal=%.2f)",
            depth_base, eval_result.depth_coverage,
            eval_result.angle_coverage, eval_result.temporal_coverage,
        )

        await save_optimization_round(task_id, rounds[-1])

        if depth_base >= self._target_score:
            logger.info("[DepthOptimization] Target reached in round 1: depth=%.2f", depth_base)
            return all_results, rounds

        # === Round 2+: 深度循环 ===
        strategy_history: list[SearchStrategy] = [initial_strategy]
        consecutive_failures = 0

        for round_num in range(2, self._max_rounds + 1):
            # 知识库提示
            kb_hint = None
            try:
                kb_hint = await self._kb.get_strategy_hint(keyword, engine, time_range)
            except Exception as e:
                logger.debug("[DepthOptimization] KB hint unavailable: %s", e)

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
                logger.info("[DepthOptimization] No strategy available, stopping at round %d", round_num - 1)
                break

            strategy_history.append(strategy)

            logger.info(
                "[DepthOptimization] Round %d: type=%s keyword='%s' engine=%s",
                round_num, strategy.strategy_type, strategy.keyword, strategy.engine,
            )

            # === 执行深度搜索 ===
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
                logger.warning("[DepthOptimization] Round %d search failed (%d consecutive): %s",
                               round_num, consecutive_failures, e)
                if consecutive_failures >= 2:
                    logger.warning("[DepthOptimization] 2 consecutive search failures, stopping")
                    break
                continue

            added = dedup_results_into(new_results, seen_urls, all_results,
                                       min_content_length=settings.min_content_length)

            # === 评估 + 保存 + 检查 ===
            prev_depth = self._depth_score(eval_result)
            eval_result = await self._evaluator.evaluate(keyword, all_results, ctx)
            depth_delta = self._depth_score(eval_result) - prev_depth

            rounds.append(OptimizationRound(
                round_num=round_num,
                evaluation=eval_result,
                strategy=strategy,
                urls_before=len(seen_urls) - added,
                urls_after=len(seen_urls),
                score_delta=round(depth_delta, 4),
            ))

            depth_now = self._depth_score(eval_result)
            logger.info(
                "[DepthOptimization] Round %d: depth=%.2f (delta=%.3f), overall=%.2f, added=%d URLs",
                round_num, depth_now, depth_delta, eval_result.overall_score, added,
            )

            await save_optimization_round(task_id, rounds[-1])

            if depth_now >= self._target_score:
                logger.info("[DepthOptimization] Target reached: depth=%.2f", depth_now)
                break

            if round_num >= 3 and depth_delta < self._min_improvement:
                logger.info(
                    "[DepthOptimization] Diminishing returns: depth_delta=%.3f < min=%.3f",
                    depth_delta, self._min_improvement,
                )
                break

            # 总时间预算检查
            if time.monotonic() > effective_deadline:
                elapsed_total = time.monotonic() - budget_start
                logger.info("[DepthOptimization] Deadline exceeded (%.0fs), stopping", elapsed_total)
                break

            await asyncio.sleep(random.uniform(settings.optimization_round_delay_min, settings.optimization_round_delay_max))

        return all_results, rounds
