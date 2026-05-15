"""
深度爬取 BFS 路径过滤器

包装 is_excluded_domain() 为 Crawl4AI URLFilter 子类，
在 BFS 发现链接时自动过滤低价值 URL（百度搜索、贴吧、电商等）。
"""

from crawl4ai.deep_crawling.filters import URLFilter
from .filters import is_excluded_domain


class ExcludedDomainFilter(URLFilter):
    """包装 is_excluded_domain() 为 Crawl4AI URLFilter。

    is_excluded_domain() 返回 True = 应排除
    URLFilter.apply() 返回 True = 应保留
    因此需要 INVERT 返回值。
    """

    def apply(self, url: str) -> bool:
        try:
            return not is_excluded_domain(url)
        except Exception:
            return True  # fail open
