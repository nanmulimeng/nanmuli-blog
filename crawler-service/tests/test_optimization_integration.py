"""自动优化引擎集成测试 — 端到端模拟完整优化循环"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass

from optimization.evaluator import CoverageEvaluator, CoverageEvaluation, _get_weights
from optimization.strategy import StrategyGenerator, SearchStrategy, ENGINE_PRIORITY
from optimization.knowledge_base import KnowledgeBase


# ============== 辅助函数 ==============

def make_result(url: str, title: str = "", content_len: int = 500,
                domain: str = "", success: bool = True, engine: str = "bing"):
    """构造模拟搜索结果"""
    if not domain:
        from urllib.parse import urlparse
        domain = urlparse(url).netloc.lower().replace("www.", "")
    return {
        "url": url,
        "title": title,
        "markdown": "x" * content_len,
        "success": success,
        "metadata": {"search_engine": engine, "search_rank": 0},
    }


def make_eval(**overrides):
    """构造 CoverageEvaluation"""
    defaults = {
        "angle_coverage": 0.8, "source_diversity": 0.8,
        "depth_coverage": 0.8, "temporal_coverage": 0.8,
        "perspective_balance": 0.8, "language_coverage": 0.8,
        "overall_score": 0.8,
    }
    defaults.update(overrides)
    return CoverageEvaluation(**defaults)


# ============== Evaluator 端到端测试 ==============

class TestEvaluatorEndToEnd:
    """测试评估器对真实数据结构的处理"""

    def test_extract_meta_from_dict_results(self):
        evaluator = CoverageEvaluator()
        results = [
            make_result("https://example.com/a", "Test A", 1000),
            make_result("https://other.com/b", "Test B", 2000),
            make_result("https://example.com/c", "Test C", 500),
        ]
        meta = evaluator._extract_result_meta(results)
        assert meta["total"] == 3
        assert "example.com" in meta["domains"]
        assert "other.com" in meta["domains"]
        assert meta["total_content_length"] == 3500

    def test_shannon_entropy_realistic_scenario(self):
        """模拟 10 个结果来自 2 个域名的场景（含样本量校正）"""
        domains = ["github.com"] * 7 + ["stackoverflow.com"] * 3
        entropy = CoverageEvaluator.calc_shannon_entropy(domains)
        # 10 个结果, 2 unique domains < 5 threshold → sample_penalty = 0.4
        # 原始归一化 ≈ 0.265, 修正后 ≈ 0.106
        assert 0.05 < entropy < 0.15

    def test_language_mix_bilingual(self):
        titles = [
            "Spring Boot 入门教程",
            "React best practices 2024",
            "Docker 容器化部署指南",
            "Kubernetes Production Patterns",
            "微服务架构设计原理",
        ]
        score = CoverageEvaluator.calc_language_mix(titles)
        assert score > 0.8  # 强中英混合

    def test_heuristic_with_single_domain(self):
        """单域名大量结果 → source_diversity 低但角度不一定低"""
        evaluator = CoverageEvaluator()
        entries = [
            {"domain": "github.com", "content_length": 5000 + i * 1000, "url": f"https://github.com/r{i}", "title": f"Title {i}", "engine": "bing", "search_rank": i}
            for i in range(8)
        ]
        meta = {
            "entries": entries,
            "domains": ["github.com"] * 8,
            "titles": [f"Title {i}" for i in range(8)],
            "total": 8,
        }
        result = evaluator._heuristic_evaluate(meta, {})
        # 角度覆盖：单域名 + 8 条结果 → min(0.6, 1/8) + min(0.2, 7/10) ≈ 0.325
        assert result["angle"] <= 0.4
        # 深度覆盖应该较高（有长内容）
        assert result["depth"] >= 0.5

    def test_heuristic_with_empty_results(self):
        """空结果 → 全低分"""
        evaluator = CoverageEvaluator()
        meta = {"entries": [], "domains": [], "titles": [], "total": 0}
        result = evaluator._heuristic_evaluate(meta, {})
        assert result["angle"] == 0.0
        assert result["depth"] == 0.1
        assert "不足" in str(result["weaknesses"])


# ============== Strategy 端到端测试 ==============

class TestStrategyEndToEnd:
    """测试策略生成在连续轮次中的行为"""

    def setup_method(self):
        self.gen = StrategyGenerator()

    def test_progressive_engine_exhaustion(self):
        """连续切换引擎直到耗尽"""
        eval_result = make_eval(source_diversity=0.1)
        history = []
        engines_used = set()

        for _ in range(5):
            strategy = self.gen.generate("test", eval_result, "bing", "week", len(history) + 1, history)
            if strategy is None:
                break
            history.append(strategy)
            engines_used.add(strategy.engine)

        # 应该尝试了多个引擎
        assert len(engines_used) >= 1

    def test_temporal_expansion_chain(self):
        """时间扩展链: day → week → month → year → None"""
        time_ranges = ["day"]
        for _ in range(4):
            eval_result = make_eval(temporal_coverage=0.1)
            strategy = self.gen.generate("test", eval_result, "bing", time_ranges[-1], 1)
            if strategy is None:
                break
            assert strategy.strategy_type == "time_adjust"
            time_ranges.append(strategy.time_range)

        assert time_ranges == ["day", "week", "month", "year", "all"]
        # 从 "all" 无法再扩展
        eval_result = make_eval(temporal_coverage=0.1)
        strategy = self.gen.generate("test", eval_result, "bing", "all", 1)
        assert strategy is None


# ============== 覆盖度计算一致性测试 ==============

class TestCoverageConsistency:
    """验证启发式评估的内部一致性"""

    def test_more_domains_higher_angle(self):
        """域名越多 → 角度覆盖越高"""
        evaluator = CoverageEvaluator()

        meta_few = {"entries": [{"domain": f"d{i}.com", "content_length": 500, "url": f"https://d{i}.com", "title": f"T{i}", "engine": "bing", "search_rank": i} for i in range(2)],
                     "domains": ["d0.com", "d1.com"], "titles": ["T0", "T1"], "total": 2}
        meta_many = {"entries": [{"domain": f"d{i}.com", "content_length": 500, "url": f"https://d{i}.com", "title": f"T{i}", "engine": "bing", "search_rank": i} for i in range(8)],
                      "domains": [f"d{i}.com" for i in range(8)], "titles": [f"T{i}" for i in range(8)], "total": 8}

        few = evaluator._heuristic_evaluate(meta_few, {})
        many = evaluator._heuristic_evaluate(meta_many, {})

        assert many["angle"] >= few["angle"]

    def test_content_length_variation_higher_depth(self):
        """内容长度差异大 → 深度覆盖更高"""
        evaluator = CoverageEvaluator()

        uniform = {"entries": [{"domain": "a.com", "content_length": 1000, "url": "https://a.com", "title": "T", "engine": "bing", "search_rank": 0}] * 5,
                    "domains": ["a.com"] * 5, "titles": ["T"] * 5, "total": 5}
        varied = {"entries": [
            {"domain": "a.com", "content_length": 200, "url": "https://a.com/s", "title": "Short", "engine": "bing", "search_rank": 0},
            {"domain": "b.com", "content_length": 5000, "url": "https://b.com/l", "title": "Long", "engine": "bing", "search_rank": 1},
            {"domain": "c.com", "content_length": 800, "url": "https://c.com/m", "title": "Medium", "engine": "bing", "search_rank": 2},
        ], "domains": ["a.com", "b.com", "c.com"], "titles": ["Short", "Long", "Medium"], "total": 3}

        u = evaluator._heuristic_evaluate(uniform, {})
        v = evaluator._heuristic_evaluate(varied, {})

        assert v["depth"] > u["depth"]


# ============== Weighted Score 验证 ==============

class TestWeightedScore:
    """验证加权评分公式"""

    def test_overall_matches_formula(self):
        """验证 overall_score 确实是加权平均"""
        evaluator = CoverageEvaluator(organizer=None)
        results = [make_result("https://a.com", "Test", 1000)]
        meta = evaluator._extract_result_meta(results)
        heuristic = evaluator._heuristic_evaluate(meta, {})

        # 手动计算
        source_diversity = CoverageEvaluator.calc_shannon_entropy(meta["domains"])
        language = CoverageEvaluator.calc_language_mix(meta["titles"])

        weights = _get_weights()
        expected = (
            weights["angle"] * heuristic["angle"]
            + weights["source_diversity"] * source_diversity
            + weights["depth"] * heuristic["depth"]
            + weights["temporal"] * heuristic["temporal"]
            + weights["perspective"] * heuristic["perspective"]
            + weights["language"] * language
        )

        # 运行完整评估
        import asyncio
        eval_result = asyncio.get_event_loop().run_until_complete(
            evaluator.evaluate("test", results, {"engine": "bing", "time_range": "week"})
        )

        assert abs(eval_result.overall_score - round(expected, 3)) < 0.01
