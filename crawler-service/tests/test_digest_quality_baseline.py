"""Golden quality baseline tests for generated digest output."""

import json
from pathlib import Path

import pytest

from ai.organizer import DigestContent, DigestItem, DigestSection
from crawler.digest_orchestrator import _calculate_digest_output_quality
from standalone.digest_quality_gate import evaluate_digest_publish_quality

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "digest_quality"


def _load_digest(name: str) -> DigestContent:
    payload = json.loads((FIXTURE_DIR / f"{name}.json").read_text(encoding="utf-8"))
    return DigestContent(
        title=payload["title"],
        summary=payload["summary"],
        highlight=payload.get("highlight", ""),
        tags=payload.get("tags", []),
        full_content=payload["full_content"],
        sections=[
            DigestSection(
                category=section["category"],
                category_name=section["category"],
                items=[
                    DigestItem(
                        title=item["title"],
                        one_liner=item["one_liner"],
                        source_url=item["source_url"],
                        source_name=item["source_name"],
                    )
                    for item in section["items"]
                ],
            )
            for section in payload["sections"]
        ],
    )


@pytest.fixture(autouse=True)
def _core_section_gate(monkeypatch):
    monkeypatch.setattr(
        "standalone.digest_quality_gate.settings.digest_publish_core_sections",
        "hot_trend,open_source,dev_tool,tech_article,paper",
        raising=False,
    )
    monkeypatch.setattr(
        "standalone.digest_quality_gate.settings.digest_publish_min_core_sections",
        3,
        raising=False,
    )
    monkeypatch.setattr(
        "standalone.digest_quality_gate.settings.digest_optimization_target_score",
        0.65,
        raising=False,
    )


def test_good_digest_baseline_is_publishable():
    digest = _load_digest("good_digest")

    quality, publishable = evaluate_digest_publish_quality(digest)

    assert publishable is True
    assert quality["score"] >= 0.65
    assert quality["core_section_count"] >= 3
    assert quality["duplicate_event_count"] == 0
    assert quality["generic_source_count"] == 0


def test_duplicate_events_baseline_keeps_event_duplication_diagnostic():
    digest = _load_digest("duplicate_events")

    quality = _calculate_digest_output_quality(digest)

    assert quality["duplicate_event_count"] >= 1
    assert any("duplicate events" in suggestion for suggestion in quality["suggestions"])
    assert quality["score"] < _calculate_digest_output_quality(_load_digest("good_digest"))["score"]


def test_core_section_missing_baseline_is_rejected_by_publish_gate():
    digest = _load_digest("core_section_missing")

    quality, publishable = evaluate_digest_publish_quality(digest)

    assert publishable is False
    assert "core_section_coverage" in quality["gate_failures"]
    assert quality["core_section_count"] == 1
    assert "open_source" in quality["missing_core_sections"]


def test_generic_listing_pollution_baseline_records_generic_source_diagnostic():
    digest = _load_digest("generic_listing_pollution")

    quality = _calculate_digest_output_quality(digest)

    assert quality["generic_source_count"] >= 1
    assert any("sourceUrl" in suggestion for suggestion in quality["suggestions"])
    assert quality["score"] < _calculate_digest_output_quality(_load_digest("good_digest"))["score"]


def test_low_relevance_baseline_records_low_relevance_diagnostic():
    digest = _load_digest("low_relevance_items")

    quality = _calculate_digest_output_quality(digest)

    assert quality["low_relevance_item_count"] >= 3
    assert any("relevance is weak" in suggestion for suggestion in quality["suggestions"])
    assert quality["score"] < 0.75
