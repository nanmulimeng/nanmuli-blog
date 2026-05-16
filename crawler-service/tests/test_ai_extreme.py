"""AI 整理模块全面测试与极端测试：HTTP 层、公开异步方法、API 端点、配置门面、极端输入"""

import os
import sys
import json
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import httpx
from fastapi.testclient import TestClient
from fastapi import FastAPI

from ai.organizer import (
    ContentOrganizer, OrganizedContent, DigestContent,
    PageContent, DigestPageContent, DigestSection, DigestItem,
    TruncatedError, UnrecoverableError, RateLimitError,
    InvalidOutputError, OrganizerError,
    _extract_json, _truncate_at_paragraph_boundary,
    SYSTEM_PROMPT, DIGEST_SYSTEM_PROMPT, TEMPLATE_PROMPTS,
)
from ai.config import AiSettings


# ============== Fixtures ==============

def _make_configured_settings(**overrides):
    defaults = dict(ai_enabled=True, ai_api_key="sk-test-key", ai_model="test-model")
    defaults.update(overrides)
    return AiSettings(**defaults)


@pytest.fixture
def configured_organizer():
    s = _make_configured_settings()
    org = ContentOrganizer(settings=s)
    return org


def _ai_response(content_json: dict, finish_reason="stop", total_tokens=100):
    """构造 _call_ai 的返回格式"""
    return {
        "content": json.dumps(content_json, ensure_ascii=False),
        "total_tokens": total_tokens,
        "finish_reason": finish_reason,
    }


def _valid_organized_json(**overrides):
    defaults = {
        "title": "Spring Boot 3 优雅停机配置",
        "summary": "本文介绍 Spring Boot 3 的优雅停机机制，包括 server.shutdown=graceful 配置和 SmartLifecycle 接口实现，以及 Kubernetes 环境下的最佳实践。",
        "keyPoints": [
            "server.shutdown=graceful 开启优雅停机",
            "实现 SmartLifecycle 接口自定义资源释放",
            "Kubernetes 需配置 terminationGracePeriodSeconds",
        ],
        "tags": ["Spring Boot 3", "优雅停机", "Kubernetes"],
        "category": "后端开发",
        "fullContent": "## 开启优雅停机\n\n在 application.yml 中配置：\n\n```yaml\nserver:\n  shutdown: graceful\n```\n\n启用后应用关闭时会拒绝新请求并等待处理中的请求完成。\n\n## 自定义资源释放\n\n实现 SmartLifecycle 接口按顺序释放资源。",
    }
    defaults.update(overrides)
    return defaults


def _valid_digest_json(**overrides):
    defaults = {
        "title": "技术日报 | 2026-05-16",
        "summary": "今日技术圈最值得关注：React 19 正式发布；Bun 1.2 性能创新高；一篇 Linux 内核调度深度解析引发广泛讨论。三大热点各有看点，对开发者影响深远。",
        "highlight": "React 19 正式发布，Server Components 进入稳定阶段",
        "tags": ["React 19", "Bun", "Linux内核"],
        "fullContent": "# 技术日报 | 2026-05-16\n\n## 热点动态\n\n### React 19 正式发布\nServer Components 稳定版上线。\n\n## 开源项目\n\n### Bun 1.2 发布\n性能再创新高。",
        "sections": [
            {
                "category": "hot_trend",
                "categoryName": "热点动态",
                "emoji": "🔥",
                "items": [
                    {
                        "title": "React 19 正式发布",
                        "oneLiner": "Server Components 稳定版上线",
                        "sourceUrl": "https://react.dev/blog/react-19",
                        "sourceName": "react.dev",
                    }
                ],
            },
            {
                "category": "open_source",
                "categoryName": "开源项目",
                "emoji": "🌟",
                "items": [
                    {
                        "title": "Bun 1.2 发布",
                        "oneLiner": "性能再创新高",
                        "sourceUrl": "https://bun.sh/blog",
                        "sourceName": "bun.sh",
                    }
                ],
            },
        ],
    }
    defaults.update(overrides)
    return defaults


