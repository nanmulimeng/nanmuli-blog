"""独立模式管理 API 路由"""

import json
import logging

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, HttpUrl
from typing import Optional as Opt

from standalone.models import TaskStatus, TASK_TYPE_LABELS, AI_TEMPLATE_LABELS
from standalone import repository as repo
from standalone.task_executor import executor
from standalone.task_diagnostics import build_task_diagnostics
from standalone.export import export_task_as_markdown
from standalone import backend_config
from config import settings
from api.crawl import CrawlConfig
from ai.config import ai_settings
from api.ssrf_guard import _is_private_url

logger = logging.getLogger(__name__)
router = APIRouter(tags=["standalone"])


# ============== Request Models ==============

class CreateTaskRequest(BaseModel):
    task_type: str = Field(..., pattern="^(single|deep|keyword|digest)$")
    url: Opt[HttpUrl] = None
    keyword: Opt[str] = None
    search_engine: str = Field(default="sogou", pattern="^(sogou|bing|baidu|google)$")
    max_depth: int = Field(default=1, ge=1, le=settings.max_depth_limit)
    max_pages: int = Field(default=10, ge=1, le=settings.max_pages_limit)
    ai_template: str = Field(default="tech_summary", pattern="^(tech_summary|tutorial|comparison|knowledge_report|daily_digest)$")
    time_range: str = Field(default="week", pattern="^(day|week|month|year|all)$")
    config: Opt[CrawlConfig] = None
    callback_url: Opt[HttpUrl] = None
    callback_headers: dict[str, str] = Field(default_factory=dict)


class SourceTestRequest(BaseModel):
    type: str = Field(..., pattern="^(url|keyword|rss)$")
    value: str = Field(..., min_length=1, max_length=2048)
    content_category: str = Field(default="tech_article", pattern="^(hot_trend|open_source|tech_article|dev_tool|creative|paper)$")
    crawl_mode: str = Field(default="single", pattern="^(single|deep)$")
    max_depth: int = Field(default=1, ge=1, le=settings.max_depth_limit)
    max_pages: int = Field(default=3, ge=1, le=5)
    freshness_hours: int = Field(default=24, ge=1, le=720)
    search_engine: str = Field(default="bing", pattern="^(sogou|bing|baidu|google)$")
    source_id: Opt[str] = None
    source_name: Opt[str] = None


# ============== Helpers ==============

def _enrich_task(task: dict) -> dict:
    """为任务响应添加标签和进度（不修改原始 dict）"""
    task = dict(task)
    task.pop("callback_headers", None)
    task["task_type_label"] = TASK_TYPE_LABELS.get(task["task_type"], task["task_type"])
    task["status_label"] = TaskStatus.label(task["status"])

    tp = task.get("total_pages", 0) or 0
    cp = task.get("completed_pages", 0) or 0
    progress = min(100, int(cp * 100 / tp)) if tp > 0 else 0
    if task.get("status") not in (TaskStatus.COMPLETED, TaskStatus.FAILED):
        progress = min(progress, 99)
    task["progress_percent"] = progress

    # 解析 AI JSON 字段
    for field in ("ai_key_points", "ai_tags"):
        raw = task.get(field)
        if raw and isinstance(raw, str):
            try:
                task[field] = json.loads(raw)
            except json.JSONDecodeError:
                pass

    # 解析 AI 搜索元数据
    raw_meta = task.get("ai_search_metadata")
    if raw_meta and isinstance(raw_meta, str):
        try:
            task["ai_search_metadata"] = json.loads(raw_meta)
        except json.JSONDecodeError:
            pass

    diagnostics = build_task_diagnostics(task)
    task["diagnostics"] = diagnostics
    if isinstance(task.get("ai_search_metadata"), dict):
        task["ai_search_metadata"].setdefault("diagnostics", diagnostics)

    task["ai_template_label"] = AI_TEMPLATE_LABELS.get(
        task.get("ai_template", "tech_summary"), "技术摘要"
    )

    return task


def _summarize_source_test_results(results: list) -> dict:
    items = []
    for result in results[:5]:
        metadata = getattr(result, "metadata", {}) or {}
        items.append({
            "success": bool(getattr(result, "success", False)),
            "url": getattr(result, "url", "") or "",
            "title": getattr(result, "title", "") or metadata.get("feed_title") or "",
            "word_count": getattr(result, "word_count", 0) or 0,
            "markdown_len": len(getattr(result, "markdown", "") or ""),
            "source_id": metadata.get("source_id"),
            "source_name": metadata.get("source_name"),
            "error": getattr(result, "error_message", None),
        })

    success_count = sum(1 for result in results if getattr(result, "success", False))
    total = len(results)
    return {
        "total": total,
        "success_count": success_count,
        "failed_count": max(total - success_count, 0),
        "crawlable": success_count > 0,
        "items": items,
    }


def _scheduler_check(key: str, label: str, status: str, message: str) -> dict:
    return {
        "key": key,
        "label": label,
        "status": status,
        "message": message,
    }


