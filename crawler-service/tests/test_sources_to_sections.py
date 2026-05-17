"""Tests for _sources_to_sections() source type grouping."""

import pytest

from standalone.task_executor import _sources_to_sections


class TestKeywordOnlySources:
    def test_single_keyword_source(self):
        sources = [{"type": "keyword", "value": "Rust", "contentCategory": "open_source", "freshnessHours": 168}]
        sections = _sources_to_sections(sources)
        assert len(sections) == 1
        assert sections[0]["name"] == "open_source"
        assert sections[0]["keyword"] == "Rust"
        assert sections[0]["source_type"] == "keyword"
        assert "url_sources" not in sections[0]
        assert "rss_sources" not in sections[0]

    def test_multiple_keywords_same_category(self):
        sources = [
            {"type": "keyword", "value": "Rust", "contentCategory": "open_source"},
            {"type": "keyword", "value": "Go 语言", "contentCategory": "open_source"},
        ]
        sections = _sources_to_sections(sources)
        assert len(sections) == 1
        assert "Rust" in sections[0]["keyword"]
        assert "Go" in sections[0]["keyword"]
        assert " OR " in sections[0]["keyword"]

    def test_different_categories(self):
        sources = [
            {"type": "keyword", "value": "AI", "contentCategory": "hot_trend"},
            {"type": "keyword", "value": "Rust", "contentCategory": "open_source"},
        ]
        sections = _sources_to_sections(sources)
        assert len(sections) == 2
        names = {s["name"] for s in sections}
        assert names == {"hot_trend", "open_source"}


class TestUrlSources:
    def test_single_url_source(self):
        sources = [{
            "type": "url", "value": "https://github.blog",
            "contentCategory": "hot_trend",
            "crawlMode": "single", "maxDepth": 1, "maxPages": 5,
        }]
        sections = _sources_to_sections(sources)
        assert len(sections) == 1
        assert sections[0]["source_type"] == "url"
        assert "url_sources" in sections[0]
        assert len(sections[0]["url_sources"]) == 1
        assert sections[0]["url_sources"][0]["url"] == "https://github.blog"
        assert sections[0]["url_sources"][0]["crawl_mode"] == "single"

    def test_deep_crawl_mode(self):
        sources = [{
            "type": "url", "value": "https://docs.python.org/3/",
            "contentCategory": "tech_article",
            "crawlMode": "deep", "maxDepth": 2, "maxPages": 15,
        }]
        sections = _sources_to_sections(sources)
        assert sections[0]["url_sources"][0]["crawl_mode"] == "deep"
        assert sections[0]["url_sources"][0]["max_depth"] == 2
        assert sections[0]["url_sources"][0]["max_pages"] == 15

    def test_multiple_url_sources_same_category(self):
        sources = [
            {"type": "url", "value": "https://github.blog", "contentCategory": "hot_trend",
             "crawlMode": "single", "maxDepth": 1, "maxPages": 5},
            {"type": "url", "value": "https://infoq.com", "contentCategory": "hot_trend",
             "crawlMode": "single", "maxDepth": 1, "maxPages": 3},
        ]
        sections = _sources_to_sections(sources)
        assert len(sections) == 1
        assert len(sections[0]["url_sources"]) == 2


class TestRssSources:
    def test_single_rss_source(self):
        sources = [{
            "type": "rss", "value": "https://hnrss.org/newest",
            "contentCategory": "hot_trend", "freshnessHours": 24,
        }]
        sections = _sources_to_sections(sources)
        assert len(sections) == 1
        assert sections[0]["source_type"] == "rss"
        assert "rss_sources" in sections[0]
        assert sections[0]["rss_sources"][0]["feed_url"] == "https://hnrss.org/newest"
        assert sections[0]["rss_sources"][0]["freshness_hours"] == 24


