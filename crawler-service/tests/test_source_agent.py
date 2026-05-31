"""SourceAgent 单元测试 — 覆盖死源过滤、效能自适应、关键词 fallback、弱点反馈"""

import pytest
from unittest.mock import MagicMock, patch

from crawler.source_agent import SourceAgent, SourceCrawlPlan
from crawler.digest_orchestrator import PlannedSection


def _make_section(
    name: str = "test_section",
    source_type: str = "keyword",
    keywords: list[str] | None = None,
    keyword_details: list[dict] | None = None,
    url_sources: list[dict] | None = None,
    rss_sources: list[dict] | None = None,
    max_items: int = 5,
    engine: str = "sogou",
    effectiveness: dict | None = None,
) -> PlannedSection:
    return PlannedSection(
        name=name,
        source_type=source_type,
        keywords=keywords or [],
        keyword_details=keyword_details or [],
        url_sources=url_sources or [],
        rss_sources=rss_sources or [],
        max_items=max_items,
        engine=engine,
        effectiveness=effectiveness or {},
    )


def _make_config():
    return MagicMock()


# ============== TestSourceCrawlPlan ==============

class TestSourceCrawlPlan:
    def test_defaults(self):
        plan = SourceCrawlPlan(section_name="s")
        assert plan.section_name == "s"
        assert plan.active_keywords == []
        assert plan.active_url_sources == []
        assert plan.active_rss_sources == []
        assert plan.skipped_source_ids == set()
        assert plan.recommended_engine == ""
        assert plan.adjusted_max_items == 5
        assert plan.analysis_log == []

    def test_custom_values(self):
        plan = SourceCrawlPlan(
            section_name="s",
            active_keywords=["AI"],
            active_url_sources=[{"url": "https://x.com"}],
            skipped_source_ids={42},
            recommended_engine="bing",
            adjusted_max_items=10,
        )
        assert plan.active_keywords == ["AI"]
        assert len(plan.active_url_sources) == 1
        assert 42 in plan.skipped_source_ids
        assert plan.recommended_engine == "bing"


# ============== TestDeadSourceFilter ==============

class TestDeadSourceFilter:
    """死源过滤：URL/RSS/Keyword 各场景"""

    @patch("crawler.source_analysis.is_truly_dead", return_value=True)
    def test_dead_url_source_skipped(self, _mock):
        sec = _make_section(
            source_type="url",
            url_sources=[{"url": "https://dead.com", "source_id": 1, "effectiveness": {"dead": True}}],
        )
        agent = SourceAgent(sec, _make_config(), {})
        plan = agent.analyze()
        assert len(plan.active_url_sources) == 0
        assert 1 in plan.skipped_source_ids

    @patch("crawler.source_analysis.is_truly_dead", return_value=True)
    def test_dead_rss_source_skipped(self, _mock):
        sec = _make_section(
            source_type="rss",
            rss_sources=[{"feed_url": "https://dead.com/feed", "source_id": 2, "effectiveness": {"dead": True}}],
        )
        agent = SourceAgent(sec, _make_config(), {})
        plan = agent.analyze()
        assert len(plan.active_rss_sources) == 0
        assert 2 in plan.skipped_source_ids

    @patch("crawler.source_analysis.is_truly_dead", return_value=True)
    def test_dead_keyword_skipped(self, _mock):
        sec = _make_section(
            source_type="keyword",
            keyword_details=[{"value": "dead_kw", "source_id": 3, "effectiveness": {"dead": True}}],
        )
        agent = SourceAgent(sec, _make_config(), {})
        plan = agent.analyze()
        assert "dead_kw" not in plan.active_keywords
        assert 3 in plan.skipped_source_ids

    @patch("crawler.source_analysis.is_truly_dead", return_value=False)
    def test_healthy_source_kept(self, _mock):
        sec = _make_section(
            source_type="keyword",
            keyword_details=[{"value": "AI", "source_id": 4, "effectiveness": {}}],
        )
        agent = SourceAgent(sec, _make_config(), {})
        plan = agent.analyze()
        assert "AI" in plan.active_keywords
        assert 4 not in plan.skipped_source_ids

    @patch("crawler.source_analysis.is_truly_dead")
    def test_mixed_sources_partial_skip(self, mock_dead):
        """混合场景：部分死、部分活"""
        mock_dead.side_effect = lambda eff: eff.get("dead", False)
        sec = _make_section(
            source_type="mixed",
            keyword_details=[
                {"value": "alive_kw", "source_id": 10, "effectiveness": {}},
                {"value": "dead_kw", "source_id": 11, "effectiveness": {"dead": True}},
            ],
            url_sources=[
                {"url": "https://alive.com", "source_id": 12, "effectiveness": {}},
                {"url": "https://dead.com", "source_id": 13, "effectiveness": {"dead": True}},
            ],
        )
        agent = SourceAgent(sec, _make_config(), {})
        plan = agent.analyze()
        assert "alive_kw" in plan.active_keywords
        assert "dead_kw" not in plan.active_keywords
        assert len(plan.active_url_sources) == 1
        assert {11, 13}.issubset(plan.skipped_source_ids)


