"""
元数据提取模块

提取网页的元数据：标题、描述、关键词、发布时间、作者、语言等
"""

import re
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def extract_metadata(html_content: str, base_url: str) -> Dict[str, Any]:
    """
    从 HTML 内容中提取元数据

    Args:
        html_content: HTML 字符串
        base_url: 页面 URL（用于解析相对链接）

    Returns:
        元数据字典
    """
    soup = BeautifulSoup(html_content, 'lxml')
    metadata = {
        'url': base_url,
        'title': None,
        'description': None,
        'keywords': None,
        'author': None,
        'published_at': None,
        'language': None,
        'canonical_url': None,
    }

    try:
        # 1. 提取标题（优先级：og:title > twitter:title > title）
        metadata['title'] = (
            _get_meta_content(soup, 'og:title') or
            _get_meta_content(soup, 'twitter:title') or
            soup.title.string if soup.title else None
        )

        # 2. 提取描述
        metadata['description'] = (
            _get_meta_content(soup, 'og:description') or
            _get_meta_content(soup, 'twitter:description') or
            _get_meta_content(soup, 'description')
        )

        # 3. 提取关键词
        keywords = _get_meta_content(soup, 'keywords')
        if keywords:
            metadata['keywords'] = [k.strip() for k in keywords.split(',')]

        # 4. 提取作者
        metadata['author'] = (
            _get_meta_content(soup, 'author') or
            _get_meta_content(soup, 'article:author') or
            _get_meta_content(soup, 'twitter:creator')
        )

        # 5. 提取发布时间（优先级：JSON-LD > meta tag > time tag）
        metadata['published_at'] = _extract_published_time(soup)

        # 6. 提取语言
        html_tag = soup.find('html')
        if html_tag and html_tag.get('lang'):
            metadata['language'] = html_tag.get('lang')

        # 7. 提取 canonical URL
        canonical = soup.find('link', rel='canonical')
        if canonical:
            metadata['canonical_url'] = urljoin(base_url, canonical.get('href', ''))

        # 8. 从 JSON-LD 提取更丰富的结构化数据
        jsonld_data = _extract_jsonld(soup)
        if jsonld_data:
            if not metadata['published_at'] and 'datePublished' in jsonld_data:
                metadata['published_at'] = jsonld_data['datePublished']
            if not metadata['author'] and 'author' in jsonld_data:
                author = jsonld_data['author']
                if isinstance(author, dict):
                    metadata['author'] = author.get('name')
                elif isinstance(author, str):
                    metadata['author'] = author

    except Exception as e:
        logger.warning(f"Failed to extract metadata from {base_url}: {e}")

    return metadata


def _get_meta_content(soup: BeautifulSoup, property_name: str) -> Optional[str]:
    """获取 meta 标签的 content 属性"""
    # 尝试 property（Open Graph）
    tag = soup.find('meta', property=property_name)
    if tag:
        return tag.get('content')

    # 尝试 name
    tag = soup.find('meta', attrs={'name': property_name})
    if tag:
        return tag.get('content')

    return None


def _extract_published_time(soup: BeautifulSoup) -> Optional[str]:
    """
    提取发布时间

    尝试多种策略：
    1. meta article:published_time
    2. meta publish_date
    3. time[datetime]
    4. 其他常见时间 meta 标签
    """
    # 策略 1: Open Graph 和专用 meta 标签
    time_meta_tags = [
        'article:published_time',
        'publish_date',
        'publishedDate',
        'datePublished',
        'date',
        'DC.date.issued',
        'dc.date',
    ]

    for tag_name in time_meta_tags:
        time_str = _get_meta_content(soup, tag_name)
        if time_str:
            return _normalize_datetime(time_str)

    # 策略 2: time 标签
    time_tag = soup.find('time')
    if time_tag:
        datetime_attr = time_tag.get('datetime')
        if datetime_attr:
            return _normalize_datetime(datetime_attr)

    # 策略 3: 从文本中匹配日期模式（作为最后手段）
    # 例如：发表于 2024-01-15
    text_patterns = [
        r'发表于\s*(\d{4}[年/-]\d{1,2}[月/-]\d{1,2})',
        r'published\s*on\s*(\w+\s+\d{1,2},?\s+\d{4})',
        r'(\d{4}[/-]\d{1,2}[/-]\d{1,2})',
    ]

    body_text = soup.get_text()[:5000]  # 只检查前 5000 字符
    for pattern in text_patterns:
        match = re.search(pattern, body_text, re.IGNORECASE)
        if match:
            return _normalize_datetime(match.group(1))

    return None


def _extract_jsonld(soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
    """提取 JSON-LD 结构化数据"""
    try:
        script_tags = soup.find_all('script', type='application/ld+json')
        for script in script_tags:
            if script.string:
                data = json.loads(script.string)
                # 优先使用 Article 类型的数据
                if isinstance(data, dict):
                    if data.get('@type') in ['Article', 'NewsArticle', 'BlogPosting']:
                        return data
                    # 处理 @graph 数组
                    graph = data.get('@graph', [])
                    for item in graph:
                        if isinstance(item, dict) and item.get('@type') in ['Article', 'NewsArticle']:
                            return item
        return None
    except (json.JSONDecodeError, Exception) as e:
        logger.debug(f"Failed to parse JSON-LD: {e}")
        return None


def _normalize_datetime(time_str: str) -> Optional[str]:
    """
    标准化日期时间字符串为 ISO 8601 格式

    Args:
        time_str: 原始时间字符串

    Returns:
        ISO 8601 格式字符串或 None
    """
    if not time_str:
        return None

    # 常见的日期时间格式
    formats = [
        '%Y-%m-%dT%H:%M:%S.%fZ',
        '%Y-%m-%dT%H:%M:%SZ',
        '%Y-%m-%dT%H:%M:%S%z',
        '%Y-%m-%dT%H:%M:%S',
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%d',
        '%Y年%m月%d日',
        '%Y/%m/%d',
        '%B %d, %Y',
        '%b %d, %Y',
    ]

    # 清理字符串
    time_str = time_str.strip()

    for fmt in formats:
        try:
            dt = datetime.strptime(time_str, fmt)
            return dt.isoformat()
        except ValueError:
            continue

    # 如果所有格式都失败，返回原始字符串
    logger.debug(f"Could not parse datetime: {time_str}")
    return time_str
