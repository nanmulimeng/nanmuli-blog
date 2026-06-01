"""source_crawler.py 测试：crawl_url_sources / crawl_rss_sources

验证从 digest.py 迁出后的独立模块功能正确。
"""

from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta, timezone

import pytest


def _make_crawl_result(url="https://example.com", success=True, title="Test",
                       markdown="word " * 200, word_count=200):
    from crawler.models import CrawlResult
    return CrawlResult(
        success=success, url=url, title=title,
        markdown=markdown, word_count=word_count, metadata={},
    )


def _iso_days_ago(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


# ============== crawl_url_sources ==============


class TestCrawlUrlSources:

    @pytest.mark.asyncio
    async def test_single_mode_crawls_url(self):
        """single 模式调用 crawl_single_page"""
        result = _make_crawl_result(url="https://example.com/article")
        section = {
            "url_sources": [{"url": "https://example.com/article", "source_id": 1}],
            "max_items": 5,
        }
        with patch("crawler.single.crawl_single_page",
                   AsyncMock(return_value=result)):
            results = await self._run(section)

        assert len(results) == 1
        assert results[0].url == "https://example.com/article"
        assert results[0].metadata["source_id"] == 1

    @pytest.mark.asyncio
    async def test_deep_mode_crawls_deep(self):
        """crawl_mode=deep 调用 crawl_deep_pages"""
        pages = [_make_crawl_result(url=f"https://example.com/p{i}") for i in range(3)]
        section = {
            "url_sources": [{
                "url": "https://example.com",
                "crawl_mode": "deep",
                "max_depth": 2,
                "max_pages": 3,
                "source_name": "TestSource",
            }],
            "max_items": 5,
        }
        with patch("crawler.deep.crawl_deep_pages",
                   AsyncMock(return_value=pages)):
            results = await self._run(section)

        assert len(results) == 3
        assert all(r.metadata["source_name"] == "TestSource" for r in results)

    @pytest.mark.asyncio
    async def test_dead_source_skipped(self):
        """is_truly_dead 返回 True 时跳过该源"""
        section = {
            "url_sources": [{
                "url": "https://example.com/dead",
                "effectiveness": {"dead": True, "last_run_at": _iso_days_ago(1)},
            }],
            "max_items": 5,
        }
        with patch("crawler.single.crawl_single_page",
                   AsyncMock(return_value=_make_crawl_result())) as mock_single:
            results = await self._run(section)

        assert len(results) == 0
        mock_single.assert_not_called()

    @pytest.mark.asyncio
    async def test_excluded_url_source_skipped(self):
        section = {
            "url_sources": [{
                "url": "https://www.microsoft.com/en-us/software-download/?msockid=abc",
            }],
            "max_items": 5,
        }
        with patch("crawler.single.crawl_single_page",
                   AsyncMock(return_value=_make_crawl_result())) as mock_single:
            results = await self._run(section)

        assert results == []
        mock_single.assert_not_called()

    @pytest.mark.asyncio
    async def test_dead_source_retried_after_recovery_window(self):
        """dead 状态超过恢复窗口后允许重试。"""
        section = {
            "url_sources": [{
                "url": "https://example.com/retry",
                "effectiveness": {"dead": True, "last_run_at": _iso_days_ago(8)},
            }],
            "max_items": 5,
        }
        with patch("crawler.single.crawl_single_page",
                   AsyncMock(return_value=_make_crawl_result())) as mock_single:
            results = await self._run(section)

        assert len(results) == 1
        mock_single.assert_called_once()

    @pytest.mark.asyncio
    async def test_max_items_limits_sources(self):
        """max_items 限制实际爬取的源数量"""
        sources = [{"url": f"https://example.com/{i}"} for i in range(10)]
        section = {"url_sources": sources, "max_items": 3}
        with patch("crawler.single.crawl_single_page",
                   AsyncMock(return_value=_make_crawl_result())):
            results = await self._run(section)

        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_empty_url_skipped(self):
        """url 为空的源被跳过"""
        section = {
            "url_sources": [{"url": ""}, {"url": None}],
            "max_items": 5,
        }
        results = await self._run(section)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_crawl_failure_does_not_block(self):
        """单个源爬取失败不阻断其他源"""
        section = {
            "url_sources": [
                {"url": "https://fail.com"},
                {"url": "https://ok.com"},
            ],
            "max_items": 5,
        }
        call_count = 0

        async def mock_crawl(url, **kw):
            nonlocal call_count
            call_count += 1
            if "fail" in url:
                raise RuntimeError("Crawl failed")
            return _make_crawl_result(url=url)

        with patch("crawler.single.crawl_single_page", mock_crawl):
            results = await self._run(section)

        assert len(results) == 1
        assert results[0].url == "https://ok.com"

    async def _run(self, section):
        from crawler.source_crawler import crawl_url_sources
        return await crawl_url_sources(section, MagicMock(), MagicMock())


# ============== crawl_rss_sources ==============


class TestCrawlRssSources:

    @pytest.mark.asyncio
    async def test_rss_feed_parsed_and_crawled(self):
        """RSS feed 被解析后逐篇爬取"""
        from crawler.feed import FeedEntry
        from datetime import datetime, timezone

        entries = [
            FeedEntry(url="https://example.com/1", title="A1",
                      published=datetime.now(timezone.utc), feed_url="https://feed.xml"),
            FeedEntry(url="https://example.com/2", title="A2",
                      published=datetime.now(timezone.utc), feed_url="https://feed.xml"),
        ]
        section = {
            "rss_sources": [{"feed_url": "https://feed.xml", "source_id": 10}],
            "max_items": 5,
        }
        with patch("crawler.feed.parse_feed",
                   AsyncMock(return_value=entries)), \
             patch("crawler.single.crawl_single_page",
                   AsyncMock(return_value=_make_crawl_result())):
            results = await self._run(section)

        assert len(results) == 2
        assert all(r.metadata["source_id"] == 10 for r in results)

    @pytest.mark.asyncio
    async def test_empty_feed_returns_empty(self):
        """RSS feed 无条目时返回空"""
        section = {
            "rss_sources": [{"feed_url": "https://empty.xml"}],
            "max_items": 5,
        }
        with patch("crawler.feed.parse_feed", AsyncMock(return_value=[])):
            results = await self._run(section)

        assert results == []

    @pytest.mark.asyncio
    async def test_dead_rss_source_skipped(self):
        """is_truly_dead 返回 True 时跳过 RSS 源"""
        section = {
            "rss_sources": [{
                "feed_url": "https://dead.xml",
                "effectiveness": {"dead": True, "last_run_at": _iso_days_ago(1)},
            }],
            "max_items": 5,
        }
        with patch("crawler.feed.parse_feed",
                   AsyncMock(return_value=[])) as mock_parse:
            results = await self._run(section)

        assert results == []
        mock_parse.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_feed_url_skipped(self):
        """feed_url 为空时跳过"""
        section = {
            "rss_sources": [{"feed_url": ""}],
            "max_items": 5,
        }
        results = await self._run(section)
        assert results == []

    @pytest.mark.asyncio
    async def test_excluded_rss_entry_skipped(self):
        from crawler.feed import FeedEntry
        from datetime import datetime, timezone

        entries = [
            FeedEntry(
                url="https://github.blog/news-insights/company-news/still-a-developer-just-outside-our-latest-github-shop-collection-is-here/",
                title="Shop",
                published=datetime.now(timezone.utc),
                feed_url="https://feed.xml",
            ),
            FeedEntry(
                url="https://example.com/valid",
                title="Valid",
                published=datetime.now(timezone.utc),
                feed_url="https://feed.xml",
            ),
        ]
        section = {
            "rss_sources": [{"feed_url": "https://feed.xml"}],
            "max_items": 5,
        }
        with patch("crawler.feed.parse_feed",
                   AsyncMock(return_value=entries)), \
             patch("crawler.single.crawl_single_page",
                   AsyncMock(return_value=_make_crawl_result(url="https://example.com/valid"))) as mock_single:
            results = await self._run(section)

        assert len(results) == 1
        mock_single.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_feed_parse_failure_continues(self):
        """feed 解析失败不崩溃"""
        section = {
            "rss_sources": [{"feed_url": "https://bad.xml"}],
            "max_items": 5,
        }
        with patch("crawler.feed.parse_feed",
                   AsyncMock(side_effect=Exception("Parse error"))):
            results = await self._run(section)

        assert results == []

    @pytest.mark.asyncio
    async def test_feed_title_fallback(self):
        """crawl_single_page 返回无 title 时用 feed_entry.title 回填"""
        from crawler.feed import FeedEntry
        from datetime import datetime, timezone

        entries = [
            FeedEntry(url="https://example.com/1", title="Feed Title",
                      published=datetime.now(timezone.utc), feed_url="https://feed.xml"),
        ]
        no_title_result = _make_crawl_result()
        no_title_result.title = ""
        section = {
            "rss_sources": [{"feed_url": "https://feed.xml"}],
            "max_items": 5,
        }
        with patch("crawler.feed.parse_feed",
                   AsyncMock(return_value=entries)), \
             patch("crawler.single.crawl_single_page",
                   AsyncMock(return_value=no_title_result)):
            results = await self._run(section)

        assert len(results) == 1
        assert results[0].title == "Feed Title"
        assert results[0].metadata["feed_title"] == "Feed Title"

    async def _run(self, section):
        from crawler.source_crawler import crawl_rss_sources
        return await crawl_rss_sources(section, MagicMock(), MagicMock())
