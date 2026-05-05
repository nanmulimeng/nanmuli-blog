"""爬取 API 路由（/crawl/single, /crawl/deep, /crawl/search）"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, HttpUrl

from crawler.single import crawl_single_page
from crawler.deep import crawl_deep_pages
from crawler.search import crawl_by_keyword
from config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


# ============== Pydantic Models ==============

class CrawlConfig(BaseModel):
    word_count_threshold: int = Field(default=15, ge=0)
    excluded_tags: list[str] = Field(default=["nav", "footer", "aside", "script", "style", "noscript", "iframe"])
    remove_overlay_elements: bool = Field(default=True)
    wait_until: str = Field(default="networkidle")
    page_timeout: int = Field(default=60000, ge=5000, le=120000)
    text_mode: bool = Field(default=True)
    light_mode: bool = Field(default=False)

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
    url: HttpUrl
    config: Optional[CrawlConfig] = Field(default_factory=CrawlConfig)


class DeepCrawlRequest(BaseModel):
    url: HttpUrl
    max_depth: int = Field(default=1, ge=1, le=3)
    max_pages: int = Field(default=10, ge=1, le=20)
    config: Optional[CrawlConfig] = Field(default_factory=CrawlConfig)


class SearchCrawlRequest(BaseModel):
    keyword: str = Field(..., min_length=1, max_length=500)
    engine: str = Field(default="sogou", pattern="^(sogou|bing|duckduckgo|google)$")
    max_results: int = Field(default=10, ge=1, le=20)
    config: Optional[CrawlConfig] = Field(default_factory=CrawlConfig)


class CrawlResultResponse(BaseModel):
    success: bool
    url: str
    title: Optional[str] = None
    markdown: Optional[str] = None
    metadata: dict = Field(default_factory=dict)
    word_count: int = 0
    crawl_time_ms: int = 0
    error_message: Optional[str] = None
    depth: int = 0
    search_rank: int = 0


class MultiPageResult(BaseModel):
    success: bool
    pages: list[CrawlResultResponse]
    total_pages: int
    total_crawl_time_ms: int
    keyword: Optional[str] = None


# ============== Endpoints ==============

@router.post("/crawl/single", response_model=CrawlResultResponse)
async def crawl_single(request: SingleCrawlRequest):
    """单页爬取"""
    logger.info(f"[Single Crawl] URL: {request.url}")

    try:
        result = await crawl_single_page(url=str(request.url), config=request.config)
        logger.info(f"[Single Crawl] Success: {result.url}, words: {result.word_count}")
        return result.to_dict()

    except Exception as e:
        logger.error(f"[Single Crawl] Failed: {request.url}, error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Crawl failed: {str(e)}")


@router.post("/crawl/deep", response_model=MultiPageResult)
async def crawl_deep(request: DeepCrawlRequest):
    """BFS 深度爬取"""
    logger.info(f"[Deep Crawl] URL: {request.url}, depth: {request.max_depth}, max_pages: {request.max_pages}")

    # 运行时校验限制值
    if request.max_depth > settings.max_depth_limit:
        raise HTTPException(status_code=422, detail=f"max_depth exceeds limit ({settings.max_depth_limit})")
    if request.max_pages > settings.max_pages_limit:
        raise HTTPException(status_code=422, detail=f"max_pages exceeds limit ({settings.max_pages_limit})")

    try:
        pages = await crawl_deep_pages(
            url=str(request.url), max_depth=request.max_depth,
            max_pages=request.max_pages, config=request.config
        )

        total_time = sum(p.crawl_time_ms for p in pages)
        success_count = sum(1 for p in pages if p.success)

        logger.info(f"[Deep Crawl] Completed: {success_count}/{len(pages)} pages, total_time: {total_time}ms")

        return MultiPageResult(
            success=success_count > 0,
            pages=[p.to_dict() for p in pages],
            total_pages=len(pages),
            total_crawl_time_ms=total_time
        )

    except Exception as e:
        logger.error(f"[Deep Crawl] Failed: {request.url}, error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Deep crawl failed: {str(e)}")


@router.post("/crawl/search", response_model=MultiPageResult)
async def crawl_search(request: SearchCrawlRequest):
    """关键词搜索爬取"""
    logger.info(f"[Search Crawl] Keyword: '{request.keyword}', engine: {request.engine}")

    if request.max_results > settings.max_pages_limit:
        raise HTTPException(status_code=422, detail=f"max_results exceeds limit ({settings.max_pages_limit})")

    try:
        pages = await crawl_by_keyword(
            keyword=request.keyword, engine=request.engine,
            max_results=request.max_results, config=request.config
        )

        total_time = sum(p.crawl_time_ms for p in pages)
        success_count = sum(1 for p in pages if p.success)

        logger.info(f"[Search Crawl] Completed: {success_count}/{len(pages)} pages for '{request.keyword}'")

        return MultiPageResult(
            success=success_count > 0,
            pages=[p.to_dict() for p in pages],
            total_pages=len(pages),
            total_crawl_time_ms=total_time,
            keyword=request.keyword
        )

    except Exception as e:
        logger.error(f"[Search Crawl] Failed: '{request.keyword}', error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Search crawl failed: {str(e)}")
