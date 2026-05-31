"""任务级 callback 测试。"""

import os
import sys
from contextlib import asynccontextmanager

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from standalone import repository as repo


@pytest.mark.asyncio
async def test_task_callback_url_and_headers_override_global_defaults(mem_db, monkeypatch):
    """任务级 callback_url 优先于全局 callback_url，且发送任务级 headers。"""
    @asynccontextmanager
    async def _mock_get_db():
        yield mem_db

    orig_db = repo.get_db
    repo.get_db = _mock_get_db
    try:
        task_id = await repo.create_task(
            task_type="single",
            source_url="https://example.com/article",
            callback_url="https://client.example.com/crawler/callback",
            callback_headers_json='{"X-Client-Token":"secret"}',
        )

        from config import settings
        from standalone.task_executor import _fire_callback

        original_url = settings.callback_url
        original_key = settings.callback_api_key
        settings.callback_url = "https://blog.example.com/internal/callback"
        settings.callback_api_key = "global-secret"

        calls = []

        class FakeResponse:
            status_code = 200

        class FakeAsyncClient:
            def __init__(self, timeout):
                self.timeout = timeout

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def post(self, url, json, headers):
                calls.append({"url": url, "json": json, "headers": headers})
                return FakeResponse()

        import httpx
        monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

        try:
            await _fire_callback(task_id, 3)
        finally:
            settings.callback_url = original_url
            settings.callback_api_key = original_key
    finally:
        repo.get_db = orig_db

    assert calls == [{
        "url": "https://client.example.com/crawler/callback",
        "json": {"python_task_id": task_id, "status": 3},
        "headers": {
            "Content-Type": "application/json",
            "X-Client-Token": "secret",
            "X-Callback-Key": "global-secret",
        },
    }]


@pytest.mark.asyncio
async def test_digest_task_without_task_callback_does_not_fire_global_java_callback(mem_db, monkeypatch):
    """Python-native digest tasks should not call Java task callback unless a task callback is supplied."""
    @asynccontextmanager
    async def _mock_get_db():
        yield mem_db

    orig_db = repo.get_db
    repo.get_db = _mock_get_db
    try:
        task_id = await repo.create_task(
            task_type="digest",
            keyword="2026-05-28",
            ai_template="daily_digest",
        )

        from config import settings
        from standalone.task_executor import _fire_callback

        original_url = settings.callback_url
        settings.callback_url = "https://blog.example.com/api/internal/collector/callback"
        calls = []

        class FakeAsyncClient:
            def __init__(self, timeout):
                self.timeout = timeout

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def post(self, url, json, headers):
                calls.append({"url": url, "json": json, "headers": headers})
                raise AssertionError("digest task should not fire global callback")

        import httpx
        monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

        try:
            await _fire_callback(task_id, 3)
        finally:
            settings.callback_url = original_url
    finally:
        repo.get_db = orig_db

    assert calls == []


@pytest.mark.asyncio
async def test_callback_rejects_java_result_error_even_when_http_status_is_200(mem_db, monkeypatch, caplog):
    """Java Result.error uses HTTP 200, so callback must inspect body code."""
    @asynccontextmanager
    async def _mock_get_db():
        yield mem_db

    orig_db = repo.get_db
    repo.get_db = _mock_get_db
    try:
        task_id = await repo.create_task(
            task_type="single",
            source_url="https://example.com/article",
        )

        from config import settings
        from standalone.task_executor import _fire_callback

        original_url = settings.callback_url
        settings.callback_url = "https://blog.example.com/api/internal/collector/callback"
        calls = []

        class FakeResponse:
            status_code = 200
            text = '{"code":403,"message":"Invalid callback key"}'

            def json(self):
                return {"code": 403, "message": "Invalid callback key"}

        class FakeAsyncClient:
            def __init__(self, timeout):
                self.timeout = timeout

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def post(self, url, json, headers):
                calls.append({"url": url, "json": json, "headers": headers})
                return FakeResponse()

        import httpx
        monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

        try:
            caplog.set_level("WARNING")
            await _fire_callback(task_id, 3)
        finally:
            settings.callback_url = original_url
    finally:
        repo.get_db = orig_db

    assert len(calls) == 1
    assert "Callback rejected" in caplog.text
