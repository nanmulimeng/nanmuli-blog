"""
共享页面处理管线

提取 single.py / deep.py 中重复的元数据提取、JS Challenge 重试、depth 提取逻辑。
"""

import logging
from typing import Optional

from .config import get_crawler_run_config
from .metadata import extract_metadata
from .models import JS_CHALLENGE_MIN_WORDS, JS_CHALLENGE_DELAY, JS_CHALLENGE_WAIT_FOR

logger = logging.getLogger(__name__)


def extract_page_metadata(result, base_url: str) -> dict:
    """从 crawl4ai result 提取并合并元数据"""
    html = getattr(result, 'html', None) or ''
    metadata = extract_metadata(html_content=html, base_url=base_url)

    if hasattr(result, 'metadata') and isinstance(result.metadata, dict):
        metadata.update({
            'crawl4ai_title': result.metadata.get('title'),
            'crawl4ai_description': result.metadata.get('description'),
        })

    return metadata


async def retry_js_challenge(crawler, url: str, params) -> Optional[object]:
    """JS Challenge 重试：等待正文元素出现 + 额外延迟

    Returns:
        重试后的 crawl4ai result，或 None 表示重试失败
    """
    retry_config = get_crawler_run_config(
        word_count_threshold=params.word_count_threshold,
        excluded_tags=params.excluded_tags,
        excluded_selector=params.excluded_selector,
        prune_threshold=params.prune_threshold,
        wait_until=params.wait_until,
        page_timeout=params.page_timeout,
        remove_overlay_elements=params.remove_overlay_elements,
        max_retries=params.max_retries,
        mean_delay=params.mean_delay,
        max_range=params.max_range,
        delay_before_return_html=JS_CHALLENGE_DELAY,
        remove_consent_popups=params.remove_consent_popups,
        wait_for=JS_CHALLENGE_WAIT_FOR,
        wait_for_timeout=5000,
    )
    return await crawler.arun(url=url, config=retry_config)


def extract_depth(result) -> int:
    """从 crawl4ai result 提取 depth（兼容 0.8.x metadata 模式）"""
    depth = getattr(result, 'depth', None)
    if depth is None and isinstance(getattr(result, 'metadata', None), dict):
        depth = result.metadata.get('depth', 0)
    return depth if depth is not None else 0