def _build_scheduler_diagnostics(status: dict) -> dict:
    """Build a stable scheduler diagnostics payload for admin UI."""
    latest = status.get("latest_digest")
    checks = []

    enabled = bool(status.get("enabled"))
    running = bool(status.get("running"))
    digest_job_registered = bool(status.get("digest_job_registered"))
    ai_enabled = bool(status.get("ai_enabled"))
    ai_configured = bool(status.get("ai_configured"))

    checks.append(_scheduler_check(
        "scheduler",
        "调度器",
        "success" if running else ("warning" if not enabled else "danger"),
        "调度器运行中" if running else "调度器未运行",
    ))
    checks.append(_scheduler_check(
        "digest_job",
        "日报任务",
        "success" if digest_job_registered else ("info" if not enabled else "warning"),
        "日报定时任务已注册" if digest_job_registered else "日报定时任务未注册",
    ))
    checks.append(_scheduler_check(
        "ai",
        "AI 配置",
        "success" if (not ai_enabled or ai_configured) else "warning",
        "AI 可用" if ai_configured else ("AI 未启用" if not ai_enabled else "AI 已启用但缺少可用配置"),
    ))

    if latest:
        latest_diagnostics = latest.get("diagnostics") or {}
        latest_failure = latest_diagnostics.get("failure") or {}
        latest_status = latest.get("status")
        latest_status_label = latest.get("status_label") or str(latest_status)
        latest_message = latest.get("error_message") or latest_diagnostics.get("summary") or latest_status_label
        checks.append(_scheduler_check(
            "latest_digest",
            "最近执行",
            "danger" if latest_status == TaskStatus.FAILED else ("warning" if latest_status in (TaskStatus.PENDING, TaskStatus.CRAWLING, TaskStatus.PROCESSING) else "success"),
            latest_message,
        ))
    else:
        latest_failure = {}
        checks.append(_scheduler_check(
            "latest_digest",
            "最近执行",
            "info",
            "暂无日报执行记录",
        ))

    if not enabled:
        state = "disabled"
        summary = "自动日报未启用"
        action_hint = "如需自动生成日报，请先启用 digest.enabled 并刷新 crawler 配置。"
    elif not running:
        state = "misconfigured"
        summary = "自动日报已启用，但调度器未运行"
        action_hint = "检查 crawler-service 启动日志和 scheduler 初始化状态。"
    elif ai_enabled and not ai_configured:
        state = "misconfigured"
        summary = "AI 已启用但配置不完整"
        action_hint = "检查 AI API Key、base URL 和 model 配置，然后刷新 crawler 配置。"
    elif not digest_job_registered:
        state = "misconfigured"
        summary = "日报调度任务未注册"
        action_hint = "检查 digest cron 表达式和调度器注册日志，必要时刷新配置。"
    elif latest and latest.get("status") == TaskStatus.FAILED:
        state = "latest_failed"
        summary = latest_failure.get("label") or "最近一次日报执行失败"
        action_hint = latest_failure.get("action_hint") or "打开最近日报详情，按失败阶段继续排查。"
    elif latest and latest.get("status") in (TaskStatus.PENDING, TaskStatus.CRAWLING, TaskStatus.PROCESSING):
        state = "running"
        summary = "日报任务正在执行"
        action_hint = "继续观察任务详情中的阶段、页面数、AI 处理和错误信息。"
    elif not latest:
        state = "idle"
        summary = "自动日报已就绪，暂无执行记录"
        action_hint = "等待下一次 cron，或在管理端手动触发一次日报生成。"
    else:
        state = "healthy"
        summary = "自动日报最近执行正常"
        action_hint = "继续观察质量趋势和自动优化动作即可。"

    return {
        "state": state,
        "summary": summary,
        "action_hint": action_hint,
        "checks": checks,
    }


def _runtime_check(
    key: str,
    label: str,
    status: str,
    message: str,
    blocking: bool = False,
) -> dict:
    return {
        "key": key,
        "label": label,
        "status": status,
        "message": message,
        "blocking": blocking,
    }


def _runtime_status(checks: list[dict]) -> str:
    if any(c.get("status") == "danger" for c in checks):
        return "danger"
    if any(c.get("status") == "warning" for c in checks):
        return "warning"
    if any(c.get("status") == "info" for c in checks):
        return "info"
    return "healthy"


def _configured_core_sections() -> list[str]:
    raw = getattr(settings, "digest_publish_core_sections", None)
    if isinstance(raw, str):
        return [item.strip() for item in raw.split(",") if item.strip()]
    if isinstance(raw, (list, tuple, set)):
        return [str(item).strip() for item in raw if str(item).strip()]
    return ["hot_trend", "open_source", "dev_tool", "tech_article", "paper"]


def _summarize_runtime_sections(sections: list[dict]) -> dict:
    names = [str(sec.get("name") or "").strip() for sec in sections if sec.get("name")]
    core_sections = _configured_core_sections()
    configured_core = [name for name in core_sections if name in names]
    min_core = int(getattr(settings, "digest_publish_min_core_sections", 3) or 3)
    missing_core = [name for name in core_sections if name not in names]
    return {
        "sections_count": len(names),
        "section_names": names,
        "core_sections": core_sections,
        "configured_core_sections": configured_core,
        "missing_core_sections": missing_core,
        "min_core_sections": min_core,
        "core_coverage_ok": len(configured_core) >= min_core,
    }


