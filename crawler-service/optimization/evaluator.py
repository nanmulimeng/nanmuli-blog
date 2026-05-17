"""覆盖度评估器 — 对搜索结果进行 6 维度评分"""

import json
import logging
import math
import re
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from urllib.parse import urlparse

if TYPE_CHECKING:
    from ai.organizer import ContentOrganizer

logger = logging.getLogger(__name__)

# ============== 数据结构 ==============

@dataclass
class CoverageEvaluation:
    angle_coverage: float = 0.0
    source_diversity: float = 0.0
    depth_coverage: float = 0.0
    temporal_coverage: float = 0.0
    perspective_balance: float = 0.0
    language_coverage: float = 0.0
    overall_score: float = 0.0
    weaknesses: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    tokens_used: int = 0
    duration_ms: int = 0


# ============== 维度权重 ==============

def _get_weights() -> dict:
    """Read evaluation weights from unified settings."""
    from config import settings
    return {
        "angle": settings.eval_weight_angle,
        "source_diversity": settings.eval_weight_source,
        "depth": settings.eval_weight_depth,
        "temporal": settings.eval_weight_temporal,
        "perspective": settings.eval_weight_perspective,
        "language": settings.eval_weight_language,
    }


# ============== AI Prompt ==============

EVALUATOR_SYSTEM_PROMPT = """你是一位技术信息覆盖度分析专家。
任务：根据搜索关键词和搜索结果的来源信息，评估搜索覆盖的完整性和质量。

## 评估维度

### 1. 角度覆盖（angle）
搜索结果是否覆盖了该技术主题的多个方面？
- 全面(0.8-1.0)：覆盖原理、实践、对比、趋势中的 3+ 个
- 一般(0.4-0.7)：覆盖 2 个方面
- 单一(0.0-0.3)：仅覆盖 1 个方面

### 2. 深度覆盖（depth）
搜索结果是否同时包含浅层介绍和深度分析？
- 全面(0.8-1.0)：有入门级也有专家级内容
- 一般(0.4-0.7)：以中等深度为主
- 单一(0.0-0.3)：全是浅层或全是极端深度

### 3. 时效性覆盖（temporal）
搜索结果是否包含不同时间阶段的内容？
- 全面(0.8-1.0)：有最新动态也有历史背景
- 一般(0.4-0.7)：以近期为主
- 单一(0.0-0.3)：全是同一时间段

### 4. 观点均衡（perspective）
搜索结果是否呈现了不同观点/立场？
- 全面(0.8-1.0)：有利有弊、有赞有弹
- 一般(0.4-0.7)：略有不同角度
- 单一(0.0-0.3)：全是正面或全是负面

## 输出格式（严格 JSON）
{"angle": 0.0-1.0, "depth": 0.0-1.0, "temporal": 0.0-1.0, "perspective": 0.0-1.0, "weaknesses": [...], "suggestions": [...]}

## 示例

关键词="Kubernetes"，2 条来自同一域名、内容浅层的介绍
{"angle": 0.2, "depth": 0.1, "temporal": 0.3, "perspective": 0.2, "weaknesses": ["仅覆盖基础概念", "内容浅层无深度分析"], "suggestions": ["搜索 Kubernetes 架构对比", "添加 site:kubernetes.io"]}

关键词="React hooks"，5 条来自 4 个域名，含入门教程和高级模式文章
{"angle": 0.7, "depth": 0.7, "temporal": 0.5, "perspective": 0.6, "weaknesses": ["缺少历史背景"], "suggestions": ["扩展时间范围到 month"]}

注意：利用"内容预览"列判断深度（入门 vs 专家级）、角度（教程 vs 对比）和观点（正面 vs 反面）。

规则：
1. 只输出 JSON，不要包裹在 markdown 代码块中
2. weaknesses 和 suggestions 各最多 3 条
3. suggestions 必须具体可操作（如"添加 site:docs.spring.io 限定词补充官方文档"）
4. 如果结果少于 3 条，直接给出低分，suggestions 指出补充方向"""

JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*\n?([\s\S]*?)```")

# 评估输出是简单 JSON，无需大量 token
_EVALUATOR_MAX_TOKENS = 600


# ============== 评估器 ==============

class CoverageEvaluator:
    """覆盖度评估器"""

    def __init__(self, organizer: "ContentOrganizer | None" = None):
        self._organizer = organizer

    @property
    def is_available(self) -> bool:
        return self._organizer is not None and self._organizer.is_available

    async def evaluate(
        self,
        keyword: str,
        results: list,
        context: dict | None = None,
    ) -> CoverageEvaluation:
        start = time.monotonic()
        ctx = context or {}

        # 提取搜索结果元数据
        meta = self._extract_result_meta(results)

        # 纯计算维度
        source_diversity = self._calc_shannon_entropy(meta["domains"])
        language_coverage = self._calc_language_mix(meta["titles"])

        # AI 评估维度
        ai_eval = {"angle": 0.5, "depth": 0.5, "temporal": 0.5, "perspective": 0.5,
                   "weaknesses": [], "suggestions": []}
        tokens_used = 0

        if self.is_available and len(meta["entries"]) >= 1:
            ai_eval, tokens_used = await self._ai_evaluate(keyword, meta, ctx)
        else:
            if not self.is_available:
                logger.info("[Evaluator] AI not available, using heuristic scores")
            ai_eval = self._heuristic_evaluate(meta, ctx)

        # 加权综合评分
        weights = _get_weights()
        overall = (
            weights["angle"] * ai_eval["angle"]
            + weights["source_diversity"] * source_diversity
            + weights["depth"] * ai_eval["depth"]
            + weights["temporal"] * ai_eval["temporal"]
            + weights["perspective"] * ai_eval["perspective"]
            + weights["language"] * language_coverage
        )

        evaluation = CoverageEvaluation(
            angle_coverage=round(ai_eval["angle"], 3),
            source_diversity=round(source_diversity, 3),
            depth_coverage=round(ai_eval["depth"], 3),
            temporal_coverage=round(ai_eval["temporal"], 3),
            perspective_balance=round(ai_eval["perspective"], 3),
            language_coverage=round(language_coverage, 3),
            overall_score=round(overall, 3),
            weaknesses=ai_eval.get("weaknesses", []),
            suggestions=ai_eval.get("suggestions", []),
            tokens_used=tokens_used,
            duration_ms=int((time.monotonic() - start) * 1000),
        )

        logger.info(
            "[Evaluator] keyword='%s' overall=%.2f angle=%.2f diversity=%.2f depth=%.2f "
            "temporal=%.2f perspective=%.2f language=%.2f (%dms)",
            keyword, evaluation.overall_score, evaluation.angle_coverage,
            evaluation.source_diversity, evaluation.depth_coverage,
            evaluation.temporal_coverage, evaluation.perspective_balance,
            evaluation.language_coverage, evaluation.duration_ms,
        )
        return evaluation

    # ============== 元数据提取 ==============

    def _extract_result_meta(self, results: list) -> dict:
        entries = []
        domains = []
        titles = []
        total_content_len = 0

        for r in results:
            rdict = r.to_dict() if hasattr(r, "to_dict") else (r if isinstance(r, dict) else {})
            success = rdict.get("success", False)
            url = rdict.get("url", "")
            title = rdict.get("title", "") or ""
            markdown = rdict.get("markdown", "") or ""
            metadata = rdict.get("metadata", {}) or {}

            if not success:
                continue

            domain = ""
            try:
                parsed = urlparse(url)
                domain = parsed.netloc.lower()
                if domain.startswith("www."):
                    domain = domain[4:]
            except Exception:
                pass

            entries.append({
                "url": url,
                "title": title,
                "domain": domain,
                "content_length": len(markdown),
                "engine": metadata.get("search_engine", ""),
                "search_rank": metadata.get("search_rank", 0),
                "content_preview": markdown[:200].strip() if markdown else "",
            })
            domains.append(domain)
            titles.append(title)
            total_content_len += len(markdown)

        return {
            "entries": entries,
            "domains": domains,
            "titles": titles,
            "total": len(entries),
            "total_content_length": total_content_len,
        }

    # ============== 纯计算维度 ==============

    @staticmethod
    def _calc_shannon_entropy(domains: list[str]) -> float:
        if not domains:
            return 0.0
        freq = Counter(domains)
        total = len(domains)
        entropy = -sum((c / total) * math.log2(c / total) for c in freq.values())
        max_entropy = math.log2(total) if total > 1 else 1.0
        if max_entropy <= 0:
            return 0.0
        # 样本量校正：unique_domains < 5 时按比例打折，避免少样本高分
        sample_penalty = min(1.0, len(freq) / 5)
        return min(1.0, (entropy / max_entropy) * sample_penalty)

    @staticmethod
    def _calc_language_mix(titles: list[str]) -> float:
        if not titles:
            return 0.0
        has_chinese = 0
        has_english = 0
        for title in titles:
            if re.search(r"[一-鿿]", title):
                has_chinese += 1
            if re.search(r"[a-zA-Z]{3,}", title):
                has_english += 1
        total = len(titles)
        chinese_ratio = has_chinese / total
        english_ratio = has_english / total

        if chinese_ratio > 0.1 and english_ratio > 0.1:
            # 调和平均：中英比例越均衡分越高
            harmonic = 2 * chinese_ratio * english_ratio / (chinese_ratio + english_ratio)
            return round(min(1.0, harmonic * 1.4), 3)
        if chinese_ratio > 0.1 or english_ratio > 0.1:
            # 单语言：少量结果 → 0.3，大量结果 → 0.45
            base = 0.3 + 0.15 * min(1.0, total / 10)
            return round(base, 3)
        return 0.0

    # ============== AI 评估 ==============

    async def _ai_evaluate(self, keyword: str, meta: dict, ctx: dict) -> tuple[dict, int]:
        from ai.organizer import _extract_json

        user_prompt = self._build_eval_prompt(keyword, meta, ctx)
        try:
            response = await self._organizer._call_ai(
                EVALUATOR_SYSTEM_PROMPT, user_prompt, max_tokens=_EVALUATOR_MAX_TOKENS
            )
            content = response.get("content", "")
            tokens = response.get("total_tokens", 0)

            raw = json.loads(_extract_json(content))
            return {
                "angle": min(1.0, max(0.0, float(raw.get("angle", 0.5)))),
                "depth": min(1.0, max(0.0, float(raw.get("depth", 0.5)))),
                "temporal": min(1.0, max(0.0, float(raw.get("temporal", 0.5)))),
                "perspective": min(1.0, max(0.0, float(raw.get("perspective", 0.5)))),
                "weaknesses": [str(w) for w in raw.get("weaknesses", [])][:3],
                "suggestions": [str(s) for s in raw.get("suggestions", [])][:3],
            }, tokens
        except Exception as e:
            logger.warning("[Evaluator] AI evaluation failed, falling back to heuristic: %s", e)
            return self._heuristic_evaluate(meta, ctx), 0

    def _build_eval_prompt(self, keyword: str, meta: dict, ctx: dict) -> str:
        engine = ctx.get("engine", "unknown")
        time_range = ctx.get("time_range", "unknown")
        entries = meta["entries"]

        lines = [
            f"## 搜索关键词\n{keyword}\n",
            f"## 搜索上下文\n- 搜索引擎: {engine}\n- 时间过滤: {time_range}",
            f"- 结果数量: {meta['total']} 条\n",
            "## 搜索结果来源\n",
        ]
        if entries:
            lines.append("| # | 标题 | 来源域名 | 长度 | 内容预览 |")
            lines.append("|---|------|---------|------|---------|")
            for i, e in enumerate(entries, 1):
                title_display = (e["title"][:40] + "...") if len(e["title"]) > 40 else e["title"]
                title_display = title_display.replace("|", "\\|")
                preview = e.get("content_preview", "")
                preview_display = (preview[:80] + "...") if len(preview) > 80 else preview
                preview_display = preview_display.replace("|", "\\|")
                lines.append(f"| {i} | {title_display} | {e['domain']} | {e['content_length']}字 | {preview_display} |")
        else:
            lines.append("（无搜索结果）")

        lines.append("\n请评估以上搜索结果的覆盖度。")
        return "\n".join(lines)

    # ============== 启发式回退 ==============

    def _heuristic_evaluate(self, meta: dict, ctx: dict) -> dict:
        """AI 不可用时的启发式评估"""
        total = meta["total"]
        domains = set(meta["domains"])
        entries = meta["entries"]

        # 角度覆盖：基于不同域名数（越多越可能覆盖多角度）
        angle = min(1.0, len(domains) / 5) if total >= 3 else min(1.0, total / 3)

        # 深度覆盖：基于内容长度分布
        if entries:
            lengths = [e["content_length"] for e in entries]
            avg_len = sum(lengths) / len(lengths)
            has_short = any(l < 500 for l in lengths)
            has_long = any(l > 3000 for l in lengths)
            depth = 0.3 + (0.3 if has_short else 0) + (0.4 if has_long else 0) + min(0.15, avg_len / 10000)
        else:
            depth = 0.1

        # 时效性覆盖：结果数量 × 域名多样性修正（AI 不可用时的代理指标）
        domain_count = len(domains)
        domain_factor = min(1.0, domain_count / 4) if domain_count >= 2 else 0.3
        count_factor = min(1.0, total / 6) if total >= 2 else 0.2
        temporal = round(count_factor * 0.6 + domain_factor * 0.4, 3)

        # 观点均衡：域名多样性 50% + 标题对立词检测 50%
        domain_component = min(1.0, len(domains) / 3) if len(domains) >= 2 else 0.2
        positive_words = {"推荐", "最佳", "优秀", "优点", "亮点", "best", "great", "awesome", "recommended"}
        negative_words = {"缺点", "问题", "踩坑", "避坑", "风险", "限制", "downside", "issue", "problem", "limitation"}
        title_words = set()
        for t in meta["titles"]:
            title_words.update(w.lower() for w in re.findall(r'[一-鿿a-zA-Z]+', t))
        has_pos = bool(title_words & positive_words)
        has_neg = bool(title_words & negative_words)
        if has_pos and has_neg:
            keyword_component = 0.8
        elif has_pos or has_neg:
            keyword_component = 0.4
        else:
            keyword_component = 0.2
        perspective = round(domain_component * 0.5 + keyword_component * 0.5, 3)

        weaknesses = []
        suggestions = []
        if total < 3:
            weaknesses.append("搜索结果数量不足")
            suggestions.append("尝试扩展关键词或切换搜索引擎")
        if len(domains) < 3 and total >= 3:
            weaknesses.append("来源域名过于集中")
            suggestions.append("切换搜索引擎引入不同来源")

        return {
            "angle": round(min(1.0, angle), 3),
            "depth": round(min(1.0, depth), 3),
            "temporal": round(min(1.0, temporal), 3),
            "perspective": round(min(1.0, perspective), 3),
            "weaknesses": weaknesses,
            "suggestions": suggestions,
        }
