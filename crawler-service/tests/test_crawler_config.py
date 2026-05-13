"""config.py 单元测试

覆盖：
- RunParams 默认值 / 自定义值 / None 输入
- BrowserConfig 代理注入
- extract_markdown fit/raw 回退逻辑
- markdown 对象为 None / 空字符串
"""

import os
import sys
import pytest
from unittest.mock import MagicMock, patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from crawler.config import (
    RunParams,
    get_browser_config,
    get_crawler_run_config,
    get_search_run_config,
    extract_markdown,
    DEFAULT_EXCLUDED_TAGS,
    _FIT_MIN_RATIO,
    _filter_nav_noise,
    _filter_breadcrumbs,
    _filter_boilerplate,
    _is_inline_nav,
)


# ============== RunParams ==============

class TestRunParams:
    def test_defaults_when_none(self):
        rp = RunParams(None)
        assert rp.text_mode is True
        assert rp.light_mode is False
        assert rp.word_count_threshold == 10
        assert rp.excluded_tags == DEFAULT_EXCLUDED_TAGS
        assert rp.wait_until == "networkidle"
        assert rp.page_timeout == 60000
        assert rp.remove_overlay_elements is True

    def test_custom_values(self):
        cfg = MagicMock()
        cfg.text_mode = False
        cfg.light_mode = True
        cfg.word_count_threshold = 50
        cfg.excluded_tags = ["nav"]
        cfg.wait_until = "domcontentloaded"
        cfg.page_timeout = 30000
        cfg.remove_overlay_elements = False

        rp = RunParams(cfg)
        assert rp.text_mode is False
        assert rp.light_mode is True
        assert rp.word_count_threshold == 50
        assert rp.excluded_tags == ["nav"]
        assert rp.wait_until == "domcontentloaded"
        assert rp.page_timeout == 30000
        assert rp.remove_overlay_elements is False

    def test_partial_config_uses_defaults(self):
        """config 对象只设置部分属性，其余回退默认值"""
        cfg = MagicMock(spec=[])  # spec=[] 让所有属性触发 AttributeError
        cfg.text_mode = False
        # 其他属性不存在 -> getattr 回退默认
        rp = RunParams(cfg)
        assert rp.text_mode is False
        assert rp.light_mode is False  # 默认
        assert rp.word_count_threshold == 10  # 默认

    def test_no_config_arg(self):
        """不传 config 也应该正常工作"""
        rp = RunParams()
        assert rp.text_mode is True

    def test_slots_prevents_dynamic_attrs(self):
        rp = RunParams()
        with pytest.raises(AttributeError):
            rp.nonexistent_attr = 42


# ============== get_browser_config ==============

class TestGetBrowserConfig:
    @patch("crawler.config.BrowserConfig")
    @patch("crawler.config.get_effective_proxy", return_value="http://127.0.0.1:7890")
    def test_proxy_injection(self, mock_eff_proxy, MockBrowserConfig):
        get_browser_config(text_mode=True, proxy="http://127.0.0.1:7890")
        call_kwargs = MockBrowserConfig.call_args[1]
        extra_args = call_kwargs["extra_args"]
        assert any("--proxy-server=http://127.0.0.1:7890" in a for a in extra_args)

    @patch("crawler.config.BrowserConfig")
    @patch("crawler.config.get_effective_proxy", return_value="")
    def test_no_proxy_no_proxy_arg(self, mock_eff_proxy, MockBrowserConfig):
        get_browser_config(text_mode=True, proxy="")
        call_kwargs = MockBrowserConfig.call_args[1]
        extra_args = call_kwargs["extra_args"]
        assert not any("--proxy-server=" in a for a in extra_args)

    @patch("crawler.config.BrowserConfig")
    @patch("crawler.config.get_effective_proxy", return_value="")
    def test_proxy_unreachable_fallback(self, mock_eff_proxy, MockBrowserConfig):
        """代理不可达时自动降级直连"""
        get_browser_config(text_mode=True, proxy="http://127.0.0.1:9999")
        call_kwargs = MockBrowserConfig.call_args[1]
        extra_args = call_kwargs["extra_args"]
        assert not any("--proxy-server=" in a for a in extra_args)

    @patch("crawler.config.BrowserConfig")
    def test_headless_always_true(self, MockBrowserConfig):
        get_browser_config()
        call_kwargs = MockBrowserConfig.call_args[1]
        assert call_kwargs["headless"] is True


# ============== extract_markdown ==============