def _summarize_next_run_action_safety(actions: dict | None) -> dict:
    actions = actions or {}
    source_ids = actions.get("source_ids") or {}
    source_urls = actions.get("source_urls") or {}
    safety = actions.get("safety") or {}
    skip_count = len(source_ids.get("skip") or []) + len(source_urls.get("skip") or [])
    deprioritize_count = (
        len(source_ids.get("deprioritize") or [])
        + len(source_urls.get("deprioritize") or [])
    )
    confidence = actions.get("confidence") or "none"
    applied = safety.get("applied") or []
    downgraded = safety.get("downgraded") or []
    status = "success"
    if confidence == "low" or downgraded:
        status = "warning"
    if skip_count > 0 and not applied and confidence in ("none", "low"):
        status = "danger"
    return {
        "status": status,
        "confidence": confidence,
        "skip_count": skip_count,
        "deprioritize_count": deprioritize_count,
        "boost_sections": actions.get("boost_sections") or [],
        "safety_applied": applied,
        "downgraded_count": len(downgraded),
        "section_source_counts": safety.get("section_source_counts") or {},
    }


def _summarize_search_feedback(records: list[dict]) -> dict:
    latest = records[0] if records else None
    summary = latest.get("summary") if latest else None
    summary = summary or {}
    return {
        "latest_digest_date": latest.get("digest_date") if latest else None,
        "latest_keep_rate": summary.get("keep_rate"),
        "zero_result_queries": summary.get("zero_result_queries") or [],
        "total_queries": summary.get("total_queries"),
        "total_kept": summary.get("total_kept"),
        "total_returned": summary.get("total_returned"),
    }


# ============== Endpoints ==============

@router.post("/tasks", status_code=201)
async def create_task(request: CreateTaskRequest):
    """创建爬取任务（异步执行：爬取 + AI 整理）"""
    if request.task_type in ("single", "deep") and not request.url:
        raise HTTPException(400, "url is required for single/deep task type")
    if request.task_type == "keyword" and not request.keyword:
        raise HTTPException(400, "keyword is required for keyword task type")

    # SSRF 防护：禁止爬取内网地址
    if request.url and _is_private_url(str(request.url)):
        raise HTTPException(400, "不允许爬取内网/私有地址")
    if (
        request.callback_url
        and not settings.callback_allow_private_urls
        and _is_private_url(str(request.callback_url))
    ):
        raise HTTPException(400, "callback_url 不允许使用内网/私有地址")

    source_url = str(request.url) if request.url else None
    config_json = request.config.model_dump_json() if request.config else None
    callback_url = str(request.callback_url) if request.callback_url else None
    callback_headers_json = (
        json.dumps(request.callback_headers, ensure_ascii=False)
        if request.callback_headers else None
    )

    task_id = await repo.create_task(
        task_type=request.task_type,
        source_url=source_url,
        keyword=request.keyword,
        search_engine=request.search_engine,
        max_depth=request.max_depth,
        max_pages=request.max_pages,
        config_json=config_json,
        ai_template=request.ai_template,
        time_range=request.time_range,
        callback_url=callback_url,
        callback_headers_json=callback_headers_json,
    )

    await executor.submit(task_id)

    return {
        "id": task_id,
        "task_type": request.task_type,
        "task_type_label": TASK_TYPE_LABELS.get(request.task_type, request.task_type),
        "ai_template": request.ai_template,
        "status": TaskStatus.PENDING,
        "status_label": TaskStatus.label(TaskStatus.PENDING),
        "message": "任务已创建，正在后台执行（爬取 + AI 整理）",
    }


