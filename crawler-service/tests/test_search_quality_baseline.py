import json
from pathlib import Path

from crawler.filters import is_excluded_domain
from crawler.search import normalize_search_result


def test_normalize_search_result_preserves_engine_keyword_rank():
    item = normalize_search_result(
        {
            "title": "GitHub Copilot coding agent",
            "url": "https://github.blog/changelog/x",
            "snippet": "New coding agent.",
        },
        keyword="github copilot coding agent",
        engine="bing",
        rank=2,
    )

    assert item["title"] == "GitHub Copilot coding agent"
    assert item["url"] == "https://github.blog/changelog/x"
    assert item["snippet"] == "New coding agent."
    assert item["metadata"]["search_keyword"] == "github copilot coding agent"
    assert item["metadata"]["search_engine"] == "bing"
    assert item["metadata"]["search_rank"] == 2


def test_fixture_low_value_domains_are_rejected():
    cases = json.loads(
        Path("crawler-service/tests/fixtures/search_quality_cases.json")
        .read_text(encoding="utf-8")
    )
    rejected = [case for case in cases if not case["expected_keep"]]

    assert rejected
    for case in rejected:
        assert is_excluded_domain(case["raw"]["url"])
