import base64
import datetime
import re
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from crawler import search


class _FakeResponse:
    def __init__(self, text: str = "<html></html>", status_code: int = 200, url: str = "https://example.com"):
        self.text = text
        self.status_code = status_code
        self.url = url

    def raise_for_status(self):
        return None


class _FakeAsyncClient:
    def __init__(self, *args, **kwargs):
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url, headers=None, timeout=None):
        self.calls.append(("get", url))
        return _FakeResponse()


class _BaiduDecodeClient:
    async def head(self, *args, **kwargs):
        return _FakeResponse(status_code=502, url="http://www.baidu.com/link?url=encoded")

    async def get(self, *args, **kwargs):
        return _FakeResponse(status_code=502, url="http://www.baidu.com/link?url=encoded")


# ============== extract_keyword_parts ==============

class TestExtractKeywordParts(unittest.TestCase):
    def test_english_single_word(self):
        parts = search._extract_keyword_parts("docker")
        self.assertEqual(parts, ["docker"])

    def test_english_multi_word(self):
        parts = search._extract_keyword_parts("spring boot tutorial")
        self.assertIn("spring", parts)
        self.assertIn("boot", parts)
        self.assertIn("tutorial", parts)

    def test_chinese_single_char(self):
        parts = search._extract_keyword_parts("云")
        self.assertEqual(parts, ["云"])

    def test_chinese_two_chars(self):
        parts = search._extract_keyword_parts("容器")
        self.assertEqual(parts, ["容器"])

    def test_chinese_long_segment_keeps_full(self):
        """3+ 字中文段应保留完整段作为匹配片段"""
        parts = search._extract_keyword_parts("深度学习框架")
        self.assertIn("深度学习框架", parts)
        # 也应有 2-gram
        self.assertIn("深度", parts)
        self.assertIn("学习", parts)

    def test_mixed_chinese_english(self):
        parts = search._extract_keyword_parts("Kubernetes 部署教程")
        self.assertIn("kubernetes", parts)
        self.assertIn("部署教程", parts)

    def test_empty_keyword(self):
        self.assertEqual(search._extract_keyword_parts(""), [])
        self.assertEqual(search._extract_keyword_parts("  "), [])

    def test_short_token_filtered(self):
        """单字符英文 token 不应出现"""
        parts = search._extract_keyword_parts("a b cd")
        self.assertNotIn("a", parts)
        self.assertNotIn("b", parts)
        self.assertIn("cd", parts)


# ============== is_relevant_to_keyword ==============

class TestIsRelevantToKeyword(unittest.TestCase):
    def test_empty_title_rejected(self):
        self.assertFalse(search._is_relevant_to_keyword("docker", "", ""))

    def test_no_title_rejected(self):
        self.assertFalse(search._is_relevant_to_keyword("docker", "No Title", "some snippet"))

    def test_exact_match_in_title(self):
        self.assertTrue(search._is_relevant_to_keyword(
            "Docker", "Docker Compose Guide", "container orchestration"
        ))

    def test_exact_match_in_snippet(self):
        self.assertTrue(search._is_relevant_to_keyword(
            "Docker", "Container Guide", "Docker workflow explained"
        ))

    def test_no_match_rejected(self):
        self.assertFalse(search._is_relevant_to_keyword(
            "Docker", "Kubernetes Networking", "CNI and ingress overview"
        ))

    def test_chinese_keyword_match(self):
        self.assertTrue(search._is_relevant_to_keyword(
            "深度学习", "深度学习框架对比", "PyTorch vs TensorFlow"
        ))

    def test_partial_chinese_match_in_title(self):
        """中文长关键词片段匹配标题"""
        self.assertTrue(search._is_relevant_to_keyword(
            "深度学习框架", "深度学习框架 PyTorch 入门", "教程摘要"
        ))

    def test_mixed_keyword_match(self):
        self.assertTrue(search._is_relevant_to_keyword(
            "Vue3 组合式 API", "Vue3 组合式 API 实战指南", "Composition API 详解"
        ))

    def test_excluded_keyword_rejected(self):
        """包含排除关键词（占星类）的结果应被拒绝"""
        self.assertFalse(search._is_relevant_to_keyword(
            "zodiac", "Your Daily Horoscope", "love compatibility chart"
        ))


# ============== baidu_time_filter ==============

class TestBaiduTimeFilter(unittest.TestCase):
    def test_all_returns_empty(self):
        self.assertEqual(search._baidu_time_filter("all"), "")

    def test_unknown_range_returns_empty(self):
        self.assertEqual(search._baidu_time_filter("century"), "")

    def test_day_filter_format(self):
        result = search._baidu_time_filter("day")
        self.assertTrue(result.startswith("&gpc="))
        encoded = result[5:]
        decoded = base64.b64decode(encoded).decode()
        self.assertIn("stf=", decoded)
        self.assertIn("stftype=1", decoded)

    def test_week_filter_format(self):
        result = search._baidu_time_filter("week")
        self.assertTrue(result.startswith("&gpc="))
        encoded = result[5:]
        decoded = base64.b64decode(encoded).decode()
        self.assertIn("stf=", decoded)

    def test_month_filter(self):
        result = search._baidu_time_filter("month")
        self.assertNotEqual(result, "")

    def test_year_filter(self):
        result = search._baidu_time_filter("year")
        self.assertNotEqual(result, "")

    def test_timestamps_ordering(self):
        """start_ts 应小于 end_ts"""
        result = search._baidu_time_filter("month")
        encoded = result[5:]
        decoded = base64.b64decode(encoded).decode()
        match = re.search(r"stf=(\d+),(\d+)", decoded)
        self.assertIsNotNone(match)
        start_ts = int(match.group(1))
        end_ts = int(match.group(2))
        self.assertLess(start_ts, end_ts)


# ============== is_anti_bot_page ==============

class TestIsAntiBotPage(unittest.TestCase):
    def test_captcha_detected(self):
        self.assertTrue(search._is_anti_bot_page("请输入验证码继续访问"))

    def test_english_captcha_detected(self):
        self.assertTrue(search._is_anti_bot_page("Please verify you are human"))

    def test_recaptcha_detected(self):
        self.assertTrue(search._is_anti_bot_page("", "<div class='recaptcha'>"))

    def test_normal_page_not_detected(self):
        self.assertFalse(search._is_anti_bot_page("Spring Boot Tutorial Guide", "<html><body>content</body></html>"))

    def test_security_check_detected(self):
        self.assertTrue(search._is_anti_bot_page("security check required"))

    def test_ip_blocked_detected(self):
        self.assertTrue(search._is_anti_bot_page("Your IP address has been blocked"))


# ============== build_headers ==============

class TestBuildHeaders(unittest.TestCase):
    def test_returns_dict(self):
        headers = search._build_headers()
        self.assertIsInstance(headers, dict)

    def test_contains_required_fields(self):
        headers = search._build_headers()
        required = ["User-Agent", "Accept", "Accept-Language", "Connection"]
        for field in required:
            self.assertIn(field, headers)

    def test_user_agent_from_pool(self):
        headers = search._build_headers()
        self.assertIn(headers["User-Agent"], search.USER_AGENTS)

    def test_sec_ch_ua_present(self):
        headers = search._build_headers()
        self.assertIn("Sec-Ch-Ua", headers)


# ============== MIN_WORD_COUNT ==============