@router.post("/sources/test")
async def test_source(request: SourceTestRequest):
    """Run a small, non-persistent crawl preview for one source configuration."""
    source_type = request.type
    source_value = request.value.strip()

    if source_type in ("url", "rss") and _is_private_url(source_value):
        raise HTTPException(400, "source value 不允许使用内网/私有地址")

    max_items = min(request.max_pages or 3, 5)
    source_id = request.source_id
    source_name = request.source_name or ""
    section = {
        "name": request.content_category,
        "max_items": max_items,
    }

    try:
        if source_type == "rss":
            from crawler.config import get_browser_config
            from crawler.dependencies import get_async_web_crawler
            from crawler.source_crawler import crawl_rss_sources

            section["rss_sources"] = [{
                "feed_url": source_value,
                "freshness_hours": request.freshness_hours,
                "max_entries": max_items,
                "source_id": source_id,
                "source_name": source_name,
                "effectiveness": {"dead": False},
            }]
            browser_config = await get_browser_config(text_mode=True, light_mode=True, proxy=settings.proxy_url)
            AsyncWebCrawler = get_async_web_crawler()
            async with AsyncWebCrawler(config=browser_config) as crawler:
                results = await crawl_rss_sources(section, config=None, crawler=crawler)
        elif source_type == "url":
            from crawler.config import get_browser_config
            from crawler.dependencies import get_async_web_crawler
            from crawler.source_crawler import crawl_url_sources

            section["url_sources"] = [{
                "url": source_value,
                "crawl_mode": request.crawl_mode,
                "max_depth": request.max_depth,
                "max_pages": max_items,
                "source_id": source_id,
                "source_name": source_name,
                "effectiveness": {"dead": False},
            }]
            browser_config = await get_browser_config(text_mode=True, light_mode=True, proxy=settings.proxy_url)
            AsyncWebCrawler = get_async_web_crawler()
            async with AsyncWebCrawler(config=browser_config) as crawler:
                results = await crawl_url_sources(section, config=None, crawler=crawler)
        else:
            from crawler.search import crawl_by_keyword

            results = await crawl_by_keyword(
                keyword=source_value,
                engine=request.search_engine,
                max_results=max_items,
                time_range="day" if request.freshness_hours <= 24 else "week",
                config=None,
                skip_dedup=True,
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("Source test failed: type=%s value=%s error=%s", source_type, source_value, e)
        raise HTTPException(502, f"source test failed: {e}")

    summary = _summarize_source_test_results(results)
    summary.update({
        "source_type": source_type,
        "source_value": source_value,
        "content_category": request.content_category,
    })
    return summary


@router.get("/tasks")
async def list_tasks(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    status: Opt[int] = Query(None),
    task_type: Opt[str] = Query(None),
):
    """查询任务列表（分页）"""
    records, total = await repo.list_tasks(status=status, task_type=task_type, page=page, size=size)
    records = [_enrich_task(r) for r in records]
    return {"total": total, "page": page, "size": size, "records": records}


@router.get("/tasks/{task_id}")
async def get_task(task_id: int):
    """查询任务详情（含 AI 结果）"""
    task = await repo.get_task(task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    return _enrich_task(task)


@router.get("/tasks/{task_id}/pages")
async def get_task_pages(task_id: int):
    """查询任务的页面列表"""
    task = await repo.get_task(task_id)
    if not task:
        raise HTTPException(404, "任务不存在")

    pages = await repo.get_pages_by_task(task_id)
    for p in pages:
        p["status_label"] = "已完成" if p["crawl_status"] == 2 else "失败" if p["crawl_status"] == 3 else "待处理"

    return {"task_id": task_id, "pages": pages, "total": len(pages)}


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: int):
    """删除任务"""
    task = await repo.get_task(task_id)
    if not task:
        raise HTTPException(404, "任务不存在")

    if not TaskStatus.is_terminal(task["status"]):
        raise HTTPException(400, "任务正在处理中，无法删除")

    await repo.delete_task(task_id)
    return {"message": f"任务 {task_id} 已删除"}


@router.post("/tasks/{task_id}/retry")
async def retry_task(task_id: int):
    """重试失败的任务"""
    task = await repo.get_task(task_id)
    if not task:
        raise HTTPException(404, "任务不存在")

    if task["status"] != TaskStatus.FAILED:
        raise HTTPException(400, "只有失败的任务才能重试")

    await repo.reset_task_for_retry(task_id)
    await executor.submit(task_id)

    return {
        "id": task_id,
        "status": TaskStatus.PENDING,
        "status_label": TaskStatus.label(TaskStatus.PENDING),
        "message": "任务已重置，正在重新执行",
    }


@router.post("/tasks/{task_id}/organize")
async def re_organize_task(task_id: int):
    """手动重新执行 AI 整理（不重新爬取）"""
    task = await repo.get_task(task_id)
    if not task:
        raise HTTPException(404, "任务不存在")

    if task["status"] not in (TaskStatus.COMPLETED, TaskStatus.FAILED):
        raise HTTPException(400, "只有已完成或失败的任务才能重新整理")

    # 竞态保护：检查执行器是否正在处理该任务
    if executor.is_running(task_id):
        raise HTTPException(409, "任务正在执行中，请稍后重试")

    from ai import content_organizer as organizer
    if not organizer.is_available:
        raise HTTPException(503, "AI 服务未配置")

    # 获取已有页面
    pages = await repo.get_pages_by_task(task_id)
    if not pages:
        raise HTTPException(400, "没有可整理的页面内容")

    original_status = task["status"]
    await repo.update_task_status(task_id, TaskStatus.PROCESSING)

    try:
        task_type = task["task_type"]

        if task_type == "digest":
            from standalone.organizer_helper import organize_digest_and_save
            result = await organize_digest_and_save(task_id, task, pages, organizer)
        else:
            from standalone.organizer_helper import organize_content_and_save
            result = await organize_content_and_save(task_id, task, pages, organizer)

        # 成功后恢复 COMPLETED 状态（之前设为了 PROCESSING）
        await repo.update_task_status(task_id, TaskStatus.COMPLETED)
        return {"message": "AI 整理完成", "title": result.title}

    except ValueError as e:
        await repo.update_task_status(task_id, original_status)
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error("Re-organize failed for task %d: %s", task_id, e)
        await repo.update_task_status(task_id, original_status)
        raise HTTPException(500, f"AI 整理失败: {str(e)}")


@router.get("/tasks/{task_id}/export")
async def export_task(task_id: int):
    """导出任务结果为 Markdown 文件"""
    task = await repo.get_task(task_id)
    if not task:
        raise HTTPException(404, "任务不存在")

    if task["status"] != TaskStatus.COMPLETED:
        raise HTTPException(400, "只有已完成的任务才能导出")

    return await export_task_as_markdown(task_id)


@router.get("/config/ai")
async def get_ai_config():
    """检查 AI 配置状态"""
    from ai import content_organizer as organizer
    return {
        "available": organizer.is_available,
        "model": ai_settings.ai_model if organizer.is_available else None,
    }


@router.get("/stats")
async def get_stats():
    """获取统计信息"""
    stats = await repo.get_stats()
    from crawler.search import get_selector_health
    stats["selector_health"] = get_selector_health()
    return stats


# ============== Optimization API ==============

@router.get("/optimization/config")
async def get_optimization_config():
    """查看优化引擎配置"""
    from config import settings as s
    return {
        "enabled": s.optimization_enabled,
        "depth_target_score": s.optimization_depth_target_score,
        "breadth_target_score": s.optimization_breadth_target_score,
        "max_rounds": s.optimization_max_rounds,
        "min_improvement": s.optimization_min_improvement,
        "mode": s.optimization_mode,
    }


@router.get("/optimization/history")
async def get_optimization_history(
    task_id: Opt[int] = Query(None),
    limit: int = Query(20, ge=1, le=100),
):
    """查看优化历史记录"""
    if task_id:
        records = await repo.get_optimization_records(task_id)
        return {"task_id": task_id, "records": records}

    strategies = await repo.get_effective_strategies(limit)
    return {"effective_strategies": strategies}


@router.get("/optimization/search-feedback")
async def get_search_feedback(limit: int = Query(10, ge=1, le=50)):
    """Return recent digest search diagnostics as replayable feedback snapshots."""
    records = await repo.get_recent_digest_search_feedback(limit=limit)
    return {
        "total": len(records),
        "limit": limit,
        "records": records,
    }


@router.get("/optimization/stats")
async def get_optimization_stats():
    """优化引擎统计"""
    from optimization.knowledge_base import KnowledgeBase
    kb = KnowledgeBase()
    return await kb.get_stats()


@router.get("/optimization/engines")
async def get_engine_effectiveness():
    """各搜索引擎效能统计"""
    from optimization.knowledge_base import KnowledgeBase
    kb = KnowledgeBase()
    data = await kb.get_engine_effectiveness()
    return {"engine_effectiveness": data}


@router.get("/optimization/strategy-types")
async def get_strategy_type_effectiveness():
    """各策略类型效能统计"""
    from optimization.knowledge_base import KnowledgeBase
    kb = KnowledgeBase()
    data = await kb.get_strategy_type_effectiveness()
    return {"strategy_type_effectiveness": data}


@router.get("/tasks/{task_id}/optimization")
async def get_task_optimization(task_id: int):
    """查看任务的优化记录"""
    task = await repo.get_task(task_id)
    if not task:
        raise HTTPException(404, "任务不存在")

    records = await repo.get_optimization_records(task_id)
    return {"task_id": task_id, "rounds": records}


@router.get("/optimization/bubble-breaker")
async def get_bubble_breaker_status():
    """信息茧房突破模块状态"""
    return {
        "enabled": settings.bubble_breaker_enabled,
        "min_source_diversity": settings.bubble_min_source_diversity,
        "cross_language": settings.bubble_cross_language,
    }


@router.get("/optimization/active")
async def get_active_optimizations():
    """查看当前正在运行的优化循环"""
    from standalone.task_executor import executor
    from standalone.scheduler import get_scheduler_status

    scheduler_info = get_scheduler_status()
    running_tasks = []
    for task_id, async_task in list(executor._running.items()):
        if not async_task.done():
            try:
                task = await repo.get_task(task_id)
                if task and task.get("status") in (1, 2):  # CRAWLING or PROCESSING
                    records = await repo.get_optimization_records(task_id)
                    latest_round = records[-1] if records else None
                    running_tasks.append({
                        "task_id": task_id,
                        "task_type": task.get("task_type"),
                        "status": task.get("status"),
                        "optimization_rounds": len(records),
                        "latest_score": latest_round.get("overall_score") if latest_round else None,
                        "latest_strategy": latest_round.get("strategy_type") if latest_round else None,
                    })
            except Exception:
                pass

    return {
        "scheduler": scheduler_info,
        "active_optimizations": running_tasks,
        "optimization_config": {
            "enabled": settings.optimization_enabled,
            "depth_target_score": settings.optimization_depth_target_score,
            "breadth_target_score": settings.optimization_breadth_target_score,
            "max_rounds": settings.optimization_max_rounds,
            "breadth_max_rounds": settings.breadth_max_rounds,
            "total_budget_seconds": settings.optimization_total_budget_seconds,
            "mode": settings.optimization_mode,
        },
    }


# ============== Digest API ==============

@router.get("/digests")
async def list_digests(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=50),
    include_all: bool = Query(False),
):
    """日报列表。

    默认仅返回有 AI 内容的记录；include_all=True 时返回生成中/失败记录，
    供管理端轮询使用。
    """
    records, total = await repo.list_digests_with_ai(
        page=page, size=size, include_all=include_all,
    )
    digests = []
    for r in records:
        r = _enrich_task(r)
        digests.append({
            "id": r["id"],
            "digest_date": r.get("digest_date"),
            "status": r["status"],
            "status_label": r["status_label"],
            "ai_title": r.get("ai_title"),
            "ai_summary": r.get("ai_summary"),
            "ai_tags": r.get("ai_tags"),
            "highlight": r.get("digest_highlight"),
            "error_message": r.get("error_message") or r.get("ai_error_message"),
            "created_at": r.get("created_at"),
        })
    return {"total": total, "page": page, "size": size, "records": digests}


