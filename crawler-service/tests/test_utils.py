"""utils.py 单元测试

覆盖：
- count_words: 纯中文、纯英文、中英混合、空字符串
- normalize_url: 带协议、带 www、带 utm 参数、带尾斜杠、带查询参数
"""

import os
import sys
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from crawler.utils import count_words, normalize_url


# ============== count_words ==============

class TestCountWords:
    def test_pure_chinese(self):
        """纯中文：每个字符计 1"""
        text = "今天天气真好"
        result = count_words(text)
        assert result == 6

    def test_pure_english(self):
        """纯英文：每个单词计 1.5"""
        text = "hello world test"
        result = count_words(text)
        # 3 words * 1.5 = 4.5 -> int(4.5) = 4
        assert result == 4

    def test_mixed_chinese_english(self):
        """中英混合：中文按字符 + 英文按单词*1.5"""
        text = "Python是最好的语言"
        # 中文: 是最好的语言 = 6 chars (的、最、好、的、语、言 - '的'出现两次)
        # 英文: Python = 1 word
        # 6 + 1*1.5 = 7.5 -> int(7.5) = 7
        result = count_words(text)
        assert result == 7

    def test_empty_string(self):
        assert count_words("") == 0

    def test_none_input(self):
        assert count_words(None) == 0

    def test_only_whitespace(self):
        assert count_words("   \n\t  ") == 0

    def test_numbers_only(self):
        """纯数字不匹配英文单词模式 [a-zA-Z]+"""
        assert count_words("12345 67890") == 0

    def test_single_chinese_char(self):
        assert count_words("测") == 1


# ============== normalize_url ==============

class TestNormalizeUrl:
    def test_strip_https(self):
        assert normalize_url("https://example.com/path") == "example.com/path"

    def test_strip_http(self):
        assert normalize_url("http://example.com/path") == "example.com/path"

    def test_strip_www(self):
        assert normalize_url("https://www.example.com/path") == "example.com/path"

    def test_strip_trailing_slash(self):
        assert normalize_url("https://example.com/path/") == "example.com/path"

    def test_strip_utm_params(self):
        result = normalize_url("https://example.com/page?utm_source=twitter&utm_medium=social")
        assert "utm_" not in result
        assert result == "example.com/page"

    def test_strip_ref_source_params(self):
        result = normalize_url("https://example.com/page?ref=abc&source=rss&id=1")
        assert "ref=" not in result
        assert "source=" not in result
        # id=1 should remain
        assert "id=1" in result

    def test_lowercase(self):
        assert normalize_url("HTTPS://EXAMPLE.COM/Path") == "example.com/path"

    def test_combined_transformations(self):
        result = normalize_url(
            "https://www.Example.com/path/?utm_source=google&key=value"
        )
        # 正则替换 utm_source=google 后剩余 &key=value（& 保留）
        assert result == "example.com/path/&key=value"
