"""CRUD 端点集成测试

使用 FastAPI TestClient 测试 routes.py 的核心端点：
- POST /api/v1/tasks 创建任务
- GET /api/v1/tasks 列表查询（分页/过滤）
- GET /api/v1/tasks/{id} 任务详情
- DELETE /api/v1/tasks/{id} 删除任务
- POST /api/v1/tasks/{id}/retry 重试
- GET /api/v1/config/ai AI配置状态
- GET /api/v1/stats 统计信息
"""

import os
import sys
import json
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from contextlib import asynccontextmanager

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from fastapi import FastAPI
from fastapi.testclient import TestClient

from standalone.models import TaskStatus
from standalone import repository as repo


# ============== Fixtures ==============

@pytest.fixture
def app_client(mem_db):
    """创建带路由和 DB mock 的测试客户端"""

    @asynccontextmanager
    async def _mock_get_db():
        yield mem_db

    orig_db = repo.get_db
    repo.get_db = _mock_get_db

    app = FastAPI()
    from standalone.routes import router
    app.include_router(router, prefix="/api/v1")

    client = TestClient(app)
    yield client

    repo.get_db = orig_db


async def _create_task_directly(db, *, task_type="single", status=TaskStatus.COMPLETED,
                                 source_url=None, keyword=None, ai_title=None,
                                 ai_summary=None, ai_tags=None, ai_full_content=None,
                                 total_pages=1, completed_pages=1):
    """直接在 DB 中插入任务"""
    await db.execute(
        """INSERT INTO crawl_task
           (task_type, source_url, keyword, status, total_pages, completed_pages,
            ai_title, ai_summary, ai_tags, ai_full_content, ai_template)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'tech_summary')""",
        (task_type, source_url, keyword, status, total_pages, completed_pages,
         ai_title, ai_summary, ai_tags, ai_full_content),
    )
    await db.commit()
    cursor = await db.execute("SELECT last_insert_rowid()")
    row = await cursor.fetchone()
    return row[0]


# ============== Create Task Tests ==============

class TestCreateTask:
    """POST /api/v1/tasks"""

    def test_create_single_task(self, app_client, mem_db):
        """创建单页爬取任务"""
        with patch.object(repo, "create_task", new_callable=AsyncMock, return_value=1) as mock_create, \
             patch("standalone.routes.executor") as mock_executor:
            mock_executor.submit = AsyncMock()

            resp = app_client.post("/api/v1/tasks", json={
                "task_type": "single",
                "url": "https://example.com/article",
            })

        assert resp.status_code == 201
        data = resp.json()
        assert data["id"] == 1
        assert data["task_type"] == "single"
        assert data["status"] == TaskStatus.PENDING

    def test_create_keyword_task(self, app_client, mem_db):
        """创建关键词搜索任务"""
        with patch.object(repo, "create_task", new_callable=AsyncMock, return_value=2) as mock_create, \
             patch("standalone.routes.executor") as mock_executor:
            mock_executor.submit = AsyncMock()

            resp = app_client.post("/api/v1/tasks", json={
                "task_type": "keyword",
                "keyword": "python async",
            })

        assert resp.status_code == 201
        assert resp.json()["id"] == 2

    def test_create_single_without_url_returns_400(self, app_client, mem_db):
        """single 类型缺少 url 返回 400"""
        resp = app_client.post("/api/v1/tasks", json={
            "task_type": "single",
        })
        assert resp.status_code == 400

    def test_create_keyword_without_keyword_returns_400(self, app_client, mem_db):
        """keyword 类型缺少 keyword 返回 400"""
        resp = app_client.post("/api/v1/tasks", json={
            "task_type": "keyword",
        })
        assert resp.status_code == 400

    def test_create_invalid_task_type_returns_422(self, app_client, mem_db):
        """无效任务类型返回 422"""
        resp = app_client.post("/api/v1/tasks", json={
            "task_type": "invalid_type",
            "url": "https://example.com",
        })
        assert resp.status_code == 422

    def test_create_task_with_ai_template(self, app_client, mem_db):
        """创建时指定 ai_template"""
        with patch.object(repo, "create_task", new_callable=AsyncMock, return_value=3) as mock_create, \
             patch("standalone.routes.executor") as mock_executor:
            mock_executor.submit = AsyncMock()

            resp = app_client.post("/api/v1/tasks", json={
                "task_type": "single",
                "url": "https://example.com/article",
                "ai_template": "tutorial",
            })

        assert resp.status_code == 201
        call_args = mock_create.call_args
        assert call_args.kwargs.get("ai_template") == "tutorial" or \
               call_args[1].get("ai_template") == "tutorial"


