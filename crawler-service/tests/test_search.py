import base64
import datetime
import re
import unittest
from unittest.mock import AsyncMock, patch

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


if __name__ == "__main__":
    unittest.main()
