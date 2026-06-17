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


def _section_feedback_list(feedback_hints: dict | None, key: str, section_name: str) -> list[str]:
    if not isinstance(feedback_hints, dict):
        return []
    values = feedback_hints.get(key) or {}
    if not isinstance(values, dict):
        return []
    section_values = values.get(section_name) or []
    return [str(item) for item in section_values if item]


def choose_engine(
    primary: str,
    *,
    keyword: str,
    section_name: str,
    selector_health: dict,
    feedback_hints: dict | None = None,
) -> str:
    primary = primary or "bing"
    preferred = _section_feedback_list(
        feedback_hints, "section_engine_preferences", section_name
    )
    penalized = set(_section_feedback_list(
        feedback_hints, "section_engine_penalties", section_name
    ))
    for engine in preferred:
        if engine and engine not in penalized:
            return engine

    primary_health = selector_health.get(primary) or {}
    attempts = int(primary_health.get("total_attempts") or 0)
    if primary not in penalized and (
        attempts < 3 or _zero_result_ratio(primary, selector_health) < 0.8
    ):
        return primary

    for candidate in ENGINE_FALLBACKS.get(primary, ["bing", "sogou", "baidu", "google"]):
        if candidate == primary:
            continue
        if candidate in penalized:
            continue
        candidate_health = selector_health.get(candidate) or {}
        candidate_attempts = int(candidate_health.get("total_attempts") or 0)
        if candidate_attempts == 0 or _zero_result_ratio(candidate, selector_health) < 0.5:
            return candidate
    return primary


def _order_variants_by_feedback(
    section_name: str,
    variants: list[tuple[str, str]],
    feedback_hints: dict | None,
) -> list[tuple[str, str]]:
    penalized_intents = set(_section_feedback_list(
        feedback_hints, "section_intent_penalties", section_name
    ))
    preferred_domains = _section_feedback_list(
        feedback_hints, "section_domain_preferences", section_name
    )
    if not penalized_intents and not preferred_domains:
        return variants

    def score(item: tuple[int, tuple[str, str]]) -> tuple[int, int, int]:
        index, (query, intent) = item
        has_preferred_domain = any(domain in query for domain in preferred_domains)
        return (
            1 if intent in penalized_intents else 0,
            0 if has_preferred_domain else 1,
            index,
        )

    return [
        variant
        for _, variant in sorted(enumerate(variants), key=score)
    ]


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
    feedback_hints = (config_snapshot or {}).get("search_feedback_hints") or {}
    total_budget = (
        max(crawl_plan.adjusted_max_items, section.max_items)
        * settings.digest_section_result_multiplier
    )
    keywords = crawl_plan.active_keywords or section.keywords
    per_query = max(2, min(8, total_budget // max(1, len(keywords) * 2)))
    for keyword in keywords:
        section_variants = _order_variants_by_feedback(
            section.name,
            _section_variants(section.name, keyword),
            feedback_hints,
        )
        for query, intent in section_variants:
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
                    feedback_hints=feedback_hints,
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
