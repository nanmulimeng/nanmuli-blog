"""
Crawl4AI 配置模块

提供针对内容采集场景优化的配置
"""

from typing import Optional

from crawl4ai import BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from crawl4ai.content_filter_strategy import PruningContentFilter

import logging

logger = logging.getLogger(__name__)

# 默认排除标签
# 注意：不排除 <header>，因为 HTML5 文章中 <header> 常包含标题/作者/日期
# PruningContentFilter 会通过内容密度自动过滤导航型 header
DEFAULT_EXCLUDED_TAGS = ["nav", "footer", "aside", "script", "style", "noscript", "iframe"]


class RunParams:
    """从 Pydantic/dict config 提取的运行参数"""
    __slots__ = ('text_mode', 'light_mode', 'word_count_threshold', 'excluded_tags', 'wait_until', 'page_timeout')

    def __init__(self, config: Optional[object] = None):
        if config is None:
            self.text_mode = True
            self.light_mode = False
            self.word_count_threshold = 15
            self.excluded_tags = DEFAULT_EXCLUDED_TAGS.copy()
            self.wait_until = "networkidle"
            self.page_timeout = 60000
        else:
            self.text_mode = getattr(config, 'text_mode', True)
            self.light_mode = getattr(config, 'light_mode', False)
            self.word_count_threshold = getattr(config, 'word_count_threshold', 15)
            self.excluded_tags = getattr(config, 'excluded_tags', DEFAULT_EXCLUDED_TAGS.copy())
            self.wait_until = getattr(config, 'wait_until', "networkidle")
            self.page_timeout = getattr(config, 'page_timeout', 60000)


def get_browser_config(text_mode: bool = True, light_mode: bool = False) -> BrowserConfig:
    """
    获取浏览器配置

    Args:
        text_mode: 不加载图片，节省内存和带宽
        light_mode: 轻量模式，减少资源占用（可能影响 SPA 渲染，默认关闭）

    Returns:
        BrowserConfig 实例
    """
    return BrowserConfig(
        headless=True,
        browser_type="chromium",
        text_mode=text_mode,
        light_mode=light_mode,
        java_script_enabled=True,
        viewport_width=1280,
        viewport_height=720,
        enable_stealth=True,       # 启用 stealth 模式反检测
        avoid_ads=True,            # 阻止广告/追踪域名请求
        ignore_https_errors=True,  # 忽略 HTTPS 证书错误
        extra_args=[
            "--disable-gpu",
            "--disable-dev-shm-usage",
            "--disable-setuid-sandbox",
            "--no-sandbox",
            "--disable-blink-features=AutomationControlled",
        ]
    )


def get_crawler_run_config(
    word_count_threshold: int = 3,
    excluded_tags: list[str] = None,
    wait_until: str = "networkidle",
    page_timeout: int = 60000
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
        excluded_tags = DEFAULT_EXCLUDED_TAGS.copy()

    return CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        word_count_threshold=word_count_threshold,
        excluded_tags=excluded_tags,
        remove_overlay_elements=True,
        remove_forms=False,
        exclude_external_links=True,
        wait_until=wait_until,
        page_timeout=page_timeout,
        magic=True,
        simulate_user=True,        # 模拟人类交互（鼠标移动等）
        override_navigator=True,   # 伪造 navigator 属性绕过检测
        scan_full_page=True,
        scroll_delay=0.5,
        markdown_generator=DefaultMarkdownGenerator(
            content_filter=PruningContentFilter(
                threshold=0.5,
                threshold_type="fixed"
            )
        )
    )


# fit_markdown 不足 raw_markdown 的此比例时回退 raw
_FIT_MIN_RATIO = 0.3


def extract_markdown(crawl4ai_result) -> str:
    """
    从 Crawl4AI 结果中提取 markdown，带智能回退：

    1. 优先 fit_markdown（PruningContentFilter 去噪后）
    2. 当 fit_markdown 不足 raw_markdown 的 30% 时回退 raw_markdown
       （说明 Pruning 过度裁剪）
    3. 最终 fallback 到 str(result.markdown)
    """
    md_obj = getattr(crawl4ai_result, 'markdown', None)
    if not md_obj:
        return ""

    fit = getattr(md_obj, 'fit_markdown', None) or ""
    raw = getattr(md_obj, 'raw_markdown', None) or ""

    # 确保 UTF-8 字符串
    if isinstance(fit, bytes):
        fit = fit.decode("utf-8", errors="replace")
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="replace")

    if fit and raw:
        ratio = len(fit) / len(raw) if len(raw) > 0 else 1.0
        if ratio < _FIT_MIN_RATIO:
            logger.info(
                f"[Markdown] fit/raw ratio={ratio:.1%} < {_FIT_MIN_RATIO}, "
                f"falling back to raw_markdown (fit={len(fit)}, raw={len(raw)})"
            )
            return raw
        return fit

    if fit:
        return fit
    if raw:
        return raw

    return str(md_obj) if md_obj else ""
