"""metadata.py 单元测试

覆盖：
- OG 标签优先级
- Twitter Card 回退
- JSON-LD 结构化数据提取
- canonical URL / language 检测
- 时间标准化多种格式
- 空页面 / 无元数据页面
"""

import os
import sys
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from crawler.metadata import extract_metadata, _normalize_datetime


# ============== Helpers ==============

def _html(body: str = "", head: str = "") -> str:
    """快速构建 HTML 字符串"""
    return f"<html><head>{head}</head><body>{body}</body></html>"


def _meta(property_name: str, content: str) -> str:
    return f'<meta property="{property_name}" content="{content}"/>'


def _meta_name(name: str, content: str) -> str:
    return f'<meta name="{name}" content="{content}"/>'


# ============== 标题优先级 ==============

class TestTitlePriority:
    """og:title > twitter:title > <title>"""

    def test_og_title_takes_priority(self):
        html = _html(head=(
            _meta("og:title", "OG Title") +
            _meta_name("twitter:title", "Twitter Title") +
            "<title>Plain Title</title>"
        ))
        result = extract_metadata(html, "https://example.com")
        assert result["title"] == "OG Title"

    def test_twitter_title_when_no_og(self):
        html = _html(head=(
            _meta_name("twitter:title", "Twitter Title") +
            "<title>Plain Title</title>"
        ))
        result = extract_metadata(html, "https://example.com")
        assert result["title"] == "Twitter Title"

    def test_plain_title_when_no_meta(self):
        html = _html(head="<title>Plain Title</title>")
        result = extract_metadata(html, "https://example.com")
        assert result["title"] == "Plain Title"

    def test_no_title_at_all(self):
        html = _html()
        result = extract_metadata(html, "https://example.com")
        assert result["title"] is None


# ============== 描述优先级 ==============

class TestDescriptionPriority:
    """og:description > twitter:description > meta description"""

    def test_og_description_first(self):
        html = _html(head=(
            _meta("og:description", "OG Desc") +
            _meta_name("twitter:description", "Twitter Desc") +
            _meta_name("description", "Meta Desc")
        ))
        result = extract_metadata(html, "https://example.com")
        assert result["description"] == "OG Desc"

    def test_falls_back_to_meta_description(self):
        html = _html(head=_meta_name("description", "Meta Desc"))
        result = extract_metadata(html, "https://example.com")
        assert result["description"] == "Meta Desc"


# ============== 关键词 ==============

class TestKeywords:
    def test_keywords_split_by_comma(self):
        html = _html(head=_meta_name("keywords", "python, ai, crawler"))
        result = extract_metadata(html, "https://example.com")
        assert result["keywords"] == ["python", "ai", "crawler"]

    def test_no_keywords(self):
        html = _html()
        result = extract_metadata(html, "https://example.com")
        assert result["keywords"] is None


# ============== 作者 ==============

class TestAuthor:
    def test_meta_author(self):
        html = _html(head=_meta_name("author", "John Doe"))
        result = extract_metadata(html, "https://example.com")
        assert result["author"] == "John Doe"

    def test_jsonld_author_dict(self):
        html = _html(head="""
        <script type="application/ld+json">
        {"@type": "Article", "author": {"name": "Jane"}, "datePublished": "2024-01-01"}
        </script>
        """)
        result = extract_metadata(html, "https://example.com")
        assert result["author"] == "Jane"

    def test_jsonld_author_string(self):
        html = _html(head="""
        <script type="application/ld+json">
        {"@type": "BlogPosting", "author": "Bob", "datePublished": "2024-01-01"}
        </script>
        """)
        result = extract_metadata(html, "https://example.com")
        assert result["author"] == "Bob"


# ============== JSON-LD ==============

