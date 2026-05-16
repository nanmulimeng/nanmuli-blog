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
from crawler.models import CrawlResult


# ============== Helpers ==============

def make_raw_result(
    url="https://example.com/page1",
    success=True,
    markdown_text="# Article Title\n\nThis is the main content with sufficient word count to pass the JS challenge minimum threshold for deep crawl testing.",
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
             patch("crawler.processor.extract_metadata", return_value={"title": "HTML Title"}):
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
        mock_config.excluded_selector = ".sidebar"
        mock_config.prune_threshold = 0.8
        mock_config.wait_until = "load"
        mock_config.page_timeout = 30000
        mock_config.remove_overlay_elements = False
        mock_config.max_retries = 1
        mock_config.wait_for = None
        mock_config.delay_before_return_html = 2.0
        mock_config.mean_delay = 1.0
        mock_config.max_range = 1.0
        mock_config.remove_consent_popups = False

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

            # 验证 get_browser_config 参数来自 config（proxy 来自 settings.proxy_url）
            call_args = mock_bc.call_args
            assert call_args.kwargs["text_mode"] is False
            assert call_args.kwargs["light_mode"] is True
            assert "proxy" in call_args.kwargs
            # 验证 get_crawler_run_config 参数来自 config
            mock_rc.assert_called_once_with(
                word_count_threshold=50,
                excluded_tags=["nav"],
                excluded_selector=".sidebar",
                prune_threshold=0.8,
                wait_until="load",
                page_timeout=30000,
                remove_overlay_elements=False,
                max_retries=1,
                mean_delay=1.0,
                max_range=1.0,
                delay_before_return_html=2.0,
                remove_consent_popups=False,
                wait_for=None,
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

    # ---------- 19. 普通子域名提取 ----------

    @pytest.mark.asyncio
    async def test_subdomain_extraction(self):
        """普通子域名（非 ccTLD）正确提取基础域名：sub.example.com → *.example.com"""
        page = make_raw_result(url="https://sub.example.com/page", depth=0)

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
                url="https://sub.example.com/page",
                max_depth=2,
                max_pages=10,
                crawler=mock_crawler,
            )

            call_kwargs = mock_domain_filter.call_args
            allowed = call_kwargs[1]["allowed_domains"]
            assert "sub.example.com" in allowed
            assert "*.example.com" in allowed

    # ---------- 20. crawl4ai metadata 保留 ----------

    @pytest.mark.asyncio
    async def test_crawl4ai_metadata_preserved(self):
        """验证 crawl4ai 原始 metadata 中的 title/description 被保留"""
        page = make_raw_result(
            url="https://example.com/article",
            depth=1,
            html="<html><head></head><body>No meta tags</body></html>",
            metadata={"title": "Crawl4AI Title", "description": "Crawl4AI Desc"},
        )

        mock_crawler = AsyncMock()
        mock_crawler.arun.return_value = [page]

        with patch("crawler.deep.AsyncWebCrawler"), \
             patch("crawler.deep.get_browser_config", return_value=MagicMock()), \
             patch("crawler.deep.get_crawler_run_config", return_value=MagicMock()), \
             patch("crawler.deep.BFSDeepCrawlStrategy", return_value=MagicMock()), \
             patch("crawler.deep.FilterChain", return_value=MagicMock()), \
             patch("crawler.deep.DomainFilter", return_value=MagicMock()):
            results = await crawl_deep_pages(
                url="https://example.com/article",
                max_depth=2,
                max_pages=10,
                crawler=mock_crawler,
            )

        assert len(results) == 1
        r = results[0]
        assert r.metadata.get("crawl4ai_title") == "Crawl4AI Title"
        assert r.metadata.get("crawl4ai_description") == "Crawl4AI Desc"

    # ---------- 21. success=True 但 html=None ----------

    @pytest.mark.asyncio
    async def test_success_html_none(self):
        """success=True 但 result.html=None 时不崩溃，metadata 为空字典"""
        page = make_raw_result(
            url="https://example.com/",
            success=True,
            depth=0,
            html=None,
        )

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
        assert isinstance(results[0].metadata, dict)

    # ---------- 22. 失败页面 metadata 中有 depth ----------

    @pytest.mark.asyncio
    async def test_failed_page_depth_from_metadata(self):
        """失败页面 result.depth=None 但从 metadata dict 获取 depth"""
        page = make_raw_result(
            url="https://example.com/fail",
            success=False,
            depth=None,
            error_message="Timeout",
            html=None,
            markdown_text=None,
        )
        page.metadata = {"depth": 3, "title": "Test"}

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
        assert results[0].depth == 3

    # ---------- 23. 参数校验 ----------

    @pytest.mark.asyncio
    async def test_max_depth_zero_raises_value_error(self):
        """max_depth=0 时抛出 ValueError"""
        with pytest.raises(ValueError, match="max_depth must be >= 1"):
            await crawl_deep_pages(
                url="https://example.com/",
                max_depth=0,
                max_pages=10,
            )

    @pytest.mark.asyncio
    async def test_max_depth_negative_raises_value_error(self):
        """max_depth 为负数时抛出 ValueError"""
        with pytest.raises(ValueError, match="max_depth must be >= 1"):
            await crawl_deep_pages(
                url="https://example.com/",
                max_depth=-1,
                max_pages=10,
            )

    @pytest.mark.asyncio
    async def test_max_pages_zero_raises_value_error(self):
        """max_pages=0 时抛出 ValueError"""
        with pytest.raises(ValueError, match="max_pages must be >= 1"):
            await crawl_deep_pages(
                url="https://example.com/",
                max_depth=2,
                max_pages=0,
            )

    @pytest.mark.asyncio
    async def test_max_pages_negative_raises_value_error(self):
        """max_pages 为负数时抛出 ValueError"""
        with pytest.raises(ValueError, match="max_pages must be >= 1"):
            await crawl_deep_pages(
                url="https://example.com/",
                max_depth=2,
                max_pages=-5,
            )

    # ---------- 24. URL 去重保护 ----------

    @pytest.mark.asyncio
    async def test_duplicate_urls_skipped(self):
        """BFS 返回重复 URL 时，上层去重保护生效"""
        page1 = make_raw_result(url="https://example.com/page1", depth=0)
        page2 = make_raw_result(url="https://example.com/page2", depth=1)
        page1_dup = make_raw_result(url="https://example.com/page1", depth=1)

        mock_crawler = AsyncMock()
        mock_crawler.arun.return_value = [page1, page2, page1_dup]

        with patch("crawler.deep.AsyncWebCrawler"), \
             patch("crawler.deep.get_browser_config", return_value=MagicMock()), \
             patch("crawler.deep.get_crawler_run_config", return_value=MagicMock()), \
             patch("crawler.deep.BFSDeepCrawlStrategy", return_value=MagicMock()), \
             patch("crawler.deep.FilterChain", return_value=MagicMock()), \
             patch("crawler.deep.DomainFilter", return_value=MagicMock()):
            results = await crawl_deep_pages(
                url="https://example.com/page1",
                max_depth=2,
                max_pages=10,
                crawler=mock_crawler,
            )

        # 重复的 page1 被跳过，只保留 2 个结果
        assert len(results) == 2
        urls = [r.url for r in results]
        assert urls == ["https://example.com/page1", "https://example.com/page2"]

    # ---------- 25. JS Challenge 重试 ----------

    @pytest.mark.asyncio
    async def test_js_challenge_retry_in_deep(self):
        """低字数页面触发 JS Challenge 重试，重试成功返回完整内容"""
        page_low = make_raw_result(
            url="https://example.com/low",
            depth=1,
            markdown_text="Brief",  # 1 word -> < 20
        )
        page_full = make_raw_result(
            url="https://example.com/low",
            depth=1,
            markdown_text="This is the complete article content after successful JS challenge retry with enough word count to pass the threshold check.",
        )

        mock_crawler = AsyncMock()
        # 第1次 BFS 返回低字数页面，第2次单页重试返回完整内容
        mock_crawler.arun.side_effect = [
            [page_low],       # BFS 结果
            [page_full],      # JS Challenge 重试结果
        ]

        with patch("crawler.deep.AsyncWebCrawler"), \
             patch("crawler.deep.get_browser_config", return_value=MagicMock()), \
             patch("crawler.deep.get_crawler_run_config", return_value=MagicMock()), \
             patch("crawler.deep.BFSDeepCrawlStrategy", return_value=MagicMock()), \
             patch("crawler.deep.FilterChain", return_value=MagicMock()), \
             patch("crawler.deep.DomainFilter", return_value=MagicMock()):
            results = await crawl_deep_pages(
                url="https://example.com/low",
                max_depth=2,
                max_pages=10,
                crawler=mock_crawler,
            )

        assert len(results) == 1
        assert results[0].success is True
        assert "complete article" in results[0].markdown
        # arun 被调用 2 次：BFS + 单页重试
        assert mock_crawler.arun.await_count == 2

    @pytest.mark.asyncio
    async def test_js_challenge_retry_fails_still_uses_original(self):
        """JS Challenge 重试失败时仍使用原始结果（不丢失低字数内容）"""
        page_low = make_raw_result(
            url="https://example.com/low",
            depth=1,
            markdown_text="Just checking",  # 2 words -> low
        )

        mock_crawler = AsyncMock()
        mock_crawler.arun.side_effect = [
            [page_low],       # BFS 结果
            RuntimeError("Retry failed"),  # 重试异常
        ]

        with patch("crawler.deep.AsyncWebCrawler"), \
             patch("crawler.deep.get_browser_config", return_value=MagicMock()), \
             patch("crawler.deep.get_crawler_run_config", return_value=MagicMock()), \
             patch("crawler.deep.BFSDeepCrawlStrategy", return_value=MagicMock()), \
             patch("crawler.deep.FilterChain", return_value=MagicMock()), \
             patch("crawler.deep.DomainFilter", return_value=MagicMock()):
            results = await crawl_deep_pages(
                url="https://example.com/low",
                max_depth=2,
                max_pages=10,
                crawler=mock_crawler,
            )

        # 重试失败不应崩溃，仍返回原始结果
        assert len(results) == 1
        assert results[0].success is True
        assert "Just checking" in results[0].markdown

    @pytest.mark.asyncio
    async def test_normal_word_count_no_unnecessary_retry(self):
        """正常字数的页面不应触发重试"""
        page = make_raw_result(
            url="https://example.com/normal",
            depth=1,
            markdown_text="This is a normal article with sufficient word count to pass the minimum threshold for deep crawl content validation testing.",
        )

        mock_crawler = AsyncMock()
        mock_crawler.arun.return_value = [page]

        with patch("crawler.deep.AsyncWebCrawler"), \
             patch("crawler.deep.get_browser_config", return_value=MagicMock()), \
             patch("crawler.deep.get_crawler_run_config", return_value=MagicMock()), \
             patch("crawler.deep.BFSDeepCrawlStrategy", return_value=MagicMock()), \
             patch("crawler.deep.FilterChain", return_value=MagicMock()), \
             patch("crawler.deep.DomainFilter", return_value=MagicMock()):
            results = await crawl_deep_pages(
                url="https://example.com/normal",
                max_depth=2,
                max_pages=10,
                crawler=mock_crawler,
            )

        assert len(results) == 1
        # arun 只调用 1 次（无重试）
        assert mock_crawler.arun.await_count == 1
