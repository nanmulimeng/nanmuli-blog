"""
Web Collector - Python Crawler Service
基于 Crawl4AI 的网页内容采集服务

端点:
- POST /crawl/single    - 单页爬取
- POST /crawl/deep      - BFS 深度爬取
- POST /crawl/search    - 关键词搜索爬取
- GET  /health          - 健康检查
"""

import os
import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, HttpUrl
from dotenv import load_dotenv

from crawler.single import crawl_single_page
from crawler.deep import crawl_deep_pages
from crawler.search import crawl_by_keyword

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 全局配置
MAX_PAGES_DEFAULT = int(os.getenv('MAX_PAGES_DEFAULT', '10'))
MAX_PAGES_LIMIT = int(os.getenv('MAX_PAGES_LIMIT', '20'))
MAX_DEPTH_LIMIT = int(os.getenv('MAX_DEPTH_LIMIT', '3'))
REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', '60'))


# ============== Pydantic Models ==============

class CrawlConfig(BaseModel):
    """爬取配置"""
    word_count_threshold: int = Field(default=10, ge=0)
    excluded_tags: list[str] = Field(default=["nav", "footer", "aside", "header", "script", "style"])
    remove_overlay_elements: bool = Field(default=True)
    wait_until: str = Field(default="networkidle")
    page_timeout: int = Field(default=30000, ge=5000, le=120000)
    text_mode: bool = Field(default=True)
    light_mode: bool = Field(default=True)

    class Config:
        json_schema_extra = {
            "example": {
                "word_count_threshold": 10,
                "excluded_tags": ["nav", "footer", "aside"],
                "text_mode": True,
                "light_mode": True
            }
        }


class SingleCrawlRequest(BaseModel):
    """单页爬取请求"""
    url: HttpUrl
    config: Optional[CrawlConfig] = Field(default_factory=CrawlConfig)


class DeepCrawlRequest(BaseModel):
    """深度爬取请求"""
    url: HttpUrl
    max_depth: int = Field(default=1, ge=1, le=MAX_DEPTH_LIMIT)
    max_pages: int = Field(default=10, ge=1, le=MAX_PAGES_LIMIT)
    config: Optional[CrawlConfig] = Field(default_factory=CrawlConfig)


class SearchCrawlRequest(BaseModel):
    """关键词搜索爬取请求"""
    keyword: str = Field(..., min_length=1, max_length=500)
    engine: str = Field(default="bing", pattern="^(bing|duckduckgo)$")
    max_results: int = Field(default=10, ge=1, le=MAX_PAGES_LIMIT)
    config: Optional[CrawlConfig] = Field(default_factory=CrawlConfig)


class CrawlResult(BaseModel):
    """爬取结果"""
    success: bool
    url: str
    title: Optional[str] = None
    markdown: Optional[str] = None
    metadata: dict = Field(default_factory=dict)
    word_count: int = 0
    crawl_time_ms: int = 0
    error_message: Optional[str] = None


class MultiPageResult(BaseModel):
    """多页爬取结果"""
    success: bool
    pages: list[CrawlResult]
    total_pages: int
    total_crawl_time_ms: int
    keyword: Optional[str] = None


# ============== FastAPI App ==============

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("🚀 Web Collector Crawler Service starting...")
    # 启动时检查 Crawl4AI 环境
    try:
        from crawl4ai import AsyncWebCrawler
        logger.info("✅ Crawl4AI imported successfully")
    except ImportException as e:
        logger.error(f"❌ Failed to import Crawl4AI: {e}")
        raise

    yield

    logger.info("🛑 Web Collector Crawler Service shutting down...")


app = FastAPI(
    title="Web Collector Crawler Service",
    description="基于 Crawl4AI 的网页内容采集服务",
    version="1.0.0",
    lifespan=lifespan
)


# ============== API Endpoints ==============

@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "service": "web-collector-crawler",
        "version": "1.0.0"
    }


@app.post("/crawl/single", response_model=CrawlResult)
async def crawl_single(request: SingleCrawlRequest):
    """
    单页爬取

    爬取单个 URL 的内容，返回 Markdown 格式文本
    """
    logger.info(f"[Single Crawl] URL: {request.url}")

    try:
        result = await crawl_single_page(
            url=str(request.url),
            config=request.config
        )
        logger.info(f"[Single Crawl] Success: {result.url}, words: {result.word_count}")
        return result

    except Exception as e:
        logger.error(f"[Single Crawl] Failed: {request.url}, error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Crawl failed: {str(e)}"
        )


@app.post("/crawl/deep", response_model=MultiPageResult)
async def crawl_deep(request: DeepCrawlRequest):
    """
    BFS 深度爬取

    从起始 URL 开始，BFS 遍历同域名下的页面
    """
    logger.info(f"[Deep Crawl] URL: {request.url}, depth: {request.max_depth}, max_pages: {request.max_pages}")

    try:
        pages = await crawl_deep_pages(
            url=str(request.url),
            max_depth=request.max_depth,
            max_pages=request.max_pages,
            config=request.config
        )

        total_time = sum(p.crawl_time_ms for p in pages)
        success_count = sum(1 for p in pages if p.success)

        logger.info(f"[Deep Crawl] Completed: {success_count}/{len(pages)} pages, total_time: {total_time}ms")

        return MultiPageResult(
            success=success_count > 0,
            pages=pages,
            total_pages=len(pages),
            total_crawl_time_ms=total_time
        )

    except Exception as e:
        logger.error(f"[Deep Crawl] Failed: {request.url}, error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Deep crawl failed: {str(e)}"
        )


@app.post("/crawl/search", response_model=MultiPageResult)
async def crawl_search(request: SearchCrawlRequest):
    """
    关键词搜索爬取

    使用搜索引擎查找关键词相关页面，并爬取前 N 个结果
    """
    logger.info(f"[Search Crawl] Keyword: '{request.keyword}', engine: {request.engine}, max_results: {request.max_results}")

    try:
        pages = await crawl_by_keyword(
            keyword=request.keyword,
            engine=request.engine,
            max_results=request.max_results,
            config=request.config
        )

        total_time = sum(p.crawl_time_ms for p in pages)
        success_count = sum(1 for p in pages if p.success)

        logger.info(f"[Search Crawl] Completed: {success_count}/{len(pages)} pages for '{request.keyword}'")

        return MultiPageResult(
            success=success_count > 0,
            pages=pages,
            total_pages=len(pages),
            total_crawl_time_ms=total_time,
            keyword=request.keyword
        )

    except Exception as e:
        logger.error(f"[Search Crawl] Failed: '{request.keyword}', error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Search crawl failed: {str(e)}"
        )


# ============== Error Handlers ==============

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """全局异常处理"""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error",
            "detail": str(exc) if os.getenv('DEBUG') else None
        }
    )


# ============== Main ==============

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv('PORT', '8500'))
    host = os.getenv('HOST', '0.0.0.0')

    logger.info(f"Starting server on {host}:{port}")
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=os.getenv('DEBUG', 'false').lower() == 'true',
        workers=1  # 单进程模式，避免 Playwright 浏览器实例冲突
    )
