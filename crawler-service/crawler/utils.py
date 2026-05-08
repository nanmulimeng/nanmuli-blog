"""Crawler utility functions shared across modules."""

import re


def count_words(text: str) -> int:
    """统计文本字数：中文字符 + 英文单词。

    英文单词信息密度低于中文字符，加权 1.5x 以更准确反映实际内容量。
    """
    if not text:
        return 0
    cn_chars = len(re.findall(r'[一-鿿]', text))
    en_words = len(re.findall(r'[a-zA-Z]+', text))
    return int(cn_chars + en_words * 1.5)


def normalize_url(url: str) -> str:
    """URL 标准化：去协议、去 www、去尾部斜杠、去追踪参数、小写。
    供 repository._hash_url 和 dedup.DedupEngine 共享。
    """
    url = url.lower().strip()
    url = re.sub(r'^https?://', '', url)
    url = re.sub(r'^www\.', '', url)
    url = url.rstrip('/')
    url = re.sub(r'[?&](utm_[^&=]*|ref|source)=[^&]*', '', url)
    url = re.sub(r'\?+$', '', url)
    return url
