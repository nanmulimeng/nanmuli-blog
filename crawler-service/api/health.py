"""健康检查路由（含组件状态）"""

import os

from fastapi import APIRouter
from config import settings

router = APIRouter()

VERSION = "2.0.0"


@router.get("/health")
async def health_check():
    components = {}

    # Crawl4AI
    try:
        from crawler.dependencies import crawl4ai_status
        status = crawl4ai_status()
        components["crawler"] = {
            "available": status.available,
            "engine": f"Crawl4AI {status.version}" if status.available else None,
            "mode": status.mode,
            "error": status.error,
        }
    except Exception as exc:
        components["crawler"] = {
            "available": False,
            "mode": settings.crawler_dependency_mode,
            "error": str(exc),
        }

    # AI
    try:
        from ai import content_organizer as organizer
        from ai.config import ai_settings
        components["ai"] = {
            "available": organizer.is_available,
            "model": ai_settings.ai_model if organizer.is_available else None,
        }
    except Exception:
        components["ai"] = {"available": False}

    # 调度器
    try:
        from standalone.scheduler import get_scheduler_status
        components["scheduler"] = get_scheduler_status()
    except Exception:
        components["scheduler"] = {"running": False}

    # 数据库
    db_path = settings.db_path
    db_size_mb = 0.0
    if os.path.exists(db_path):
        db_size_mb = round(os.path.getsize(db_path) / 1024 / 1024, 1)
    components["database"] = {"path": db_path, "size_mb": db_size_mb}

    # 运行中的任务数
    active_tasks = 0
    try:
        from standalone.task_executor import executor
        active_tasks = executor.running_count
    except Exception:
        pass

    return {
        "status": "healthy",
        "version": VERSION,
        "components": components,
        "active_tasks": active_tasks,
    }
