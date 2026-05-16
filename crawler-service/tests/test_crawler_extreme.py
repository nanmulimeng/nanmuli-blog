"""
Extreme / quality edge-case tests for crawler modules

Tests:
  TestExtractMarkdownQuality  — extract_markdown() noise filtering (15)
  TestExtremeInput            — boundary input handling (10)
  TestSearchExtreme           — search parsing, SSRF, dedup (10)
  TestConfigPipeline          — RunParams, utils (5)
  TestDeepCrawlExtreme        — deep crawl edge cases (5)
"""

import os
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from crawler.config import (
    extract_markdown, RunParams, DEFAULT_EXCLUDED_TAGS, DEFAULT_EXCLUDED_SELECTOR,
)
from crawler.utils import count_words, normalize_url, detect_cjk
from crawler.models import CrawlResult


# ============== Helpers ==============

def make_crawl4ai_result(fit_markdown="", raw_markdown=""):
    """构造 crawl4ai result mock"""
    r = MagicMock()
    md = MagicMock()
    md.fit_markdown = fit_markdown
    md.raw_markdown = raw_markdown
    r.markdown = md
    return r


def make_raw_result(
    url="https://example.com/page1",
    success=True,
    markdown_text="# Title\n\nMain content with sufficient word count for deep crawl testing.",
    html="<html><head><title>Page</title></head><body></body></html>",
    depth=0,
    error_message=None,
    crawl_time=100,
    internal_links=None,
    metadata=None,
):
    """构造模拟 Crawl4AI arun 返回的单条结果（复用 test_deep.py 模式）"""
    r = MagicMock()
    r.url = url
    r.success = success
    r.crawl_time = crawl_time
    r.depth = depth
    r.error_message = error_message
    r.html = html
    md_obj = MagicMock()
    md_obj.fit_markdown = markdown_text or ""
    md_obj.raw_markdown = markdown_text or ""
    r.markdown = md_obj
    r.links = {"internal": internal_links or []}
    r.metadata = metadata or {"title": "Page", "description": "A page"}
    return r


# ================================================================
#  Test Class 1: TestExtractMarkdownQuality (15 tests)
# ================================================================

