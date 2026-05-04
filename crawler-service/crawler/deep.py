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

from .config import get_browser_config, get_crawler_run_config, RunParams, extract_markdown
from .metadata import extract_metadata
from .single import CrawlResult

logger = logging.getLogger(__name__)


async def crawl_deep_pages(
    url: str,
    max_depth: int = 2,
    max_pages: int = 10,
    config: Optional[object] = None
) -> List[CrawlResult]:
    """
    BFS 深度爬取同域名页面

    Args:
        url: 起始 URL
        max_depth: 最大爬取深度（1-3）
        max_pages: 最大页面数（1-20）
        config: 爬取配置

    Returns:
        CrawlResult 列表
    """
    start_time = time.time()
    results = []
    crawled_urls = set()

    try:
        params = RunParams(config)

        # 提取域名
        parsed = urlparse(url)
        domain = parsed.netloc
        base_domain = '.'.join(domain.split('.')[-2:])  # 处理子域名

        logger.info(f"[Deep] Starting BFS crawl: {url}, depth={max_depth}, max_pages={max_pages}, domain={base_domain}")

        browser_config = get_browser_config(text_mode=params.text_mode, light_mode=params.light_mode)
        run_config = get_crawler_run_config(
            word_count_threshold=params.word_count_threshold,
            excluded_tags=params.excluded_tags,
            wait_until=params.wait_until,
            page_timeout=params.page_timeout
        )

        # 配置深度爬取策略
        run_config.deep_crawl_strategy = BFSDeepCrawlStrategy(
            max_depth=max_depth,
            max_pages=max_pages,
            include_external=False,  # 只爬同域名
            filter_chain=FilterChain([
                DomainFilter(allowed_domains=[domain, f"*.{base_domain}"]),
            ])
        )

        page_count = 0
        async with AsyncWebCrawler(config=browser_config) as crawler:
            # Crawl4AI 0.8.x: arun 返回 list（非 AsyncGenerator）
            results_raw = await crawler.arun(url=url, config=run_config)
            for result in results_raw:
                page_count += 1

                if result.success:
                    # 智能提取 markdown：fit_markdown 优先，过度裁剪时自动回退 raw_markdown
                    markdown = extract_markdown(result)

                    word_count = len(markdown.replace('\n', '').replace(' ', '')) if markdown else 0

                    # 获取深度信息（Crawl4AI 0.8.x: depth 在 metadata 中）
                    depth = getattr(result, 'depth', None)
                    if depth is None and isinstance(result.metadata, dict):
                        depth = result.metadata.get('depth', 0)
                    if depth is None:
                        depth = 0

                    # 提取丰富元数据（与 single.py 一致）
                    page_metadata = extract_metadata(
                        html_content=result.html,
                        base_url=result.url
                    ) if result.html else {}

                    page_metadata['links_found'] = len(getattr(result, 'links', {}).get('internal', []))

                    if hasattr(result, 'metadata') and isinstance(result.metadata, dict):
                        page_metadata.update({
                            'crawl4ai_title': result.metadata.get('title'),
                            'crawl4ai_description': result.metadata.get('description'),
                        })

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
                    crawled_urls.add(result.url)

                    logger.info(f"[Deep] Page {page_count}/{max_pages}: {result.url} (depth={depth}, words={word_count})")

                else:
                    logger.warning(f"[Deep] Failed to crawl: {result.url}, error: {getattr(result, 'error_message', 'Unknown')}")
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
                    logger.info(f"[Deep] Reached max_pages limit: {max_pages}")
                    break

        total_time = int((time.time() - start_time) * 1000)
        success_count = sum(1 for r in results if r.success)
        logger.info(f"[Deep] Completed: {success_count}/{len(results)} pages crawled successfully, total_time={total_time}ms")

        return results

    except Exception as e:
        logger.error(f"[Deep] Exception during deep crawl: {str(e)}", exc_info=True)

        # 返回已爬取的结果 + 错误信息
        results.append(CrawlResult(
            success=False,
            url=url,
            error_message=f"Deep crawl failed: {str(e)}",
            crawl_time_ms=int((time.time() - start_time) * 1000)
        ))

        return results
