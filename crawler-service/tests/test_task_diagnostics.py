import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from standalone.models import TaskStatus
from standalone.routes import _enrich_task
from standalone.task_diagnostics import build_task_diagnostics, classify_failure


def _task(**overrides):
    data = {
        "id": 1,
        "task_type": "digest",
        "source_url": None,
        "keyword": "daily digest",
        "search_engine": "sogou",
        "max_depth": 1,
        "max_pages": 10,
        "ai_template": "daily_digest",
        "status": TaskStatus.FAILED,
        "error_message": None,
        "ai_error_message": None,
        "total_pages": 0,
        "completed_pages": 0,
        "ai_search_metadata": None,
    }
    data.update(overrides)
    return data


def test_classify_ai_failure_from_timeout_message():
    result = classify_failure("AI timeout while organizing digest")

    assert result["category"] == "ai"
    assert result["severity"] == "warning"
    assert "AI" in result["label"]


def test_classify_search_failure_from_empty_results():
    result = classify_failure("No search results found for keyword")

    assert result["category"] == "search"
    assert result["severity"] == "warning"


def test_classify_quality_gate_failure_from_digest_threshold():
    result = classify_failure("Digest quality below publish threshold (score=0.438)")

    assert result["category"] == "quality_gate"
    assert result["severity"] == "danger"


def test_build_task_diagnostics_uses_ai_error_when_task_completed():
    diagnostics = build_task_diagnostics(_task(
        status=TaskStatus.COMPLETED,
        error_message=None,
        ai_error_message="AI timeout",
        total_pages=3,
        completed_pages=3,
    ))

    assert diagnostics["stage"] == "completed"
    assert diagnostics["failure"]["category"] == "ai"
    assert diagnostics["signals"]["ai_error"] is True


def test_build_task_diagnostics_marks_stalled_crawl_when_no_pages_finished():
    diagnostics = build_task_diagnostics(_task(
        status=TaskStatus.FAILED,
        error_message="All pages failed",
        total_pages=5,
        completed_pages=0,
    ))

    assert diagnostics["stage"] == "failed"
    assert diagnostics["signals"]["no_completed_pages"] is True
    assert diagnostics["failure"]["category"] == "source"


def test_enrich_task_exposes_task_diagnostics():
    enriched = _enrich_task(_task(
        error_message="Callback failed: Invalid callback key",
        total_pages=2,
        completed_pages=1,
    ))

    assert enriched["diagnostics"]["failure"]["category"] == "callback"
    assert enriched["diagnostics"]["signals"]["partial_pages"] is True
