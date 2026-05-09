"""KnowledgeBase 策略学习引擎单元测试"""

import pytest
from contextlib import asynccontextmanager
from unittest.mock import patch

from optimization.knowledge_base import KnowledgeBase


async def _insert(db, **kwargs):
    # 确保父记录 crawl_task 存在（FOREIGN KEY 约束）
    task_id = kwargs.get("task_id", 1)
    cursor = await db.execute("SELECT 1 FROM crawl_task WHERE id = ?", (task_id,))
    if not await cursor.fetchone():
        await db.execute(
            """INSERT INTO crawl_task (id, task_type, status)
               VALUES (?, 'keyword', 3)""",
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


def _mock_get_db(mem_db):
    @asynccontextmanager
    async def _get_db():
        yield mem_db
    return _get_db


# ============== get_strategy_hint ==============

class TestGetStrategyHint:

    @pytest.mark.asyncio
    async def test_empty_db_returns_none(self, mem_db):
        with patch("optimization.knowledge_base.get_db", _mock_get_db(mem_db)):
            hint = await KnowledgeBase().get_strategy_hint("Python", "bing", "week")
        assert hint is None

    @pytest.mark.asyncio
    async def test_single_effective_record(self, mem_db):
        await _insert(mem_db, search_keyword="Python", search_engine="baidu",
                      score_delta=0.15, strategy_type="engine_switch")
        with patch("optimization.knowledge_base.get_db", _mock_get_db(mem_db)):
            hint = await KnowledgeBase().get_strategy_hint("Python", "bing", "week")
        assert hint is not None
        assert hint["recommended_engine"] == "baidu"
        assert hint["recommended_strategy_type"] == "engine_switch"

    @pytest.mark.asyncio
    async def test_prefers_best_engine(self, mem_db):
        await _insert(mem_db, search_keyword="Python", search_engine="bing",
                      score_delta=0.05, strategy_type="engine_switch")
        await _insert(mem_db, search_keyword="Python", search_engine="baidu",
                      score_delta=0.20, strategy_type="engine_switch")
        with patch("optimization.knowledge_base.get_db", _mock_get_db(mem_db)):
            hint = await KnowledgeBase().get_strategy_hint("Python", "bing", "week")
        assert hint["recommended_engine"] == "baidu"

    @pytest.mark.asyncio
    async def test_no_positive_delta_returns_none(self, mem_db):
        await _insert(mem_db, search_keyword="test", score_delta=-0.05)
        with patch("optimization.knowledge_base.get_db", _mock_get_db(mem_db)):
            hint = await KnowledgeBase().get_strategy_hint("test", "bing", "week")
        assert hint is None

    @pytest.mark.asyncio
    async def test_related_keywords(self, mem_db):
        await _insert(mem_db, search_keyword="Python async", search_engine="baidu",
                      score_delta=0.15, task_id=1)
        await _insert(mem_db, search_keyword="Python asyncio", search_engine="sogou",
                      score_delta=0.10, task_id=2)
        with patch("optimization.knowledge_base.get_db", _mock_get_db(mem_db)):
            hint = await KnowledgeBase().get_strategy_hint("Python tutorial", "bing", "week")
        assert hint is not None
        assert len(hint["related_keywords"]) > 0

    @pytest.mark.asyncio
    async def test_matches_by_time_range(self, mem_db):
        await _insert(mem_db, search_keyword="unrelated", search_engine="sogou",
                      score_delta=0.12, time_range="week")
        with patch("optimization.knowledge_base.get_db", _mock_get_db(mem_db)):
            hint = await KnowledgeBase().get_strategy_hint("different", "bing", "week")
        assert hint is not None


# ============== get_engine_effectiveness ==============

class TestGetEngineEffectiveness:

    @pytest.mark.asyncio
    async def test_empty_db(self, mem_db):
        with patch("optimization.knowledge_base.get_db", _mock_get_db(mem_db)):
            data = await KnowledgeBase().get_engine_effectiveness()
        assert data == []

    @pytest.mark.asyncio
    async def test_groups_by_engine(self, mem_db):
        await _insert(mem_db, search_engine="bing", score_delta=0.10)
        await _insert(mem_db, search_engine="bing", score_delta=0.15)
        await _insert(mem_db, search_engine="baidu", score_delta=0.20)
        with patch("optimization.knowledge_base.get_db", _mock_get_db(mem_db)):
            data = await KnowledgeBase().get_engine_effectiveness()
        assert len(data) == 2
        assert data[0]["search_engine"] == "baidu"

    @pytest.mark.asyncio
    async def test_excludes_round1(self, mem_db):
        await _insert(mem_db, round_num=1, search_engine="bing", score_delta=0.50)
        with patch("optimization.knowledge_base.get_db", _mock_get_db(mem_db)):
            data = await KnowledgeBase().get_engine_effectiveness()
        assert data == []


# ============== get_strategy_type_effectiveness ==============

class TestGetStrategyTypeEffectiveness:

    @pytest.mark.asyncio
    async def test_empty_db(self, mem_db):
        with patch("optimization.knowledge_base.get_db", _mock_get_db(mem_db)):
            data = await KnowledgeBase().get_strategy_type_effectiveness()
        assert data == []

    @pytest.mark.asyncio
    async def test_groups_by_type(self, mem_db):
        await _insert(mem_db, strategy_type="engine_switch", score_delta=0.15)
        await _insert(mem_db, strategy_type="time_adjust", score_delta=0.20)
        await _insert(mem_db, strategy_type="engine_switch", score_delta=0.10)
        with patch("optimization.knowledge_base.get_db", _mock_get_db(mem_db)):
            data = await KnowledgeBase().get_strategy_type_effectiveness()
        assert len(data) == 2
        assert data[0]["strategy_type"] == "time_adjust"


# ============== get_similar_keyword_strategies ==============

class TestGetSimilarKeywordStrategies:

    @pytest.mark.asyncio
    async def test_empty_db(self, mem_db):
        with patch("optimization.knowledge_base.get_db", _mock_get_db(mem_db)):
            data = await KnowledgeBase().get_similar_keyword_strategies("test")
        assert data == []

    @pytest.mark.asyncio
    async def test_finds_by_token(self, mem_db):
        await _insert(mem_db, search_keyword="Spring Boot 教程", score_delta=0.15)
        await _insert(mem_db, search_keyword="React 入门", score_delta=0.10)
        with patch("optimization.knowledge_base.get_db", _mock_get_db(mem_db)):
            data = await KnowledgeBase().get_similar_keyword_strategies("Spring Boot")
        assert len(data) == 1
        assert "Spring" in data[0]["search_keyword"]

    @pytest.mark.asyncio
    async def test_only_positive_delta(self, mem_db):
        await _insert(mem_db, search_keyword="Python 教程", score_delta=-0.05)
        with patch("optimization.knowledge_base.get_db", _mock_get_db(mem_db)):
            data = await KnowledgeBase().get_similar_keyword_strategies("Python")
        assert data == []


# ============== get_stats ==============

class TestGetStats:

    @pytest.mark.asyncio
    async def test_empty_db(self, mem_db):
        with patch("optimization.knowledge_base.get_db", _mock_get_db(mem_db)):
            stats = await KnowledgeBase().get_stats()
        assert stats["total_rounds"] == 0
        assert stats["improvement_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_with_records(self, mem_db):
        await _insert(mem_db, task_id=1, score_delta=0.10)
        await _insert(mem_db, task_id=1, score_delta=-0.05)
        await _insert(mem_db, task_id=2, score_delta=0.15)
        with patch("optimization.knowledge_base.get_db", _mock_get_db(mem_db)):
            stats = await KnowledgeBase().get_stats()
        assert stats["total_rounds"] == 3
        assert stats["total_tasks"] == 2
        assert stats["improved_rounds"] == 2


# ============== cleanup_old_records ==============

class TestCleanupOldRecords:

    @pytest.mark.asyncio
    async def test_no_old_records(self, mem_db):
        await _insert(mem_db, search_keyword="recent")
        with patch("optimization.knowledge_base.get_db", _mock_get_db(mem_db)):
            deleted = await KnowledgeBase().cleanup_old_records(days=90)
        assert deleted == 0

    @pytest.mark.asyncio
    async def test_deletes_old_records(self, mem_db):
        await mem_db.execute(
            "INSERT INTO crawl_task (id, task_type, status) VALUES (1, 'keyword', 3)",
        )
        await mem_db.execute(
            """INSERT INTO optimization_record
               (task_id, round_num, overall_score, search_keyword, search_engine,
                time_range, strategy_type, score_delta, created_at)
               VALUES (1, 2, 0.5, 'old', 'bing', 'week', 'engine_switch', 0.1,
                       datetime('now', '-100 days'))""",
        )
        await mem_db.commit()
        await _insert(mem_db, search_keyword="recent")

        with patch("optimization.knowledge_base.get_db", _mock_get_db(mem_db)):
            deleted = await KnowledgeBase().cleanup_old_records(days=90)
        assert deleted == 1

        cursor = await mem_db.execute("SELECT COUNT(*) AS cnt FROM optimization_record")
        row = await cursor.fetchone()
        assert row["cnt"] == 1
