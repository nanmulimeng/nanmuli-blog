"""Source Agent for digest source planning.

It receives one planned digest section, filters unusable sources, applies
quality-feedback hints from the knowledge base, and returns a crawl plan for
CrawlerAgent. It does not crawl pages itself.
"""

import logging
from copy import deepcopy
from dataclasses import dataclass, field

from crawler.digest_orchestrator import PlannedSection

logger = logging.getLogger(__name__)

_MAX_ITEMS_CAP = 30


def _normalize_source_id(source_id) -> int | str | None:
    if source_id is None or source_id == "":
        return None
    try:
        return int(source_id)
    except (TypeError, ValueError):
        return str(source_id)


def _normalize_source_url(source_url) -> str | None:
    if source_url is None:
        return None
    value = str(source_url).strip()
    return value or None


def _source_action_for(source_id, next_run_actions: dict, source_url=None) -> dict | None:
    normalized = _normalize_source_id(source_id)
    sources = next_run_actions.get("sources") or {}
    if normalized is not None:
        action = sources.get(normalized) or sources.get(str(normalized))
        if action:
            return action

        source_ids = next_run_actions.get("source_ids") or {}
        skip_ids = {_normalize_source_id(item) for item in source_ids.get("skip", [])}
        deprioritize_ids = {
            _normalize_source_id(item) for item in source_ids.get("deprioritize", [])
        }
        if normalized in skip_ids:
            return {"action": "skip", "reason": "source feedback"}
        if normalized in deprioritize_ids:
            return {"action": "deprioritize", "reason": "source feedback"}

    normalized_url = _normalize_source_url(source_url)
    if normalized_url is None:
        return None
    action = sources.get(f"url:{normalized_url}") or sources.get(normalized_url)
    if action:
        return action

    source_urls = next_run_actions.get("source_urls") or {}
    skip_urls = {_normalize_source_url(item) for item in source_urls.get("skip", [])}
    deprioritize_urls = {
        _normalize_source_url(item) for item in source_urls.get("deprioritize", [])
    }
    if normalized_url in skip_urls:
        return {"action": "skip", "reason": "source feedback"}
    if normalized_url in deprioritize_urls:
        return {"action": "deprioritize", "reason": "source feedback"}
    return None


@dataclass
class SourceCrawlPlan:
    """Source analysis report consumed by DigestOrchestrator."""

    section_name: str
    active_keywords: list[str] = field(default_factory=list)
    active_url_sources: list[dict] = field(default_factory=list)
    active_rss_sources: list[dict] = field(default_factory=list)
    skipped_source_ids: set = field(default_factory=set)
    skipped_source_urls: set[str] = field(default_factory=set)
    deprioritized_source_urls: set[str] = field(default_factory=set)
    recommended_engine: str = ""
    adjusted_max_items: int = 5
    analysis_log: list[str] = field(default_factory=list)