class TestExtractMarkdown:
    def _make_result(self, fit=None, raw=None, md_obj_exists=True):
        """构造 mock crawl4ai_result"""
        result = MagicMock()
        if md_obj_exists:
            md = MagicMock()
            md.fit_markdown = fit
            md.raw_markdown = raw
            result.markdown = md
        else:
            result.markdown = None
        return result

    def test_fit_preferred_when_ratio_ok(self):
        """fit 占 raw > 30% 时返回 fit"""
        result = self._make_result(fit="A" * 80, raw="B" * 100)
        assert extract_markdown(result) == "A" * 80

    def test_fallback_to_raw_when_ratio_low(self):
        """fit 占 raw < 30% 时回退 raw"""
        result = self._make_result(fit="A" * 10, raw="B" * 100)
        assert extract_markdown(result) == "B" * 100

    def test_fit_only_no_raw(self):
        """有 fit 无 raw 时返回 fit"""
        result = self._make_result(fit="Good content", raw=None)
        assert extract_markdown(result) == "Good content"

    def test_raw_only_no_fit(self):
        """有 raw 无 fit 时返回 raw"""
        result = self._make_result(fit=None, raw="Raw content")
        assert extract_markdown(result) == "Raw content"

    def test_no_markdown_object(self):
        """markdown 为 None 时返回空字符串"""
        result = self._make_result(md_obj_exists=False)
        assert extract_markdown(result) == ""

    def test_empty_fit_and_raw(self):
        """fit 和 raw 都为空字符串时返回空字符串"""
        result = self._make_result(fit="", raw="")
        # fit="" 是 falsy, raw="" 也是 falsy, 返回空字符串
        assert extract_markdown(result) == ""

    def test_bytes_fit_decoded(self):
        """fit 是 bytes 时自动 decode"""
        result = self._make_result(fit=b"Hello bytes", raw=b"Raw bytes")
        assert extract_markdown(result) == "Hello bytes"

    def test_ratio_boundary(self):
        """精确在 30% 边界：应返回 fit"""
        fit_len = 30
        raw_len = 100
        result = self._make_result(fit="A" * fit_len, raw="B" * raw_len)
        # ratio = 30/100 = 0.3, 不小于 0.3, 返回 fit
        assert extract_markdown(result) == "A" * fit_len

    def test_ratio_just_below_threshold(self):
        """29% 回退 raw"""
        fit_len = 29
        raw_len = 100
        result = self._make_result(fit="A" * fit_len, raw="B" * raw_len)
        # ratio = 29/100 = 0.29 < 0.3, 回退 raw
        assert extract_markdown(result) == "B" * raw_len


# ============== _filter_nav_noise ==============

class TestFilterNavNoise:
    """_filter_nav_noise 增强覆盖测试"""

    def test_bullet_list_nav_removed(self):
        """标准无序列表导航被移除"""
        md = "\n".join([f"- [Link {i}](https://a.com/p{i})" for i in range(10)])
        result = _filter_nav_noise(md)
        assert result.strip() == "" or len(result) < len(md)

    def test_numbered_list_nav_removed(self):
        """编号列表导航被移除: 1. [text](url)"""
        md = "\n".join([f"{i}. [Link {i}](https://a.com/p{i})" for i in range(1, 11)])
        result = _filter_nav_noise(md)
        assert len(result.strip()) < len(md)

    def test_paren_numbered_list_nav_removed(self):
        """编号列表导航被移除: 1) [text](url)"""
        md = "\n".join([f"{i}) [Link {i}](https://a.com/p{i})" for i in range(1, 11)])
        result = _filter_nav_noise(md)
        assert len(result.strip()) < len(md)

    def test_inline_nav_removed(self):
        """管道分隔内联导航被移除"""
        md = "[Home](/) | [Blog](/blog) | [About](/about) | [Contact](/contact)"
        result = _filter_nav_noise(md)
        assert result.strip() == ""

    def test_small_nav_group_high_density_removed(self):
        """3-7项高密度小导航组被移除（>80%）"""
        md = "\n".join([
            "- [Page 1](https://a.com/1)",
            "- [Page 2](https://a.com/2)",
            "- [Page 3](https://a.com/3)",
            "- [Page 4](https://a.com/4)",
            "- [Page 5](https://a.com/5)",
        ])
        # 5行纯链接 = 100% density
        result = _filter_nav_noise(md)
        assert len(result.strip()) < len(md)

    def test_real_content_not_removed(self):
        """正常正文内容不被误删"""
        md = (
            "## Introduction\n\n"
            "This is the first paragraph with some real content.\n\n"
            "## Section 1\n\n"
            "Here is more detailed text that discusses the topic.\n\n"
            "- Key point one: explains something important\n"
            "- Key point two: another important insight\n"
        )
        result = _filter_nav_noise(md)
        assert "Introduction" in result
        assert "Key point one" in result
        assert "Key point two" in result

    def test_only_three_links_in_real_context_not_removed(self):
        """3个链接但嵌入正文中不应被误删（密度不够）"""
        md = (
            "Here is a paragraph with [link one](https://a.com/1) and some text.\n"
            "Another paragraph with [link two](https://a.com/2) and more content.\n"
            "A third paragraph with [link three](https://a.com/3) to finish.\n"
        )
        result = _filter_nav_noise(md)
        assert "link one" in result
        assert "link two" in result
        assert "link three" in result


