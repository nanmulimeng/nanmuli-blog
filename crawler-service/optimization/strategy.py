"""策略生成器 — 深度/广度分离架构

DepthStrategyGen: 深度方向（depth, angle, temporal）
BreadthStrategyGen: 广度方向（source_diversity, perspective, language）
StrategyGenerator: 向后兼容的合并入口
"""

import logging
import random
from dataclasses import dataclass

from crawler.utils import detect_cjk

logger = logging.getLogger(__name__)

# 搜索引擎优先级（与 crawler/search.py 一致）
ENGINE_PRIORITY = ["bing", "baidu", "sogou", "google"]

# 维度策略触发阈值（language 天然偏低，降低阈值避免过度优化）
_DIMENSION_THRESHOLDS = {
    "source_diversity": 0.6,
    "perspective": 0.6,
    "language": 0.3,
    "depth": 0.6,
    "angle": 0.6,
    "temporal": 0.6,
}


@dataclass
class SearchStrategy:
    keyword: str
    engine: str
    time_range: str
    site_scope: str | None = None
    strategy_type: str = "initial"
    reason: str = ""
    source_expand_section: dict | None = None
    source_expand_overrides: dict | None = None
    target_dimension: str = ""


class DepthStrategyGen:
    """深度策略生成器 — 关注 depth/angle/temporal"""

    DEPTH_DIMENSIONS = {
        "depth": "depth_coverage",
        "angle": "angle_coverage",
        "temporal": "temporal_coverage",
    }

    def generate(
        self,
        keyword: str,
        evaluation,
        current_engine: str,
        current_time_range: str,
        round_num: int,
        history: list[SearchStrategy] | None = None,
        kb_hint: dict | None = None,
        **kwargs,
    ) -> SearchStrategy | None:
        dims = {name: getattr(evaluation, attr) for name, attr in self.DEPTH_DIMENSIONS.items()}
        sorted_dims = sorted(dims.items(), key=lambda x: x[1])

        history = history or []

        for weakest, weakest_score in sorted_dims:
            threshold = _DIMENSION_THRESHOLDS.get(weakest, 0.6)
            if weakest_score >= threshold:
                continue

            if self._is_dimension_exhausted(weakest, history):
                continue

            strategy_map = {
                "temporal": self._strategy_temporal,
                "depth": self._strategy_depth,
                "angle": self._strategy_angle,
            }

            handler = strategy_map.get(weakest)
            if not handler:
                continue

            strategy = handler(
                keyword=keyword,
                score=weakest_score,
                current_engine=current_engine,
                current_time_range=current_time_range,
                history=history,
            )
            if strategy is not None:
                return strategy

        return None

    @staticmethod
    def _is_dimension_exhausted(dimension: str, history: list) -> bool:
        """某维度连续 2 轮被尝试且无效果，视为疲劳"""
        if len(history) < 2:
            return False
        recent = history[-2:]
        matching = sum(1 for h in recent if getattr(h, 'target_dimension', '') == dimension)
        return matching >= 2

    # ============== 具体策略 ==============

    def _strategy_temporal(
        self, keyword: str, score: float,
        current_engine: str, current_time_range: str,
        history: list[SearchStrategy],
    ) -> SearchStrategy | None:
        expansion = {"day": "week", "week": "month", "month": "year", "year": "all"}
        expanded = expansion.get(current_time_range)
        if expanded:
            return SearchStrategy(
                keyword=keyword,
                engine=current_engine,
                time_range=expanded,
                strategy_type="time_adjust",
                reason=f"时效性覆盖仅 {score:.0%}，扩展时间范围 {current_time_range} → {expanded}",
                target_dimension="temporal",
            )
        return None

    # 深度限定词（基础 + 二级）
    _CN_DEPTH = ["原理 源码分析", "内部实现 实战", "深入理解 底层原理", "源码解读 实现细节"]
    _CN_DEPTH_SEC = ["架构设计 思路", "核心概念 详解", "实现原理 分析", "技术选型 方案"]
    _EN_DEPTH = ["architecture deep dive", "internals implementation", "how it works under the hood", "in-depth tutorial"]
    _EN_DEPTH_SEC = ["architecture design patterns", "core concepts explained", "implementation analysis", "technology selection"]

    # 角度变体（基础 + 二级）
    _CN_ANGLE = ["对比 评测", "最佳实践", "性能优化", "常见问题 解决方案"]
    _CN_ANGLE_SEC = ["使用场景 案例", "进阶技巧 高级用法", "替代方案 迁移", "趋势 发展方向"]
    _EN_ANGLE = ["comparison vs alternatives", "best practices", "performance optimization", "common issues troubleshooting"]
    _EN_ANGLE_SEC = ["use cases examples", "advanced techniques", "alternatives migration", "trends roadmap"]

    def _strategy_depth(
        self, keyword: str, score: float,
        current_engine: str, current_time_range: str,
        history: list[SearchStrategy],
    ) -> SearchStrategy | None:
        is_cn = detect_cjk(keyword)
        depth_modifiers = (
            self._CN_DEPTH + self._CN_DEPTH_SEC
            if is_cn else
            self._EN_DEPTH + self._EN_DEPTH_SEC
        )
        used_keywords = {h.keyword for h in history}
        for mod in depth_modifiers:
            candidate = f"{keyword} {mod}"
            if candidate not in used_keywords:
                return SearchStrategy(
                    keyword=candidate,
                    engine=current_engine,
                    time_range=current_time_range,
                    strategy_type="keyword_refine",
                    reason=f"深度覆盖仅 {score:.0%}，添加深度限定词 '{mod}'",
                    target_dimension="depth",
                )
        # 年份限定 fallback
        import datetime
        year = datetime.datetime.now().year
        suffix = "最新" if is_cn else "latest"
        year_candidate = f"{keyword} {year} {suffix}"
        if year_candidate not in used_keywords:
            return SearchStrategy(
                keyword=year_candidate,
                engine=current_engine,
                time_range=current_time_range,
                strategy_type="keyword_refine",
                reason=f"深度覆盖仅 {score:.0%}，添加年份限定",
                target_dimension="depth",
            )
        return None

    def _strategy_angle(
        self, keyword: str, score: float,
        current_engine: str, current_time_range: str,
        history: list[SearchStrategy],
    ) -> SearchStrategy | None:
        is_cn = detect_cjk(keyword)
        suffixes = (
            self._CN_ANGLE + self._CN_ANGLE_SEC
            if is_cn else
            self._EN_ANGLE + self._EN_ANGLE_SEC
        )
        angle_variants = [f"{keyword} {s}" for s in suffixes]
        used_keywords = {h.keyword for h in history}
        for variant in angle_variants:
            if variant not in used_keywords:
                return SearchStrategy(
                    keyword=variant,
                    engine=current_engine,
                    time_range=current_time_range,
                    strategy_type="keyword_refine",
                    reason=f"角度覆盖仅 {score:.0%}，搜索角度变体",
                    target_dimension="angle",
                )
        return None


