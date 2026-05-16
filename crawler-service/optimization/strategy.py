"""策略生成器 — 根据覆盖度评估短板生成改进搜索策略（纯规则，无 AI）"""

import logging
from dataclasses import dataclass

from crawler.utils import detect_cjk

logger = logging.getLogger(__name__)

# 搜索引擎优先级（与 crawler/search.py 一致）
ENGINE_PRIORITY = ["bing", "baidu", "sogou", "google"]


@dataclass
class SearchStrategy:
    keyword: str
    engine: str
    time_range: str
    site_scope: str | None = None
    strategy_type: str = "initial"
    reason: str = ""


class StrategyGenerator:
    """策略生成器（纯规则映射）"""

    def generate(
        self,
        keyword: str,
        evaluation,
        current_engine: str,
        current_time_range: str,
        round_num: int,
        history: list[SearchStrategy] | None = None,
        kb_hint: dict | None = None,
    ) -> SearchStrategy | None:
        dimensions = {
            "source_diversity": evaluation.source_diversity,
            "temporal": evaluation.temporal_coverage,
            "depth": evaluation.depth_coverage,
            "angle": evaluation.angle_coverage,
            "perspective": evaluation.perspective_balance,
            "language": evaluation.language_coverage,
        }

        weakest = min(dimensions, key=dimensions.get)
        weakest_score = dimensions[weakest]

        # 知识库提示：优先选择历史有效策略对应的维度
        if kb_hint and weakest_score < 0.6:
            alt = self._pick_hinted_dimension(dimensions, kb_hint)
            if alt:
                weakest = alt
                weakest_score = dimensions[weakest]

        if weakest_score >= 0.6:
            return None

        strategy_map = {
            "source_diversity": self._strategy_diversity,
            "temporal": self._strategy_temporal,
            "depth": self._strategy_depth,
            "angle": self._strategy_angle,
            "perspective": self._strategy_perspective,
            "language": self._strategy_language,
        }

        handler = strategy_map.get(weakest)
        if not handler:
            return None

        history = history or []
        return handler(
            keyword=keyword,
            score=weakest_score,
            current_engine=current_engine,
            current_time_range=current_time_range,
            history=history,
            kb_hint=kb_hint,
        )

    # ============== 知识库提示辅助 ==============

    # 策略类型 → 对应维度的映射
    _TYPE_TO_DIMENSION = {
        "engine_switch": "source_diversity",
        "site_scope": "source_diversity",
        "time_adjust": "temporal",
        "cross_language": "language",
    }

    def _pick_hinted_dimension(self, dimensions: dict, kb_hint: dict) -> str | None:
        """当推荐策略类型对应维度也偏弱时，优先选择推荐维度"""
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
        """按历史引擎效能重排可用引擎列表"""
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
                )
        return None

    def _strategy_temporal(
        self, keyword: str, score: float,
        current_engine: str, current_time_range: str,
        history: list[SearchStrategy],
        kb_hint: dict | None = None,
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
            )
        return None

    def _strategy_depth(
        self, keyword: str, score: float,
        current_engine: str, current_time_range: str,
        history: list[SearchStrategy],
        kb_hint: dict | None = None,
    ) -> SearchStrategy | None:
        is_cn = detect_cjk(keyword)
        depth_modifiers = (
            ["原理 源码分析", "内部实现 实战", "深入理解 底层原理", "源码解读 实现细节"]
            if is_cn else
            ["architecture deep dive", "internals implementation", "how it works under the hood", "in-depth tutorial"]
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
                )
        return None

    def _strategy_angle(
        self, keyword: str, score: float,
        current_engine: str, current_time_range: str,
        history: list[SearchStrategy],
        kb_hint: dict | None = None,
    ) -> SearchStrategy | None:
        is_cn = detect_cjk(keyword)
        if is_cn:
            angle_variants = [
                f"{keyword} 对比 评测",
                f"{keyword} 最佳实践",
                f"{keyword} 性能优化",
                f"{keyword} 常见问题 解决方案",
            ]
        else:
            angle_variants = [
                f"{keyword} comparison vs alternatives",
                f"{keyword} best practices",
                f"{keyword} performance optimization",
                f"{keyword} common issues troubleshooting",
            ]
        used_keywords = {h.keyword for h in history}
        for variant in angle_variants:
            if variant not in used_keywords:
                return SearchStrategy(
                    keyword=variant,
                    engine=current_engine,
                    time_range=current_time_range,
                    strategy_type="keyword_refine",
                    reason=f"角度覆盖仅 {score:.0%}，搜索角度变体",
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
                )
        return None

    def _strategy_language(
        self, keyword: str, score: float,
        current_engine: str, current_time_range: str,
        history: list[SearchStrategy],
        kb_hint: dict | None = None,
    ) -> SearchStrategy | None:
        """跨语言扩展策略 — 翻译关键词为英文补充搜索"""
        used_types = {h.strategy_type for h in history}
        if "cross_language" in used_types:
            return None
        return SearchStrategy(
            keyword=keyword,
            engine=current_engine,
            time_range=current_time_range,
            strategy_type="cross_language",
            reason=f"语言覆盖仅 {score:.0%}，需补充跨语言搜索",
        )