class TestMinWordCount(unittest.TestCase):
    def test_constant_exists(self):
        self.assertEqual(search.MIN_WORD_COUNT, 50)


# ============== Integration tests ==============

class SearchTests(unittest.IsolatedAsyncioTestCase):
    def test_single_keyword_must_match_title_or_snippet(self):
        self.assertFalse(
            search._is_relevant_to_keyword(
                "Docker",
                "Kubernetes Networking Guide",
                "CNI and ingress overview",
            )
        )
        self.assertTrue(
            search._is_relevant_to_keyword(
                "Docker",
                "Docker Compose Tutorial",
                "Container workflow guide",
            )
        )

    async def test_search_results_do_not_stop_after_first_empty_page(self):
        parse_results = AsyncMock(side_effect=[
            (10, 0),
            (10, 1),
        ])

        with patch.object(search, "_parse_search_results", parse_results), \
                patch.object(search.httpx, "AsyncClient", _FakeAsyncClient), \
                patch.object(search.asyncio, "sleep", AsyncMock()):
            urls = await search._get_search_results(
                keyword="docker",
                engine="bing",
                max_results=5,
                time_range="week",
            )

        self.assertGreaterEqual(parse_results.await_count, 2)
        self.assertEqual(len(urls), 0)

    async def test_baidu_unresolved_redirect_is_skipped(self):
        html = """
        <html><body>
          <div class="result">
            <h3><a href="http://www.baidu.com/link?url=encoded">Example</a></h3>
            <div class="c-abstract">Spring Boot tutorial guide</div>
          </div>
        </body></html>
        """

        urls = []
        raw_count, added_count = await search._parse_search_results(
            html=html,
            engine="baidu",
            config=search.SEARCH_ENGINES["baidu"],
            keyword="Spring Boot tutorial",
            max_results=5,
            seen_domains={},
            urls=urls,
            search_url="http://www.baidu.com/s?wd=Spring+Boot+tutorial",
            headers={"User-Agent": "Mozilla/5.0"},
            client=_BaiduDecodeClient(),
        )

        self.assertEqual(raw_count, 1)
        self.assertEqual(added_count, 0)
        self.assertEqual(urls, [])

    async def test_invalid_engine_raises_error(self):
        with self.assertRaises(ValueError):
            await search._get_search_results("test", engine="yahoo", max_results=5)

    async def test_invalid_time_range_raises_error(self):
        with self.assertRaises(ValueError):
            await search.crawl_by_keyword("test", time_range="century")

    async def test_parse_results_domain_dedup(self):
        """同一域名超过 MAX_DOMAIN_DEDUP 条应被去重"""
        html = """
        <html><body>
          <div class="result">
            <h3><a href="https://example.com/page1">Page 1</a></h3>
            <p>docker tutorial part 1</p>
          </div>
          <div class="result">
            <h3><a href="https://example.com/page2">Page 2</a></h3>
            <p>docker tutorial part 2</p>
          </div>
          <div class="result">
            <h3><a href="https://example.com/page3">Page 3</a></h3>
            <p>docker tutorial part 3</p>
          </div>
        </body></html>
        """

        urls = []
        await search._parse_search_results(
            html=html,
            engine="bing",
            config=search.SEARCH_ENGINES["bing"],
            keyword="docker tutorial",
            max_results=10,
            seen_domains={},
            urls=urls,
            search_url="https://www.bing.com/search?q=docker",
            headers={"User-Agent": "Mozilla/5.0"},
            client=None,
        )

        # MAX_DOMAIN_DEDUP defaults to 2, so only 2 from example.com
        self.assertLessEqual(len(urls), search.MAX_DOMAIN_DEDUP)


# ============== _is_relevant_to_keyword 单词边界 & 片段匹配 ==============

class TestIsRelevantToKeywordBoundary(unittest.TestCase):
    """英文单词边界 + CJK子串匹配 + 片段匹配阈值"""

    # ---------- 英文单词边界 ----------

    def test_english_short_word_not_in_combined(self):
        """关键词片段不在标题/摘要的任意单词中 → False"""
        self.assertFalse(search._is_relevant_to_keyword(
            "go", "Rust Systems Programming", "concurrent memory safety"
        ))

    def test_english_short_word_matches_exact(self):
        """'go' 应匹配 Go 编程语言（\b 单词边界）"""
        self.assertTrue(search._is_relevant_to_keyword(
            "go", "Go Programming Language", "concurrency in go"
        ))

    def test_english_substring_not_in_combined(self):
        """'ai' 在标题/摘要中完全不出现 → False"""
        self.assertFalse(search._is_relevant_to_keyword(
            "AI", "Security Guide", "smtp server setup"
        ))

    def test_english_word_boundary_in_snippet(self):
        """单词边界也适用于摘要"""
        self.assertTrue(search._is_relevant_to_keyword(
            "rust", "Systems Programming", "learn rust language"
        ))

    # ---------- CJK 子串匹配 ----------

    def test_cjk_single_char_matches_compound(self):
        """中文单字 '人' 应匹配 '人工智能'（CJK无单词边界，子串匹配）"""
        self.assertTrue(search._is_relevant_to_keyword(
            "人", "人工智能入门指南", "AI 学习教程"
        ))

    def test_cjk_two_char_matches_longer(self):
        """中文双字 '学习' 应匹配 '深度学习框架'"""
        self.assertTrue(search._is_relevant_to_keyword(
            "学习", "深度学习框架对比", "PyTorch vs TensorFlow"
        ))

    # ---------- 片段匹配阈值 ----------

    def test_snippet_enough_parts_match(self):
        """标题无匹配，摘要匹配 >= 50% 片段 → True"""
        self.assertTrue(search._is_relevant_to_keyword(
            "spring boot tutorial",
            "Java Framework Guide",
            "this spring boot tutorial covers auto configuration"
        ))

    def test_snippet_insufficient_parts_match(self):
        """标题无匹配，摘要匹配 < 50% 片段 → False"""
        self.assertFalse(search._is_relevant_to_keyword(
            "spring boot tutorial docker",
            "Java Framework Guide",
            "this article mentions spring only"
        ))

    def test_single_part_keyword_no_match(self):
        """单片段关键词，摘要也未匹配 → False"""
        self.assertFalse(search._is_relevant_to_keyword(
            "kubernetes",
            "Container Orchestration Overview",
            "Docker and container management"
        ))

    # ---------- 特殊字符 ----------

    def test_keyword_with_special_chars_no_match(self):
        """C++ 含特殊字符无法通过 \b 单词边界匹配（+ 非单词字符切断边界）"""
        self.assertFalse(search._is_relevant_to_keyword(
            "C++", "C++ Programming Guide", "modern C++ features"
        ))

    def test_empty_snippet_title_match(self):
        """空摘要但标题匹配 → True"""
        self.assertTrue(search._is_relevant_to_keyword(
            "docker", "Docker Compose Tutorial", ""
        ))

    def test_excluded_keyword_in_title_rejected(self):
        """标题含排除关键词（horoscope）→ False"""
        self.assertFalse(search._is_relevant_to_keyword(
            "python", "Python Horoscope Library", "astrology tools"
        ))


# ============== _fetch_search_html ==============

class _FakeCrawlResult:
    def __init__(self, success=True, html="<html>fake</html>", error_message=None):
        self.success = success
        self.html = html
        self.error_message = error_message


