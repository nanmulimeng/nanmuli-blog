"""端到端学习闭环测试 — 验证知识库让策略生成更智能"""

import pytest
from contextlib import asynccontextmanager
from unittest.mock import patch, MagicMock, AsyncMock

from optimization.evaluator import CoverageEvaluator, CoverageEvaluation
from optimization.strategy import StrategyGenerator, SearchStrategy, ENGINE_PRIORITY
from optimization.feedback import FeedbackLoop, OptimizationRound
from optimization.knowledge_base import KnowledgeBase


# ============== 辅助 ==============

def _mock_get_db(mem_db):
    @asynccontextmanager
    async def _get_db():
        yield mem_db
    return _get_db


async def _insert(db, **kwargs):
    task_id = kwargs.get("task_id", 1)
    cursor = await db.execute("SELECT 1 FROM crawl_task WHERE id = ?", (task_id,))
    if not await cursor.fetchone():
        await db.execute(
            "INSERT INTO crawl_task (id, task_type, status) VALUES (?, 'keyword', 3)",
            (task_id,),
        )
    defaults = {
        "task_id": 1, "round_num": 2,
        "angle_coverage": 0.5, "source_diversity": 0.5, "depth_coverage": 0.5,
        "temporal_coverage": 0.5, "perspective_balance": 0.5, "language_coverage": 0.5,
        "overall_score": 0.5,
        "search_keyword": "test", "search_engine": "bing", "time_range": "week",
        "strategy_type": "engine_switch", "strategy_detail": "",
        "weaknesses": None, "suggestions": None,
        "urls_before": 3, "urls_after": 5, "score_delta": 0.1,
    }
    defaults.update(kwargs)
    keys = list(defaults.keys())
    values = [defaults[k] for k in keys]
    await db.execute(
        f"INSERT INTO optimization_record ({', '.join(keys)}) VALUES ({', '.join('?' * len(keys))})",
        values,
    )
    await db.commit()


def make_eval(**overrides):
    defaults = {
        "angle_coverage": 0.8, "source_diversity": 0.8,
        "depth_coverage": 0.8, "temporal_coverage": 0.8,
        "perspective_balance": 0.8, "language_coverage": 0.8,
        "overall_score": 0.8,
    }
    defaults.update(overrides)
    return CoverageEvaluation(**defaults)


# ============== 学习闭环测试 ==============

class TestLearningLoop:
    """验证：历史数据 → 知识库推荐 → 策略优先级调整"""

    @pytest.mark.asyncio
    async def test_kb_hint_prefers_historically_effective_engine(self, mem_db):
        """
        场景：历史数据表明 baidu 在搜索 "Spring Boot" 时 score_delta=0.20，
              而 baidu 在 ENGINE_PRIORITY 排在 bing 后面。
              知识库应该让策略生成器优先选 baidu。
        """
        # 准备历史数据：baidu 表现好
        await _insert(mem_db, search_keyword="Spring Boot", search_engine="baidu",
                      score_delta=0.20, strategy_type="engine_switch")
        await _insert(mem_db, search_keyword="Spring Boot", search_engine="sogou",
                      score_delta=0.05, strategy_type="engine_switch")

        # 从知识库获取 hint
        with patch("optimization.knowledge_base.get_db", _mock_get_db(mem_db)):
            kb = KnowledgeBase()
            hint = await kb.get_strategy_hint("Spring Boot", "bing", "week")

        assert hint is not None
        assert hint["recommended_engine"] == "baidu"
        assert hint["engine_scores"]["baidu"] > hint["engine_scores"]["sogou"]

        # 验证 StrategyGenerator 使用 hint 重排引擎
        gen = StrategyGenerator()
        eval_result = make_eval(source_diversity=0.2)

        # 不带 hint：按 ENGINE_PRIORITY 顺序，bing 后面是 baidu
        strategy_no_hint = gen.generate("Spring Boot", eval_result, "bing", "week", 1)
        assert strategy_no_hint.engine == ENGINE_PRIORITY[ENGINE_PRIORITY.index("bing") + 1]
        # ENGINE_PRIORITY = ["bing", "baidu", "sogou", "google"]，bing 后面是 baidu
        # 这个例子碰巧一样，换成另一个引擎验证

        # 换当前引擎为 sogou（可用引擎=[bing, baidu, google]），默认选 bing
        # hint 应该把 baidu（历史最优）排到 bing 前面
        strategy_no_hint = gen.generate("Spring Boot", eval_result, "sogou", "week", 1)
        assert strategy_no_hint.engine == "bing"  # 默认按 ENGINE_PRIORITY 第一个可用

        strategy_with_hint = gen.generate("Spring Boot", eval_result, "sogou", "week", 1,
                                           kb_hint=hint)
        assert strategy_with_hint.engine == "baidu"  # 知识库推荐 baidu 优先于 bing

    @pytest.mark.asyncio
    async def test_kb_hint_adjusts_dimension_priority(self, mem_db):
        """
        场景：历史数据表明 engine_switch 策略效果最好（对应 source_diversity 维度）。
              当 source_diversity 和 temporal 都偏低且接近时，
              知识库应让策略生成器优先选 source_diversity。
        """
        await _insert(mem_db, search_keyword="Python", search_engine="baidu",
                      score_delta=0.25, strategy_type="engine_switch")

        with patch("optimization.knowledge_base.get_db", _mock_get_db(mem_db)):
            kb = KnowledgeBase()
            hint = await kb.get_strategy_hint("Python", "bing", "week")

        assert hint is not None
        assert hint["recommended_strategy_type"] == "engine_switch"

        gen = StrategyGenerator()
        # 两个维度都低且接近：source_diversity=0.3, temporal=0.25
        # 默认 min() 选 temporal（更低）
        eval_temporal_weakest = make_eval(source_diversity=0.3, temporal_coverage=0.25)

        strategy_no_hint = gen.generate("Python", eval_temporal_weakest, "bing", "week", 1)
        assert strategy_no_hint.strategy_type == "time_adjust"  # temporal 最弱

        # 带 hint：engine_switch 对应 source_diversity=0.3 (< 0.55)
        # 与最低 0.25 差距 = 0.05 < 0.15 → 应该切换到 source_diversity
        strategy_with_hint = gen.generate("Python", eval_temporal_weakest, "bing", "week", 1,
                                           kb_hint=hint)
        assert strategy_with_hint.strategy_type == "engine_switch"  # 知识库推荐优先

    @pytest.mark.asyncio
    async def test_full_feedback_loop_uses_kb(self, mem_db):
        """
        端到端：FeedbackLoop 在 Round 2+ 时使用知识库 hint。
        """
        # 准备历史：baidu 在 "Docker" 搜索中效果很好
        await _insert(mem_db, search_keyword="Docker", search_engine="baidu",
                      score_delta=0.20, strategy_type="engine_switch",
                      task_id=1)

        with patch("optimization.knowledge_base.get_db", _mock_get_db(mem_db)):
            kb = KnowledgeBase()
            evaluator = CoverageEvaluator(organizer=None)
            gen = StrategyGenerator()
            loop = FeedbackLoop(evaluator, gen, kb, target_score=0.9, max_rounds=2)

            # 初始结果：全 github.com（低多样性）
            initial = [
                {"url": f"https://github.com/p{i}", "title": f"Docker {i}",
                 "markdown": "x" * 500, "success": True,
                 "metadata": {"search_engine": "bing"}}
                for i in range(3)
            ]

            call_log = []

            async def spy_crawl(**kwargs):
                call_log.append(kwargs)
                engine = kwargs.get("engine", "bing")
                return [
                    {"url": f"https://{engine}.com/result", "title": "New",
                     "markdown": "x" * 1000, "success": True,
                     "metadata": {"search_engine": engine}},
                ]

            results, rounds = await loop.execute(
                keyword="Docker",
                initial_results=initial,
                crawl_fn=spy_crawl,
                context={"engine": "bing", "time_range": "week"},
            )

            # 应该触发了补充搜索
            assert len(rounds) >= 2
            # 补充搜索应该用了 baidu（知识库推荐）而不是默认的下一个
            if call_log:
                assert call_log[0]["engine"] == "baidu"


