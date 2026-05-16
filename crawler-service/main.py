"""
Web Collector - Python Crawler Service
基于 Crawl4AI 的网页内容采集服务

双模式部署:
  - 纯 API 模式（默认）: 作为博客微服务，仅提供 /crawl/* 和 /health 端点
  - 独立模式（STANDALONE=true）: 额外提供任务管理 /api/v1/* 端点

端点:
- POST /crawl/single    - 单页爬取
- POST /crawl/deep      - BFS 深度爬取
- POST /crawl/search    - 关键词搜索爬取
- GET  /health          - 健康检查
- 独立模式额外端点见 standalone/routes.py
"""

from __future__ import annotations

import os
import sys
import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

# Windows UTF-8 全局保护：Crawl4AI/Playwright 输出包含 Unicode 字符，
# Windows 默认 GBK 编码会崩溃，必须在任何 IO 操作前强制 UTF-8
os.environ.setdefault("PYTHONUTF8", "1")
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    # 强制 Rich 使用 UTF-8 模式，避免 legacy Windows GBK 编码崩溃
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.environ.setdefault("TERM", "xterm-256color")

# 防止系统 HTTP_PROXY 代理劫持 localhost 连接
# httpx/Crawl4AI 会读取 *_PROXY 环境变量，导致 127.0.0.1 请求走代理超时
if not os.environ.get("NO_PROXY") and not os.environ.get("no_proxy"):
    os.environ.setdefault("NO_PROXY", "localhost,127.0.0.1,.local")

from config import settings

if TYPE_CHECKING:
    from fastapi import FastAPI

from logging_config import setup_logging

setup_logging(log_level=settings.log_level, standalone=settings.standalone)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Web Collector Crawler Service starting...")

    try:
        from crawl4ai import AsyncWebCrawler
        logger.info("Crawl4AI imported successfully")
    except ImportError as e:
        logger.error(f"Failed to import Crawl4AI: {e}")
        raise

    logger.info(f"Mode: {'standalone' if settings.standalone else 'api-only'}")

    if settings.standalone:
        from standalone.db import init_db
        await init_db()
        logger.info(f"SQLite database initialized: {settings.db_path}")

        # 从 Java 后端拉取爬虫配置（AI key、日报开关等）
        try:
            from standalone import backend_config
            await backend_config.fetch_from_backend()
        except Exception as e:
            logger.warning("Failed to fetch config from backend on startup: %s", e)

        from standalone.scheduler import start_scheduler, stop_scheduler
        start_scheduler()

    yield

    # Shutdown: close shared resources
    if settings.standalone:
        from standalone.scheduler import stop_scheduler
        stop_scheduler()

    # 关闭 AI httpx 连接池
    try:
        from ai import content_organizer as organizer
        await organizer.close()
    except (ImportError, RuntimeError, AttributeError) as e:
        logger.warning("Failed to close AI organizer during shutdown: %s", e)
    except Exception as e:
        logger.error("Unexpected error closing AI organizer: %s", e)

    # 取消运行中的任务
    try:
        from standalone.task_executor import executor
        await executor.shutdown()
    except (ImportError, RuntimeError) as e:
        logger.warning("Failed to shutdown task executor: %s", e)
    except Exception as e:
        logger.error("Unexpected error shutting down task executor: %s", e)

    logger.info("Web Collector Crawler Service shutting down...")


def create_app() -> "FastAPI":
    from fastapi import FastAPI
    from api.crawl import router as crawl_router
    from api.health import router as health_router
    from api.errors import register_error_handlers, register_middlewares

    app = FastAPI(
        title="Web Collector Crawler Service",
        description="基于 Crawl4AI 的网页内容采集服务（支持双模式部署）",
        version="2.0.0",
        lifespan=lifespan,
    )

    # 始终注册：RequestID + AccessLog + 爬取 API + 健康检查 + 错误处理
    register_middlewares(app)
    app.include_router(crawl_router)
    app.include_router(health_router)
    register_error_handlers(app)

    # 独立模式：管理 API + 认证（覆盖 /api/v1/*, /crawl/*, /organize, /keyword）
    if settings.standalone:
        from standalone.auth import ApiKeyMiddleware
        from standalone.routes import router as standalone_router

        if settings.auth_enabled and settings.api_keys:
            app.add_middleware(ApiKeyMiddleware)

        app.include_router(standalone_router, prefix="/api/v1")
        logger.info("Standalone mode enabled: /api/v1/* endpoints registered")

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting server on {settings.host}:{settings.port}")
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        workers=1
    )
