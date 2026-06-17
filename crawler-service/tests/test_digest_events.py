"""Tests for pre-generation digest event merging."""

from ai.organizer import DigestPageContent

from crawler.digest_events import (
    build_digest_event_candidates,
    merge_digest_event_pages,
)


def _page(
    *,
    url: str,
    title: str,
    markdown: str,
    category: str = "hot_trend",
    source_level: str = "medium",
    source_name: str = "",
) -> DigestPageContent:
    return DigestPageContent(
        url=url,
        title=title,
        markdown=markdown,
        summary=markdown[:160],
        category=category,
        source_name=source_name or url.split("/")[2],
        source_level=source_level,
    )


def test_same_openai_responses_api_event_merges_multi_source_pages():
    pages = [
        _page(
            url="https://openai.com/index/introducing-responses-api/",
            title="OpenAI introduces the Responses API",
            markdown="OpenAI introduces the Responses API for agents and tool use. " * 8,
            source_level="official",
            source_name="OpenAI",
        ),
        _page(
            url="https://github.blog/changelog/2026-06-17-responses-api-support/",
            title="GitHub adds Responses API support for coding agents",
            markdown="GitHub adds Responses API support after OpenAI introduces Responses API. " * 8,
            source_level="high",
            source_name="GitHub Blog",
        ),
    ]

    candidates = build_digest_event_candidates(pages)

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.primary_source.url == "https://openai.com/index/introducing-responses-api/"
    assert candidate.item_count == 2
    assert candidate.source_diversity == 2
    assert candidate.source_domains == ["openai.com", "github.blog"]


def test_distinct_events_in_same_category_do_not_merge():
    pages = [
        _page(
            url="https://postgresql.org/about/news/planner-update",
            title="PostgreSQL planner improves join estimates",
            markdown="PostgreSQL planner improves join estimates for analytical workloads. " * 8,
        ),
        _page(
            url="https://kubernetes.io/blog/scheduler-queueing",
            title="Kubernetes scheduler updates queueing behavior",
            markdown="Kubernetes scheduler updates queueing behavior for cluster workloads. " * 8,
        ),
        _page(
            url="https://openai.com/index/responses-api/",
            title="OpenAI Responses API adds tracing",
            markdown="OpenAI Responses API adds tracing for agent developers. " * 8,
        ),
    ]

    candidates = build_digest_event_candidates(pages)

    assert len(candidates) == 3
    assert {candidate.item_count for candidate in candidates} == {1}


def test_primary_source_prefers_authority_then_content_length_then_url():
    official_short = _page(
        url="https://official.example.com/short",
        title="Project Merlin release",
        markdown="Project Merlin release.",
        source_level="official",
    )
    medium_long = _page(
        url="https://medium.example.com/long",
        title="Project Merlin release analysis",
        markdown="Project Merlin release analysis with much more detail. " * 20,
        source_level="medium",
    )
    candidates = build_digest_event_candidates([medium_long, official_short])
    assert candidates[0].primary_source.url == official_short.url

    high_long = _page(
        url="https://b.example.com/event",
        title="Project Atlas launch",
        markdown="Project Atlas launch details. " * 20,
        source_level="high",
    )
    high_short = _page(
        url="https://a.example.com/event",
        title="Project Atlas launch",
        markdown="Project Atlas launch.",
        source_level="high",
    )
    candidates = build_digest_event_candidates([high_short, high_long])
    assert candidates[0].primary_source.url == high_long.url


def test_merged_page_markdown_includes_structured_source_evidence():
    pages = [
        _page(
            url="https://openai.com/index/responses-api/",
            title="OpenAI Responses API reaches GA",
            markdown="OpenAI Responses API reaches GA for agents and tools. " * 8,
            source_level="official",
        ),
        _page(
            url="https://github.blog/changelog/responses-api-ga/",
            title="GitHub adds Responses API GA integration",
            markdown="GitHub adds Responses API GA integration for agent workflows. " * 8,
            source_level="high",
        ),
    ]

    merged_pages, diagnostics = merge_digest_event_pages(pages)

    assert len(merged_pages) == 1
    assert "## Multi-source evidence" in merged_pages[0].markdown
    assert "Primary source: https://openai.com/index/responses-api/" in merged_pages[0].markdown
    assert "Related sources:" in merged_pages[0].markdown
    assert "github.blog" in merged_pages[0].markdown
    assert diagnostics["event_count"] == 1
    assert diagnostics["merged_event_count"] == 1
    assert diagnostics["duplicate_input_count"] == 1
    assert diagnostics["multi_source_event_count"] == 1
    assert diagnostics["max_sources_per_event"] == 2
    assert diagnostics["source_diversity"] == 1.0
    assert diagnostics["sample_events"][0]["source_domains"] == ["openai.com", "github.blog"]


def test_event_merge_is_category_scoped():
    pages = [
        _page(
            url="https://openai.com/index/responses-api/",
            title="OpenAI Responses API update",
            markdown="OpenAI Responses API update for agents and tools. " * 8,
            category="hot_trend",
            source_level="official",
        ),
        _page(
            url="https://github.com/openai/openai-python/releases/tag/v2",
            title="OpenAI Responses API SDK update",
            markdown="OpenAI Responses API SDK update for Python developers. " * 8,
            category="dev_tool",
            source_level="high",
        ),
    ]

    merged_pages, diagnostics = merge_digest_event_pages(pages)

    assert len(merged_pages) == 2
    assert diagnostics["merged_event_count"] == 0