@router.get("/digests/latest")
async def get_latest_digest():
    """最近一期日报"""
    task = await repo.get_latest_public_digest()
    if not task:
        raise HTTPException(404, "暂无日报")
    return await _build_digest_detail(task["id"])


@router.post("/config/refresh")
async def refresh_config():
    """刷新配置（从 Java 后端重新拉取）"""
    result = await backend_config.refresh()
    from standalone.task_executor import invalidate_digest_sections_cache
    invalidate_digest_sections_cache()
    try:
        from standalone.scheduler import refresh_source_schedules
        await refresh_source_schedules()
    except Exception as e:
        logger.warning("Source schedule refresh failed during config refresh: %s", e)
    return {
        "message": "配置已刷新",
        "keys": list(result.keys()) if result else [],
    }


@router.get("/digests/config/sections")
async def get_digest_sections_config(force_refresh: bool = Query(False)):
    """查看日报板块配置"""
    from standalone.task_executor import get_digest_sections
    sections = await get_digest_sections(force_refresh=force_refresh)
    return {"sections": sections}


@router.get("/digests/scheduler/status")
async def get_scheduler_status():
    """获取调度器状态"""
    from standalone.scheduler import get_scheduler_status
    status = get_scheduler_status()
    records, _ = await repo.list_digests_with_ai(page=1, size=1, include_all=True)
    if records:
        latest = _enrich_task(records[0])
        status["latest_digest"] = {
            "id": latest.get("id"),
            "digest_date": latest.get("digest_date"),
            "status": latest.get("status"),
            "status_label": latest.get("status_label"),
            "error_message": latest.get("error_message") or latest.get("ai_error_message"),
            "created_at": latest.get("created_at"),
            "diagnostics": latest.get("diagnostics"),
        }
    else:
        status["latest_digest"] = None
    status["diagnostics"] = _build_scheduler_diagnostics(status)
    return status


