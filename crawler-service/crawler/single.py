"""
单页爬取模块

爬取单个 URL 的内容，返回 Markdown 格式文本
"""

import time
import logging
from typing import Optional

from crawl4ai import AsyncWebCrawler

from .config import get_browser_config, get_crawler_run_config, RunParams, extract_markdown
from .metadata import extract_metadata

logger = logging.getLogger(__name__)


class CrawlResult:
    """爬取结果数据类"""
    def __init__(
        self,
        success: bool,
        url: str,
        title: Optional[str] = None,
        markdown: Optional[str] = None,
        metadata: Optional[dict] = None,
        word_count: int = 0,
        crawl_time_ms: int = 0,
        error_message: Optional[str] = None,
        depth: int = 0,
        search_rank: int = 0
    ):
        self.success = success
        self.url = url
        self.title = title
        self.markdown = markdown
        self.metadata = metadata or {}
        self.word_count = word_count
        self.crawl_time_ms = crawl_time_ms
        self.error_message = error_message
        self.depth = depth
        self.search_rank = search_rank

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "url": self.url,
            "title": self.title,
            "markdown": self.markdown,
            "metadata": self.metadata,
            "word_count": self.word_count,
            "crawl_time_ms": self.crawl_time_ms,
            "error_message": self.error_message,
            "depth": self.depth,
            "search_rank": self.search_rank
        }


async def crawl_single_page(
    url: str,
    config: Optional[object] = None,
    crawler: Optional[AsyncWebCrawler] = None
) -> CrawlResult:
    """
    爬取单个页面

    Args:
        url: 目标 URL
        config: 爬取配置（Pydantic 模型或 dict）
        crawler: 外部传入的浏览器实例（复用时不启停浏览器）

    Returns:
        CrawlResult 对象
    """
    start_time = time.time()
    own_crawler = crawler is None

    try:
        params = RunParams(config)

        logger.info(f"[Single] Crawling: {url}")

        browser_config = get_browser_config(text_mode=params.text_mode, light_mode=params.light_mode)
        run_config = get_crawler_run_config(
            word_count_threshold=params.word_count_threshold,
            excluded_tags=params.excluded_tags,
            wait_until=params.wait_until,
            page_timeout=params.page_timeout
        )

        if own_crawler:
            crawler = AsyncWebCrawler(config=browser_config)
            await crawler.__aenter__()

        try:
            result = await crawler.arun(url=url, config=run_config)

            if result.success:
                # 智能提取 markdown：fit_markdown 优先，过度裁剪时自动回退 raw_markdown
                markdown = extract_markdown(result)

                word_count = len(markdown.replace('\n', '').replace(' ', '')) if markdown else 0

                # 提取元数据
                metadata = extract_metadata(
                    html_content=result.html,
                    base_url=url
                )

                if hasattr(result, 'metadata') and isinstance(result.metadata, dict):
                    metadata.update({
                        'crawl4ai_title': result.metadata.get('title'),
                        'crawl4ai_description': result.metadata.get('description'),
                    })

                crawl_time_ms = int((time.time() - start_time) * 1000)

                logger.info(f"[Single] Success: {url}, words: {word_count}, time: {crawl_time_ms}ms")

                return CrawlResult(
                    success=True,
                    url=url,
                    title=metadata.get('title') or metadata.get('crawl4ai_title'),
                    markdown=markdown,
                    metadata=metadata,
                    word_count=word_count,
                    crawl_time_ms=crawl_time_ms
                )
            else:
                error_msg = f"Crawl4AI returned unsuccessful result: {getattr(result, 'error_message', 'Unknown error')}"
                logger.warning(f"[Single] Failed: {url}, {error_msg}")

                return CrawlResult(
                    success=False,
                    url=url,
                    error_message=error_msg,
                    crawl_time_ms=int((time.time() - start_time) * 1000)
                )
        finally:
            if own_crawler:
                await crawler.__aexit__(None, None, None)

    except Exception as e:
        logger.error(f"[Single] Exception: {url}, {str(e)}", exc_info=True)

        return CrawlResult(
            success=False,
            url=url,
            error_message=str(e),
            crawl_time_ms=int((time.time() - start_time) * 1000)
        )
