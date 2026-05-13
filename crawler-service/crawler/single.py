"""
单页爬取模块

爬取单个 URL 的内容，返回 Markdown 格式文本
"""

import re
import time
import logging
from typing import Optional

from crawl4ai import AsyncWebCrawler

from config import settings
from .config import get_browser_config, get_crawler_run_config, RunParams, extract_markdown
from .metadata import extract_metadata
from .utils import count_words

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


_JS_CHALLENGE_MIN_WORDS = 20
_JS_CHALLENGE_WAIT_FOR = "article, main, .post-content, .entry-content, .content, #content, .article"
_JS_CHALLENGE_DELAY = 3.0


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

    try:
        params = RunParams(config)

        logger.info("[Single] Crawling: %s", url)

        browser_config = get_browser_config(text_mode=params.text_mode, light_mode=params.light_mode, proxy=settings.proxy_url)
        run_config = get_crawler_run_config(
            word_count_threshold=params.word_count_threshold,
            excluded_tags=params.excluded_tags,
            excluded_selector=params.excluded_selector,
            prune_threshold=params.prune_threshold,
            wait_until=params.wait_until,
            page_timeout=params.page_timeout,
            remove_overlay_elements=params.remove_overlay_elements,
            max_retries=params.max_retries,
            mean_delay=params.mean_delay,
            max_range=params.max_range,
            delay_before_return_html=params.delay_before_return_html,
            remove_consent_popups=params.remove_consent_popups,
        )

        if crawler is None:
            async with AsyncWebCrawler(config=browser_config) as c:
                return await _run_crawl(c, url, run_config, start_time, params)
        else:
            return await _run_crawl(crawler, url, run_config, start_time, params)

    except Exception as e:
        logger.error("[Single] Exception: %s, %s", url, str(e), exc_info=True)

        return CrawlResult(
            success=False,
            url=url,
            error_message=str(e),
            crawl_time_ms=int((time.time() - start_time) * 1000)
        )


async def _run_crawl(crawler, url: str, run_config, start_time: float,
                   params=None) -> CrawlResult:
    """执行单次爬取（与 crawler 生命周期解耦），低字数时自动 JS Challenge 重试"""
    result = await crawler.arun(url=url, config=run_config)

    if result.success:
        markdown = extract_markdown(result)
        word_count = count_words(markdown) if markdown else 0

        # JS Challenge 检测：成功但字数异常低，可能捕获了 interstitial
        if word_count < _JS_CHALLENGE_MIN_WORDS and params is not None:
            logger.warning(
                "[Single] Low word count (%s), possible JS challenge interstitial, "
                "retrying with wait_for", word_count
            )
            retry_config = get_crawler_run_config(
                word_count_threshold=params.word_count_threshold,
                excluded_tags=params.excluded_tags,
                excluded_selector=params.excluded_selector,
                prune_threshold=params.prune_threshold,
                wait_until=params.wait_until,
                page_timeout=params.page_timeout,
                remove_overlay_elements=params.remove_overlay_elements,
                max_retries=params.max_retries,
                mean_delay=params.mean_delay,
                max_range=params.max_range,
                delay_before_return_html=_JS_CHALLENGE_DELAY,
                remove_consent_popups=params.remove_consent_popups,
                wait_for=_JS_CHALLENGE_WAIT_FOR,
                wait_for_timeout=5000,
            )
            result = await crawler.arun(url=url, config=retry_config)
            if result.success:
                markdown = extract_markdown(result)
                word_count = count_words(markdown) if markdown else 0

        metadata = extract_metadata(
            html_content=getattr(result, 'html', None) or '',
            base_url=url
        )

        if hasattr(result, 'metadata') and isinstance(result.metadata, dict):
            metadata.update({
                'crawl4ai_title': result.metadata.get('title'),
                'crawl4ai_description': result.metadata.get('description'),
            })

        crawl_time_ms = int((time.time() - start_time) * 1000)
        logger.info("[Single] Success: %s, words: %s, time: %sms", url, word_count, crawl_time_ms)

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
        logger.warning("[Single] Failed: %s, %s", url, error_msg)

        return CrawlResult(
            success=False,
            url=url,
            error_message=error_msg,
            crawl_time_ms=int((time.time() - start_time) * 1000)
        )

