"""Deterministic ranking for digest search candidates."""

import re
from copy import copy
from urllib.parse import urlparse

from crawler.filters import is_excluded_domain


SECTION_DOMAIN_BOOSTS = {
    "hot_trend": {
        "github.blog", "openai.com", "anthropic.com", "deepmind.google",
        "microsoft.com", "cloudflare.com",
    },
    "open_source": {"github.com", "gitlab.com", "huggingface.co"},
    "dev_tool": {
        "code.visualstudio.com", "jetbrains.com", "github.blog",
        "postman.com", "vercel.com",
    },
    "tech_article": {
        "martinfowler.com", "github.blog", "cloudflare.com",
        "netflixtechblog.com", "engineering.atspotify.com",
    },
    "paper": {"arxiv.org", "openreview.net", "paperswithcode.com"},
}

GENERIC_PATH_PARTS = {
    "", "blog", "blogs", "news", "latest", "tag", "tags", "category",
    "categories", "search", "topics", "topic",
}

WEAK_TERMS = {
    "the", "and", "or", "for", "with", "from", "what", "is", "are",
    "this", "that", "latest", "today", "news", "article", "blog",
}


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9][a-z0-9._-]*", (text or "").lower())
        if len(token) >= 2 and token not in WEAK_TERMS
    }


def _domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().removeprefix("www.")
    except Exception:
        return ""


def _path_parts(url: str) -> list[str]:
    try:
        return [part for part in urlparse(url).path.lower().split("/") if part]
    except Exception:
        return []


def _section_domain_boost(section_name: str, url: str) -> float:
    domain = _domain(url)
    boosts = SECTION_DOMAIN_BOOSTS.get(section_name, set())
    if domain in boosts:
        return 0.45 if section_name == "paper" else 0.3
    if any(domain.endswith("." + item) for item in boosts):
        return 0.4 if section_name == "paper" else 0.25
    return 0.0


def _generic_path_penalty(url: str) -> float:
    parts = _path_parts(url)
    if not parts:
        return 0.18
    if len(parts) == 1 and parts[0] in GENERIC_PATH_PARTS:
        return 0.14
    if any(part in {"tag", "tags", "category", "categories", "search"} for part in parts):
        return 0.12
    return 0.0


def _rank_penalty(metadata: dict | None) -> float:
    if not metadata:
        return 0.0
    try:
        rank = int(metadata.get("search_rank") or 0)
    except (TypeError, ValueError):
        return 0.0
    return min(0.12, max(0, rank - 1) * 0.015)


def score_search_candidate(
    section_name: str,
    keyword: str,
    title: str,
    url: str,
    snippet: str,
    metadata: dict | None = None,
) -> dict:
    keyword_tokens = _tokens(keyword)
    title_tokens = _tokens(title)
    snippet_tokens = _tokens(snippet)
    combined_tokens = title_tokens | snippet_tokens

    title_overlap = len(keyword_tokens & title_tokens) / max(1, len(keyword_tokens))
    text_overlap = len(keyword_tokens & combined_tokens) / max(1, len(keyword_tokens))
    score = 0.18 + title_overlap * 0.32 + text_overlap * 0.22
    score += _section_domain_boost(section_name, url)
    score -= _generic_path_penalty(url)
    score -= _rank_penalty(metadata)
    if is_excluded_domain(url):
        score -= 0.45
    score = max(0.0, min(1.0, round(score, 4)))
    return {
        "score": score,
        "title_overlap": round(title_overlap, 4),
        "text_overlap": round(text_overlap, 4),
        "domain": _domain(url),
    }


def _field(item, key: str, default=""):
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def _metadata(item) -> dict:
    if isinstance(item, dict):
        return dict(item.get("metadata") or {})
    return dict(getattr(item, "metadata", {}) or {})


def _with_metadata(item, metadata: dict):
    if isinstance(item, dict):
        enriched = dict(item)
        enriched["metadata"] = metadata
        return enriched
    enriched = copy(item)
    enriched.metadata = metadata
    return enriched


def rank_search_candidates(section_name: str, keyword: str, candidates: list) -> list:
    ranked = []
    for index, item in enumerate(candidates):
        metadata = _metadata(item)
        score = score_search_candidate(
            section_name,
            keyword,
            _field(item, "title", ""),
            _field(item, "url", ""),
            _field(item, "snippet", _field(item, "markdown", "")),
            metadata,
        )
        metadata["relevance_score"] = score["score"]
        metadata["rank_features"] = score
        ranked.append((_with_metadata(item, metadata), index))
    ranked.sort(
        key=lambda pair: (
            -pair[0]["metadata"]["relevance_score"] if isinstance(pair[0], dict)
            else -pair[0].metadata.get("relevance_score", 0),
            pair[1],
        )
    )
    return [item for item, _ in ranked]