class SourceAgent:
    """Analyze configured sources and produce a section-level crawl plan."""

    def __init__(self, section: PlannedSection, config, config_snapshot: dict):
        self.section = section
        self.config_snapshot = config_snapshot
        self._config = self._copy_config(config)

    def analyze(self, kb_hint: dict | None = None) -> SourceCrawlPlan:
        """Filter sources and adapt crawl parameters using historical feedback."""
        from crawler.source_analysis import is_truly_dead

        section = self.section
        hint = kb_hint or {}
        next_run_actions = hint.get("next_run_actions") or {}
        plan = SourceCrawlPlan(
            section_name=section.name,
            recommended_engine=section.engine,
            adjusted_max_items=min(section.max_items, _MAX_ITEMS_CAP),
        )
        next_run_actions = self._guard_next_run_actions(next_run_actions, plan)
        self._attach_url_feedback(plan, next_run_actions)

        deprioritized_urls: list[dict] = []
        deprioritized_rss: list[dict] = []
        deprioritized_keywords: list[str] = []

        for src in section.url_sources:
            action = _source_action_for(src.get("source_id"), next_run_actions, src.get("url"))
            if self._skip_by_feedback(plan, "URL source", src.get("url", "?"), src.get("source_id"), action):
                continue
            eff = src.get("effectiveness", {})
            if is_truly_dead(eff):
                self._skip_dead(plan, "URL source", src.get("url", "?"), src.get("source_id"), eff)
                continue
            if action and action.get("action") == "deprioritize":
                deprioritized_urls.append(src)
                self._log_deprioritize(plan, "URL source", src.get("url", "?"), action)
                continue
            plan.active_url_sources.append(src)
        plan.active_url_sources.extend(deprioritized_urls)

        for src in section.rss_sources:
            action = _source_action_for(src.get("source_id"), next_run_actions, src.get("feed_url"))
            if self._skip_by_feedback(plan, "RSS source", src.get("feed_url", "?"), src.get("source_id"), action):
                continue
            eff = src.get("effectiveness", {})
            if is_truly_dead(eff):
                self._skip_dead(plan, "RSS source", src.get("feed_url", "?"), src.get("source_id"), eff)
                continue
            if action and action.get("action") == "deprioritize":
                deprioritized_rss.append(src)
                self._log_deprioritize(plan, "RSS source", src.get("feed_url", "?"), action)
                continue
            plan.active_rss_sources.append(src)
        plan.active_rss_sources.extend(deprioritized_rss)

        for kd in section.keyword_details:
            action = _source_action_for(kd.get("source_id"), next_run_actions, kd.get("value"))
            if self._skip_by_feedback(plan, "keyword", kd.get("value", "?"), kd.get("source_id"), action):
                continue
            eff = kd.get("effectiveness", {})
            if is_truly_dead(eff):
                self._skip_dead(plan, "keyword", kd.get("value", "?"), kd.get("source_id"), eff)
                continue
            kw_value = (kd.get("value") or "").strip()
            if not kw_value:
                continue
            if action and action.get("action") == "deprioritize":
                deprioritized_keywords.append(kw_value)
                self._log_deprioritize(plan, "keyword", kw_value, action)
                continue
            plan.active_keywords.append(kw_value)
        plan.active_keywords.extend(deprioritized_keywords)

        if not plan.active_keywords and section.keywords:
            plan.active_keywords = list(section.keywords)

        self._adapt_by_section_effectiveness(plan, hint)
        self._adapt_by_last_weaknesses(plan, hint)
        self._adapt_by_persistent_weaknesses(plan, hint)
        self._adapt_by_next_run_actions(plan, hint)

        plan.adjusted_max_items = min(plan.adjusted_max_items, _MAX_ITEMS_CAP)
        total = len(section.url_sources) + len(section.rss_sources) + len(section.keyword_details)
        skipped = len(plan.skipped_source_ids)
        plan.analysis_log.insert(
            0,
            f"Section '{section.name}': {total} sources analyzed, {skipped} skipped, "
            f"engine={plan.recommended_engine}, max_items={plan.adjusted_max_items}",
        )
        logger.info("[SourceAgent.analyze] %s", plan.analysis_log[0])
        return plan

    def _adapt_by_section_effectiveness(self, plan: SourceCrawlPlan, hint: dict) -> None:
        eff = self.section.effectiveness
        total_runs = eff.get("total_runs", 0)
        success_rate = eff.get("success_rate", 0.5)
        if total_runs < 3:
            return
        if success_rate < 0.4:
            plan.adjusted_max_items = max(3, int(plan.adjusted_max_items * 0.7))
            fallback_engines = ["bing", "sogou", "baidu"]
            recommended = hint.get("recommended_engine", "")
            if recommended and recommended in fallback_engines and recommended != plan.recommended_engine:
                plan.recommended_engine = recommended
                plan.analysis_log.append(
                    f"Low success rate ({success_rate:.2f}), switching engine to {recommended}"
                )
        elif success_rate >= 0.7:
            plan.adjusted_max_items = min(int(plan.adjusted_max_items * 1.3), _MAX_ITEMS_CAP)

    def _adapt_by_last_weaknesses(self, plan: SourceCrawlPlan, hint: dict) -> None:
        last_weaknesses = hint.get("last_weaknesses", [])
        if not last_weaknesses:
            return
        weakness_text = " ".join(str(w) for w in last_weaknesses)
        if "source_diversity" in weakness_text:
            plan.adjusted_max_items = min(int(plan.adjusted_max_items * 1.2), _MAX_ITEMS_CAP)
            plan.analysis_log.append(
                f"Boosted max_items (last weakness: source_diversity) -> {plan.adjusted_max_items}"
            )
        if "language" in weakness_text or "language_coverage" in weakness_text:
            plan.analysis_log.append(
                "Hint: last weakness was language coverage; cross-language may activate in optimization"
            )

    def _adapt_by_persistent_weaknesses(self, plan: SourceCrawlPlan, hint: dict) -> None:
        persistent_weak = hint.get("persistent_weak_dims", [])
        if not persistent_weak:
            return
        if "source_diversity" in persistent_weak:
            kb_engine = hint.get("recommended_engine", "")
            if kb_engine and kb_engine != plan.recommended_engine:
                plan.recommended_engine = kb_engine
                plan.analysis_log.append(
                    f"Persistent weak source_diversity, overriding engine to {kb_engine}"
                )
        if "depth" in persistent_weak or "angle" in persistent_weak:
            plan.adjusted_max_items = min(int(plan.adjusted_max_items * 1.3), _MAX_ITEMS_CAP)
            plan.analysis_log.append(
                f"Boosted max_items for persistent depth/angle weakness -> {plan.adjusted_max_items}"
            )
        if "temporal" in persistent_weak:
            time_upgrade = {"day": "week", "week": "month", "month": "year", "year": "all"}
            upgraded = time_upgrade.get(self.section.time_range)
            if upgraded:
                plan.analysis_log.append(
                    f"Persistent weak temporal, widening time_range {self.section.time_range} -> {upgraded}"
                )
                self.section.time_range = upgraded

    def _adapt_by_next_run_actions(self, plan: SourceCrawlPlan, hint: dict) -> None:
        actions = hint.get("next_run_actions") or {}
        boost_sections = {str(item) for item in actions.get("boost_sections", [])}
        if self.section.name in boost_sections or any(dim in boost_sections for dim in ("source_diversity", "angle", "depth")):
            plan.adjusted_max_items = min(int(plan.adjusted_max_items * 1.2), _MAX_ITEMS_CAP)
            plan.analysis_log.append(
                f"Applied next_run_actions boost section -> {plan.adjusted_max_items}"
            )

    def _guard_next_run_actions(self, next_run_actions: dict, plan: SourceCrawlPlan) -> dict:
        """Keep optimization feedback from starving a section due to one bad judgment."""
        if not isinstance(next_run_actions, dict) or not next_run_actions:
            return {}

        guarded = deepcopy(next_run_actions)
        confidence = str(guarded.get("confidence") or "").lower()
        if confidence == "low":
            self._downgrade_all_skip_actions(
                guarded, "guardrail: low-confidence skip downgraded"
            )
            plan.analysis_log.append(
                "Applied next_run_actions guardrail: low-confidence skip actions downgraded to deprioritize"
            )

        refs = self._configured_source_refs()
        if not refs:
            return guarded

        skip_refs = [
            ref for ref in refs
            if (_source_action_for(ref.get("source_id"), guarded, ref.get("value")) or {}).get("action") == "skip"
        ]
        if not skip_refs:
            return guarded

        max_skip = max(0, len(refs) // 2)
        if len(refs) == 1:
            max_skip = 0
        if len(skip_refs) <= max_skip:
            return guarded

        skip_refs.sort(key=lambda ref: self._source_action_score(ref, guarded))
        for ref in skip_refs[max_skip:]:
            self._downgrade_skip_ref(
                guarded, ref, "guardrail: per-section skip cap downgraded"
            )
        plan.analysis_log.append(
            f"Applied next_run_actions guardrail: skip cap {len(skip_refs)} -> {max_skip}"
        )
        return guarded

    def _configured_source_refs(self) -> list[dict]:
        refs: list[dict] = []
        for src in self.section.url_sources:
            refs.append({
                "source_id": src.get("source_id"),
                "value": src.get("url"),
            })
        for src in self.section.rss_sources:
            refs.append({
                "source_id": src.get("source_id"),
                "value": src.get("feed_url"),
            })
        for item in self.section.keyword_details:
            refs.append({
                "source_id": item.get("source_id"),
                "value": item.get("value"),
            })
        return [
            ref for ref in refs
            if _normalize_source_id(ref.get("source_id")) is not None
            or _normalize_source_url(ref.get("value")) is not None
        ]

    @staticmethod
    def _source_action_score(ref: dict, actions: dict) -> float:
        action = _source_action_for(ref.get("source_id"), actions, ref.get("value")) or {}
        score = action.get("quality_score")
        try:
            return float(score)
        except (TypeError, ValueError):
            return 1.0

    @classmethod
    def _downgrade_all_skip_actions(cls, actions: dict, reason: str) -> None:
        source_ids = actions.setdefault("source_ids", {})
        source_urls = actions.setdefault("source_urls", {})
        for sid in list(source_ids.get("skip", []) or []):
            cls._move_unique(source_ids.setdefault("deprioritize", []), sid)
        source_ids["skip"] = []
        for url in list(source_urls.get("skip", []) or []):
            cls._move_unique(source_urls.setdefault("deprioritize", []), url)
        source_urls["skip"] = []
        for action in (actions.get("sources") or {}).values():
            if isinstance(action, dict) and action.get("action") == "skip":
                action["action"] = "deprioritize"
                action["reason"] = f"{reason}; {action.get('reason', 'source feedback')}"

    @classmethod
    def _downgrade_skip_ref(cls, actions: dict, ref: dict, reason: str) -> None:
        sid = _normalize_source_id(ref.get("source_id"))
        url = _normalize_source_url(ref.get("value"))
        source_ids = actions.setdefault("source_ids", {})
        source_urls = actions.setdefault("source_urls", {})

        if sid is not None:
            source_ids["skip"] = [
                item for item in source_ids.get("skip", []) or []
                if _normalize_source_id(item) != sid
            ]
            cls._move_unique(source_ids.setdefault("deprioritize", []), sid)

        if url is not None:
            source_urls["skip"] = [
                item for item in source_urls.get("skip", []) or []
                if _normalize_source_url(item) != url
            ]
            cls._move_unique(source_urls.setdefault("deprioritize", []), url)

        sources = actions.get("sources") or {}
        candidate_keys = []
        if sid is not None:
            candidate_keys.extend([sid, str(sid)])
        if url is not None:
            candidate_keys.extend([url, f"url:{url}"])
        for key in candidate_keys:
            action = sources.get(key)
            if isinstance(action, dict) and action.get("action") == "skip":
                action["action"] = "deprioritize"
                action["reason"] = f"{reason}; {action.get('reason', 'source feedback')}"

    @staticmethod
    def _move_unique(target: list, value) -> None:
        normalized_value = _normalize_source_id(value)
        normalized_url = _normalize_source_url(value)
        for item in target:
            if _normalize_source_id(item) == normalized_value:
                return
            if normalized_url is not None and _normalize_source_url(item) == normalized_url:
                return
        target.append(value)

    @staticmethod
    def _attach_url_feedback(plan: SourceCrawlPlan, next_run_actions: dict) -> None:
        source_urls = next_run_actions.get("source_urls") or {}
        for url in source_urls.get("skip", []) or []:
            normalized = _normalize_source_url(url)
            if normalized:
                plan.skipped_source_urls.add(normalized)
        for url in source_urls.get("deprioritize", []) or []:
            normalized = _normalize_source_url(url)
            if normalized:
                plan.deprioritized_source_urls.add(normalized)

        for action in (next_run_actions.get("sources") or {}).values():
            if not isinstance(action, dict):
                continue
            normalized = _normalize_source_url(action.get("source_url"))
            if not normalized:
                continue
            if action.get("action") == "skip":
                plan.skipped_source_urls.add(normalized)
            elif action.get("action") == "deprioritize":
                plan.deprioritized_source_urls.add(normalized)

    @staticmethod
    def _skip_by_feedback(
        plan: SourceCrawlPlan,
        source_type: str,
        label: str,
        source_id,
        action: dict | None,
    ) -> bool:
        if not action or action.get("action") != "skip":
            return False
        sid = _normalize_source_id(source_id)
        if sid is not None:
            plan.skipped_source_ids.add(sid)
        normalized_label = _normalize_source_url(label)
        if normalized_label and normalized_label.startswith(("http://", "https://")):
            plan.skipped_source_urls.add(normalized_label)
        plan.analysis_log.append(
            f"Skip next_run_actions {source_type}: {label} ({action.get('reason', 'source feedback')})"
        )
        return True

    @staticmethod
    def _skip_dead(
        plan: SourceCrawlPlan,
        source_type: str,
        label: str,
        source_id,
        effectiveness: dict,
    ) -> None:
        sid = _normalize_source_id(source_id)
        if sid is not None:
            plan.skipped_source_ids.add(sid)
        plan.analysis_log.append(
            f"Skip dead {source_type}: {label} (quality={effectiveness.get('avg_quality_score', '?')})"
        )

    @staticmethod
    def _log_deprioritize(
        plan: SourceCrawlPlan,
        source_type: str,
        label: str,
        action: dict,
    ) -> None:
        plan.analysis_log.append(
            f"deprioritize {source_type}: {label} ({action.get('reason', 'source feedback')})"
        )

    @staticmethod
    def _copy_config(config):
        """Deep-copy crawler config."""
        from crawler.digest import copy_config
        return copy_config(config)
