"""自动优化引擎 — 覆盖度评估 + 策略生成 + 反馈循环"""

from optimization.evaluator import CoverageEvaluator, CoverageEvaluation
from optimization.strategy import StrategyGenerator, SearchStrategy
from optimization.feedback import FeedbackLoop, OptimizationRound
from optimization.knowledge_base import KnowledgeBase
from optimization.bubble_breaker import BubbleBreaker
