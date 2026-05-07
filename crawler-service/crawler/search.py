"""Keyword-search crawler implementation."""

import asyncio
import base64
import logging
import os
import random
import re
import time
from typing import List, Optional
from urllib.parse import parse_qs, quote_plus, urlparse

import httpx
from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler

from .config import RunParams, get_browser_config, get_search_run_config
from .dedup import dedup_results
from .filters import has_excluded_keywords, is_excluded_domain
from .single import CrawlResult, crawl_single_page

logger = logging.getLogger(__name__)

MAX_DOMAIN_DEDUP = int(os.getenv("MAX_DOMAIN_DEDUP", "2"))
PROXY_URL = os.getenv("PROXY_URL") or os.getenv("HTTP_PROXY") or os.getenv("HTTPS_PROXY") or ""
SEARCH_PAGE_RETRIES = 2

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:138.0) Gecko/20100101 Firefox/138.0",
]

SEARCH_ENGINES = {
    "sogou": {
        "result_selector": ".vrwrap",
        "title_selector": ".vrTitle a, h3 a",
        "link_selector": ".vrTitle a, h3 a",
        "snippet_selector": ".str-text, .star-w",
        "fallback_selectors": [".results .rb", ".result"],
    },
    "bing": {
        "result_selector": "li.b_algo",
        "title_selector": "h2 a",
        "link_selector": "h2 a",
        "snippet_selector": "p",
        "fallback_selectors": ["#b_results li", "ol#b_results > li"],
    },
    "baidu": {
        "result_selector": ".result",
        "title_selector": "h3 a",
        "link_selector": "h3 a",
        "snippet_selector": ".content-right, .c-abstract",
        "fallback_selectors": [".c-container"],
    },
    "google": {
        "result_selector": "div.g",
        "title_selector": "h3",
        "link_selector": "a",
        "snippet_selector": ".VwiC3b, .s3v94d",
        "fallback_selectors": ["div[data-sokoban-container]", "div.tF2Cxc"],
    },
}

ENGINE_PRIORITY = ["bing", "baidu", "sogou", "google"]

TIME_FILTER_PARAMS = {
    "bing": {
        "day": '&filters=ex1:"ez5_4251_4252"',
        "week": '&filters=ex1:"ez5_4251_4253"',
        "month": '&filters=ex1:"ez5_4251_4254"',
        "year": '&filters=ex1:"ez5_4251_4255"',
        "all": "",
    },
    "google": {
        "day": "&tbs=qdr:d",
        "week": "&tbs=qdr:w",
        "month": "&tbs=qdr:m",
        "year": "&tbs=qdr:y",
        "all": "",
    },
    "sogou": {
        "day": "&s_from=forecast&forecast=day",
        "week": "&s_from=forecast&forecast=week",
        "month": "&s_from=forecast&forecast=month",
        "year": "&s_from=forecast&forecast=year",
        "all": "",
    },
}


def _build_headers() -> dict:
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Sec-Ch-Ua": '"Chromium";v="136", "Google Chrome";v="136"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "DNT": "1",
    }


def _is_whole_word_match(text: str, keyword: str) -> bool:
    if not keyword:
        return False
    if len(keyword.split()) > 1 or any("\u4e00" <= char <= "\u9fff" for char in keyword):
        return keyword in text
    return bool(re.search(r"\b" + re.escape(keyword) + r"\b", text))


def _is_relevant_to_keyword(keyword: str, title: str, snippet: str) -> bool:
    if not title or title.strip().lower() in ("no title", ""):
        return False

    title_lower = title.lower()
    snippet_lower = snippet.lower()
    if has_excluded_keywords(title_lower + " " + snippet_lower):
        return False

    keyword_lower = keyword.lower().strip()
    if _is_whole_word_match(title_lower, keyword_lower):
        return True
    if _is_whole_word_match(snippet_lower, keyword_lower):
        return True

    keyword_parts = [part for part in keyword_lower.split() if len(part) >= 2]
    if not keyword_parts:
        short_kw = keyword_lower.strip()
        return _is_whole_word_match(title_lower, short_kw) or _is_whole_word_match(snippet_lower, short_kw)

    title_matches = sum(1 for part in keyword_parts if _is_whole_word_match(title_lower, part))
    if title_matches >= 1:
        return True

    snippet_matches = sum(1 for part in keyword_parts if _is_whole_word_match(snippet_lower, part))
    min_required = max(1, int(len(keyword_parts) * 0.5 + 0.5))
    return snippet_matches >= min_required


