"""Routes 层验证测试：SSRF 防护、请求验证、_enrich_task 富化、Repository 安全性

覆盖：
1. _is_private_url SSRF 防护（IPv4/IPv6/域名）
2. CreateTaskRequest Pydantic 验证（task_type / search_engine / time_range）
3. _enrich_task 字段富化（progress_percent / ai_key_points JSON / status_label）
4. Repository create_task 返回 lastrowid
5. Repository 事务安全性（delete_task 不存在的任务 / reset_task_for_retry 清除 AI 字段）
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

from standalone.models import TaskStatus, TASK_TYPE_LABELS, AI_TEMPLATE_LABELS
from standalone.routes import _is_private_url, _enrich_task, CreateTaskRequest
from standalone import repository as repo


# ============================================================
# 1. SSRF Protection — _is_private_url
# ============================================================

class TestIsPrivateUrl:
    """SSRF 防护：私有地址检测"""

    # --- IPv4 loopback ---
    def test_localhost_blocked(self):
        assert _is_private_url("http://localhost/admin") is True

    def test_localhost_localdomain_blocked(self):
        assert _is_private_url("http://localhost.localdomain/secret") is True

    def test_127_0_0_1_blocked(self):
        assert _is_private_url("http://127.0.0.1/admin") is True

    def test_127_255_255_255_blocked(self):
        """整个 127.0.0.0/8 都是 loopback"""
        assert _is_private_url("http://127.255.255.255/admin") is True

    # --- IPv4 RFC1918 private ---
    def test_10_x_x_x_blocked(self):
        assert _is_private_url("http://10.0.0.1/internal") is True

    def test_10_255_255_255_blocked(self):
        assert _is_private_url("http://10.255.255.255/internal") is True

    def test_172_16_x_x_blocked(self):
        assert _is_private_url("http://172.16.0.1/internal") is True

    def test_172_31_255_255_blocked(self):
        """172.16.0.0/12 范围上界"""
        assert _is_private_url("http://172.31.255.255/internal") is True

    def test_172_15_x_x_allowed(self):
        """172.15.x.x 不在 172.16.0.0/12 范围内"""
        assert _is_private_url("http://172.15.0.1/public") is False

    def test_172_32_x_x_allowed(self):
        """172.32.x.x 不在 172.16.0.0/12 范围内"""
        assert _is_private_url("http://172.32.0.1/public") is False

    def test_192_168_x_x_blocked(self):
        assert _is_private_url("http://192.168.1.1/router") is True

    def test_192_168_0_100_blocked(self):
        assert _is_private_url("http://192.168.0.100/nas") is True

    # --- IPv4 link-local ---
    def test_169_254_x_x_blocked(self):
        """169.254.0.0/16 link-local"""
        assert _is_private_url("http://169.254.1.1/metadata") is True

    # --- IPv6 ---
    def test_ipv6_loopback_blocked(self):
        assert _is_private_url("http://[::1]/admin") is True

    def test_ipv6_private_fc00_blocked(self):
        """IPv6 ULA fc00::/7"""
        assert _is_private_url("http://[fc00::1]/internal") is True

    def test_ipv6_private_fd00_blocked(self):
        """IPv6 ULA fd00::/7"""
        assert _is_private_url("http://[fd12:3456::1]/internal") is True

    def test_ipv6_fe80_link_local_blocked(self):
        """IPv6 link-local fe80::/10"""
        assert _is_private_url("http://[fe80::1]/local") is True

    def test_ipv6_loopback_long_form_blocked(self):
        """IPv6 loopback 完整形式"""
        assert _is_private_url("http://[0:0:0:0:0:0:0:1]/admin") is True

    # --- Public domains → allowed ---
    def test_google_com_allowed(self):
        assert _is_private_url("https://google.com/search") is False

    def test_github_com_allowed(self):
        assert _is_private_url("https://github.com/repo") is False

    def test_example_com_allowed(self):
        assert _is_private_url("https://example.com/page") is False

    def test_ip_8_8_8_8_allowed(self):
        """Google Public DNS"""
        assert _is_private_url("http://8.8.8.8/dns") is False

    def test_ip_1_1_1_1_allowed(self):
        """Cloudflare Public DNS"""
        assert _is_private_url("http://1.1.1.1/dns") is False

    # --- Non-IP domain names → allowed ---
    def test_arbitrary_domain_allowed(self):
        assert _is_private_url("https://my-app.example.com/api") is False

    def test_subdomain_allowed(self):
        assert _is_private_url("https://sub.domain.org/page") is False

    # --- .local mDNS ---
    def test_dot_local_blocked(self):
        assert _is_private_url("http://myprinter.local/status") is True

    # --- Edge cases ---
    def test_empty_hostname(self):
        """空主机名不应判定为私有"""
        assert _is_private_url("about:blank") is False

    def test_none_hostname(self):
        """无 host 的 URL"""
        assert _is_private_url("data:text/plain,hello") is False

    def test_https_scheme_private_blocked(self):
        """HTTPS 不影响私有地址判定"""
        assert _is_private_url("https://192.168.1.1/admin") is True

    def test_nonstandard_port_private_blocked(self):
        """非标准端口不影响私有地址判定"""
        assert _is_private_url("http://10.0.0.1:8080/internal") is True


# ============================================================
# 2. CreateTaskRequest Validation (via API endpoints)
# ============================================================

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


class TestCreateTaskValidation:
    """CreateTaskRequest Pydantic 验证"""

    def test_valid_single_task_with_url(self, app_client):
        """合法 single 任务 + url → 201"""
        mock_executor = MagicMock()
        mock_executor.submit = AsyncMock()
        with patch.object(repo, "create_task", new_callable=AsyncMock, return_value=1), \
             patch("standalone.routes.executor", mock_executor):
            resp = app_client.post("/api/v1/tasks", json={
                "task_type": "single",
                "url": "https://example.com/article",
            })
        assert resp.status_code == 201

    def test_valid_deep_task_with_url(self, app_client):
        """合法 deep 任务 + url → 201"""
        mock_executor = MagicMock()
        mock_executor.submit = AsyncMock()
        with patch.object(repo, "create_task", new_callable=AsyncMock, return_value=2), \
             patch("standalone.routes.executor", mock_executor):
            resp = app_client.post("/api/v1/tasks", json={
                "task_type": "deep",
                "url": "https://example.com/docs",
                "max_depth": 2,
            })
        assert resp.status_code == 201

    def test_valid_keyword_task(self, app_client):
        """合法 keyword 任务 → 201"""
        mock_executor = MagicMock()
        mock_executor.submit = AsyncMock()
        with patch.object(repo, "create_task", new_callable=AsyncMock, return_value=3), \
             patch("standalone.routes.executor", mock_executor):
            resp = app_client.post("/api/v1/tasks", json={
                "task_type": "keyword",
                "keyword": "python async",
            })
        assert resp.status_code == 201

    def test_single_without_url_returns_400(self, app_client):
        """single 类型缺少 url → 400"""
        resp = app_client.post("/api/v1/tasks", json={
            "task_type": "single",
        })
        assert resp.status_code == 400

    def test_deep_without_url_returns_400(self, app_client):
        """deep 类型缺少 url → 400"""
        resp = app_client.post("/api/v1/tasks", json={
            "task_type": "deep",
        })
        assert resp.status_code == 400

    def test_keyword_without_keyword_returns_400(self, app_client):
        """keyword 类型缺少 keyword → 400"""
        resp = app_client.post("/api/v1/tasks", json={
            "task_type": "keyword",
        })
        assert resp.status_code == 400

    def test_invalid_task_type_returns_422(self, app_client):
        """非法 task_type → 422"""
        resp = app_client.post("/api/v1/tasks", json={
            "task_type": "scrape",
            "url": "https://example.com",
        })
        assert resp.status_code == 422

    def test_empty_task_type_returns_422(self, app_client):
        """空 task_type → 422"""
        resp = app_client.post("/api/v1/tasks", json={
            "task_type": "",
            "url": "https://example.com",
        })
        assert resp.status_code == 422

    def test_invalid_search_engine_returns_422(self, app_client):
        """非法 search_engine → 422"""
        resp = app_client.post("/api/v1/tasks", json={
            "task_type": "keyword",
            "keyword": "test",
            "search_engine": "yahoo",
        })
        assert resp.status_code == 422

    def test_valid_search_engines_accepted(self, app_client):
        """所有合法搜索引擎均通过验证"""
        mock_executor = MagicMock()
        mock_executor.submit = AsyncMock()
        for engine in ("sogou", "bing", "baidu", "google"):
            with patch.object(repo, "create_task", new_callable=AsyncMock, return_value=10), \
                 patch("standalone.routes.executor", mock_executor):
                resp = app_client.post("/api/v1/tasks", json={
                    "task_type": "keyword",
                    "keyword": f"test-{engine}",
                    "search_engine": engine,
                })
            assert resp.status_code == 201, f"engine={engine} should be accepted"

    def test_invalid_time_range_returns_422(self, app_client):
        """非法 time_range → 422"""
        resp = app_client.post("/api/v1/tasks", json={
            "task_type": "keyword",
            "keyword": "test",
            "time_range": "decade",
        })
        assert resp.status_code == 422

    def test_valid_time_ranges_accepted(self, app_client):
        """所有合法 time_range 均通过验证"""
        mock_executor = MagicMock()
        mock_executor.submit = AsyncMock()
        for tr in ("day", "week", "month", "year", "all"):
            with patch.object(repo, "create_task", new_callable=AsyncMock, return_value=10), \
                 patch("standalone.routes.executor", mock_executor):
                resp = app_client.post("/api/v1/tasks", json={
                    "task_type": "keyword",
                    "keyword": f"test-{tr}",
                    "time_range": tr,
                })
            assert resp.status_code == 201, f"time_range={tr} should be accepted"

    def test_invalid_ai_template_returns_422(self, app_client):
        """非法 ai_template → 422"""
        resp = app_client.post("/api/v1/tasks", json={
            "task_type": "single",
            "url": "https://example.com",
            "ai_template": "invalid_template",
        })
        assert resp.status_code == 422

    def test_private_url_returns_400(self, app_client):
        """SSRF 防护：私有地址 → 400"""
        resp = app_client.post("/api/v1/tasks", json={
            "task_type": "single",
            "url": "http://192.168.1.1/admin",
        })
        assert resp.status_code == 400

    def test_private_url_localhost_returns_400(self, app_client):
        """SSRF 防护：localhost → 400"""
        resp = app_client.post("/api/v1/tasks", json={
            "task_type": "single",
            "url": "http://localhost:3000/api",
        })
        assert resp.status_code == 400

    def test_max_pages_exceeds_limit_returns_422(self, app_client):
        """max_pages 超过上限 → 422"""
        resp = app_client.post("/api/v1/tasks", json={
            "task_type": "single",
            "url": "https://example.com",
            "max_pages": 999,
        })
        assert resp.status_code == 422

    def test_max_depth_exceeds_limit_returns_422(self, app_client):
        """max_depth 超过上限 → 422"""
        resp = app_client.post("/api/v1/tasks", json={
            "task_type": "deep",
            "url": "https://example.com",
            "max_depth": 99,
        })
        assert resp.status_code == 422

    def test_max_pages_zero_returns_422(self, app_client):
        """max_pages=0 → 422 (ge=1)"""
        resp = app_client.post("/api/v1/tasks", json={
            "task_type": "single",
            "url": "https://example.com",
            "max_pages": 0,
        })
        assert resp.status_code == 422


# ============================================================
# 3. _enrich_task Field Enrichment
# ============================================================

class TestEnrichTask:
    """_enrich_task 辅助函数单元测试"""

    # --- progress_percent ---
    def test_progress_60_percent(self):
        task = {"total_pages": 5, "completed_pages": 3, "task_type": "single", "status": 3}
        result = _enrich_task(task)
        assert result["progress_percent"] == 60

    def test_progress_100_percent(self):
        task = {"total_pages": 10, "completed_pages": 10, "task_type": "single", "status": 3}
        result = _enrich_task(task)
        assert result["progress_percent"] == 100

    def test_progress_0_when_total_is_zero(self):
        task = {"total_pages": 0, "completed_pages": 0, "task_type": "single", "status": 0}
        result = _enrich_task(task)
        assert result["progress_percent"] == 0

    def test_progress_0_when_total_is_none(self):
        task = {"total_pages": None, "completed_pages": 0, "task_type": "single", "status": 0}
        result = _enrich_task(task)
        assert result["progress_percent"] == 0

    def test_progress_33_percent_truncates(self):
        """1/3 * 100 = 33.33 → int(33.33) = 33"""
        task = {"total_pages": 3, "completed_pages": 1, "task_type": "single", "status": 1}
        result = _enrich_task(task)
        assert result["progress_percent"] == 33

    def test_progress_does_not_modify_original(self):
        """_enrich_task 不应修改原始 dict"""
        original = {"total_pages": 5, "completed_pages": 2, "task_type": "single", "status": 1}
        _enrich_task(original)
        assert "progress_percent" not in original
        assert "status_label" not in original

    # --- ai_key_points JSON parsing ---
    def test_ai_key_points_parsed_from_json(self):
        """ai_key_points 字符串 → list"""
        task = {
            "total_pages": 1, "completed_pages": 1,
            "task_type": "single", "status": 3,
            "ai_key_points": '["point1", "point2", "point3"]',
        }
        result = _enrich_task(task)
        assert result["ai_key_points"] == ["point1", "point2", "point3"]

    def test_ai_tags_parsed_from_json(self):
        """ai_tags 字符串 → list"""
        task = {
            "total_pages": 1, "completed_pages": 1,
            "task_type": "single", "status": 3,
            "ai_tags": '["java", "spring", "boot"]',
        }
        result = _enrich_task(task)
        assert result["ai_tags"] == ["java", "spring", "boot"]

    def test_ai_key_points_already_list(self):
        """已经是 list 的不再二次解析"""
        task = {
            "total_pages": 1, "completed_pages": 1,
            "task_type": "single", "status": 3,
            "ai_key_points": ["already", "a", "list"],
        }
        result = _enrich_task(task)
        assert result["ai_key_points"] == ["already", "a", "list"]

    def test_ai_key_points_invalid_json_left_as_string(self):
        """非法 JSON 不解析，保持原字符串"""
        task = {
            "total_pages": 1, "completed_pages": 1,
            "task_type": "single", "status": 3,
            "ai_key_points": "not valid json [{",
        }
        result = _enrich_task(task)
        assert result["ai_key_points"] == "not valid json [{"

    def test_ai_key_points_null_not_parsed(self):
        """None 值不触发解析"""
        task = {
            "total_pages": 1, "completed_pages": 1,
            "task_type": "single", "status": 3,
            "ai_key_points": None,
        }
        result = _enrich_task(task)
        assert result["ai_key_points"] is None

    def test_ai_search_metadata_parsed(self):
        """ai_search_metadata 字符串 → dict"""
        meta = {"originalKeyword": "docker", "optimizedKeyword": "docker 容器"}
        task = {
            "total_pages": 1, "completed_pages": 1,
            "task_type": "keyword", "status": 3,
            "ai_search_metadata": json.dumps(meta),
        }
        result = _enrich_task(task)
        assert result["ai_search_metadata"]["originalKeyword"] == "docker"

    # --- status_label mapping ---
    def test_status_label_pending(self):
        task = {"total_pages": 0, "completed_pages": 0, "task_type": "single", "status": 0}
        result = _enrich_task(task)
        assert result["status_label"] == "待处理"

    def test_status_label_crawling(self):
        task = {"total_pages": 0, "completed_pages": 0, "task_type": "single", "status": 1}
        result = _enrich_task(task)
        assert result["status_label"] == "爬取中"

    def test_status_label_processing(self):
        task = {"total_pages": 0, "completed_pages": 0, "task_type": "single", "status": 2}
        result = _enrich_task(task)
        assert result["status_label"] == "AI整理中"

    def test_status_label_completed(self):
        task = {"total_pages": 1, "completed_pages": 1, "task_type": "single", "status": 3}
        result = _enrich_task(task)
        assert result["status_label"] == "已完成"

    def test_status_label_failed(self):
        task = {"total_pages": 0, "completed_pages": 0, "task_type": "single", "status": 4}
        result = _enrich_task(task)
        assert result["status_label"] == "失败"

    def test_status_label_unknown(self):
        """未知状态码 → "未知" """
        task = {"total_pages": 0, "completed_pages": 0, "task_type": "single", "status": 99}
        result = _enrich_task(task)
        assert result["status_label"] == "未知"

    # --- task_type_label ---
    def test_task_type_label_single(self):
        task = {"total_pages": 1, "completed_pages": 1, "task_type": "single", "status": 3}
        result = _enrich_task(task)
        assert result["task_type_label"] == "单页爬取"

    def test_task_type_label_keyword(self):
        task = {"total_pages": 1, "completed_pages": 1, "task_type": "keyword", "status": 3}
        result = _enrich_task(task)
        assert result["task_type_label"] == "关键词搜索"

    def test_task_type_label_digest(self):
        task = {"total_pages": 1, "completed_pages": 1, "task_type": "digest", "status": 3}
        result = _enrich_task(task)
        assert result["task_type_label"] == "技术日报"

    def test_task_type_label_unknown_falls_through(self):
        """未知类型 → 使用原值"""
        task = {"total_pages": 1, "completed_pages": 1, "task_type": "custom", "status": 3}
        result = _enrich_task(task)
        assert result["task_type_label"] == "custom"

    # --- ai_template_label ---
    def test_ai_template_label_default(self):
        task = {"total_pages": 1, "completed_pages": 1, "task_type": "single", "status": 3}
        result = _enrich_task(task)
        assert result["ai_template_label"] == "技术摘要"

    def test_ai_template_label_tutorial(self):
        task = {
            "total_pages": 1, "completed_pages": 1,
            "task_type": "single", "status": 3,
            "ai_template": "tutorial",
        }
        result = _enrich_task(task)
        assert result["ai_template_label"] == "教程提炼"

    def test_ai_template_label_comparison(self):
        task = {
            "total_pages": 1, "completed_pages": 1,
            "task_type": "single", "status": 3,
            "ai_template": "comparison",
        }
        result = _enrich_task(task)
        assert result["ai_template_label"] == "对比分析"

    def test_ai_template_label_knowledge_report(self):
        task = {
            "total_pages": 1, "completed_pages": 1,
            "task_type": "single", "status": 3,
            "ai_template": "knowledge_report",
        }
        result = _enrich_task(task)
        assert result["ai_template_label"] == "知识报告"

    def test_ai_template_label_daily_digest(self):
        task = {
            "total_pages": 1, "completed_pages": 1,
            "task_type": "digest", "status": 3,
            "ai_template": "daily_digest",
        }
        result = _enrich_task(task)
        assert result["ai_template_label"] == "技术日报"


# ============================================================
# 4. Repository create_task returns valid ID (lastrowid)
# ============================================================

class TestRepositoryCreateTask:
    """验证 create_task 使用 cursor.lastrowid 而非 last_insert_rowid()"""

    @pytest.mark.asyncio
    async def test_create_task_returns_incrementing_id(self, mem_db):
        """连续创建返回递增的 ID"""
        from standalone.db import get_db

        # Patch get_db to yield our in-memory db
        @asynccontextmanager
        async def _mock_get_db():
            yield mem_db

        orig = repo.get_db
        repo.get_db = _mock_get_db
        try:
            id1 = await repo.create_task(
                task_type="single",
                source_url="https://example.com/1",
            )
            id2 = await repo.create_task(
                task_type="keyword",
                keyword="docker",
            )
            id3 = await repo.create_task(
                task_type="deep",
                source_url="https://example.com/docs",
            )
        finally:
            repo.get_db = orig

        assert id1 >= 1
        assert id2 == id1 + 1
        assert id3 == id1 + 2

    @pytest.mark.asyncio
    async def test_create_task_id_matches_db_row(self, mem_db):
        """返回的 ID 能在 DB 中查到对应记录"""
        from standalone.db import get_db

        @asynccontextmanager
        async def _mock_get_db():
            yield mem_db

        orig = repo.get_db
        repo.get_db = _mock_get_db
        try:
            task_id = await repo.create_task(
                task_type="single",
                source_url="https://example.com/article",
                search_engine="sogou",
                max_depth=2,
                max_pages=5,
                ai_template="tutorial",
                time_range="month",
            )
        finally:
            repo.get_db = orig

        cursor = await mem_db.execute("SELECT * FROM crawl_task WHERE id = ?", (task_id,))
        row = dict(await cursor.fetchone())

        assert row["id"] == task_id
        assert row["task_type"] == "single"
        assert row["source_url"] == "https://example.com/article"
        assert row["search_engine"] == "sogou"
        assert row["max_depth"] == 2
        assert row["max_pages"] == 5
        assert row["ai_template"] == "tutorial"
        assert row["time_range"] == "month"


# ============================================================
# 5. Repository transaction safety
# ============================================================

class TestRepositoryTransactionSafety:
    """Repository 事务安全性"""

    @pytest.mark.asyncio
    async def test_delete_task_on_nonexistent_does_not_raise(self, mem_db):
        """删除不存在的任务不抛异常（幂等）"""
        @asynccontextmanager
        async def _mock_get_db():
            yield mem_db

        orig = repo.get_db
        repo.get_db = _mock_get_db
        try:
            # 不应抛异常
            await repo.delete_task(99999)
        finally:
            repo.get_db = orig

        # 验证 DB 没有多余数据
        cursor = await mem_db.execute("SELECT COUNT(*) FROM crawl_task")
        count = (await cursor.fetchone())[0]
        assert count == 0

    @pytest.mark.asyncio
    async def test_delete_task_removes_pages_and_task(self, mem_db):
        """删除任务时级联删除关联页面"""
        # 手动插入任务 + 页面
        await mem_db.execute(
            "INSERT INTO crawl_task (task_type, status, total_pages, completed_pages) VALUES (?, ?, ?, ?)",
            ("single", TaskStatus.COMPLETED, 2, 2),
        )
        await mem_db.commit()
        cursor = await mem_db.execute("SELECT last_insert_rowid()")
        task_id = (await cursor.fetchone())[0]

        import hashlib
        for i in range(2):
            url = f"https://example.com/page{i}"
            await mem_db.execute(
                """INSERT INTO crawl_page
                   (task_id, url, crawl_status, url_hash, sort_order)
                   VALUES (?, ?, ?, ?, ?)""",
                (task_id, url, 2, hashlib.sha256(url.encode()).hexdigest(), i),
            )
        await mem_db.commit()

        # 执行删除
        @asynccontextmanager
        async def _mock_get_db():
            yield mem_db

        orig = repo.get_db
        repo.get_db = _mock_get_db
        try:
            await repo.delete_task(task_id)
        finally:
            repo.get_db = orig

        # 验证任务和页面都已删除
        cursor = await mem_db.execute("SELECT COUNT(*) FROM crawl_task WHERE id = ?", (task_id,))
        assert (await cursor.fetchone())[0] == 0

        cursor = await mem_db.execute("SELECT COUNT(*) FROM crawl_page WHERE task_id = ?", (task_id,))
        assert (await cursor.fetchone())[0] == 0

    @pytest.mark.asyncio
    async def test_reset_task_for_retry_clears_all_ai_fields(self, mem_db):
        """reset_task_for_retry 清除所有 AI 字段"""
        # 创建一个带完整 AI 结果的失败任务
        await mem_db.execute(
            """INSERT INTO crawl_task
               (task_type, status, ai_title, ai_summary, ai_key_points, ai_tags,
                ai_category, ai_full_content, ai_duration, ai_tokens_used,
                ai_error_message, ai_search_metadata, error_message,
                crawl_duration, total_word_count, completed_pages)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("keyword", TaskStatus.FAILED,
             "AI Title", "AI Summary", '["p1"]', '["t1"]',
             "programming", "Full content", 1500, 800,
             "AI error msg", '{"original":"docker"}', "Crawl failed",
             5000, 3000, 5),
        )
        await mem_db.commit()
        cursor = await mem_db.execute("SELECT last_insert_rowid()")
        task_id = (await cursor.fetchone())[0]

        # 执行 reset
        @asynccontextmanager
        async def _mock_get_db():
            yield mem_db

        orig = repo.get_db
        repo.get_db = _mock_get_db
        try:
            await repo.reset_task_for_retry(task_id)
        finally:
            repo.get_db = orig

        # 验证所有字段已清除
        cursor = await mem_db.execute("SELECT * FROM crawl_task WHERE id = ?", (task_id,))
        row = dict(await cursor.fetchone())

        assert row["status"] == TaskStatus.PENDING
        # AI 字段全部为 None
        assert row["ai_title"] is None
        assert row["ai_summary"] is None
        assert row["ai_key_points"] is None
        assert row["ai_tags"] is None
        assert row["ai_category"] is None
        assert row["ai_full_content"] is None
        assert row["ai_duration"] is None
        assert row["ai_tokens_used"] is None
        assert row["ai_error_message"] is None
        assert row["ai_search_metadata"] is None
        # 爬取统计也已清除
        assert row["error_message"] is None
        assert row["crawl_duration"] is None
        assert row["total_word_count"] is None
        assert row["completed_pages"] == 0

    @pytest.mark.asyncio
    async def test_reset_task_for_retry_on_nonexistent_does_not_raise(self, mem_db):
        """重置不存在的任务不抛异常"""
        @asynccontextmanager
        async def _mock_get_db():
            yield mem_db

        orig = repo.get_db
        repo.get_db = _mock_get_db
        try:
            # 不应抛异常（UPDATE 0 行是合法操作）
            await repo.reset_task_for_retry(99999)
        finally:
            repo.get_db = orig

    @pytest.mark.asyncio
    async def test_reset_task_clears_digest_fields(self, mem_db):
        """reset_task_for_retry 也清除日报字段"""
        await mem_db.execute(
            """INSERT INTO crawl_task
               (task_type, status, ai_title, digest_date, digest_highlight)
               VALUES (?, ?, ?, ?, ?)""",
            ("digest", TaskStatus.FAILED, "Daily Digest", "2026-05-08", "highlight text"),
        )
        await mem_db.commit()
        cursor = await mem_db.execute("SELECT last_insert_rowid()")
        task_id = (await cursor.fetchone())[0]

        @asynccontextmanager
        async def _mock_get_db():
            yield mem_db

        orig = repo.get_db
        repo.get_db = _mock_get_db
        try:
            await repo.reset_task_for_retry(task_id)
        finally:
            repo.get_db = orig

        cursor = await mem_db.execute("SELECT * FROM crawl_task WHERE id = ?", (task_id,))
        row = dict(await cursor.fetchone())

        assert row["digest_date"] is None
        assert row["digest_highlight"] is None
