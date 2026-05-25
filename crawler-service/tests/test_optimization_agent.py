"""OptimizationAgent 板块感知优化 Agent 测试

覆盖：
- _map_results_to_sections() — keyword/URL/未匹配三层
- _identify_weak_sections() — 低于阈值标记、维度标注
- _rebuild_section_document() — 条目追加、聚合字段更新
- execute() — 完整流程、预算耗尽、零弱板块、错误降级
"""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass, field

from crawler.optimization_agent import (
    OptimizationAgent, OptimizationResult, WeakSection,
)
from crawler.digest_orchestrator import PlannedSection, DigestCrawlPlan
from crawler.section_document import SectionDocument, SourceEntry
from optimization.evaluator import CoverageEvaluation


# ============== 辅助工厂 ==============

def _make_section(name="tech", keywords=None, url_sources=None, rss_sources=None,
                  engine="sogou") -> PlannedSection:
    return PlannedSection(
        name=name,
        source_type="keyword",
        keywords=keywords or ["AI"],
        url_sources=url_sources or [],
        rss_sources=rss_sources or [],
        engine=engine,
    )


def _make_crawl_plan(sections=None) -> DigestCrawlPlan:
    return DigestCrawlPlan(
        sections=sections or [_make_section()],
        config_snapshot={},
    )


def _make_result(url="https://example.com/1", title="Test Article",
                 markdown="x" * 200, search_keyword="AI") -> MagicMock:
    r = MagicMock()
    r.url = url
    r.title = title
    r.markdown = markdown
    r.success = True
    r.metadata = {"search_keyword": search_keyword}
    return r


def _make_eval(overall=0.5, source_diversity=0.3, depth_coverage=0.4,
               angle_coverage=0.5, temporal_coverage=0.6,
               perspective_balance=0.4, language_coverage=0.5,
               weaknesses=None, suggestions=None) -> CoverageEvaluation:
    return CoverageEvaluation(
        overall_score=overall,
        source_diversity=source_diversity,
        depth_coverage=depth_coverage,
        angle_coverage=angle_coverage,
        temporal_coverage=temporal_coverage,
        perspective_balance=perspective_balance,
        language_coverage=language_coverage,
        weaknesses=weaknesses or [],
        suggestions=suggestions or [],
    )


def _make_agent() -> OptimizationAgent:
    return OptimizationAgent(config_snapshot={
        "engine": "sogou",
        "digest_optimization_target_score": 0.65,
    })


# ============== _map_results_to_sections 测试 ==============

class TestMapResultsToSections:
    def test_keyword_match(self):
        agent = _make_agent()
        plan = _make_crawl_plan([_make_section("AI新闻", keywords=["人工智能"])])
        r = _make_result(url="https://x.com/1", search_keyword="人工智能")
        result = agent._map_results_to_sections([r], plan)
        assert len(result["AI新闻"]) == 1

    def test_title_keyword_match(self):
        agent = _make_agent()
        plan = _make_crawl_plan([_make_section("tech", keywords=["Python"])])
        r = _make_result(title="Python 3.13 released", search_keyword="")
        result = agent._map_results_to_sections([r], plan)
        assert len(result["tech"]) == 1

    def test_url_domain_match(self):
        agent = _make_agent()
        plan = _make_crawl_plan([
            _make_section("gh", url_sources=[{"url": "https://github.com/test"}])
        ])
        r = _make_result(url="https://github.com/test/repo", search_keyword="")
        result = agent._map_results_to_sections([r], plan)
        assert len(result["gh"]) == 1

    def test_unmatched_goes_to_all(self):
        agent = _make_agent()
        plan = _make_crawl_plan([
            _make_section("a", keywords=["Python"]),
            _make_section("b", keywords=["Rust"]),
        ])
        r = _make_result(url="https://unknown.com/1", title="Random", search_keyword="")
        result = agent._map_results_to_sections([r], plan)
        # Unmatched goes to all sections
        assert len(result["a"]) == 1
        assert len(result["b"]) == 1

    def test_empty_results(self):
        agent = _make_agent()
        plan = _make_crawl_plan([_make_section()])
        result = agent._map_results_to_sections([], plan)
        assert len(result["tech"]) == 0

    def test_multiple_sections(self):
        agent = _make_agent()
        plan = _make_crawl_plan([
            _make_section("ai", keywords=["AI"]),
            _make_section("rust", keywords=["Rust"]),
        ])
        r1 = _make_result(url="https://a.com/1", search_keyword="AI")
        r2 = _make_result(url="https://b.com/2", search_keyword="Rust")
        result = agent._map_results_to_sections([r1, r2], plan)
        assert len(result["ai"]) == 1
        assert len(result["rust"]) == 1


