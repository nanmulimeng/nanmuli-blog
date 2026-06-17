from crawler.digest_orchestrator import PlannedSection
from crawler.source_agent import SourceCrawlPlan
from crawler.search_planner import build_search_query_plan, choose_engine


def test_open_source_adds_project_intent_variants():
    section = PlannedSection(
        name="open_source",
        source_type="keyword",
        keywords=["AI developer tools"],
        max_items=4,
        engine="bing",
    )
    plan = SourceCrawlPlan(
        section_name="open_source",
        active_keywords=["AI developer tools"],
        recommended_engine="bing",
        adjusted_max_items=4,
    )

    query_plan = build_search_query_plan(section, plan, config_snapshot={})

    queries = [q.query for q in query_plan.queries]
    assert "AI developer tools github" in queries
    assert "AI developer tools release" in queries
    assert query_plan.max_total_results == 8


def test_paper_adds_academic_domains_without_dropping_original():
    section = PlannedSection(
        name="paper",
        source_type="keyword",
        keywords=["LLM agent benchmark"],
        max_items=3,
        engine="bing",
    )
    plan = SourceCrawlPlan(
        section_name="paper",
        active_keywords=["LLM agent benchmark"],
        recommended_engine="bing",
        adjusted_max_items=3,
    )

    query_plan = build_search_query_plan(section, plan, config_snapshot={})

    queries = [q.query for q in query_plan.queries]
    assert "LLM agent benchmark" in queries
    assert "site:arxiv.org LLM agent benchmark" in queries
    assert "site:openreview.net LLM agent benchmark" in queries


def test_choose_engine_avoids_repeated_zero_result_engine():
    health = {
        "bing": {"total_attempts": 5, "zero_results": 5},
        "sogou": {"total_attempts": 2, "zero_results": 0},
    }

    assert choose_engine(
        "bing",
        keyword="AI coding agent",
        section_name="hot_trend",
        selector_health=health,
    ) == "sogou"


def test_feedback_hints_override_penalized_primary_engine():
    health = {
        "sogou": {"total_attempts": 1, "zero_results": 0},
        "bing": {"total_attempts": 4, "zero_results": 1},
    }

    assert choose_engine(
        "sogou",
        keyword="AI developer tools",
        section_name="open_source",
        selector_health=health,
        feedback_hints={
            "section_engine_preferences": {"open_source": ["bing"]},
            "section_engine_penalties": {"open_source": ["sogou"]},
        },
    ) == "bing"


def test_build_plan_uses_feedback_to_prioritize_engine_and_delay_bad_intents():
    section = PlannedSection(
        name="paper",
        source_type="keyword",
        keywords=["LLM agent benchmark"],
        max_items=3,
        engine="sogou",
    )
    plan = SourceCrawlPlan(
        section_name="paper",
        active_keywords=["LLM agent benchmark"],
        recommended_engine="sogou",
        adjusted_max_items=3,
    )

    query_plan = build_search_query_plan(
        section,
        plan,
        config_snapshot={
            "search_feedback_hints": {
                "section_engine_preferences": {"paper": ["google"]},
                "section_engine_penalties": {"paper": ["sogou"]},
                "section_intent_penalties": {"paper": ["base"]},
            }
        },
    )

    assert {q.engine for q in query_plan.queries} == {"google"}
    assert query_plan.queries[0].intent == "arxiv"
    assert query_plan.queries[-1].intent == "base"