# ============== List Tasks Tests ==============

class TestListTasks:
    """GET /api/v1/tasks"""

    @pytest.mark.asyncio
    async def test_list_tasks_default_pagination(self, app_client, mem_db):
        """默认分页查询"""
        tid1 = await _create_task_directly(mem_db, task_type="single", ai_title="Task 1")
        tid2 = await _create_task_directly(mem_db, task_type="keyword", keyword="test", ai_title="Task 2")

        resp = app_client.get("/api/v1/tasks")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert data["page"] == 1
        assert len(data["records"]) == 2

    @pytest.mark.asyncio
    async def test_list_tasks_with_status_filter(self, app_client, mem_db):
        """按状态过滤"""
        await _create_task_directly(mem_db, status=TaskStatus.COMPLETED)
        await _create_task_directly(mem_db, status=TaskStatus.FAILED)

        resp = app_client.get("/api/v1/tasks", params={"status": TaskStatus.COMPLETED})

        data = resp.json()
        assert data["total"] == 1
        assert data["records"][0]["status"] == TaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_list_tasks_with_type_filter(self, app_client, mem_db):
        """按任务类型过滤"""
        await _create_task_directly(mem_db, task_type="single")
        await _create_task_directly(mem_db, task_type="keyword", keyword="test")

        resp = app_client.get("/api/v1/tasks", params={"task_type": "keyword"})

        data = resp.json()
        assert data["total"] == 1
        assert data["records"][0]["task_type"] == "keyword"

    @pytest.mark.asyncio
    async def test_list_tasks_enriched_with_labels(self, app_client, mem_db):
        """返回结果包含中文标签和进度百分比"""
        await _create_task_directly(mem_db, task_type="single", ai_title="Test",
                                     total_pages=5, completed_pages=3)

        resp = app_client.get("/api/v1/tasks")
        record = resp.json()["records"][0]

        assert record["task_type_label"] == "单页爬取"
        assert record["status_label"] == "已完成"
        assert record["progress_percent"] == 60  # 3/5 * 100

    @pytest.mark.asyncio
    async def test_list_tasks_pagination(self, app_client, mem_db):
        """分页参数"""
        for i in range(5):
            await _create_task_directly(mem_db, ai_title=f"Task {i}")

        resp = app_client.get("/api/v1/tasks", params={"page": 1, "size": 2})
        data = resp.json()
        assert data["total"] == 5
        assert len(data["records"]) == 2
        assert data["page"] == 1
        assert data["size"] == 2


# ============== Get Task Detail Tests ==============

