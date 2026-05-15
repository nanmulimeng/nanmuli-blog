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
from .utils import count_words
from .models import CrawlResult, JS_CHALLENGE_MIN_WORDS
from .processor import extract_page_metadata, retry_js_challenge

logger = logging.getLogger(__name__)


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

        browser_config = await get_browser_config(text_mode=params.text_mode, light_mode=params.light_mode, proxy=settings.proxy_url)
        run_config = get_crawler_run_config(**params.to_run_config_kwargs())

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
        if word_count < JS_CHALLENGE_MIN_WORDS and params is not None:
            logger.warning(
                "[Single] Low word count (%s), possible JS challenge interstitial, "
                "retrying with wait_for", word_count
            )
            result = await retry_js_challenge(crawler, url, params)
            if result.success:
                markdown = extract_markdown(result)
                word_count = count_words(markdown) if markdown else 0

        metadata = extract_page_metadata(result, url)

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

