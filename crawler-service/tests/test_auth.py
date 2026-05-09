"""API Key 认证中间件测试

覆盖场景:
1. Valid API Key → 200 pass-through
2. Invalid API Key → 401
3. Missing Authorization header → 401
4. Wrong auth scheme (Bearer vs X-API-Key) → 401
5. Auth disabled → all requests pass
6. Whitelist paths (health, crawl, docs) → bypass auth
7. Empty API key configured → deny all /api/v1/* requests
8. Multiple valid keys accepted
"""

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from fastapi import FastAPI
from fastapi.testclient import TestClient
from standalone.auth import ApiKeyMiddleware
from config import settings as real_settings


# ============== Helpers ==============

def _make_app_with_middleware(api_keys: str):
    """创建带 ApiKeyMiddleware 的 FastAPI 应用。

    直接修改 config.settings 对象（非 patch），因为 BaseHTTPMiddleware
    的 __init__ 在首次请求时才被调用（延迟实例化）。
    """
    app = FastAPI()

    @app.get("/api/v1/tasks")
    def protected_endpoint():
        return {"ok": True}

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/crawl/status")
    def crawl_status():
        return {"status": "idle"}

    @app.get("/docs")
    def docs_page():
        return "docs"

    @app.get("/openapi.json")
    def openapi_spec():
        return {"openapi": "3.0"}

    @app.get("/redoc")
    def redoc_page():
        return "redoc"

    # 直接修改全局 settings，确保 middleware 延迟初始化时能读到正确值
    original = real_settings.api_keys
    real_settings.api_keys = api_keys
    try:
        app.add_middleware(ApiKeyMiddleware)
        app._test_original_api_keys = original  # 保存原始值用于恢复
        return app
    except Exception:
        real_settings.api_keys = original
        raise


def _cleanup_app(app):
    """恢复 settings"""
    if hasattr(app, '_test_original_api_keys'):
        real_settings.api_keys = app._test_original_api_keys


def _make_app_no_middleware():
    """创建不带中间件的应用，模拟 auth_enabled=false"""
    app = FastAPI()

    @app.get("/api/v1/tasks")
    def protected_endpoint():
        return {"ok": True}

    return app


VALID_KEY = "test-secret-key-123"
VALID_KEY_2 = "another-valid-key-456"


# ============== 1. Valid API Key ==============

class TestValidApiKey:

    def test_single_valid_key_passes(self):
        app = _make_app_with_middleware(VALID_KEY)
        try:
            client = TestClient(app)
            resp = client.get("/api/v1/tasks", headers={"X-API-Key": VALID_KEY})
            assert resp.status_code == 200
            assert resp.json() == {"ok": True}
        finally:
            _cleanup_app(app)

    def test_multiple_valid_keys_first_accepted(self):
        app = _make_app_with_middleware(f"{VALID_KEY},{VALID_KEY_2}")
        try:
            client = TestClient(app)
            resp = client.get("/api/v1/tasks", headers={"X-API-Key": VALID_KEY})
            assert resp.status_code == 200
        finally:
            _cleanup_app(app)

    def test_multiple_valid_keys_second_accepted(self):
        app = _make_app_with_middleware(f"{VALID_KEY},{VALID_KEY_2}")
        try:
            client = TestClient(app)
            resp = client.get("/api/v1/tasks", headers={"X-API-Key": VALID_KEY_2})
            assert resp.status_code == 200
        finally:
            _cleanup_app(app)


# ============== 2. Invalid API Key ==============

class TestInvalidApiKey:

    def test_wrong_key_returns_401(self):
        app = _make_app_with_middleware(VALID_KEY)
        try:
            client = TestClient(app)
            resp = client.get("/api/v1/tasks", headers={"X-API-Key": "wrong-key"})
            assert resp.status_code == 401
            assert "API key" in resp.json()["detail"]
        finally:
            _cleanup_app(app)

    def test_partial_key_match_returns_401(self):
        app = _make_app_with_middleware(VALID_KEY)
        try:
            client = TestClient(app)
            resp = client.get("/api/v1/tasks", headers={"X-API-Key": VALID_KEY[:5]})
            assert resp.status_code == 401
        finally:
            _cleanup_app(app)

    def test_case_sensitive_key_returns_401(self):
        app = _make_app_with_middleware("CaseSensitiveKey")
        try:
            client = TestClient(app)
            resp = client.get("/api/v1/tasks", headers={"X-API-Key": "casesensitivekey"})
            assert resp.status_code == 401
        finally:
            _cleanup_app(app)