@router.get("/digests/runtime/health")
async def get_digest_runtime_health():
    """Aggregate digest launch-readiness signals for admin diagnostics."""
    checks: list[dict] = []
    recommendations: list[str] = []

    try:
        from standalone.scheduler import get_scheduler_status as _get_scheduler_status
        scheduler_status = _get_scheduler_status()
    except Exception as exc:
        scheduler_status = {}
        checks.append(_runtime_check(
            "scheduler", "Scheduler", "danger",
            f"Scheduler status unavailable: {exc}", blocking=True,
        ))

    if scheduler_status:
        enabled = bool(scheduler_status.get("enabled"))
        running = bool(scheduler_status.get("running"))
        digest_job_registered = bool(scheduler_status.get("digest_job_registered"))
        ai_enabled = bool(scheduler_status.get("ai_enabled"))
        ai_configured = bool(scheduler_status.get("ai_configured"))

        checks.append(_runtime_check(
            "scheduler", "Scheduler",
            "success" if running else ("warning" if not enabled else "danger"),
            "Scheduler is running" if running else "Scheduler is not running",
            blocking=enabled and not running,
        ))
        checks.append(_runtime_check(
            "digest_job", "Digest job",
            "success" if digest_job_registered else ("info" if not enabled else "danger"),
            "Digest job is registered" if digest_job_registered else "Digest job is not registered",
            blocking=enabled and not digest_job_registered,
        ))
        checks.append(_runtime_check(
            "ai", "AI",
            "success" if (not ai_enabled or ai_configured) else "danger",
            "AI is configured" if ai_configured else ("AI is disabled" if not ai_enabled else "AI is enabled but not configured"),
            blocking=ai_enabled and not ai_configured,
        ))
        if ai_enabled and not ai_configured:
            recommendations.append(
                "AI is enabled but missing usable configuration; set AI_API_KEY/base URL/model and refresh crawler config."
            )

    try:
        from standalone.task_executor import get_digest_sections
        sections = await get_digest_sections()
        config_summary = _summarize_runtime_sections(sections)
        checks.append(_runtime_check(
            "sections", "Digest sections",
            "success" if config_summary["core_coverage_ok"] else "danger",
            (
                f"{len(config_summary['configured_core_sections'])}/"
                f"{config_summary['min_core_sections']} required core sections configured"
            ),
            blocking=not config_summary["core_coverage_ok"],
        ))
        if not config_summary["core_coverage_ok"]:
            recommendations.append(
                "Digest core sections are insufficient; enable at least "
                f"{config_summary['min_core_sections']} core sections."
            )
    except Exception as exc:
        config_summary = {
            "sections_count": 0,
            "section_names": [],
            "core_sections": _configured_core_sections(),
            "configured_core_sections": [],
            "missing_core_sections": _configured_core_sections(),
            "min_core_sections": int(getattr(settings, "digest_publish_min_core_sections", 3) or 3),
            "core_coverage_ok": False,
        }
        checks.append(_runtime_check(
            "sections", "Digest sections", "danger",
            f"Digest section config unavailable: {exc}", blocking=True,
        ))

    try:
        from optimization.knowledge_base import KnowledgeBase
        kb = KnowledgeBase()
        quality_overview = await kb.get_digest_quality_overview(limit=10)
    except Exception as exc:
        quality_overview = {
            "summary": {"latest_score": None, "average_score": None, "status": "unknown"},
            "next_run_actions": None,
        }
        checks.append(_runtime_check(
            "quality", "Quality trend", "warning",
            f"Quality overview unavailable: {exc}",
        ))

    quality_summary = quality_overview.get("summary") or {}
    quality_status = quality_summary.get("status") or "unknown"
    if quality_status == "danger":
        checks.append(_runtime_check(
            "quality", "Quality trend", "warning",
            "Latest digest quality trend is below target",
        ))
        recommendations.append("Review latest quality weaknesses before relying on automatic optimization.")
    elif quality_summary.get("latest_score") is not None:
        checks.append(_runtime_check(
            "quality", "Quality trend",
            "success" if quality_status == "success" else "warning",
            f"Latest score: {quality_summary.get('latest_score')}",
        ))
    else:
        checks.append(_runtime_check(
            "quality", "Quality trend", "info",
            "No final digest quality evaluation yet",
        ))

    optimization_safety = _summarize_next_run_action_safety(
        quality_overview.get("next_run_actions")
    )
    checks.append(_runtime_check(
        "optimization_safety", "Optimization safety",
        optimization_safety["status"],
        (
            f"confidence={optimization_safety['confidence']}, "
            f"skip={optimization_safety['skip_count']}, "
            f"deprioritize={optimization_safety['deprioritize_count']}"
        ),
        blocking=optimization_safety["status"] == "danger",
    ))
    if optimization_safety["status"] != "success":
        recommendations.append(
            "Keep automatic optimization in conservative mode until source feedback confidence improves."
        )

    try:
        feedback_records = await repo.get_recent_digest_search_feedback(limit=1)
    except Exception as exc:
        feedback_records = []
        checks.append(_runtime_check(
            "search_feedback", "Search feedback", "warning",
            f"Search feedback unavailable: {exc}",
        ))
    search_feedback = _summarize_search_feedback(feedback_records)
    if feedback_records:
        keep_rate = search_feedback.get("latest_keep_rate")
        checks.append(_runtime_check(
            "search_feedback", "Search feedback",
            "success" if keep_rate is not None and keep_rate >= 0.25 else "warning",
            f"Latest keep rate: {keep_rate}",
        ))
    else:
        checks.append(_runtime_check(
            "search_feedback", "Search feedback", "info",
            "No search feedback snapshot yet",
        ))

    status = _runtime_status(checks)
    blocking = any(check.get("blocking") for check in checks)
    if blocking:
        status = "danger"

    return {
        "status": status,
        "summary": {
            "blocking": blocking,
            "message": "Digest runtime is ready" if status == "healthy" else "Digest runtime needs attention",
        },
        "checks": checks,
        "recommendations": recommendations[:8],
        "config": config_summary,
        "scheduler": scheduler_status,
        "quality": quality_overview,
        "optimization_safety": optimization_safety,
        "search_feedback": search_feedback,
    }


