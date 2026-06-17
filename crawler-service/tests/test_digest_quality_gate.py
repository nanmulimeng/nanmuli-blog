from ai.organizer import DigestContent, DigestItem, DigestSection
from standalone.digest_quality_gate import evaluate_digest_publish_quality


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
