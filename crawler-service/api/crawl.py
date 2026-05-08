"""爬取 API 路由（/crawl/single, /crawl/deep, /crawl/search）"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from crawler.single import crawl_single_page
from crawler.deep import crawl_deep_pages
from crawler.search import crawl_by_keyword
from config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


# ============== Pydantic Models ==============

class CrawlConfig(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "word_count_threshold": 10,
            "excluded_tags": ["nav", "footer", "aside"],
            "text_mode": True,
            "light_mode": True
        }
    })

    word_count_threshold: int = Field(default=15, ge=0)
    excluded_tags: list[str] = Field(default=["nav", "footer", "aside", "script", "style", "noscript", "iframe"])
    remove_overlay_elements: bool = Field(default=True)
    wait_until: str = Field(default="networkidle")
    page_timeout: int = Field(default=60000, ge=5000, le=120000)
    text_mode: bool = Field(default=True)
    light_mode: bool = Field(default=False)


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
    engine: str = Field(default="sogou", pattern="^(sogou|bing|baidu|google)$")
    max_results: int = Field(default=10, ge=1, le=20)
    time_range: str = Field(default="week", pattern="^(day|week|month|year|all)$")
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
            max_results=request.max_results, time_range=request.time_range,
            config=request.config
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


# ============== AI Organization Endpoint ==============

class AiOrganizeRequest(BaseModel):
    """AI 整理请求（单页或多页）"""
    pages: list[dict] = Field(..., description="页面列表，每个包含 url/title/markdown/word_count")
    template: str = Field(default="tech_summary", pattern="^(tech_summary|tutorial|comparison|knowledge_report|daily_digest)$")
    keyword_context: str | None = Field(default=None, description="搜索关键词上下文")


class AiOrganizeResponse(BaseModel):
    success: bool
    title: str = ""
    summary: str = ""
    key_points: list[str] = []
    tags: list[str] = []
    category: str = ""
    full_content: str = ""
    duration_ms: int = 0
    tokens_used: int = 0
    error_message: str | None = None


@router.post("/organize", response_model=AiOrganizeResponse)
async def organize_content(request: AiOrganizeRequest):
    """AI 内容整理（供外部系统调用，如 Java 后端）"""
    import asyncio
    from ai import content_organizer as organizer
    from ai.organizer import PageContent, RateLimitError, OrganizerError

    if not organizer.is_available:
        raise HTTPException(status_code=503, detail="AI service not configured")

    try:
        pages = [
            PageContent(
                url=p.get("url", ""),
                title=p.get("title", ""),
                markdown=p.get("markdown", ""),
                word_count=p.get("word_count", 0),
            )
            for p in request.pages if p.get("markdown")
        ]

        if not pages:
            raise HTTPException(status_code=400, detail="No valid pages to organize")

        max_retries = 2
        result = None

        for attempt in range(max_retries + 1):
            try:
                if len(pages) == 1:
                    result = await organizer.organize(
                        pages[0].markdown, request.template, request.keyword_context
                    )
                else:
                    result = await organizer.organize_multiple(
                        pages, request.template, request.keyword_context
                    )
                break
            except RateLimitError:
                if attempt < max_retries:
                    logger.warning("[AiOrganize] Rate limited, retry %d/%d", attempt + 1, max_retries)
                    await asyncio.sleep(10.0)
                else:
                    raise
            except OrganizerError:
                raise

        return AiOrganizeResponse(
            success=True,
            title=result.title,
            summary=result.summary,
            key_points=result.key_points,
            tags=result.tags,
            category=result.category,
            full_content=result.full_content,
            duration_ms=result.duration_ms,
            tokens_used=result.tokens_used,
        )

    except Exception as e:
        logger.error("[AiOrganize] Failed: %s", e, exc_info=True)
        return AiOrganizeResponse(success=False, error_message=str(e))


class AiKeywordRequest(BaseModel):
    keyword: str
    action: str = Field(default="optimize", pattern="^(optimize|expand)$")


@router.post("/keyword")
async def process_keyword(request: AiKeywordRequest):
    """AI 关键词优化或扩展（供外部系统调用）"""
    from ai import content_organizer as organizer

    if not organizer.is_available:
        raise HTTPException(status_code=503, detail="AI service not configured")

    try:
        if request.action == "optimize":
            result = await organizer.optimize_keyword(request.keyword)
            return {"success": True, "original": request.keyword, "optimized": result}
        else:
            result = await organizer.expand_keywords(request.keyword)
            return {"success": True, "original": request.keyword, "variants": result}
    except Exception as e:
        return {"success": False, "original": request.keyword, "error": str(e)}
