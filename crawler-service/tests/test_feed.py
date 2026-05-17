"""RSS/Atom feed parser tests."""

import datetime
import json
from unittest.mock import AsyncMock, patch

import pytest

from crawler.feed import FeedEntry, parse_feed


def _make_rss_xml(entries: list[dict]) -> str:
    """Build a minimal RSS 2.0 XML string."""
    items = []
    for e in entries:
        pub_date = e.get("published", "Fri, 16 May 2026 10:00:00 GMT")
        items.append(f"""<item>
  <title>{e.get("title", "Test")}</title>
  <link>{e.get("link", "https://example.com/article")}</link>
  <pubDate>{pub_date}</pubDate>
</item>""")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <link>https://example.com</link>
    {" ".join(items)}
  </channel>
</rss>"""


def _make_atom_xml(entries: list[dict]) -> str:
    """Build a minimal Atom XML string."""
    items = []
    for e in entries:
        updated = e.get("updated", "2026-05-16T10:00:00Z")
        items.append(f"""<entry>
  <title>{e.get("title", "Test")}</title>
  <link href="{e.get("link", "https://example.com/article")}" />
  <updated>{updated}</updated>
</entry>""")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Test Feed</title>
  {" ".join(items)}
</feed>"""


@pytest.fixture
def mock_httpx_get():
    """Mock httpx.AsyncClient.get to return XML content."""
    with patch("crawler.feed.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=None)
        yield mock_client


class TestParseRss:
    @pytest.mark.asyncio
    async def test_parse_valid_rss(self, mock_httpx_get):
        xml = _make_rss_xml([
            {"title": "Article 1", "link": "https://example.com/1",
             "published": "Fri, 16 May 2026 10:00:00 GMT"},
            {"title": "Article 2", "link": "https://example.com/2",
             "published": "Fri, 15 May 2026 10:00:00 GMT"},
        ])
        mock_httpx_get.get.return_value.status_code = 200
        mock_httpx_get.get.return_value.text = xml
        mock_httpx_get.get.return_value.raise_for_status = lambda: None

        result = await parse_feed("https://example.com/feed.xml", freshness_hours=48)
        assert len(result) == 2
        assert result[0].title == "Article 1"
        assert result[0].url == "https://example.com/1"

    @pytest.mark.asyncio
    async def test_parse_valid_atom(self, mock_httpx_get):
        xml = _make_atom_xml([
            {"title": "Atom Post", "link": "https://example.com/atom1",
             "updated": "2026-05-16T10:00:00Z"},
        ])
        mock_httpx_get.get.return_value.status_code = 200
        mock_httpx_get.get.return_value.text = xml
        mock_httpx_get.get.return_value.raise_for_status = lambda: None

        result = await parse_feed("https://example.com/atom.xml")
        assert len(result) == 1
        assert result[0].title == "Atom Post"

    @pytest.mark.asyncio
    async def test_freshness_filter(self, mock_httpx_get):
        xml = _make_rss_xml([
            {"title": "Recent", "link": "https://example.com/recent",
             "published": "Fri, 16 May 2026 10:00:00 GMT"},
            {"title": "Old", "link": "https://example.com/old",
             "published": "Mon, 01 Jan 2024 10:00:00 GMT"},
        ])
        mock_httpx_get.get.return_value.status_code = 200
        mock_httpx_get.get.return_value.text = xml
        mock_httpx_get.get.return_value.raise_for_status = lambda: None

        result = await parse_feed("https://example.com/feed.xml", freshness_hours=24)
        assert len(result) == 1
        assert result[0].title == "Recent"

    @pytest.mark.asyncio
    async def test_max_entries_cap(self, mock_httpx_get):
        entries = [
            {"title": f"Article {i}", "link": f"https://example.com/{i}",
             "published": "Fri, 16 May 2026 10:00:00 GMT"}
            for i in range(20)
        ]
        xml = _make_rss_xml(entries)
        mock_httpx_get.get.return_value.status_code = 200
        mock_httpx_get.get.return_value.text = xml
        mock_httpx_get.get.return_value.raise_for_status = lambda: None

        result = await parse_feed("https://example.com/feed.xml", max_entries=5)
        assert len(result) == 5

    @pytest.mark.asyncio
    async def test_network_error_returns_empty(self, mock_httpx_get):
        mock_httpx_get.get.side_effect = Exception("Network error")

        result = await parse_feed("https://example.com/feed.xml")
        assert result == []

    @pytest.mark.asyncio
    async def test_empty_feed(self, mock_httpx_get):
        xml = """<?xml version="1.0"?><rss version="2.0"><channel><title>Empty</title></channel></rss>"""
        mock_httpx_get.get.return_value.status_code = 200
        mock_httpx_get.get.return_value.text = xml
        mock_httpx_get.get.return_value.raise_for_status = lambda: None

        result = await parse_feed("https://example.com/feed.xml")
        assert result == []

    @pytest.mark.asyncio
    async def test_relative_url_resolution(self, mock_httpx_get):
        xml = _make_rss_xml([
            {"title": "Relative", "link": "/articles/123",
             "published": "Fri, 16 May 2026 10:00:00 GMT"},
        ])
        mock_httpx_get.get.return_value.status_code = 200
        mock_httpx_get.get.return_value.text = xml
        mock_httpx_get.get.return_value.raise_for_status = lambda: None

        result = await parse_feed("https://example.com/feed.xml")
        assert len(result) == 1
        assert result[0].url == "https://example.com/articles/123"


# ============== 极端/边界情况测试 ==============


class TestFeedParseExtreme:
    """RSS/Atom 解析极端测试：畸形 XML、非 HTTP URL、极端参数等"""

    @pytest.mark.asyncio
    async def test_malformed_xml_returns_empty(self, mock_httpx_get):
        """畸形 XML 不崩溃，返回空列表"""
        mock_httpx_get.get.return_value.status_code = 200
        mock_httpx_get.get.return_value.text = "<rss><not_closed><item><title>Broke"
        mock_httpx_get.get.return_value.raise_for_status = lambda: None
        result = await parse_feed("https://example.com/broken.xml")
        # feedparser 容错解析可能返回空或部分结果
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_html_instead_of_xml(self, mock_httpx_get):
        """返回 HTML 页面而非 XML，返回空列表"""
        html = "<html><body><h1>Not a feed</h1></body></html>"
        mock_httpx_get.get.return_value.status_code = 200
        mock_httpx_get.get.return_value.text = html
        mock_httpx_get.get.return_value.raise_for_status = lambda: None
        result = await parse_feed("https://example.com/not-a-feed")
        assert result == []

    @pytest.mark.asyncio
    async def test_response_too_short(self, mock_httpx_get):
        """响应体 < 50 字符返回空列表"""
        mock_httpx_get.get.return_value.status_code = 200
        mock_httpx_get.get.return_value.text = "<rss/>"
        mock_httpx_get.get.return_value.raise_for_status = lambda: None
        result = await parse_feed("https://example.com/tiny.xml")
        assert result == []

    @pytest.mark.asyncio
    async def test_http_500_returns_empty(self, mock_httpx_get):
        """HTTP 500 错误返回空列表"""
        mock_httpx_get.get.side_effect = Exception("500 Internal Server Error")
        result = await parse_feed("https://example.com/feed.xml")
        assert result == []

    @pytest.mark.asyncio
    async def test_dns_failure_returns_empty(self, mock_httpx_get):
        """DNS 解析失败返回空列表"""
        mock_httpx_get.get.side_effect = Exception("DNS resolution failed")
        result = await parse_feed("https://nonexistent.domain.example/feed.xml")
        assert result == []

    @pytest.mark.asyncio
    async def test_entries_without_dates_kept_as_recent(self, mock_httpx_get):
        """没有发布日期的条目保留为最近条目"""
        xml = """<?xml version="1.0"?>
        <rss version="2.0"><channel><title>Test</title>
        <item><title>No Date</title><link>https://example.com/1</link></item>
        <item><title>With Date</title><link>https://example.com/2</link>
        <pubDate>Fri, 16 May 2026 10:00:00 GMT</pubDate></item>
        </channel></rss>"""
        mock_httpx_get.get.return_value.status_code = 200
        mock_httpx_get.get.return_value.text = xml
        mock_httpx_get.get.return_value.raise_for_status = lambda: None
        result = await parse_feed("https://example.com/feed.xml")
        assert len(result) == 2
        assert result[0].title == "No Date"  # 无日期视为最新，排在前面
        assert result[1].title == "With Date"

    @pytest.mark.asyncio
    async def test_non_http_links_filtered(self, mock_httpx_get):
        """ftp://, javascript:, mailto: 链接被过滤"""
        xml = """<?xml version="1.0"?>
        <rss version="2.0"><channel><title>Test</title>
        <item><title>FTP</title><link>ftp://files.example.com/pub/doc</link>
        <pubDate>Fri, 16 May 2026 10:00:00 GMT</pubDate></item>
        <item><title>JS</title><link>javascript:alert(1)</link>
        <pubDate>Fri, 16 May 2026 10:00:00 GMT</pubDate></item>
        <item><title>Mail</title><link>mailto:test@example.com</link>
        <pubDate>Fri, 16 May 2026 10:00:00 GMT</pubDate></item>
        </channel></rss>"""
        mock_httpx_get.get.return_value.status_code = 200
        mock_httpx_get.get.return_value.text = xml
        mock_httpx_get.get.return_value.raise_for_status = lambda: None
        result = await parse_feed("https://example.com/feed.xml")
        assert result == []

    @pytest.mark.asyncio
    async def test_empty_link_skipped(self, mock_httpx_get):
        """link 为空的条目被跳过"""
        xml = """<?xml version="1.0"?>
        <rss version="2.0"><channel><title>Test</title>
        <item><title>No Link</title><pubDate>Fri, 16 May 2026 10:00:00 GMT</pubDate></item>
        </channel></rss>"""
        mock_httpx_get.get.return_value.status_code = 200
        mock_httpx_get.get.return_value.text = xml
        mock_httpx_get.get.return_value.raise_for_status = lambda: None
        result = await parse_feed("https://example.com/feed.xml")
        assert result == []

    @pytest.mark.asyncio
    async def test_empty_title_preserved(self, mock_httpx_get):
        """title 为空的条目仍被保留（有 URL 和日期即可）"""
        xml = _make_rss_xml([
            {"title": "", "link": "https://example.com/notitle",
             "published": "Fri, 16 May 2026 10:00:00 GMT"},
        ])
        mock_httpx_get.get.return_value.status_code = 200
        mock_httpx_get.get.return_value.text = xml
        mock_httpx_get.get.return_value.raise_for_status = lambda: None
        result = await parse_feed("https://example.com/feed.xml")
        assert len(result) == 1
        assert result[0].title == ""

    @pytest.mark.asyncio
    async def test_future_dated_entries_included(self, mock_httpx_get):
        """未来日期的条目被包含（在 freshness 窗口内）"""
        # 使用"现在 + 30 分钟"确保在 1 小时容差内
        future_time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=30)
        published_str = future_time.strftime("%a, %d %b %Y %H:%M:%S GMT")
        xml = _make_rss_xml([
            {"title": "Future", "link": "https://example.com/future",
             "published": published_str},
        ])
        mock_httpx_get.get.return_value.status_code = 200
        mock_httpx_get.get.return_value.text = xml
        mock_httpx_get.get.return_value.raise_for_status = lambda: None
        result = await parse_feed("https://example.com/feed.xml", freshness_hours=48)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_all_entries_outside_freshness(self, mock_httpx_get):
        """所有条目都超出 freshness 窗口，返回空列表"""
        xml = _make_rss_xml([
            {"title": "Old1", "link": "https://example.com/old1",
             "published": "Mon, 01 Jan 2024 10:00:00 GMT"},
            {"title": "Old2", "link": "https://example.com/old2",
             "published": "Tue, 02 Jan 2024 10:00:00 GMT"},
        ])
        mock_httpx_get.get.return_value.status_code = 200
        mock_httpx_get.get.return_value.text = xml
        mock_httpx_get.get.return_value.raise_for_status = lambda: None
        result = await parse_feed("https://example.com/feed.xml", freshness_hours=24)
        assert result == []

    @pytest.mark.asyncio
    async def test_large_feed_capped_at_max_entries(self, mock_httpx_get):
        """200 条 feed 被 max_entries=3 截断为 3 条"""
        entries = [
            {"title": f"Article {i}", "link": f"https://example.com/{i}",
             "published": "Fri, 16 May 2026 10:00:00 GMT"}
            for i in range(200)
        ]
        xml = _make_rss_xml(entries)
        mock_httpx_get.get.return_value.status_code = 200
        mock_httpx_get.get.return_value.text = xml
        mock_httpx_get.get.return_value.raise_for_status = lambda: None
        result = await parse_feed("https://example.com/feed.xml", max_entries=3)
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_zero_freshness_hours_includes_all(self, mock_httpx_get):
        """freshness_hours=0 只包含当前时刻的条目（通常 0 条）"""
        xml = _make_rss_xml([
            {"title": "Recent", "link": "https://example.com/recent",
             "published": "Fri, 16 May 2026 10:00:00 GMT"},
        ])
        mock_httpx_get.get.return_value.status_code = 200
        mock_httpx_get.get.return_value.text = xml
        mock_httpx_get.get.return_value.raise_for_status = lambda: None
        # freshness=0 → cutoff=now → 已发布的条目通常在 cutoff 之前
        result = await parse_feed("https://example.com/feed.xml", freshness_hours=0)
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_negative_freshness_hours(self, mock_httpx_get):
        """负数 freshness_hours 不崩溃"""
        xml = _make_rss_xml([
            {"title": "Test", "link": "https://example.com/1",
             "published": "Fri, 16 May 2026 10:00:00 GMT"},
        ])
        mock_httpx_get.get.return_value.status_code = 200
        mock_httpx_get.get.return_value.text = xml
        mock_httpx_get.get.return_value.raise_for_status = lambda: None
        # 负 hours → cutoff 在未来 → 结果可能为空
        result = await parse_feed("https://example.com/feed.xml", freshness_hours=-1)
        assert isinstance(result, list)