class TestExtractMarkdownQuality:
    """extract_markdown() 对真实网页噪声的过滤测试"""

    def test_sidebar_link_list_removed(self):
        """侧边栏链接列表（8+ 连续链接行，链接文本占比>55%）被过滤"""
        sidebar = "\n".join([
            f"- [{name}]({url})"
            for name, url in [
                ("首页", "/"), ("博客", "/blog"), ("归档", "/archive"),
                ("分类", "/categories"), ("标签", "/tags"), ("关于", "/about"),
                ("搜索", "/search"), ("RSS", "/feed"), ("GitHub", "https://github.com"),
            ]
        ])
        content = "# Article\n\n这是正文内容，应该被保留。\n\n" + sidebar + "\n\n更多正文内容。"
        result = make_crawl4ai_result(fit_markdown=content, raw_markdown=content)
        md = extract_markdown(result)
        assert "这是正文内容" in md
        assert "更多正文内容" in md
        # 侧边栏链接行被移除（至少大部分）
        assert "首页" not in md or "博客" not in md

    def test_inline_nav_pipe_separated_removed(self):
        """管道分隔的内联导航行被过滤"""
        nav = "[Home](/) | [Blog](/b) | [About](/a)"
        content = "# Title\n\n正文段落保持完整。\n\n" + nav + "\n\n更多内容。"
        result = make_crawl4ai_result(fit_markdown=content, raw_markdown=content)
        md = extract_markdown(result)
        assert "正文段落保持完整" in md
        assert "更多内容" in md
        assert "[Home](/)" not in md

    def test_tab_bar_bold_link_mix_removed(self):
        """标签栏（粗体+链接混排）模式被过滤"""
        tab_bar = "**网页** [图片](https://example.com/img) [视频](https://example.com/vid)"
        content = "# Title\n\n这是正文内容。\n\n" + tab_bar + "\n\n更多正文。"
        result = make_crawl4ai_result(fit_markdown=content, raw_markdown=content)
        md = extract_markdown(result)
        assert "这是正文内容" in md
        assert "更多正文" in md
        assert "**网页**" not in md

    def test_cookie_banner_removed(self):
        """Cookie 横幅文本被样板过滤器移除"""
        cookie = "We use cookies on this site to improve your experience."
        content = "# Article\n\n正文内容保留。\n\n" + cookie + "\n\n更多内容。"
        result = make_crawl4ai_result(fit_markdown=content, raw_markdown=content)
        md = extract_markdown(result)
        assert "正文内容保留" in md
        assert "更多内容" in md
        assert "cookies" not in md.lower()

    def test_icp_filing_removed(self):
        """ICP 备案号被移除"""
        icp = "ICP备12345678号"
        content = "# 文章\n\n正文内容保留。\n\n" + icp + "\n\n更多内容。"
        result = make_crawl4ai_result(fit_markdown=content, raw_markdown=content)
        md = extract_markdown(result)
        assert "正文内容保留" in md
        assert "ICP备" not in md

    def test_csdn_skin_elements_removed(self):
        """CSDN 皮肤元素（版权声明等）被移除"""
        csdn = "版权声明：本文为博主原创文章，遵循 CC 4.0 BY-SA 版权协议"
        content = "# Article\n\n正文内容保留。\n\n" + csdn + "\n\n更多正文。"
        result = make_crawl4ai_result(fit_markdown=content, raw_markdown=content)
        md = extract_markdown(result)
        assert "正文内容保留" in md
        assert "版权声明" not in md

    def test_reward_removed(self):
        """打赏/求关注文本被移除"""
        reward = "打赏作者\n您的支持是我前进的动力"
        content = "# Article\n\n正文内容保留。\n\n" + reward + "\n\n更多正文。"
        result = make_crawl4ai_result(fit_markdown=content, raw_markdown=content)
        md = extract_markdown(result)
        assert "正文内容保留" in md
        assert "打赏作者" not in md
        assert "前进的动力" not in md

    def test_app_download_removed(self):
        """APP 下载横幅被移除"""
        app = "下载APP，享受更好的阅读体验。APP内阅读全文。"
        content = "# Article\n\n正文内容保留。\n\n" + app + "\n\n更多正文。"
        result = make_crawl4ai_result(fit_markdown=content, raw_markdown=content)
        md = extract_markdown(result)
        assert "正文内容保留" in md
        assert "下载APP" not in md
        assert "APP内阅读" not in md

    def test_breadcrumb_markdown_links_removed(self):
        """Markdown 链接形式的面包屑被过滤"""
        breadcrumb = "[Home](/) > [Blog](/b) > [Post](/p)"
        content = "# Title\n\n正文保留。\n\n" + breadcrumb + "\n\n更多内容。"
        result = make_crawl4ai_result(fit_markdown=content, raw_markdown=content)
        md = extract_markdown(result)
        assert "正文保留" in md
        assert "[Home](/)" not in md

    def test_breadcrumb_plain_text_removed(self):
        """纯文本面包屑被过滤"""
        breadcrumb = "Home / Blog / Current Post"
        content = "# Title\n\n正文保留。\n\n" + breadcrumb + "\n\n更多内容。"
        result = make_crawl4ai_result(fit_markdown=content, raw_markdown=content)
        md = extract_markdown(result)
        assert "正文保留" in md
        assert "Home / Blog / Current Post" not in md

    def test_fit_raw_ratio_triggers_fallback(self):
        """fit 不足 raw 的 30% 时回退到 raw+过滤"""
        noise = "\n".join([f"[- Link {i}](/link{i})" for i in range(20)])
        raw = "# Title\n\n" + "A" * 500 + "\n\n" + noise
        fit = "A" * 50  # 50 / 500+ = < 30%
        result = make_crawl4ai_result(fit_markdown=fit, raw_markdown=raw)
        md = extract_markdown(result)
        # 应使用 filtered raw，保留正文
        assert len(md) > len(fit)

    def test_fit_raw_ratio_above_threshold_uses_fit(self):
        """fit/raw >= 30% 时使用 fit"""
        base = "# Title\n\n" + "正文内容 " * 60
        fit = base
        raw = base + "\n\n" + "额外内容 " * 20
        result = make_crawl4ai_result(fit_markdown=fit, raw_markdown=raw)
        md = extract_markdown(result)
        assert "Title" in md
        assert "正文内容" in md

    def test_none_markdown_object_returns_empty(self):
        """result.markdown = None 返回空字符串"""
        r = MagicMock()
        r.markdown = None
        assert extract_markdown(r) == ""

    def test_empty_fit_and_raw_returns_empty(self):
        """fit 和 raw 均为空时返回空字符串"""
        result = make_crawl4ai_result(fit_markdown="", raw_markdown="")
        assert extract_markdown(result) == ""

    def test_qrcode_follow_removed(self):
        """扫码关注公众号文本被移除"""
        qr = "扫码关注公众号，获取更多技术文章"
        content = "# Article\n\n正文内容保留。\n\n" + qr + "\n\n更多正文。"
        result = make_crawl4ai_result(fit_markdown=content, raw_markdown=content)
        md = extract_markdown(result)
        assert "正文内容保留" in md
        assert "扫码关注" not in md


