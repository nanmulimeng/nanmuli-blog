"""Search feedback snapshots built from digest search diagnostics."""

import json
from collections import Counter, defaultdict
from typing import Any


def _as_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _round_rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def _safe_metadata(value: Any) -> dict:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _search_diagnostics_from_task(task: dict) -> list[dict]:
    metadata = _safe_metadata(task.get("ai_search_metadata"))
    plan = metadata.get("orchestrator_plan")
    if not isinstance(plan, dict):
        return []
    diagnostics = plan.get("search_diagnostics")
    return diagnostics if isinstance(diagnostics, list) else []


def _domain_top(counter: Counter, limit: int = 5) -> list[str]:
    return [domain for domain, _ in counter.most_common(limit)]


def summarize_search_diagnostics(diagnostics: list[dict]) -> dict:
    """Aggregate query-level diagnostics into stable section/engine summaries."""
    total_returned = 0
    total_kept = 0
    total_filtered = 0
    zero_result_queries = []
    section_stats: dict[str, dict] = {}
    engine_stats: dict[str, dict] = {}

    for raw in diagnostics or []:
        if not isinstance(raw, dict):
            continue
        section = str(raw.get("section") or "unknown")
        engine = str(raw.get("engine") or "unknown")
        returned = _as_int(raw.get("returned"))
        kept = _as_int(raw.get("kept"))
        filtered = _as_int(raw.get("filtered"))
        total_returned += returned
        total_kept += kept
        total_filtered += filtered

        if returned == 0 or kept == 0:
            zero_result_queries.append({
                "section": section,
                "engine": engine,
                "query": raw.get("query") or "",
                "returned": returned,
                "kept": kept,
            })

        section_bucket = section_stats.setdefault(section, {
            "section": section,
            "queries": 0,
            "returned": 0,
            "kept": 0,
            "filtered": 0,
            "zero_result_queries": 0,
            "_domains": Counter(),
        })
        engine_bucket = engine_stats.setdefault(engine, {
            "engine": engine,
            "queries": 0,
            "returned": 0,
            "kept": 0,
            "filtered": 0,
            "zero_result_queries": 0,
            "_domains": Counter(),
        })

        for bucket in (section_bucket, engine_bucket):
            bucket["queries"] += 1
            bucket["returned"] += returned
            bucket["kept"] += kept
            bucket["filtered"] += filtered
            if returned == 0 or kept == 0:
                bucket["zero_result_queries"] += 1
            for domain in raw.get("top_domains") or []:
                if domain:
                    bucket["_domains"][str(domain)] += 1

    def finalize(bucket: dict) -> dict:
        bucket = dict(bucket)
        domains = bucket.pop("_domains", Counter())
        bucket["keep_rate"] = _round_rate(bucket["kept"], bucket["returned"])
        bucket["top_domains"] = _domain_top(domains)
        return bucket

    return {
        "total_queries": len([d for d in diagnostics or [] if isinstance(d, dict)]),
        "total_returned": total_returned,
        "total_kept": total_kept,
        "total_filtered": total_filtered,
        "keep_rate": _round_rate(total_kept, total_returned),
        "zero_result_queries": zero_result_queries,
        "section_summaries": [
            finalize(bucket)
            for bucket in sorted(section_stats.values(), key=lambda item: item["section"])
        ],
        "engine_summaries": [
            finalize(bucket)
            for bucket in sorted(engine_stats.values(), key=lambda item: item["engine"])
        ],
    }


def build_search_feedback_snapshot(task: dict) -> dict:
    diagnostics = _search_diagnostics_from_task(task)
    return {
        "task_id": task.get("id"),
        "digest_date": task.get("digest_date"),
        "status": task.get("status"),
        "created_at": task.get("created_at"),
        "diagnostics": diagnostics,
        "summary": summarize_search_diagnostics(diagnostics),
    }


def _diagnostics_from_snapshot(snapshot: dict) -> list[dict]:
    if not isinstance(snapshot, dict):
        return []
    diagnostics = snapshot.get("diagnostics")
    if isinstance(diagnostics, list):
        return diagnostics
    summary = snapshot.get("summary")
    if isinstance(summary, dict):
        zero_queries = summary.get("zero_result_queries")
        if isinstance(zero_queries, list):
            return zero_queries
    return []


