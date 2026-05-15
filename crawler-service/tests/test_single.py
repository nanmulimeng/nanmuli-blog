"""单页爬取模块单元测试

覆盖 crawler/single.py 的核心逻辑：
- 成功爬取：metadata/markdown/word_count 提取
- 失败爬取：error_message 正确返回
- result.html 为 None 时的空值保护
- result.success=False 时的降级处理
- 外部 crawler 复用（不创建新浏览器）
- 浏览器实例内部创建
- 异常处理
"""

import os
import sys
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from crawler.single import crawl_single_page
from crawler.models import CrawlResult


# ============== Helpers ==============

def make_raw_result(
    url="https://example.com/",
    success=True,
    markdown_text="# Article Title\n\nThis is the main content with sufficient word count to pass the JS challenge minimum threshold for testing purposes.",
    html="<html><head><title>Page Title</title></head><body><h1>Title</h1><p>Content</p></body></html>",
    error_message=None,
    crawl_time=100,
):
    """构造一个模拟 Crawl4AI arun 返回的单条结果对象"""
    r = MagicMock()
    r.url = url
    r.success = success
    r.crawl_time = crawl_time
    r.error_message = error_message
    r.html = html

    md_obj = MagicMock()
    md_obj.fit_markdown = markdown_text
    md_obj.raw_markdown = markdown_text
    r.markdown = md_obj

    r.metadata = {"title": "Meta Title", "description": "Meta Desc"}
    return r


# ============== Test Class ==============