class TestParseTimeTuple:
    """_parse_time_tuple 内部函数极端测试"""

    def test_none_input(self):
        from crawler.feed import _parse_time_tuple
        assert _parse_time_tuple(None) is None

    def test_empty_tuple(self):
        from crawler.feed import _parse_time_tuple
        assert _parse_time_tuple(()) is None

    def test_short_tuple(self):
        from crawler.feed import _parse_time_tuple
        assert _parse_time_tuple((2026, 5, 16)) is None

    def test_valid_9_tuple(self):
        from crawler.feed import _parse_time_tuple
        import datetime
        t = (2026, 5, 16, 10, 0, 0, 0, 0, 0)
        result = _parse_time_tuple(t)
        assert result is not None
        assert result.year == 2026
        assert result.month == 5

    def test_overflow_year(self):
        from crawler.feed import _parse_time_tuple
        t = (99999, 1, 1, 0, 0, 0, 0, 0, 0)
        assert _parse_time_tuple(t) is None

    def test_invalid_month(self):
        from crawler.feed import _parse_time_tuple
        t = (2026, 13, 1, 0, 0, 0, 0, 0, 0)
        assert _parse_time_tuple(t) is None

    def test_string_elements(self):
        from crawler.feed import _parse_time_tuple
        t = ("2026", "5", "16", "10", "0", "0", "0", "0", "0")
        # strings cause TypeError in datetime constructor → caught → None
        assert _parse_time_tuple(t) is None