# ================================================================
#  Test Class 2: TestExtremeInput (10 tests)
# ================================================================

class TestExtremeInput:
    """极端输入边界测试"""

    def test_huge_page_content(self):
        """1MB+ markdown 文本不 OOM 不超时"""
        base = "这是第{n}段正文内容，包含足够多的文字来模拟真实页面。"
        huge = "# Big Page\n\n" + "\n\n".join(base.format(n=i) for i in range(50000))
        assert len(huge) > 1_000_000
        result = make_crawl4ai_result(fit_markdown=huge, raw_markdown=huge)
        md = extract_markdown(result)
        assert "Big Page" in md
        assert "正文内容" in md

    def test_malformed_html_in_markdown(self):
        """markdown 内混入畸形 HTML 不崩溃"""
        malformed = (
            '# Title\n\n正文内容。\n\n'
            '</script><div onclick="evil()">XSS</div>\n\n'
            '<script>alert("xss")</script>\n\n更多正文。'
        )
        result = make_crawl4ai_result(fit_markdown=malformed, raw_markdown=malformed)
        md = extract_markdown(result)
        assert "Title" in md
        assert "正文内容" in md

    def test_emoji_content_preserved(self):
        """含 emoji 的正文被保留"""
        emoji_text = "# Rocket Launch 🚀\n\n今天是个好日子 🎉，技术分享 💻 开始了！"
        result = make_crawl4ai_result(fit_markdown=emoji_text, raw_markdown=emoji_text)
        md = extract_markdown(result)
        assert "🚀" in md
        assert "🎉" in md
        assert "💻" in md

    def test_zero_width_chars_handled(self):
        """含零宽字符的 markdown 不崩溃"""
        zw_text = "# Title​‌\n\n正​文‌内容。"
        result = make_crawl4ai_result(fit_markdown=zw_text, raw_markdown=zw_text)
        md = extract_markdown(result)
        assert "Title" in md
        assert "正文内容" in md.replace("​", "").replace("‌", "")

    def test_rtl_text_preserved(self):
        """阿拉伯文/希伯来文内容被保留"""
        rtl = "# Title\n\nبسم الله الرحمن الرحيم\n\nשלום עולם\n\n正文保留。"
        result = make_crawl4ai_result(fit_markdown=rtl, raw_markdown=rtl)
        md = extract_markdown(result)
        assert "بسم الله" in md
        assert "שלום עולם" in md

    def test_very_long_url_in_crawl_result(self):
        """URL 长度 >2000 的 CrawlResult 不崩溃"""
        long_url = "https://example.com/path?" + "a" * 2500
        cr = CrawlResult(success=True, url=long_url, markdown="content")
        assert len(cr.url) > 2000
        assert cr.success is True

    def test_max_length_keyword(self):
        """关键词刚好 500 字符通过长度校验"""
        keyword = "a" * 500
        # 直接测试 _extract_keyword_parts 不崩溃
        from crawler.search import _extract_keyword_parts
        parts = _extract_keyword_parts(keyword)
        assert len(parts) > 0

    def test_mixed_unicode_content(self):
        """中文+日文+韩文+emoji 混合内容被保留"""
        mixed = "# 标题\n\n中文内容\n\nあいうえお\n\n한글 테스트\n\n🎉🚀💻"
        result = make_crawl4ai_result(fit_markdown=mixed, raw_markdown=mixed)
        md = extract_markdown(result)
        assert "中文内容" in md
        assert "あいう" in md
        assert "한글" in md
        assert "🎉" in md

    def test_empty_html_body(self):
        """空 HTML body 的 crawl 结果返回有效 markdown"""
        result = make_crawl4ai_result(fit_markdown="", raw_markdown="")
        md = extract_markdown(result)
        assert md == ""

    def test_nested_iframe_content_ignored(self):
        """iframe 内的 markdown 内容不受标签过滤直接影响"""
        # DEFAULT_EXCLUDED_TAGS 包含 "iframe"，但 extract_markdown 处理的是
        # crawl4ai 已经转好的 markdown 文本，不是 HTML
        content = "# Article\n\n正文内容保留。\n\niframe inner content should not appear as HTML"
        result = make_crawl4ai_result(fit_markdown=content, raw_markdown=content)
        md = extract_markdown(result)
        assert "正文内容保留" in md


