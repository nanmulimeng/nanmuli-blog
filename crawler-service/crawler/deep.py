"""
深度爬取模块

BFS 遍历同域名下的多个页面
"""

import time
import logging
from typing import List, Optional
from urllib.parse import urlparse

from crawl4ai import AsyncWebCrawler
from crawl4ai.deep_crawling import BFSDeepCrawlStrategy
from crawl4ai.deep_crawling.filters import FilterChain, DomainFilter
from .deep_filters import ExcludedDomainFilter

from config import settings
from .config import get_browser_config, get_crawler_run_config, RunParams, extract_markdown
from .models import CrawlResult, JS_CHALLENGE_MIN_WORDS
from .utils import count_words
from .processor import extract_page_metadata, retry_js_challenge, extract_depth

logger = logging.getLogger(__name__)

_MULTI_PART_TLD = {
    'co', 'com', 'org', 'net', 'edu', 'gov', 'ac',
}


async def crawl_deep_pages(
    url: str,
    max_depth: int = 2,
    max_pages: int = 10,
    config: Optional[object] = None,
    crawler: Optional[AsyncWebCrawler] = None
) -> List[CrawlResult]:
    """
    BFS 深度爬取同域名页面

    Args:
        url: 起始 URL
        max_depth: 最大爬取深度（1-3）
        max_pages: 最大页面数（1-20）
        config: 爬取配置
        crawler: 外部传入的浏览器实例（复用时不启停浏览器）

    Returns:
        CrawlResult 列表
    """
    start_time = time.time()
    results = []
    crawled_urls = set()

    # 参数校验
    if max_depth < 1:
        raise ValueError(f"max_depth must be >= 1, got {max_depth}")
    if max_pages < 1:
        raise ValueError(f"max_pages must be >= 1, got {max_pages}")

    try:
        params = RunParams(config)

        # 提取域名
        parsed = urlparse(url)
        domain = parsed.netloc
        # 处理子域名：考虑 ccTLD 如 co.uk, com.cn, com.au 等
        parts = domain.split('.')
        if len(parts) >= 3 and parts[-2] in _MULTI_PART_TLD:
            base_domain = '.'.join(parts[-3:])
        else:
            base_domain = '.'.join(parts[-2:])

        logger.info("[Deep] Starting BFS crawl: %s, depth=%s, max_pages=%s, domain=%s", url, max_depth, max_pages, base_domain)

        browser_config = await get_browser_config(text_mode=params.text_mode, light_mode=params.light_mode, proxy=settings.proxy_url)
        run_config = get_crawler_run_config(**params.to_run_config_kwargs())

        # 配置深度爬取策略
        run_config.deep_crawl_strategy = BFSDeepCrawlStrategy(
            max_depth=max_depth,
            max_pages=max_pages,
            include_external=False,  # 只爬同域名
            filter_chain=FilterChain([
                DomainFilter(allowed_domains=[domain, f"*.{base_domain}"]),
                ExcludedDomainFilter(),  # P2: 路径级过滤
            ])
        )

        # 获取爬取结果（复用或新建浏览器），保留活跃 crawler 引用供重试
        active_crawler = None
        if crawler is None:
            async with AsyncWebCrawler(config=browser_config) as c:
                active_crawler = c
                results_raw = await c.arun(url=url, config=run_config)
        else:
            active_crawler = crawler
            results_raw = await crawler.arun(url=url, config=run_config)

        # Crawl4AI 0.8.x: arun 返回 list（非 AsyncGenerator）
        if not isinstance(results_raw, list):
            results_raw = [results_raw]
        page_count = 0
        for result in results_raw:
            # 上层 URL 去重保护（防御 BFSDeepCrawlStrategy 去重失效）
            if result.url in crawled_urls:
                logger.debug("[Deep] Skipping duplicate URL: %s", result.url)
                continue
            crawled_urls.add(result.url)

            page_count += 1

            if result.success:
                markdown = extract_markdown(result)
                word_count = count_words(markdown) if markdown else 0

                # JS Challenge 检测：成功但字数异常低，对该 URL 单独重试
                if word_count < JS_CHALLENGE_MIN_WORDS and active_crawler is not None:
                    logger.warning(
                        "[Deep] Low word count (%s) on %s, possible JS challenge, retrying",
                        word_count, result.url
                    )
                    try:
                        retry_results = await retry_js_challenge(active_crawler, result.url, params)
                        if retry_results and isinstance(retry_results, list):
                            retry = retry_results[0]
                        else:
                            retry = retry_results
                        if retry and getattr(retry, 'success', False):
                            markdown = extract_markdown(retry)
                            word_count = count_words(markdown) if markdown else 0
                            result = retry
                            logger.info("[Deep] JS challenge retry succeeded: %s, words=%s", result.url, word_count)
                    except Exception as retry_err:
                        logger.warning("[Deep] JS challenge retry failed for %s: %s, keeping original", result.url, retry_err)

                depth = extract_depth(result)

                page_metadata = extract_page_metadata(result, result.url) if result.html else {}
                page_metadata['links_found'] = len(getattr(result, 'links', {}).get('internal', []))

                page_title = page_metadata.get('title') or page_metadata.get('crawl4ai_title')

                crawl_result = CrawlResult(
                    success=True,
                    url=result.url,
                    title=page_title,
                    markdown=markdown,
                    metadata=page_metadata,
                    word_count=word_count,
                    crawl_time_ms=getattr(result, 'crawl_time', 0),
                    depth=depth
                )
                results.append(crawl_result)

                logger.info("[Deep] Page %s/%s: %s (depth=%s, words=%s)", page_count, max_pages, result.url, depth, word_count)

            else:
                logger.warning("[Deep] Failed to crawl: %s, error: %s", result.url, getattr(result, 'error_message', 'Unknown'))
                fail_depth = getattr(result, 'depth', None)
                if fail_depth is None and isinstance(getattr(result, 'metadata', None), dict):
                    fail_depth = result.metadata.get('depth', 0)
                if fail_depth is None:
                    fail_depth = 0

                results.append(CrawlResult(
                    success=False,
                    url=result.url,
                    error_message=getattr(result, 'error_message', 'Unknown error'),
                    crawl_time_ms=getattr(result, 'crawl_time', 0),
                    depth=fail_depth
                ))

            # 达到最大页面数时停止
            if page_count >= max_pages:
                logger.info("[Deep] Reached max_pages limit: %s", max_pages)
                break

        total_time = int((time.time() - start_time) * 1000)
        success_count = sum(1 for r in results if r.success)
        logger.info("[Deep] Completed: %s/%s pages crawled successfully, total_time=%sms", success_count, len(results), total_time)

        return results

    except Exception as e:
        logger.error("[Deep] Exception during deep crawl: %s", str(e), exc_info=True)

        # 返回已爬取的结果 + 错误信息
        results.append(CrawlResult(
            success=False,
            url=url,
            error_message=f"Deep crawl failed: {str(e)}",
            crawl_time_ms=int((time.time() - start_time) * 1000)
        ))

        return results