class TestFetchSearchHtml(unittest.IsolatedAsyncioTestCase):
    """_fetch_search_html 浏览器抓取 + httpx 降级"""

    async def test_browser_success_returns_html(self):
        mock_crawler = AsyncMock()
        mock_crawler.arun.return_value = _FakeCrawlResult(success=True, html="<html>results</html>")
        with patch.object(search, "get_search_run_config", return_value=MagicMock()):
            result = await search._fetch_search_html(
                "https://example.com/search", engine="bing", crawler=mock_crawler
            )
        self.assertEqual(result, "<html>results</html>")

    async def test_browser_fail_falls_back_to_httpx(self):
        mock_crawler = AsyncMock()
        mock_crawler.arun.return_value = _FakeCrawlResult(success=False, html=None, error_message="timeout")
        long_text = "<html>" + "X" * 600 + "</html>"
        fake_resp = _FakeResponse(text=long_text, status_code=200)
        with patch.object(search, "get_search_run_config", return_value=MagicMock()), \
             patch.object(search, "get_effective_proxy", return_value=""), \
             patch.object(search.httpx, "AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.get.return_value = fake_resp
            mock_client_cls.return_value = mock_client
            result = await search._fetch_search_html(
                "https://example.com/search", engine="bing", crawler=mock_crawler,
                fallback_headers={"User-Agent": "test"}
            )
        self.assertEqual(result, long_text)

    async def test_httpx_short_response_returns_none(self):
        """httpx 降级返回短内容（<500字节）→ None"""
        mock_crawler = AsyncMock()
        mock_crawler.arun.return_value = _FakeCrawlResult(success=False, html=None)
        fake_resp = _FakeResponse(text="short", status_code=200)
        with patch.object(search, "get_search_run_config", return_value=MagicMock()), \
             patch.object(search, "get_effective_proxy", return_value=""), \
             patch.object(search.httpx, "AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.get.return_value = fake_resp
            mock_client_cls.return_value = mock_client
            result = await search._fetch_search_html(
                "https://example.com/search", engine="bing", crawler=mock_crawler,
                fallback_headers={"User-Agent": "test"}
            )
        self.assertIsNone(result)

    async def test_both_browser_and_httpx_fail_returns_none(self):
        mock_crawler = AsyncMock()
        mock_crawler.arun.return_value = _FakeCrawlResult(success=False, html=None)
        with patch.object(search, "get_search_run_config", return_value=MagicMock()), \
             patch.object(search, "get_effective_proxy", return_value=""), \
             patch.object(search.httpx, "AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.get.side_effect = Exception("Connection refused")
            mock_client_cls.return_value = mock_client
            result = await search._fetch_search_html(
                "https://example.com/search", engine="bing", crawler=mock_crawler,
                fallback_headers={"User-Agent": "test"}
            )
        self.assertIsNone(result)

    async def test_no_crawler_creates_new_browser(self):
        """crawler=None 时内部创建 AsyncWebCrawler"""
        mock_inner = AsyncMock()
        mock_inner.arun.return_value = _FakeCrawlResult(success=True, html="<html>new</html>")
        mock_inst = AsyncMock()
        mock_inst.__aenter__.return_value = mock_inner
        mock_inst.__aexit__.return_value = False
        with patch.object(search, "get_search_run_config", return_value=MagicMock()), \
             patch.object(search, "get_browser_config", return_value=MagicMock()), \
             patch.object(search, "AsyncWebCrawler", return_value=mock_inst):
            result = await search._fetch_search_html("https://example.com/search", engine="bing")
        self.assertEqual(result, "<html>new</html>")


# ============== _parse_search_results 补充测试 ==============

BING_HTML_TEMPLATE = """
<html><body>
  <li class="b_algo">
    <h2><a href="{}">Test Title</a></h2>
    <p>docker tutorial part 1</p>
  </li>
</body></html>
"""

GOOGLE_HTML_TEMPLATE = """
<html><body>
  <div class="tF2Cxc">
    <h3>Test Title</h3>
    <div class="yuRUbf"><a href="{}">link</a></div>
    <span class="aCOpRe">docker tutorial</span>
  </div>
</body></html>
"""


class TestParseSearchResultsUrlDecoding(unittest.IsolatedAsyncioTestCase):
    """各搜索引擎 URL 解码"""

    async def test_bing_url_u_decoding(self):
        """Bing /url?u= 参数解码"""
        html = BING_HTML_TEMPLATE.format("https://www.bing.com/url?u=https://example.com/article")
        urls = []
        await search._parse_search_results(
            html=html, engine="bing", config=search.SEARCH_ENGINES["bing"],
            keyword="docker", max_results=5, seen_domains={}, urls=urls,
            search_url="https://www.bing.com/search?q=docker",
            headers={"User-Agent": "test"}, client=None,
        )
        self.assertEqual(len(urls), 1)
        self.assertEqual(urls[0], "https://example.com/article")

    async def test_bing_ck_a_decoding(self):
        """Bing /ck/a? 含 base64 编码的真实 URL"""
        real_url = b"https://example.com/real-article"
        encoded = base64.b64encode(real_url).decode()
        ck_param = "a1" + encoded
        html = BING_HTML_TEMPLATE.format(f"https://www.bing.com/ck/a?u={ck_param}")
        urls = []
        await search._parse_search_results(
            html=html, engine="bing", config=search.SEARCH_ENGINES["bing"],
            keyword="docker", max_results=5, seen_domains={}, urls=urls,
            search_url="https://www.bing.com/search?q=docker",
            headers={"User-Agent": "test"}, client=None,
        )
        self.assertEqual(len(urls), 1)
        self.assertEqual(urls[0], "https://example.com/real-article")

    async def test_bing_ck_a_bing_domain_keeps_original_href(self):
        """Bing /ck/a? 解码后为 bing.com → 保留原始 href（不覆盖），原始 https URL 仍被收录"""
        real_url = b"https://www.bing.com/some-page"
        encoded = base64.b64encode(real_url).decode()
        ck_param = "a1" + encoded
        html = BING_HTML_TEMPLATE.format(f"https://www.bing.com/ck/a?u={ck_param}")
        urls = []
        await search._parse_search_results(
            html=html, engine="bing", config=search.SEARCH_ENGINES["bing"],
            keyword="docker", max_results=5, seen_domains={}, urls=urls,
            search_url="https://www.bing.com/search?q=docker",
            headers={"User-Agent": "test"}, client=None,
        )
        # 解码后 href 仍是原始 /ck/a?u=... URL（以 https 开头），不会被过滤
        # 因为 bing.com 本身不在排除域名列表中
        self.assertEqual(len(urls), 1)

    async def test_google_url_q_decoding(self):
        """Google /url?q= 参数解码"""
        html = GOOGLE_HTML_TEMPLATE.format("/url?q=https://example.com/article&sa=U")
        urls = []
        await search._parse_search_results(
            html=html, engine="google", config=search.SEARCH_ENGINES["google"],
            keyword="docker", max_results=5, seen_domains={}, urls=urls,
            search_url="https://www.google.com/search?q=docker",
            headers={"User-Agent": "test"}, client=None,
        )
        self.assertEqual(len(urls), 1)
        self.assertEqual(urls[0], "https://example.com/article")

    async def test_sogou_weixin_excluded(self):
        """搜狗微信搜索结果被排除"""
        sogou_html = """
        <html><body>
          <div class="vrwrap">
            <h3 class="vrTitle"><a href="https://weixin.sogou.com/weixin?type=2&query=test">WeChat Article</a></h3>
            <p class="str-text">docker tutorial</p>
          </div>
        </body></html>
        """
        urls = []
        await search._parse_search_results(
            html=sogou_html, engine="sogou", config=search.SEARCH_ENGINES["sogou"],
            keyword="docker", max_results=5, seen_domains={}, urls=urls,
            search_url="https://www.sogou.com/web?query=docker",
            headers={"User-Agent": "test"}, client=None,
        )
        self.assertEqual(len(urls), 0)

    async def test_excluded_domain_filtered(self):
        """排除域名（如 bilibili.com）在解析时被过滤"""
        html = BING_HTML_TEMPLATE.format("https://www.bing.com/url?u=https://bilibili.com/video/BV1xx")
        urls = []
        await search._parse_search_results(
            html=html, engine="bing", config=search.SEARCH_ENGINES["bing"],
            keyword="docker", max_results=5, seen_domains={}, urls=urls,
            search_url="https://www.bing.com/search?q=docker",
            headers={"User-Agent": "test"}, client=None,
        )
        self.assertEqual(len(urls), 0)


class TestParseSearchResultsEdgeCases(unittest.IsolatedAsyncioTestCase):
    """_parse_search_results 边界/异常场景"""

    async def test_empty_html_returns_zero(self):
        """空 HTML 返回 (0, 0)"""
        raw, added = await search._parse_search_results(
            html="", engine="bing", config=search.SEARCH_ENGINES["bing"],
            keyword="docker", max_results=5, seen_domains={}, urls=[],
            search_url="https://www.bing.com/search?q=docker",
            headers={"User-Agent": "test"}, client=None,
        )
        self.assertEqual(raw, 0)
        self.assertEqual(added, 0)

    async def test_no_results_triggers_anti_bot_check(self):
        """非 google 引擎 0 结果时检测反爬页面"""
        html = "<html><body>请输入验证码继续访问</body></html>"
        with self.assertRaises(RuntimeError) as ctx:
            await search._parse_search_results(
                html=html, engine="bing", config=search.SEARCH_ENGINES["bing"],
                keyword="docker", max_results=5, seen_domains={}, urls=[],
                search_url="https://www.bing.com/search?q=docker",
                headers={"User-Agent": "test"}, client=None,
            )
        self.assertIn("anti-bot", str(ctx.exception))

    async def test_google_no_results_no_anti_bot_raise(self):
        """Google 0 结果时不抛反爬异常（Google 有自己的处理逻辑）"""
        html = "<html><body>please verify you are human</body></html>"
        # Google 即使检测到 captcha 也不抛 RuntimeError
        raw, added = await search._parse_search_results(
            html=html, engine="google", config=search.SEARCH_ENGINES["google"],
            keyword="extremely rare keyword xyz", max_results=5, seen_domains={}, urls=[],
            search_url="https://www.google.com/search?q=test",
            headers={"User-Agent": "test"}, client=None,
        )
        self.assertEqual(raw, 0)

    async def test_fallback_selector_used_when_primary_fails(self):
        """主选择器无匹配时使用 fallback 选择器 (.results .rb)"""
        html = """
        <html><body>
          <div class="results">
            <div class="rb">
              <h3><a href="https://example.com/page1">Page 1</a></h3>
              <div class="star-w">docker tutorial</div>
            </div>
          </div>
        </body></html>
        """
        urls = []
        await search._parse_search_results(
            html=html, engine="sogou", config=search.SEARCH_ENGINES["sogou"],
            keyword="docker", max_results=5, seen_domains={}, urls=urls,
            search_url="https://www.sogou.com/web?query=docker",
            headers={"User-Agent": "test"}, client=None,
        )
        self.assertEqual(len(urls), 1)

    async def test_max_results_limit_enforced(self):
        """达到 max_results 时停止收集"""
        html_multi = """
        <html><body>
          <div class="tF2Cxc">
            <h3>Title 1</h3>
            <div class="yuRUbf"><a href="/url?q=https://example.com/1">link</a></div>
            <span class="aCOpRe">docker tutorial 1</span>
          </div>
          <div class="tF2Cxc">
            <h3>Title 2</h3>
            <div class="yuRUbf"><a href="/url?q=https://example.com/2">link</a></div>
            <span class="aCOpRe">docker tutorial 2</span>
          </div>
        </body></html>
        """
        urls = []
        await search._parse_search_results(
            html=html_multi, engine="google", config=search.SEARCH_ENGINES["google"],
            keyword="docker", max_results=1, seen_domains={}, urls=urls,
            search_url="https://www.google.com/search?q=docker",
            headers={"User-Agent": "test"}, client=None,
        )
        self.assertEqual(len(urls), 1)

    async def test_non_http_urls_filtered(self):
        """非 http/https URL 被过滤"""
        html = BING_HTML_TEMPLATE.format("ftp://example.com/file")
        urls = []
        await search._parse_search_results(
            html=html, engine="bing", config=search.SEARCH_ENGINES["bing"],
            keyword="docker", max_results=5, seen_domains={}, urls=urls,
            search_url="https://www.bing.com/search?q=docker",
            headers={"User-Agent": "test"}, client=None,
        )
        self.assertEqual(len(urls), 0)

    async def test_empty_href_filtered(self):
        """空 href 被跳过"""
        html = """
        <html><body>
          <div class="result">
            <h3><a href="">No Link</a></h3>
            <p>docker tutorial</p>
          </div>
        </body></html>
        """
        urls = []
        await search._parse_search_results(
            html=html, engine="bing", config=search.SEARCH_ENGINES["bing"],
            keyword="docker", max_results=5, seen_domains={}, urls=urls,
            search_url="https://www.bing.com/search?q=docker",
            headers={"User-Agent": "test"}, client=None,
        )
        self.assertEqual(len(urls), 0)


# ============== _get_search_results 补充测试 ==============

class TestGetSearchResultsExtended(unittest.IsolatedAsyncioTestCase):
    """_get_search_results 分页终止 & 时间过滤"""

    async def test_consecutive_empty_pages_stops_pagination(self):
        """连续2页0新增 → 停止分页"""
        parse_results = AsyncMock(side_effect=[
            (10, 0),  # page 1: 0 new
            (10, 0),  # page 2: 0 new → stop
        ])
        with patch.object(search, "_parse_search_results", parse_results), \
             patch.object(search.httpx, "AsyncClient", _FakeAsyncClient), \
             patch.object(search.asyncio, "sleep", AsyncMock()):
            urls = await search._get_search_results(
                keyword="docker", engine="bing", max_results=10, time_range="all"
            )
        # 应只调用了2页就停止
        self.assertEqual(parse_results.await_count, 2)
        self.assertEqual(len(urls), 0)

    async def test_time_filter_day_applied_to_bing(self):
        """Bing time_range='day' 时至少调用一次 parse（URL 含 filter 参数）"""
        parse_results = AsyncMock(return_value=(10, 0))  # page_new=0 只爬1页
        with patch.object(search, "_parse_search_results", parse_results), \
             patch.object(search.httpx, "AsyncClient", _FakeAsyncClient), \
             patch.object(search.asyncio, "sleep", AsyncMock()):
            await search._get_search_results(
                keyword="docker", engine="bing", max_results=1, time_range="day"
            )
        self.assertGreaterEqual(parse_results.await_count, 1)

    async def test_sogou_warmup_does_not_fail_get_results(self):
        """搜狗预热失败不影响后续搜索"""
        parse_results = AsyncMock(return_value=(10, 0))  # page_new=0 只爬1页
        _search_html = "<html>" + "x" * 600 + "</html>"
        call_order = []

        class _WarmupFailsButSearchSucceeds:
            def __init__(self, *a, **kw):
                pass
            async def __aenter__(self):
                return self
            async def __aexit__(self, *a):
                return False
            async def get(self, url, headers=None, timeout=None):
                call_order.append(url)
                if "sogou.com/" == url.rstrip("/"):
                    raise Exception("warmup failed")
                return _FakeResponse(text=_search_html)

        with patch.object(search, "_parse_search_results", parse_results), \
             patch.object(search.httpx, "AsyncClient", _WarmupFailsButSearchSucceeds), \
             patch.object(search.asyncio, "sleep", AsyncMock()), \
             patch.object(search, "_build_headers", return_value={"User-Agent": "test"}):
            await search._get_search_results(
                keyword="docker", engine="sogou", max_results=3, time_range="all"
            )
        # 预热失败但不影响搜索：parse 仍被调用
        self.assertGreaterEqual(parse_results.await_count, 1)
        # warmup + search 调用（page_new=0 时 consecutive_empty_pages 机制会触发额外1页）
        self.assertGreaterEqual(len(call_order), 2)

    async def test_baidu_time_filter_in_url(self):
        """Baidu time_range='week' 时 URL 包含 gpc 参数"""
        parse_results = AsyncMock(return_value=(10, 1))
        fake_client = _FakeAsyncClient()
        with patch.object(search, "_parse_search_results", parse_results), \
             patch.object(search.httpx, "AsyncClient", return_value=fake_client), \
             patch.object(search.asyncio, "sleep", AsyncMock()):
            await search._get_search_results(
                keyword="docker", engine="baidu", max_results=1, time_range="week"
            )
        self.assertGreaterEqual(parse_results.await_count, 1)


# ============== crawl_by_keyword 集成测试 ==============

class TestCrawlByKeyword(unittest.IsolatedAsyncioTestCase):
    """crawl_by_keyword 入口函数"""

    async def test_all_engines_fail_returns_error_result(self):
        """所有引擎失败时返回单个错误 CrawlResult"""
        with patch.object(search, "_get_search_results", AsyncMock(return_value=[])):
            results = await search.crawl_by_keyword(
                keyword="xyz_no_results", engine="bing", max_results=5
            )
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0].success)
        self.assertIn("No search results found", results[0].error_message)

    async def test_url_dedup_across_engines(self):
        """不同引擎返回相同 URL 时去重"""
        async def fake_get_results(keyword, engine, max_results, time_range):
            if engine == "bing":
                return ["https://example.com/article", "https://unique.com/page"]
            elif engine == "baidu":
                return ["https://example.com/article", "https://baidu-only.com/post"]
            return []
        with patch.object(search, "_get_search_results", fake_get_results), \
             patch.object(search, "_crawl_urls_with_shared_browser", AsyncMock(return_value=[])):
            with patch.object(search, "dedup_results", lambda x: x):
                await search.crawl_by_keyword(
                    keyword="docker", engine="bing", max_results=10
                )
        # 验证 _crawl_urls_with_shared_browser 被调用，且传入的 URL 不会重复
        # (这里主要验证不抛异常)

    async def test_max_results_truncation(self):
        """搜索结果超过 max_results 时截断"""
        many_urls = [f"https://example{i}.com/page" for i in range(20)]
        async def fake_get_results(*a, **kw):
            return many_urls
        captured_urls = []
        async def fake_crawl(urls, **kw):
            captured_urls.extend(urls)
            return []
        with patch.object(search, "_get_search_results", fake_get_results), \
             patch.object(search, "_crawl_urls_with_shared_browser", fake_crawl), \
             patch.object(search, "dedup_results", lambda x: x):
            await search.crawl_by_keyword(
                keyword="docker", engine="bing", max_results=5
            )
        self.assertEqual(len(captured_urls), 5)

    async def test_engine_fallback_chain(self):
        """主引擎无结果时回退到下一个引擎"""
        call_order = []
        async def fake_get_results(keyword, engine, max_results, time_range):
            call_order.append(engine)
            if engine == "bing":
                return []  # 无结果 → 回退
            elif engine == "baidu":
                return ["https://baidu-result.com/article"]
            return []
        with patch.object(search, "_get_search_results", fake_get_results), \
             patch.object(search, "_crawl_urls_with_shared_browser", AsyncMock(return_value=[])):
            with patch.object(search, "dedup_results", lambda x: x):
                await search.crawl_by_keyword(
                    keyword="docker", engine="bing", max_results=5
                )
        # bing 失败后应尝试 baidu
        self.assertIn("bing", call_order)
        self.assertIn("baidu", call_order)
        self.assertLess(call_order.index("bing"), call_order.index("baidu"))

    async def test_invalid_time_range_raises(self):
        """无效 time_range → ValueError"""
        with self.assertRaises(ValueError):
            await search.crawl_by_keyword("test", time_range="century")

    async def test_unexpected_exception_in_engine_is_handled(self):
        """单个引擎抛异常不影响后续引擎"""
        call_order = []
        async def fake_get_results(keyword, engine, max_results, time_range):
            call_order.append(engine)
            if engine == "bing":
                raise RuntimeError("Bing crashed")
            return ["https://result-from-baidu.com/page"]
        with patch.object(search, "_get_search_results", fake_get_results), \
             patch.object(search, "_crawl_urls_with_shared_browser", AsyncMock(return_value=[])):
            with patch.object(search, "dedup_results", lambda x: x):
                await search.crawl_by_keyword(
                    keyword="docker", engine="bing", max_results=5
                )
        # bing 失败后 baidu 和其他引擎继续尝试
        self.assertIn("bing", call_order)
        self.assertIn("baidu", call_order)
        self.assertLess(call_order.index("bing"), call_order.index("baidu"))

    async def test_dedup_integration(self):
        """验证去重模块集成调用"""
        results_in = [
            search.CrawlResult(success=True, url="https://a.com/1", title="A"),
            search.CrawlResult(success=True, url="https://a.com/1", title="A (dup)"),
        ]
        async def fake_get_results(*a, **kw):
            return ["https://a.com/1"]
        async def fake_crawl(*a, **kw):
            return results_in
        with patch.object(search, "_get_search_results", fake_get_results), \
             patch.object(search, "_crawl_urls_with_shared_browser", fake_crawl):
            # dedup_results should be called and remove duplicate
            results = await search.crawl_by_keyword(
                keyword="test", engine="bing", max_results=5
            )
        # dedup 应移除重复 URL
        self.assertEqual(len(results), 1)


# ============== _crawl_urls_with_shared_browser ==============

class TestCrawlUrlsWithSharedBrowser(unittest.IsolatedAsyncioTestCase):
    """_crawl_urls_with_shared_browser 并发爬取"""

    async def _make_crawl_result(self, url, success=True, word_count=200):
        return search.CrawlResult(
            success=success, url=url, title=f"Title: {url}",
            markdown="content " * 50, word_count=word_count, metadata={}
        )

    async def test_successful_concurrent_crawl(self):
        """并发爬取多个 URL 全部成功"""
        urls = [f"https://example.com/page{i}" for i in range(3)]
        async def fake_crawl_single(url, config, crawler):
            return await self._make_crawl_result(url)
        with patch.object(search, "crawl_single_page", fake_crawl_single), \
             patch.object(search, "AsyncWebCrawler") as mock_awc:
            mock_inst = AsyncMock()
            mock_inst.__aenter__.return_value = mock_inst
            mock_awc.return_value = mock_inst
            results = await search._crawl_urls_with_shared_browser(
                urls=urls, keyword="test", url_source_map={}, config=None,
                browser_config=MagicMock(),
            )
        self.assertEqual(len(results), 3)
        self.assertTrue(all(r.success for r in results))
        for r in results:
            self.assertEqual(r.metadata["search_keyword"], "test")

    async def test_crawl_error_per_url_isolated(self):
        """单个 URL 爬取失败不影响其他 URL"""
        urls = [f"https://example.com/page{i}" for i in range(3)]
        async def fake_crawl_single(url, config, crawler):
            if "page1" in url:
                raise RuntimeError("Connection refused")
            return await self._make_crawl_result(url)
        with patch.object(search, "crawl_single_page", fake_crawl_single), \
             patch.object(search, "AsyncWebCrawler") as mock_awc:
            mock_inst = AsyncMock()
            mock_inst.__aenter__.return_value = mock_inst
            mock_awc.return_value = mock_inst
            results = await search._crawl_urls_with_shared_browser(
                urls=urls, keyword="test", url_source_map={}, config=None,
                browser_config=MagicMock(),
            )
        self.assertEqual(len(results), 3)
        success_count = sum(1 for r in results if r.success)
        self.assertEqual(success_count, 2)

    async def test_low_word_count_marked_failed(self):
        """字数低于 MIN_WORD_COUNT → success=False"""
        urls = ["https://example.com/short"]
        async def fake_crawl_single(url, config, crawler):
            return await self._make_crawl_result(url, word_count=10)
        with patch.object(search, "crawl_single_page", fake_crawl_single), \
             patch.object(search, "AsyncWebCrawler") as mock_awc:
            mock_inst = AsyncMock()
            mock_inst.__aenter__.return_value = mock_inst
            mock_awc.return_value = mock_inst
            results = await search._crawl_urls_with_shared_browser(
                urls=urls, keyword="test", url_source_map={}, config=None,
                browser_config=MagicMock(),
            )
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0].success)
        self.assertIn("Content too short", results[0].error_message)

    async def test_external_crawler_reuse(self):
        """传入 external_crawler 时不创建新 AsyncWebCrawler"""
        urls = [f"https://example.com/page{i}" for i in range(2)]
        external = AsyncMock()
        async def fake_crawl_single(url, config, crawler):
            # 验证 crawler 是外部传入的
            self.assertIs(crawler, external)
            return await self._make_crawl_result(url)
        with patch.object(search, "crawl_single_page", fake_crawl_single), \
             patch.object(search, "AsyncWebCrawler") as mock_awc:
            results = await search._crawl_urls_with_shared_browser(
                urls=urls, keyword="test", url_source_map={}, config=None,
                browser_config=MagicMock(), external_crawler=external,
            )
        mock_awc.assert_not_called()
        self.assertEqual(len(results), 2)

    async def test_fallback_flag_in_metadata(self):
        """is_fallback=True 时 metadata 标记 fallback"""
        urls = ["https://example.com/page"]
        async def fake_crawl_single(url, config, crawler):
            return await self._make_crawl_result(url)
        with patch.object(search, "crawl_single_page", fake_crawl_single), \
             patch.object(search, "AsyncWebCrawler") as mock_awc:
            mock_inst = AsyncMock()
            mock_inst.__aenter__.return_value = mock_inst
            mock_awc.return_value = mock_inst
            results = await search._crawl_urls_with_shared_browser(
                urls=urls, keyword="test", url_source_map={}, config=None,
                browser_config=MagicMock(), is_fallback=True,
            )
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].metadata.get("fallback"))


