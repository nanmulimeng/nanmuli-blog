"""Deep crawl module unit tests

覆盖 crawler/deep.py 的 BFS 深度爬取逻辑：
- BFS 基本流程：从起始 URL 发现并爬取子链接
- max_depth / max_pages 限制
- 同域名限制
- 爬取失败不影响其他页面
- 空结果 / 无链接发现
- URL 去重
- 边界条件
- 外部 crawler 复用
- 异常处理
"""

import os
import sys
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from crawler.deep import crawl_deep_pages
from crawler.single import CrawlResult


# ============== Helpers ==============

def make_raw_result(
    url="https://example.com/page1",
    success=True,
    markdown_text="# Title\n\nSome content here for word count.",
    html="<html><head><title>Page Title</title></head><body></body></html>",
    depth=0,
    error_message=None,
    crawl_time=100,
    internal_links=None,
    metadata=None,
):
    """构造一个模拟 Crawl4AI arun 返回的单条结果对象"""
    r = MagicMock()
    r.url = url
    r.success = success
    r.crawl_time = crawl_time
    r.depth = depth
    r.error_message = error_message
    r.html = html

    # markdown 属性：带 fit_markdown / raw_markdown 的对象
    md_obj = MagicMock()
    md_obj.fit_markdown = markdown_text
    md_obj.raw_markdown = markdown_text
    r.markdown = md_obj

    # links
    r.links = {"internal": internal_links or []}

    # metadata
    r.metadata = metadata or {"title": "Page Title", "description": "A page"}

    return r


# ============== Test Class ==============