# ============== 3. Missing Authorization Header ==============

class TestMissingAuthHeader:

    def test_no_header_returns_401(self):
        app = _make_app_with_middleware(VALID_KEY)
        try:
            client = TestClient(app)
            resp = client.get("/api/v1/tasks")
            assert resp.status_code == 401
        finally:
            _cleanup_app(app)

    def test_empty_x_api_key_returns_401(self):
        app = _make_app_with_middleware(VALID_KEY)
        try:
            client = TestClient(app)
            resp = client.get("/api/v1/tasks", headers={"X-API-Key": ""})
            assert resp.status_code == 401
        finally:
            _cleanup_app(app)

    def test_whitespace_only_key_returns_401(self):
        app = _make_app_with_middleware(VALID_KEY)
        try:
            client = TestClient(app)
            resp = client.get("/api/v1/tasks", headers={"X-API-Key": "   "})
            assert resp.status_code == 401
        finally:
            _cleanup_app(app)


# ============== 4. Wrong Auth Scheme ==============

class TestWrongAuthScheme:

    def test_bearer_scheme_returns_401(self):
        app = _make_app_with_middleware(VALID_KEY)
        try:
            client = TestClient(app)
            resp = client.get("/api/v1/tasks", headers={"Authorization": f"Bearer {VALID_KEY}"})
            assert resp.status_code == 401
        finally:
            _cleanup_app(app)

    def test_basic_scheme_returns_401(self):
        app = _make_app_with_middleware(VALID_KEY)
        try:
            client = TestClient(app)
            resp = client.get("/api/v1/tasks", headers={"Authorization": "Basic dXNlcjpwYXNz"})
            assert resp.status_code == 401
        finally:
            _cleanup_app(app)

    def test_authorization_without_x_api_key_returns_401(self):
        app = _make_app_with_middleware(VALID_KEY)
        try:
            client = TestClient(app)
            resp = client.get("/api/v1/tasks", headers={"Authorization": VALID_KEY})
            assert resp.status_code == 401
        finally:
            _cleanup_app(app)

    def test_bearer_plus_x_api_key_passes(self):
        app = _make_app_with_middleware(VALID_KEY)
        try:
            client = TestClient(app)
            resp = client.get("/api/v1/tasks", headers={
                "Authorization": "Bearer some-token",
                "X-API-Key": VALID_KEY,
            })
            assert resp.status_code == 200
        finally:
            _cleanup_app(app)


# ============== 5. Auth Disabled ==============

class TestAuthDisabled:

    def test_no_middleware_all_requests_pass(self):
        app = _make_app_no_middleware()
        client = TestClient(app)
        resp = client.get("/api/v1/tasks")
        assert resp.status_code == 200

    def test_no_middleware_ignores_wrong_key(self):
        app = _make_app_no_middleware()
        client = TestClient(app)
        resp = client.get("/api/v1/tasks", headers={"X-API-Key": "garbage"})
        assert resp.status_code == 200


# ============== 6. Whitelist Paths ==============

class TestWhitelistPaths:

    def test_health_no_auth_needed(self):
        app = _make_app_with_middleware(VALID_KEY)
        try:
            client = TestClient(app)
            resp = client.get("/health")
            assert resp.status_code == 200
        finally:
            _cleanup_app(app)

    def test_crawl_prefix_requires_auth(self):
        """C2 fix: /crawl/* endpoints now require authentication"""
        app = _make_app_with_middleware(VALID_KEY)
        try:
            client = TestClient(app)
            # Without API key -> 401
            resp = client.get("/crawl/status")
            assert resp.status_code == 401
            # With valid API key -> 200
            resp = client.get("/crawl/status", headers={"X-API-Key": VALID_KEY})
            assert resp.status_code == 200
        finally:
            _cleanup_app(app)

    def test_docs_no_auth_needed(self):
        app = _make_app_with_middleware(VALID_KEY)
        try:
            client = TestClient(app)
            resp = client.get("/docs")
            assert resp.status_code == 200
        finally:
            _cleanup_app(app)

    def test_redoc_no_auth_needed(self):
        app = _make_app_with_middleware(VALID_KEY)
        try:
            client = TestClient(app)
            resp = client.get("/redoc")
            assert resp.status_code == 200
        finally:
            _cleanup_app(app)

    def test_openapi_json_no_auth_needed(self):
        app = _make_app_with_middleware(VALID_KEY)
        try:
            client = TestClient(app)
            resp = client.get("/openapi.json")
            assert resp.status_code == 200
        finally:
            _cleanup_app(app)

    def test_invalid_key_on_whitelist_still_passes(self):
        app = _make_app_with_middleware(VALID_KEY)
        try:
            client = TestClient(app)
            resp = client.get("/health", headers={"X-API-Key": "wrong"})
            assert resp.status_code == 200
        finally:
            _cleanup_app(app)