# ============== _identify_weak_sections 测试 ==============

class TestIdentifyWeakSections:
    def test_weak_section_identified(self):
        agent = _make_agent()
        plan = _make_crawl_plan([_make_section("tech", keywords=["AI"])])
        sec_eval = {"tech": _make_eval(overall=0.4, source_diversity=0.2, depth_coverage=0.3)}
        global_eval = _make_eval(overall=0.5)
        weak = agent._identify_weak_sections(sec_eval, global_eval, plan, 0.65)
        assert len(weak) == 1
        assert weak[0].section.name == "tech"
        assert "source_diversity" in weak[0].weakest_dimensions

    def test_strong_section_skipped(self):
        agent = _make_agent()
        plan = _make_crawl_plan([_make_section("tech")])
        sec_eval = {"tech": _make_eval(overall=0.8)}
        global_eval = _make_eval(overall=0.8)
        weak = agent._identify_weak_sections(sec_eval, global_eval, plan, 0.65)
        assert len(weak) == 0

    def test_multiple_weak_dimensions(self):
        agent = _make_agent()
        plan = _make_crawl_plan([_make_section("tech")])
        sec_eval = {"tech": _make_eval(
            overall=0.3, source_diversity=0.1, depth_coverage=0.15,
            perspective_balance=0.8,
        )}
        global_eval = _make_eval(overall=0.4)
        weak = agent._identify_weak_sections(sec_eval, global_eval, plan, 0.65)
        assert len(weak) == 1
        # Should identify the 2 lowest dimensions
        dims = weak[0].weakest_dimensions
        assert len(dims) >= 1

    def test_no_eval_for_section(self):
        agent = _make_agent()
        plan = _make_crawl_plan([_make_section("tech")])
        global_eval = _make_eval(overall=0.5)
        weak = agent._identify_weak_sections({}, global_eval, plan, 0.65)
        assert len(weak) == 0


# ============== _rebuild_section_document 测试 ==============

class TestRebuildSectionDocument:
    def test_appends_entries(self):
        agent = _make_agent()
        doc = SectionDocument(section_name="tech", entries=[])
        results = [_make_result(url="https://a.com/1", markdown="Valid " * 50)]
        agent._rebuild_section_document(doc, results)
        assert doc.cleaned_count == 1
        assert len(doc.entries) == 1
        assert doc.entries[0].source_type == "optimization"

    def test_skips_short_content(self):
        agent = _make_agent()
        doc = SectionDocument(section_name="tech", entries=[])
        results = [_make_result(url="https://a.com/1", markdown="hi")]
        agent._rebuild_section_document(doc, results)
        assert doc.cleaned_count == 0

    def test_skips_duplicate_url(self):
        agent = _make_agent()
        doc = SectionDocument(
            section_name="tech",
            entries=[SourceEntry(url="https://a.com/1", cleaned_content="existing")],
        )
        results = [_make_result(url="https://a.com/1", markdown="New " * 50)]
        agent._rebuild_section_document(doc, results)
        assert doc.cleaned_count == 1  # Still only 1

    def test_updates_aggregates(self):
        agent = _make_agent()
        doc = SectionDocument(section_name="tech", entries=[])
        results = [
            _make_result(url="https://a.com/1", markdown="Content A " * 30),
            _make_result(url="https://b.com/2", markdown="Content B " * 30),
        ]
        agent._rebuild_section_document(doc, results)
        assert doc.cleaned_count == 2
        assert doc.total_word_count > 0
        assert "---" in doc.merged_content