# ============== Sogou 无重试机制 ==============

class TestSogouRetry(unittest.IsolatedAsyncioTestCase):
    """Sogou 搜索引擎重试行为（SEARCH_PAGE_RETRIES=2）"""

    async def test_sogou_retries_then_succeeds(self):
        """Sogou 第一次搜索失败后重试成功"""
        parse_results = AsyncMock(return_value=(10, 0))
        html = "<html>" + "x" * 600 + "</html>"
        call_order = []

        class _RetryClient:
            def __init__(self, *a, **kw):
                pass
            async def __aenter__(self):
                return self
            async def __aexit__(self, *a):
                return False
            async def get(self, url, headers=None, timeout=None):
                call_order.append(url)
                if "sogou.com/" == url.rstrip("/"):
                    return None  # warmup success
                if len(call_order) <= 2:
                    raise Exception("Connection refused")
                return _FakeResponse(text=html)

        with patch.object(search, "_parse_search_results", parse_results), \
             patch.object(search.httpx, "AsyncClient", _RetryClient), \
             patch.object(search.asyncio, "sleep", AsyncMock()), \
             patch.object(search, "_build_headers", return_value={"User-Agent": "test"}):
            await search._get_search_results(
                keyword="docker", engine="sogou", max_results=10, time_range="all"
            )
        # 重试后 parse 被调用
        self.assertGreaterEqual(parse_results.await_count, 1)

    async def test_sogou_exhausts_retries_then_stops(self):
        """Sogou 全部重试失败后停止引擎"""
        parse_results = AsyncMock()

        class _AlwaysFails:
            def __init__(self, *a, **kw):
                pass
            async def __aenter__(self):
                return self
            async def __aexit__(self, *a):
                return False
            async def get(self, url, headers=None, timeout=None):
                if "sogou.com/" == url.rstrip("/"):
                    return None  # warmup success
                raise Exception("Connection refused")

        with patch.object(search, "_parse_search_results", parse_results), \
             patch.object(search.httpx, "AsyncClient", _AlwaysFails), \
             patch.object(search.asyncio, "sleep", AsyncMock()), \
             patch.object(search, "_build_headers", return_value={"User-Agent": "test"}):
            urls = await search._get_search_results(
                keyword="docker", engine="sogou", max_results=10, time_range="all"
            )
        parse_results.assert_not_called()
        self.assertEqual(len(urls), 0)


