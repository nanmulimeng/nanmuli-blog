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
)


# ============== RunParams ==============

class TestRunParams:
    def test_defaults_when_none(self):
        rp = RunParams(None)
        assert rp.text_mode is True
        assert rp.light_mode is False
        assert rp.word_count_threshold == 15
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
        assert rp.word_count_threshold == 15  # 默认

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
    def test_proxy_injection(self, MockBrowserConfig):
        get_browser_config(text_mode=True, proxy="http://127.0.0.1:7890")
        call_kwargs = MockBrowserConfig.call_args[1]
        extra_args = call_kwargs["extra_args"]
        assert any("--proxy-server=http://127.0.0.1:7890" in a for a in extra_args)

    @patch("crawler.config.BrowserConfig")
    def test_no_proxy_no_proxy_arg(self, MockBrowserConfig):
        get_browser_config(text_mode=True, proxy="")
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
        """fit 和 raw 都为空字符串时返回 str(md_obj)"""
        result = self._make_result(fit="", raw="")
        # fit="" 是 falsy, raw="" 也是 falsy, 最终走 str(md_obj)
        md_str = result.markdown.__str__()
        assert extract_markdown(result) == md_str

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