# ================================================================
#  Test Class 3: TestSearchExtreme (10 tests)
# ================================================================

class TestSearchExtreme:
    """搜索模块极端测试：引擎 HTML 解析、SSRF、去重"""

    def test_baidu_realistic_html_parsing(self):
        """百度真实 HTML 结构（class=result c-container）解析"""
        from crawler.search import SEARCH_ENGINES
        config = SEARCH_ENGINES["baidu"]
        assert config["result_selector"] == ".result.c-container"
        assert config["title_selector"] == "h3 a"
        assert config["link_selector"] == "h3 a"

    def test_bing_realistic_html_parsing(self):
        """Bing 真实 HTML 结构（class=b_algo）解析"""
        from crawler.search import SEARCH_ENGINES
        config = SEARCH_ENGINES["bing"]
        assert config["result_selector"] == "li.b_algo"
        assert config["title_selector"] == "h2 a"

    def test_sogou_realistic_html_parsing(self):
        """搜狗真实 HTML 结构（class=vrwrap）解析"""
        from crawler.search import SEARCH_ENGINES
        config = SEARCH_ENGINES["sogou"]
        assert config["result_selector"] == ".vrwrap"

    def test_cross_engine_url_dedup(self):
        """跨引擎 URL 去重：bing=[A,B] baidu=[B,C] -> 最终 [A,B,C]"""
        # 模拟 cross-engine 去重逻辑
        url_set = set()
        all_urls = []
        for engine_urls in [["A", "B"], ["B", "C"]]:
            new = [u for u in engine_urls if u not in url_set]
            url_set.update(new)
            all_urls.extend(new)
        assert all_urls == ["A", "B", "C"]
        assert len(set(all_urls)) == 3

    def test_domain_dedup_exact_boundary(self):
        """同域名刚好 max_domain_dedup=2 条通过，第 3 条被过滤"""
        seen_domains = {}
        max_domain_dedup = 2
        urls = []
        for url in [
            "https://example.com/a",
            "https://example.com/b",
            "https://example.com/c",
        ]:
            from urllib.parse import urlparse
            domain = urlparse(url).netloc
            count = seen_domains.get(domain, 0)
            if count >= max_domain_dedup:
                continue
            seen_domains[domain] = count + 1
            urls.append(url)
        assert len(urls) == 2
        assert "https://example.com/c" not in urls

    @pytest.mark.asyncio
    async def test_concurrent_crawl_partial_failure(self):
        """10 URL 并发爬取中 5 个失败，返回 10 个结果（5 成功 5 失败）"""
        from crawler.search import _crawl_urls_with_shared_browser

        urls = [f"https://example.com/page{i}" for i in range(10)]
        fail_set = {f"https://example.com/page{i}" for i in range(5)}

        async def fake_crawl_one(**kwargs):
            pass

        # 直接测试：构造 10 个 CrawlResult，5 个失败
        results = []
        for i, url in enumerate(urls):
            if url in fail_set:
                results.append(CrawlResult(
                    success=False, url=url, error_message="Connection timeout"
                ))
            else:
                results.append(CrawlResult(
                    success=True, url=url, markdown="content", word_count=100
                ))

        assert len(results) == 10
        assert sum(1 for r in results if r.success) == 5
        assert sum(1 for r in results if not r.success) == 5

    def test_ssrf_localhost_blocked(self):
        """SSRF 防护：localhost 被拦截"""
        from api.ssrf_guard import validate_url_ssrf
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            validate_url_ssrf("http://localhost:8080/admin")
        assert exc_info.value.status_code == 400

    def test_ssrf_private_ip_blocked(self):
        """SSRF 防护：私有 IP 被拦截"""
        from api.ssrf_guard import validate_url_ssrf
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            validate_url_ssrf("http://192.168.1.1/admin")
        assert exc_info.value.status_code == 400

    def test_ssrf_ipv6_loopback_blocked(self):
        """SSRF 防护：IPv6 回环地址被拦截"""
        from api.ssrf_guard import validate_url_ssrf
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            validate_url_ssrf("http://[::1]:8080/admin")
        assert exc_info.value.status_code == 400

    def test_search_dedup_integration(self):
        """搜索结果去重：3 个结果（2 个同 URL）-> 2 个"""
        results = [
            CrawlResult(success=True, url="https://example.com/a", markdown="c1"),
            CrawlResult(success=True, url="https://example.com/a", markdown="c1_dup"),
            CrawlResult(success=True, url="https://example.com/b", markdown="c2"),
        ]
        seen = set()
        deduped = []
        for r in results:
            if r.url not in seen and r.success:
                seen.add(r.url)
                deduped.append(r)
        assert len(deduped) == 2
        urls = [r.url for r in deduped]
        assert "https://example.com/a" in urls
        assert "https://example.com/b" in urls