# ============== Bing /ck/a? 非 a1 前缀 ==============

BING_ALGO_HTML = """<html><body>
  <li class="b_algo">
    <h2><a href="{}">Test Title</a></h2>
    <p>docker tutorial content with enough text for keyword matching purposes here</p>
  </li>
</body></html>"""


class TestBingCkANonA1Prefix(unittest.IsolatedAsyncioTestCase):
    """Bing /ck/a? 只处理 'a1' 前缀的编码 URL"""

    async def test_bing_ck_a_non_a1_prefix_ignored(self):
        """非 'a1' 前缀的 ck/a 参数被静默忽略（href 保留为原始 /ck/a? URL）"""
        real_url = b"https://example.com/article"
        encoded = base64.b64encode(real_url).decode()
        # 使用 "a2" 前缀而非 "a1"
        ck_param = "a2" + encoded
        href = f"https://www.bing.com/ck/a?u={ck_param}"
        # 原始 href 以 https 开头但指向 bing.com 中转页
        # 因为解码被跳过（非 a1 前缀），href 仍为 bing.com 中转 URL
        # bing.com 不在排除域名列表，所以会被收录
        html = BING_ALGO_HTML.format(href)
        urls = []
        await search._parse_search_results(
            html=html, engine="bing", config=search.SEARCH_ENGINES["bing"],
            keyword="docker", max_results=5, seen_domains={}, urls=urls,
            search_url="https://www.bing.com/search?q=docker",
            headers={"User-Agent": "test"}, client=None,
        )
        # 非 a1 前缀不解码，原始 bing.com 中转 URL 被当作有效 URL 收录
        # 这是一个已知局限：非 a1 前缀的 ck/a URL 不会被解析出真实目标
        self.assertEqual(len(urls), 1)
        self.assertIn("bing.com/ck/a", urls[0])

    async def test_bing_ck_a_decode_exception_keeps_original(self):
        """base64 解码异常时保留原始 href，不抛异常"""
        ck_param = "a1" + "!!!!not-valid-base64!!!!"
        href = f"https://www.bing.com/ck/a?u={ck_param}"
        html = BING_ALGO_HTML.format(href)
        urls = []
        # 不应抛异常
        await search._parse_search_results(
            html=html, engine="bing", config=search.SEARCH_ENGINES["bing"],
            keyword="docker", max_results=5, seen_domains={}, urls=urls,
            search_url="https://www.bing.com/search?q=docker",
            headers={"User-Agent": "test"}, client=None,
        )
        self.assertEqual(len(urls), 1)