class TestMixedSources:
    def test_keyword_and_url_same_category(self):
        sources = [
            {"type": "keyword", "value": "AI", "contentCategory": "hot_trend"},
            {"type": "url", "value": "https://github.blog", "contentCategory": "hot_trend",
             "crawlMode": "single", "maxDepth": 1, "maxPages": 5},
        ]
        sections = _sources_to_sections(sources)
        assert len(sections) == 1
        assert sections[0]["source_type"] == "mixed"
        assert sections[0]["keyword"] == "AI"
        assert len(sections[0]["url_sources"]) == 1

    def test_keyword_and_rss_same_category(self):
        sources = [
            {"type": "keyword", "value": "开源", "contentCategory": "open_source"},
            {"type": "rss", "value": "https://changelog.com/feed", "contentCategory": "open_source",
             "freshnessHours": 48},
        ]
        sections = _sources_to_sections(sources)
        assert len(sections) == 1
        assert sections[0]["source_type"] == "mixed"
        assert "keyword" in sections[0]
        assert "rss_sources" in sections[0]

    def test_all_three_types_same_category(self):
        sources = [
            {"type": "keyword", "value": "Python", "contentCategory": "tech_article"},
            {"type": "url", "value": "https://docs.python.org/3/", "contentCategory": "tech_article",
             "crawlMode": "deep", "maxDepth": 2, "maxPages": 10},
            {"type": "rss", "value": "https://planetpython.org/rss20.xml", "contentCategory": "tech_article",
             "freshnessHours": 48},
        ]
        sections = _sources_to_sections(sources)
        assert len(sections) == 1
        assert sections[0]["source_type"] == "mixed"
        assert "keyword" in sections[0]
        assert len(sections[0]["url_sources"]) == 1
        assert len(sections[0]["rss_sources"]) == 1


class TestDefaults:
    def test_default_category(self):
        sources = [{"type": "keyword", "value": "test"}]
        sections = _sources_to_sections(sources)
        assert sections[0]["name"] == "tech_article"

    def test_default_crawl_params(self):
        sources = [{"type": "url", "value": "https://example.com"}]
        sections = _sources_to_sections(sources)
        src = sections[0]["url_sources"][0]
        assert src["crawl_mode"] == "single"
        assert src["max_depth"] == 1
        assert src["max_pages"] == 10

    def test_default_freshness(self):
        sources = [{"type": "rss", "value": "https://example.com/feed"}]
        sections = _sources_to_sections(sources)
        assert sections[0]["rss_sources"][0]["freshness_hours"] == 24

    def test_empty_sources(self):
        assert _sources_to_sections([]) == []

    def test_backward_compatible_keyword_sections(self):
        """旧版 keyword-only 配置应无 source_type 字段也能正常工作。"""
        sources = [{"type": "keyword", "value": "test", "contentCategory": "tech_article"}]
        sections = _sources_to_sections(sources)
        assert sections[0]["source_type"] == "keyword"


# ============== 极端/边界情况测试 ==============