def _is_anti_bot_page(page_text: str, raw_html: str = "") -> bool:
    text_lower = page_text.lower()
    html_lower = raw_html.lower()
    indicators = [
        "验证码",
        "captcha",
        "security check",
        "verify you are human",
        "unusual traffic",
        "automated requests",
        "ip address has been blocked",
        "please verify",
        "i'm not a robot",
        "recaptcha",
        "安全验证",
    ]
    return any(indicator in text_lower or indicator in html_lower for indicator in indicators)


def _baidu_time_filter(time_range: str) -> str:
    if time_range == "all":
        return ""

    import datetime

    now = datetime.datetime.now()
    if time_range == "day":
        start = now - datetime.timedelta(days=1)
    elif time_range == "week":
        start = now - datetime.timedelta(days=7)
    elif time_range == "month":
        start = now - datetime.timedelta(days=30)
    elif time_range == "year":
        start = now - datetime.timedelta(days=365)
    else:
        return ""

    start_ts = int(start.timestamp())
    end_ts = int(now.timestamp())
    raw = f"stf={start_ts},{end_ts}|stftype=1"
    return "&gpc=" + base64.b64encode(raw.encode()).decode()


async def _fetch_search_html(search_url: str, engine: str) -> Optional[str]:
    try:
        proxy = PROXY_URL if engine == "google" else ""
        browser_config = get_browser_config(text_mode=True, light_mode=True, proxy=proxy)
        run_config = get_search_run_config(page_timeout=20000)
        async with AsyncWebCrawler(config=browser_config) as crawler:
            result = await crawler.arun(url=search_url, config=run_config)
            if result.success and result.html:
                return result.html
            logger.warning(
                "[Search] %s browser fetch failed: %s",
                engine,
                getattr(result, "error_message", "unknown error"),
            )
            return None
    except Exception as exc:
        logger.warning("[Search] %s browser fetch exception: %s", engine, exc)
        return None


async def _decode_baidu_redirect(href: str, search_url: str, headers: dict, client: httpx.AsyncClient) -> Optional[str]:
    link_headers = {
        "Referer": search_url,
        "User-Agent": headers["User-Agent"],
    }
    resolved_href = None

    resp = await client.head(href, headers=link_headers, follow_redirects=True)
    candidate = str(resp.url)
    if resp.status_code < 400 and "baidu.com/link?url=" not in candidate:
        resolved_href = candidate
    else:
        resp = await client.get(href, headers=link_headers, follow_redirects=True)
        candidate = str(resp.url)
        if resp.status_code < 400 and "baidu.com/link?url=" not in candidate:
            resolved_href = candidate

    return resolved_href


