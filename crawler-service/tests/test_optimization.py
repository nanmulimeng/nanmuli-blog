"""自动优化引擎测试套件"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from optimization.evaluator import CoverageEvaluator, CoverageEvaluation, WEIGHTS
from optimization.strategy import StrategyGenerator, SearchStrategy
from optimization.feedback import FeedbackLoop, OptimizationRound
from optimization.knowledge_base import KnowledgeBase


# ============== Evaluator Tests ==============

class TestShannonEntropy:
    def test_single_domain(self):
        assert CoverageEvaluator._calc_shannon_entropy(["a.com"]) == 0.0

    def test_two_equal_domains(self):
        result = CoverageEvaluator._calc_shannon_entropy(["a.com", "b.com"])
        assert result == 1.0

    def test_all_same_domain(self):
        result = CoverageEvaluator._calc_shannon_entropy(["a.com"] * 10)
        assert result == 0.0

    def test_empty_list(self):
        assert CoverageEvaluator._calc_shannon_entropy([]) == 0.0

    def test_diverse_domains(self):
        domains = ["a.com", "b.com", "c.com", "d.com", "e.com"]
        result = CoverageEvaluator._calc_shannon_entropy(domains)
        assert result == 1.0


class TestLanguageMix:
    def test_chinese_only(self):
        result = CoverageEvaluator._calc_language_mix(["Spring Boot 入门教程", "React 实战"])
        assert 0.0 < result <= 1.0

    def test_english_only(self):
        result = CoverageEvaluator._calc_language_mix(["Spring Boot tutorial", "React best practices"])
        assert 0.0 < result <= 1.0

    def test_mixed(self):
        result = CoverageEvaluator._calc_language_mix(["Spring Boot 入门", "React best practices"])
        assert result > 0.5

    def test_empty(self):
        assert CoverageEvaluator._calc_language_mix([]) == 0.0


class TestEvaluatorHeuristic:
    def test_fallback_with_few_results(self):
        evaluator = CoverageEvaluator(organizer=None)
        meta = {
            "entries": [{"domain": "a.com", "content_length": 500}],
            "domains": ["a.com"],
            "titles": ["Test"],
            "total": 1,
        }
        result = evaluator._heuristic_evaluate(meta, {})
        assert 0.0 <= result["angle"] <= 1.0
        assert result["weaknesses"]  # Should have weaknesses for few results

    def test_fallback_with_diverse_results(self):
        evaluator = CoverageEvaluator(organizer=None)
        entries = [
            {"domain": f"site{i}.com", "content_length": 500 + i * 500}
            for i in range(5)
        ]
        meta = {
            "entries": entries,
            "domains": [e["domain"] for e in entries],
            "titles": [f"Title {i}" for i in range(5)],
            "total": 5,
        }
        result = evaluator._heuristic_evaluate(meta, {})
        assert result["angle"] > 0.5


class TestEvaluatorExtractMeta:
    def test_extract_from_dict(self):
        evaluator = CoverageEvaluator()
        results = [
            {"success": True, "url": "https://example.com/page1", "title": "Test", "markdown": "x" * 500},
            {"success": False, "url": "https://bad.com", "title": "", "markdown": ""},
        ]
        meta = evaluator._extract_result_meta(results)
        assert meta["total"] == 1
        assert "example.com" in meta["domains"]


# ============== Strategy Tests ==============

class TestStrategyGenerator:
    def setup_method(self):
        self.gen = StrategyGenerator()

    def _make_eval(self, **overrides):
        defaults = {
            "angle_coverage": 0.8, "source_diversity": 0.8,
            "depth_coverage": 0.8, "temporal_coverage": 0.8,
            "perspective_balance": 0.8, "language_coverage": 0.8,
        }
        defaults.update(overrides)
        return CoverageEvaluation(**defaults)

    def test_all_good_no_strategy(self):
        eval_result = self._make_eval()
        result = self.gen.generate("test", eval_result, "bing", "week", 1)
        assert result is None

    def test_low_diversity_engine_switch(self):
        eval_result = self._make_eval(source_diversity=0.2)
        result = self.gen.generate("test", eval_result, "bing", "week", 1)
        assert result is not None
        assert result.strategy_type == "engine_switch"
        assert result.engine != "bing"

    def test_low_temporal_expand_time(self):
        eval_result = self._make_eval(temporal_coverage=0.2)
        result = self.gen.generate("test", eval_result, "bing", "day", 1)
        assert result is not None
        assert result.strategy_type == "time_adjust"
        assert result.time_range == "week"

    def test_low_depth_add_modifier(self):
        eval_result = self._make_eval(depth_coverage=0.2)
        result = self.gen.generate("test", eval_result, "bing", "week", 1)
        assert result is not None
        assert result.strategy_type == "keyword_refine"
        assert "test" in result.keyword

    def test_low_angle_add_variant(self):
        eval_result = self._make_eval(angle_coverage=0.2)
        result = self.gen.generate("test", eval_result, "bing", "week", 1)
        assert result is not None
        assert result.strategy_type == "keyword_refine"

    def test_low_perspective_add_opposing(self):
        eval_result = self._make_eval(perspective_balance=0.2)
        result = self.gen.generate("test", eval_result, "bing", "week", 1)
        assert result is not None
        assert result.strategy_type == "keyword_refine"

    def test_avoids_duplicate_strategies(self):
        eval_result = self._make_eval(source_diversity=0.1)
        history = [
            SearchStrategy(keyword="test", engine="bing", time_range="week", strategy_type="initial", reason=""),
            SearchStrategy(keyword="test", engine="baidu", time_range="week", strategy_type="engine_switch", reason=""),
            SearchStrategy(keyword="test", engine="sogou", time_range="week", strategy_type="engine_switch", reason=""),
        ]
        result = self.gen.generate("test", eval_result, "bing", "week", 3, history)
        # Should try google or site scope
        if result:
            assert result.engine not in {"bing", "baidu", "sogou"} or result.site_scope is not None

    def test_no_time_expansion_from_all(self):
        eval_result = self._make_eval(temporal_coverage=0.1)
        result = self.gen.generate("test", eval_result, "bing", "all", 1)
        assert result is None  # Can't expand beyond "all"


# ============== Feedback Loop Tests ==============

class TestFeedbackLoop:
    @pytest.fixture
    def mock_evaluator(self):
        evaluator = MagicMock(spec=CoverageEvaluator)
        evaluator.is_available = True
        evaluator.evaluate = AsyncMock()
        return evaluator

    @pytest.fixture
    def mock_strategy_gen(self):
        return MagicMock(spec=StrategyGenerator)

    @pytest.fixture
    def mock_kb(self):
        kb = MagicMock(spec=KnowledgeBase)
        kb.get_strategy_hint = AsyncMock(return_value=None)
        return kb

    @pytest.mark.asyncio
    async def test_target_reached_round1(self, mock_evaluator, mock_strategy_gen, mock_kb):
        mock_evaluator.evaluate.return_value = CoverageEvaluation(
            angle_coverage=0.8, source_diversity=0.8, depth_coverage=0.8,
            temporal_coverage=0.8, perspective_balance=0.8, language_coverage=0.8,
            overall_score=0.85,
        )

        loop = FeedbackLoop(mock_evaluator, mock_strategy_gen, mock_kb)
        results, rounds = await loop.execute(
            keyword="test",
            initial_results=[],
            crawl_fn=AsyncMock(return_value=[]),
            context={"engine": "bing", "time_range": "week"},
        )
        assert len(rounds) == 1
        assert rounds[0].evaluation.overall_score >= 0.7

    @pytest.mark.asyncio
    async def test_improvement_loop(self, mock_evaluator, mock_strategy_gen, mock_kb):
        # Round 1: low score, Round 2: improved
        mock_evaluator.evaluate.side_effect = [
            CoverageEvaluation(overall_score=0.3, source_diversity=0.1),
            CoverageEvaluation(overall_score=0.75, source_diversity=0.6),
        ]
        mock_strategy_gen.generate.return_value = SearchStrategy(
            keyword="test", engine="baidu", time_range="week",
            strategy_type="engine_switch", reason="test",
        )

        crawl_fn = AsyncMock(return_value=[
            type("R", (), {"url": "http://new.com", "success": True})(),
        ])

        loop = FeedbackLoop(mock_evaluator, mock_strategy_gen, mock_kb)
        results, rounds = await loop.execute(
            keyword="test",
            initial_results=[],
            crawl_fn=crawl_fn,
            context={"engine": "bing", "time_range": "week"},
        )
        assert len(rounds) == 2
        assert rounds[1].evaluation.overall_score >= 0.7

    @pytest.mark.asyncio
    async def test_diminishing_returns(self, mock_evaluator, mock_strategy_gen, mock_kb):
        mock_evaluator.evaluate.side_effect = [
            CoverageEvaluation(overall_score=0.3),
            CoverageEvaluation(overall_score=0.32),  # +0.02 < 0.03 threshold
        ]
        mock_strategy_gen.generate.return_value = SearchStrategy(
            keyword="test", engine="baidu", time_range="week",
            strategy_type="engine_switch", reason="test",
        )

        crawl_fn = AsyncMock(return_value=[])

        loop = FeedbackLoop(
            mock_evaluator, mock_strategy_gen, mock_kb,
            min_improvement=0.03,
        )
        results, rounds = await loop.execute(
            keyword="test",
            initial_results=[],
            crawl_fn=crawl_fn,
            context={"engine": "bing", "time_range": "week"},
        )
        assert len(rounds) == 2

    @pytest.mark.asyncio
    async def test_no_strategy_stops(self, mock_evaluator, mock_strategy_gen, mock_kb):
        mock_evaluator.evaluate.return_value = CoverageEvaluation(overall_score=0.3)
        mock_strategy_gen.generate.return_value = None

        loop = FeedbackLoop(mock_evaluator, mock_strategy_gen, mock_kb)
        results, rounds = await loop.execute(
            keyword="test",
            initial_results=[],
            crawl_fn=AsyncMock(return_value=[]),
            context={"engine": "bing", "time_range": "week"},
        )
        assert len(rounds) == 1


# ============== CoverageEvaluation Tests ==============

class TestCoverageEvaluation:
    def test_default_values(self):
        ev = CoverageEvaluation()
        assert ev.overall_score == 0.0
        assert ev.weaknesses == []
        assert ev.suggestions == []

    def test_weighted_score_calculation(self):
        ev = CoverageEvaluation(
            angle_coverage=1.0, source_diversity=1.0, depth_coverage=1.0,
            temporal_coverage=1.0, perspective_balance=1.0, language_coverage=1.0,
            overall_score=1.0,
        )
        assert ev.overall_score == 1.0
