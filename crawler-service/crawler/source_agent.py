"""Source Agent for digest source planning.

It receives one planned digest section, filters unusable sources, applies
quality-feedback hints from the knowledge base, and returns a crawl plan for
CrawlerAgent. It does not crawl pages itself.
"""

import logging
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