# ============== 7. Empty API Key Configured ==============

class TestEmptyApiKeyConfig:

    def test_empty_keys_denies_all(self):
        app = _make_app_with_middleware("")
        try:
            client = TestClient(app)
            resp = client.get("/api/v1/tasks", headers={"X-API-Key": "anything"})
            assert resp.status_code == 401
        finally:
            _cleanup_app(app)

    def test_empty_keys_denies_without_header(self):
        app = _make_app_with_middleware("")
        try:
            client = TestClient(app)
            resp = client.get("/api/v1/tasks")
            assert resp.status_code == 401
        finally:
            _cleanup_app(app)

    def test_empty_keys_whitelist_still_works(self):
        app = _make_app_with_middleware("")
        try:
            client = TestClient(app)
            resp = client.get("/health")
            assert resp.status_code == 200
        finally:
            _cleanup_app(app)


# ============== 8. Key with Whitespace Trimming ==============

class TestKeyWhitespaceHandling:

    def test_key_with_leading_trailing_spaces(self):
        app = _make_app_with_middleware(f"  {VALID_KEY}  ,  {VALID_KEY_2}  ")
        try:
            client = TestClient(app)
            resp = client.get("/api/v1/tasks", headers={"X-API-Key": VALID_KEY})
            assert resp.status_code == 200
        finally:
            _cleanup_app(app)

    def test_key_with_spaces_trimmed(self):
        app = _make_app_with_middleware(f"  {VALID_KEY}  ")
        try:
            client = TestClient(app)
            resp = client.get("/api/v1/tasks", headers={"X-API-Key": VALID_KEY})
            assert resp.status_code == 200
        finally:
            _cleanup_app(app)


# ============== 9. Edge Cases ==============

class TestEdgeCases:

    def test_unknown_path_with_valid_key_returns_404(self):
        app = _make_app_with_middleware(VALID_KEY)
        try:
            client = TestClient(app)
            resp = client.get("/unknown/path", headers={"X-API-Key": VALID_KEY})
            assert resp.status_code == 404
        finally:
            _cleanup_app(app)

    def test_unknown_path_without_key_returns_404(self):
        app = _make_app_with_middleware(VALID_KEY)
        try:
            client = TestClient(app)
            resp = client.get("/unknown/path")
            assert resp.status_code == 404
        finally:
            _cleanup_app(app)

    def test_post_method_requires_key(self):
        app = _make_app_with_middleware(VALID_KEY)

        @app.post("/api/v1/tasks")
        def create_task():
            return {"ok": True}

        try:
            client = TestClient(app)
            resp = client.post("/api/v1/tasks", json={})
            assert resp.status_code == 401
        finally:
            _cleanup_app(app)

    def test_delete_method_requires_key(self):
        app = _make_app_with_middleware(VALID_KEY)

        @app.delete("/api/v1/tasks/1")
        def delete_task():
            return {"ok": True}

        try:
            client = TestClient(app)
            resp = client.delete("/api/v1/tasks/1")
            assert resp.status_code == 401
        finally:
            _cleanup_app(app)

    def test_error_response_format(self):
        app = _make_app_with_middleware(VALID_KEY)
        try:
            client = TestClient(app)
            resp = client.get("/api/v1/tasks")
            assert resp.status_code == 401
            body = resp.json()
            assert "detail" in body
            assert isinstance(body["detail"], str)
        finally:
            _cleanup_app(app)
