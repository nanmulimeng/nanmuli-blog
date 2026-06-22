"""日报 API 端点测试：GET /digests, /digests/{date}, /digests/latest, /digests/config/sections"""

import os
import sys
import pytest
import pytest_asyncio
import json
from httpx import AsyncClient, ASGITransport
from contextlib import asynccontextmanager

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from fastapi import FastAPI
from standalone.routes import router as standalone_router


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(standalone_router)
    return app


@pytest_asyncio.fixture
async def patched_repo():
    """Patch repository to use a shared in-memory DB"""
    import aiosqlite
    from standalone.db import DDL, _MIGRATIONS
    from standalone import repository as repo_mod

    # 创建共享内存 DB
    shared_db = await aiosqlite.connect(":memory:")
    shared_db.text_factory = lambda b: b.decode("utf-8", errors="replace")
    shared_db.row_factory = aiosqlite.Row
    await shared_db.execute("PRAGMA foreign_keys=ON")
    await shared_db.executescript(DDL)
    await shared_db.commit()

    cursor = await shared_db.execute("PRAGMA table_info(crawl_task)")
    existing = {row[1] for row in await cursor.fetchall()}
    for col_name, sql in _MIGRATIONS:
        if col_name not in existing:
            try:
                await shared_db.execute(sql)
            except Exception:
                pass
    await shared_db.commit()

    @asynccontextmanager
    async def _mock_get_db():
        yield shared_db

    original = repo_mod.get_db
    repo_mod.get_db = _mock_get_db
    yield repo_mod
    repo_mod.get_db = original
    await shared_db.close()


# ============== GET /digests ==============

class TestListDigests:
    @pytest.mark.asyncio
    async def test_empty_list(self, app, patched_repo):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/digests")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["records"] == []

    @pytest.mark.asyncio
    async def test_list_returns_digest_tasks_only(self, app, patched_repo):
        repo = patched_repo

        await repo.create_task(task_type="single", source_url="https://example.com")
        digest_id = await repo.create_task(task_type="digest", keyword="2026-05-08", ai_template="daily_digest")
        # Public list returns completed digest tasks with publishable AI content.
        await repo.save_ai_results(
            digest_id, ai_title="Test Digest", ai_summary="s", ai_key_points=[],
            ai_tags=[], ai_category="tech_article", ai_full_content="c",
            ai_duration=1, ai_tokens_used=0,
        )
        await repo.complete_task(digest_id)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/digests")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1

    @pytest.mark.asyncio
    async def test_list_hides_in_progress_digest_by_default(self, app, patched_repo):
        repo = patched_repo

        await repo.create_task(
            task_type="digest",
            keyword="2026-05-10",
            ai_template="daily_digest",
            digest_date="2026-05-10",
        )

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/digests")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["records"] == []

    @pytest.mark.asyncio
    async def test_list_can_include_in_progress_digest_for_admin(self, app, patched_repo):
        repo = patched_repo

        digest_id = await repo.create_task(
            task_type="digest",
            keyword="2026-05-10",
            ai_template="daily_digest",
            digest_date="2026-05-10",
        )

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/digests?include_all=true")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["records"][0]["id"] == digest_id
        assert data["records"][0]["status"] == 0
        assert data["records"][0]["ai_title"] is None

    @pytest.mark.asyncio
    async def test_list_hides_failed_digest_with_ai_title_by_default(self, app, patched_repo):
        repo = patched_repo

        digest_id = await repo.create_task(
            task_type="digest",
            keyword="2026-06-17",
            ai_template="daily_digest",
            digest_date="2026-06-17",
        )
        await repo.save_digest_results(
            digest_id, "失败日报", "摘要", ["AI"], "内容", 100, 50,
            "2026-06-17", "亮点", [],
        )
        await repo.fail_task(digest_id, "Digest quality below publish threshold (score=0.420)")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            public_resp = await ac.get("/digests")
            admin_resp = await ac.get("/digests?include_all=true")

        assert public_resp.status_code == 200
        assert public_resp.json()["total"] == 0
        assert admin_resp.status_code == 200
        assert admin_resp.json()["total"] == 1
        assert admin_resp.json()["records"][0]["id"] == digest_id

    @pytest.mark.asyncio
    async def test_list_hides_quality_rejected_completed_digest_by_default(self, app, patched_repo):
        repo = patched_repo

        digest_id = await repo.create_task(
            task_type="digest",
            keyword="2026-06-18",
            ai_template="daily_digest",
            digest_date="2026-06-18",
        )
        await repo.save_digest_results(
            digest_id, "质量拒绝日报", "摘要", ["AI"], "内容", 100, 50,
            "2026-06-18", "亮点", [],
        )
        await repo.save_ai_search_metadata(digest_id, {
            "digest_publishable": False,
            "digest_publish_stage": "pre_generated",
            "digest_publish_quality": {"score": 0.42},
        })
        await repo.complete_task(digest_id)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            public_resp = await ac.get("/digests")
            admin_resp = await ac.get("/digests?include_all=true")

        assert public_resp.status_code == 200
        assert public_resp.json()["records"] == []
        assert admin_resp.status_code == 200
        assert admin_resp.json()["records"][0]["id"] == digest_id