# ============== _is_inline_nav ==============

class TestIsInlineNav:
    def test_pipe_separated_links_is_nav(self):
        assert _is_inline_nav("[Home](/) | [Blog](/b) | [About](/a)") is True

    def test_two_links_is_not_nav(self):
        assert _is_inline_nav("[Home](/) | [Blog](/b)") is False

    def test_text_with_links_is_not_nav(self):
        s = "This is a [link](https://a.com) in normal text with [another](https://b.com) and [third](https://c.com) link"
        assert _is_inline_nav(s) is False

    def test_empty_line_is_not_nav(self):
        assert _is_inline_nav("") is False


# ============== _filter_breadcrumbs ==============

class TestFilterBreadcrumbs:
    def test_markdown_breadcrumbs_removed(self):
        md = "[Home](/) > [Blog](/blog) > [Current Post](/post)"
        result = _filter_breadcrumbs(md)
        assert result.strip() == ""

    def test_text_breadcrumbs_removed(self):
        md = "Home / Blog / Current Post"
        result = _filter_breadcrumbs(md)
        assert result.strip() == ""

    def test_normal_content_not_removed(self):
        md = "This is some normal text about the topic"
        result = _filter_breadcrumbs(md)
        assert result == md

    def test_single_link_not_removed(self):
        md = "[Click here](https://a.com) to learn more"
        result = _filter_breadcrumbs(md)
        assert result == md


# ============== _filter_boilerplate ==============

class TestFilterBoilerplate:
    def test_cookie_text_removed(self):
        assert _filter_boilerplate("We use cookies to improve your experience").strip() == ""

    def test_newsletter_text_removed(self):
        assert _filter_boilerplate("Subscribe to our newsletter for updates").strip() == ""
        assert _filter_boilerplate("Sign up for email updates today").strip() == ""

    def test_social_share_text_removed(self):
        assert _filter_boilerplate("Share on Twitter and Facebook").strip() == ""

    def test_copyright_text_removed(self):
        assert _filter_boilerplate("Copyright 2024 All rights reserved").strip() == ""

    def test_pagination_text_removed(self):
        assert _filter_boilerplate("Page 1 of 10").strip() == ""

    def test_normal_content_preserved(self):
        md = "## Introduction\n\nThis is the main content of the article.\n\nIt covers important topics."
        result = _filter_boilerplate(md)
        assert "Introduction" in result
        assert "main content" in result


# ============== extract_markdown 噪音过滤链集成 ==============

class TestExtractMarkdownNoiseChain:
    """验证 extract_markdown 的完整噪音过滤链"""

    def _make_result(self, fit=None, raw=None):
        result = MagicMock()
        md = MagicMock()
        md.fit_markdown = fit
        md.raw_markdown = raw
        result.markdown = md
        return result

    def test_breadcrumbs_filtered_in_chain(self):
        result = self._make_result(
            fit="[Home](/) > [Blog](/blog) > [Post](/post)\n\n## Real Content\n\nThis is the article body."
        )
        output = extract_markdown(result)
        assert "Home" not in output
        assert "Real Content" in output

    def test_boilerplate_filtered_in_chain(self):
        result = self._make_result(
            fit="We use cookies to improve your experience\n\n## Article\n\nArticle body text here."
        )
        output = extract_markdown(result)
        assert "cookies" not in output.lower()
        assert "Article" in output

    def test_nav_noise_filtered_in_chain(self):
        links = "\n".join([f"- [Nav {i}](https://a.com/p{i})" for i in range(10)])
        result = self._make_result(fit=f"{links}\n\n## Content\n\nReal article text.")
        output = extract_markdown(result)
        assert "Content" in output
        # 导航链接应被移除（减少）
        assert len(output) < len(result.markdown.fit_markdown)
