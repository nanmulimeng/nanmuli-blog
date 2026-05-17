"""RSS/Atom feed parser for information source integration.

Fetches and parses RSS/Atom feeds, extracts article URLs with freshness filtering.
"""

import datetime
import logging
from dataclasses import dataclass
from urllib.parse import urljoin

import httpx

logger = logging.getLogger(__name__)


@dataclass
class FeedEntry:
    """Single entry extracted from an RSS/Atom feed."""
    url: str
    title: str
    published: datetime.datetime
    feed_url: str


def _parse_time_tuple(t) -> datetime.datetime | None:
    """Convert feedparser time tuple to datetime."""
    if not t or len(t) < 9:
        return None
    try:
        return datetime.datetime(*t[:6], tzinfo=datetime.timezone.utc)
    except (ValueError, TypeError, OverflowError):
        return None


async def parse_feed(
    feed_url: str,
    freshness_hours: int = 24,
    max_entries: int = 10,
    proxy: str = "",
) -> list[FeedEntry]:
    """Fetch and parse an RSS/Atom feed, returning entries within the freshness window.

    Args:
        feed_url: URL of the RSS/Atom feed.
        freshness_hours: Only return entries published within this many hours.
        max_entries: Maximum number of entries to return (newest first).
        proxy: Optional proxy URL for the HTTP request.

    Returns:
        List of FeedEntry sorted by publication date (newest first).
        Returns empty list on any error (non-fatal for digest pipeline).
    """
    import feedparser

    # Fetch feed XML via httpx (no browser needed for XML)
    try:
        client_kwargs = {"follow_redirects": True, "timeout": 15.0}
        if proxy:
            client_kwargs["proxy"] = proxy
        async with httpx.AsyncClient(**client_kwargs) as client:
            resp = await client.get(
                feed_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; FeedParser/6.0)",
                    "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
                },
            )
            resp.raise_for_status()
            raw_xml = resp.text
    except Exception as e:
        logger.warning("Feed fetch failed: url=%s error=%s", feed_url, e)
        return []

    if not raw_xml or len(raw_xml) < 50:
        logger.warning("Feed response too short: url=%s len=%d", feed_url, len(raw_xml) if raw_xml else 0)
        return []

    # Parse with feedparser
    try:
        feed = feedparser.parse(raw_xml)
    except Exception as e:
        logger.warning("Feed parse failed: url=%s error=%s", feed_url, e)
        return []

    if not feed.entries:
        logger.info("Feed has no entries: url=%s bozo=%s", feed_url, getattr(feed, "bozo", False))
        return []

    # Filter by freshness
    now = datetime.datetime.now(datetime.timezone.utc)
    cutoff = now - datetime.timedelta(hours=freshness_hours)
    entries: list[FeedEntry] = []

    no_date_entries: list[FeedEntry] = []
    for entry in feed.entries:
        # Extract publication time
        published = _parse_time_tuple(getattr(entry, "published_parsed", None))
        if published is None:
            published = _parse_time_tuple(getattr(entry, "updated_parsed", None))

        if published is None:
            # 无日期条目：保留作为"最近条目"，受 max_entries 上限约束
            link = getattr(entry, "link", "")
            if not link:
                continue
            url = urljoin(feed_url, link)
            if not url.startswith(("http://", "https://")):
                continue
            no_date_entries.append(FeedEntry(
                url=url,
                title=getattr(entry, "title", "") or "",
                published=now,  # 无日期视为最新
                feed_url=feed_url,
            ))
            continue

        # Freshness filter
        if published < cutoff:
            continue
        # 未来日期过滤（容差1小时，应对时区偏差）
        if published > now + datetime.timedelta(hours=1):
            continue

        # Extract and resolve URL
        link = getattr(entry, "link", "")
        if not link:
            continue
        url = urljoin(feed_url, link)
        if not url.startswith(("http://", "https://")):
            continue

        title = getattr(entry, "title", "") or ""

        entries.append(FeedEntry(
            url=url,
            title=title,
            published=published,
            feed_url=feed_url,
        ))

    # Merge no-date entries (capped to avoid stale content flooding), sort newest first
    no_date_cap = max(1, max_entries // 5)
    entries.extend(no_date_entries[:no_date_cap])
    entries.sort(key=lambda e: e.published, reverse=True)
    entries = entries[:max_entries]

    logger.info("Feed parsed: url=%s entries=%d (freshness=%dh, total_feed=%d)",
                feed_url, len(entries), freshness_hours, len(feed.entries))
    return entries