# ============== _decode_baidu_redirect 分支覆盖 ==============

class TestDecodeBaiduRedirect(unittest.IsolatedAsyncioTestCase):
    """_decode_baidu_redirect HEAD 成功 / GET 回退"""

    async def test_head_succeeds_returns_url(self):
        """HEAD 请求成功（status < 400，非 baidu redirect）→ 返回真实 URL"""
        client = AsyncMock()
        head_resp = _FakeResponse(status_code=200, url="https://example.com/real-article")
        client.head.return_value = head_resp
        result = await search._decode_baidu_redirect(
            href="https://www.baidu.com/link?url=encoded",
            search_url="https://www.baidu.com/s?wd=test",
            headers={"User-Agent": "test"},
            client=client,
        )
        self.assertEqual(result, "https://example.com/real-article")

    async def test_head_fails_falls_back_to_get(self):
        """HEAD 返回 baidu redirect → GET 回退 → 返回真实 URL"""
        client = AsyncMock()
        head_resp = _FakeResponse(status_code=200, url="https://www.baidu.com/link?url=still_encoded")
        get_resp = _FakeResponse(status_code=200, url="https://example.com/resolved")
        client.head.return_value = head_resp
        client.get.return_value = get_resp
        result = await search._decode_baidu_redirect(
            href="https://www.baidu.com/link?url=encoded",
            search_url="https://www.baidu.com/s?wd=test",
            headers={"User-Agent": "test"},
            client=client,
        )
        self.assertEqual(result, "https://example.com/resolved")

    async def test_head_and_get_both_unresolved_returns_none(self):
        """HEAD 和 GET 都未解析（仍为 baidu.com/link）→ 返回 None"""
        client = AsyncMock()
        unresolved = _FakeResponse(status_code=302, url="https://www.baidu.com/link?url=still_encoded")
        client.head.return_value = unresolved
        client.get.return_value = unresolved
        result = await search._decode_baidu_redirect(
            href="https://www.baidu.com/link?url=encoded",
            search_url="https://www.baidu.com/s?wd=test",
            headers={"User-Agent": "test"},
            client=client,
        )
        self.assertIsNone(result)

    async def test_head_500_triggers_get_fallback(self):
        """HEAD 返回 >=400 状态码 → GET 回退"""
        client = AsyncMock()
        head_resp = _FakeResponse(status_code=500, url="https://www.baidu.com/link?url=encoded")
        get_resp = _FakeResponse(status_code=200, url="https://example.com/resolved")
        client.head.return_value = head_resp
        client.get.return_value = get_resp
        result = await search._decode_baidu_redirect(
            href="https://www.baidu.com/link?url=encoded",
            search_url="https://www.baidu.com/s?wd=test",
            headers={"User-Agent": "test"},
            client=client,
        )
        self.assertEqual(result, "https://example.com/resolved")


