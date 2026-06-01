"""OptimizationAgent 单元测试"""

import crawler.config as _crawler_config  # noqa: F401

import asyncio
import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass, field


# ============== 辅助工厂 ==============

def _make_section(name="tech", keywords=None, url_sources=None, rss_sources=None,
                  engine="sogou") -> "PlannedSection":
    from crawler.digest_orchestrator import PlannedSection
    return PlannedSection(
        name=name,
        source_type="keyword",
        keywords=keywords or ["AI"],
        url_sources=url_sources or [],
        rss_sources=rss_sources or [],
        engine=engine,
    )


def _make_crawl_plan(sections=None) -> "DigestCrawlPlan":
    from crawler.digest_orchestrator import DigestCrawlPlan
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
               weaknesses=None, suggestions=None) -> "CoverageEvaluation":
    from optimization.evaluator import CoverageEvaluation
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


def _make_agent() -> "OptimizationAgent":
    from crawler.optimization_agent import OptimizationAgent
    return OptimizationAgent(config_snapshot={
        "engine": "sogou",
        "digest_optimization_target_score": 0.65,
    })


# ============== TestOptimizationAgentInit ==============

class TestOptimizationAgentInit:
    def test_init_stores_config(self):
        """初始化时保存 config_snapshot"""
        from crawler.optimization_agent import OptimizationAgent
        snap = {"engine": "bing", "digest_optimization_target_score": 0.7}
        agent = OptimizationAgent(config_snapshot=snap)
        assert agent._snap is snap
        assert agent._snap["engine"] == "bing"

    def test_init_creates_fatigue_tracker(self):
        """初始化时创建 FatigueTracker"""
        from crawler.optimization_agent import OptimizationAgent
        from optimization.fatigue import FatigueTracker
        agent = OptimizationAgent(config_snapshot={})
        assert isinstance(agent._fatigue, FatigueTracker)

    def test_digest_optimization_budget_keeps_recrawl_time(self, monkeypatch):
        agent = _make_agent()
        from crawler import optimization_agent as opt_mod

        monkeypatch.setattr(opt_mod.settings, "optimization_total_budget_seconds", 120)

        assert agent._optimization_budget_seconds() >= 90


# ============== TestShouldRunOptimization ==============

class TestShouldRunOptimization:
    """测试 DigestOrchestrator._should_run_optimization（OptimizationAgent 的触发条件）"""

    def _setup_orch(self, result_counts: list[int]):
        from crawler.digest_orchestrator import DigestOrchestrator, PlannedSection, DigestCrawlPlan
        orch = DigestOrchestrator()
        sections = [
            PlannedSection(name=f"s{i}", source_type="keyword", result_count=rc)
            for i, rc in enumerate(result_counts)
        ]
        orch._crawl_plan = DigestCrawlPlan(sections=sections)
        return orch

    def test_returns_false_when_results_below_threshold(self):
        """结果不足时不触发优化"""
        snap = {
            "optimization_enabled": True,
            "optimization_mode": "digest",
            "digest_optimization_enabled": True,
            "digest_optimization_min_sections": 2,
            "digest_optimization_min_results_per_section": 5,
        }
        orch = self._setup_orch([2, 1, 0])
        assert orch._should_run_optimization(snap, []) is False

    def test_returns_true_when_results_sufficient(self):
        """结果充足且板块达标时触发优化"""
        snap = {
            "optimization_enabled": True,
            "optimization_mode": "digest",
            "digest_optimization_enabled": True,
            "digest_optimization_min_sections": 2,
            "digest_optimization_min_results_per_section": 3,
        }
        orch = self._setup_orch([5, 4, 2])
        assert orch._should_run_optimization(snap, []) is True

    def test_returns_false_after_global_timeout(self):
        """全局超时后不再进入优化补爬"""
        snap = {
            "optimization_enabled": True,
            "optimization_mode": "digest",
            "digest_optimization_enabled": True,
            "digest_optimization_min_sections": 2,
            "digest_optimization_min_results_per_section": 3,
        }
        orch = self._setup_orch([5, 4, 2])
        orch._global_timeout_reached = True
        assert orch._should_run_optimization(snap, []) is False

    def test_returns_false_when_all_sections_weak(self):
        """所有板块都不达标时不触发"""
        snap = {
            "optimization_enabled": True,
            "optimization_mode": "digest",
            "digest_optimization_enabled": True,
            "digest_optimization_min_sections": 2,
            "digest_optimization_min_results_per_section": 3,
        }
        # 没有任何板块满足 min_results_per_section=3
        orch = self._setup_orch([1, 2, 1])
        assert orch._should_run_optimization(snap, []) is False