# ============== Step 1: _call_ai HTTP 层测试 ==============


class TestCallAi:
    """测试 _call_ai 的 HTTP 交互和错误分支"""

    def _mock_response(self, status_code=200, json_data=None, text=""):
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = status_code
        resp.text = text
        resp.json.return_value = json_data or {}
        return resp

    @pytest.mark.asyncio
    async def test_success_response(self, configured_organizer):
        ai_data = {
            "choices": [
                {"message": {"content": '{"title":"test"}'}, "finish_reason": "stop"}
            ],
            "usage": {"total_tokens": 42},
        }
        with patch.object(configured_organizer, "_get_client", new_callable=AsyncMock) as mock_client:
            client = AsyncMock()
            client.post.return_value = self._mock_response(200, ai_data)
            mock_client.return_value = client

            result = await configured_organizer._call_ai("sys", "user")

        assert result["content"] == '{"title":"test"}'
        assert result["total_tokens"] == 42
        assert result["finish_reason"] == "stop"

    @pytest.mark.asyncio
    async def test_429_raises_rate_limit(self, configured_organizer):
        with patch.object(configured_organizer, "_get_client", new_callable=AsyncMock) as mock_client:
            client = AsyncMock()
            client.post.return_value = self._mock_response(429, text="rate limited")
            mock_client.return_value = client

            with pytest.raises(RateLimitError, match="Rate limited"):
                await configured_organizer._call_ai("sys", "user")

    @pytest.mark.asyncio
    async def test_4xx_raises_unrecoverable(self, configured_organizer):
        with patch.object(configured_organizer, "_get_client", new_callable=AsyncMock) as mock_client:
            client = AsyncMock()
            client.post.return_value = self._mock_response(400, text="bad request")
            mock_client.return_value = client

            with pytest.raises(UnrecoverableError, match="client error 400"):
                await configured_organizer._call_ai("sys", "user")

    @pytest.mark.asyncio
    async def test_403_raises_unrecoverable(self, configured_organizer):
        with patch.object(configured_organizer, "_get_client", new_callable=AsyncMock) as mock_client:
            client = AsyncMock()
            client.post.return_value = self._mock_response(403, text="forbidden")
            mock_client.return_value = client

            with pytest.raises(UnrecoverableError, match="client error 403"):
                await configured_organizer._call_ai("sys", "user")

    @pytest.mark.asyncio
    async def test_5xx_raises_runtime(self, configured_organizer):
        with patch.object(configured_organizer, "_get_client", new_callable=AsyncMock) as mock_client:
            client = AsyncMock()
            client.post.return_value = self._mock_response(500, text="internal error")
            mock_client.return_value = client

            with pytest.raises(RuntimeError, match="server error 500"):
                await configured_organizer._call_ai("sys", "user")

    @pytest.mark.asyncio
    async def test_empty_choices_raises(self, configured_organizer):
        with patch.object(configured_organizer, "_get_client", new_callable=AsyncMock) as mock_client:
            client = AsyncMock()
            client.post.return_value = self._mock_response(200, {"choices": []})
            mock_client.return_value = client

            with pytest.raises(RuntimeError, match="No choices"):
                await configured_organizer._call_ai("sys", "user")

    @pytest.mark.asyncio
    async def test_empty_content_raises(self, configured_organizer):
        with patch.object(configured_organizer, "_get_client", new_callable=AsyncMock) as mock_client:
            client = AsyncMock()
            client.post.return_value = self._mock_response(
                200, {"choices": [{"message": {"content": ""}, "finish_reason": "stop"}]}
            )
            mock_client.return_value = client

            with pytest.raises(RuntimeError, match="Empty content"):
                await configured_organizer._call_ai("sys", "user")

    @pytest.mark.asyncio
    async def test_none_content_raises(self, configured_organizer):
        with patch.object(configured_organizer, "_get_client", new_callable=AsyncMock) as mock_client:
            client = AsyncMock()
            client.post.return_value = self._mock_response(
                200, {"choices": [{"message": {"content": None}, "finish_reason": "stop"}]}
            )
            mock_client.return_value = client

            with pytest.raises(RuntimeError, match="Empty content"):
                await configured_organizer._call_ai("sys", "user")

    @pytest.mark.asyncio
    async def test_finish_reason_length_raises_truncated(self, configured_organizer):
        with patch.object(configured_organizer, "_get_client", new_callable=AsyncMock) as mock_client:
            client = AsyncMock()
            client.post.return_value = self._mock_response(
                200,
                {
                    "choices": [{"message": {"content": "partial"}, "finish_reason": "length"}],
                    "usage": {"total_tokens": 8000},
                },
            )
            mock_client.return_value = client

            with pytest.raises(TruncatedError, match="truncated"):
                await configured_organizer._call_ai("sys", "user")

    @pytest.mark.asyncio
    async def test_not_configured_raises(self):
        s = AiSettings(ai_enabled=False, ai_api_key="")
        org = ContentOrganizer(settings=s)
        with pytest.raises(RuntimeError, match="AI not configured"):
            await org._call_ai("sys", "user")

    @pytest.mark.asyncio
    async def test_list_content_multimodal(self, configured_organizer):
        ai_data = {
            "choices": [
                {
                    "message": {
                        "content": [
                            {"type": "text", "text": '{"title":'},
                            {"type": "text", "text": '"hello"}'},
                        ]
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {"total_tokens": 50},
        }
        with patch.object(configured_organizer, "_get_client", new_callable=AsyncMock) as mock_client:
            client = AsyncMock()
            client.post.return_value = self._mock_response(200, ai_data)
            mock_client.return_value = client

            result = await configured_organizer._call_ai("sys", "user")

        assert result["content"] == '{"title":\n"hello"}'
        assert result["total_tokens"] == 50

    @pytest.mark.asyncio
    async def test_connect_timeout_propagates(self, configured_organizer):
        with patch.object(configured_organizer, "_get_client", new_callable=AsyncMock) as mock_client:
            client = AsyncMock()
            client.post.side_effect = httpx.ConnectTimeout("timeout")
            mock_client.return_value = client

            with pytest.raises(httpx.ConnectTimeout):
                await configured_organizer._call_ai("sys", "user")


# ============== Step 2: 公开异步方法端到端测试 ==============


class TestPublicAsyncMethods:
    """通过 mock _call_ai 测试完整调用链"""

    @pytest.mark.asyncio
    async def test_organize_normal_flow(self, configured_organizer):
        with patch.object(configured_organizer, "_call_ai", new_callable=AsyncMock) as mock_ai:
            mock_ai.return_value = _ai_response(_valid_organized_json(), total_tokens=200)

            result = await configured_organizer.organize("# Spring Boot\nContent here.")

        assert result.title == "Spring Boot 3 优雅停机配置"
        assert result.category == "后端开发"
        assert len(result.key_points) == 3
        assert len(result.tags) == 3
        assert result.tokens_used == 200
        assert result.duration_ms >= 0

    @pytest.mark.asyncio
    async def test_organize_non_tech_detection(self, configured_organizer):
        data = _valid_organized_json(
            summary="该页面不包含有效技术内容，仅为登录页面。",
            keyPoints=[],
            tags=[],
        )
        with patch.object(configured_organizer, "_call_ai", new_callable=AsyncMock) as mock_ai:
            mock_ai.return_value = _ai_response(data)

            with pytest.raises(InvalidOutputError, match="不包含有效技术内容"):
                await configured_organizer.organize("Login page content")

    @pytest.mark.asyncio
    async def test_organize_with_keyword_context(self, configured_organizer):
        with patch.object(configured_organizer, "_call_ai", new_callable=AsyncMock) as mock_ai:
            mock_ai.return_value = _ai_response(_valid_organized_json())

            result = await configured_organizer.organize(
                "# Docker\nContent.", "tech_summary", "原始关键词：docker\n优化关键词：Docker 容器"
            )

        prompt_arg = mock_ai.call_args[0][1]
        assert "docker" in prompt_arg
        assert "搜索上下文" in prompt_arg
        assert result.title

    @pytest.mark.asyncio
    async def test_organize_multiple_normal(self, configured_organizer):
        pages = [
            PageContent(url=f"http://a{i}.com", title=f"Page {i}",
                        markdown=f"# Content {i}\n" + "X" * 500, word_count=500)
            for i in range(3)
        ]
        with patch.object(configured_organizer, "_call_ai", new_callable=AsyncMock) as mock_ai:
            mock_ai.return_value = _ai_response(_valid_organized_json())

            result = await configured_organizer.organize_multiple(pages, "tech_summary")

        prompt_arg = mock_ai.call_args[0][1]
        assert "来源 1" in prompt_arg
        assert "来源 3" in prompt_arg
        assert result.title

    @pytest.mark.asyncio
    async def test_organize_multiple_budget_exhaustion(self, configured_organizer):
        # per_max=20K, total_budget=150K → 8 pages × 20K = 160K > 150K
        # 第 8 页 budget < 20K，第 9 页 budget = 0 → 触发省略提示
        large_md = "Y" * 50_000
        pages = [
            PageContent(url=f"http://big{i}.com", title=f"Big {i}",
                        markdown=large_md, word_count=50000)
            for i in range(10)
        ]
        with patch.object(configured_organizer, "_call_ai", new_callable=AsyncMock) as mock_ai:
            mock_ai.return_value = _ai_response(_valid_organized_json())

            result = await configured_organizer.organize_multiple(pages, "tech_summary")

        prompt_arg = mock_ai.call_args[0][1]
        assert "已达到总输入预算上限" in prompt_arg

    @pytest.mark.asyncio
    async def test_optimize_keyword_normal(self, configured_organizer):
        with patch.object(configured_organizer, "_call_ai", new_callable=AsyncMock) as mock_ai:
            mock_ai.return_value = {"content": "Docker 容器化部署最佳实践", "total_tokens": 30, "finish_reason": "stop"}

            result = await configured_organizer.optimize_keyword("docker")

        assert result == "Docker 容器化部署最佳实践"

    @pytest.mark.asyncio
    async def test_optimize_keyword_output_too_long(self, configured_organizer):
        with patch.object(configured_organizer, "_call_ai", new_callable=AsyncMock) as mock_ai:
            mock_ai.return_value = {"content": "X" * 150, "total_tokens": 30, "finish_reason": "stop"}

            result = await configured_organizer.optimize_keyword("docker")

        assert result == "docker"

    @pytest.mark.asyncio
    async def test_optimize_keyword_output_too_short(self, configured_organizer):
        with patch.object(configured_organizer, "_call_ai", new_callable=AsyncMock) as mock_ai:
            mock_ai.return_value = {"content": "X", "total_tokens": 30, "finish_reason": "stop"}

            result = await configured_organizer.optimize_keyword("docker")

        assert result == "docker"

    @pytest.mark.asyncio
    async def test_optimize_keyword_exception_fallback(self, configured_organizer):
        with patch.object(configured_organizer, "_call_ai", new_callable=AsyncMock) as mock_ai:
            mock_ai.side_effect = RuntimeError("API down")

            result = await configured_organizer.optimize_keyword("docker")

        assert result == "docker"

    @pytest.mark.asyncio
    async def test_expand_keywords_normal(self, configured_organizer):
        with patch.object(configured_organizer, "_call_ai", new_callable=AsyncMock) as mock_ai:
            mock_ai.return_value = {
                "content": '["容器化部署最佳实践", "Docker Compose 微服务编排", "Docker 多阶段构建优化"]',
                "total_tokens": 40,
                "finish_reason": "stop",
            }

            result = await configured_organizer.expand_keywords("docker")

        assert len(result) == 3
        assert "容器化部署最佳实践" in result

    @pytest.mark.asyncio
    async def test_expand_keywords_empty_list_fallback(self, configured_organizer):
        with patch.object(configured_organizer, "_call_ai", new_callable=AsyncMock) as mock_ai:
            mock_ai.return_value = {"content": "[]", "total_tokens": 10, "finish_reason": "stop"}

            result = await configured_organizer.expand_keywords("docker")

        assert result == ["docker"]

    @pytest.mark.asyncio
    async def test_generate_digest_normal(self, configured_organizer):
        pages = [
            DigestPageContent(url="http://a.com", title="React 19", markdown="React 19 released", category="hot_trend"),
            DigestPageContent(url="http://b.com", title="Bun 1.2", markdown="Bun 1.2 released", category="open_source"),
        ]
        with patch.object(configured_organizer, "_call_ai", new_callable=AsyncMock) as mock_ai:
            mock_ai.return_value = _ai_response(_valid_digest_json(), total_tokens=300)

            result = await configured_organizer.generate_digest(pages, "2026-05-16")

        assert result.title == "技术日报 | 2026-05-16"
        assert len(result.sections) == 2
        assert result.highlight
        assert result.tokens_used == 300
        assert result.duration_ms >= 0


# ============== Step 3: API 端点测试 ==============


@pytest.fixture
def app():
    _app = FastAPI()
    from api.crawl import router as crawl_router
    _app.include_router(crawl_router)
    return _app


@pytest.fixture
def client(app):
    return TestClient(app, raise_server_exceptions=False)


class TestApiOrganizeEndpoint:

    def test_single_page_success(self, client):
        import ai
        mock_org = MagicMock()
        mock_org.is_available = True
        mock_org.organize = AsyncMock(return_value=OrganizedContent(
            title="Test", summary="A valid summary that is long enough.",
            key_points=["point 1"], tags=["test"], category="其他",
            full_content="Full content here that is long enough.",
            tokens_used=50, duration_ms=100,
        ))

        with patch.object(ai, "content_organizer", mock_org):
            resp = client.post("/organize", json={
                "pages": [{"url": "http://a.com", "title": "A", "markdown": "content", "word_count": 10}],
                "template": "tech_summary",
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["title"] == "Test"
        assert data["tokens_used"] == 50

    def test_multi_page_success(self, client):
        import ai
        mock_org = MagicMock()
        mock_org.is_available = True
        mock_org.organize_multiple = AsyncMock(return_value=OrganizedContent(
            title="Multi", summary="A valid multi-page summary that is long enough.",
            key_points=["p1", "p2"], tags=["t1"], category="后端开发",
            full_content="Multi-page content that is long enough.",
            tokens_used=80, duration_ms=200,
        ))

        with patch.object(ai, "content_organizer", mock_org):
            resp = client.post("/organize", json={
                "pages": [
                    {"url": "http://a.com", "title": "A", "markdown": "content A", "word_count": 10},
                    {"url": "http://b.com", "title": "B", "markdown": "content B", "word_count": 20},
                    {"url": "http://c.com", "title": "C", "markdown": "content C", "word_count": 30},
                ],
                "template": "tech_summary",
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["title"] == "Multi"
        mock_org.organize_multiple.assert_called_once()

    def test_ai_not_configured_returns_503(self, client):
        resp = client.post("/organize", json={
            "pages": [{"url": "http://a.com", "title": "A", "markdown": "content", "word_count": 10}],
            "template": "tech_summary",
        })
        assert resp.status_code == 503

    def test_empty_pages_returns_400(self, client):
        import ai
        mock_org = MagicMock()
        mock_org.is_available = True

        with patch.object(ai, "content_organizer", mock_org):
            resp = client.post("/organize", json={
                "pages": [{"url": "http://a.com", "title": "A", "markdown": "", "word_count": 0}],
                "template": "tech_summary",
            })

        assert resp.status_code == 400

    def test_rate_limit_retry_then_success(self, client):
        import ai
        mock_org = MagicMock()
        mock_org.is_available = True
        mock_org.organize = AsyncMock(
            side_effect=[RateLimitError("limited"), RateLimitError("limited"),
                         OrganizedContent(
                             title="Retry OK", summary="Summary after retry is long enough.",
                             key_points=["p"], tags=["t"], category="其他",
                             full_content="Content after retry is long enough.",
                             tokens_used=60, duration_ms=150,
                         )]
        )

        with patch.object(ai, "content_organizer", mock_org):
            with patch("api.crawl.ai_settings") as mock_settings:
                mock_settings.ai_max_retries = 2
                mock_settings.ai_rate_limit_backoff_ms = 0

                resp = client.post("/organize", json={
                    "pages": [{"url": "http://a.com", "title": "A", "markdown": "content", "word_count": 10}],
                    "template": "tech_summary",
                })

        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Retry OK"
        assert mock_org.organize.call_count == 3

    def test_organizer_error_returns_500(self, client):
        import ai
        mock_org = MagicMock()
        mock_org.is_available = True
        mock_org.organize = AsyncMock(side_effect=InvalidOutputError("bad output"))

        with patch.object(ai, "content_organizer", mock_org):
            resp = client.post("/organize", json={
                "pages": [{"url": "http://a.com", "title": "A", "markdown": "content", "word_count": 10}],
                "template": "tech_summary",
            })

        assert resp.status_code == 500


class TestApiKeywordEndpoint:

    def test_optimize_success(self, client):
        import ai
        mock_org = MagicMock()
        mock_org.is_available = True
        mock_org.optimize_keyword = AsyncMock(return_value="Docker 容器化部署最佳实践")

        with patch.object(ai, "content_organizer", mock_org):
            resp = client.post("/keyword", json={"keyword": "docker", "action": "optimize"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["optimized"] == "Docker 容器化部署最佳实践"
        assert data["original"] == "docker"

    def test_expand_success(self, client):
        import ai
        mock_org = MagicMock()
        mock_org.is_available = True
        mock_org.expand_keywords = AsyncMock(
            return_value=["容器化部署", "Docker Compose", "Docker 多阶段构建"]
        )

        with patch.object(ai, "content_organizer", mock_org):
            resp = client.post("/keyword", json={"keyword": "docker", "action": "expand"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert len(data["variants"]) == 3

    def test_ai_not_configured_returns_503(self, client):
        resp = client.post("/keyword", json={"keyword": "docker", "action": "optimize"})
        assert resp.status_code == 503

    def test_keyword_validation_422(self, client):
        resp = client.post("/keyword", json={"keyword": "", "action": "optimize"})
        assert resp.status_code == 422

        resp = client.post("/keyword", json={"keyword": "x" * 201, "action": "optimize"})
        assert resp.status_code == 422


# ============== Step 4: AiSettings 配置门面测试 ==============


class TestAiSettings:

    def test_constructor_overrides(self):
        s = AiSettings(ai_enabled=True, ai_api_key="sk-override")
        assert s.ai_enabled is True
        assert s.ai_api_key == "sk-override"

    def test_getattr_delegates_to_settings(self):
        s = AiSettings()
        from config import settings
        assert s.ai_temperature == settings.ai_temperature
        assert s.ai_max_retries == settings.ai_max_retries

    def test_is_configured_all_present(self):
        s = AiSettings(ai_enabled=True, ai_api_key="sk-test", ai_model="test-model")
        assert s.is_configured is True

    def test_is_configured_missing_key(self):
        s = AiSettings(ai_enabled=True, ai_api_key="")
        assert s.is_configured is False

    def test_is_configured_disabled(self):
        s = AiSettings(ai_enabled=False, ai_api_key="sk-test")
        assert s.is_configured is False

    def test_private_attr_raises(self):
        s = AiSettings()
        with pytest.raises(AttributeError):
            _ = s._nonexistent

    def test_dynamic_backend_config_override(self):
        s = AiSettings(ai_enabled=True, ai_api_key="sk-test", ai_model="base-model")
        # __getattr__ 在无 override 且无 backend_config 时回退到 config.settings
        # 直接验证：未 override 的字段从全局 settings 读取
        from config import settings as global_settings
        assert s.ai_connect_timeout == global_settings.ai_connect_timeout


# ============== Step 5: 极端输入与内容质量测试 ==============


class TestExtremeInput:

    @pytest.mark.asyncio
    async def test_huge_markdown_input(self, configured_organizer):
        huge_md = "# Big\n" + "Content line.\n" * 20_000
        with patch.object(configured_organizer, "_call_ai", new_callable=AsyncMock) as mock_ai:
            mock_ai.return_value = _ai_response(_valid_organized_json())

            result = await configured_organizer.organize(huge_md)

        prompt_arg = mock_ai.call_args[0][1]
        assert len(prompt_arg) < len(huge_md)
        assert "内容过长已截断" in prompt_arg
        assert result.title

    @pytest.mark.asyncio
    async def test_ai_returns_malformed_json(self, configured_organizer):
        with patch.object(configured_organizer, "_call_ai", new_callable=AsyncMock) as mock_ai:
            mock_ai.return_value = {"content": '{title: missing_quotes}', "total_tokens": 10, "finish_reason": "stop"}

            with pytest.raises(Exception):
                await configured_organizer.organize("content")

    @pytest.mark.asyncio
    async def test_ai_returns_plain_text(self, configured_organizer):
        with patch.object(configured_organizer, "_call_ai", new_callable=AsyncMock) as mock_ai:
            mock_ai.return_value = {"content": "This is just plain text, no JSON", "total_tokens": 10, "finish_reason": "stop"}

            with pytest.raises(ValueError, match="No JSON found"):
                await configured_organizer.organize("content")

    @pytest.mark.asyncio
    async def test_ai_returns_markdown_wrapped_json(self, configured_organizer):
        json_str = json.dumps(_valid_organized_json(), ensure_ascii=False)
        wrapped = f"```json\n{json_str}\n```"
        with patch.object(configured_organizer, "_call_ai", new_callable=AsyncMock) as mock_ai:
            mock_ai.return_value = {"content": wrapped, "total_tokens": 100, "finish_reason": "stop"}

            result = await configured_organizer.organize("content")
            assert result.title == "Spring Boot 3 优雅停机配置"

    @pytest.mark.asyncio
    async def test_ai_returns_nested_json(self, configured_organizer):
        data = _valid_organized_json(fullContent='{"nested": "content with braces { and }"}')
        with patch.object(configured_organizer, "_call_ai", new_callable=AsyncMock) as mock_ai:
            mock_ai.return_value = _ai_response(data)

            result = await configured_organizer.organize("content")
            assert result.title

    @pytest.mark.asyncio
    async def test_multi_page_all_empty_markdown(self, configured_organizer):
        pages = [
            PageContent(url="http://a.com", title="Empty", markdown="", word_count=0),
            PageContent(url="http://b.com", title="None", markdown="", word_count=0),
        ]
        with patch.object(configured_organizer, "_call_ai", new_callable=AsyncMock) as mock_ai:
            mock_ai.return_value = _ai_response(_valid_organized_json())

            result = await configured_organizer.organize_multiple(pages, "tech_summary")

        prompt_arg = mock_ai.call_args[0][1]
        assert "来源 1" in prompt_arg
        assert result.title

    @pytest.mark.asyncio
    async def test_unicode_keyword_optimize(self, configured_organizer):
        with patch.object(configured_organizer, "_call_ai", new_callable=AsyncMock) as mock_ai:
            mock_ai.return_value = {"content": "안녕하세요 Docker コンテナ最佳实践", "total_tokens": 20, "finish_reason": "stop"}

            result = await configured_organizer.optimize_keyword("docker 🐳")
            assert result

    @pytest.mark.asyncio
    async def test_special_chars_markdown(self, configured_organizer):
        special_md = "Content\x00with\x00nulls​​zero​width"
        with patch.object(configured_organizer, "_call_ai", new_callable=AsyncMock) as mock_ai:
            mock_ai.return_value = _ai_response(_valid_organized_json())

            result = await configured_organizer.organize(special_md)
            assert result.title

    @pytest.mark.asyncio
    async def test_all_template_variants(self, configured_organizer):
        for template in ["tech_summary", "tutorial", "comparison", "knowledge_report"]:
            with patch.object(configured_organizer, "_call_ai", new_callable=AsyncMock) as mock_ai:
                mock_ai.return_value = _ai_response(_valid_organized_json())

                result = await configured_organizer.organize("# Content", template)
                assert result.title

                prompt_arg = mock_ai.call_args[0][1]
                assert template in str(TEMPLATE_PROMPTS) or "tech_summary" in prompt_arg

    @pytest.mark.asyncio
    async def test_digest_zero_valid_sections(self, configured_organizer):
        data = _valid_digest_json(
            sections=[{
                "category": "hot_trend",
                "categoryName": "热点",
                "emoji": "🔥",
                "items": [{"title": "", "oneLiner": "", "sourceUrl": "", "sourceName": ""}],
            }]
        )
        with patch.object(configured_organizer, "_call_ai", new_callable=AsyncMock) as mock_ai:
            mock_ai.return_value = _ai_response(data)

            with pytest.raises(InvalidOutputError, match="missing valid items"):
                await configured_organizer.generate_digest(
                    [DigestPageContent(url="http://a.com", title="A", markdown="c")],
                    "2026-05-16",
                )

    @pytest.mark.asyncio
    async def test_digest_unknown_category_fallback(self, configured_organizer):
        data = _valid_digest_json(
            sections=[{
                "category": "quantum",
                "categoryName": "量子",
                "emoji": "⚛️",
                "items": [{
                    "title": "Quantum Computing",
                    "oneLiner": "Breakthrough in quantum",
                    "sourceUrl": "https://q.com",
                    "sourceName": "q.com",
                }],
            }]
        )
        with patch.object(configured_organizer, "_call_ai", new_callable=AsyncMock) as mock_ai:
            mock_ai.return_value = _ai_response(data)

            result = await configured_organizer.generate_digest(
                [DigestPageContent(url="http://q.com", title="Q", markdown="quantum")],
                "2026-05-16",
            )

        assert result.sections[0].category == "tech_article"
        assert result.sections[0].category_name == "技术文章"

    @pytest.mark.asyncio
    async def test_organize_tokens_and_duration_populated(self, configured_organizer):
        with patch.object(configured_organizer, "_call_ai", new_callable=AsyncMock) as mock_ai:
            mock_ai.return_value = _ai_response(_valid_organized_json(), total_tokens=42)

            result = await configured_organizer.organize("content")
            assert result.tokens_used == 42
            assert result.duration_ms >= 0

    @pytest.mark.asyncio
    async def test_generate_digest_empty_pages(self, configured_organizer):
        with patch.object(configured_organizer, "_call_ai", new_callable=AsyncMock) as mock_ai:
            mock_ai.return_value = _ai_response(_valid_digest_json())

            result = await configured_organizer.generate_digest([], "2026-05-16")

        prompt_arg = mock_ai.call_args[0][1]
        assert "日报日期" in prompt_arg
        assert "来源内容" in prompt_arg