# ============== _merge_optimized_results 测试 ==============

class TestMergeOptimizedResults:
    def test_adds_new_urls(self):
        agent = _make_agent()
        all_results = []
        seen_urls = set()
        dedup = MagicMock()
        dedup.is_duplicate.return_value = {"is_duplicate": False}
        results = [_make_result(url="https://a.com/1")]
        added = agent._merge_optimized_results(results, all_results, seen_urls, dedup)
        assert added == 1
        assert len(all_results) == 1

    def test_skips_seen_urls(self):
        agent = _make_agent()
        all_results = []
        seen_urls = {"example.com/1"}
        dedup = MagicMock()
        results = [_make_result(url="https://example.com/1")]
        added = agent._merge_optimized_results(results, all_results, seen_urls, dedup)
        assert added == 0

    def test_skips_content_dedup(self):
        agent = _make_agent()
        all_results = []
        seen_urls = set()
        dedup = MagicMock()
        dedup.is_duplicate.return_value = {"is_duplicate": True}
        results = [_make_result(url="https://a.com/1")]
        added = agent._merge_optimized_results(results, all_results, seen_urls, dedup)
        assert added == 0


# ============== execute 测试 ==============

class TestOptimizationAgentExecute:
    def _make_agent_with_mocks(self):
        agent = _make_agent()
        return agent

    def _make_crawl_context(self):
        plan = _make_crawl_plan([
            _make_section("tech", keywords=["AI"]),
            _make_section("rust", keywords=["Rust"]),
        ])
        docs = [
            SectionDocument(section_name="tech", entries=[
                SourceEntry(url="https://a.com/1", title="AI News", cleaned_content="x" * 200),
            ]),
            SectionDocument(section_name="rust", entries=[
                SourceEntry(url="https://b.com/2", title="Rust Update", cleaned_content="y" * 200),
            ]),
        ]
        results = [
            _make_result(url="https://a.com/1", title="AI News", search_keyword="AI"),
            _make_result(url="https://b.com/2", title="Rust Update", search_keyword="Rust"),
        ]
        return plan, docs, results

    @pytest.mark.asyncio
    async def test_no_weak_sections_skips(self):
        """所有板块都达标时跳过优化"""
        agent = self._make_agent_with_mocks()
        plan, docs, results = self._make_crawl_context()
        seen_urls = set()

        high_eval = _make_eval(overall=0.9)
        with patch.object(agent, "_safe_evaluate", return_value=high_eval):
            opt_result = await agent.execute(
                crawl_plan=plan, section_documents=docs, all_results=results,
                seen_urls=seen_urls, shared_crawler=MagicMock(),
                history_engine=MagicMock(), content_dedup=MagicMock(),
                config=MagicMock(), task={"id": 1},
            )

        assert opt_result.rounds_completed == 0
        assert opt_result.sections_improved == 0

    @pytest.mark.asyncio
    async def test_evaluation_failure_returns_original(self):
        """全局评估失败时返回原始数据"""
        agent = self._make_agent_with_mocks()
        plan, docs, results = self._make_crawl_context()

        with patch.object(agent, "_safe_evaluate", return_value=None):
            opt_result = await agent.execute(
                crawl_plan=plan, section_documents=docs, all_results=results,
                seen_urls=set(), shared_crawler=MagicMock(),
                history_engine=MagicMock(), content_dedup=MagicMock(),
                config=MagicMock(), task={"id": 1},
            )

        assert opt_result.rounds_completed == 0
        assert len(opt_result.all_results) == 2

    @pytest.mark.asyncio
    async def test_strategy_generation_recrawls(self):
        """弱板块触发策略生成和重爬"""
        agent = self._make_agent_with_mocks()
        plan, docs, results = self._make_crawl_context()
        seen_urls = set()

        low_eval = _make_eval(overall=0.3, source_diversity=0.1)
        high_eval = _make_eval(overall=0.6)

        mock_strategy = MagicMock()
        mock_strategy.keyword = "AI"
        mock_strategy.engine = "bing"
        mock_strategy.time_range = "week"
        mock_strategy.site_scope = None
        mock_strategy.strategy_type = "engine_switch"

        new_results = [_make_result(url="https://new.com/1", search_keyword="AI")]

        # _safe_evaluate calls: initial global(1) + per-section(2) + round1 global(1) + round2 global(1)
        eval_side_effects = [low_eval, low_eval, low_eval, high_eval, high_eval]

        with patch.object(agent, "_safe_evaluate", side_effect=eval_side_effects), \
             patch("optimization.strategy.BreadthStrategyGen") as mock_bg, \
             patch("optimization.strategy.DepthStrategyGen") as mock_dg, \
             patch("optimization.knowledge_base.KnowledgeBase") as mock_kb_cls, \
             patch("optimization.utils.save_optimization_round", new_callable=AsyncMock), \
             patch("crawler.search.crawl_by_keyword", new_callable=AsyncMock, return_value=new_results), \
             patch("ai.content_organizer") as mock_org:
            mock_org.is_available = False
            mock_bg_inst = MagicMock()
            mock_bg_inst.generate.return_value = mock_strategy
            mock_bg.return_value = mock_bg_inst
            mock_kb_inst = MagicMock()
            mock_kb_inst.get_strategy_hint = AsyncMock(return_value={})
            mock_kb_cls.return_value = mock_kb_inst

            opt_result = await agent.execute(
                crawl_plan=plan, section_documents=docs, all_results=results,
                seen_urls=seen_urls, shared_crawler=MagicMock(),
                history_engine=MagicMock(), content_dedup=MagicMock(),
                config=MagicMock(), task={"id": 1},
            )

        assert opt_result.rounds_completed >= 1

    @pytest.mark.asyncio
    async def test_empty_results_returns_empty(self):
        """空结果列表返回空"""
        agent = self._make_agent_with_mocks()
        plan = _make_crawl_plan([_make_section()])

        with patch.object(agent, "_safe_evaluate", return_value=None):
            opt_result = await agent.execute(
                crawl_plan=plan, section_documents=[], all_results=[],
                seen_urls=set(), shared_crawler=MagicMock(),
                history_engine=MagicMock(), content_dedup=MagicMock(),
                config=MagicMock(), task={"id": 1},
            )

        assert opt_result.rounds_completed == 0
        assert len(opt_result.all_results) == 0