async def _parse_search_results(
    html: str,
    engine: str,
    config: dict,
    keyword: str,
    max_results: int,
    seen_domains: dict,
    urls: list,
    search_url: str,
    headers: dict,
    client: Optional[httpx.AsyncClient],
) -> tuple[int, int]:
    soup = BeautifulSoup(html, "lxml")
    result_items = soup.select(config["result_selector"])

    if not result_items:
        for selector in config.get("fallback_selectors", []):
            result_items = soup.select(selector)
            if result_items:
                logger.info("[Search] Fallback selector '%s' matched %s items for '%s'", selector, len(result_items), engine)
                break

    if not result_items:
        if engine != "google":
            page_text = soup.get_text() if soup else ""
            if _is_anti_bot_page(page_text, html):
                raise RuntimeError(f"Engine '{engine}' blocked by anti-bot/captcha")
        return 0, 0

    page_new = 0
    for item in result_items:
        if len(urls) >= max_results:
            break

        link_elem = item.select_one(config["link_selector"])
        if not link_elem:
            continue

        href = link_elem.get("href", "")
        title_elem = item.select_one(config.get("title_selector", config["link_selector"]))
        title = title_elem.get_text(strip=True) if title_elem else (link_elem.get_text(strip=True) or "")
        snippet_elem = item.select_one(config["snippet_selector"])
        snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""

        if engine == "bing":
            if "/url?u=" in href:
                parsed = parse_qs(urlparse(href).query)
                if "u" in parsed:
                    href = parsed["u"][0]
            elif "/ck/a?" in href:
                parsed = parse_qs(urlparse(href).query)
                if "u" in parsed:
                    try:
                        encoded = parsed["u"][0]
                        if encoded.startswith("a1"):
                            href = base64.b64decode(encoded[2:] + "==").decode("utf-8")
                    except Exception as exc:
                        logger.debug("[Search] Bing ck/a base64 decode failed: %s", exc)
        elif engine == "google" and href.startswith("/url?"):
            parsed = parse_qs(urlparse(href).query)
            if "q" in parsed:
                href = parsed["q"][0]
        elif engine == "sogou":
            if "weixin.sogou.com" in href:
                continue
            if href.startswith("/link?url="):
                if client is None:
                    continue
                try:
                    resp = await client.get(
                        f"https://www.sogou.com{href}",
                        headers={"User-Agent": headers["User-Agent"]},
                        follow_redirects=False,
                    )
                    match = re.search(r'window\.location\.replace\(["\'](.+?)["\']\)', resp.text)
                    if match:
                        href = match.group(1)
                    else:
                        match = re.search(
                            r'<meta[^>]+http-equiv=["\']refresh["\'][^>]+content=["\']\d+;URL=["\']?(.+?)["\']?["\']',
                            resp.text,
                            re.IGNORECASE,
                        )
                        if match:
                            href = match.group(1)
                        else:
                            continue
                    if "sogou.com" in href:
                        continue
                except Exception as exc:
                    logger.debug("[Search] Sogou link decode failed: %s", exc)
                    continue
        elif engine == "baidu" and "baidu.com/link?url=" in href:
            if client is None:
                continue
            try:
                resolved_href = await _decode_baidu_redirect(href, search_url, headers, client)
                if not resolved_href:
                    logger.debug("[Search] Baidu link decode returned unresolved URL, skipping")
                    continue
                href = resolved_href
            except Exception as exc:
                logger.debug("[Search] Baidu link decode failed: %s", exc)
                continue

        if not href or not href.startswith(("http://", "https://")):
            continue
        if is_excluded_domain(href):
            continue
        if not _is_relevant_to_keyword(keyword, title, snippet):
            continue

        domain = urlparse(href).netloc
        domain_count = seen_domains.get(domain, 0)
        if domain_count >= MAX_DOMAIN_DEDUP:
            continue
        seen_domains[domain] = domain_count + 1

        urls.append(href)
        page_new += 1

    logger.debug("[Search] Page: %s new URLs from %s raw results", page_new, len(result_items))
    return len(result_items), page_new