# ============== TestMapResultsToSections ==============

class TestMapResultsToSections:
    def test_maps_results_by_keyword_match(self):
        """按关键词匹配结果到板块"""
        agent = _make_agent()
        plan = _make_crawl_plan([_make_section("AI新闻", keywords=["人工智能"])])
        r = _make_result(url="https://x.com/1", search_keyword="人工智能")
        result = agent._map_results_to_sections([r], plan)
        assert len(result["AI新闻"]) == 1

    def test_unmatched_results_go_to_unclassified(self):
        """未匹配结果分配给所有板块"""
        agent = _make_agent()
        plan = _make_crawl_plan([
            _make_section("a", keywords=["Python"]),
            _make_section("b", keywords=["Rust"]),
        ])
        r = _make_result(url="https://unknown.com/1", title="Random", search_keyword="")
        result = agent._map_results_to_sections([r], plan)
        # Unmatched results should not contaminate every section evaluation.
        assert len(result["a"]) == 0
        assert len(result["b"]) == 0

    def test_unmatched_results_are_inferred_to_matching_section(self):
        """Unmatched URLs can still be assigned when category inference is confident."""
        agent = _make_agent()
        plan = _make_crawl_plan([
            _make_section("hot_trend", keywords=["AI news"]),
            _make_section("tech_article", keywords=["engineering"]),
        ])
        r = _make_result(
            url="https://martinfowler.com/articles/architecture/post.html",
            title="Lessons learned from large systems",
            search_keyword="",
        )
        result = agent._map_results_to_sections([r], plan)
        assert len(result["tech_article"]) == 1
        assert len(result["hot_trend"]) == 0


# ============== TestIdentifyWeakSections ==============

class TestIdentifyWeakSections:
    def test_identifies_low_count_sections(self):
        """识别结果数少的弱板块"""
        agent = _make_agent()
        plan = _make_crawl_plan([_make_section("tech", keywords=["AI"])])
        sec_eval = {"tech": _make_eval(overall=0.4, source_diversity=0.2, depth_coverage=0.3)}
        global_eval = _make_eval(overall=0.5)
        weak = agent._identify_weak_sections(sec_eval, global_eval, plan, 0.65)
        assert len(weak) == 1
        assert weak[0].section.name == "tech"
        assert "source_diversity" in weak[0].weakest_dimensions

    def test_returns_empty_when_all_strong(self):
        """所有板块都强时返回空"""
        agent = _make_agent()
        plan = _make_crawl_plan([_make_section("tech")])
        sec_eval = {"tech": _make_eval(overall=0.8)}
        global_eval = _make_eval(overall=0.8)
        weak = agent._identify_weak_sections(sec_eval, global_eval, plan, 0.65)
        assert len(weak) == 0

    def test_identifies_empty_sections_as_weak(self):
        """0 结果板块必须进入优化队列。"""
        agent = _make_agent()
        plan = _make_crawl_plan([_make_section("open_source", keywords=["GitHub trending"])])
        global_eval = _make_eval(overall=0.7)

        weak = agent._identify_weak_sections({}, global_eval, plan, 0.65)

        assert len(weak) == 1
        assert weak[0].section.name == "open_source"
        assert "source_diversity" in weak[0].weakest_dimensions


# ============== TestExecuteLoop ==============