class TestDigestSchedulerStatus:
    @pytest.mark.asyncio
    async def test_status_includes_latest_digest_result(self, app, patched_repo, monkeypatch):
        from standalone import scheduler

        def fake_scheduler_status():
            return {
                "running": True,
                "cron": "0 8 * * 1-5",
                "enabled": True,
                "next_run": "2026-06-13 08:00:00+08:00",
                "source_jobs": 0,
                "digest_job_registered": True,
                "ai_enabled": True,
                "ai_configured": True,
                "jobs": [],
            }

        monkeypatch.setattr(scheduler, "get_scheduler_status", fake_scheduler_status)

        repo = patched_repo
        digest_id = await repo.create_task(
            task_type="digest",
            keyword="2026-05-10",
            ai_template="daily_digest",
            digest_date="2026-05-10",
        )
        await repo.update_task_status(digest_id, 4, "callback failed: 401")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/digests/scheduler/status")

        assert resp.status_code == 200
        data = resp.json()
        assert data["latest_digest"]["id"] == digest_id
        assert data["latest_digest"]["status"] == 4
        assert data["latest_digest"]["error_message"] == "callback failed: 401"
        assert "diagnostics" in data["latest_digest"]
        assert data["diagnostics"]["state"] == "latest_failed"
        assert data["diagnostics"]["summary"] == data["latest_digest"]["diagnostics"]["failure"]["label"]
        assert any(check["key"] == "latest_digest" for check in data["diagnostics"]["checks"])

    @pytest.mark.asyncio
    async def test_status_reports_misconfigured_scheduler(self, app, patched_repo, monkeypatch):
        from standalone import scheduler

        def fake_scheduler_status():
            return {
                "running": True,
                "cron": "0 8 * * 1-5",
                "enabled": True,
                "next_run": None,
                "source_jobs": 0,
                "digest_job_registered": False,
                "ai_enabled": True,
                "ai_configured": False,
                "jobs": [],
            }

        monkeypatch.setattr(scheduler, "get_scheduler_status", fake_scheduler_status)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/digests/scheduler/status")

        assert resp.status_code == 200
        data = resp.json()
        assert data["diagnostics"]["state"] == "misconfigured"
        assert "AI" in data["diagnostics"]["summary"]
        checks = {check["key"]: check for check in data["diagnostics"]["checks"]}
        assert checks["ai"]["status"] == "warning"
        assert checks["digest_job"]["status"] == "warning"


class TestSearchFeedbackApi:
    @pytest.mark.asyncio
    async def test_search_feedback_returns_recent_digest_diagnostics(self, app, patched_repo):
        repo = patched_repo

        task_id = await repo.create_task(
            task_type="digest",
            keyword="2026-06-21",
            ai_template="daily_digest",
            digest_date="2026-06-21",
        )
        await repo.save_ai_search_metadata(task_id, {
            "orchestrator_plan": {
                "search_diagnostics": [
                    {
                        "section": "open_source",
                        "query": "AI agent github",
                        "engine": "bing",
                        "requested": 5,
                        "returned": 7,
                        "kept": 4,
                        "filtered": 2,
                        "top_domains": ["github.com"],
                    },
                    {
                        "section": "paper",
                        "query": "site:arxiv.org AI agent",
                        "engine": "bing",
                        "requested": 5,
                        "returned": 0,
                        "kept": 0,
                        "filtered": 0,
                        "top_domains": [],
                    },
                ],
            }
        })
        await repo.fail_task(task_id, "quality below threshold")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/optimization/search-feedback?limit=5")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        record = data["records"][0]
        assert record["task_id"] == task_id
        assert record["summary"]["total_queries"] == 2
        assert record["summary"]["total_kept"] == 4
        assert record["summary"]["zero_result_queries"][0]["section"] == "paper"


