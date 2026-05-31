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
        # list_digests only returns tasks with ai_title set
        await repo.save_ai_results(
            digest_id, ai_title="Test Digest", ai_summary="s", ai_key_points=[],
            ai_tags=[], ai_category="tech_article", ai_full_content="c",
            ai_duration=1, ai_tokens_used=0,
        )

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
        assert resp.json()["id"] == task_id
        assert resp.json()["digest_date"] == "2026-05-09"


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