async def _get_search_results(keyword: str, engine: str, max_results: int, time_range: str = "week") -> List[str]:
    if engine not in SEARCH_ENGINES:
        raise ValueError(f"Unsupported search engine: {engine}. Supported: {list(SEARCH_ENGINES.keys())}")

    config = SEARCH_ENGINES[engine]
    headers = _build_headers()
    if engine == "sogou":
        headers["Referer"] = "https://www.sogou.com/"

    urls = []
    seen_domains = {}
    total_raw = 0
    page = 0
    consecutive_empty_pages = 0

    if engine == "baidu":
        time_filter = _baidu_time_filter(time_range)
    else:
        time_filter = TIME_FILTER_PARAMS.get(engine, {}).get(time_range, "")
    if time_range != "all":
        logger.info("[Search] Applying time filter '%s' for engine '%s'", time_range, engine)

    while len(urls) < max_results and page < 5:
        if engine == "bing":
            first = page * 10 + 1
            search_url = f"https://www.bing.com/search?q={quote_plus(keyword)}&setmkt=en-US&setlang=en&first={first}{time_filter}"
        elif engine == "sogou":
            search_url = f"https://www.sogou.com/web?query={quote_plus(keyword)}&page={page + 1}{time_filter}"
        elif engine == "google":
            start = page * 10
            search_url = f"https://www.google.com/search?q={quote_plus(keyword)}&num=10&start={start}&hl=en{time_filter}"
        elif engine == "baidu":
            pn = page * 10
            search_url = f"https://www.baidu.com/s?wd={quote_plus(keyword)}&pn={pn}{time_filter}"
        else:
            raise ValueError(f"Unsupported search engine: {engine}")

        try:
            if engine == "google":
                html = None
                for attempt in range(SEARCH_PAGE_RETRIES):
                    html = await _fetch_search_html(search_url, engine="google")
                    if html is not None:
                        break
                    if attempt < SEARCH_PAGE_RETRIES - 1:
                        await asyncio.sleep(random.uniform(1.0, 2.0))
                if html is None:
                    break
                raw_count, page_new = await _parse_search_results(
                    html=html,
                    engine=engine,
                    config=config,
                    keyword=keyword,
                    max_results=max_results,
                    seen_domains=seen_domains,
                    urls=urls,
                    search_url=search_url,
                    headers=headers,
                    client=None,
                )
            elif engine == "sogou":
                client_kwargs = {"follow_redirects": True, "timeout": 30}
                if PROXY_URL:
                    client_kwargs["proxy"] = PROXY_URL
                async with httpx.AsyncClient(**client_kwargs) as client:
                    try:
                        await client.get("https://www.sogou.com/", headers={"User-Agent": headers["User-Agent"]}, timeout=10)
                        await asyncio.sleep(0.5)
                    except Exception:
                        pass
                    response = await client.get(search_url, headers=headers)
                    response.raise_for_status()
                    raw_count, page_new = await _parse_search_results(
                        html=response.text,
                        engine=engine,
                        config=config,
                        keyword=keyword,
                        max_results=max_results,
                        seen_domains=seen_domains,
                        urls=urls,
                        search_url=search_url,
                        headers=headers,
                        client=client,
                    )
            else:
                client_kwargs = {"follow_redirects": True, "timeout": 30}
                if PROXY_URL:
                    client_kwargs["proxy"] = PROXY_URL
                async with httpx.AsyncClient(**client_kwargs) as client:
                    last_exc = None
                    for attempt in range(SEARCH_PAGE_RETRIES):
                        try:
                            response = await client.get(search_url, headers=headers)
                            if response.status_code >= 500:
                                response.raise_for_status()
                            raw_count, page_new = await _parse_search_results(
                                html=response.text,
                                engine=engine,
                                config=config,
                                keyword=keyword,
                                max_results=max_results,
                                seen_domains=seen_domains,
                                urls=urls,
                                search_url=search_url,
                                headers=headers,
                                client=client,
                            )
                            last_exc = None
                            break
                        except Exception as exc:
                            last_exc = exc
                            if attempt < SEARCH_PAGE_RETRIES - 1:
                                await asyncio.sleep(random.uniform(0.5, 1.5))
                            else:
                                raise last_exc

            total_raw += raw_count
            if page_new == 0:
                consecutive_empty_pages += 1
                if consecutive_empty_pages >= 2:
                    break
            else:
                consecutive_empty_pages = 0

            page += 1
            if page < 5:
                await asyncio.sleep(random.uniform(0.8, 2.0))
        except Exception as exc:
            logger.warning("[Search] Page %s failed for '%s': %s", page + 1, keyword, exc)
            break

    logger.info("[Search] Filtered %s URLs from %s raw results (pages=%s) for keyword='%s'", len(urls), total_raw, page, keyword)
    return urls


