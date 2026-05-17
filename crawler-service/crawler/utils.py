"""Crawler utility functions shared across modules."""

import re


def detect_cjk(text: str) -> bool:
    """检测文本是否包含 CJK 字符（中日韩统一表意文字）。"""
    return any('一' <= c <= '鿿' for c in text)


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


def get_result_url(r) -> str | None:
    """从爬取结果对象中安全提取 URL（兼容 dict 和对象两种类型）。"""
    if isinstance(r, dict):
        return r.get("url")
    return getattr(r, "url", None)


def get_result_success(r) -> bool:
    """从爬取结果对象中安全提取 success 标志（兼容 dict 和对象两种类型）。"""
    if isinstance(r, dict):
        return bool(r.get("success", False))
    return bool(getattr(r, "success", False))


def dedup_results_into(
    results: list, seen_urls: set, target: list,
    min_content_length: int = 0,
) -> int:
    """将 results 中未重复的 URL 追加到 target，返回新增数量。

    统一的去重逻辑，供 task_executor / feedback / bubble_breaker 复用。

    Args:
        min_content_length: 内容最小长度阈值，低于此的结果不加入（0=不过滤）
    """
    added = 0
    for r in results:
        url = get_result_url(r)
        success = get_result_success(r)
        if not url or not success:
            continue
        normalized = normalize_url(url)
        if normalized in seen_urls:
            continue
        if min_content_length > 0:
            content = ""
            if isinstance(r, dict):
                content = r.get("markdown", "") or ""
            elif hasattr(r, "markdown"):
                content = r.markdown or ""
            if len(content) < min_content_length:
                continue
        seen_urls.add(normalized)
        target.append(r)
        added += 1
    return added