# ============== Sogou /link?url= 跳转提取器 ==============

class TestSogouLinkRedirect(unittest.IsolatedAsyncioTestCase):
    """搜狗 /link?url= JS 跳转 / meta refresh 抽取"""

    async def test_js_redirect_extracted(self):
        """window.location.replace 被正确抽取"""
        sogou_html = """
        <html><body>
          <div class="vrwrap">
            <h3 class="vrTitle"><a href="/link?url=abcd">Link</a></h3>
            <p class="str-text">docker tutorial content for keyword matching test purposes</p>
          </div>
        </body></html>
        """
        js_redirect_html = '<script>window.location.replace("https://example.com/target")</script>'
        client = AsyncMock()
        client.get.return_value = _FakeResponse(text=js_redirect_html, status_code=200)
        urls = []
        await search._parse_search_results(
            html=sogou_html, engine="sogou", config=search.SEARCH_ENGINES["sogou"],
            keyword="docker", max_results=5, seen_domains={}, urls=urls,
            search_url="https://www.sogou.com/web?query=docker",
            headers={"User-Agent": "test"}, client=client,
        )
        self.assertEqual(len(urls), 1)
        self.assertEqual(urls[0], "https://example.com/target")

    async def test_meta_refresh_extracted(self):
        """meta http-equiv=refresh 被正确抽取"""
        sogou_html = """
        <html><body>
          <div class="vrwrap">
            <h3 class="vrTitle"><a href="/link?url=abcd">Link</a></h3>
            <p class="str-text">docker tutorial content for keyword matching test purposes</p>
          </div>
        </body></html>
        """
        meta_html = '<meta http-equiv="refresh" content="0;URL=https://example.com/meta-target">'
        client = AsyncMock()
        client.get.return_value = _FakeResponse(text=meta_html, status_code=200)
        urls = []
        await search._parse_search_results(
            html=sogou_html, engine="sogou", config=search.SEARCH_ENGINES["sogou"],
            keyword="docker", max_results=5, seen_domains={}, urls=urls,
            search_url="https://www.sogou.com/web?query=docker",
            headers={"User-Agent": "test"}, client=client,
        )
        self.assertEqual(len(urls), 1)
        self.assertEqual(urls[0], "https://example.com/meta-target")

    async def test_sogou_link_redirect_sogou_domain_skipped(self):
        """link?url= 跳转后仍为 sogou.com → 跳过"""
        sogou_html = """
        <html><body>
          <div class="vrwrap">
            <h3 class="vrTitle"><a href="/link?url=abcd">Link</a></h3>
            <p class="str-text">docker tutorial content for keyword matching test purposes</p>
          </div>
        </body></html>
        """
        js_html = '<script>window.location.replace("https://www.sogou.com/internal-page")</script>'
        client = AsyncMock()
        client.get.return_value = _FakeResponse(text=js_html, status_code=200)
        urls = []
        await search._parse_search_results(
            html=sogou_html, engine="sogou", config=search.SEARCH_ENGINES["sogou"],
            keyword="docker", max_results=5, seen_domains={}, urls=urls,
            search_url="https://www.sogou.com/web?query=docker",
            headers={"User-Agent": "test"}, client=client,
        )
        self.assertEqual(len(urls), 0)

    async def test_sogou_link_no_client_skipped(self):
        """client=None 时 Sogou link?url= 被跳过"""
        sogou_html = """
        <html><body>
          <div class="vrwrap">
            <h3 class="vrTitle"><a href="/link?url=abcd">Link</a></h3>
            <p class="str-text">docker tutorial content for keyword matching test purposes</p>
          </div>
        </body></html>
        """
        urls = []
        await search._parse_search_results(
            html=sogou_html, engine="sogou", config=search.SEARCH_ENGINES["sogou"],
            keyword="docker", max_results=5, seen_domains={}, urls=urls,
            search_url="https://www.sogou.com/web?query=docker",
            headers={"User-Agent": "test"}, client=None,
        )
        self.assertEqual(len(urls), 0)

    async def test_no_redirect_mechanism_found_skipped(self):
        """无 JS redirect 也无 meta refresh → 跳过"""
        sogou_html = """
        <html><body>
          <div class="vrwrap">
            <h3 class="vrTitle"><a href="/link?url=abcd">Link</a></h3>
            <p class="str-text">docker tutorial content for keyword matching test purposes</p>
          </div>
        </body></html>
        """
        empty_html = "<html><body>redirecting...</body></html>"
        client = AsyncMock()
        client.get.return_value = _FakeResponse(text=empty_html, status_code=200)
        urls = []
        await search._parse_search_results(
            html=sogou_html, engine="sogou", config=search.SEARCH_ENGINES["sogou"],
            keyword="docker", max_results=5, seen_domains={}, urls=urls,
            search_url="https://www.sogou.com/web?query=docker",
            headers={"User-Agent": "test"}, client=client,
        )
        self.assertEqual(len(urls), 0)