# ============== _should_run_optimization 测试 ==============

class TestShouldRunOptimization:
    def test_enabled_with_enough_results(self):
        from crawler.digest_orchestrator import DigestOrchestrator
        orch = DigestOrchestrator()
        snap = {
            "optimization_enabled": True,
            "optimization_mode": "digest",
            "digest_optimization_enabled": True,
            "digest_optimization_min_sections": 2,
            "digest_optimization_min_results_per_section": 3,
        }
        assert orch._should_run_optimization(snap, [1, 2, 3, 4, 5, 6]) is True

    def test_disabled(self):
        from crawler.digest_orchestrator import DigestOrchestrator
        orch = DigestOrchestrator()
        snap = {
            "optimization_enabled": False,
            "optimization_mode": "digest",
            "digest_optimization_enabled": True,
            "digest_optimization_min_sections": 2,
            "digest_optimization_min_results_per_section": 3,
        }
        assert orch._should_run_optimization(snap, [1, 2, 3, 4, 5, 6]) is False

    def test_insufficient_results(self):
        from crawler.digest_orchestrator import DigestOrchestrator
        orch = DigestOrchestrator()
        snap = {
            "optimization_enabled": True,
            "optimization_mode": "digest",
            "digest_optimization_enabled": True,
            "digest_optimization_min_sections": 2,
            "digest_optimization_min_results_per_section": 3,
        }
        assert orch._should_run_optimization(snap, [1, 2]) is False

    def test_mode_keyword_excludes(self):
        from crawler.digest_orchestrator import DigestOrchestrator
        orch = DigestOrchestrator()
        snap = {
            "optimization_enabled": True,
            "optimization_mode": "keyword",
            "digest_optimization_enabled": True,
            "digest_optimization_min_sections": 2,
            "digest_optimization_min_results_per_section": 3,
        }
        assert orch._should_run_optimization(snap, [1, 2, 3, 4, 5, 6]) is False