class TestExecuteLoop:
    @pytest.mark.asyncio
    async def test_execute_uses_digest_context_and_refreshes_section_map(self):
        """补爬后必须用新结果重建板块映射，并用 digest 评估上下文。"""
        from optimization.evaluator import CoverageEvaluation
        from crawler.optimization_agent import OptimizationAgent

        agent = OptimizationAgent(config_snapshot={
            "engine": "sogou",
            "digest_optimization_target_score": 0.65,
            "optimization_max_rounds": 1,
        })
        section = _make_section("tech_article", keywords=["AI"], engine="sogou")
        plan = _make_crawl_plan([section])
        initial = _make_result(url="https://a.com/1", search_keyword="AI")
        fresh = _make_result(url="https://b.com/2", search_keyword="AI")
        all_results = [initial]
        seen_urls = {initial.url}
        section_eval_lengths = []
        seen_contexts = []

        async def fake_safe_evaluate(_evaluator, _keyword, results, ctx):
            seen_contexts.append(dict(ctx))
            if results is not all_results:
                section_eval_lengths.append(len(results))
            score = 0.8 if len(results) >= 2 else 0.4
            return CoverageEvaluation(
                overall_score=score,
                source_diversity=score,
                depth_coverage=score,
                angle_coverage=score,
                temporal_coverage=score,
                perspective_balance=score,
                language_coverage=score,
            )

        async def fake_recrawl(*args, **kwargs):
            all_results.append(fresh)
            return 1

        agent._safe_evaluate = AsyncMock(side_effect=fake_safe_evaluate)
        agent._recrawl_section = AsyncMock(side_effect=fake_recrawl)

        kb = MagicMock()
        kb.get_recent_dimension_fatigue = AsyncMock(return_value={})

        with patch("optimization.knowledge_base.KnowledgeBase", return_value=kb), \
             patch("optimization.utils.save_optimization_round", new_callable=AsyncMock) as save_round:
            result = await agent.execute(
                crawl_plan=plan,
                section_documents=[],
                all_results=all_results,
                seen_urls=seen_urls,
                shared_crawler=MagicMock(),
                history_engine=MagicMock(),
                content_dedup=MagicMock(),
                config=MagicMock(),
                task={"id": 123},
            )

        assert result.rounds_completed == 1
        assert result.sections_improved == 1
        assert section_eval_lengths == [1, 2]
        assert any(ctx.get("task_type") == "digest" for ctx in seen_contexts)
        assert any(ctx.get("section_result_counts") == {"tech_article": 1} for ctx in seen_contexts)
        assert any(ctx.get("section_result_counts") == {"tech_article": 2} for ctx in seen_contexts)
        save_round.assert_awaited_once()


# ============== TestRebuildSectionDocuments ==============