class TestSourceEdgeCases:
    """信息源转换极端测试：未知类型、缺失字段、极端参数等"""

    def test_unknown_type_skipped(self):
        """type=unknown 不产生 keyword/url/rss 条目，被跳过"""
        sources = [{"type": "unknown", "value": "test", "contentCategory": "tech_article"}]
        sections = _sources_to_sections(sources)
        # unknown type 不会添加到任何分组 → 空组 → 空 sections
        assert sections == []

    def test_missing_value_field_raises(self):
        """缺少 value 字段时 keyword 类型应抛 KeyError"""
        sources = [{"type": "keyword", "contentCategory": "tech_article"}]
        # keyword 分支访问 src["value"]，缺失应 KeyError
        with pytest.raises(KeyError):
            _sources_to_sections(sources)

    def test_empty_content_category_defaults(self):
        """contentCategory 为空字符串时默认为 tech_article"""
        sources = [{"type": "keyword", "value": "test", "contentCategory": ""}]
        sections = _sources_to_sections(sources)
        assert sections[0]["name"] == "tech_article"

    def test_none_content_category_defaults(self):
        """contentCategory 为 None 时默认为 tech_article"""
        sources = [{"type": "keyword", "value": "test", "contentCategory": None}]
        sections = _sources_to_sections(sources)
        assert sections[0]["name"] == "tech_article"

    def test_missing_type_defaults_to_keyword(self):
        """缺少 type 字段默认为 keyword"""
        sources = [{"value": "Rust", "contentCategory": "open_source"}]
        sections = _sources_to_sections(sources)
        assert sections[0]["source_type"] == "keyword"
        assert sections[0]["keyword"] == "Rust"

    def test_negative_freshness_hours(self):
        """负数 freshnessHours 不崩溃"""
        sources = [{"type": "rss", "value": "https://example.com/feed",
                     "contentCategory": "hot_trend", "freshnessHours": -10}]
        sections = _sources_to_sections(sources)
        assert len(sections) == 1
        assert sections[0]["rss_sources"][0]["freshness_hours"] == -10

    def test_zero_max_pages(self):
        """maxPages=0 的 URL 源不崩溃"""
        sources = [{"type": "url", "value": "https://example.com",
                     "contentCategory": "hot_trend", "maxPages": 0}]
        sections = _sources_to_sections(sources)
        assert sections[0]["url_sources"][0]["max_pages"] == 0

    def test_very_large_max_pages(self):
        """极大 maxPages 不崩溃"""
        sources = [{"type": "url", "value": "https://example.com",
                     "contentCategory": "hot_trend", "maxPages": 999999}]
        sections = _sources_to_sections(sources)
        assert sections[0]["url_sources"][0]["max_pages"] == 999999

    def test_many_sources_same_category(self):
        """50 个同分类源合并为 1 个 section"""
        sources = [
            {"type": "keyword", "value": f"keyword_{i}", "contentCategory": "hot_trend"}
            for i in range(50)
        ]
        sections = _sources_to_sections(sources)
        assert len(sections) == 1
        assert " OR " in sections[0]["keyword"]
        # 50 个关键词用 OR 连接
        assert sections[0]["keyword"].count(" OR ") == 49

    def test_mixed_types_preserve_all(self):
        """同一分类的 keyword + url + rss 混合源全部保留"""
        sources = [
            {"type": "keyword", "value": "AI", "contentCategory": "tech"},
            {"type": "url", "value": "https://example.com", "contentCategory": "tech",
             "crawlMode": "single", "maxDepth": 1, "maxPages": 5},
            {"type": "rss", "value": "https://example.com/feed", "contentCategory": "tech",
             "freshnessHours": 48},
        ]
        sections = _sources_to_sections(sources)
        assert len(sections) == 1
        s = sections[0]
        assert s["source_type"] == "mixed"
        assert s["keyword"] == "AI"
        assert len(s["url_sources"]) == 1
        assert len(s["rss_sources"]) == 1

    def test_unicode_keyword(self):
        """Unicode 关键词不崩溃"""
        sources = [
            {"type": "keyword", "value": "Docker 🐳 컨테이ナー コンテナ", "contentCategory": "tech"},
        ]
        sections = _sources_to_sections(sources)
        assert "🐳" in sections[0]["keyword"]

    def test_url_with_unicode_path(self):
        """含 Unicode 路径的 URL 源不崩溃"""
        sources = [
            {"type": "url", "value": "https://example.com/技术/文章", "contentCategory": "tech"},
        ]
        sections = _sources_to_sections(sources)
        assert sections[0]["url_sources"][0]["url"] == "https://example.com/技术/文章"


class TestFreshnessToTimeRange:
    """_freshness_to_time_range 边界测试"""

    def test_zero_hours(self):
        from standalone.task_executor import _freshness_to_time_range
        assert _freshness_to_time_range(0) == "day"

    def test_exact_24_hours(self):
        from standalone.task_executor import _freshness_to_time_range
        assert _freshness_to_time_range(24) == "day"

    def test_25_hours_is_week(self):
        from standalone.task_executor import _freshness_to_time_range
        assert _freshness_to_time_range(25) == "week"

    def test_exact_168_hours(self):
        from standalone.task_executor import _freshness_to_time_range
        assert _freshness_to_time_range(168) == "week"

    def test_169_hours_is_month(self):
        from standalone.task_executor import _freshness_to_time_range
        assert _freshness_to_time_range(169) == "month"

    def test_exact_720_hours(self):
        from standalone.task_executor import _freshness_to_time_range
        assert _freshness_to_time_range(720) == "month"

    def test_721_hours_is_year(self):
        from standalone.task_executor import _freshness_to_time_range
        assert _freshness_to_time_range(721) == "year"

    def test_negative_hours(self):
        from standalone.task_executor import _freshness_to_time_range
        # 负数 ≤ 24 → "day"
        assert _freshness_to_time_range(-1) == "day"

    def test_very_large_hours(self):
        from standalone.task_executor import _freshness_to_time_range
        assert _freshness_to_time_range(87600) == "year"
