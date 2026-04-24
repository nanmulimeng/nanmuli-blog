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
import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

# Windows UTF-8 模式：确保 sqlite3 和 IO 操作使用 UTF-8 而非系统编码（GBK）
os.environ.setdefault("PYTHONUTF8", "1")

from dotenv import load_dotenv
from config import settings

if TYPE_CHECKING:
    from fastapi import FastAPI

load_dotenv()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
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

    yield

    logger.info("Web Collector Crawler Service shutting down...")


def create_app() -> "FastAPI":
    from fastapi import FastAPI
    from api.crawl import router as crawl_router
    from api.health import router as health_router
    from api.errors import register_error_handlers

    app = FastAPI(
        title="Web Collector Crawler Service",
        description="基于 Crawl4AI 的网页内容采集服务（支持双模式部署）",
        version="2.0.0",
        lifespan=lifespan,
    )

    # 始终注册：爬取 API + 健康检查 + 错误处理
    app.include_router(crawl_router)
    app.include_router(health_router)
    register_error_handlers(app)

    # 独立模式：管理 API + 认证
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