# ============== TestEfficiencyAdaptation ==============

class TestEfficiencyAdaptation:
    """板块效能自适应：低 success_rate 缩减 + 切换引擎，高 success_rate 增加"""

    @patch("crawler.source_analysis.is_truly_dead", return_value=False)
    def test_low_success_rate_reduces_max_items(self, _mock):
        sec = _make_section(
            max_items=10,
            effectiveness={"total_runs": 5, "success_rate": 0.3},
            keyword_details=[{"value": "AI", "effectiveness": {}}],
        )
        agent = SourceAgent(sec, _make_config(), {})
        plan = agent.analyze()
        assert plan.adjusted_max_items < 10

    @patch("crawler.source_analysis.is_truly_dead", return_value=False)
    def test_low_success_rate_switches_engine(self, _mock):
        sec = _make_section(
            max_items=5, engine="baidu",
            effectiveness={"total_runs": 5, "success_rate": 0.3},
            keyword_details=[{"value": "AI", "effectiveness": {}}],
        )
        kb_hint = {"recommended_engine": "bing"}
        agent = SourceAgent(sec, _make_config(), {})
        plan = agent.analyze(kb_hint=kb_hint)
        assert plan.recommended_engine == "bing"
        assert any("Low success rate" in log for log in plan.analysis_log)

    @patch("crawler.source_analysis.is_truly_dead", return_value=False)
    def test_high_success_rate_increases_max_items(self, _mock):
        sec = _make_section(
            max_items=5,
            effectiveness={"total_runs": 10, "success_rate": 0.8},
            keyword_details=[{"value": "AI", "effectiveness": {}}],
        )
        agent = SourceAgent(sec, _make_config(), {})
        plan = agent.analyze()
        assert plan.adjusted_max_items > 5

    @patch("crawler.source_analysis.is_truly_dead", return_value=False)
    def test_no_history_no_adjustment(self, _mock):
        """无历史数据不调整"""
        sec = _make_section(
            max_items=5,
            effectiveness={"total_runs": 0, "success_rate": 0},
            keyword_details=[{"value": "AI", "effectiveness": {}}],
        )
        agent = SourceAgent(sec, _make_config(), {})
        plan = agent.analyze()
        assert plan.adjusted_max_items == 5


# ============== TestKeywordFallback ==============

class TestKeywordFallback:
    """keyword_details 为空时 fallback 到 section.keywords"""

    @patch("crawler.source_analysis.is_truly_dead", return_value=False)
    def test_fallback_to_section_keywords(self, _mock):
        sec = _make_section(
            keywords=["Python", "Rust"],
            keyword_details=[],
        )
        agent = SourceAgent(sec, _make_config(), {})
        plan = agent.analyze()
        assert plan.active_keywords == ["Python", "Rust"]

    @patch("crawler.source_analysis.is_truly_dead", return_value=False)
    def test_keyword_details_take_priority(self, _mock):
        sec = _make_section(
            keywords=["Python", "Rust"],
            keyword_details=[{"value": "Go", "effectiveness": {}}],
        )
        agent = SourceAgent(sec, _make_config(), {})
        plan = agent.analyze()
        assert "Go" in plan.active_keywords
        assert "Python" not in plan.active_keywords


# ============== TestWeaknessFeedback ==============

class TestWeaknessFeedback:
    """能力 6: 基于上次评估弱点调整参数"""

    @patch("crawler.source_analysis.is_truly_dead", return_value=False)
    def test_source_diversity_weakness_boosts_max_items(self, _mock):
        sec = _make_section(
            max_items=5,
            keyword_details=[{"value": "AI", "effectiveness": {}}],
        )
        kb_hint = {"last_weaknesses": ["source_diversity"]}
        agent = SourceAgent(sec, _make_config(), {})
        plan = agent.analyze(kb_hint=kb_hint)
        assert plan.adjusted_max_items > 5
        assert any("source_diversity" in log for log in plan.analysis_log)

    @patch("crawler.source_analysis.is_truly_dead", return_value=False)
    def test_language_weakness_logged(self, _mock):
        sec = _make_section(
            max_items=5,
            keyword_details=[{"value": "AI", "effectiveness": {}}],
        )
        kb_hint = {"last_weaknesses": ["language"]}
        agent = SourceAgent(sec, _make_config(), {})
        plan = agent.analyze(kb_hint=kb_hint)
        assert any("language" in log.lower() for log in plan.analysis_log)

    @patch("crawler.source_analysis.is_truly_dead", return_value=False)
    def test_formatted_source_diversity_weakness_boosts_max_items(self, _mock):
        sec = _make_section(
            max_items=5,
            keyword_details=[{"value": "AI", "effectiveness": {}}],
        )
        kb_hint = {"last_weaknesses": ["source_diversity=0.31 偏低"]}
        agent = SourceAgent(sec, _make_config(), {})
        plan = agent.analyze(kb_hint=kb_hint)
        assert plan.adjusted_max_items > 5