class TestDeepCrawl:
    """crawl_deep_pages 的单元测试"""

    # ---------- 1. BFS 基本流程 ----------

    @pytest.mark.asyncio
    async def test_basic_bfs_crawl_multiple_pages(self):
        """BFS 基本流程：起始 URL 成功爬取，返回多个页面结果"""
        page1 = make_raw_result(url="https://example.com/", depth=0)
        page2 = make_raw_result(url="https://example.com/about", depth=1)
        page3 = make_raw_result(url="https://example.com/blog", depth=1)

        mock_crawler = AsyncMock()
        mock_crawler.arun.return_value = [page1, page2, page3]

        with patch("crawler.deep.AsyncWebCrawler"), \
             patch("crawler.deep.get_browser_config", return_value=MagicMock()), \
             patch("crawler.deep.get_crawler_run_config", return_value=MagicMock()), \
             patch("crawler.deep.BFSDeepCrawlStrategy", return_value=MagicMock()), \
             patch("crawler.deep.FilterChain", return_value=MagicMock()), \
             patch("crawler.deep.DomainFilter", return_value=MagicMock()):
            results = await crawl_deep_pages(
                url="https://example.com/",
                max_depth=2,
                max_pages=10,
                crawler=mock_crawler,
            )

        assert len(results) == 3
        assert all(isinstance(r, CrawlResult) for r in results)
        assert results[0].success is True
        assert results[0].url == "https://example.com/"
        assert results[0].depth == 0
        assert results[1].depth == 1
        assert results[2].depth == 1

    # ---------- 2. 单页爬取 ----------

    @pytest.mark.asyncio
    async def test_single_page_no_links(self):
        """起始页无子链接时，只返回起始页结果"""
        page = make_raw_result(url="https://example.com/", depth=0, internal_links=[])

        mock_crawler = AsyncMock()
        mock_crawler.arun.return_value = [page]

        with patch("crawler.deep.AsyncWebCrawler"), \
             patch("crawler.deep.get_browser_config", return_value=MagicMock()), \
             patch("crawler.deep.get_crawler_run_config", return_value=MagicMock()), \
             patch("crawler.deep.BFSDeepCrawlStrategy", return_value=MagicMock()), \
             patch("crawler.deep.FilterChain", return_value=MagicMock()), \
             patch("crawler.deep.DomainFilter", return_value=MagicMock()):
            results = await crawl_deep_pages(
                url="https://example.com/",
                max_depth=2,
                max_pages=10,
                crawler=mock_crawler,
            )

        assert len(results) == 1
        assert results[0].success is True
        assert results[0].url == "https://example.com/"

    # ---------- 3. max_pages 限制 ----------

    @pytest.mark.asyncio
    async def test_max_pages_limit_stops_early(self):
        """达到 max_pages 上限时提前停止"""
        pages = [
            make_raw_result(url=f"https://example.com/p{i}", depth=0)
            for i in range(20)
        ]

        mock_crawler = AsyncMock()
        mock_crawler.arun.return_value = pages

        with patch("crawler.deep.AsyncWebCrawler"), \
             patch("crawler.deep.get_browser_config", return_value=MagicMock()), \
             patch("crawler.deep.get_crawler_run_config", return_value=MagicMock()), \
             patch("crawler.deep.BFSDeepCrawlStrategy", return_value=MagicMock()), \
             patch("crawler.deep.FilterChain", return_value=MagicMock()), \
             patch("crawler.deep.DomainFilter", return_value=MagicMock()):
            results = await crawl_deep_pages(
                url="https://example.com/",
                max_depth=3,
                max_pages=5,
                crawler=mock_crawler,
            )

        assert len(results) == 5

    # ---------- 4. 边界：max_depth=1 ----------

    @pytest.mark.asyncio
    async def test_max_depth_one(self):
        """max_depth=1 时只爬起始页和直接子链接"""
        page1 = make_raw_result(url="https://example.com/", depth=0)
        page2 = make_raw_result(url="https://example.com/child", depth=1)

        mock_crawler = AsyncMock()
        mock_crawler.arun.return_value = [page1, page2]

        with patch("crawler.deep.AsyncWebCrawler"), \
             patch("crawler.deep.get_browser_config", return_value=MagicMock()), \
             patch("crawler.deep.get_crawler_run_config", return_value=MagicMock()), \
             patch("crawler.deep.BFSDeepCrawlStrategy", return_value=MagicMock()), \
             patch("crawler.deep.FilterChain", return_value=MagicMock()), \
             patch("crawler.deep.DomainFilter", return_value=MagicMock()):
            results = await crawl_deep_pages(
                url="https://example.com/",
                max_depth=1,
                max_pages=10,
                crawler=mock_crawler,
            )

        # BFSDeepCrawlStrategy 传入 max_depth=1
        assert len(results) == 2
        assert results[0].depth == 0
        assert results[1].depth == 1

    # ---------- 5. 边界：max_pages=1 ----------

    @pytest.mark.asyncio
    async def test_max_pages_one(self):
        """max_pages=1 时只爬取第一个页面"""
        pages = [
            make_raw_result(url="https://example.com/", depth=0),
            make_raw_result(url="https://example.com/other", depth=1),
        ]

        mock_crawler = AsyncMock()
        mock_crawler.arun.return_value = pages

        with patch("crawler.deep.AsyncWebCrawler"), \
             patch("crawler.deep.get_browser_config", return_value=MagicMock()), \
             patch("crawler.deep.get_crawler_run_config", return_value=MagicMock()), \
             patch("crawler.deep.BFSDeepCrawlStrategy", return_value=MagicMock()), \
             patch("crawler.deep.FilterChain", return_value=MagicMock()), \
             patch("crawler.deep.DomainFilter", return_value=MagicMock()):
            results = await crawl_deep_pages(
                url="https://example.com/",
                max_depth=2,
                max_pages=1,
                crawler=mock_crawler,
            )

        assert len(results) == 1
        assert results[0].url == "https://example.com/"

    # ---------- 6. 爬取失败不影响其他页面 ----------

    @pytest.mark.asyncio
    async def test_mixed_success_and_failure(self):
        """部分页面爬取失败不影响其他页面的结果"""
        page1 = make_raw_result(url="https://example.com/", success=True, depth=0)
        page2 = make_raw_result(
            url="https://example.com/fail",
            success=False,
            depth=1,
            error_message="Timeout",
            html=None,
            markdown_text=None,
        )
        page3 = make_raw_result(url="https://example.com/ok", success=True, depth=1)

        mock_crawler = AsyncMock()
        mock_crawler.arun.return_value = [page1, page2, page3]

        with patch("crawler.deep.AsyncWebCrawler"), \
             patch("crawler.deep.get_browser_config", return_value=MagicMock()), \
             patch("crawler.deep.get_crawler_run_config", return_value=MagicMock()), \
             patch("crawler.deep.BFSDeepCrawlStrategy", return_value=MagicMock()), \
             patch("crawler.deep.FilterChain", return_value=MagicMock()), \
             patch("crawler.deep.DomainFilter", return_value=MagicMock()):
            results = await crawl_deep_pages(
                url="https://example.com/",
                max_depth=2,
                max_pages=10,
                crawler=mock_crawler,
            )

        assert len(results) == 3
        assert results[0].success is True
        assert results[1].success is False
        assert results[1].error_message == "Timeout"
        assert results[2].success is True

    # ---------- 7. 全部失败 ----------

    @pytest.mark.asyncio
    async def test_all_pages_fail(self):
        """所有页面都爬取失败时返回全部失败结果"""
        pages = [
            make_raw_result(
                url=f"https://example.com/fail{i}",
                success=False,
                depth=i,
                error_message="Connection refused",
                html=None,
                markdown_text=None,
            )
            for i in range(3)
        ]

        mock_crawler = AsyncMock()
        mock_crawler.arun.return_value = pages

        with patch("crawler.deep.AsyncWebCrawler"), \
             patch("crawler.deep.get_browser_config", return_value=MagicMock()), \
             patch("crawler.deep.get_crawler_run_config", return_value=MagicMock()), \
             patch("crawler.deep.BFSDeepCrawlStrategy", return_value=MagicMock()), \
             patch("crawler.deep.FilterChain", return_value=MagicMock()), \
             patch("crawler.deep.DomainFilter", return_value=MagicMock()):
            results = await crawl_deep_pages(
                url="https://example.com/",
                max_depth=2,
                max_pages=10,
                crawler=mock_crawler,
            )

        assert len(results) == 3
        assert all(not r.success for r in results)

    # ---------- 8. 空结果 ----------

    @pytest.mark.asyncio
    async def test_empty_results(self):
        """arun 返回空列表时返回空列表"""
        mock_crawler = AsyncMock()
        mock_crawler.arun.return_value = []

        with patch("crawler.deep.AsyncWebCrawler"), \
             patch("crawler.deep.get_browser_config", return_value=MagicMock()), \
             patch("crawler.deep.get_crawler_run_config", return_value=MagicMock()), \
             patch("crawler.deep.BFSDeepCrawlStrategy", return_value=MagicMock()), \
             patch("crawler.deep.FilterChain", return_value=MagicMock()), \
             patch("crawler.deep.DomainFilter", return_value=MagicMock()):
            results = await crawl_deep_pages(
                url="https://example.com/",
                max_depth=2,
                max_pages=10,
                crawler=mock_crawler,
            )

        assert results == []

    # ---------- 9. URL 去重（BFS 策略层） ----------

    @pytest.mark.asyncio
    async def test_url_dedup_in_strategy(self):
        """验证 BFSDeepCrawlStrategy 配置正确传递参数（去重由策略内部处理）"""
        page = make_raw_result(url="https://example.com/", depth=0)

        mock_crawler = AsyncMock()
        mock_crawler.arun.return_value = [page]

        with patch("crawler.deep.AsyncWebCrawler"), \
             patch("crawler.deep.get_browser_config", return_value=MagicMock()), \
             patch("crawler.deep.get_crawler_run_config", return_value=MagicMock()), \
             patch("crawler.deep.BFSDeepCrawlStrategy") as mock_strategy, \
             patch("crawler.deep.FilterChain", return_value=MagicMock()), \
             patch("crawler.deep.DomainFilter", return_value=MagicMock()):

            await crawl_deep_pages(
                url="https://example.com/",
                max_depth=3,
                max_pages=15,
                crawler=mock_crawler,
            )

            # 验证策略参数正确传入 max_depth / max_pages / include_external
            call_kwargs = mock_strategy.call_args
            assert call_kwargs[1]["max_depth"] == 3
            assert call_kwargs[1]["max_pages"] == 15
            assert call_kwargs[1]["include_external"] is False
            assert "filter_chain" in call_kwargs[1]

    # ---------- 10. 同域名限制 ----------

    @pytest.mark.asyncio
    async def test_same_domain_filter(self):
        """验证 DomainFilter 配置了正确的域名"""
        page = make_raw_result(url="https://blog.example.com/post", depth=0)

        mock_crawler = AsyncMock()
        mock_crawler.arun.return_value = [page]

        with patch("crawler.deep.AsyncWebCrawler"), \
             patch("crawler.deep.get_browser_config", return_value=MagicMock()), \
             patch("crawler.deep.get_crawler_run_config", return_value=MagicMock()), \
             patch("crawler.deep.BFSDeepCrawlStrategy", return_value=MagicMock()), \
             patch("crawler.deep.FilterChain") as mock_filter_chain, \
             patch("crawler.deep.DomainFilter") as mock_domain_filter:

            mock_domain_filter.return_value = MagicMock()

            await crawl_deep_pages(
                url="https://blog.example.com/post",
                max_depth=2,
                max_pages=10,
                crawler=mock_crawler,
            )

            # 验证 DomainFilter 传入 allowed_domains 包含完整域名和通配符基础域名
            mock_domain_filter.assert_called_once()
            call_kwargs = mock_domain_filter.call_args
            allowed = call_kwargs[1]["allowed_domains"]
            assert "blog.example.com" in allowed
            assert "*.example.com" in allowed

    # ---------- 11. ccTLD 域名解析 ----------

    @pytest.mark.asyncio
    async def test_cctld_domain_extraction(self):
        """ccTLD（如 co.uk, com.cn）正确提取基础域名"""
        page = make_raw_result(url="https://www.example.co.uk/page", depth=0)

        mock_crawler = AsyncMock()
        mock_crawler.arun.return_value = [page]

        with patch("crawler.deep.AsyncWebCrawler"), \
             patch("crawler.deep.get_browser_config", return_value=MagicMock()), \
             patch("crawler.deep.get_crawler_run_config", return_value=MagicMock()), \
             patch("crawler.deep.BFSDeepCrawlStrategy", return_value=MagicMock()), \
             patch("crawler.deep.FilterChain") as mock_filter_chain, \
             patch("crawler.deep.DomainFilter") as mock_domain_filter:

            mock_domain_filter.return_value = MagicMock()

            await crawl_deep_pages(
                url="https://www.example.co.uk/page",
                max_depth=2,
                max_pages=10,
                crawler=mock_crawler,
            )

            call_kwargs = mock_domain_filter.call_args
            allowed = call_kwargs[1]["allowed_domains"]
            # co.uk 是 ccTLD，基础域名取后三段
            assert "*.example.co.uk" in allowed

    # ---------- 12. 外部 crawler 复用（不创建新浏览器） ----------

    @pytest.mark.asyncio
    async def test_external_crawler_reuse(self):
        """传入外部 crawler 时直接使用，不创建新的 AsyncWebCrawler"""
        page = make_raw_result(url="https://example.com/", depth=0)

        mock_crawler = AsyncMock()
        mock_crawler.arun.return_value = [page]

        with patch("crawler.deep.AsyncWebCrawler") as mock_awc_class, \
             patch("crawler.deep.get_browser_config", return_value=MagicMock()), \
             patch("crawler.deep.get_crawler_run_config", return_value=MagicMock()), \
             patch("crawler.deep.BFSDeepCrawlStrategy", return_value=MagicMock()), \
             patch("crawler.deep.FilterChain", return_value=MagicMock()), \
             patch("crawler.deep.DomainFilter", return_value=MagicMock()):

            await crawl_deep_pages(
                url="https://example.com/",
                max_depth=2,
                max_pages=10,
                crawler=mock_crawler,
            )

            # AsyncWebCrawler 不应被实例化
            mock_awc_class.assert_not_called()
            mock_crawler.arun.assert_called_once()

    # ---------- 13. 内部创建浏览器（crawler=None） ----------

    @pytest.mark.asyncio
    async def test_create_browser_when_no_crawler(self):
        """crawler=None 时内部创建 AsyncWebCrawler 实例"""
        page = make_raw_result(url="https://example.com/", depth=0)

        mock_crawler_instance = AsyncMock()
        mock_crawler_instance.arun.return_value = [page]
        # 模拟 async with 上下文管理器
        mock_crawler_instance.__aenter__ = AsyncMock(return_value=mock_crawler_instance)
        mock_crawler_instance.__aexit__ = AsyncMock(return_value=False)

        with patch("crawler.deep.AsyncWebCrawler", return_value=mock_crawler_instance), \
             patch("crawler.deep.get_browser_config", return_value=MagicMock()), \
             patch("crawler.deep.get_crawler_run_config", return_value=MagicMock()), \
             patch("crawler.deep.BFSDeepCrawlStrategy", return_value=MagicMock()), \
             patch("crawler.deep.FilterChain", return_value=MagicMock()), \
             patch("crawler.deep.DomainFilter", return_value=MagicMock()):

            results = await crawl_deep_pages(
                url="https://example.com/",
                max_depth=2,
                max_pages=10,
                crawler=None,
            )

        assert len(results) == 1
        assert results[0].success is True

    # ---------- 14. 异常处理 ----------

    @pytest.mark.asyncio
    async def test_exception_returns_error_result(self):
        """爬取过程抛出异常时返回已爬取结果 + 错误信息"""
        mock_crawler = AsyncMock()
        mock_crawler.arun.side_effect = RuntimeError("Browser crashed")

        with patch("crawler.deep.AsyncWebCrawler"), \
             patch("crawler.deep.get_browser_config", return_value=MagicMock()), \
             patch("crawler.deep.get_crawler_run_config", return_value=MagicMock()), \
             patch("crawler.deep.BFSDeepCrawlStrategy", return_value=MagicMock()), \
             patch("crawler.deep.FilterChain", return_value=MagicMock()), \
             patch("crawler.deep.DomainFilter", return_value=MagicMock()):

            results = await crawl_deep_pages(
                url="https://example.com/",
                max_depth=2,
                max_pages=10,
                crawler=mock_crawler,
            )

        assert len(results) == 1
        assert results[0].success is False
        assert "Browser crashed" in results[0].error_message
        assert results[0].url == "https://example.com/"

    # ---------- 15. metadata 和 title 提取 ----------

    @pytest.mark.asyncio
    async def test_metadata_and_title_extraction(self):
        """成功页面正确提取 metadata（含 links_found）和 title"""
        page = make_raw_result(
            url="https://example.com/article",
            depth=1,
            html="<html><head><title>Article Title</title></head><body></body></html>",
            internal_links=["/about", "/contact"],
            metadata={"title": "Meta Title", "description": "Meta Desc"},
        )

        mock_crawler = AsyncMock()
        mock_crawler.arun.return_value = [page]

        with patch("crawler.deep.AsyncWebCrawler"), \
             patch("crawler.deep.get_browser_config", return_value=MagicMock()), \
             patch("crawler.deep.get_crawler_run_config", return_value=MagicMock()), \
             patch("crawler.deep.BFSDeepCrawlStrategy", return_value=MagicMock()), \
             patch("crawler.deep.FilterChain", return_value=MagicMock()), \
             patch("crawler.deep.DomainFilter", return_value=MagicMock()), \
             patch("crawler.deep.extract_metadata", return_value={"title": "HTML Title"}):
            results = await crawl_deep_pages(
                url="https://example.com/article",
                max_depth=2,
                max_pages=10,
                crawler=mock_crawler,
            )

        assert len(results) == 1
        r = results[0]
        assert r.success is True
        assert r.word_count > 0
        # links_found 来自 page.links["internal"] 的长度
        assert r.metadata.get("links_found") == 2

    # ---------- 16. depth 从 metadata 回退 ----------

    @pytest.mark.asyncio
    async def test_depth_fallback_to_metadata(self):
        """result.depth 为 None 时从 metadata['depth'] 获取"""
        page = make_raw_result(url="https://example.com/page", depth=None)
        page.metadata = {"depth": 2, "title": "Test"}

        mock_crawler = AsyncMock()
        mock_crawler.arun.return_value = [page]

        with patch("crawler.deep.AsyncWebCrawler"), \
             patch("crawler.deep.get_browser_config", return_value=MagicMock()), \
             patch("crawler.deep.get_crawler_run_config", return_value=MagicMock()), \
             patch("crawler.deep.BFSDeepCrawlStrategy", return_value=MagicMock()), \
             patch("crawler.deep.FilterChain", return_value=MagicMock()), \
             patch("crawler.deep.DomainFilter", return_value=MagicMock()):
            results = await crawl_deep_pages(
                url="https://example.com/page",
                max_depth=3,
                max_pages=10,
                crawler=mock_crawler,
            )

        assert len(results) == 1
        assert results[0].depth == 2

    # ---------- 17. config 参数透传 ----------

    @pytest.mark.asyncio
    async def test_config_params_passed_to_run_config(self):
        """自定义 config 对象的属性正确传递给 RunParams"""
        page = make_raw_result(url="https://example.com/", depth=0)

        mock_config = MagicMock()
        mock_config.text_mode = False
        mock_config.light_mode = True
        mock_config.word_count_threshold = 50
        mock_config.excluded_tags = ["nav"]
        mock_config.wait_until = "load"
        mock_config.page_timeout = 30000
        mock_config.remove_overlay_elements = False

        mock_crawler = AsyncMock()
        mock_crawler.arun.return_value = [page]

        with patch("crawler.deep.AsyncWebCrawler"), \
             patch("crawler.deep.get_browser_config") as mock_bc, \
             patch("crawler.deep.get_crawler_run_config") as mock_rc, \
             patch("crawler.deep.BFSDeepCrawlStrategy", return_value=MagicMock()), \
             patch("crawler.deep.FilterChain", return_value=MagicMock()), \
             patch("crawler.deep.DomainFilter", return_value=MagicMock()):

            mock_bc.return_value = MagicMock()
            mock_rc.return_value = MagicMock()

            await crawl_deep_pages(
                url="https://example.com/",
                max_depth=2,
                max_pages=10,
                config=mock_config,
                crawler=mock_crawler,
            )

            # 验证 get_browser_config 参数来自 config
            mock_bc.assert_called_once_with(text_mode=False, light_mode=True)
            # 验证 get_crawler_run_config 参数来自 config
            mock_rc.assert_called_once_with(
                word_count_threshold=50,
                excluded_tags=["nav"],
                wait_until="load",
                page_timeout=30000,
                remove_overlay_elements=False,
            )

    # ---------- 18. 失败页面的 depth 回退 ----------

    @pytest.mark.asyncio
    async def test_failed_page_depth_fallback_to_zero(self):
        """失败页面 depth 和 metadata 都为 None 时回退到 0"""
        page = make_raw_result(
            url="https://example.com/fail",
            success=False,
            depth=None,
            error_message="Timeout",
            html=None,
            markdown_text=None,
        )
        page.metadata = None

        mock_crawler = AsyncMock()
        mock_crawler.arun.return_value = [page]

        with patch("crawler.deep.AsyncWebCrawler"), \
             patch("crawler.deep.get_browser_config", return_value=MagicMock()), \
             patch("crawler.deep.get_crawler_run_config", return_value=MagicMock()), \
             patch("crawler.deep.BFSDeepCrawlStrategy", return_value=MagicMock()), \
             patch("crawler.deep.FilterChain", return_value=MagicMock()), \
             patch("crawler.deep.DomainFilter", return_value=MagicMock()):
            results = await crawl_deep_pages(
                url="https://example.com/fail",
                max_depth=2,
                max_pages=10,
                crawler=mock_crawler,
            )

        assert len(results) == 1
        assert results[0].success is False
        assert results[0].depth == 0
        assert results[0].error_message == "Timeout"
