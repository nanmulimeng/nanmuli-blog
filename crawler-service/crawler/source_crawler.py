"""URL/RSS 信息源爬取模块

从 digest.py 迁出，作为独立的源爬取工具。
被 CrawlerAgent / bubble_breaker / digest 旧路径共同引用。
"""

import asyncio
import logging

from config import settings
from crawler.filters import is_excluded_domain

logger = logging.getLogger(__name__)


async def crawl_url_sources(section: dict, config, crawler) -> list:
    """爬取板块中所有 URL 类型的信息源。

    对每个 URL 源根据 crawlMode 选择 single 或 deep 爬取。
    单个源失败不阻断其他源。
    """
    from crawler.single import crawl_single_page
    from crawler.deep import crawl_deep_pages
    from crawler.models import CrawlResult
    from crawler.source_analysis import is_truly_dead

    results: list[CrawlResult] = []
    url_sources = section.get("url_sources", [])
    max_items = section.get("max_items", 5)

    for src in url_sources[:max_items]:
        url = src.get("url", "")
        if not url:
            continue
        if is_excluded_domain(url):
            logger.info("Skipping excluded URL source: %s", url)
            continue
        eff = src.get("effectiveness", {})
        if is_truly_dead(eff):
            logger.debug("Skipping dead URL source: url=%s success_rate=%.0f%%",
                         url, eff.get("success_rate", 0) * 100)
            continue
        try:
            src_name = src.get("source_name", "")
            source_id = src.get("source_id")
            if src.get("crawl_mode", "single") == "deep":
                pages = await crawl_deep_pages(
                    url=url,
                    max_depth=src.get("max_depth", 1),
                    max_pages=src.get("max_pages", 10),
                    config=config,
                    crawler=crawler,
                )
                for p in pages:
                    if src_name:
                        p.metadata["source_name"] = src_name
                    if source_id is not None:
                        p.metadata["source_id"] = source_id
                results.extend(pages)
            else:
                result = await crawl_single_page(url=url, config=config, crawler=crawler)
                if src_name:
                    result.metadata["source_name"] = src_name
                if source_id is not None:
                    result.metadata["source_id"] = source_id
                results.append(result)
        except Exception as e:
            logger.warning("URL source crawl failed: url=%s error=%s", url, e)

    return results


async def crawl_rss_sources(section: dict, config, crawler) -> list:
    """解析板块中所有 RSS Feed，爬取每篇文章。

    1. parse_feed() 提取文章 URL 列表
    2. 逐篇 crawl_single_page() 获取 markdown
    """
    from crawler.feed import parse_feed
    from crawler.single import crawl_single_page
    from crawler.models import CrawlResult
    from crawler.source_analysis import is_truly_dead

    results: list[CrawlResult] = []
    rss_sources = section.get("rss_sources", [])
    max_items = section.get("max_items", 5)

    page_sem = asyncio.Semaphore(settings.max_concurrent_crawls)

    async def _crawl_feed_entry(entry_url: str, feed_title: str = "") -> CrawlResult | None:
        async with page_sem:
            try:
                result = await crawl_single_page(url=entry_url, config=config, crawler=crawler)
                if result and feed_title:
                    result.metadata["feed_title"] = feed_title
                    if not result.title:
                        result.title = feed_title
                return result
            except Exception as e:
                logger.debug("RSS article crawl failed: url=%s error=%s", entry_url, e)
                return None

    for rss_src in rss_sources:
        feed_url = rss_src.get("feed_url", "")
        freshness_hours = rss_src.get("freshness_hours", 24)
        src_name = rss_src.get("source_name", "")
        source_id = rss_src.get("source_id")
        rss_max = rss_src.get("max_entries", max_items)
        if not feed_url:
            continue
        eff = rss_src.get("effectiveness", {})
        if is_truly_dead(eff):
            logger.debug("Skipping dead RSS source: feed=%s", feed_url)
            continue

        try:
            entries = await parse_feed(
                feed_url=feed_url,
                freshness_hours=freshness_hours,
                max_entries=rss_max,
                proxy=settings.proxy_url,
            )
        except Exception as e:
            logger.warning("RSS feed parse failed: url=%s error=%s", feed_url, e)
            continue

        if not entries:
            continue

        logger.info("RSS feed '%s': %d fresh entries to crawl", feed_url, len(entries))

        filtered_entries = []
        for entry in entries:
            if is_excluded_domain(entry.url):
                logger.info("Skipping excluded RSS entry: %s", entry.url)
                continue
            filtered_entries.append(entry)

        tasks = [_crawl_feed_entry(e.url, e.title) for e in filtered_entries]
        page_results = await asyncio.gather(*tasks, return_exceptions=True)

        failed_count = sum(1 for r in page_results if not isinstance(r, CrawlResult))
        if failed_count:
            logger.warning("RSS feed '%s': %d/%d entries failed",
                           feed_url, failed_count, len(filtered_entries))

        for r in page_results:
            if isinstance(r, CrawlResult):
                if src_name:
                    r.metadata["source_name"] = src_name
                if source_id is not None:
                    r.metadata["source_id"] = source_id
                results.append(r)

    return results