# ============== GET /digests/latest ==============

class TestGetLatestDigest:
    @pytest.mark.asyncio
    async def test_no_digests_returns_404(self, app, patched_repo):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/digests/latest")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_latest_digest_with_sections(self, app, patched_repo):
        repo = patched_repo

        task_id = await repo.create_task(
            task_type="digest", keyword="2026-05-08", ai_template="daily_digest"
        )
        await repo.save_digest_results(
            task_id,
            ai_title="技术日报 | 2026-05-08",
            ai_summary="今日概要",
            ai_tags=["AI"],
            ai_full_content="## 日报内容",
            ai_duration=3000,
            ai_tokens_used=500,
            digest_date="2026-05-08",
            highlight="重大发布",
            sections=[
                {
                    "category": "hot_trend",
                    "category_name": "热点动态",
                    "emoji": "🔥",
                    "items": [
                        {"title": "新闻1", "one_liner": "一句话",
                         "source_url": "https://a.com", "source_name": "a.com"},
                    ],
                },
            ],
        )
        await repo.complete_task(task_id)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/digests/latest")

        assert resp.status_code == 200
        data = resp.json()
        assert data["ai_title"] == "技术日报 | 2026-05-08"
        assert data["digest_date"] == "2026-05-08"
        assert data["highlight"] == "重大发布"
        assert len(data["sections"]) == 1
        assert data["sections"][0]["category"] == "hot_trend"
        assert len(data["sections"][0]["items"]) == 1
        assert data["sections"][0]["items"][0]["title"] == "新闻1"
        assert "id" not in data["sections"][0]
        assert "id" not in data["sections"][0]["items"][0]

    @pytest.mark.asyncio
    async def test_latest_skips_newer_quality_rejected_digest(self, app, patched_repo):
        repo = patched_repo

        public_id = await repo.create_task(
            task_type="digest", keyword="2026-06-15", ai_template="daily_digest",
            digest_date="2026-06-15",
        )
        await repo.save_digest_results(
            public_id, "可发布日报", "摘要", ["AI"], "内容", 100, 50,
            "2026-06-15", "亮点", [],
        )
        await repo.complete_task(public_id)

        rejected_id = await repo.create_task(
            task_type="digest", keyword="2026-06-16", ai_template="daily_digest",
            digest_date="2026-06-16",
        )
        await repo.save_digest_results(
            rejected_id, "质量拒绝日报", "摘要", ["AI"], "内容", 100, 50,
            "2026-06-16", "亮点", [],
        )
        await repo.save_ai_search_metadata(rejected_id, {
            "digest_publishable": False,
            "digest_publish_stage": "fallback",
            "digest_publish_quality": {"score": 0.4},
        })
        await repo.complete_task(rejected_id)
        async with repo.get_db() as db:
            await db.execute(
                "UPDATE crawl_task SET created_at = ? WHERE id = ?",
                ("2026-06-15 08:00:00", public_id),
            )
            await db.execute(
                "UPDATE crawl_task SET created_at = ? WHERE id = ?",
                ("2026-06-16 08:00:00", rejected_id),
            )
            await db.commit()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/digests/latest")

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == public_id
        assert data["digest_date"] == "2026-06-15"


# ============== GET /digests/{date} ==============

class TestGetDigestByDate:
    @pytest.mark.asyncio
    async def test_not_found_date(self, app, patched_repo):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/digests/2099-12-31")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_found_by_date(self, app, patched_repo):
        repo = patched_repo

        task_id = await repo.create_task(
            task_type="digest", keyword="2026-05-07", ai_template="daily_digest"
        )
        await repo.save_digest_results(
            task_id, "日报 5/7", "摘要", ["t"], "内容", 100, 50,
            "2026-05-07", "亮点", [],
        )
        await repo.complete_task(task_id)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/digests/2026-05-07")

        assert resp.status_code == 200
        assert resp.json()["digest_date"] == "2026-05-07"

    @pytest.mark.asyncio
    async def test_quality_rejected_digest_by_date_returns_404(self, app, patched_repo):
        repo = patched_repo

        task_id = await repo.create_task(
            task_type="digest", keyword="2026-06-19", ai_template="daily_digest",
            digest_date="2026-06-19",
        )
        await repo.save_digest_results(
            task_id, "质量拒绝日报", "摘要", ["AI"], "内容", 100, 50,
            "2026-06-19", "亮点", [],
        )
        await repo.save_ai_search_metadata(task_id, {
            "digest_publishable": False,
            "digest_publish_stage": "fallback",
            "digest_publish_quality": {"score": 0.42},
        })
        await repo.complete_task(task_id)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/digests/2026-06-19")

        assert resp.status_code == 404