# ============== 能力 1: 跨语言扩展测试 ==============

class TestCrossLanguageExpansion:
    @pytest.mark.asyncio
    async def test_cross_language_translates_keyword(self):
        """cross_language 策略触发翻译并使用翻译后的关键词"""
        agent = _make_agent()
        section = _make_section("ai", keywords=["人工智能"])
        ws_eval = _make_eval(overall=0.3, source_diversity=0.1)
        ws = WeakSection(section=section, evaluation=ws_eval, weakest_dimensions=["source_diversity"])

        mock_strategy = MagicMock()
        mock_strategy.keyword = "人工智能"
        mock_strategy.engine = "sogou"
        mock_strategy.time_range = "week"
        mock_strategy.site_scope = None
        mock_strategy.strategy_type = "cross_language"
        mock_strategy.reason = "cross-language expansion"
        mock_strategy.source_expand_section = None

        new_results = [_make_result(url="https://en.com/1", search_keyword="artificial intelligence")]

        mock_breadth = MagicMock()
        mock_breadth.generate.return_value = mock_strategy
        mock_kb = MagicMock()
        mock_kb.get_strategy_hint = AsyncMock(return_value={})
        mock_kb.get_similar_keyword_strategies = AsyncMock(return_value=[])

        mock_dedup = MagicMock()
        mock_dedup.is_duplicate.return_value = {"is_duplicate": False}

        with patch("optimization.bubble_breaker.BubbleBreaker") as MockBreaker, \
             patch("crawler.search.crawl_by_keyword", new_callable=AsyncMock, return_value=new_results):
            breaker_inst = MagicMock()
            breaker_inst.translate_keyword = AsyncMock(return_value="artificial intelligence")
            MockBreaker.return_value = breaker_inst

            added = await agent._recrawl_section(
                ws, MagicMock(), mock_breadth, MagicMock(), mock_kb,
                MagicMock(), [], set(), [], mock_dedup,
                {"engine": "sogou", "config": MagicMock(), "crawler": MagicMock()},
                [], 1, time.monotonic() + 60,
            )

        assert added >= 1

    @pytest.mark.asyncio
    async def test_cross_language_translation_fails_returns_zero(self):
        """翻译失败时跳过此板块"""
        agent = _make_agent()
        section = _make_section("ai", keywords=["人工智能"])
        ws_eval = _make_eval(overall=0.3, source_diversity=0.1)
        ws = WeakSection(section=section, evaluation=ws_eval, weakest_dimensions=["source_diversity"])

        mock_strategy = MagicMock()
        mock_strategy.keyword = "人工智能"
        mock_strategy.engine = "sogou"
        mock_strategy.time_range = "week"
        mock_strategy.strategy_type = "cross_language"
        mock_strategy.reason = "cross-language"

        mock_breadth = MagicMock()
        mock_breadth.generate.return_value = mock_strategy
        mock_kb = MagicMock()
        mock_kb.get_strategy_hint = AsyncMock(return_value={})
        mock_kb.get_similar_keyword_strategies = AsyncMock(return_value=[])

        with patch("optimization.bubble_breaker.BubbleBreaker") as MockBreaker:
            breaker_inst = MagicMock()
            breaker_inst.translate_keyword = AsyncMock(return_value=None)
            MockBreaker.return_value = breaker_inst

            added = await agent._recrawl_section(
                ws, MagicMock(), mock_breadth, MagicMock(), mock_kb,
                MagicMock(), [], set(), [], MagicMock(),
                {"engine": "sogou", "config": MagicMock(), "crawler": MagicMock()},
                [], 1, time.monotonic() + 60,
            )

        assert added == 0