class TestSingleCrawl:
    """crawl_single_page 的单元测试"""

    # ---------- 1. 成功爬取 ----------

    @pytest.mark.asyncio
    async def test_successful_crawl(self):
        """正常页面爬取：返回 CrawlResult，success=True，metadata 完整"""
        page = make_raw_result()

        mock_crawler = AsyncMock()
        mock_crawler.arun.return_value = page

        with patch("crawler.single.AsyncWebCrawler") as mock_awc_class, \
             patch("crawler.single.get_browser_config", return_value=MagicMock()), \
             patch("crawler.single.get_crawler_run_config", return_value=MagicMock()):

            mock_instance = AsyncMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_crawler)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_awc_class.return_value = mock_instance

            result = await crawl_single_page("https://example.com/")

        assert isinstance(result, CrawlResult)
        assert result.success is True
        assert result.url == "https://example.com/"
        assert result.title is not None
        assert result.markdown is not None
        assert result.word_count >= 0
        assert result.crawl_time_ms >= 0
        assert "url" in result.metadata

    @pytest.mark.asyncio
    async def test_crawl_result_to_dict(self):
        """CrawlResult.to_dict() 返回可序列化的字典"""
        result = CrawlResult(
            success=True,
            url="https://example.com/",
            title="Test",
            markdown="# Hello",
            metadata={"key": "value"},
            word_count=5,
            crawl_time_ms=100,
            depth=0,
            search_rank=1,
        )
        d = result.to_dict()
        assert d["success"] is True
        assert d["url"] == "https://example.com/"
        assert d["title"] == "Test"
        assert d["word_count"] == 5
        assert d["depth"] == 0
        assert d["search_rank"] == 1

    # ---------- 2. 失败爬取 ----------

    @pytest.mark.asyncio
    async def test_failed_crawl(self):
        """Crawl4AI 返回 success=False 时，正确记录错误信息"""
        page = make_raw_result(success=False, error_message="Connection timeout")

        mock_crawler = AsyncMock()
        mock_crawler.arun.return_value = page

        with patch("crawler.single.AsyncWebCrawler") as mock_awc_class, \
             patch("crawler.single.get_browser_config", return_value=MagicMock()), \
             patch("crawler.single.get_crawler_run_config", return_value=MagicMock()):

            mock_instance = AsyncMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_crawler)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_awc_class.return_value = mock_instance

            result = await crawl_single_page("https://example.com/")

        assert result.success is False
        assert "Connection timeout" in result.error_message
        assert result.crawl_time_ms >= 0

    # ---------- 3. result.html 为 None 的空值保护 ----------

    @pytest.mark.asyncio
    async def test_success_but_html_is_none(self):
        """success=True 但 html 为 None 时不抛异常，降级返回空 metadata"""
        page = make_raw_result(success=True, html=None)

        mock_crawler = AsyncMock()
        mock_crawler.arun.return_value = page

        with patch("crawler.single.AsyncWebCrawler") as mock_awc_class, \
             patch("crawler.single.get_browser_config", return_value=MagicMock()), \
             patch("crawler.single.get_crawler_run_config", return_value=MagicMock()):

            mock_instance = AsyncMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_crawler)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_awc_class.return_value = mock_instance

            result = await crawl_single_page("https://example.com/")

        assert result.success is True
        assert result.metadata is not None
        # 空 HTML 时 metadata 字段应全为 None
        assert result.metadata.get("title") is None
        assert result.metadata.get("description") is None

    # ---------- 4. 外部 crawler 复用 ----------

    @pytest.mark.asyncio
    async def test_external_crawler_reuse(self):
        """传入外部 crawler 时直接使用，不创建新的 AsyncWebCrawler"""
        page = make_raw_result()

        mock_crawler = AsyncMock()
        mock_crawler.arun.return_value = page

        with patch("crawler.single.AsyncWebCrawler") as mock_awc_class, \
             patch("crawler.single.get_browser_config", return_value=MagicMock()), \
             patch("crawler.single.get_crawler_run_config", return_value=MagicMock()):

            result = await crawl_single_page(
                "https://example.com/",
                crawler=mock_crawler,
            )

            mock_awc_class.assert_not_called()
            mock_crawler.arun.assert_called_once()

        assert result.success is True

    # ---------- 5. 内部创建浏览器（crawler=None） ----------

    @pytest.mark.asyncio
    async def test_create_browser_when_no_crawler(self):
        """crawler=None 时内部创建 AsyncWebCrawler 实例"""
        page = make_raw_result()

        mock_crawler = AsyncMock()
        mock_crawler.arun.return_value = page

        mock_instance = AsyncMock()
        mock_instance.__aenter__ = AsyncMock(return_value=mock_crawler)
        mock_instance.__aexit__ = AsyncMock(return_value=False)

        with patch("crawler.single.AsyncWebCrawler", return_value=mock_instance), \
             patch("crawler.single.get_browser_config", return_value=MagicMock()), \
             patch("crawler.single.get_crawler_run_config", return_value=MagicMock()):

            result = await crawl_single_page("https://example.com/")

        assert result.success is True
        mock_instance.__aenter__.assert_awaited_once()
        mock_instance.__aexit__.assert_awaited_once()

    # ---------- 6. 异常处理 ----------

    @pytest.mark.asyncio
    async def test_exception_returns_error_result(self):
        """爬取过程抛出异常时返回失败结果"""
        with patch("crawler.single.AsyncWebCrawler") as mock_awc_class, \
             patch("crawler.single.get_browser_config", return_value=MagicMock()), \
             patch("crawler.single.get_crawler_run_config", return_value=MagicMock()):

            mock_instance = AsyncMock()
            mock_instance.__aenter__ = AsyncMock(side_effect=RuntimeError("Browser not found"))
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_awc_class.return_value = mock_instance

            result = await crawl_single_page("https://example.com/")

        assert result.success is False
        assert "Browser not found" in result.error_message
        assert result.crawl_time_ms >= 0

    # ---------- 7. config 参数透传 ----------

    @pytest.mark.asyncio
    async def test_config_params_passed(self):
        """自定义 config 对象的属性正确传递给 browser/run config"""
        page = make_raw_result()

        mock_config = MagicMock()
        mock_config.text_mode = False
        mock_config.light_mode = True
        mock_config.word_count_threshold = 50
        mock_config.excluded_tags = ["nav"]
        mock_config.excluded_selector = ".sidebar"
        mock_config.prune_threshold = 0.8
        mock_config.wait_until = "domcontentloaded"
        mock_config.page_timeout = 30000
        mock_config.remove_overlay_elements = False

        mock_crawler = AsyncMock()
        mock_crawler.arun.return_value = page

        with patch("crawler.single.AsyncWebCrawler") as mock_awc_class, \
             patch("crawler.single.get_browser_config") as mock_bc, \
             patch("crawler.single.get_crawler_run_config") as mock_rc:

            mock_bc.return_value = MagicMock()
            mock_rc.return_value = MagicMock()

            mock_instance = AsyncMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_crawler)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_awc_class.return_value = mock_instance

            await crawl_single_page(
                "https://example.com/",
                config=mock_config,
            )

            # 验证 get_browser_config 参数
            call_args = mock_bc.call_args
            assert call_args.kwargs["text_mode"] is False
            assert call_args.kwargs["light_mode"] is True
            assert "proxy" in call_args.kwargs

            # 验证 get_crawler_run_config 参数
            call_args = mock_rc.call_args
            assert call_args.kwargs["word_count_threshold"] == 50
            assert call_args.kwargs["excluded_tags"] == ["nav"]
            assert call_args.kwargs["excluded_selector"] == ".sidebar"
            assert call_args.kwargs["prune_threshold"] == 0.8
            assert call_args.kwargs["wait_until"] == "domcontentloaded"
            assert call_args.kwargs["page_timeout"] == 30000
            assert call_args.kwargs["remove_overlay_elements"] is False

    # ---------- 8. 空 markdown ----------

    @pytest.mark.asyncio
    async def test_empty_markdown(self):
        """markdown 为空字符串时 word_count=0，不抛异常"""
        page = make_raw_result(markdown_text="")

        mock_crawler = AsyncMock()
        mock_crawler.arun.return_value = page

        with patch("crawler.single.AsyncWebCrawler") as mock_awc_class, \
             patch("crawler.single.get_browser_config", return_value=MagicMock()), \
             patch("crawler.single.get_crawler_run_config", return_value=MagicMock()):

            mock_instance = AsyncMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_crawler)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_awc_class.return_value = mock_instance

            result = await crawl_single_page("https://example.com/")

        assert result.success is True
        assert result.word_count == 0
        assert result.markdown is not None  # 空字符串也是合法的 markdown

    # ---------- 9. metadata 中的 crawl4ai_title 回退 ----------

    @pytest.mark.asyncio
    async def test_metadata_title_fallback(self):
        """extract_metadata 返回的 title 优先于 crawl4ai_title"""
        page = make_raw_result(
            html='<html><head><title>HTML Title</title></head><body></body></html>',
            markdown_text="Article content with sufficient word count to pass the JS challenge minimum threshold check.",
        )
        page.metadata = {"title": "Crawl4AI Title", "description": "Desc"}

        mock_crawler = AsyncMock()
        mock_crawler.arun.return_value = page

        with patch("crawler.single.AsyncWebCrawler") as mock_awc_class, \
             patch("crawler.single.get_browser_config", return_value=MagicMock()), \
             patch("crawler.single.get_crawler_run_config", return_value=MagicMock()):

            mock_instance = AsyncMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_crawler)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_awc_class.return_value = mock_instance

            result = await crawl_single_page("https://example.com/")

        assert result.title == "HTML Title"  # extract_metadata 优先
        assert result.metadata.get("crawl4ai_title") == "Crawl4AI Title"

    # ---------- 10. JS Challenge 自动重试 ----------

    @pytest.mark.asyncio
    async def test_js_challenge_retry(self):
        """低字数时自动以 wait_for 重试（JS Challenge 恢复）"""
        page_low = make_raw_result(
            markdown_text="Just checking",  # 2 words = 3 -> < 20
        )
        page_full = make_raw_result(
            markdown_text="This is the complete article with enough word count to pass the minimum threshold check for content validation.",
        )

        mock_crawler = AsyncMock()
        # 第1次返回低字数结果，第2次返回完整内容
        mock_crawler.arun.side_effect = [page_low, page_full]

        with patch("crawler.single.AsyncWebCrawler") as mock_awc_class, \
             patch("crawler.single.get_browser_config", new_callable=AsyncMock, return_value=MagicMock()), \
             patch("crawler.single.get_crawler_run_config", return_value=MagicMock()) as mock_rc, \
             patch("crawler.processor.get_crawler_run_config", return_value=MagicMock()):

            mock_rc.return_value = MagicMock()

            mock_instance = AsyncMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_crawler)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_awc_class.return_value = mock_instance

            result = await crawl_single_page("https://example.com/")

            # 验证重试了
            assert mock_crawler.arun.await_count == 2
            # 最终应返回完整内容
            assert result.success is True
            assert "complete article" in result.markdown

    @pytest.mark.asyncio
    async def test_js_challenge_retry_with_external_crawler(self):
        """传入外部 crawler 时的 JS Challenge 重试"""
        page_low = make_raw_result(
            markdown_text="Brief",  # 1 word = 1.5 -> 1 -> < 20
        )
        page_full = make_raw_result(
            markdown_text="This is the full article with sufficient word count to pass the minimum threshold check for testing purposes.",
        )

        mock_crawler = AsyncMock()
        mock_crawler.arun.side_effect = [page_low, page_full]

        with patch("crawler.single.AsyncWebCrawler") as mock_awc_class, \
             patch("crawler.single.get_browser_config", return_value=MagicMock()), \
             patch("crawler.single.get_crawler_run_config", return_value=MagicMock()):

            result = await crawl_single_page(
                "https://example.com/",
                crawler=mock_crawler,
            )

            mock_awc_class.assert_not_called()
            assert mock_crawler.arun.await_count == 2
            assert result.success is True
            assert "full article" in result.markdown
