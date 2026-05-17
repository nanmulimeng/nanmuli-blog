"""优化模块共享工具"""

import logging

logger = logging.getLogger(__name__)

_consecutive_save_failures = 0


async def save_optimization_round(task_id: int, r):
    """保存优化轮次记录到数据库

    接受任何具有以下字段的对象（duck typing）：
    round_num, evaluation (CoverageEvaluation), strategy (SearchStrategy),
    urls_before, urls_after, score_delta
    """
    global _consecutive_save_failures
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
        _consecutive_save_failures = 0
    except Exception as e:
        _consecutive_save_failures += 1
        if _consecutive_save_failures >= 5:
            logger.error("[Optimization] Save round failed %d consecutive times — KB may be degraded!",
                         _consecutive_save_failures)
        else:
            logger.warning("[Optimization] Failed to save round: %s", e)