class TestGetTaskDetail:
    """GET /api/v1/tasks/{id}"""

    @pytest.mark.asyncio
    async def test_get_task_detail(self, app_client, mem_db):
        """查询任务详情含 AI 结果富化"""
        tid = await _create_task_directly(
            mem_db, task_type="keyword", keyword="docker",
            ai_title="Docker Guide", ai_summary="Summary",
            ai_tags=json.dumps(["docker", "container"]),
        )

        resp = app_client.get(f"/api/v1/tasks/{tid}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == tid
        assert data["ai_title"] == "Docker Guide"
        assert data["ai_tags"] == ["docker", "container"]  # parsed from JSON
        assert data["ai_template_label"] == "技术摘要"

    def test_get_nonexistent_task_returns_404(self, app_client, mem_db):
        """查询不存在的任务返回 404"""
        resp = app_client.get("/api/v1/tasks/99999")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_ai_key_points_parsed(self, app_client, mem_db):
        """ai_key_points JSON 字符串被解析为数组"""
        tid = await _create_task_directly(mem_db, ai_title="Test")

        await mem_db.execute(
            "UPDATE crawl_task SET ai_key_points = ? WHERE id = ?",
            (json.dumps(["point1", "point2"]), tid),
        )
        await mem_db.commit()

        resp = app_client.get(f"/api/v1/tasks/{tid}")
        data = resp.json()
        assert data["ai_key_points"] == ["point1", "point2"]


# ============== Delete Task Tests ==============

class TestDeleteTask:
    """DELETE /api/v1/tasks/{id}"""

    @pytest.mark.asyncio
    async def test_delete_completed_task(self, app_client, mem_db):
        """删除已完成的任务"""
        tid = await _create_task_directly(mem_db, status=TaskStatus.COMPLETED)

        resp = app_client.delete(f"/api/v1/tasks/{tid}")

        assert resp.status_code == 200
        assert "已删除" in resp.json()["message"]

    @pytest.mark.asyncio
    async def test_delete_running_task_returns_400(self, app_client, mem_db):
        """不能删除正在处理的任务"""
        tid = await _create_task_directly(mem_db, status=TaskStatus.CRAWLING)

        resp = app_client.delete(f"/api/v1/tasks/{tid}")

        assert resp.status_code == 400
        assert "处理中" in resp.json()["detail"]

    def test_delete_nonexistent_task_returns_404(self, app_client, mem_db):
        """删除不存在的任务返回 404"""
        resp = app_client.delete("/api/v1/tasks/99999")
        assert resp.status_code == 404


# ============== Retry Task Tests ==============

class TestRetryTask:
    """POST /api/v1/tasks/{id}/retry"""

    @pytest.mark.asyncio
    async def test_retry_failed_task(self, app_client, mem_db):
        """重试失败的任务"""
        tid = await _create_task_directly(mem_db, status=TaskStatus.FAILED)

        with patch.object(repo, "reset_task_for_retry", new_callable=AsyncMock) as mock_reset, \
             patch("standalone.routes.executor") as mock_executor:
            mock_executor.submit = AsyncMock()

            resp = app_client.post(f"/api/v1/tasks/{tid}/retry")

        assert resp.status_code == 200
        assert resp.json()["status"] == TaskStatus.PENDING
        mock_reset.assert_called_once_with(tid)

    @pytest.mark.asyncio
    async def test_retry_completed_task_returns_400(self, app_client, mem_db):
        """不能重试已完成的任务"""
        tid = await _create_task_directly(mem_db, status=TaskStatus.COMPLETED)

        resp = app_client.post(f"/api/v1/tasks/{tid}/retry")

        assert resp.status_code == 400

    def test_retry_nonexistent_task_returns_404(self, app_client, mem_db):
        """重试不存在的任务返回 404"""
        resp = app_client.post("/api/v1/tasks/99999/retry")
        assert resp.status_code == 404


# ============== Config & Stats Tests ==============

class TestConfigAndStats:
    """GET /api/v1/config/ai & GET /api/v1/stats"""

    def test_ai_config_unavailable(self, app_client, mem_db):
        """AI 未配置时返回 unavailable"""
        with patch("ai.content_organizer._settings", MagicMock(is_configured=False)):
            resp = app_client.get("/api/v1/config/ai")

        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is False
        assert data["model"] is None

    @pytest.mark.asyncio
    async def test_stats_endpoint(self, app_client, mem_db):
        """统计信息端点"""
        await _create_task_directly(mem_db, status=TaskStatus.COMPLETED)
        await _create_task_directly(mem_db, status=TaskStatus.FAILED)

        resp = app_client.get("/api/v1/stats")

        assert resp.status_code == 200
        data = resp.json()
        assert "total_tasks" in data


# ============== Task Pages Tests ==============

class TestTaskPages:
    """GET /api/v1/tasks/{id}/pages"""

    @pytest.mark.asyncio
    async def test_get_task_pages(self, app_client, mem_db):
        """查询任务页面列表"""
        tid = await _create_task_directly(mem_db, task_type="deep")

        import hashlib
        for i in range(3):
            url = f"https://example.com/page{i}"
            await mem_db.execute(
                """INSERT INTO crawl_page
                   (task_id, url, page_title, crawl_status, word_count, url_hash, sort_order)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (tid, url, f"Page {i}", 2 if i < 2 else 3, 100 * i,
                 hashlib.sha256(url.encode()).hexdigest(), i),
            )
        await mem_db.commit()

        resp = app_client.get(f"/api/v1/tasks/{tid}/pages")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert data["pages"][0]["status_label"] == "已完成"
        assert data["pages"][2]["status_label"] == "失败"

    def test_get_pages_nonexistent_task_returns_404(self, app_client, mem_db):
        """查询不存在任务的页面返回 404"""
        resp = app_client.get("/api/v1/tasks/99999/pages")
        assert resp.status_code == 404
