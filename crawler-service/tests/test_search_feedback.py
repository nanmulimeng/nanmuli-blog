import json

from crawler.search_feedback import (
    build_search_feedback_snapshot,
    derive_search_feedback_hints,
    summarize_search_diagnostics,
)


def test_summarize_search_diagnostics_groups_by_section_and_engine():
    diagnostics = [
        {
            "section": "hot_trend",
            "query": "AI coding agent",
            "engine": "bing",
            "requested": 5,
            "returned": 6,
            "kept": 3,
            "filtered": 2,
            "top_domains": ["github.blog", "openai.com"],
        },
        {
            "section": "hot_trend",
            "query": "AI coding agent analysis",
            "engine": "sogou",
            "requested": 5,
            "returned": 0,
            "kept": 0,
            "filtered": 0,
            "top_domains": [],
        },
        {
            "section": "paper",
            "query": "site:arxiv.org agent memory",
            "engine": "bing",
            "requested": 4,
            "returned": 4,
            "kept": 2,
            "filtered": 1,
            "top_domains": ["arxiv.org"],
        },
    ]

    summary = summarize_search_diagnostics(diagnostics)

    assert summary["total_queries"] == 3
    assert summary["total_returned"] == 10
    assert summary["total_kept"] == 5
    assert summary["keep_rate"] == 0.5
    assert summary["zero_result_queries"][0]["query"] == "AI coding agent analysis"

    sections = {item["section"]: item for item in summary["section_summaries"]}
    assert sections["hot_trend"]["queries"] == 2
    assert sections["hot_trend"]["keep_rate"] == 0.5
    assert sections["hot_trend"]["top_domains"] == ["github.blog", "openai.com"]
    assert sections["paper"]["keep_rate"] == 0.5

    engines = {item["engine"]: item for item in summary["engine_summaries"]}
    assert engines["bing"]["queries"] == 2
    assert engines["bing"]["kept"] == 5
    assert engines["sogou"]["zero_result_queries"] == 1


def test_build_search_feedback_snapshot_parses_task_metadata():
    task = {
        "id": 42,
        "digest_date": "2026-06-17",
        "status": 4,
        "created_at": "2026-06-17 08:00:00",
        "ai_search_metadata": json.dumps({
            "orchestrator_plan": {
                "plan_log": ["Search diagnostic: hot_trend bing kept 3/6"],
                "search_diagnostics": [
                    {
                        "section": "hot_trend",
                        "query": "AI coding agent",
                        "engine": "bing",
                        "returned": 6,
                        "kept": 3,
                    }
                ],
            }
        }),
    }

    snapshot = build_search_feedback_snapshot(task)

    assert snapshot["task_id"] == 42
    assert snapshot["digest_date"] == "2026-06-17"
    assert snapshot["diagnostics"][0]["query"] == "AI coding agent"
    assert snapshot["summary"]["total_queries"] == 1
    assert snapshot["summary"]["total_kept"] == 3


def test_derive_search_feedback_hints_prefers_productive_section_engines_and_domains():
    snapshots = [
        {
            "diagnostics": [
                {
                    "section": "open_source",
                    "query": "AI developer tools github",
                    "engine": "bing",
                    "intent": "project",
                    "returned": 8,
                    "kept": 5,
                    "top_domains": ["github.com", "github.com"],
                },
                {
                    "section": "open_source",
                    "query": "AI developer tools",
                    "engine": "sogou",
                    "intent": "base",
                    "returned": 0,
                    "kept": 0,
                    "top_domains": [],
                },
                {
                    "section": "paper",
                    "query": "site:arxiv.org agent memory",
                    "engine": "google",
                    "intent": "arxiv",
                    "returned": 6,
                    "kept": 4,
                    "top_domains": ["arxiv.org"],
                },
                {
                    "section": "paper",
                    "query": "agent memory",
                    "engine": "sogou",
                    "intent": "base",
                    "returned": 3,
                    "kept": 0,
                    "top_domains": [],
                },
            ]
        }
    ]

    hints = derive_search_feedback_hints(snapshots)

    assert hints["section_engine_preferences"]["open_source"] == ["bing"]
    assert "sogou" in hints["section_engine_penalties"]["open_source"]
    assert hints["section_engine_preferences"]["paper"] == ["google"]
    assert "base" in hints["section_intent_penalties"]["paper"]
    assert hints["section_domain_preferences"]["paper"] == ["arxiv.org"]
