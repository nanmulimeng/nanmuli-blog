"""统一策略疲劳追踪器

outcome-aware：连续 N 次尝试无改善视为疲劳。
替代 strategy.py 中基于尝试次数的 _is_dimension_exhausted 和
feedback.py 中基于连续失败计数的简单实现。
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# 默认疲劳阈值：连续 2 次无改善即标记为疲劳
_DEFAULT_EXHAUST_WINDOW = 2


class FatigueTracker:
    """outcome-aware 维度疲劳追踪"""

    def __init__(self, window: int = _DEFAULT_EXHAUST_WINDOW):
        self._window = window
        self._attempts: dict[str, list[bool]] = {}

    def record(self, dimension: str, improved: bool) -> None:
        """记录一次维度尝试结果"""
        history = self._attempts.setdefault(dimension, [])
        history.append(improved)

    def is_exhausted(self, dimension: str) -> bool:
        """最近 window 次尝试全部无改善 → 疲劳"""
        history = self._attempts.get(dimension, [])
        if len(history) < self._window:
            return False
        return not any(history[-self._window:])

    def reset(self) -> None:
        """重置所有追踪状态"""
        self._attempts.clear()

    def status(self) -> dict[str, list[bool]]:
        """返回当前追踪状态（调试用）"""
        return dict(self._attempts)