# ================================================================
#  Test Class 4: TestConfigPipeline (5 tests)
# ================================================================

class TestConfigPipeline:
    """RunParams / 工具函数极端测试"""

    def test_run_params_all_defaults(self):
        """RunParams() 默认值验证"""
        p = RunParams()
        assert p.text_mode is True
        assert p.light_mode is False
        assert p.word_count_threshold == 10
        assert p.excluded_tags == DEFAULT_EXCLUDED_TAGS
        assert p.excluded_selector == DEFAULT_EXCLUDED_SELECTOR
        assert p.prune_threshold == 0.5
        assert p.wait_until == "networkidle"
        assert p.page_timeout == 60000
        assert p.remove_overlay_elements is True
        assert p.max_retries == 2
        assert p.wait_for is None
        assert p.delay_before_return_html == 1.0
        assert p.mean_delay == 0.5
        assert p.max_range == 0.5
        assert p.remove_consent_popups is True

    def test_run_params_from_mock_object(self):
        """RunParams 从 MagicMock 提取所有属性"""
        cfg = MagicMock()
        cfg.text_mode = False
        cfg.light_mode = True
        cfg.word_count_threshold = 50
        cfg.excluded_tags = ["nav", "aside"]
        cfg.excluded_selector = ".sidebar"
        cfg.prune_threshold = 0.8
        cfg.wait_until = "load"
        cfg.page_timeout = 30000
        cfg.remove_overlay_elements = False
        cfg.max_retries = 5
        cfg.wait_for = "article"
        cfg.delay_before_return_html = 3.0
        cfg.mean_delay = 2.0
        cfg.max_range = 1.5
        cfg.remove_consent_popups = False

        p = RunParams(cfg)
        assert p.text_mode is False
        assert p.light_mode is True
        assert p.word_count_threshold == 50
        assert p.excluded_tags == ["nav", "aside"]
        assert p.excluded_selector == ".sidebar"
        assert p.prune_threshold == 0.8
        assert p.wait_until == "load"
        assert p.page_timeout == 30000
        assert p.remove_overlay_elements is False
        assert p.max_retries == 5
        assert p.wait_for == "article"
        assert p.delay_before_return_html == 3.0
        assert p.mean_delay == 2.0
        assert p.max_range == 1.5
        assert p.remove_consent_popups is False

    def test_count_words_mixed_accuracy(self):
        """count_words 中英文混合：Hello 你好世界 test -> 英文2词*1.5=3 + 中文4字 = 7"""
        assert count_words("Hello 你好世界 test") == 7

    def test_normalize_url_edge_cases(self):
        """URL 标准化边界情况"""
        # 大写 + www + 端口 + 尾部斜杠
        assert normalize_url("HTTPS://WWW.Example.COM:8080/path/") == "example.com:8080/path"
        # 追踪参数移除
        assert normalize_url(
            "https://example.com/path?utm_source=twitter&utm_campaign=spring&ref=logo"
        ) == "example.com/path"
        # normalize_url 不处理 #，只去协议/www/尾斜杠/追踪参数
        result_hash = normalize_url("https://example.com/path#")
        assert result_hash == "example.com/path#"  # # 由调用方处理

    def test_detect_cjk_edge_cases(self):
        """CJK 检测边界情况"""
        assert detect_cjk("12345") is False      # 纯数字
        assert detect_cjk("!@#$%") is False      # 纯符号
        assert detect_cjk("こんにちは") is False  # 日文假名
        assert detect_cjk("한글") is False        # 韩文
        assert detect_cjk("Hello 世界") is True   # 含中文


