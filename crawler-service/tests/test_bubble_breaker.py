"""信息茧房突破模块测试"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from optimization.bubble_breaker import BubbleBreaker
from optimization.evaluator import CoverageEvaluator


def _make_result(url, title="", success=True, content_len=500):
    return {
        "url": url,
        "title": title,
        "markdown": "x" * content_len,
        "success": success,
        "metadata": {},
    }


# ============== _needs_cross_language ==============

class TestNeedsCrossLanguage:

    def test_chinese_only_titles(self):
        breaker = BubbleBreaker()
        results = [
            _make_result("https://a.com/1", "入门教程详解"),
            _make_result("https://b.com/2", "容器化部署指南"),
            _make_result("https://c.com/3", "微服务架构设计"),
        ]
        assert breaker._needs_cross_language(results) is True

    def test_mixed_titles(self):
        breaker = BubbleBreaker()
        results = [
            _make_result("https://a.com/1", "Spring Boot 入门教程"),
            _make_result("https://b.com/2", "Docker best practices"),
            _make_result("https://c.com/3", "微服务 architecture design"),
        ]
        assert breaker._needs_cross_language(results) is False

    def test_english_only_titles(self):
        breaker = BubbleBreaker()
        results = [
            _make_result("https://a.com/1", "Spring Boot tutorial"),
            _make_result("https://b.com/2", "Docker deployment guide"),
        ]
        assert breaker._needs_cross_language(results) is True

    def test_empty_results(self):
        breaker = BubbleBreaker()
        assert breaker._needs_cross_language([]) is False

    def test_failed_results_excluded(self):
        breaker = BubbleBreaker()
        results = [
            _make_result("https://a.com/1", "Spring Boot 入门教程", success=False),
        ]
        assert breaker._needs_cross_language(results) is False


# ============== translate_keyword ==============

class TestTranslateKeyword:

    @pytest.mark.asyncio
    async def test_translate_success(self):
        organizer = MagicMock()
        organizer.is_available = True
        organizer._call_ai = AsyncMock(return_value={
            "content": "Spring Boot tutorial",
            "total_tokens": 50,
        })
        breaker = BubbleBreaker(organizer=organizer)
        result = await breaker.translate_keyword("Spring Boot 入门教程")
        assert result == "Spring Boot tutorial"

    @pytest.mark.asyncio
    async def test_translate_no_organizer(self):
        breaker = BubbleBreaker(organizer=None)
        result = await breaker.translate_keyword("Spring Boot 入门")
        assert result is None

    @pytest.mark.asyncio
    async def test_translate_organizer_unavailable(self):
        organizer = MagicMock()
        organizer.is_available = False
        breaker = BubbleBreaker(organizer=organizer)
        result = await breaker.translate_keyword("Spring Boot 入门")
        assert result is None

    @pytest.mark.asyncio
    async def test_translate_same_as_original(self):
        organizer = MagicMock()
        organizer.is_available = True
        organizer._call_ai = AsyncMock(return_value={
            "content": "Spring Boot",
            "total_tokens": 10,
        })
        breaker = BubbleBreaker(organizer=organizer)
        result = await breaker.translate_keyword("Spring Boot")
        assert result is None

    @pytest.mark.asyncio
    async def test_translate_failure_silent(self):
        organizer = MagicMock()
        organizer.is_available = True
        organizer._call_ai = AsyncMock(side_effect=Exception("API error"))
        breaker = BubbleBreaker(organizer=organizer)
        result = await breaker.translate_keyword("Spring Boot 入门")
        assert result is None


# ============== check_and_expand ==============

class TestCheckAndExpand:

    @pytest.mark.asyncio
    async def test_disabled_returns_original(self):
        breaker = BubbleBreaker()
        results = [_make_result("https://a.com/1", "Spring Boot 入门")]
        with patch("optimization.bubble_breaker.settings") as mock_settings:
            mock_settings.bubble_breaker_enabled = False
            output = await breaker.check_and_expand("test", results, AsyncMock(), {})
        assert output == results

    @pytest.mark.asyncio
    async def test_adds_cross_language_results(self):
        organizer = MagicMock()
        organizer.is_available = True
        organizer._call_ai = AsyncMock(return_value={
            "content": "Spring Boot tutorial",
            "total_tokens": 50,
        })
        breaker = BubbleBreaker(organizer=organizer)

        chinese_results = [
            _make_result("https://cn1.com/1", "入门教程详解"),
            _make_result("https://cn2.com/2", "配置详解指南"),
        ]

        async def mock_crawl(**kwargs):
            return [
                _make_result("https://en1.com/1", "Spring Boot Tutorial Guide"),
                _make_result("https://en2.com/2", "Spring Boot Best Practices"),
            ]

        with patch("optimization.bubble_breaker.settings") as mock_settings:
            mock_settings.bubble_breaker_enabled = True
            mock_settings.bubble_cross_language = True
            output = await breaker.check_and_expand(
                "Spring Boot 入门", chinese_results, mock_crawl,
                {"engine": "bing", "time_range": "week"},
            )

        assert len(output) == 4
        urls = [r["url"] for r in output]
        assert "https://en1.com/1" in urls
        assert "https://en2.com/2" in urls

    @pytest.mark.asyncio
    async def test_skips_when_language_already_mixed(self):
        breaker = BubbleBreaker()

        mixed_results = [
            _make_result("https://a.com/1", "Spring Boot 入门教程"),
            _make_result("https://b.com/2", "Docker best practices"),
        ]

        crawl_fn = AsyncMock(return_value=[_make_result("https://new.com/1", "New")])

        with patch("optimization.bubble_breaker.settings") as mock_settings:
            mock_settings.bubble_breaker_enabled = True
            mock_settings.bubble_cross_language = True
            output = await breaker.check_and_expand(
                "test", mixed_results, crawl_fn, {"engine": "bing"},
            )

        assert len(output) == 2
        crawl_fn.assert_not_called()

    @pytest.mark.asyncio
    async def test_dedup_urls(self):
        organizer = MagicMock()
        organizer.is_available = True
        organizer._call_ai = AsyncMock(return_value={
            "content": "Spring Boot tutorial",
            "total_tokens": 50,
        })
        breaker = BubbleBreaker(organizer=organizer)

        results = [_make_result("https://dup.com/page", "配置指南详解")]

        async def mock_crawl(**kwargs):
            return [
                _make_result("https://dup.com/page", "Duplicate", success=True),
                _make_result("https://new.com/page", "New Result", success=True),
            ]

        with patch("optimization.bubble_breaker.settings") as mock_settings:
            mock_settings.bubble_breaker_enabled = True
            mock_settings.bubble_cross_language = True
            output = await breaker.check_and_expand(
                "配置指南", results, mock_crawl, {"engine": "bing"},
            )

        urls = [r["url"] for r in output]
        assert urls.count("https://dup.com/page") == 1
        assert "https://new.com/page" in urls

    @pytest.mark.asyncio
    async def test_crawl_failure_silent(self):
        organizer = MagicMock()
        organizer.is_available = True
        organizer._call_ai = AsyncMock(return_value={
            "content": "Spring Boot tutorial",
            "total_tokens": 50,
        })
        breaker = BubbleBreaker(organizer=organizer)

        results = [_make_result("https://cn.com/1", "入门详解")]

        async def mock_crawl(**kwargs):
            raise Exception("Network error")

        with patch("optimization.bubble_breaker.settings") as mock_settings:
            mock_settings.bubble_breaker_enabled = True
            mock_settings.bubble_cross_language = True
            output = await breaker.check_and_expand(
                "test", results, mock_crawl, {"engine": "bing"},
            )

        assert len(output) == 1