class BreadthStrategyGen:
    """广度策略生成器 — 关注 source_diversity/perspective/language"""

    BREADTH_DIMENSIONS = {
        "source_diversity": "source_diversity",
        "perspective": "perspective_balance",
        "language": "language_coverage",
    }

    # 策略类型 → 对应维度的映射
    _TYPE_TO_DIMENSION = {
        "engine_switch": "source_diversity",
        "site_scope": "source_diversity",
        "source_expand": "source_diversity",
        "cross_language": "language",
    }

    def generate(
        self,
        keyword: str,
        evaluation,
        current_engine: str,
        current_time_range: str,
        round_num: int,
        history: list[SearchStrategy] | None = None,
        kb_hint: dict | None = None,
        sections: list[dict] | None = None,
        **kwargs,
    ) -> SearchStrategy | None:
        dims = {name: getattr(evaluation, attr) for name, attr in self.BREADTH_DIMENSIONS.items()}
        sorted_dims = sorted(dims.items(), key=lambda x: x[1])

        history = history or []

        # 知识库提示
        if kb_hint:
            alt = self._pick_hinted_dimension(dims, kb_hint)
            if alt:
                # 将 KB 推荐维度移到前面
                sorted_dims = [(alt, dims[alt])] + [(k, v) for k, v in sorted_dims if k != alt]

        for weakest, weakest_score in sorted_dims:
            threshold = _DIMENSION_THRESHOLDS.get(weakest, 0.6)
            if weakest_score >= threshold:
                continue

            if self._is_dimension_exhausted(weakest, history):
                continue

            # source_diversity 偏弱且有可扩展信息源时，优先走 source_expand
            if sections and weakest == "source_diversity" and weakest_score < 0.6:
                expand_section = self._pick_expand_section(sections, history)
                if expand_section:
                    return self._strategy_source_expand(keyword, weakest, weakest_score, expand_section)

            strategy_map = {
                "source_diversity": self._strategy_diversity,
                "perspective": self._strategy_perspective,
                "language": self._strategy_language,
            }

            handler = strategy_map.get(weakest)
            if not handler:
                continue

            strategy = handler(
                keyword=keyword,
                score=weakest_score,
                current_engine=current_engine,
                current_time_range=current_time_range,
                history=history,
                kb_hint=kb_hint,
            )
            if strategy is not None:
                return strategy

        return None

    @staticmethod
    def _is_dimension_exhausted(dimension: str, history: list) -> bool:
        """某维度连续 2 轮被尝试且无效果，视为疲劳"""
        if len(history) < 2:
            return False
        recent = history[-2:]
        matching = sum(1 for h in recent if getattr(h, 'target_dimension', '') == dimension)
        return matching >= 2

    # ============== 知识库提示辅助 ==============

    def _pick_hinted_dimension(self, dimensions: dict, kb_hint: dict) -> str | None:
        recommended_type = kb_hint.get("recommended_strategy_type")
        if not isinstance(recommended_type, str):
            return None
        target_dim = self._TYPE_TO_DIMENSION.get(recommended_type)
        if not target_dim or target_dim not in dimensions:
            return None
        target_score = dimensions[target_dim]
        if target_score >= 0.55:
            return None
        min_score = min(dimensions.values())
        if target_score - min_score > 0.15:
            return None
        return target_dim

    @staticmethod
    def _reorder_engines_by_hint(available: list[str], kb_hint: dict) -> list[str]:
        scores = kb_hint.get("engine_scores", {})
        if not scores:
            return available
        return sorted(available, key=lambda e: scores.get(e, 0.0), reverse=True)

    # ============== 具体策略 ==============

    def _strategy_diversity(
        self, keyword: str, score: float,
        current_engine: str, current_time_range: str,
        history: list[SearchStrategy],
        kb_hint: dict | None = None,
    ) -> SearchStrategy | None:
        used_engines = {h.engine for h in history}
        used_engines.add(current_engine)
        available = [e for e in ENGINE_PRIORITY if e not in used_engines]

        if available:
            if kb_hint:
                available = self._reorder_engines_by_hint(available, kb_hint)
            return SearchStrategy(
                keyword=keyword,
                engine=available[0],
                time_range=current_time_range,
                strategy_type="engine_switch",
                reason=f"来源多样性仅 {score:.0%}，切换到 {available[0]} 引入新来源",
                target_dimension="source_diversity",
            )

        is_cn = detect_cjk(keyword)
        site_targets = (
            ["github.com", "juejin.cn", "zhihu.com", "segmentfault.com", "infoq.cn"]
            if is_cn else
            ["github.com", "medium.com", "dev.to", "stackoverflow.com", "news.ycombinator.com"]
        )
        used_sites = {h.site_scope for h in history if h.site_scope}
        for site in site_targets:
            scope = f"site:{site}"
            if scope not in used_sites:
                return SearchStrategy(
                    keyword=f"{keyword} {scope}",
                    engine=current_engine,
                    time_range=current_time_range,
                    site_scope=scope,
                    strategy_type="site_scope",
                    reason=f"所有引擎已使用，添加 {scope} 引入特定来源",
                    target_dimension="source_diversity",
                )
        return None

    def _strategy_perspective(
        self, keyword: str, score: float,
        current_engine: str, current_time_range: str,
        history: list[SearchStrategy],
        kb_hint: dict | None = None,
    ) -> SearchStrategy | None:
        is_cn = detect_cjk(keyword)
        if is_cn:
            perspective_modifiers = [
                f"{keyword} 缺点 限制",
                f"{keyword} 问题 风险",
                f"{keyword} 踩坑 避坑",
            ]
        else:
            perspective_modifiers = [
                f"{keyword} downsides limitations",
                f"{keyword} problems risks",
                f"{keyword} pitfalls lessons learned",
            ]
        used_keywords = {h.keyword for h in history}
        for mod in perspective_modifiers:
            if mod not in used_keywords:
                return SearchStrategy(
                    keyword=mod,
                    engine=current_engine,
                    time_range=current_time_range,
                    strategy_type="keyword_refine",
                    reason=f"观点均衡仅 {score:.0%}，搜索对立观点",
                    target_dimension="perspective",
                )
        return None

    def _strategy_language(
        self, keyword: str, score: float,
        current_engine: str, current_time_range: str,
        history: list[SearchStrategy],
        kb_hint: dict | None = None,
    ) -> SearchStrategy | None:
        used_types = {h.strategy_type for h in history}
        if "cross_language" in used_types:
            return None
        return SearchStrategy(
            keyword=keyword,
            engine=current_engine,
            time_range=current_time_range,
            strategy_type="cross_language",
            reason=f"语言覆盖仅 {score:.0%}，需补充跨语言搜索",
            target_dimension="language",
        )

    # ============== 广度扩展策略 ==============

    def _pick_expand_section(
        self, sections: list[dict], history: list[SearchStrategy],
    ) -> dict | None:
        used_sections: set[str] = set()
        for h in history:
            if h.strategy_type == "source_expand" and h.source_expand_section:
                used_sections.add(h.source_expand_section.get("name", ""))

        candidates = []
        for section in sections:
            name = section.get("name", "")
            has_url = bool(section.get("url_sources"))
            has_rss = bool(section.get("rss_sources"))
            if (has_url or has_rss) and name not in used_sections:
                candidates.append(section)

        if not candidates:
            fallback = [s for s in sections
                        if s.get("url_sources") or s.get("rss_sources")]
            if not fallback:
                return None
            return random.choice(fallback)

        def _section_score(sec: dict) -> float:
            eff = sec.get("effectiveness", {})
            if eff.get("dead", False):
                return -1.0
            return eff.get("avg_quality", 50.0)

        candidates.sort(key=_section_score, reverse=True)
        return candidates[0]

    def _strategy_source_expand(
        self, keyword: str, dimension: str, score: float, section: dict,
    ) -> SearchStrategy:
        name = section.get("name", "unknown")
        sources = []
        if section.get("url_sources"):
            sources.append(f"{len(section['url_sources'])}个URL")
        if section.get("rss_sources"):
            sources.append(f"{len(section['rss_sources'])}个RSS")

        overrides = self._generate_overrides(section)
        return SearchStrategy(
            keyword=keyword,
            engine="",
            time_range="",
            strategy_type="source_expand",
            reason=f"{dimension}仅{score:.0%}，从板块'{name}'扩展来源（{'+'.join(sources)}）",
            source_expand_section=section,
            source_expand_overrides=overrides,
            target_dimension="source_diversity",
        )

    def _generate_overrides(self, section: dict) -> dict | None:
        eff = section.get("effectiveness", {})
        if eff.get("dead", False):
            return None

        total_runs = eff.get("total_runs", 0)
        if total_runs < 3:
            return None

        overrides = {}
        avg_quality = eff.get("avg_quality", 0)
        success_rate = eff.get("success_rate", 0)

        if avg_quality >= 60 and success_rate >= 0.6:
            overrides["freshness_multiplier"] = 2.0
            overrides["max_items_multiplier"] = 1.5
        elif avg_quality >= 40 and success_rate >= 0.5:
            overrides["freshness_multiplier"] = 1.5

        skip_ids = []
        for src in section.get("url_sources", []) + section.get("rss_sources", []):
            src_eff = src.get("effectiveness", {})
            s = src_eff.get("success_count", 0)
            f = src_eff.get("fail_count", 0)
            t = s + f
            if t >= 3 and s / t < 0.2:
                sid = src.get("source_id")
                if sid is not None:
                    skip_ids.append(sid)
        if skip_ids:
            overrides["skip_source_ids"] = skip_ids

        return overrides if overrides else None


