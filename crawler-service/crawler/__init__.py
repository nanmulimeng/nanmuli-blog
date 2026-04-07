"""
Web Collector - Crawler Package

基于 Crawl4AI 的网页内容采集实现
"""

__version__ = "1.0.0"

from .single import crawl_single_page
from .deep import crawl_deep_pages
from .search import crawl_by_keyword

__all__ = [
    "crawl_single_page",
    "crawl_deep_pages",
    "crawl_by_keyword",
]