class TestJsonLd:
    def test_article_type(self):
        html = _html(head="""
        <script type="application/ld+json">
        {"@type": "Article", "headline": "Test", "datePublished": "2024-03-15"}
        </script>
        """)
        result = extract_metadata(html, "https://example.com")
        assert result["published_at"] is not None
        assert "2024-03-15" in result["published_at"]

    def test_graph_array_extraction(self):
        html = _html(head="""
        <script type="application/ld+json">
        {"@graph": [{"@type": "NewsArticle", "datePublished": "2024-06-01"}]}
        </script>
        """)
        result = extract_metadata(html, "https://example.com")
        assert "2024-06-01" in (result["published_at"] or "")

    def test_non_article_type_ignored(self):
        html = _html(head="""
        <script type="application/ld+json">
        {"@type": "Product", "name": "Widget"}
        </script>
        """)
        result = extract_metadata(html, "https://example.com")
        # Product type 不应填充 published_at
        assert result["published_at"] is None

    def test_malformed_jsonld_does_not_crash(self):
        html = _html(head="""
        <script type="application/ld+json">{invalid json}</script>
        """)
        result = extract_metadata(html, "https://example.com")
        # 不崩溃即可
        assert isinstance(result, dict)


# ============== 语言 & canonical ==============

class TestLanguageAndCanonical:
    def test_language_from_html_tag(self):
        html = '<html lang="zh-CN"><head></head><body></body></html>'
        result = extract_metadata(html, "https://example.com")
        assert result["language"] == "zh-CN"

    def test_canonical_url(self):
        html = _html(head='<link rel="canonical" href="https://example.com/post/1"/>')
        result = extract_metadata(html, "https://example.com")
        assert result["canonical_url"] == "https://example.com/post/1"

    def test_canonical_relative_url_resolved(self):
        html = _html(head='<link rel="canonical" href="/post/1"/>')
        result = extract_metadata(html, "https://example.com")
        assert result["canonical_url"] == "https://example.com/post/1"

    def test_no_language_no_canonical(self):
        html = _html()
        result = extract_metadata(html, "https://example.com")
        assert result["language"] is None
        assert result["canonical_url"] is None


# ============== 时间标准化 ==============

class TestNormalizeDatetime:
    def test_iso8601_with_timezone(self):
        result = _normalize_datetime("2024-01-15T10:30:00+08:00")
        assert result is not None
        assert "2024-01-15" in result

    def test_iso8601_utc(self):
        result = _normalize_datetime("2024-01-15T10:30:00Z")
        assert result is not None
        assert "2024-01-15" in result

    def test_date_only(self):
        result = _normalize_datetime("2024-01-15")
        assert result == "2024-01-15T00:00:00"

    def test_chinese_date(self):
        result = _normalize_datetime("2024年01月15日")
        assert result is not None
        assert "2024-01-15" in result

    def test_english_month_format(self):
        result = _normalize_datetime("January 15, 2024")
        assert result is not None
        assert "2024-01-15" in result

    def test_short_month_format(self):
        result = _normalize_datetime("Jan 15, 2024")
        assert result is not None
        assert "2024-01-15" in result

    def test_unparseable_returns_none(self):
        result = _normalize_datetime("not-a-date")
        assert result is None

    def test_empty_string_returns_none(self):
        result = _normalize_datetime("")
        assert result is None

    def test_none_returns_none(self):
        result = _normalize_datetime(None)
        assert result is None


# ============== 边界情况 ==============

class TestEdgeCases:
    def test_empty_html(self):
        result = extract_metadata("", "https://example.com")
        assert result["url"] == "https://example.com"
        assert result["title"] is None

    def test_soup_param_skips_parsing(self):
        from bs4 import BeautifulSoup
        soup = BeautifulSoup("<html><head><title>Cached</title></head></html>", "lxml")
        result = extract_metadata("", "https://example.com", soup=soup)
        assert result["title"] == "Cached"

    def test_time_tag_extraction(self):
        html = _html(body='<time datetime="2024-05-20">May 20</time>')
        result = extract_metadata(html, "https://example.com")
        assert result["published_at"] is not None
        assert "2024-05-20" in result["published_at"]