# ============== GET /digests/task/{task_id} ==============

class TestGetDigestByTaskId:
    @pytest.mark.asyncio
    async def test_not_found_task(self, app, patched_repo):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/digests/task/99999")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_non_digest_task_rejected(self, app, patched_repo):
        repo = patched_repo

        task_id = await repo.create_task(
            task_type="single", source_url="https://example.com"
        )

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"/digests/task/{task_id}")
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_digest_task_found(self, app, patched_repo):
        repo = patched_repo

        task_id = await repo.create_task(
            task_type="digest", keyword="2026-05-09", ai_template="daily_digest"
        )
        await repo.save_digest_results(
            task_id, "日报 5/9", "摘要", ["t"], "内容", 100, 50,
            "2026-05-09", "亮点", [],
        )
        await repo.complete_task(task_id)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"/digests/task/{task_id}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == task_id
        assert data["digest_date"] == "2026-05-09"
        assert data["diagnostics"]["stage"] == "completed"
        assert data["diagnostics"]["failure"]["category"] == "none"

    @pytest.mark.asyncio
    async def test_digest_task_includes_quality_evaluation(self, app, patched_repo):
        repo = patched_repo

        task_id = await repo.create_task(
            task_type="digest", keyword="2026-05-11", ai_template="daily_digest"
        )
        async with repo.get_db() as db:
            await db.execute(
                """INSERT INTO crawl_page
                   (task_id, url, page_title, raw_markdown, page_metadata,
                    crawl_status, word_count, url_hash, sort_order)
                   VALUES (?, ?, ?, ?, ?, 1, 1200, ?, 0)""",
                (
                    task_id,
                    "https://low.example.com/a",
                    "Low source item",
                    "content",
                    json.dumps({
                        "source_id": "42",
                        "source_name": "LowFeed",
                        "quality_score": 38,
                        "quality_verdict": "review",
                    }, ensure_ascii=False),
                    "low-source-hash",
                ),
            )
            cursor = await db.execute("SELECT last_insert_rowid()")
            page_id = (await cursor.fetchone())[0]
            await db.commit()
        await repo.save_digest_results(
            task_id, "日报 5/11", "摘要", ["t"], "内容", 100, 50,
            "2026-05-11", "亮点", [],
        )
        async with repo.get_db() as db:
            cursor = await db.execute(
                """INSERT INTO digest_section
                   (task_id, category, category_name, emoji, sort_order)
                   VALUES (?, 'hot_trend', '热点', '', 0)""",
                (task_id,),
            )
            section_id = cursor.lastrowid
            await db.execute(
                """INSERT INTO digest_item
                   (section_id, title, one_liner, source_url, source_name, page_id, sort_order)
                   VALUES (?, 'Low source item', '来源质量偏低',
                           'https://low.example.com/a', 'LowFeed', ?, 0)""",
                (section_id, page_id),
            )
            await db.commit()
        await repo.complete_task(task_id)
        async with repo.get_db() as db:
            await db.execute(
                """INSERT INTO optimization_record
                   (task_id, round_num, angle_coverage, source_diversity,
                    depth_coverage, temporal_coverage, perspective_balance,
                    language_coverage, overall_score, search_keyword,
                    search_engine, time_range, strategy_type, strategy_detail,
                    weaknesses, suggestions, score_delta)
                   VALUES (?, 0, 0.8, 0.42, 0.66, 0.7, 0.5, 0.9,
                           0.61, '2026-05-11', 'digest', '',
                           'digest_final_eval', ?, ?, ?, 0.0)""",
                (
                    task_id,
                    json.dumps([
                        {"name": "hot_trend", "result_count": 1, "status": "completed", "fill_score": 0.33},
                        {"name": "__digest_output__", "score": 0.72, "issues": ["内容偏薄"]},
                    ], ensure_ascii=False),
                    json.dumps(["source_diversity"], ensure_ascii=False),
                    json.dumps(["补充权威来源"], ensure_ascii=False),
                ),
            )
            await db.commit()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"/digests/task/{task_id}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["quality_evaluation"]["overall_score"] == 0.61
        assert data["quality_evaluation"]["dimensions"]["source_diversity"] == 0.42
        assert data["quality_evaluation"]["weaknesses"] == ["source_diversity"]
        assert data["quality_evaluation"]["suggestions"] == ["补充权威来源"]
        assert data["quality_evaluation"]["section_scores"][0]["name"] == "hot_trend"
        source_diag = data["quality_evaluation"]["source_diagnostics"][0]
        assert source_diag["section"] == "hot_trend"
        assert source_diag["source_name"] == "LowFeed"
        assert source_diag["source_id"] == "42"
        assert source_diag["item_count"] == 1
        assert source_diag["quality_score"] == 38
        assert source_diag["quality_verdict"] == "review"
        next_actions = data["quality_evaluation"]["next_run_actions"]
        assert next_actions["confidence"] == "low"
        assert next_actions["source_ids"]["skip"] == []
        assert next_actions["source_ids"]["deprioritize"] == [42]
        assert next_actions["sources"]["42"]["action"] == "deprioritize"
        assert any("low-confidence" in item for item in next_actions["safety"]["applied"])

    @pytest.mark.asyncio
    async def test_digest_task_uses_publish_quality_metadata_without_final_eval(self, app, patched_repo):
        repo = patched_repo

        task_id = await repo.create_task(
            task_type="digest",
            keyword="2026-06-16",
            ai_template="daily_digest",
            digest_date="2026-06-16",
        )
        await repo.save_ai_search_metadata(task_id, {
            "digest_publishable": False,
            "digest_publish_stage": "fallback",
            "digest_publish_quality": {
                "score": 0.42,
                "item_count": 3,
                "section_count": 1,
                "suggestions": ["补充权威来源"],
            },
        })
        await repo.fail_task(task_id, "Digest quality below publish threshold (score=0.420)")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"/digests/task/{task_id}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == 4
        assert data["quality_evaluation"]["overall_score"] == 0.42
        assert data["quality_evaluation"]["publishable"] is False
        assert data["quality_evaluation"]["stage"] == "fallback"
        assert data["quality_evaluation"]["suggestions"] == ["补充权威来源"]
        assert data["quality_evaluation"]["next_run_actions"] is None

    @pytest.mark.asyncio
    async def test_digest_task_returns_search_diagnostics_from_orchestrator_plan(self, app, patched_repo):
        repo = patched_repo

        task_id = await repo.create_task(
            task_type="digest",
            keyword="2026-06-20",
            ai_template="daily_digest",
            digest_date="2026-06-20",
        )
        await repo.save_ai_search_metadata(task_id, {
            "orchestrator_plan": {
                "search_diagnostics": [
                    {
                        "section": "hot_trend",
                        "query": "AI coding agent",
                        "engine": "bing",
                        "requested": 5,
                        "returned": 6,
                        "kept": 3,
                        "filtered": 1,
                        "top_domains": ["github.blog"],
                    }
                ]
            }
        })
        await repo.fail_task(task_id, "quality below threshold")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"/digests/task/{task_id}")

        assert resp.status_code == 200
        data = resp.json()
        diagnostic = data["orchestrator_plan"]["search_diagnostics"][0]
        assert diagnostic["section"] == "hot_trend"
        assert diagnostic["query"] == "AI coding agent"
        assert diagnostic["kept"] == 3

    @pytest.mark.asyncio
    async def test_digest_task_returns_event_diagnostics_from_orchestrator_plan(self, app, patched_repo):
        repo = patched_repo

        task_id = await repo.create_task(
            task_type="digest",
            keyword="2026-06-21",
            ai_template="daily_digest",
            digest_date="2026-06-21",
        )
        await repo.save_ai_search_metadata(task_id, {
            "orchestrator_plan": {
                "event_diagnostics": {
                    "event_count": 4,
                    "merged_event_count": 1,
                    "duplicate_input_count": 2,
                    "multi_source_event_count": 1,
                    "max_sources_per_event": 3,
                    "source_diversity": 0.75,
                    "sample_events": [
                        {
                            "event_group_key": "openai responses api",
                            "category": "hot_trend",
                            "primary_url": "https://openai.com/index/responses-api/",
                            "source_domains": ["openai.com", "github.blog"],
                            "source_urls": [
                                "https://openai.com/index/responses-api/",
                                "https://github.blog/changelog/responses-api/",
                            ],
                            "item_count": 2,
                        }
                    ],
                }
            }
        })
        await repo.fail_task(task_id, "quality below threshold")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"/digests/task/{task_id}")

        assert resp.status_code == 200
        data = resp.json()
        diagnostics = data["orchestrator_plan"]["event_diagnostics"]
        assert diagnostics["event_count"] == 4
        assert diagnostics["merged_event_count"] == 1
        assert diagnostics["sample_events"][0]["source_domains"] == ["openai.com", "github.blog"]

    @pytest.mark.asyncio
    async def test_digest_task_returns_optimization_action_outcome_from_orchestrator_plan(self, app, patched_repo):
        repo = patched_repo

        task_id = await repo.create_task(
            task_type="digest",
            keyword="2026-06-22",
            ai_template="daily_digest",
            digest_date="2026-06-22",
        )
        await repo.save_ai_search_metadata(task_id, {
            "orchestrator_plan": {
                "optimization_action_outcome": {
                    "applied": True,
                    "digest_date": "2026-06-22",
                    "verdict": "positive",
                    "action_snapshot": {
                        "confidence": "medium",
                        "source_id_skip_count": 1,
                        "source_id_deprioritize_count": 2,
                        "source_url_skip_count": 0,
                        "source_url_deprioritize_count": 1,
                        "boost_sections": ["open_source"],
                        "reasons": ["last run low quality"],
                        "safety": {"applied": ["min_section_source_count"]},
                    },
                    "result": {
                        "overall_score": 0.82,
                        "section_fill_ratio": 0.9,
                        "section_result_counts": {"open_source": 4},
                        "saved_to_kb": True,
                    },
                    "suggestions": ["keep current source feedback guardrails"],
                }
            }
        })
        await repo.fail_task(task_id, "quality below threshold")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"/digests/task/{task_id}")

        assert resp.status_code == 200
        data = resp.json()
        outcome = data["orchestrator_plan"]["optimization_action_outcome"]
        assert outcome["applied"] is True
        assert outcome["verdict"] == "positive"
        assert outcome["action_snapshot"]["source_id_skip_count"] == 1
        assert outcome["result"]["section_fill_ratio"] == 0.9


