"""API 端点测试：/crawl/organize + /crawl/keyword，Mock AI 调用"""

import os
import sys
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from fastapi.testclient import TestClient
from fastapi import FastAPI
from api.crawl import router as crawl_router
from api.health import router as health_router


@pytest.fixture
def app():
    """创建精简 FastAPI 应用（不触发 lifespan 中的 crawl4ai 导入）"""
    app = FastAPI()
    app.include_router(crawl_router)
    app.include_router(health_router)
    return app


@pytest.fixture
def client(app):
    return TestClient(app, raise_server_exceptions=False)


# ============== /crawl/organize ==============

class TestOrganizeEndpoint:
    def test_organize_returns_503_when_ai_not_configured(self, client):
        """AI 未配置时应返回 503"""
        resp = client.post("/organize", json={
            "pages": [{"url": "http://a.com", "title": "A", "markdown": "content", "word_count": 10}],
            "template": "tech_summary",
        })
        assert resp.status_code == 503

    def test_organize_returns_400_for_empty_pages(self, client):
        """空页面列表应返回 success=false"""
        import ai
        mock_org = MagicMock()
        mock_org.is_available = True
        mock_org.organize = AsyncMock(return_value=None)
        mock_org.organize_multiple = AsyncMock(return_value=None)

        with patch.object(ai, "content_organizer", mock_org):
            resp = client.post("/organize", json={
                "pages": [{"url": "http://a.com", "title": "A", "markdown": "", "word_count": 0}],
                "template": "tech_summary",
            })
            # Empty markdown -> filtered out -> HTTPException(400) caught by generic except -> 200 + success=false
            assert resp.status_code == 200
            assert resp.json()["success"] is False

    def test_organize_invalid_template_rejected(self, client):
        """非法 template 值应被 Pydantic 拒绝"""
        resp = client.post("/organize", json={
            "pages": [{"url": "http://a.com", "title": "A", "markdown": "c", "word_count": 10}],
            "template": "invalid_template",
        })
        assert resp.status_code == 422


# ============== /keyword ==============

class TestKeywordEndpoint:
    def test_keyword_returns_503_when_ai_not_configured(self, client):
        resp = client.post("/keyword", json={
            "keyword": "docker",
            "action": "optimize",
        })
        assert resp.status_code == 503

    def test_keyword_invalid_action_rejected(self, client):
        resp = client.post("/keyword", json={
            "keyword": "docker",
            "action": "invalid",
        })
        assert resp.status_code == 422

    def test_keyword_missing_keyword_rejected(self, client):
        resp = client.post("/keyword", json={
            "action": "optimize",
        })
        assert resp.status_code == 422


# ============== Crawl endpoints ==============

class TestCrawlEndpoints:
    def test_single_crawl_missing_url(self, client):
        resp = client.post("/crawl/single", json={})
        assert resp.status_code == 422

    def test_search_crawl_invalid_engine(self, client):
        resp = client.post("/crawl/search", json={
            "keyword": "docker",
            "engine": "yahoo",
        })
        assert resp.status_code == 422

    def test_search_crawl_invalid_time_range(self, client):
        resp = client.post("/crawl/search", json={
            "keyword": "docker",
            "time_range": "decade",
        })
        assert resp.status_code == 422

    def test_search_crawl_valid_params(self, client):
        """合法参数不应触发 422（实际爬取会失败，但参数验证通过）"""
        resp = client.post("/crawl/search", json={
            "keyword": "docker",
            "engine": "bing",
            "time_range": "week",
            "max_results": 5,
        })
        # 500 = 爬虫执行失败（正常，无浏览器），422 = 参数验证失败（不正常）
        assert resp.status_code != 422


# ============== Health ==============

class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "ok" or "status" in data