class TestRebuildSectionDocuments:
    def test_rebuilds_from_results(self):
        """从结果重建 SectionDocument 列表"""
        agent = _make_agent()
        from crawler.section_document import SectionDocument, SourceEntry
        doc = SectionDocument(section_name="tech", entries=[])
        results = [
            _make_result(url="https://a.com/1", markdown="Content A " * 30),
            _make_result(url="https://b.com/2", markdown="Content B " * 30),
        ]
        agent._rebuild_section_document(doc, results)
        assert doc.cleaned_count == 2
        assert len(doc.entries) == 2
        assert doc.total_word_count > 0
        assert "---" in doc.merged_content
        assert doc.entries[0].source_type == "optimization"

    @pytest.mark.asyncio
    async def test_recrawl_updates_document_with_only_merged_new_results(self):
        """重爬返回重复 URL 时，只把实际合并成功的新结果追加到 SectionDocument。"""
        agent = _make_agent()
        from crawler.optimization_agent import WeakSection
        from crawler.section_document import SectionDocument
        from crawler.utils import normalize_url
        from optimization.strategy import SearchStrategy

        duplicate = _make_result(url="https://dup.com/post", markdown="Duplicate " * 40)
        fresh = _make_result(url="https://fresh.com/post", markdown="Fresh " * 40)
        all_results = [duplicate]
        seen_urls = {normalize_url(duplicate.url)}
        doc = SectionDocument(section_name="tech", entries=[])

        breadth_gen = MagicMock()
        breadth_gen.generate.return_value = SearchStrategy(
            keyword="AI",
            engine="bing",
            time_range="week",
            strategy_type="engine_switch",
            reason="test",
            target_dimension="source_diversity",
        )
        kb = MagicMock()
        kb.get_strategy_hint = AsyncMock(return_value={})
        kb.get_similar_keyword_strategies = AsyncMock(return_value=[])
        content_dedup = MagicMock()
        content_dedup.is_duplicate.return_value = {"is_duplicate": False}
        content_dedup.add = MagicMock()

        with patch("crawler.search.crawl_by_keyword", new_callable=AsyncMock, return_value=[duplicate, fresh]):
            added = await agent._recrawl_section(
                WeakSection(
                    section=_make_section("tech", keywords=["AI"], engine="bing"),
                    evaluation=_make_eval(source_diversity=0.2),
                    weakest_dimensions=["source_diversity"],
                ),
                evaluator=MagicMock(),
                breadth_gen=breadth_gen,
                depth_gen=MagicMock(),
                kb=kb,
                organizer=MagicMock(),
                all_results=all_results,
                seen_urls=seen_urls,
                section_documents=[doc],
                content_dedup=content_dedup,
                ctx={"config": MagicMock(), "crawler": MagicMock()},
                strategy_history=[],
                round_num=1,
                deadline=time.monotonic() + 30,
            )

        assert added == 1
        assert [entry.url for entry in doc.entries] == ["https://fresh.com/post"]

    @pytest.mark.asyncio
    async def test_recrawl_respects_optimization_deadline(self):
        """A section recrawl must not outlive the optimization budget."""
        agent = _make_agent()
        from crawler.optimization_agent import WeakSection
        from optimization.strategy import SearchStrategy

        breadth_gen = MagicMock()
        breadth_gen.generate.return_value = SearchStrategy(
            keyword="AI",
            engine="bing",
            time_range="week",
            strategy_type="engine_switch",
            reason="test",
            target_dimension="depth",
        )
        kb = MagicMock()
        kb.get_strategy_hint = AsyncMock(return_value={})
        kb.get_similar_keyword_strategies = AsyncMock(return_value=[])

        async def slow_crawl(*args, **kwargs):
            await asyncio.sleep(1.0)
            return [_make_result(url="https://late.com/post")]

        started = time.monotonic()
        with patch("crawler.search.crawl_by_keyword", side_effect=slow_crawl):
            added = await agent._recrawl_section(
                WeakSection(
                    section=_make_section("tech", keywords=["AI"], engine="bing"),
                    evaluation=_make_eval(depth_coverage=0.2),
                    weakest_dimensions=["depth"],
                ),
                evaluator=MagicMock(),
                breadth_gen=breadth_gen,
                depth_gen=MagicMock(),
                kb=kb,
                organizer=MagicMock(),
                all_results=[],
                seen_urls=set(),
                section_documents=[],
                content_dedup=MagicMock(),
                ctx={"config": MagicMock(), "crawler": MagicMock()},
                strategy_history=[],
                round_num=1,
                deadline=time.monotonic() + 0.03,
            )

        assert added == 0
        assert time.monotonic() - started < 0.5


# ============== TestFatigueTracker ==============

class TestFatigueTracker:
    def test_not_exhausted_initially(self):
        """初始状态不疲劳"""
        from optimization.fatigue import FatigueTracker
        ft = FatigueTracker()
        assert ft.is_exhausted("source_diversity") is False

    def test_exhausted_after_consecutive_declines(self):
        """连续下降后标记疲劳"""
        from optimization.fatigue import FatigueTracker
        ft = FatigueTracker(window=2)
        ft.record("source_diversity", False)
        ft.record("source_diversity", False)
        assert ft.is_exhausted("source_diversity") is True

    def test_not_exhausted_with_improvement(self):
        """有改善时不标记疲劳"""
        from optimization.fatigue import FatigueTracker
        ft = FatigueTracker(window=2)
        ft.record("source_diversity", False)
        ft.record("source_diversity", True)
        assert ft.is_exhausted("source_diversity") is False
