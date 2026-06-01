"""自动优化引擎测试套件"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from optimization.evaluator import CoverageEvaluator, CoverageEvaluation
from optimization.strategy import StrategyGenerator, DepthStrategyGen, BreadthStrategyGen, SearchStrategy
from optimization.feedback import FeedbackLoop, OptimizationRound
from optimization.knowledge_base import KnowledgeBase


# ============== Evaluator Tests ==============

class TestShannonEntropy:
    def test_single_domain(self):
        assert CoverageEvaluator.calc_shannon_entropy(["a.com"]) == 0.0

    def test_two_equal_domains(self):
        result = CoverageEvaluator.calc_shannon_entropy(["a.com", "b.com"])
        # 2 unique domains < 3 threshold → sample_penalty = 2/6 ≈ 0.333
        assert abs(result - 1/3) < 0.01

    def test_all_same_domain(self):
        result = CoverageEvaluator.calc_shannon_entropy(["a.com"] * 10)
        assert result == 0.0

    def test_empty_list(self):
        assert CoverageEvaluator.calc_shannon_entropy([]) == 0.0

    def test_diverse_domains(self):
        domains = ["a.com", "b.com", "c.com", "d.com", "e.com"]
        result = CoverageEvaluator.calc_shannon_entropy(domains)
        assert result == 1.0


class TestLanguageMix:
    def test_chinese_only(self):
        result = CoverageEvaluator.calc_language_mix(["Spring Boot 入门教程", "React 实战"])
        assert 0.0 < result <= 1.0

    def test_english_only(self):
        result = CoverageEvaluator.calc_language_mix(["Spring Boot tutorial", "React best practices"])
        assert 0.0 < result <= 1.0

    def test_mixed(self):
        result = CoverageEvaluator.calc_language_mix(["Spring Boot 入门", "React best practices"])
        assert result > 0.5

    def test_empty(self):
        assert CoverageEvaluator.calc_language_mix([]) == 0.0


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

    def test_digest_fallback_uses_section_coverage(self):
        evaluator = CoverageEvaluator(organizer=None)
        entries = [
            {"domain": "github.blog", "content_length": 900},
            {"domain": "github.com", "content_length": 2600},
            {"domain": "engineering.example.com", "content_length": 4200},
        ]
        meta = {
            "entries": entries,
            "domains": [e["domain"] for e in entries],
            "titles": ["GitHub update", "Open source project", "Architecture case study"],
            "total": 3,
        }
        result = evaluator._heuristic_evaluate(
            meta,
            {
                "task_type": "digest",
                "time_range": "week",
                "section_result_counts": {"hot_trend": 2, "open_source": 1, "tech_article": 1},
            },
        )
        assert result["angle"] >= 0.8
        assert result["depth"] >= 0.7
        assert result["temporal"] >= 0.55

    def test_digest_eval_prompt_mentions_digest_rubric(self):
        evaluator = CoverageEvaluator(organizer=None)
        meta = {
            "entries": [],
            "domains": [],
            "titles": [],
            "total": 0,
        }
        prompt = evaluator._build_eval_prompt(
            "technology digest",
            meta,
            {
                "task_type": "digest",
                "section_result_counts": {"hot_trend": 4, "open_source": 3, "tech_article": 3},
            },
        )
        assert "daily technical digest" in prompt
        assert "Digest sections: hot_trend=4" in prompt
        assert "do not require pro/con debate" in prompt

    @pytest.mark.asyncio
    async def test_digest_evaluate_skips_ai_call(self):
        organizer = MagicMock()
        organizer.is_available = True
        organizer._call_ai = AsyncMock()
        evaluator = CoverageEvaluator(organizer=organizer)
        results = [
            {
                "success": True,
                "url": "https://github.blog/engineering/example",
                "title": "Architecture example",
                "markdown": "Detailed engineering writeup " * 100,
                "metadata": {"section_category": "tech_article"},
            }
        ]

        evaluation = await evaluator.evaluate(
            "technology digest",
            results,
            {"task_type": "digest", "section_result_counts": {"tech_article": 1}, "time_range": "week"},
        )

        organizer._call_ai.assert_not_awaited()
        assert evaluation.tokens_used == 0
        assert evaluation.overall_score > 0


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

    # ============== Source Expand Tests ==============

    @staticmethod
    def _sec(name, url_sources=None, rss_sources=None, effectiveness=None):
        """Helper: build a section dict with default effectiveness."""
        sec = {"name": name}
        if url_sources:
            sec["url_sources"] = url_sources
        if rss_sources:
            sec["rss_sources"] = rss_sources
        sec["effectiveness"] = effectiveness or {"avg_quality": 50, "success_rate": 0.5, "total_runs": 0, "dead": False}
        return sec

    def test_source_expand_when_diversity_low_with_url_sources(self):
        """source_diversity 最低且有 URL 源时，生成 source_expand 策略"""
        eval_result = self._make_eval(source_diversity=0.2)
        sections = [self._sec("tech", url_sources=[{"url": "https://example.com"}])]
        result = self.gen.generate("AI", eval_result, "bing", "week", 2, sections=sections)
        assert result is not None
        assert result.strategy_type == "source_expand"
        assert result.source_expand_section["name"] == "tech"
        assert "tech" in result.reason

    def test_source_expand_when_angle_low_with_rss_sources(self):
        """angle 是深度维度，低时走 keyword_refine 而非 source_expand"""
        eval_result = self._make_eval(angle_coverage=0.2)
        sections = [self._sec("news", rss_sources=[{"feed_url": "https://example.com/feed"}])]
        result = self.gen.generate("AI", eval_result, "bing", "week", 2, sections=sections)
        assert result is not None
        assert result.strategy_type == "keyword_refine"

    def test_source_expand_not_triggered_for_temporal(self):
        """temporal 维度最弱时不触发 source_expand，走深度策略"""
        eval_result = self._make_eval(temporal_coverage=0.1)
        sections = [self._sec("tech", url_sources=[{"url": "https://example.com"}])]
        result = self.gen.generate("AI", eval_result, "bing", "day", 2, sections=sections)
        assert result is not None
        assert result.strategy_type == "time_adjust"

    def test_source_expand_not_triggered_for_depth(self):
        """depth 维度最弱时不触发 source_expand，走深度策略"""
        eval_result = self._make_eval(depth_coverage=0.1)
        sections = [self._sec("tech", url_sources=[{"url": "https://example.com"}])]
        result = self.gen.generate("AI", eval_result, "bing", "week", 2, sections=sections)
        assert result is not None
        assert result.strategy_type == "keyword_refine"

    def test_source_expand_fallback_when_no_sources(self):
        """sections 为空或无 URL/RSS 源时，回退到深度策略"""
        eval_result = self._make_eval(source_diversity=0.2)
        result = self.gen.generate("AI", eval_result, "bing", "week", 2, sections=[])
        assert result is not None
        assert result.strategy_type == "engine_switch"
        sections = [{"name": "kw", "keyword": "AI"}]
        result2 = self.gen.generate("AI", eval_result, "bing", "week", 2, sections=sections)
        assert result2 is not None
        assert result2.strategy_type == "engine_switch"

    def test_source_expand_rotates_sections(self):
        """多个板块时轮转使用，不重复"""
        eval_result = self._make_eval(source_diversity=0.1)
        sections = [
            self._sec("A", url_sources=[{"url": "https://a.com"}]),
            self._sec("B", rss_sources=[{"feed_url": "https://b.com/feed"}]),
        ]
        s1 = self.gen.generate("AI", eval_result, "bing", "week", 2, sections=sections)
        assert s1 is not None
        assert s1.strategy_type == "source_expand"
        assert s1.source_expand_section["name"] == "A"

        s2 = self.gen.generate("AI", eval_result, "bing", "week", 3, history=[s1], sections=sections)
        assert s2 is not None
        assert s2.strategy_type == "source_expand"
        assert s2.source_expand_section["name"] == "B"

    def test_source_expand_reuse_after_all_used(self):
        """所有板块都用过后不再回退 source_expand，应切换到其他策略"""
        eval_result = self._make_eval(source_diversity=0.1)
        sections = [self._sec("only", url_sources=[{"url": "https://a.com"}])]
        s1 = self.gen.generate("AI", eval_result, "bing", "week", 2, sections=sections)
        assert s1.source_expand_section["name"] == "only"
        s2 = self.gen.generate("AI", eval_result, "bing", "week", 3, history=[s1], sections=sections)
        assert s2 is not None
        assert s2.strategy_type != "source_expand"

    def test_source_expand_none_sections(self):
        """sections=None 时不触发 source_expand，正常走深度策略"""
        eval_result = self._make_eval(source_diversity=0.2)
        result = self.gen.generate("AI", eval_result, "bing", "week", 2, sections=None)
        assert result is not None
        assert result.strategy_type == "engine_switch"

    # ============== Effectiveness Tests ==============

    def test_pick_expand_prefers_effective_section(self):
        """效能高的板块优先被选择"""
        eval_result = self._make_eval(source_diversity=0.1)
        sections = [
            self._sec("low", url_sources=[{"url": "https://low.com"}],
                      effectiveness={"avg_quality": 20, "success_rate": 0.3, "total_runs": 5, "dead": False}),
            self._sec("high", rss_sources=[{"feed_url": "https://high.com/feed"}],
                      effectiveness={"avg_quality": 80, "success_rate": 0.9, "total_runs": 10, "dead": False}),
        ]
        result = self.gen.generate("AI", eval_result, "bing", "week", 2, sections=sections)
        assert result.source_expand_section["name"] == "high"

    def test_pick_expand_skips_dead_section(self):
        """dead 板块在无其他选择时才被选中"""
        eval_result = self._make_eval(source_diversity=0.1)
        sections = [
            self._sec("dead", url_sources=[{"url": "https://dead.com"}],
                      effectiveness={"avg_quality": 10, "success_rate": 0.1, "total_runs": 5, "dead": True}),
            self._sec("ok", url_sources=[{"url": "https://ok.com"}],
                      effectiveness={"avg_quality": 50, "success_rate": 0.7, "total_runs": 3, "dead": False}),
        ]
        result = self.gen.generate("AI", eval_result, "bing", "week", 2, sections=sections)
        assert result.source_expand_section["name"] == "ok"

    # ============== Override Tests ==============

    def test_generate_overrides_freshness_expansion(self):
        """高质量低结果 → freshness_multiplier=2.0"""
        eval_result = self._make_eval(source_diversity=0.1)
        section = self._sec("good",
            rss_sources=[{"feed_url": "https://good.com/feed", "freshness_hours": 24, "source_id": 1}],
            effectiveness={"avg_quality": 70, "success_rate": 0.8, "total_runs": 5, "dead": False},
        )
        result = self.gen.generate("AI", eval_result, "bing", "week", 2, sections=[section])
        assert result is not None
        assert result.source_expand_overrides is not None
        assert result.source_expand_overrides.get("freshness_multiplier") == 2.0

    def test_generate_overrides_skip_dead_source(self):
        """板块内单源失败率 >80% → skip_source_ids"""
        eval_result = self._make_eval(source_diversity=0.1)
        section = self._sec("mixed",
            url_sources=[
                {"url": "https://good.com", "source_id": 10, "effectiveness": {"success_count": 5, "fail_count": 1, "avg_quality_score": 80}},
                {"url": "https://dead.com", "source_id": 20, "effectiveness": {"success_count": 0, "fail_count": 5, "avg_quality_score": 0}},
            ],
            effectiveness={"avg_quality": 50, "success_rate": 0.5, "total_runs": 5, "dead": False},
        )
        result = self.gen.generate("AI", eval_result, "bing", "week", 2, sections=[section])
        assert result is not None
        overrides = result.source_expand_overrides
        assert overrides is not None
        assert 20 in overrides.get("skip_source_ids", [])

    def test_generate_overrides_insufficient_data(self):
        """total_runs < 3 → 无 overrides"""
        eval_result = self._make_eval(source_diversity=0.1)
        section = self._sec("new",
            url_sources=[{"url": "https://new.com"}],
            effectiveness={"avg_quality": 80, "success_rate": 1.0, "total_runs": 1, "dead": False},
        )
        result = self.gen.generate("AI", eval_result, "bing", "week", 2, sections=[section])
        assert result is not None
        assert result.source_expand_overrides is None

    def test_apply_overrides_freshness(self):
        """_apply_overrides 正确扩展 freshness_hours"""
        from crawler.digest import apply_overrides as _apply_overrides
        section = {
            "name": "test", "max_items": 5,
            "rss_sources": [{"feed_url": "https://x.com/feed", "freshness_hours": 24}],
            "url_sources": [],
        }
        overrides = {"freshness_multiplier": 2.0}
        result = _apply_overrides(section, overrides)
        assert result["rss_sources"][0]["freshness_hours"] == 48
        assert section["rss_sources"][0]["freshness_hours"] == 24  # original unchanged

    def test_apply_overrides_skip_ids(self):
        """_apply_overrides 过滤死源"""
        from crawler.digest import apply_overrides as _apply_overrides
        section = {
            "name": "test", "max_items": 5,
            "url_sources": [
                {"url": "https://keep.com", "source_id": 1},
                {"url": "https://skip.com", "source_id": 2},
            ],
            "rss_sources": [{"feed_url": "https://r.com/feed", "source_id": 3}],
        }
        overrides = {"skip_source_ids": [2, 3]}
        result = _apply_overrides(section, overrides)
        assert len(result["url_sources"]) == 1
        assert result["url_sources"][0]["url"] == "https://keep.com"
        assert len(result["rss_sources"]) == 0

    def test_apply_overrides_none(self):
        """overrides=None 返回原 section"""
        from crawler.digest import apply_overrides as _apply_overrides
        section = {"name": "test", "max_items": 5}
        result = _apply_overrides(section, None)
        assert result == section


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
        # Round 1: low depth score, Round 2: depth score reaches target
        mock_evaluator.evaluate.side_effect = [
            CoverageEvaluation(overall_score=0.3, source_diversity=0.1,
                               depth_coverage=0.2, angle_coverage=0.2, temporal_coverage=0.2),
            CoverageEvaluation(overall_score=0.75, source_diversity=0.6,
                               depth_coverage=0.8, angle_coverage=0.8, temporal_coverage=0.8),
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
            CoverageEvaluation(overall_score=0.32),
            CoverageEvaluation(overall_score=0.33),  # +0.01 < 0.03 threshold
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
        assert len(rounds) == 3

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


# ============== Depth/Breadth Split Tests ==============

class TestDepthStrategyGen:
    def setup_method(self):
        self.gen = DepthStrategyGen()

    def _make_eval(self, **overrides):
        defaults = {
            "angle_coverage": 0.8, "source_diversity": 0.8,
            "depth_coverage": 0.8, "temporal_coverage": 0.8,
            "perspective_balance": 0.8, "language_coverage": 0.8,
        }
        defaults.update(overrides)
        return CoverageEvaluation(**defaults)

    def test_depth_only_responds_to_depth_dims(self):
        """depth 低时生成 keyword_refine"""
        ev = self._make_eval(depth_coverage=0.1)
        result = self.gen.generate("test", ev, "bing", "week", 1)
        assert result is not None
        assert result.strategy_type == "keyword_refine"

    def test_depth_responds_to_temporal(self):
        """temporal 低时生成 time_adjust"""
        ev = self._make_eval(temporal_coverage=0.1)
        result = self.gen.generate("test", ev, "bing", "day", 1)
        assert result is not None
        assert result.strategy_type == "time_adjust"

    def test_depth_responds_to_angle(self):
        """angle 低时生成 keyword_refine"""
        ev = self._make_eval(angle_coverage=0.1)
        result = self.gen.generate("test", ev, "bing", "week", 1)
        assert result is not None
        assert result.strategy_type == "keyword_refine"

    def test_depth_ignores_breadth_dims(self):
        """广度维度低时不生成策略（所有深度维度都高）"""
        ev = self._make_eval(source_diversity=0.1, perspective_balance=0.1, language_coverage=0.1)
        result = self.gen.generate("test", ev, "bing", "week", 1)
        assert result is None

    def test_all_good_no_strategy(self):
        ev = self._make_eval()
        result = self.gen.generate("test", ev, "bing", "week", 1)
        assert result is None


class TestBreadthStrategyGen:
    def setup_method(self):
        self.gen = BreadthStrategyGen()

    def _make_eval(self, **overrides):
        defaults = {
            "angle_coverage": 0.8, "source_diversity": 0.8,
            "depth_coverage": 0.8, "temporal_coverage": 0.8,
            "perspective_balance": 0.8, "language_coverage": 0.8,
        }
        defaults.update(overrides)
        return CoverageEvaluation(**defaults)

    def test_breadth_responds_to_low_diversity(self):
        """source_diversity 低时生成 engine_switch"""
        ev = self._make_eval(source_diversity=0.1)
        result = self.gen.generate("test", ev, "bing", "week", 1)
        assert result is not None
        assert result.strategy_type == "engine_switch"

    def test_breadth_generates_cross_language(self):
        """language_coverage 低时生成 cross_language"""
        ev = self._make_eval(language_coverage=0.1)
        result = self.gen.generate("test", ev, "bing", "week", 1)
        assert result is not None
        assert result.strategy_type == "cross_language"

    def test_breadth_generates_perspective(self):
        """perspective 低时生成 keyword_refine"""
        ev = self._make_eval(perspective_balance=0.1)
        result = self.gen.generate("test", ev, "bing", "week", 1)
        assert result is not None
        assert result.strategy_type == "keyword_refine"

    def test_breadth_generates_source_expand(self):
        """source_diversity 低且有 URL 源时生成 source_expand"""
        ev = self._make_eval(source_diversity=0.1)
        sections = [{"name": "tech", "url_sources": [{"url": "https://example.com"}], "effectiveness": {"avg_quality": 50, "success_rate": 0.5, "total_runs": 0, "dead": False}}]
        result = self.gen.generate("AI", ev, "bing", "week", 2, sections=sections)
        assert result is not None
        assert result.strategy_type == "source_expand"

    def test_breadth_ignores_depth_dims(self):
        """深度维度低时不生成策略（所有广度维度都高）"""
        ev = self._make_eval(depth_coverage=0.1, angle_coverage=0.1, temporal_coverage=0.1)
        result = self.gen.generate("test", ev, "bing", "week", 1)
        assert result is None

    def test_all_good_no_strategy(self):
        ev = self._make_eval()
        result = self.gen.generate("test", ev, "bing", "week", 1)
        assert result is None


class TestBreadthExpander:
    @pytest.fixture
    def mock_evaluator(self):
        evaluator = MagicMock(spec=CoverageEvaluator)
        evaluator.is_available = True
        evaluator.evaluate = AsyncMock()
        return evaluator

    @pytest.fixture
    def mock_breadth_gen(self):
        return MagicMock(spec=BreadthStrategyGen)

    @pytest.fixture
    def mock_kb(self):
        kb = MagicMock(spec=KnowledgeBase)
        kb.get_strategy_hint = AsyncMock(return_value=None)
        return kb

    @pytest.fixture
    def mock_breaker(self):
        from optimization.bubble_breaker import BubbleBreaker
        breaker = MagicMock(spec=BubbleBreaker)
        breaker.translate_keyword = AsyncMock(return_value=None)
        return breaker

    @pytest.mark.asyncio
    async def test_breadth_loop_stops_on_target(self, mock_evaluator, mock_breadth_gen, mock_kb, mock_breaker):
        """广度三维已达标时只跑 1 轮"""
        from optimization.bubble_breaker import BreadthExpander
        mock_evaluator.evaluate.return_value = CoverageEvaluation(
            source_diversity=0.9, perspective_balance=0.85, language_coverage=0.8,
            overall_score=0.85,
        )
        expander = BreadthExpander(mock_evaluator, mock_breadth_gen, mock_kb, mock_breaker)
        results, rounds = await expander.execute(
            keyword="test", initial_results=[],
            crawl_fn=AsyncMock(return_value=[]),
            context={"engine": "bing", "time_range": "week"},
        )
        assert len(rounds) == 1

    @pytest.mark.asyncio
    async def test_breadth_loop_expands_sources(self, mock_evaluator, mock_breadth_gen, mock_kb, mock_breaker):
        """广度不足时执行扩展循环"""
        from optimization.bubble_breaker import BreadthExpander
        mock_evaluator.evaluate.side_effect = [
            CoverageEvaluation(source_diversity=0.1, perspective_balance=0.8, language_coverage=0.8, overall_score=0.4),
            CoverageEvaluation(source_diversity=0.7, perspective_balance=0.85, language_coverage=0.8, overall_score=0.78),
        ]
        mock_breadth_gen.generate.return_value = SearchStrategy(
            keyword="test", engine="baidu", time_range="week",
            strategy_type="engine_switch", reason="test",
        )
        crawl_fn = AsyncMock(return_value=[
            type("R", (), {"url": "http://new.com", "success": True})(),
        ])
        expander = BreadthExpander(mock_evaluator, mock_breadth_gen, mock_kb, mock_breaker)
        results, rounds = await expander.execute(
            keyword="test", initial_results=[],
            crawl_fn=crawl_fn,
            context={"engine": "bing", "time_range": "week"},
        )
        assert len(rounds) == 2

    @pytest.mark.asyncio
    async def test_breadth_loop_cross_language(self, mock_evaluator, mock_breadth_gen, mock_kb, mock_breaker):
        """跨语言策略正确翻译关键词"""
        from optimization.bubble_breaker import BreadthExpander
        mock_evaluator.evaluate.side_effect = [
            CoverageEvaluation(source_diversity=0.5, perspective_balance=0.5, language_coverage=0.1, overall_score=0.3),
            CoverageEvaluation(source_diversity=0.8, perspective_balance=0.8, language_coverage=0.8, overall_score=0.8),
        ]
        mock_breadth_gen.generate.return_value = SearchStrategy(
            keyword="测试", engine="bing", time_range="week",
            strategy_type="cross_language", reason="test",
        )
        mock_breaker.translate_keyword = AsyncMock(return_value="test keyword")
        crawl_fn = AsyncMock(return_value=[
            type("R", (), {"url": "http://en.com", "success": True})(),
        ])
        expander = BreadthExpander(mock_evaluator, mock_breadth_gen, mock_kb, mock_breaker)
        results, rounds = await expander.execute(
            keyword="测试", initial_results=[],
            crawl_fn=crawl_fn,
            context={"engine": "bing", "time_range": "week"},
        )
        assert len(rounds) == 2
        # crawl_fn 应收到翻译后的关键词
        call_args = crawl_fn.call_args
        assert call_args.kwargs.get("keyword") == "test keyword" or call_args[1].get("keyword") == "test keyword"


# ============== KnowledgeBase Digest Eval Tests ==============

# Minimal DDL for in-memory test DB — only tables needed by the FK chain
_MEMORY_DDL = """
CREATE TABLE IF NOT EXISTS crawl_task (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    task_type       TEXT NOT NULL DEFAULT 'single',
    source_url      TEXT,
    keyword         TEXT,
    search_engine   TEXT DEFAULT 'bing',
    max_depth       INTEGER DEFAULT 1,
    max_pages       INTEGER DEFAULT 10,
    status          INTEGER NOT NULL DEFAULT 0,
    time_range      TEXT DEFAULT 'week',
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS optimization_record (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id         INTEGER NOT NULL REFERENCES crawl_task(id) ON DELETE CASCADE,
    round_num       INTEGER NOT NULL,
    angle_coverage  REAL,
    source_diversity REAL,
    depth_coverage  REAL,
    temporal_coverage REAL,
    perspective_balance REAL,
    language_coverage REAL,
    overall_score   REAL,
    search_keyword  TEXT,
    search_engine   TEXT,
    time_range      TEXT,
    strategy_type   TEXT,
    strategy_detail TEXT,
    weaknesses      TEXT,
    suggestions     TEXT,
    urls_before     INTEGER,
    urls_after      INTEGER,
    score_delta     REAL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


class TestKnowledgeBaseDigestEval:
    """Tests for KnowledgeBase.save_digest_evaluation and get_digest_quality_trend."""

    @pytest.fixture
    def memory_db(self):
        """Provide an in-memory SQLite connection with required tables."""
        import aiosqlite

        async def _make():
            db = await aiosqlite.connect(":memory:")
            db.row_factory = aiosqlite.Row
            await db.execute("PRAGMA foreign_keys=ON")
            await db.executescript(_MEMORY_DDL)
            await db.commit()
            return db

        return _make

    async def _insert_crawl_task(self, db) -> int:
        """Insert a minimal crawl_task row and return its id."""
        import aiosqlite
        cursor = await db.execute(
            "INSERT INTO crawl_task (task_type, status) VALUES ('digest', 3)"
        )
        await db.commit()
        return cursor.lastrowid

    @pytest.mark.asyncio
    async def test_save_digest_evaluation_writes_record(self, memory_db):
        from optimization.knowledge_base import KnowledgeBase
        from unittest.mock import patch, AsyncMock
        from contextlib import asynccontextmanager
        import json

        db = await memory_db()
        task_id = await self._insert_crawl_task(db)

        @asynccontextmanager
        async def _fake_get_db():
            yield db

        with patch("optimization.knowledge_base.get_db", _fake_get_db):
            kb = KnowledgeBase()
            await kb.save_digest_evaluation(
                task_id=task_id,
                digest_date="2026-05-25",
                overall_score=0.78,
                dimension_scores={
                    "angle": 0.8,
                    "source_diversity": 0.7,
                    "depth": 0.9,
                    "temporal": 0.6,
                    "perspective": 0.75,
                    "language": 0.85,
                },
                section_scores=[{"section": "tech", "score": 0.9}],
                suggestions=["增加深度分析", "补充对比视角"],
            )

        # Verify the record was written correctly
        cursor = await db.execute(
            "SELECT * FROM optimization_record WHERE task_id = ?", (task_id,)
        )
        rows = await cursor.fetchall()
        assert len(rows) == 1

        row = dict(rows[0])
        assert row["round_num"] == 0
        assert row["overall_score"] == 0.78
        assert row["angle_coverage"] == 0.8
        assert row["source_diversity"] == 0.7
        assert row["depth_coverage"] == 0.9
        assert row["temporal_coverage"] == 0.6
        assert row["perspective_balance"] == 0.75
        assert row["language_coverage"] == 0.85
        assert row["search_keyword"] == "2026-05-25"
        assert row["search_engine"] == "digest"
        assert row["strategy_type"] == "digest_final_eval"
        assert row["urls_before"] == 0
        assert row["urls_after"] == 0
        assert row["score_delta"] == 0.0

        # JSON fields
        assert json.loads(row["strategy_detail"]) == [{"section": "tech", "score": 0.9}]
        assert json.loads(row["suggestions"]) == ["增加深度分析", "补充对比视角"]

        await db.close()

    @pytest.mark.asyncio
    async def test_get_digest_quality_trend_returns_records(self, memory_db):
        from optimization.knowledge_base import KnowledgeBase
        from unittest.mock import patch
        from contextlib import asynccontextmanager
        import json

        db = await memory_db()

        # Insert two crawl tasks + two eval records
        tid1 = await self._insert_crawl_task(db)
        tid2 = await self._insert_crawl_task(db)

        await db.execute(
            """INSERT INTO optimization_record
               (task_id, round_num, overall_score, search_keyword, search_engine,
                strategy_type, strategy_detail, suggestions, created_at)
               VALUES (?, 0, ?, ?, 'digest', 'digest_final_eval', ?, ?,
                       datetime('now', '-1 day'))""",
            (tid1, 0.65, "2026-05-24", json.dumps([]), json.dumps(["suggestion A"])),
        )
        await db.execute(
            """INSERT INTO optimization_record
               (task_id, round_num, overall_score, search_keyword, search_engine,
                strategy_type, strategy_detail, suggestions, created_at)
               VALUES (?, 0, ?, ?, 'digest', 'digest_final_eval', ?, ?,
                       datetime('now'))""",
            (tid2, 0.82, "2026-05-25", json.dumps([{"sec": "news", "s": 0.8}]), json.dumps([])),
        )
        await db.commit()

        @asynccontextmanager
        async def _fake_get_db():
            yield db

        with patch("optimization.knowledge_base.get_db", _fake_get_db):
            kb = KnowledgeBase()
            trend = await kb.get_digest_quality_trend(limit=10)

        assert len(trend) == 2
        # Most recent first
        assert trend[0]["digest_date"] == "2026-05-25"
        assert trend[0]["overall_score"] == 0.82
        assert trend[1]["digest_date"] == "2026-05-24"
        assert trend[1]["overall_score"] == 0.65

        # JSON fields auto-parsed
        assert trend[0]["strategy_detail"] == [{"sec": "news", "s": 0.8}]
        assert trend[1]["suggestions"] == ["suggestion A"]

        await db.close()

    @pytest.mark.asyncio
    async def test_get_digest_quality_trend_empty(self, memory_db):
        from optimization.knowledge_base import KnowledgeBase
        from unittest.mock import patch
        from contextlib import asynccontextmanager

        db = await memory_db()

        @asynccontextmanager
        async def _fake_get_db():
            yield db

        with patch("optimization.knowledge_base.get_db", _fake_get_db):
            kb = KnowledgeBase()
            trend = await kb.get_digest_quality_trend()

        assert trend == []

        await db.close()
