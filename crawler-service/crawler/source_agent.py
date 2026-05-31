"""信息源 Agent — 分析管理员配置的信息源，产出 SourceCrawlPlan 报告

由总管 Agent (DigestOrchestrator) 创建。
职责单一：接收板块配置，分析源健康度，过滤死源，参数自适应，输出爬取计划。
实际爬取由 CrawlerAgent 执行。
"""

import logging
from dataclasses import dataclass, field

from config import settings
from crawler.digest_orchestrator import PlannedSection

logger = logging.getLogger(__name__)

_MAX_ITEMS_CAP = 30


@dataclass
class SourceCrawlPlan:
    """信息源分析报告（交给 Orchestrator，再转交 CrawlerAgent）"""
    section_name: str
    active_keywords: list[str] = field(default_factory=list)
    active_url_sources: list[dict] = field(default_factory=list)
    active_rss_sources: list[dict] = field(default_factory=list)
    skipped_source_ids: set = field(default_factory=set)
    recommended_engine: str = ""
    adjusted_max_items: int = 5
    analysis_log: list[str] = field(default_factory=list)


class SourceAgent:
    """信息源 Agent：分析整理信息源，输出 SourceCrawlPlan

    由总管 Agent 创建，不做实际爬取（那是 CrawlerAgent 的职责）。
    """

    def __init__(self, section: PlannedSection, config, config_snapshot: dict):
        self.section = section
        self.config_snapshot = config_snapshot
        self._config = self._copy_config(config)

    def analyze(self, kb_hint: dict | None = None) -> SourceCrawlPlan:
        """分析信息源健康度，过滤死源，参数自适应，输出 SourceCrawlPlan"""
        from crawler.source_analysis import is_truly_dead

        section = self.section
        plan = SourceCrawlPlan(
            section_name=section.name,
            recommended_engine=section.engine,
            adjusted_max_items=min(section.max_items, _MAX_ITEMS_CAP),
        )

        # 1. URL/RSS 源过滤
        for src in section.url_sources:
            eff = src.get("effectiveness", {})
            if is_truly_dead(eff):
                sid = src.get("source_id")
                if sid is not None:
                    plan.skipped_source_ids.add(sid)
                plan.analysis_log.append(
                    f"Skip dead URL source: {src.get('url', '?')} (quality={eff.get('avg_quality_score', '?')})"
                )
                continue
            plan.active_url_sources.append(src)

        for src in section.rss_sources:
            eff = src.get("effectiveness", {})
            if is_truly_dead(eff):
                sid = src.get("source_id")
                if sid is not None:
                    plan.skipped_source_ids.add(sid)
                plan.analysis_log.append(
                    f"Skip dead RSS source: {src.get('feed_url', '?')} (quality={eff.get('avg_quality_score', '?')})"
                )
                continue
            plan.active_rss_sources.append(src)

        # 2. Keyword 源过滤
        for kd in section.keyword_details:
            eff = kd.get("effectiveness", {})
            if is_truly_dead(eff):
                sid = kd.get("source_id")
                if sid is not None:
                    plan.skipped_source_ids.add(sid)
                plan.analysis_log.append(
                    f"Skip dead keyword: {kd.get('value', '?')} (quality={eff.get('avg_quality_score', '?')})"
                )
                continue
            kw_value = kd.get("value", "").strip()
            if kw_value:
                plan.active_keywords.append(kw_value)

        # 兼容旧路径：keyword_details 为空时 fallback 到 section.keywords
        if not plan.active_keywords and section.keywords:
            plan.active_keywords = list(section.keywords)

        # 3. 参数自适应：基于板块效能
        eff = section.effectiveness
        total_runs = eff.get("total_runs", 0)
        success_rate = eff.get("success_rate", 0.5)

        if total_runs >= 3:
            if success_rate < 0.4:
                plan.adjusted_max_items = max(3, int(plan.adjusted_max_items * 0.7))
                fallback_engines = ["bing", "sogou", "baidu"]
                recommended = (kb_hint or {}).get("recommended_engine", "")
                if recommended and recommended in fallback_engines and recommended != plan.recommended_engine:
                    plan.recommended_engine = recommended
                    plan.analysis_log.append(
                        f"Low success rate ({success_rate:.2f}), switching engine to {recommended}"
                    )
            elif success_rate >= 0.7:
                plan.adjusted_max_items = min(
                    int(plan.adjusted_max_items * 1.3), _MAX_ITEMS_CAP
                )

        # 4. 能力 6: 基于上次评估弱点调整参数
        last_weaknesses = (kb_hint or {}).get("last_weaknesses", [])
        if last_weaknesses:
            weakness_text = " ".join(str(w) for w in last_weaknesses)
            if "source_diversity" in weakness_text:
                plan.adjusted_max_items = min(int(plan.adjusted_max_items * 1.2), _MAX_ITEMS_CAP)
                plan.analysis_log.append(
                    f"Boosted max_items (last weakness: source_diversity) → {plan.adjusted_max_items}"
                )
            if "language" in weakness_text or "language_coverage" in weakness_text:
                plan.analysis_log.append(
                    "Hint: last weakness was language coverage — cross-language may activate in optimization"
                )

        # 5. 基于持续弱维度（质量趋势）调整策略
        persistent_weak = (kb_hint or {}).get("persistent_weak_dims", [])
        if persistent_weak:
            if "source_diversity" in persistent_weak:
                kb_engine = (kb_hint or {}).get("recommended_engine", "")
                if kb_engine and kb_engine != plan.recommended_engine:
                    plan.recommended_engine = kb_engine
                    plan.analysis_log.append(
                        f"Persistent weak source_diversity, overriding engine to {kb_engine}"
                    )
            if "depth" in persistent_weak or "angle" in persistent_weak:
                plan.adjusted_max_items = min(int(plan.adjusted_max_items * 1.3), _MAX_ITEMS_CAP)
                plan.analysis_log.append(
                    f"Boosted max_items for persistent depth/angle weakness → {plan.adjusted_max_items}"
                )
            if "temporal" in persistent_weak:
                time_upgrade = {"day": "week", "week": "month", "month": "year", "year": "all"}
                upgraded = time_upgrade.get(section.time_range)
                if upgraded:
                    plan.analysis_log.append(
                        f"Persistent weak temporal, widening time_range {section.time_range} → {upgraded}"
                    )
                    section.time_range = upgraded

        # 6. max_items 上限保护
        plan.adjusted_max_items = min(plan.adjusted_max_items, _MAX_ITEMS_CAP)

        # 汇总日志
        total = len(section.url_sources) + len(section.rss_sources) + len(section.keyword_details)
        skipped = len(plan.skipped_source_ids)
        plan.analysis_log.insert(0,
            f"Section '{section.name}': {total} sources analyzed, {skipped} dead skipped, "
            f"engine={plan.recommended_engine}, max_items={plan.adjusted_max_items}"
        )

        logger.info("[SourceAgent.analyze] %s", plan.analysis_log[0])
        return plan

    @staticmethod
    def _copy_config(config):
        """深拷贝配置"""
        from crawler.digest import copy_config
        return copy_config(config)
