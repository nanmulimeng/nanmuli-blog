"""api/errors.py 单元测试

覆盖：
- AppError 类（创建、to_dict、错误码工厂函数）
- 异常处理器（validation / AppError / HTTPException / 兜底 Exception）
- RequestID 中间件（自动生成、透传、错误响应携带）
"""

import os
import sys
import pytest
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from fastapi import FastAPI, HTTPException, Query
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from api.errors import (
    AppError,
    crawl_timeout,
    ai_rate_limited,
    ai_not_configured,
    task_not_found,
    task_not_terminal,
    invalid_url,
    search_blocked,
    register_error_handlers,
    register_middlewares,
)


# ============== Helpers ==============

def _make_app() -> FastAPI:
    """创建注册了中间件 + 异常处理器的测试 app"""
    app = FastAPI()
    register_middlewares(app)
    register_error_handlers(app)
    return app


# ============== AppError 类测试 ==============

class TestAppError:
    """AppError 基础行为"""

    def test_create(self):
        err = AppError("TEST_CODE", "test msg", 418)
        assert err.code == "TEST_CODE"
        assert err.message == "test msg"
        assert err.status == 418

    def test_default_status_is_400(self):
        err = AppError("X", "y")
        assert err.status == 400

    def test_to_dict_without_request_id(self):
        err = AppError("CODE", "msg", 400)
        d = err.to_dict()
        assert d == {"success": False, "code": "CODE", "message": "msg"}
        assert "request_id" not in d

    def test_to_dict_with_request_id(self):
        err = AppError("CODE", "msg", 400)
        d = err.to_dict("abc123")
        assert d["request_id"] == "abc123"

    def test_to_dict_ignores_empty_request_id(self):
        err = AppError("CODE", "msg", 400)
        d = err.to_dict("")
        assert "request_id" not in d

    def test_to_dict_ignores_none_request_id(self):
        err = AppError("CODE", "msg", 400)
        d = err.to_dict(None)
        assert "request_id" not in d


# ============== 错误码工厂函数测试 ==============

class TestErrorFactories:
    """每个工厂函数返回正确的 code / status"""

    @pytest.mark.parametrize(
        "factory, expected_code, expected_status",
        [
            (crawl_timeout, "CRAWL_TIMEOUT", 504),
            (ai_rate_limited, "AI_RATE_LIMITED", 429),
            (ai_not_configured, "AI_NOT_CONFIGURED", 503),
            (task_not_found, "TASK_NOT_FOUND", 404),
            (task_not_terminal, "TASK_NOT_TERMINAL", 400),
            (invalid_url, "INVALID_URL", 400),
            (search_blocked, "SEARCH_BLOCKED", 503),
        ],
    )
    def test_factory_default(self, factory, expected_code, expected_status):
        err = factory()
        assert isinstance(err, AppError)
        assert err.code == expected_code
        assert err.status == expected_status

    def test_factory_custom_message(self):
        err = crawl_timeout("自定义超时消息")
        assert err.message == "自定义超时消息"


# ============== 异常处理器测试 ==============

class _ItemModel(BaseModel):
    name: str = Field(..., min_length=1)
    value: int = Field(..., ge=0)


class TestExceptionHandlers:
    """通过 TestClient 验证异常处理器的 HTTP 行为"""

    def setup_method(self):
        self.app = _make_app()

        @self.app.get("/raise-app-error")
        async def raise_app_error():
            raise task_not_found()

        @self.app.get("/raise-http-exception")
        async def raise_http_exc():
            raise HTTPException(status_code=403, detail="forbidden")

        @self.app.get("/raise-unhandled")
        async def raise_unhandled():
            raise RuntimeError("boom")

        @self.app.post("/validate")
        async def validate(body: _ItemModel):
            return {"ok": True}

        self.client = TestClient(self.app, raise_server_exceptions=False)

    def test_validation_error_returns_422(self):
        resp = self.client.post("/validate", json={"name": "", "value": -1})
        assert resp.status_code == 422
        body = resp.json()
        assert body["code"] == "VALIDATION_ERROR"
        assert body["success"] is False
        assert "request_id" in body  # 中间件应该已注入

    def test_app_error_returns_correct_status(self):
        resp = self.client.get("/raise-app-error")
        assert resp.status_code == 404
        body = resp.json()
        assert body["code"] == "TASK_NOT_FOUND"
        assert body["success"] is False

    def test_http_exception_passthrough(self):
        resp = self.client.get("/raise-http-exception")
        assert resp.status_code == 403
        body = resp.json()
        assert body["code"] == "HTTP_ERROR"
        assert body["message"] == "forbidden"
        assert body["success"] is False

    def test_unhandled_exception_returns_500(self):
        resp = self.client.get("/raise-unhandled")
        assert resp.status_code == 500
        body = resp.json()
        assert body["code"] == "INTERNAL_ERROR"
        assert "RuntimeError" in body["message"]

    def test_unhandled_exception_includes_request_id(self):
        resp = self.client.get("/raise-unhandled")
        body = resp.json()
        # global_exception_handler 直接返回 JSONResponse，绕过中间件 call_next 流程
        # 因此 X-Request-ID header 不一定在 response 上，但 body 内一定有
        assert "request_id" in body
        assert len(body["request_id"]) > 0


# ============== RequestID 中间件测试 ==============

class TestRequestIDMiddleware:
    """X-Request-ID 中间件行为"""

    def setup_method(self):
        self.app = _make_app()

        @self.app.get("/ping")
        async def ping():
            return {"pong": True}

        @self.app.get("/fail")
        async def fail():
            raise AppError("FAIL", "bang", 400)

        self.client = TestClient(self.app, raise_server_exceptions=False)

    def test_auto_generate_when_missing(self):
        resp = self.client.get("/ping")
        rid = resp.headers.get("X-Request-ID")
        assert rid is not None
        assert len(rid) == 12  # uuid4 hex[:12]

    def test_passthrough_custom_request_id(self):
        custom_rid = "my-custom-id-42"
        resp = self.client.get("/ping", headers={"X-Request-ID": custom_rid})
        assert resp.headers.get("X-Request-ID") == custom_rid

    def test_error_response_includes_request_id(self):
        resp = self.client.get("/fail")
        body = resp.json()
        rid_header = resp.headers.get("X-Request-ID")
        assert "request_id" in body
        assert body["request_id"] == rid_header

    def test_different_requests_get_different_ids(self):
        r1 = self.client.get("/ping")
        r2 = self.client.get("/ping")
        id1 = r1.headers.get("X-Request-ID")
        id2 = r2.headers.get("X-Request-ID")
        assert id1 != id2