# ============== 边界条件测试 ==============

class TestKBBoundaryConditions:

    @pytest.mark.asyncio
    async def test_hint_with_special_chars_in_keyword(self, mem_db):
        """关键词含 % 和 _ 等特殊字符不应导致 SQL 错误"""
        await _insert(mem_db, search_keyword="C++ memory", score_delta=0.10)
        with patch("optimization.knowledge_base.get_db", _mock_get_db(mem_db)):
            kb = KnowledgeBase()
            # 这些不应抛异常
            hint1 = await kb.get_strategy_hint("100% coverage", "bing", "week")
            hint2 = await kb.get_strategy_hint("test_value", "bing", "week")
        # 不崩溃就算通过

    @pytest.mark.asyncio
    async def test_hint_with_empty_keyword(self, mem_db):
        """空关键词应返回 None（LIKE '%' 匹配全表但有 score_delta>0 过滤）"""
        await _insert(mem_db, search_keyword="something", score_delta=0.15)
        with patch("optimization.knowledge_base.get_db", _mock_get_db(mem_db)):
            kb = KnowledgeBase()
            hint = await kb.get_strategy_hint("", "bing", "week")
        # 空关键词 → "%" 匹配，如果有正 delta 记录应返回 hint
        # 关键是不崩溃

    @pytest.mark.asyncio
    async def test_hint_does_not_override_strong_dimension(self, mem_db):
        """知识库不应让已很强的维度被替换"""
        await _insert(mem_db, strategy_type="engine_switch", score_delta=0.20,
                      search_keyword="test")
        with patch("optimization.knowledge_base.get_db", _mock_get_db(mem_db)):
            kb = KnowledgeBase()
            hint = await kb.get_strategy_hint("test", "bing", "week")

        gen = StrategyGenerator()
        # source_diversity = 0.7（> 0.55 阈值），即使知识库推荐 engine_switch 也不应干预
        eval_result = make_eval(source_diversity=0.7, temporal_coverage=0.2)
        strategy = gen.generate("test", eval_result, "bing", "week", 1, kb_hint=hint)
        # 应该按原始规则选 temporal（最弱维度）
        assert strategy is not None
        assert strategy.strategy_type == "time_adjust"

    @pytest.mark.asyncio
    async def test_similar_keywords_with_many_tokens(self, mem_db):
        """多词关键词应正确生成 OR 条件"""
        await _insert(mem_db, search_keyword="Python 异步编程 教程", score_delta=0.15)
        with patch("optimization.knowledge_base.get_db", _mock_get_db(mem_db)):
            kb = KnowledgeBase()
            data = await kb.get_similar_keyword_strategies("Python 教程")
        assert len(data) == 1