# ============== GET /digests/config/sections ==============

class TestDigestSectionsConfig:
    @pytest.mark.asyncio
    async def test_returns_default_sections(self, app, patched_repo):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/digests/config/sections")
        assert resp.status_code == 200
        data = resp.json()
        assert "sections" in data
        assert len(data["sections"]) >= 3
        # 验证板块结构有效
        assert all("keyword" in s for s in data["sections"])

    @pytest.mark.asyncio
    async def test_sections_cache_can_be_invalidated(self, monkeypatch):
        from standalone import task_executor

        task_executor.invalidate_digest_sections_cache()
        calls = {"count": 0}

        async def fake_fetch_sections():
            calls["count"] += 1
            return [{"name": f"section-{calls['count']}", "keyword": "python"}]

        monkeypatch.setattr(task_executor, "_fetch_digest_sections", fake_fetch_sections)

        first = await task_executor.get_digest_sections()
        second = await task_executor.get_digest_sections()
        task_executor.invalidate_digest_sections_cache()
        third = await task_executor.get_digest_sections()

        assert calls["count"] == 2
        assert first == second
        assert third[0]["name"] == "section-2"

        task_executor.invalidate_digest_sections_cache()

    @pytest.mark.asyncio
    async def test_config_refresh_invalidates_sections_and_refreshes_source_schedules(self, app, monkeypatch):
        from standalone import backend_config, scheduler, task_executor

        calls = {"refresh": 0, "schedules": 0, "invalidate": 0}

        async def fake_backend_refresh():
            calls["refresh"] += 1
            return {"digest.enabled": "true"}

        async def fake_refresh_source_schedules():
            calls["schedules"] += 1

        def fake_invalidate():
            calls["invalidate"] += 1

        monkeypatch.setattr(backend_config, "refresh", fake_backend_refresh)
        monkeypatch.setattr(scheduler, "refresh_source_schedules", fake_refresh_source_schedules)
        monkeypatch.setattr(task_executor, "invalidate_digest_sections_cache", fake_invalidate)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post("/config/refresh")

        assert resp.status_code == 200
        assert calls == {"refresh": 1, "schedules": 1, "invalidate": 1}
