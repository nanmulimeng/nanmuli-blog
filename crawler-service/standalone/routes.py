"""独立模式管理 API 路由"""

import json
import logging

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, HttpUrl
from typing import Optional as Opt

from standalone.models import TaskStatus, TASK_TYPE_LABELS, AI_TEMPLATE_LABELS
from standalone import repository as repo
from standalone.task_executor import executor
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


# ============== Helpers ==============

def _enrich_task(task: dict) -> dict:
    """为任务响应添加标签和进度（不修改原始 dict）"""
    task = dict(task)
    task["task_type_label"] = TASK_TYPE_LABELS.get(task["task_type"], task["task_type"])
    task["status_label"] = TaskStatus.label(task["status"])

    tp = task.get("total_pages", 0) or 0
    cp = task.get("completed_pages", 0) or 0
    task["progress_percent"] = int(cp * 100 / tp) if tp > 0 else 0

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

    task["ai_template_label"] = AI_TEMPLATE_LABELS.get(
        task.get("ai_template", "tech_summary"), "技术摘要"
    )

    return task


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

    source_url = str(request.url) if request.url else None
    config_json = request.config.model_dump_json() if request.config else None

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
    return await repo.get_stats()


# ============== Optimization API ==============

@router.get("/optimization/config")
async def get_optimization_config():
    """查看优化引擎配置"""
    from config import settings as s
    return {
        "enabled": s.optimization_enabled,
        "target_score": s.optimization_target_score,
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


# ============== Digest API ==============

@router.get("/digests")
async def list_digests(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=50),
):
    """日报列表（按日期倒序）"""
    records, total = await repo.list_tasks(
        task_type="digest", page=page, size=size
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
    task = await repo.get_latest_completed_digest()
    if not task:
        raise HTTPException(404, "暂无日报")
    return await _build_digest_detail(task["id"])


@router.post("/config/refresh")
async def refresh_config():
    """刷新配置（从 Java 后端重新拉取）"""
    result = await backend_config.refresh()
    return {
        "message": "配置已刷新",
        "keys": list(result.keys()) if result else [],
    }


@router.get("/digests/config/sections")
async def get_digest_sections_config():
    """查看日报板块配置"""
    from standalone.task_executor import get_digest_sections
    sections = await get_digest_sections()
    return {"sections": sections}


@router.get("/digests/scheduler/status")
async def get_scheduler_status():
    """获取调度器状态"""
    from standalone.scheduler import get_scheduler_status
    return get_scheduler_status()


@router.post("/digests/trigger")
async def trigger_digest(force: bool = Query(False)):
    """手动触发日报生成（force=true 可强制重新生成当天日报）"""
    from standalone.scheduler import generate_scheduled_digest
    await generate_scheduled_digest(force=force)
    return {"message": "日报生成已触发"}


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
    task = await repo.get_digest_by_date(date)
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

    # 清理内部 id（用副本避免修改原始数据）
    clean_sections = []
    for sec in sections:
        clean_sec = {k: v for k, v in sec.items() if k not in ("id", "task_id", "created_at")}
        clean_sec["items"] = [
            {k: v for k, v in item.items() if k not in ("id", "section_id", "created_at")}
            for item in sec.get("items", [])
        ]
        clean_sections.append(clean_sec)

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
        "created_at": task.get("created_at"),
    }
