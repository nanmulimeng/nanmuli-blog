"""
关键词搜索爬取模块

基于搜索引擎的关键词搜索，爬取搜索结果页面的内容
"""

import asyncio
import time
import logging
from typing import List, Optional
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup

from crawl4ai import AsyncWebCrawler

from .config import get_browser_config, RunParams
from .single import CrawlResult, crawl_single_page

logger = logging.getLogger(__name__)

# 搜索引擎配置
SEARCH_ENGINES = {
    'bing': {
        'url': 'https://www.bing.com/search?q={query}&count={count}',
        'result_selector': 'li.b_algo',
        'title_selector': 'h2 a',
        'link_selector': 'h2 a',
        'snippet_selector': 'p',
    },
    'duckduckgo': {
        'url': 'https://html.duckduckgo.com/html/?q={query}',
        'result_selector': '.result',
        'title_selector': '.result__a',
        'link_selector': '.result__a',
        'snippet_selector': '.result__snippet',
    }
}


async def crawl_by_keyword(
    keyword: str,
    engine: str = 'bing',
    max_results: int = 10,
    config: Optional[object] = None
) -> List[CrawlResult]:
    """
    通过搜索引擎查找关键词，爬取前 N 个结果

    Args:
        keyword: 搜索关键词
        engine: 搜索引擎 ('bing' 或 'duckduckgo')
        max_results: 最大结果数
        config: 爬取配置

    Returns:
        CrawlResult 列表
    """
    start_time = time.time()

    logger.info(f"[Search] Keyword: '{keyword}', engine: {engine}, max_results: {max_results}")

    try:
        # 获取搜索结果 URL 列表
        search_urls = await _get_search_results(
            keyword=keyword,
            engine=engine,
            max_results=max_results
        )

        if not search_urls:
            logger.warning(f"[Search] No results found for keyword: '{keyword}'")
            return [CrawlResult(
                success=False,
                url="",
                error_message=f"No search results found for keyword: '{keyword}'"
            )]

        logger.info(f"[Search] Found {len(search_urls)} URLs for keyword '{keyword}'")

        # 共享浏览器实例 + 并发控制
        params = RunParams(config)
        browser_config = get_browser_config(text_mode=params.text_mode, light_mode=params.light_mode)

        results = await _crawl_urls_with_shared_browser(
            urls=search_urls, keyword=keyword, engine=engine,
            config=config, browser_config=browser_config
        )

        total_time = int((time.time() - start_time) * 1000)
        success_count = sum(1 for r in results if r.success)
        logger.info(f"[Search] Completed: {success_count}/{len(results)} pages crawled, keyword='{keyword}', time={total_time}ms")

        return results

    except Exception as e:
        logger.error(f"[Search] Primary search failed: {e}")

        # 降级策略：主搜索引擎失败后尝试 DuckDuckGo
        if engine != 'duckduckgo':
            try:
                fallback_urls = await _fallback_search(keyword, max_results)
                if fallback_urls:
                    logger.info(f"[Search] Fallback found {len(fallback_urls)} results")
                    fallback_urls = fallback_urls[:max_results]

                    params = RunParams(config)
                    browser_config = get_browser_config(text_mode=params.text_mode, light_mode=params.light_mode)
                    fallback_results = await _crawl_urls_with_shared_browser(
                        urls=fallback_urls, keyword=keyword, engine='duckduckgo',
                        config=config, browser_config=browser_config,
                        is_fallback=True
                    )
                    return fallback_results
            except Exception as fallback_e:
                logger.error(f"[Search] Fallback also failed: {fallback_e}")

        return [CrawlResult(
            success=False,
            url="",
            error_message=f"Search crawl failed: {str(e)}"
        )]


async def _crawl_urls_with_shared_browser(
    urls: List[str],
    keyword: str,
    engine: str,
    config: Optional[object],
    browser_config,
    is_fallback: bool = False
) -> List[CrawlResult]:
    """共享浏览器实例 + 并发信号量爬取多个 URL"""
    sem = asyncio.Semaphore(3)

    async def _crawl_one(rank: int, url: str) -> CrawlResult:
        async with sem:
            try:
                result = await crawl_single_page(url=url, config=config, crawler=crawler)
                result.search_rank = rank
                result.metadata['search_keyword'] = keyword
                result.metadata['search_engine'] = engine
                if is_fallback:
                    result.metadata['fallback'] = True
                return result
            except Exception as e:
                logger.warning(f"[Search] Failed to crawl {url}: {e}")
                meta = {'search_rank': rank, 'search_keyword': keyword}
                if is_fallback:
                    meta['fallback'] = True
                return CrawlResult(
                    success=False,
                    url=url,
                    error_message=str(e),
                    search_rank=rank,
                    metadata=meta
                )

    async with AsyncWebCrawler(config=browser_config) as crawler:
        tasks = [_crawl_one(rank, url) for rank, url in enumerate(urls, 1)]
        results = await asyncio.gather(*tasks)
        return list(results)


async def _get_search_results(
    keyword: str,
    engine: str,
    max_results: int
) -> List[str]:
    """
    获取搜索结果页面的 URL 列表

    Args:
        keyword: 搜索关键词
        engine: 搜索引擎
        max_results: 最大结果数

    Returns:
        URL 列表
    """
    if engine not in SEARCH_ENGINES:
        raise ValueError(f"Unsupported search engine: {engine}. Supported: {list(SEARCH_ENGINES.keys())}")

    config = SEARCH_ENGINES[engine]
    search_url = config['url'].format(
        query=quote_plus(keyword),
        count=max(min(max_results * 2, 30), 10)  # 请求更多结果以过滤
    )

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.5',
    }

    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
        response = await client.get(search_url, headers=headers)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'lxml')

        urls = []
        result_items = soup.select(config['result_selector'])

        for item in result_items[:max_results]:
            link_elem = item.select_one(config['link_selector'])
            if link_elem:
                href = link_elem.get('href', '')
                # 清理 Bing 的跳转链接
                if engine == 'bing' and '/url?u=' in href:
                    import urllib.parse
                    parsed = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
                    if 'u' in parsed:
                        href = parsed['u'][0]

                # 验证 URL
                if href and href.startswith(('http://', 'https://')):
                    # 排除常见广告/无关域名
                    if not _is_excluded_domain(href):
                        urls.append(href)

        return urls[:max_results]


def _is_excluded_domain(url: str) -> bool:
    """检查 URL 是否属于排除列表（广告、社交等）"""
    excluded_patterns = [
        'google.com/search',
        'bing.com/search',
        'duckduckgo.com',
        'youtube.com',
        'facebook.com',
        'twitter.com',
        'instagram.com',
        'amazon.com',
        'ebay.com',
        'pinterest.com',
        'linkedin.com',
    ]

    url_lower = url.lower()
    return any(pattern in url_lower for pattern in excluded_patterns)


# 降级搜索策略（如果主搜索引擎失败）
async def _fallback_search(
    keyword: str,
    max_results: int
) -> List[str]:
    """
    搜索引擎失败时的降级策略

    尝试使用 DuckDuckGo（通常限制较少）
    """
    logger.info(f"[Search] Attempting fallback search for: '{keyword}'")
    try:
        return await _get_search_results(keyword, 'duckduckgo', max_results)
    except Exception as e:
        logger.error(f"[Search] Fallback also failed: {e}")
        return []