class StrategyGenerator:
    """向后兼容的合并策略生成器 — 合并深度+广度维度（旧行为）"""

    def __init__(self):
        self._depth_gen = DepthStrategyGen()
        self._breadth_gen = BreadthStrategyGen()

    # 策略类型 → 对应维度的映射（合并深度+广度）
    _TYPE_TO_DIMENSION = {
        "engine_switch": "source_diversity",
        "site_scope": "source_diversity",
        "source_expand": "source_diversity",
        "time_adjust": "temporal",
        "cross_language": "language",
    }

    def generate(
        self,
        keyword: str,
        evaluation,
        current_engine: str,
        current_time_range: str,
        round_num: int,
        history: list[SearchStrategy] | None = None,
        kb_hint: dict | None = None,
        sections: list[dict] | None = None,
    ) -> SearchStrategy | None:
        all_dims = {
            "source_diversity": evaluation.source_diversity,
            "temporal": evaluation.temporal_coverage,
            "depth": evaluation.depth_coverage,
            "angle": evaluation.angle_coverage,
            "perspective": evaluation.perspective_balance,
            "language": evaluation.language_coverage,
        }

        weakest = min(all_dims, key=all_dims.get)
        weakest_score = all_dims[weakest]

        # KB hint 维度调整
        if kb_hint and weakest_score < 0.6:
            recommended_type = kb_hint.get("recommended_strategy_type")
            if isinstance(recommended_type, str):
                target_dim = self._TYPE_TO_DIMENSION.get(recommended_type)
                if target_dim and target_dim in all_dims:
                    target_score = all_dims[target_dim]
                    if target_score < 0.55:
                        min_score = min(all_dims.values())
                        if target_score - min_score <= 0.15:
                            weakest = target_dim
                            weakest_score = target_score

        threshold = _DIMENSION_THRESHOLDS.get(weakest, 0.6)
        if weakest_score >= threshold:
            return None

        # 广度维度优先 source_expand
        breadth_dimensions = {"source_diversity", "perspective"}
        if sections and weakest in breadth_dimensions and weakest_score < 0.6:
            expand_section = self._breadth_gen._pick_expand_section(sections, history or [])
            if expand_section:
                return self._breadth_gen._strategy_source_expand(keyword, weakest, weakest_score, expand_section)

        # 按维度归属分发
        depth_dims = {"depth", "angle", "temporal"}
        if weakest in depth_dims:
            return self._depth_gen.generate(
                keyword=keyword, evaluation=evaluation,
                current_engine=current_engine, current_time_range=current_time_range,
                round_num=round_num, history=history,
            )
        else:
            return self._breadth_gen.generate(
                keyword=keyword, evaluation=evaluation,
                current_engine=current_engine, current_time_range=current_time_range,
                round_num=round_num, history=history, kb_hint=kb_hint,
                sections=sections,
            )
