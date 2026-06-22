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
    async def test_negative_delta_returns_hint_with_low_scores(self, mem_db):
        """负向结果也应返回 hint（低分策略应被降权）"""
        await _insert(mem_db, search_keyword="test", score_delta=-0.05)
        with patch("optimization.knowledge_base.get_db", _mock_get_db(mem_db)):
            hint = await KnowledgeBase().get_strategy_hint("test", "bing", "week")
        assert hint is not None
        assert hint["recommended_engine"] == "bing"
        assert hint["engine_scores"]["bing"] == -0.05

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
    async def test_includes_negative_delta(self, mem_db):
        """负向结果也应被返回，供调用方降权判断"""
        await _insert(mem_db, search_keyword="Python 教程", score_delta=-0.05)
        with patch("optimization.knowledge_base.get_db", _mock_get_db(mem_db)):
            data = await KnowledgeBase().get_similar_keyword_strategies("Python")
        assert len(data) == 1
        assert data[0]["score_delta"] == -0.05


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


# ============== Digest evaluation feedback ==============

class TestDigestEvaluationFeedback:

    @pytest.mark.asyncio
    async def test_save_digest_evaluation_stores_weak_dimensions(self, mem_db):
        await mem_db.execute(
            "INSERT INTO crawl_task (id, task_type, status) VALUES (101, 'digest', 3)",
        )
        await mem_db.commit()

        with patch("optimization.knowledge_base.get_db", _mock_get_db(mem_db)):
            kb = KnowledgeBase()
            await kb.save_digest_evaluation(
                task_id=101,
                digest_date="2026-05-28",
                overall_score=0.42,
                dimension_scores={
                    "angle": 0.72,
                    "source_diversity": 0.31,
                    "depth": 0.61,
                    "temporal": 0.66,
                    "perspective": 0.54,
                    "language": 0.29,
                },
                suggestions=["扩展来源", "补充英文资料"],
            )
            feedback = await kb.get_last_digest_weaknesses()

        assert feedback is not None
        assert feedback["weaknesses"] == ["source_diversity", "language"]
        assert feedback["suggestions"] == ["扩展来源", "补充英文资料"]

    @pytest.mark.asyncio
    async def test_recent_dimension_fatigue_uses_actual_dimension_columns(self, mem_db):
        await mem_db.execute(
            "INSERT INTO crawl_task (id, task_type, status) VALUES (201, 'digest', 3)",
        )
        rows = [
            ("2026-05-26 08:00:00", 0.70, 0.70, 0.30),
            ("2026-05-27 08:00:00", 0.50, 0.50, 0.50),
            ("2026-05-28 08:00:00", 0.30, 0.30, 0.80),
        ]
        for created_at, source_diversity, perspective_balance, depth_coverage in rows:
            await mem_db.execute(
                """INSERT INTO optimization_record
                   (task_id, round_num, source_diversity, perspective_balance,
                    depth_coverage, angle_coverage, temporal_coverage, language_coverage,
                    overall_score, search_keyword, search_engine, time_range,
                    strategy_type, score_delta, created_at)
                   VALUES (201, 0, ?, ?, ?, 0.8, 0.8, 0.8,
                           0.4, '2026-05-28', 'digest', '',
                           'digest_final_eval', 0.0, ?)""",
                (source_diversity, perspective_balance, depth_coverage, created_at),
            )
        await mem_db.commit()

        with patch("optimization.knowledge_base.get_db", _mock_get_db(mem_db)):
            fatigue = await KnowledgeBase().get_recent_dimension_fatigue(limit=3)

        assert fatigue["source_diversity"] == [0.30, 0.50, 0.70]
        assert fatigue["perspective"] == [0.30, 0.50, 0.70]
        assert "depth" not in fatigue

    @pytest.mark.asyncio
    async def test_digest_quality_overview_summarizes_trend_and_latest_feedback(self, mem_db):
        await mem_db.execute(
            "INSERT INTO crawl_task (id, task_type, status) VALUES (301, 'digest', 3)",
        )
        rows = [
            ("2026-05-29", 0.72, 0.70, 0.62, [], [], "2026-05-29 08:00:00"),
            ("2026-05-30", 0.58, 0.48, 0.55, ["source_diversity"], ["增加英文技术源"], "2026-05-30 08:00:00"),
            ("2026-05-31", 0.64, 0.44, 0.51, ["source_diversity"], ["补充 GitHub Trending"], "2026-05-31 08:00:00"),
        ]
        for digest_date, overall, source_diversity, depth, weaknesses, suggestions, created_at in rows:
            await mem_db.execute(
                """INSERT INTO optimization_record
                   (task_id, round_num, source_diversity, depth_coverage,
                    angle_coverage, temporal_coverage, perspective_balance,
                    language_coverage, overall_score, search_keyword, search_engine,
                    time_range, strategy_type, weaknesses, suggestions,
                    score_delta, created_at)
                   VALUES (301, 0, ?, ?, 0.7, 0.7, 0.7, 0.7,
                           ?, ?, 'digest', '', 'digest_final_eval', ?, ?,
                           0.0, ?)""",
                (
                    source_diversity,
                    depth,
                    overall,
                    digest_date,
                    __import__("json").dumps(weaknesses, ensure_ascii=False),
                    __import__("json").dumps(suggestions, ensure_ascii=False),
                    created_at,
                ),
            )
        await mem_db.commit()

        with patch("optimization.knowledge_base.get_db", _mock_get_db(mem_db)):
            overview = await KnowledgeBase().get_digest_quality_overview(limit=10)

        assert overview["count"] == 3
        assert overview["summary"]["average_score"] == 0.6467
        assert overview["summary"]["latest_score"] == 0.64
        assert overview["summary"]["score_delta"] == -0.08
        assert overview["summary"]["status"] == "warning"
        assert overview["latest"]["digest_date"] == "2026-05-31"
        assert overview["latest"]["weaknesses"] == ["source_diversity"]
        assert overview["suggestions"] == ["补充 GitHub Trending"]
        assert "source_diversity" in overview["weak_dimensions"]
        assert len(overview["trend"]) == 3

    @pytest.mark.asyncio
    async def test_digest_source_actions_derive_skip_and_deprioritize_from_latest_eval(self, mem_db):
        await mem_db.execute(
            "INSERT INTO crawl_task (id, task_type, status) VALUES (401, 'digest', 3)",
        )
        source_scores = [
            {
                "section": "open_source",
                "source_id": 10,
                "source_name": "Low Quality",
                "source_url": "https://low.example.com",
                "item_count": 2,
                "quality_score": 0.35,
                "quality_verdict": "keep",
            },
            {
                "section": "tools",
                "source_id": 11,
                "source_name": "Review Source",
                "source_url": "https://review.example.com",
                "item_count": 1,
                "quality_score": 0.72,
                "quality_verdict": "review",
            },
            {
                "section": "ai_news",
                "source_id": 12,
                "source_name": "Healthy",
                "source_url": "https://healthy.example.com",
                "item_count": 4,
                "quality_score": 0.86,
                "quality_verdict": "keep",
            },
        ]
        await _insert(
            mem_db,
            task_id=401,
            round_num=0,
            strategy_type="digest_final_eval",
            search_keyword="2026-06-08",
            search_engine="digest",
            strategy_detail=__import__("json").dumps(source_scores, ensure_ascii=False),
            weaknesses=__import__("json").dumps(["source_diversity"], ensure_ascii=False),
            suggestions=__import__("json").dumps(["补充开源信息源"], ensure_ascii=False),
            overall_score=0.52,
        )

        with patch("optimization.knowledge_base.get_db", _mock_get_db(mem_db)):
            actions = await KnowledgeBase().get_digest_source_actions()

        assert actions["source_ids"]["skip"] == []
        assert actions["source_ids"]["deprioritize"] == [11, 10]
        assert actions["boost_sections"] == ["source_diversity"]
        assert actions["confidence"] == "medium"
        assert actions["sources"][10]["action"] == "deprioritize"
        assert actions["sources"][11]["action"] == "deprioritize"
        assert 12 not in actions["sources"]
        assert any("section-skip-cap" in item for item in actions["safety"]["applied"])

    def test_digest_source_actions_include_url_actions_without_source_id(self):
        actions = KnowledgeBase.derive_digest_source_actions(
            diagnostics=[
                {
                    "section": "tech_article",
                    "source_id": None,
                    "source_name": "Review URL",
                    "source_url": "https://review.example.com/article",
                    "item_count": 1,
                    "quality_score": 53.6,
                    "quality_verdict": "review",
                },
                {
                    "section": "hot_trend",
                    "source_name": "Filtered URL",
                    "source_url": "https://filter.example.com/post",
                    "item_count": 1,
                    "quality_score": 72,
                    "quality_verdict": "filter",
                },
            ],
            weaknesses=["language"],
            suggestions=[],
            digest_date="2026-06-08",
        )

        assert actions["source_ids"] == {"skip": [], "deprioritize": []}
        assert actions["source_urls"]["deprioritize"] == [
            "https://review.example.com/article",
            "https://filter.example.com/post",
        ]
        assert actions["source_urls"]["skip"] == []
        assert actions["sources"]["url:https://review.example.com/article"]["quality_score"] == 0.536
        assert actions["sources"]["url:https://filter.example.com/post"]["action"] == "deprioritize"
        assert actions["confidence"] == "medium"
        assert any("section-skip-cap" in item for item in actions["safety"]["applied"])

    def test_digest_source_actions_downgrade_single_low_confidence_skip(self):
        actions = KnowledgeBase.derive_digest_source_actions(
            diagnostics=[
                {
                    "section": "open_source",
                    "source_id": 501,
                    "source_name": "Single Weak Source",
                    "source_url": "https://weak.example.com",
                    "item_count": 1,
                    "quality_score": 0.21,
                    "quality_verdict": "keep",
                },
            ],
            weaknesses=["source_diversity"],
            suggestions=["review source mix"],
            digest_date="2026-06-09",
        )

        assert actions["confidence"] == "low"
        assert actions["source_ids"]["skip"] == []
        assert actions["source_ids"]["deprioritize"] == [501]
        assert actions["sources"][501]["action"] == "deprioritize"
        assert actions["safety"]["applied"]
        assert any("low-confidence" in item for item in actions["safety"]["applied"])

    def test_digest_source_actions_cap_section_skip_actions(self):
        actions = KnowledgeBase.derive_digest_source_actions(
            diagnostics=[
                {
                    "section": "dev_tool",
                    "source_id": 601,
                    "source_name": "Worst",
                    "source_url": "https://worst.example.com",
                    "item_count": 1,
                    "quality_score": 0.10,
                    "quality_verdict": "keep",
                },
                {
                    "section": "dev_tool",
                    "source_id": 602,
                    "source_name": "Bad",
                    "source_url": "https://bad.example.com",
                    "item_count": 1,
                    "quality_score": 0.20,
                    "quality_verdict": "keep",
                },
                {
                    "section": "dev_tool",
                    "source_id": 603,
                    "source_name": "Maybe Bad",
                    "source_url": "https://maybe.example.com",
                    "item_count": 1,
                    "quality_score": 0.30,
                    "quality_verdict": "keep",
                },
                {
                    "section": "dev_tool",
                    "source_id": 604,
                    "source_name": "Healthy",
                    "source_url": "https://healthy.example.com",
                    "item_count": 3,
                    "quality_score": 0.82,
                    "quality_verdict": "keep",
                },
            ],
            weaknesses=[],
            suggestions=[],
            digest_date="2026-06-09",
        )

        assert actions["confidence"] == "medium"
        assert actions["source_ids"]["skip"] == [601, 602]
        assert actions["source_ids"]["deprioritize"] == [603]
        assert actions["sources"][603]["action"] == "deprioritize"
        assert any("section-skip-cap" in item for item in actions["safety"]["applied"])

    def test_negative_optimization_outcome_downgrades_next_source_actions(self):
        actions = KnowledgeBase.derive_digest_source_actions(
            diagnostics=[
                {
                    "section": "open_source",
                    "source_id": 701,
                    "source_name": "Bad Source",
                    "source_url": "https://bad.example.com",
                    "item_count": 1,
                    "quality_score": 0.12,
                    "quality_verdict": "filter",
                },
                {
                    "section": "open_source",
                    "source_id": 702,
                    "source_name": "Review Source",
                    "source_url": "https://review.example.com",
                    "item_count": 1,
                    "quality_score": 0.52,
                    "quality_verdict": "review",
                },
            ],
            weaknesses=["source_diversity"],
            suggestions=["boost source diversity"],
            digest_date="2026-06-10",
            action_outcomes=[
                {
                    "applied": True,
                    "verdict": "negative",
                    "result": {"overall_score": 0.41, "section_fill_ratio": 0.52},
                }
            ],
        )

        assert actions["confidence"] == "low"
        assert actions["boost_sections"] == []
        assert actions["source_ids"]["skip"] == []
        assert set(actions["source_ids"]["deprioritize"]) == {701, 702}
        assert actions["sources"][701]["action"] == "deprioritize"
        assert any("negative-outcome-circuit-breaker" in item for item in actions["safety"]["applied"])
        assert actions["safety"]["suppressed_boost_sections"] == ["source_diversity"]

    @pytest.mark.asyncio
    async def test_get_digest_source_actions_uses_task_metadata_outcome_guard(self, mem_db):
        json = __import__("json")
        source_scores = [
            {
                "section": "paper",
                "source_id": 801,
                "source_name": "Weak Paper Source",
                "source_url": "https://paper.example.com",
                "item_count": 1,
                "quality_score": 0.21,
                "quality_verdict": "filter",
            },
        ]
        await _insert(
            mem_db,
            task_id=801,
            round_num=0,
            strategy_type="digest_final_eval",
            search_keyword="2026-06-10",
            search_engine="digest",
            strategy_detail=json.dumps(source_scores, ensure_ascii=False),
            weaknesses=json.dumps(["source_diversity"], ensure_ascii=False),
            suggestions=json.dumps(["avoid repeating bad sources"], ensure_ascii=False),
            overall_score=0.46,
        )

        async def fake_get_task(_task_id):
            return {
                "ai_search_metadata": json.dumps({
                    "orchestrator_plan": {
                        "optimization_action_outcome": {
                            "applied": True,
                            "verdict": "negative",
                            "result": {
                                "overall_score": 0.42,
                                "section_fill_ratio": 0.5,
                            },
                        }
                    }
                })
            }

        async def fake_source_diagnostics(_task_id):
            return []

        with patch("optimization.knowledge_base.get_db", _mock_get_db(mem_db)), \
             patch("standalone.repository.get_task", fake_get_task), \
             patch("standalone.repository.get_digest_source_diagnostics", fake_source_diagnostics):
            actions = await KnowledgeBase().get_digest_source_actions()

        assert actions["source_ids"]["skip"] == []
        assert actions["source_ids"]["deprioritize"] == [801]
        assert actions["confidence"] == "low"
        assert any("negative-outcome-circuit-breaker" in item for item in actions["safety"]["applied"])