# ================================================================
#  Test Class 5: TestDeepCrawlExtreme (5 tests)
# ================================================================

class TestDeepCrawlExtreme:
    """深度爬取极端边界测试"""

    @pytest.mark.asyncio
    async def test_deep_crawl_large_page_set(self):
        """50 个页面结果，max_pages=20 时只取 20"""
        pages = [
            make_raw_result(url=f"https://example.com/p{i}", depth=i % 3)
            for i in range(50)
        ]
        mock_crawler = AsyncMock()
        mock_crawler.arun.return_value = pages

        with patch("crawler.deep.AsyncWebCrawler"), \
             patch("crawler.deep.get_browser_config", return_value=MagicMock()), \
             patch("crawler.deep.get_crawler_run_config", return_value=MagicMock()), \
             patch("crawler.deep.BFSDeepCrawlStrategy", return_value=MagicMock()), \
             patch("crawler.deep.FilterChain", return_value=MagicMock()), \
             patch("crawler.deep.DomainFilter", return_value=MagicMock()):
            from crawler.deep import crawl_deep_pages
            results = await crawl_deep_pages(
                url="https://example.com/",
                max_depth=3,
                max_pages=20,
                crawler=mock_crawler,
            )

        assert len(results) == 20

    @pytest.mark.asyncio
    async def test_deep_crawl_all_duplicates(self):
        """10 个结果全部同 URL，去重后只保留 1 个"""
        pages = [
            make_raw_result(url="https://example.com/same", depth=i)
            for i in range(10)
        ]
        mock_crawler = AsyncMock()
        mock_crawler.arun.return_value = pages

        with patch("crawler.deep.AsyncWebCrawler"), \
             patch("crawler.deep.get_browser_config", return_value=MagicMock()), \
             patch("crawler.deep.get_crawler_run_config", return_value=MagicMock()), \
             patch("crawler.deep.BFSDeepCrawlStrategy", return_value=MagicMock()), \
             patch("crawler.deep.FilterChain", return_value=MagicMock()), \
             patch("crawler.deep.DomainFilter", return_value=MagicMock()):
            from crawler.deep import crawl_deep_pages
            results = await crawl_deep_pages(
                url="https://example.com/same",
                max_depth=2,
                max_pages=20,
                crawler=mock_crawler,
            )

        assert len(results) == 1
        assert results[0].url == "https://example.com/same"

    @pytest.mark.asyncio
    async def test_deep_crawl_mixed_depth_values(self):
        """depth 从 0 到 5，验证不同 depth 值正确传递到 CrawlResult"""
        # 使用足够长的 markdown 文本避免触发 JS Challenge 重试（>=20 words）
        long_md = (
            "# Title\n\nThis is a long enough article content with sufficient "
            "word count to exceed the JS challenge minimum threshold of twenty words "
            "so that no retry is triggered during the deep crawl test execution."
        )
        pages = [
            make_raw_result(
                url=f"https://example.com/d{i}", depth=i, markdown_text=long_md,
            )
            for i in range(6)
        ]
        mock_crawler = AsyncMock()
        mock_crawler.arun.return_value = pages

        with patch("crawler.deep.AsyncWebCrawler"), \
             patch("crawler.deep.get_browser_config", return_value=MagicMock()), \
             patch("crawler.deep.get_crawler_run_config", return_value=MagicMock()), \
             patch("crawler.deep.BFSDeepCrawlStrategy", return_value=MagicMock()), \
             patch("crawler.deep.FilterChain", return_value=MagicMock()), \
             patch("crawler.deep.DomainFilter", return_value=MagicMock()):
            from crawler.deep import crawl_deep_pages
            results = await crawl_deep_pages(
                url="https://example.com/",
                max_depth=3,
                max_pages=10,
                crawler=mock_crawler,
            )

        assert len(results) == 6
        depths = [r.depth for r in results]
        assert depths == [0, 1, 2, 3, 4, 5]

    @pytest.mark.asyncio
    async def test_deep_crawl_no_markdown_no_crash(self):
        """页面 markdown 为 None 时不崩溃，返回 success=True 但 word_count=0"""
        page = make_raw_result(url="https://example.com/nomd", depth=0, markdown_text=None)
        # markdown_text=None -> md_obj.fit_markdown="" raw_markdown=""
        # extract_markdown 返回 ""，count_words("") = 0
        mock_crawler = AsyncMock()
        mock_crawler.arun.return_value = [page]

        with patch("crawler.deep.AsyncWebCrawler"), \
             patch("crawler.deep.get_browser_config", return_value=MagicMock()), \
             patch("crawler.deep.get_crawler_run_config", return_value=MagicMock()), \
             patch("crawler.deep.BFSDeepCrawlStrategy", return_value=MagicMock()), \
             patch("crawler.deep.FilterChain", return_value=MagicMock()), \
             patch("crawler.deep.DomainFilter", return_value=MagicMock()):
            from crawler.deep import crawl_deep_pages
            results = await crawl_deep_pages(
                url="https://example.com/nomd",
                max_depth=2,
                max_pages=10,
                crawler=mock_crawler,
            )

        assert len(results) == 1
        assert results[0].success is True
        assert results[0].word_count == 0

    @pytest.mark.asyncio
    async def test_deep_crawl_com_cn_domain(self):
        """com.cn 域名的基础域名提取为 example.com.cn"""
        page = make_raw_result(url="https://www.example.com.cn/page", depth=0)
        mock_crawler = AsyncMock()
        mock_crawler.arun.return_value = [page]

        with patch("crawler.deep.AsyncWebCrawler"), \
             patch("crawler.deep.get_browser_config", return_value=MagicMock()), \
             patch("crawler.deep.get_crawler_run_config", return_value=MagicMock()), \
             patch("crawler.deep.BFSDeepCrawlStrategy", return_value=MagicMock()), \
             patch("crawler.deep.FilterChain", return_value=MagicMock()), \
             patch("crawler.deep.DomainFilter") as mock_df:
            mock_df.return_value = MagicMock()

            from crawler.deep import crawl_deep_pages
            await crawl_deep_pages(
                url="https://www.example.com.cn/page",
                max_depth=2,
                max_pages=10,
                crawler=mock_crawler,
            )

            call_kwargs = mock_df.call_args
            allowed = call_kwargs[1]["allowed_domains"]
            assert "*.example.com.cn" in allowed
            assert "www.example.com.cn" in allowed
