"""独立模式管理 API 路由"""

import json
import logging

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, HttpUrl
from typing import Optional as Opt

from standalone.models import TaskStatus, TASK_TYPE_LABELS
from standalone import repository as repo
from standalone.task_executor import executor
from standalone.export import export_task_as_markdown
from api.crawl import CrawlConfig

logger = logging.getLogger(__name__)
router = APIRouter(tags=["standalone"])


# ============== Request Models ==============

class CreateTaskRequest(BaseModel):
    task_type: str = Field(..., pattern="^(single|deep|keyword)$")
    url: Opt[HttpUrl] = None
    keyword: Opt[str] = None
    search_engine: str = Field(default="sogou", pattern="^(sogou|bing|duckduckgo|google)$")
    max_depth: int = Field(default=1, ge=1, le=5)
    max_pages: int = Field(default=10, ge=1, le=20)
    config: Opt[CrawlConfig] = None


# ============== Endpoints ==============

@router.post("/tasks", status_code=201)
async def create_task(request: CreateTaskRequest):
    """创建爬取任务（异步执行）"""
    # 校验必填参数
    if request.task_type in ("single", "deep") and not request.url:
        raise HTTPException(400, "url is required for single/deep task type")
    if request.task_type == "keyword" and not request.keyword:
        raise HTTPException(400, "keyword is required for keyword task type")

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
    )

    # 提交异步执行
    await executor.submit(task_id)

    return {
        "id": task_id,
        "task_type": request.task_type,
        "task_type_label": TASK_TYPE_LABELS.get(request.task_type, request.task_type),
        "status": TaskStatus.PENDING,
        "status_label": TaskStatus.label(TaskStatus.PENDING),
        "message": "任务已创建，正在后台执行",
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

    for r in records:
        r["task_type_label"] = TASK_TYPE_LABELS.get(r["task_type"], r["task_type"])
        r["status_label"] = TaskStatus.label(r["status"])
        tp = r.get("total_pages", 0) or 0
        cp = r.get("completed_pages", 0) or 0
        r["progress_percent"] = int(cp * 100 / tp) if tp > 0 else 0

    return {"total": total, "page": page, "size": size, "records": records}


@router.get("/tasks/{task_id}")
async def get_task(task_id: int):
    """查询任务详情"""
    task = await repo.get_task(task_id)
    if not task:
        raise HTTPException(404, "任务不存在")

    task["task_type_label"] = TASK_TYPE_LABELS.get(task["task_type"], task["task_type"])
    task["status_label"] = TaskStatus.label(task["status"])
    tp = task.get("total_pages", 0) or 0
    cp = task.get("completed_pages", 0) or 0
    task["progress_percent"] = int(cp * 100 / tp) if tp > 0 else 0

    return task


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


@router.get("/tasks/{task_id}/export")
async def export_task(task_id: int):
    """导出任务结果为 Markdown 文件"""
    task = await repo.get_task(task_id)
    if not task:
        raise HTTPException(404, "任务不存在")

    if task["status"] != TaskStatus.COMPLETED:
        raise HTTPException(400, "只有已完成的任务才能导出")

    return await export_task_as_markdown(task_id)


@router.get("/stats")
async def get_stats():
    """获取统计信息"""
    return await repo.get_stats()
