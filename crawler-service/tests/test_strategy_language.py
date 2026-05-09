"""language 维度策略生成测试"""

import pytest
from optimization.strategy import StrategyGenerator, SearchStrategy
from optimization.evaluator import CoverageEvaluation


def _make_eval(**overrides):
    defaults = {
        "angle_coverage": 0.8, "source_diversity": 0.8,
        "depth_coverage": 0.8, "temporal_coverage": 0.8,
        "perspective_balance": 0.8, "language_coverage": 0.8,
        "overall_score": 0.8,
    }
    defaults.update(overrides)
    return CoverageEvaluation(**defaults)


class TestStrategyLanguage:

    def setup_method(self):
        self.gen = StrategyGenerator()

    def test_low_language_generates_cross_language(self):
        eval_result = _make_eval(language_coverage=0.2)
        result = self.gen.generate("Spring Boot 入门", eval_result, "bing", "week", 1)
        assert result is not None
        assert result.strategy_type == "cross_language"
        assert "Spring Boot 入门" in result.keyword

    def test_cross_language_not_duplicated(self):
        eval_result = _make_eval(language_coverage=0.1)
        history = [
            SearchStrategy(
                keyword="test", engine="bing", time_range="week",
                strategy_type="cross_language", reason="test",
            ),
        ]
        # language 最低但已尝试过 cross_language
        result = self.gen.generate("test", eval_result, "bing", "week", 2, history)
        # 应该选另一个弱维度或 None
        if result:
            assert result.strategy_type != "cross_language"

    def test_language_dimension_in_dimensions_map(self):
        """验证 language 维度已被加入策略映射"""
        eval_result = _make_eval(language_coverage=0.05)
        result = self.gen.generate("test", eval_result, "bing", "week", 1)
        assert result is not None
        assert result.strategy_type == "cross_language"

    def test_high_language_no_cross_language(self):
        eval_result = _make_eval(language_coverage=0.9, source_diversity=0.2)
        result = self.gen.generate("test", eval_result, "bing", "week", 1)
        assert result is not None
        assert result.strategy_type != "cross_language"

    def test_cross_language_reason_contains_score(self):
        eval_result = _make_eval(language_coverage=0.15)
        result = self.gen.generate("test", eval_result, "bing", "week", 1)
        assert result is not None
        assert "15%" in result.reason or "语言覆盖" in result.reason