# ============== 能力 2: source_expand 测试 ==============

class TestSourceExpand:
    @pytest.mark.asyncio
    async def test_source_expand_uses_url_sources(self):
        """source_expand 策略走 URL/RSS 爬取路径"""
        agent = _make_agent()
        section = _make_section("gh", url_sources=[{"url": "https://github.com/test"}])
        ws_eval = _make_eval(overall=0.3, source_diversity=0.1)
        ws = WeakSection(section=section, evaluation=ws_eval, weakest_dimensions=["source_diversity"])

        mock_strategy = MagicMock()
        mock_strategy.strategy_type = "source_expand"
        mock_strategy.source_expand_section = {
            "name": "gh", "url_sources": [{"url": "https://github.com/new"}],
        }
        mock_strategy.source_expand_overrides = {}

        new_results = [_make_result(url="https://github.com/new/repo1", search_keyword="")]

        mock_breadth = MagicMock()
        mock_breadth.generate.return_value = mock_strategy
        mock_kb = MagicMock()
        mock_kb.get_strategy_hint = AsyncMock(return_value={})
        mock_kb.get_similar_keyword_strategies = AsyncMock(return_value=[])

        mock_dedup = MagicMock()
        mock_dedup.is_duplicate.return_value = {"is_duplicate": False}

        with patch("crawler.digest._apply_overrides", return_value={
            "url_sources": [{"url": "https://github.com/new"}],
        }), patch("crawler.source_crawler.crawl_url_sources", new_callable=AsyncMock, return_value=new_results), \
             patch("crawler.source_crawler.crawl_rss_sources", new_callable=AsyncMock, return_value=[]):
            added = await agent._recrawl_section(
                ws, MagicMock(), mock_breadth, MagicMock(), mock_kb,
                MagicMock(), [], set(), [], mock_dedup,
                {"engine": "sogou", "config": MagicMock(), "crawler": MagicMock()},
                [], 1, time.monotonic() + 60,
            )

        assert added >= 1


# ============== 能力 4: 策略疲劳追踪测试 ==============

class TestFatigueTracking:
    def test_not_exhausted_initially(self):
        agent = _make_agent()
        agent._dimension_attempts = {}
        assert agent._is_dimension_exhausted("source_diversity") is False

    def test_not_exhausted_after_one_failure(self):
        agent = _make_agent()
        agent._dimension_attempts = {"source_diversity": [False]}
        assert agent._is_dimension_exhausted("source_diversity") is False

    def test_exhausted_after_two_failures(self):
        agent = _make_agent()
        agent._dimension_attempts = {"source_diversity": [False, False]}
        assert agent._is_dimension_exhausted("source_diversity") is True

    def test_not_exhausted_if_recent_improvement(self):
        agent = _make_agent()
        agent._dimension_attempts = {"source_diversity": [False, True]}
        assert agent._is_dimension_exhausted("source_diversity") is False

    def test_record_result_appends(self):
        agent = _make_agent()
        agent._dimension_attempts = {}
        agent._record_dimension_result("depth", True)
        agent._record_dimension_result("depth", False)
        assert agent._dimension_attempts["depth"] == [True, False]

    @pytest.mark.asyncio
    async def test_exhausted_dims_filtered_out(self):
        """已耗尽维度被过滤，导致返回 0"""
        agent = _make_agent()
        agent._dimension_attempts = {"source_diversity": [False, False]}
        section = _make_section("tech", keywords=["AI"])
        ws_eval = _make_eval(overall=0.3, source_diversity=0.1)
        ws = WeakSection(section=section, evaluation=ws_eval, weakest_dimensions=["source_diversity"])

        mock_kb = MagicMock()
        mock_kb.get_strategy_hint = AsyncMock(return_value={})
        mock_kb.get_similar_keyword_strategies = AsyncMock(return_value=[])

        added = await agent._recrawl_section(
            ws, MagicMock(), MagicMock(), MagicMock(), mock_kb,
            MagicMock(), [], set(), [], MagicMock(),
            {"engine": "sogou", "config": MagicMock(), "crawler": MagicMock()},
            [], 1, time.monotonic() + 60,
        )
        assert added == 0


