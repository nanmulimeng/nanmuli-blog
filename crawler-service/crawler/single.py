"""
单页爬取模块

爬取单个 URL 的内容，返回 Markdown 格式文本
"""

import time
import logging
from typing import Optional
from urllib.parse import urljoin, urlparse

from crawl4ai import AsyncWebCrawler

from .config import get_browser_config, get_crawler_run_config
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
    config: Optional[object] = None
) -> CrawlResult:
    """
    爬取单个页面

    Args:
        url: 目标 URL
        config: 爬取配置（Pydantic 模型或 dict）

    Returns:
        CrawlResult 对象
    """
    start_time = time.time()

    try:
        # 转换配置
        if config is None:
            text_mode = True
            light_mode = True
            word_count_threshold = 3
            excluded_tags = ["nav", "footer", "aside", "header", "script", "style"]
            wait_until = "networkidle"
            page_timeout = 60000
        else:
            text_mode = getattr(config, 'text_mode', True)
            light_mode = getattr(config, 'light_mode', True)
            word_count_threshold = getattr(config, 'word_count_threshold', 3)
            excluded_tags = getattr(config, 'excluded_tags', ["nav", "footer", "aside", "header", "script", "style"])
            wait_until = getattr(config, 'wait_until', "networkidle")
            page_timeout = getattr(config, 'page_timeout', 60000)

        logger.info(f"[Single] Crawling: {url}")

        browser_config = get_browser_config(text_mode=text_mode, light_mode=light_mode)
        run_config = get_crawler_run_config(
            word_count_threshold=word_count_threshold,
            excluded_tags=excluded_tags,
            wait_until=wait_until,
            page_timeout=page_timeout
        )

        async with AsyncWebCrawler(config=browser_config) as crawler:
            result = await crawler.arun(url=url, config=run_config)

            if result.success:
                # Crawl4AI 0.8.x: markdown 可能是 StringCompatibleMarkdown 或 MarkdownGenerationResult
                markdown = None
                if hasattr(result.markdown, 'raw_markdown') and result.markdown.raw_markdown:
                    markdown = result.markdown.raw_markdown
                elif hasattr(result.markdown, 'fit_markdown') and result.markdown.fit_markdown:
                    markdown = result.markdown.fit_markdown
                if not markdown:
                    markdown = str(result.markdown) if result.markdown else ""

                # 计算字数
                word_count = len(markdown.replace('\n', '').replace(' ', '')) if markdown else 0

                # 提取元数据
                metadata = extract_metadata(
                    html_content=result.html,
                    base_url=url
                )

                # 添加 Crawl4AI 提供的元数据
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

    except Exception as e:
        logger.error(f"[Single] Exception: {url}, {str(e)}", exc_info=True)

        return CrawlResult(
            success=False,
            url=url,
            error_message=str(e),
            crawl_time_ms=int((time.time() - start_time) * 1000)
        )