@router.post("/digests/trigger")
async def trigger_digest(force: bool = Query(False)):
    """手动触发日报生成（force=true 可强制重新生成当天日报）"""
    from standalone.scheduler import generate_scheduled_digest
    result = await generate_scheduled_digest(force=force)
    if result["status"] == "error":
        raise HTTPException(500, result["message"])
    return result


@router.get("/digests/task/{task_id}")
async def get_digest_by_task_id(task_id: int):
    """按任务 ID 查询日报详情"""
    task = await repo.get_task(task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    if task["task_type"] != "digest":
        raise HTTPException(400, "该任务不是日报类型")
    return await _build_digest_detail(task_id)


@router.get("/digests/{date}")
async def get_digest_by_date(date: str):
    """按日期查询日报详情"""
    task = await repo.get_public_digest_by_date(date)
    if not task:
        raise HTTPException(404, f"未找到 {date} 的日报")
    return await _build_digest_detail(task["id"])


async def _build_digest_detail(task_id: int) -> dict:
    """构建日报详情（含结构化 sections/items）"""
    task = await repo.get_task(task_id)
    if not task:
        raise HTTPException(404, "任务不存在")

    task = _enrich_task(task)
    sections = await repo.get_digest_sections(task_id)
    evaluation = await repo.get_latest_digest_evaluation(task_id)
    source_diagnostics = await repo.get_digest_source_diagnostics(task_id)
    next_run_actions = None
    if evaluation:
        try:
            from optimization.knowledge_base import KnowledgeBase
            next_run_actions = KnowledgeBase.derive_digest_source_actions(
                diagnostics=source_diagnostics,
                weaknesses=evaluation.get("weaknesses") or [],
                suggestions=evaluation.get("suggestions") or [],
                digest_date=task.get("digest_date"),
                created_at=evaluation.get("created_at"),
            )
        except Exception:
            next_run_actions = None

    # 清理内部 id（用副本避免修改原始数据）
    clean_sections = []
    for sec in sections:
        clean_sec = {k: v for k, v in sec.items() if k not in ("id", "task_id", "created_at")}
        clean_sec["items"] = [
            {k: v for k, v in item.items() if k not in ("id", "section_id", "created_at")}
            for item in sec.get("items", [])
        ]
        clean_sections.append(clean_sec)

    # 提取 orchestrator 规划日志（从 ai_search_metadata JSON 中）
    orchestrator_plan = None
    metadata = None
    raw_meta = task.get("ai_search_metadata")
    if raw_meta:
        try:
            import json as _json
            metadata = _json.loads(raw_meta) if isinstance(raw_meta, str) else raw_meta
            orchestrator_plan = metadata.get("orchestrator_plan")
        except Exception:
            pass

    quality_evaluation = None
    if evaluation:
        quality_evaluation = {
            "overall_score": evaluation.get("overall_score"),
            "dimensions": {
                "angle": evaluation.get("angle_coverage"),
                "source_diversity": evaluation.get("source_diversity"),
                "depth": evaluation.get("depth_coverage"),
                "temporal": evaluation.get("temporal_coverage"),
                "perspective": evaluation.get("perspective_balance"),
                "language": evaluation.get("language_coverage"),
            },
            "section_scores": evaluation.get("strategy_detail") or [],
            "source_diagnostics": source_diagnostics,
            "next_run_actions": next_run_actions,
            "weaknesses": evaluation.get("weaknesses") or [],
            "suggestions": evaluation.get("suggestions") or [],
            "created_at": evaluation.get("created_at"),
        }
    elif isinstance(metadata, dict) and metadata.get("digest_publish_quality"):
        publish_quality = metadata.get("digest_publish_quality") or {}
        quality_evaluation = {
            "overall_score": publish_quality.get("score"),
            "dimensions": {},
            "section_scores": [publish_quality],
            "source_diagnostics": source_diagnostics,
            "next_run_actions": None,
            "weaknesses": [],
            "suggestions": publish_quality.get("suggestions") or [],
            "publishable": metadata.get("digest_publishable"),
            "stage": metadata.get("digest_publish_stage"),
            "created_at": None,
        }

    return {
        "id": task["id"],
        "digest_date": task.get("digest_date"),
        "status": task["status"],
        "status_label": task["status_label"],
        "ai_title": task.get("ai_title"),
        "ai_summary": task.get("ai_summary"),
        "ai_tags": task.get("ai_tags"),
        "highlight": task.get("digest_highlight"),
        "ai_full_content": task.get("ai_full_content"),
        "ai_duration": task.get("ai_duration"),
        "ai_tokens_used": task.get("ai_tokens_used"),
        "error_message": task.get("error_message") or task.get("ai_error_message"),
        "sections": clean_sections,
        "orchestrator_plan": orchestrator_plan,
        "diagnostics": task.get("diagnostics"),
        "quality_evaluation": quality_evaluation,
        "created_at": task.get("created_at"),
    }


# ============== 就绪检查 ==============

@router.get("/ready")
async def readiness_check():
    """就绪检查：DB 连接 + 调度器状态 + 配置完整性"""
    checks = {}

    # DB 连接
    try:
        from standalone.db import get_db
        async with get_db() as db:
            await db.execute("SELECT 1")
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}"

    # 调度器
    try:
        from standalone.scheduler import get_scheduler_status
        status = get_scheduler_status()
        checks["scheduler"] = "ok" if status.get("running") else "stopped"
    except Exception:
        checks["scheduler"] = "not_available"

    # AI 配置
    try:
        from ai.config import ai_settings
        checks["ai"] = "configured" if ai_settings.ai_api_key else "not_configured"
    except Exception:
        checks["ai"] = "not_available"

    all_ok = all(v in ("ok", "configured") for v in checks.values())
    return {
        "ready": all_ok,
        "checks": checks,
    }


# ============== 日报质量趋势 ==============

@router.get("/optimization/digest-trend")
async def get_digest_quality_trend(limit: int = Query(default=10, ge=1, le=50)):
    """最近 N 次日报的质量评估趋势"""
    try:
        from optimization.knowledge_base import KnowledgeBase
        kb = KnowledgeBase()
        return await kb.get_digest_quality_overview(limit=limit)
    except Exception as e:
        raise HTTPException(500, f"Failed to get digest quality trend: {e}")
