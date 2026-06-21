import pytest

from ai.organizer import DigestContent, DigestItem, DigestSection
from standalone.digest_quality_gate import (
    evaluate_digest_publish_quality,
    save_digest_publish_quality,
)


def _section(category: str, count: int) -> DigestSection:
    return DigestSection(
        category=category,
        category_name=category,
        items=[
            DigestItem(
                title=f"{category} item {idx}",
                one_liner="This item explains concrete AI developer impact and next action.",
                source_url=f"https://example.com/{category}/{idx}",
                source_name="example.com",
            )
            for idx in range(count)
        ],
    )


def test_publish_gate_rejects_high_score_digest_with_too_few_core_sections(monkeypatch):
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

    digest = DigestContent(
        title="AI Daily",
        summary="A generated AI daily digest.",
        full_content="# AI Daily\n\nUseful structured digest.",
        sections=[_section("hot_trend", 8)],
    )

    quality, publishable = evaluate_digest_publish_quality(digest)

    assert quality["score"] >= 0.65
    assert publishable is False
    assert quality["core_section_count"] == 1
    assert quality["missing_core_sections"] == [
        "open_source",
        "dev_tool",
        "tech_article",
        "paper",
    ]
    assert "core_section_coverage" in quality["gate_failures"]


def test_publish_gate_allows_digest_with_enough_core_sections(monkeypatch):
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

    digest = DigestContent(
        title="AI Daily",
        summary="A generated AI daily digest.",
        full_content="# AI Daily\n\nUseful structured digest.",
        sections=[
            _section("hot_trend", 3),
            _section("open_source", 3),
            _section("paper", 2),
        ],
    )

    quality, publishable = evaluate_digest_publish_quality(digest)

    assert publishable is True
    assert quality["core_section_count"] == 3
    assert quality["gate_failures"] == []


@pytest.mark.asyncio
async def test_save_digest_publish_quality_merges_existing_metadata():
    class FakeRepository:
        def __init__(self):
            self.metadata = {
                "orchestrator_plan": {
                    "event_diagnostics": {
                        "event_count": 3,
                        "merged_event_count": 1,
                    }
                }
            }
            self.overwrite_called = False

        async def update_task_metadata(self, task_id, metadata):
            assert task_id == 42
            self.metadata.update(metadata)

        async def save_ai_search_metadata(self, task_id, metadata):
            self.overwrite_called = True
            self.metadata = metadata

    repository = FakeRepository()

    await save_digest_publish_quality(
        repository,
        42,
        {"score": 0.92, "gate_failures": []},
        True,
        "fallback",
    )

    assert repository.overwrite_called is False
    assert repository.metadata["digest_publishable"] is True
    assert repository.metadata["digest_publish_stage"] == "fallback"
    assert repository.metadata["digest_publish_quality"]["score"] == 0.92
    assert repository.metadata["orchestrator_plan"]["event_diagnostics"]["merged_event_count"] == 1