# ============== 能力 5: 板块级 KB 测试 ==============

class TestSectionKB:
    def test_make_section_strategy(self):
        from optimization.strategy import SearchStrategy
        strategy = OptimizationAgent._make_section_strategy("AI", "bing", {"time_range": "week"})
        assert strategy.keyword == "AI"
        assert strategy.engine == "bing"
        assert strategy.strategy_type == "digest_section_opt"

    def test_planned_to_raw_dict(self):
        section = PlannedSection(
            name="tech", source_type="keyword",
            url_sources=[{"url": "https://github.com"}],
            rss_sources=[{"feed_url": "https://example.com/rss"}],
        )
        raw = OptimizationAgent._planned_to_raw_dict(section)
        assert raw["name"] == "tech"
        assert len(raw["url_sources"]) == 1
        assert len(raw["rss_sources"]) == 1


# ============== 能力 6: 评估弱点反馈测试 ==============

class TestWeaknessFeedback:
    def test_source_agent_boosts_max_items_for_source_diversity(self):
        """上次评估弱点含 source_diversity → SourceAgent 增加 max_items"""
        from crawler.source_agent import SourceAgent
        section = PlannedSection(
            name="tech", source_type="keyword", keywords=["AI"],
            max_items=5, effectiveness={"total_runs": 0},
        )
        agent = SourceAgent(section, MagicMock(), {})
        kb_hint = {
            "last_weaknesses": ["source_diversity"],
            "recommended_engine": "sogou",
        }
        plan = agent.analyze(kb_hint=kb_hint)
        assert plan.adjusted_max_items >= 6  # 5 * 1.2 = 6

    def test_source_agent_no_boost_without_weaknesses(self):
        """无弱点信息时不调整"""
        from crawler.source_agent import SourceAgent
        section = PlannedSection(
            name="tech", source_type="keyword", keywords=["AI"],
            max_items=5, effectiveness={"total_runs": 0},
        )
        agent = SourceAgent(section, MagicMock(), {})
        plan = agent.analyze(kb_hint={})
        assert plan.adjusted_max_items == 5

    @pytest.mark.asyncio
    async def test_kb_get_last_digest_weaknesses(self):
        """KnowledgeBase.get_last_digest_weaknesses 查询"""
        with patch("optimization.knowledge_base.get_db") as mock_db_cm:
            mock_db = AsyncMock()
            mock_cursor = AsyncMock()
            mock_cursor.fetchone.return_value = None
            mock_db.execute.return_value = mock_cursor
            mock_db.__aenter__ = AsyncMock(return_value=mock_db)
            mock_db.__aexit__ = AsyncMock(return_value=False)
            mock_db_cm.return_value = mock_db

            from optimization.knowledge_base import KnowledgeBase
            kb = KnowledgeBase()
            result = await kb.get_last_digest_weaknesses()

        assert result is None