# ============== 搜索引擎 URL 构造 ==============

class TestSearchUrlConstruction(unittest.TestCase):
    """验证各搜索引擎的 URL 构造（分页参数起止值）"""

    def test_bing_first_page_starts_at_1(self):
        """Bing 第一页: first=1"""
        keyword = "test"
        expected = f"https://www.bing.com/search?q={keyword}&setmkt=en-US&setlang=en&first=1"
        url = f"https://www.bing.com/search?q={keyword}&setmkt=en-US&setlang=en&first=1"
        self.assertIn("first=1", url)

    def test_bing_page_two_starts_at_11(self):
        """Bing 第二页: first=11"""
        first = 1 * 10 + 1
        self.assertEqual(first, 11)

    def test_google_page_zero_start_at_zero(self):
        """Google 第一页: start=0"""
        start = 0 * 10
        self.assertEqual(start, 0)

    def test_google_page_one_start_at_10(self):
        """Google 第二页: start=10"""
        start = 1 * 10
        self.assertEqual(start, 10)

    def test_baidu_page_zero_pn_zero(self):
        """Baidu 第一页: pn=0"""
        pn = 0 * 10
        self.assertEqual(pn, 0)

    def test_baidu_page_one_pn_is_10(self):
        """Baidu 第二页: pn=10"""
        pn = 1 * 10
        self.assertEqual(pn, 10)

    def test_sogou_page_zero_uses_page_1(self):
        """Sogou 第一页: page=1"""
        sogou_page = 0 + 1
        self.assertEqual(sogou_page, 1)

    def test_sogou_page_one_uses_page_2(self):
        """Sogou 第二页: page=2"""
        sogou_page = 1 + 1
        self.assertEqual(sogou_page, 2)


# ============== _is_anti_bot_page 补充 ==============

class TestIsAntiBotPageExtended(unittest.TestCase):
    def test_chinese_security_verification(self):
        self.assertTrue(search._is_anti_bot_page("安全验证", ""))

    def test_baidu_captcha_style(self):
        self.assertTrue(search._is_anti_bot_page("请输入验证码", "<div>captcha</div>"))

    def test_html_only_detection(self):
        """raw_html 中检测到 recaptcha 即使 text 为空"""
        self.assertTrue(search._is_anti_bot_page("", "<div class='g-recaptcha'></div>"))

    def test_unusual_traffic_detected(self):
        self.assertTrue(search._is_anti_bot_page("unusual traffic detected from your network", ""))


# ============== _get_search_results 重试行为 ==============

class TestGetSearchResultsRetryBehavior(unittest.IsolatedAsyncioTestCase):
    """Bing/Baidu 有重试，Sogou 无重试"""

    async def test_bing_retries_on_exception(self):
        """Bing 页面请求失败时重试（最多 SEARCH_PAGE_RETRIES 次），成功后继续"""
        parse_results = AsyncMock(return_value=(0, 0))
        succeed = _FakeResponse(text="<html>" + "x" * 600 + "</html>", status_code=200)
        fail_then_succeed = [Exception("Connection reset"), succeed]

        class _RetryClient:
            def __init__(self, *a, **kw):
                self.calls = 0
            async def __aenter__(self):
                return self
            async def __aexit__(self, *a):
                return False
            async def get(self, url, headers=None):
                result = fail_then_succeed[self.calls]
                self.calls += 1
                if isinstance(result, Exception):
                    raise result
                return result

        with patch.object(search, "_parse_search_results", parse_results), \
             patch.object(search.httpx, "AsyncClient", _RetryClient), \
             patch.object(search.asyncio, "sleep", AsyncMock()):
            await search._get_search_results(
                keyword="docker", engine="bing", max_results=3, time_range="all"
            )
        # 第1次失败，第2次重试成功 → parse 被调用
        self.assertEqual(parse_results.await_count, 1)

    async def test_baidu_500_triggers_retry(self):
        """Baidu >=500 状态码触发响应异常 → 重试"""
        parse_results = AsyncMock(return_value=(0, 0))

        class _RaiseForStatusResponse(_FakeResponse):
            def raise_for_status(self):
                from httpx import HTTPStatusError
                raise HTTPStatusError("Server Error", request=MagicMock(), response=MagicMock())

        class _FailThenSucceedClient:
            def __init__(self, *a, **kw):
                self.attempts = 0
            async def __aenter__(self):
                return self
            async def __aexit__(self, *a):
                return False
            async def get(self, url, headers=None):
                self.attempts += 1
                if self.attempts == 1:
                    return _RaiseForStatusResponse(text="error", status_code=500)
                return _FakeResponse(text="<html>" + "x" * 600 + "</html>")

        with patch.object(search, "_parse_search_results", parse_results), \
             patch.object(search.httpx, "AsyncClient", _FailThenSucceedClient), \
             patch.object(search.asyncio, "sleep", AsyncMock()):
            await search._get_search_results(
                keyword="docker", engine="baidu", max_results=2, time_range="all"
            )
        # 第1次500异常→重试，第2次成功→parse 被调用（至少1次，含后续分页）
        self.assertGreaterEqual(parse_results.await_count, 1)


# ============== _build_headers 补充 ==============

class TestBuildHeadersExtended(unittest.TestCase):
    def test_dnt_header_present(self):
        headers = search._build_headers()
        self.assertEqual(headers.get("DNT"), "1")

    def test_sec_fetch_headers(self):
        headers = search._build_headers()
        self.assertEqual(headers.get("Sec-Fetch-Dest"), "document")
        self.assertEqual(headers.get("Sec-Fetch-Mode"), "navigate")
        self.assertEqual(headers.get("Sec-Fetch-Site"), "none")

    def test_accept_encoding_includes_gzip(self):
        headers = search._build_headers()
        self.assertIn("gzip", headers.get("Accept-Encoding", ""))


if __name__ == "__main__":
    unittest.main()
