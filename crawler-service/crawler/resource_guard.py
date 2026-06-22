"""Process-wide resource guards for browser-heavy crawler operations."""

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass

from config import settings


@dataclass
class _BrowserCrawlLimiter:
    limit: int
    semaphore: asyncio.Semaphore


_browser_crawl_limiter: _BrowserCrawlLimiter | None = None


def _configured_browser_crawl_limit() -> int:
    try:
        return max(1, int(settings.max_concurrent_crawls))
    except Exception:
        return 1


def _get_browser_crawl_limiter() -> _BrowserCrawlLimiter:
    global _browser_crawl_limiter
    limit = _configured_browser_crawl_limit()
    if _browser_crawl_limiter is None or _browser_crawl_limiter.limit != limit:
        _browser_crawl_limiter = _BrowserCrawlLimiter(
            limit=limit,
            semaphore=asyncio.Semaphore(limit),
        )
    return _browser_crawl_limiter


@asynccontextmanager
async def browser_crawl_slot():
    """Limit concurrent crawl4ai/Playwright page work across the process."""
    limiter = _get_browser_crawl_limiter()
    async with limiter.semaphore:
        yield


def reset_browser_crawl_limiter_for_tests() -> None:
    global _browser_crawl_limiter
    _browser_crawl_limiter = None
