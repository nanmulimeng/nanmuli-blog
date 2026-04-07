"""
Crawl4AI 配置模块

提供针对个人博客场景（2G 服务器）优化的配置
"""

from crawl4ai import BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from crawl4ai.content_filter_strategy import PruningContentFilter


def get_browser_config(text_mode: bool = True, light_mode: bool = True) -> BrowserConfig:
    """
    获取浏览器配置

    Args:
        text_mode: 不加载图片，节省内存和带宽
        light_mode: 轻量模式，减少资源占用

    Returns:
        BrowserConfig 实例
    """
    return BrowserConfig(
        headless=True,
        browser_type="chromium",
        text_mode=text_mode,
        light_mode=light_mode,
        java_script_enabled=True,
        viewport_width=1920,
        viewport_height=1080,
        extra_args=[
            "--disable-gpu",
            "--disable-dev-shm-usage",
            "--disable-setuid-sandbox",
            "--no-sandbox",
        ] if light_mode else []
    )


def get_crawler_run_config(
    word_count_threshold: int = 10,
    excluded_tags: list[str] = None,
    wait_until: str = "networkidle",
    page_timeout: int = 30000
) -> CrawlerRunConfig:
    """
    获取爬虫运行配置

    Args:
        word_count_threshold: 过滤短文本块的阈值
        excluded_tags: 排除的 HTML 标签
        wait_until: 页面加载完成条件
        page_timeout: 页面加载超时时间（毫秒）

    Returns:
        CrawlerRunConfig 实例
    """
    if excluded_tags is None:
        excluded_tags = ["nav", "footer", "aside", "header", "script", "style"]

    return CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        word_count_threshold=word_count_threshold,
        excluded_tags=excluded_tags,
        remove_overlay_elements=True,
        remove_forms=True,
        exclude_external_links=False,
        wait_until=wait_until,
        page_timeout=page_timeout,
        markdown_generator=DefaultMarkdownGenerator(
            content_filter=PruningContentFilter(
                threshold=0.48,
                threshold_type="fixed"
            )
        )
    )
