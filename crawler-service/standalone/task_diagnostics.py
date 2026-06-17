"""Task diagnostics for admin observability.

The diagnostics object is intentionally small and schema-stable so the Java
backend and Vue admin UI can display it without understanding crawler internals.
"""

from __future__ import annotations

from typing import Any

from standalone.models import TaskStatus


_FAILURE_RULES = [
    (
        "quality_gate",
        ("digest quality below", "publish threshold", "low-value digest candidate", "quality below"),
        "质量门槛",
        "danger",
        "日报质量未达到发布阈值。优先查看低质来源、重复来源和 section 覆盖情况。",
    ),
    (
        "callback",
        ("callback", "x-callback", "invalid callback key", "java result", "result.error"),
        "回调链路",
        "warning",
        "检查 callback URL、callback key 和 Java internal endpoint 是否可访问。",
    ),
    (
        "ai",
        ("ai ", "ai_", "openai", "model", "token", "rate limit", "organize", "organizer", "llm"),
        "AI 调用",
        "warning",
        "检查 AI key、base URL、模型名、限流和 token 预算。",
    ),
    (
        "search",
        ("no search results", "search results", "search engine", "sogou", "bing", "baidu", "google", "captcha"),
        "搜索链路",
        "warning",
        "检查搜索引擎、代理、关键词和 fallback 搜索是否有效。",
    ),
    (
        "crawler_runtime",
        ("browser", "chromium", "playwright", "crawl4ai", "crawler unavailable", "dependency", "crash"),
        "爬虫运行时",
        "danger",
        "检查浏览器依赖、Crawl4AI、browser_channel 和服务器运行环境。",
    ),
    (
        "security",
        ("private address", "ssrf", "not allowed", "unauthorized", "api key", "invalid or missing api key"),
        "安全拦截",
        "warning",
        "检查目标 URL、API key、SSRF 规则和调用方认证配置。",
    ),
    (
        "source",
        ("all pages failed", "content too short", "connection refused", "timeout", "404", "403", "503"),
        "源站/内容",
        "warning",
        "检查源站是否可访问、是否反爬、内容是否过短或页面类型不适合日报。",
    ),
]


def classify_failure(message: str | None) -> dict[str, str]:
    text = (message or "").strip()
    if not text:
        return {
            "category": "none",
            "label": "暂无异常",
            "severity": "info",
            "action_hint": "任务当前没有记录错误信息。",
        }

    lowered = text.lower()
    for category, needles, label, severity, action_hint in _FAILURE_RULES:
        if any(needle in lowered for needle in needles):
            return {
                "category": category,
                "label": label,
                "severity": severity,
                "action_hint": action_hint,
            }

    return {
        "category": "unknown",
        "label": "未知异常",
        "severity": "warning",
        "action_hint": "查看 crawler 日志和任务页面错误详情，必要时按 trace/task id 排查。",
    }


def build_task_diagnostics(task: dict[str, Any]) -> dict[str, Any]:
    status = int(task.get("status") or 0)
    total_pages = int(task.get("total_pages") or 0)
    completed_pages = int(task.get("completed_pages") or 0)
    error_message = task.get("error_message")
    ai_error_message = task.get("ai_error_message")
    diagnostic_message = error_message or ai_error_message

    stage = {
        TaskStatus.PENDING: "pending",
        TaskStatus.CRAWLING: "crawling",
        TaskStatus.PROCESSING: "processing",
        TaskStatus.COMPLETED: "completed",
        TaskStatus.FAILED: "failed",
    }.get(status, "unknown")

    signals = {
        "terminal": TaskStatus.is_terminal(status),
        "active": TaskStatus.is_active(status),
        "ai_error": bool(ai_error_message),
        "has_error_message": bool(error_message),
        "no_completed_pages": total_pages > 0 and completed_pages == 0,
        "partial_pages": total_pages > 0 and 0 < completed_pages < total_pages,
    }

    failure = classify_failure(diagnostic_message)
    if failure["category"] == "unknown" and signals["no_completed_pages"]:
        failure = classify_failure("all pages failed")

    return {
        "stage": stage,
        "failure": failure,
        "signals": signals,
        "summary": _build_summary(stage, failure, signals),
    }


def _build_summary(stage: str, failure: dict[str, str], signals: dict[str, bool]) -> str:
    if failure["category"] != "none":
        return f"{failure['label']}：{failure['action_hint']}"
    if stage == "completed" and signals.get("ai_error"):
        return "任务已完成，但 AI 整理阶段出现过错误，请检查 AI 结果是否完整。"
    if stage == "completed":
        return "任务已完成，未记录明显异常。"
    if stage == "failed":
        return "任务失败但缺少明确错误信息，请查看 crawler 日志。"
    return "任务仍在执行中，继续观察采集进度和错误信息。"
