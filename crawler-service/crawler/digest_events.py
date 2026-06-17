"""Pre-generation event candidate merging for digest pages."""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlparse

from ai.organizer import DigestPageContent
from crawler.dedup import group_event_candidates

_SOURCE_LEVEL_ORDER = {"official": 0, "high": 1, "medium": 2, "low": 3, "spam": 4}


@dataclass(frozen=True)
class DigestEventSource:
    url: str
    title: str
    source_name: str
    source_level: str
    source_domain: str
    markdown_length: int


@dataclass
class DigestEventCandidate:
    category: str
    event_group_key: str
    primary_page: DigestPageContent
    supporting_pages: list[DigestPageContent] = field(default_factory=list)
    source_urls: list[str] = field(default_factory=list)
    source_domains: list[str] = field(default_factory=list)

    @property
    def primary_source(self) -> DigestEventSource:
        return _source_from_page(self.primary_page)

    @property
    def item_count(self) -> int:
        return 1 + len(self.supporting_pages)

    @property
    def source_diversity(self) -> int:
        return len(self.source_domains)


def build_digest_event_candidates(pages: list[DigestPageContent]) -> list[DigestEventCandidate]:
    """Build conservative same-event candidates within each digest category."""
    by_category: dict[str, list[DigestPageContent]] = {}
    for page in pages:
        category = (getattr(page, "category", "") or "__uncategorized__").strip() or "__uncategorized__"
        by_category.setdefault(category, []).append(page)

    candidates: list[DigestEventCandidate] = []
    for category, category_pages in by_category.items():
        groups = group_event_candidates(category_pages, section_name=category)
        for group in groups:
            items = list(group.get("items") or [])
            if not items:
                continue
            group_domains = _unique(_source_domain(getattr(page, "url", "") or "") for page in items)
            if len(group_domains) < 2:
                for page in items:
                    url = getattr(page, "url", "") or ""
                    domain = _source_domain(url)
                    candidates.append(DigestEventCandidate(
                        category=category,
                        event_group_key=str(group.get("event_group_key") or domain or url),
                        primary_page=page,
                        supporting_pages=[],
                        source_urls=[url] if url else [],
                        source_domains=[domain] if domain else [],
                    ))
                continue
            primary = _select_primary_page(items)
            supporting = [page for page in items if page is not primary]
            source_urls = _unique(
                [getattr(primary, "url", "") or ""]
                + [getattr(page, "url", "") or "" for page in supporting]
            )
            source_domains = _unique(_source_domain(url) for url in source_urls)
            candidates.append(DigestEventCandidate(
                category=category,
                event_group_key=str(group.get("event_group_key") or _source_domain(getattr(primary, "url", ""))),
                primary_page=primary,
                supporting_pages=supporting,
                source_urls=source_urls,
                source_domains=source_domains,
            ))
    return candidates


def merge_digest_event_pages(pages: list[DigestPageContent]) -> tuple[list[DigestPageContent], dict]:
    """Merge same-event digest pages before AI generation.

    The merge is conservative: single-source candidates are returned unchanged,
    while multi-source candidates keep the best primary page and append a
    structured evidence block for the organizer prompt.
    """
    candidates = build_digest_event_candidates(pages)
    merged_pages: list[DigestPageContent] = []
    for candidate in candidates:
        if candidate.item_count <= 1:
            merged_pages.append(candidate.primary_page)
            continue
        merged_pages.append(_build_merged_page(candidate))
    return merged_pages, _build_event_diagnostics(candidates, len(pages))


def _select_primary_page(pages: list[DigestPageContent]) -> DigestPageContent:
    return sorted(
        pages,
        key=lambda page: (
            _SOURCE_LEVEL_ORDER.get((getattr(page, "source_level", "") or "medium").lower(), 3),
            -len(getattr(page, "markdown", "") or ""),
            getattr(page, "url", "") or "",
        ),
    )[0]


def _source_from_page(page: DigestPageContent) -> DigestEventSource:
    url = getattr(page, "url", "") or ""
    return DigestEventSource(
        url=url,
        title=getattr(page, "title", "") or "",
        source_name=getattr(page, "source_name", "") or _source_domain(url),
        source_level=getattr(page, "source_level", "") or "medium",
        source_domain=_source_domain(url),
        markdown_length=len(getattr(page, "markdown", "") or ""),
    )


def _build_merged_page(candidate: DigestEventCandidate) -> DigestPageContent:
    primary = candidate.primary_page
    evidence = _build_evidence_block(candidate)
    summary = getattr(primary, "summary", "") or ""
    if candidate.item_count > 1:
        summary = f"{summary}\nMulti-source event with {candidate.item_count} sources.".strip()
    return DigestPageContent(
        url=getattr(primary, "url", "") or "",
        title=getattr(primary, "title", "") or "",
        markdown=f"{getattr(primary, 'markdown', '') or ''}\n\n{evidence}".strip(),
        summary=summary,
        category=getattr(primary, "category", "") or candidate.category,
        source_name=getattr(primary, "source_name", "") or "",
        source_level=getattr(primary, "source_level", "") or "",
        page_id=getattr(primary, "page_id", None),
    )


def _build_evidence_block(candidate: DigestEventCandidate) -> str:
    lines = [
        "## Multi-source evidence",
        f"Event group key: {candidate.event_group_key}",
        f"Primary source: {getattr(candidate.primary_page, 'url', '') or ''}",
        "Related sources:",
    ]
    for page in candidate.supporting_pages:
        url = getattr(page, "url", "") or ""
        title = getattr(page, "title", "") or url
        domain = _source_domain(url)
        lines.append(f"- {title} ({domain}): {url}")
    return "\n".join(lines)


def _build_event_diagnostics(candidates: list[DigestEventCandidate], input_count: int) -> dict:
    if not candidates:
        return {
            "event_count": 0,
            "merged_event_count": 0,
            "duplicate_input_count": 0,
            "multi_source_event_count": 0,
            "max_sources_per_event": 0,
            "source_diversity": 0.0,
            "sample_events": [],
        }
    merged_event_count = sum(1 for candidate in candidates if candidate.item_count > 1)
    max_sources = max(candidate.item_count for candidate in candidates)
    domains = {
        domain
        for candidate in candidates
        for domain in candidate.source_domains
        if domain
    }
    return {
        "event_count": len(candidates),
        "merged_event_count": merged_event_count,
        "duplicate_input_count": max(0, input_count - len(candidates)),
        "multi_source_event_count": sum(1 for candidate in candidates if len(candidate.source_domains) >= 2),
        "max_sources_per_event": max_sources,
        "source_diversity": round(len(domains) / input_count, 4) if input_count else 0.0,
        "sample_events": [
            {
                "event_group_key": candidate.event_group_key,
                "category": candidate.category,
                "primary_url": getattr(candidate.primary_page, "url", "") or "",
                "source_urls": candidate.source_urls,
                "source_domains": candidate.source_domains,
                "item_count": candidate.item_count,
            }
            for candidate in candidates[:5]
        ],
    }


def _source_domain(url: str) -> str:
    if not url:
        return ""
    try:
        return urlparse(url).netloc.lower().removeprefix("www.")
    except Exception:
        return ""


def _unique(values) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
