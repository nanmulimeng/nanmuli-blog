"""Section-aware query planning for digest search."""

from dataclasses import dataclass

from config import settings
from crawler.digest_orchestrator import PlannedSection
from crawler.source_agent import SourceCrawlPlan

ENGINE_FALLBACKS = {
    "bing": ["sogou", "baidu", "google"],
    "sogou": ["bing", "baidu", "google"],
    "baidu": ["bing", "sogou", "google"],
    "google": ["bing", "sogou", "baidu"],
}


@dataclass(frozen=True)
class SearchQueryVariant:
    query: str
    engine: str
    max_results: int
    time_range: str
    intent: str


@dataclass(frozen=True)
class SearchQueryPlan:
    section_name: str
    queries: list[SearchQueryVariant]
    max_total_results: int


def _section_variants(section_name: str, keyword: str) -> list[tuple[str, str]]:
    base = keyword.strip()
    if not base:
        return []
    if section_name == "open_source":
        return [(base, "base"), (f"{base} github", "project"), (f"{base} release", "release")]
    if section_name == "paper":
        return [(base, "base"), (f"site:arxiv.org {base}", "arxiv"), (f"site:openreview.net {base}", "openreview")]
    if section_name == "dev_tool":
        return [(base, "base"), (f"{base} changelog", "release"), (f"{base} docs", "docs")]
    return [(base, "base"), (f"{base} analysis", "analysis")]


def _zero_result_ratio(engine: str, selector_health: dict) -> float:
    health = selector_health.get(engine) or {}
    attempts = int(health.get("total_attempts") or 0)
    if attempts <= 0:
        return 0.0
    zero_results = int(health.get("zero_results") or 0)
    return zero_results / attempts


def choose_engine(
    primary: str,
    *,
    keyword: str,
    section_name: str,
    selector_health: dict,
) -> str:
    primary = primary or "bing"
    primary_health = selector_health.get(primary) or {}
    attempts = int(primary_health.get("total_attempts") or 0)
    if attempts < 3 or _zero_result_ratio(primary, selector_health) < 0.8:
        return primary

    for candidate in ENGINE_FALLBACKS.get(primary, ["bing", "sogou", "baidu", "google"]):
        if candidate == primary:
            continue
        candidate_health = selector_health.get(candidate) or {}
        candidate_attempts = int(candidate_health.get("total_attempts") or 0)
        if candidate_attempts == 0 or _zero_result_ratio(candidate, selector_health) < 0.5:
            return candidate
    return primary


def build_search_query_plan(
    section: PlannedSection,
    crawl_plan: SourceCrawlPlan,
    *,
    config_snapshot: dict,
) -> SearchQueryPlan:
    from crawler.search import get_selector_health

    seen: set[str] = set()
    variants: list[SearchQueryVariant] = []
    selector_health = get_selector_health()
    total_budget = (
        max(crawl_plan.adjusted_max_items, section.max_items)
        * settings.digest_section_result_multiplier
    )
    keywords = crawl_plan.active_keywords or section.keywords
    per_query = max(2, min(8, total_budget // max(1, len(keywords) * 2)))
    for keyword in keywords:
        for query, intent in _section_variants(section.name, keyword):
            key = query.lower()
            if key in seen:
                continue
            seen.add(key)
            variants.append(SearchQueryVariant(
                query=query,
                engine=choose_engine(
                    crawl_plan.recommended_engine or section.engine or "bing",
                    keyword=query,
                    section_name=section.name,
                    selector_health=selector_health,
                ),
                max_results=per_query,
                time_range=section.time_range,
                intent=intent,
            ))
    return SearchQueryPlan(
        section_name=section.name,
        queries=variants,
        max_total_results=total_budget,
    )
