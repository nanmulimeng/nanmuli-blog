"""Digest runtime health API tests."""

import os
import sys
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from standalone import repository as repo
from standalone.routes import router


@pytest.fixture
def app(mem_db):
    @asynccontextmanager
    async def _mock_get_db():
        yield mem_db

    orig_db = repo.get_db
    repo.get_db = _mock_get_db

    _app = FastAPI()
    _app.include_router(router, prefix="/api/v1")
    yield _app

    repo.get_db = orig_db


@pytest.mark.asyncio
async def test_runtime_health_reports_healthy_when_core_signals_are_good(app):
    scheduler_status = {
        "running": True,
        "enabled": True,
        "cron": "0 8 * * 1-5",
        "next_run": "2026-06-22 08:00:00+08:00",
        "source_jobs": 3,
        "digest_job_registered": True,
        "ai_enabled": True,
        "ai_configured": True,
    }
    sections = [
        {"name": "hot_trend"},
        {"name": "open_source"},
        {"name": "dev_tool"},
        {"name": "tech_article"},
        {"name": "paper"},
    ]
    overview = {
        "summary": {"latest_score": 0.82, "average_score": 0.78, "status": "success"},
        "next_run_actions": {
            "confidence": "medium",
            "source_ids": {"skip": [], "deprioritize": [101]},
            "source_urls": {"skip": [], "deprioritize": []},
            "boost_sections": ["source_diversity"],
            "safety": {"applied": [], "downgraded": [], "section_source_counts": {"hot_trend": 3}},
        },
    }
    feedback = [{
        "digest_date": "2026-06-21",
        "summary": {
            "keep_rate": 0.66,
            "zero_result_queries": [],
            "total_queries": 8,
            "total_kept": 20,
            "total_returned": 30,
        },
    }]
    kb = MagicMock()
    kb.get_digest_quality_overview = AsyncMock(return_value=overview)

    with patch("standalone.scheduler.get_scheduler_status", return_value=scheduler_status), \
         patch("standalone.task_executor.get_digest_sections", new_callable=AsyncMock, return_value=sections), \
         patch("optimization.knowledge_base.KnowledgeBase", return_value=kb), \
         patch.object(repo, "get_recent_digest_search_feedback", new_callable=AsyncMock, return_value=feedback):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/api/v1/digests/runtime/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "healthy"
    assert body["summary"]["blocking"] is False
    assert body["config"]["sections_count"] == 5
    assert body["optimization_safety"]["status"] == "success"
    assert body["search_feedback"]["latest_keep_rate"] == 0.66
    assert {check["key"] for check in body["checks"]} >= {
        "scheduler", "ai", "digest_job", "sections", "optimization_safety"
    }


@pytest.mark.asyncio
async def test_runtime_health_marks_blocking_when_ai_and_sections_are_not_ready(app):
    scheduler_status = {
        "running": True,
        "enabled": True,
        "cron": "0 8 * * 1-5",
        "next_run": None,
        "source_jobs": 0,
        "digest_job_registered": True,
        "ai_enabled": True,
        "ai_configured": False,
    }
    sections = [{"name": "hot_trend"}]
    overview = {
        "summary": {"latest_score": 0.51, "average_score": 0.57, "status": "danger"},
        "next_run_actions": {
            "confidence": "low",
            "source_ids": {"skip": [1], "deprioritize": []},
            "source_urls": {"skip": [], "deprioritize": []},
            "boost_sections": [],
            "safety": {
                "applied": ["low-confidence-skip-downgrade"],
                "downgraded": [{"source_id": 1, "reason": "low-confidence"}],
                "section_source_counts": {"hot_trend": 1},
            },
        },
    }
    kb = MagicMock()
    kb.get_digest_quality_overview = AsyncMock(return_value=overview)

    with patch("standalone.scheduler.get_scheduler_status", return_value=scheduler_status), \
         patch("standalone.task_executor.get_digest_sections", new_callable=AsyncMock, return_value=sections), \
         patch("optimization.knowledge_base.KnowledgeBase", return_value=kb), \
         patch.object(repo, "get_recent_digest_search_feedback", new_callable=AsyncMock, return_value=[]):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/api/v1/digests/runtime/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "danger"
    assert body["summary"]["blocking"] is True
    assert body["optimization_safety"]["status"] == "warning"
    checks = {check["key"]: check for check in body["checks"]}
    assert checks["ai"]["status"] == "danger"
    assert checks["sections"]["status"] == "danger"
    assert any("AI" in item or "ai" in item for item in body["recommendations"])