async def _crawl_urls_with_shared_browser(
    urls: List[str],
    keyword: str,
    url_source_map: dict,
    config: Optional[object],
    browser_config,
    is_fallback: bool = False,
) -> List[CrawlResult]:
    sem = asyncio.Semaphore(3)

    async def _crawl_one(rank: int, url: str) -> CrawlResult:
        async with sem:
            try:
                result = await crawl_single_page(url=url, config=config, crawler=crawler)
                if result.success and result.word_count < 50:
                    result.success = False
                    result.error_message = f"Content too short ({result.word_count} words, min 50)"
                result.search_rank = rank
                result.metadata["search_keyword"] = keyword
                result.metadata["search_engine"] = url_source_map.get(url, "unknown")
                if is_fallback:
                    result.metadata["fallback"] = True
                return result
            except Exception as exc:
                meta = {
                    "search_rank": rank,
                    "search_keyword": keyword,
                    "search_engine": url_source_map.get(url, "unknown"),
                }
                if is_fallback:
                    meta["fallback"] = True
                return CrawlResult(
                    success=False,
                    url=url,
                    error_message=str(exc),
                    search_rank=rank,
                    metadata=meta,
                )

    async with AsyncWebCrawler(config=browser_config) as crawler:
        tasks = [_crawl_one(rank, url) for rank, url in enumerate(urls, 1)]
        return list(await asyncio.gather(*tasks))


async def crawl_by_keyword(
    keyword: str,
    engine: str = "bing",
    max_results: int = 10,
    time_range: str = "week",
    config: Optional[object] = None,
) -> List[CrawlResult]:
    valid_time_ranges = {"day", "week", "month", "year", "all"}
    if time_range not in valid_time_ranges:
        raise ValueError(f"Invalid time_range '{time_range}'. Must be one of: {valid_time_ranges}")

    start_time = time.time()
    logger.info("[Search] Keyword: '%s', engine: %s, max_results=%s, time_range=%s", keyword, engine, max_results, time_range)

    engines_to_try = [engine]
    for current in ENGINE_PRIORITY:
        if current != engine and current not in engines_to_try:
            engines_to_try.append(current)

    url_set = set()
    all_search_urls = []
    url_source_map = {}
    tried_engines = []

    for idx, current_engine in enumerate(engines_to_try):
        try:
            logger.info("[Search] Trying engine '%s' for keyword: '%s'", current_engine, keyword)
            search_urls = await _get_search_results(keyword=keyword, engine=current_engine, max_results=max_results, time_range=time_range)
            tried_engines.append(current_engine)

            if search_urls:
                new_urls = [url for url in search_urls if url not in url_set]
                for url in new_urls:
                    url_set.add(url)
                    url_source_map[url] = current_engine
                all_search_urls.extend(new_urls)
                logger.info(
                    "[Search] Engine '%s' returned %s URLs (%s new, total unique=%s)",
                    current_engine,
                    len(search_urls),
                    len(new_urls),
                    len(all_search_urls),
                )
                if len(all_search_urls) >= max_results:
                    break
            else:
                logger.warning("[Search] Engine '%s' returned 0 results for '%s'", current_engine, keyword)
        except Exception as exc:
            logger.warning("[Search] Engine '%s' failed for '%s': %s", current_engine, keyword, exc)
            tried_engines.append(current_engine)

        if idx < len(engines_to_try) - 1:
            await asyncio.sleep(random.uniform(2.0, 5.0))

    if not all_search_urls:
        logger.error("[Search] All engines failed for keyword: '%s'. Tried: %s", keyword, tried_engines)
        return [
            CrawlResult(
                success=False,
                url="",
                error_message=f"No search results found for keyword: '{keyword}' (tried engines: {', '.join(tried_engines)})",
            )
        ]

    all_search_urls = all_search_urls[:max_results]
    logger.info("[Search] Total %s unique URLs from %s engine(s) for '%s'", len(all_search_urls), len(tried_engines), keyword)

    params = RunParams(config)
    browser_config = get_browser_config(text_mode=params.text_mode, light_mode=params.light_mode)
    results = await _crawl_urls_with_shared_browser(
        urls=all_search_urls,
        keyword=keyword,
        url_source_map=url_source_map,
        config=config,
        browser_config=browser_config,
    )

    try:
        deduped = dedup_results(results)
        removed = len(results) - len(deduped)
        if removed > 0:
            logger.info("[Search] Dedup removed %s duplicate results", removed)
        results = deduped
    except Exception as exc:
        logger.warning("[Search] Dedup failed: %s", exc)

    total_time = int((time.time() - start_time) * 1000)
    success_count = sum(1 for result in results if result.success)
    logger.info("[Search] Completed: %s/%s pages crawled, keyword='%s', time=%sms", success_count, len(results), keyword, total_time)
    return results