def derive_search_feedback_hints(snapshots: list[dict]) -> dict:
    """Convert recent search diagnostics into planner-safe section hints.

    Hints are intentionally conservative: they prefer productive engines/domains
    and demote repeatedly unproductive engines/intents, but they do not remove
    query variants outright.
    """
    engine_stats: dict[tuple[str, str], dict] = defaultdict(
        lambda: {"queries": 0, "returned": 0, "kept": 0, "zero": 0}
    )
    intent_stats: dict[tuple[str, str], dict] = defaultdict(
        lambda: {"queries": 0, "returned": 0, "kept": 0, "zero": 0}
    )
    domain_stats: dict[str, Counter] = defaultdict(Counter)

    for snapshot in snapshots or []:
        for raw in _diagnostics_from_snapshot(snapshot):
            if not isinstance(raw, dict):
                continue
            section = str(raw.get("section") or "").strip()
            if not section:
                continue
            engine = str(raw.get("engine") or "").strip()
            intent = str(raw.get("intent") or "").strip()
            returned = _as_int(raw.get("returned"))
            kept = _as_int(raw.get("kept"))
            is_zero = returned == 0 or kept == 0

            if engine:
                bucket = engine_stats[(section, engine)]
                bucket["queries"] += 1
                bucket["returned"] += returned
                bucket["kept"] += kept
                if is_zero:
                    bucket["zero"] += 1

            if intent:
                bucket = intent_stats[(section, intent)]
                bucket["queries"] += 1
                bucket["returned"] += returned
                bucket["kept"] += kept
                if is_zero:
                    bucket["zero"] += 1

            if kept > 0:
                for domain in raw.get("top_domains") or []:
                    if domain:
                        domain_stats[section][str(domain)] += kept

    preferred_engines: dict[str, list[str]] = defaultdict(list)
    penalized_engines: dict[str, list[str]] = defaultdict(list)
    penalized_intents: dict[str, list[str]] = defaultdict(list)
    preferred_domains: dict[str, list[str]] = {}

    engines_by_section: dict[str, list[tuple[str, dict]]] = defaultdict(list)
    for (section, engine), stats in engine_stats.items():
        engines_by_section[section].append((engine, stats))
        keep_rate = _round_rate(stats["kept"], stats["returned"])
        zero_rate = _round_rate(stats["zero"], stats["queries"])
        if stats["queries"] >= 1 and (stats["kept"] == 0 or zero_rate >= 0.75):
            penalized_engines[section].append(engine)
        elif stats["kept"] > 0 and keep_rate >= 0.35:
            preferred_engines[section].append(engine)

    for section, engines in engines_by_section.items():
        preferred_engines[section] = [
            engine
            for engine, stats in sorted(
                engines,
                key=lambda item: (
                    _round_rate(item[1]["kept"], item[1]["returned"]),
                    item[1]["kept"],
                ),
                reverse=True,
            )
            if engine in preferred_engines.get(section, [])
            and engine not in penalized_engines.get(section, [])
        ][:2]

    for (section, intent), stats in intent_stats.items():
        zero_rate = _round_rate(stats["zero"], stats["queries"])
        if stats["queries"] >= 1 and (stats["kept"] == 0 or zero_rate >= 0.75):
            penalized_intents[section].append(intent)

    for section, domains in domain_stats.items():
        top_domains = _domain_top(domains, limit=3)
        if top_domains:
            preferred_domains[section] = top_domains

    hints = {
        "section_engine_preferences": {
            section: engines
            for section, engines in preferred_engines.items()
            if engines
        },
        "section_engine_penalties": {
            section: sorted(set(engines))
            for section, engines in penalized_engines.items()
            if engines
        },
        "section_intent_penalties": {
            section: sorted(set(intents))
            for section, intents in penalized_intents.items()
            if intents
        },
        "section_domain_preferences": preferred_domains,
    }
    return {key: value for key, value in hints.items() if value}
