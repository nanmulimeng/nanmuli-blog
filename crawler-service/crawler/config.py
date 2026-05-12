"""
Crawl4AI 配置模块

提供针对内容采集场景优化的配置
"""

from typing import Optional

from crawl4ai import BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from crawl4ai.content_filter_strategy import PruningContentFilter

import logging
import time
import urllib.request

logger = logging.getLogger(__name__)

# 代理健康检查配置
_PROXY_CHECK_TIMEOUT = 5          # HTTP 请求超时（秒）
_PROXY_CHECK_URL = "https://www.baidu.com"  # 用于检测代理连通性的 URL
_PROXY_CACHE_TTL = 30             # 健康检查结果缓存时间（秒），避免高频爬取时重复检测
_proxy_cache: dict[str, tuple[float, bool]] = {}  # {proxy_url: (timestamp, is_healthy)}

# 默认排除标签
# 注意：不排除 <header>，因为 HTML5 文章中 <header> 常包含标题/作者/日期
# PruningContentFilter 会通过内容密度自动过滤导航型 header
DEFAULT_EXCLUDED_TAGS = ["nav", "footer", "aside", "script", "style", "noscript", "iframe"]


def check_proxy_health(proxy_url: str) -> bool:
    """
    检测代理服务器是否可用。

    通过 HTTP CONNECT 代理发出 HTTPS 请求，
    验证代理是否在线并能成功建立隧道。

    Args:
        proxy_url: 代理地址（如 http://127.0.0.1:7890）

    Returns:
        True 表示代理可用
    """
    if not proxy_url:
        return False
    try:
        proxy_handler = urllib.request.ProxyHandler({
            'https': proxy_url,
            'http': proxy_url,
        })
        opener = urllib.request.build_opener(proxy_handler)
        req = urllib.request.Request(_PROXY_CHECK_URL, method='HEAD')
        resp = opener.open(req, timeout=_PROXY_CHECK_TIMEOUT)
        return resp.status in (200, 301, 302, 307, 308)
    except Exception:
        return False


def get_effective_proxy(proxy_url: str) -> str:
    """
    全项目统一的代理决策入口。

    - proxy_url 为空 → 返回空字符串（直连）
    - 代理健康检查缓存命中且健康 → 返回 proxy_url
    - 代理不可达 → 返回空字符串 + 记录 WARNING

    所有需要代理的代码（BrowserConfig / httpx / urllib）均应通过此函数
    获取有效代理地址，而非直接读取 settings.proxy_url。

    Returns:
        有效代理 URL，或空字符串表示直连
    """
    if not proxy_url:
        return ""

    # 读取缓存
    now = time.monotonic()
    cached = _proxy_cache.get(proxy_url)
    if cached:
        ts, healthy = cached
        if now - ts < _PROXY_CACHE_TTL:
            if healthy:
                return proxy_url
            else:
                return ""

    # 执行健康检查
    is_healthy = check_proxy_health(proxy_url)
    _proxy_cache[proxy_url] = (now, is_healthy)

    if is_healthy:
        return proxy_url

    logger.warning("[Proxy] %s is unreachable, using direct connection", proxy_url)
    return ""


class RunParams:
    """从 Pydantic/dict config 提取的运行参数"""
    __slots__ = ('text_mode', 'light_mode', 'word_count_threshold', 'excluded_tags',
                 'excluded_selector', 'prune_threshold', 'wait_until', 'page_timeout', 'remove_overlay_elements')

    def __init__(self, config: Optional[object] = None):
        if config is None:
            self.text_mode = True
            self.light_mode = False
            self.word_count_threshold = 10
            self.excluded_tags = DEFAULT_EXCLUDED_TAGS.copy()
            self.excluded_selector = ".sidebar,.nav-links,.footer-links,.related-posts,.recommendations,#sidebar,#comments,.comment-list"
            self.prune_threshold = 0.5
            self.wait_until = "load"
            self.page_timeout = 60000
            self.remove_overlay_elements = True
        else:
            self.text_mode = getattr(config, 'text_mode', True)
            self.light_mode = getattr(config, 'light_mode', False)
            self.word_count_threshold = getattr(config, 'word_count_threshold', 10)
            self.excluded_tags = getattr(config, 'excluded_tags', DEFAULT_EXCLUDED_TAGS.copy())
            self.excluded_selector = getattr(config, 'excluded_selector', ".sidebar,.nav-links,.footer-links,.related-posts,.recommendations,#sidebar,#comments,.comment-list")
            self.prune_threshold = getattr(config, 'prune_threshold', 0.5)
            self.wait_until = getattr(config, 'wait_until', "load")
            self.page_timeout = getattr(config, 'page_timeout', 60000)
            self.remove_overlay_elements = getattr(config, 'remove_overlay_elements', True)


def get_browser_config(text_mode: bool = True, light_mode: bool = False,
                        proxy: str = '') -> BrowserConfig:
    """
    获取浏览器配置

    Args:
        text_mode: 不加载图片，节省内存和带宽
        light_mode: 轻量模式，减少资源占用（可能影响 SPA 渲染，默认关闭）
        proxy: 代理服务器地址（如 http://127.0.0.1:7890），
               不可用时自动降级直连并记录警告

    Returns:
        BrowserConfig 实例
    """
    extra_args = [
        "--disable-gpu",
        "--disable-dev-shm-usage",
        "--disable-setuid-sandbox",
        "--no-sandbox",
        "--disable-blink-features=AutomationControlled",
        "--disable-features=IsolateOrigins,site-per-process",
        "--disable-site-isolation-trials",
        "--disable-web-security",
        "--disable-features=BlockInsecurePrivateNetworkRequests",
    ]

    # 代理健康检查 + 自动降级：统一通过 get_effective_proxy() 决策
    effective_proxy = get_effective_proxy(proxy)
    if effective_proxy:
        extra_args.append(f"--proxy-server={effective_proxy}")

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
        extra_args=extra_args
    )


def get_crawler_run_config(
    word_count_threshold: int = 3,
    excluded_tags: list[str] = None,
    excluded_selector: str = "",
    prune_threshold: float = 0.5,
    wait_until: str = "load",
    page_timeout: int = 60000,
    remove_overlay_elements: bool = True
) -> CrawlerRunConfig:
    """
    获取爬虫运行配置

    Args:
        word_count_threshold: 过滤短文本块的阈值
        excluded_tags: 排除的 HTML 标签
        excluded_selector: 排除的 CSS 选择器（如 .sidebar, #comments）
        prune_threshold: PruningContentFilter 阈值（越高越激进去噪）
        wait_until: 页面加载完成条件
        page_timeout: 页面加载超时时间（毫秒）
        remove_overlay_elements: 是否移除弹窗/覆盖层元素

    Returns:
        CrawlerRunConfig 实例
    """
    if excluded_tags is None:
        excluded_tags = DEFAULT_EXCLUDED_TAGS.copy()

    return CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        word_count_threshold=word_count_threshold,
        excluded_tags=excluded_tags,
        excluded_selector=excluded_selector,
        remove_overlay_elements=remove_overlay_elements,
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
                threshold=prune_threshold,
                threshold_type="fixed"
            )
        )
    )


def get_search_run_config(page_timeout: int = 15000) -> CrawlerRunConfig:
    """
    获取搜索引擎结果页专用的轻量爬虫配置。

    针对搜索页优化：
    - 无需模拟人类交互（simulate_user=False）
    - 无需 magic 模式
    - 只需 DOM 加载完成即可解析（domcontentloaded）
    - 不生成 markdown，只取 raw HTML
    """
    return CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        word_count_threshold=3,
        excluded_tags=DEFAULT_EXCLUDED_TAGS.copy(),
        remove_overlay_elements=True,
        remove_forms=False,
        exclude_external_links=True,
        wait_until="domcontentloaded",
        page_timeout=page_timeout,
        magic=False,
        simulate_user=False,
        override_navigator=True,
        scan_full_page=False,
        scroll_delay=0.0,
        # 搜索页不需要 markdown 生成器，我们只解析 raw HTML
    )


# fit_markdown 不足 raw_markdown 的此比例时回退 raw
_FIT_MIN_RATIO = 0.3

# 导航噪音过滤阈值：区域内链接文本占比超过此比例则丢弃
_MAX_LINK_RATIO = 0.55
# 导航噪音过滤阈值：区域内总行数超过此值的纯链接列表将被丢弃
_MIN_NAV_BLOCK_LINES = 8


def _link_text_ratio(block: str) -> float:
    """计算文本块中链接显示文本占全部可见文本的比例（排除URL影响）"""
    import re
    # 提取链接显示文本
    link_texts = re.findall(r'\[([^\]]*)\]\([^)]+\)', block)
    link_len = sum(len(t) for t in link_texts)
    # 将所有 [text](url) 替换为 text，然后移除格式标记
    clean = re.sub(r'\[([^\]]*)\]\([^)]+\)', r'\1', block)
    clean = re.sub(r'[#*>\-\[\]\(\)\!`|~\s]', '', clean)
    clean_len = len(clean)
    if clean_len == 0:
        return 0.0
    return link_len / clean_len


def _filter_nav_noise(markdown: str) -> str:
    """过滤导航/侧边栏噪音：移除高链接密度的连续性列表行"""
    import re
    lines = markdown.split('\n')
    if len(lines) < _MIN_NAV_BLOCK_LINES:
        return markdown

    # 标记每行是否为"链接型列表行"
    def _is_link_bullet(line: str) -> bool:
        s = line.strip()
        if not s:
            return False
        # 以 - * + 开头 + 包含 markdown 链接
        return bool(re.match(r'^[-*+]', s)) and '[' in s and '](' in s

    # 扫描连续链接行组
    to_remove = set()
    i = 0
    while i < len(lines):
        if _is_link_bullet(lines[i]):
            start = i
            while i < len(lines) and (_is_link_bullet(lines[i]) or lines[i].strip() == ''):
                i += 1
            group = lines[start:i]
            # 计算组内非空链接行数
            link_lines = [l for l in group if _is_link_bullet(l)]
            if len(link_lines) >= _MIN_NAV_BLOCK_LINES:
                # 验证链接密度
                group_text = '\n'.join(group)
                ratio = _link_text_ratio(group_text)
                if ratio > _MAX_LINK_RATIO:
                    for j in range(start, i):
                        to_remove.add(j)
                    logger.debug(
                        "[Filter] Dropped nav group: %d link lines, ratio=%.2f",
                        len(link_lines), ratio
                    )
        else:
            i += 1

    if to_remove:
        kept = [l for idx, l in enumerate(lines) if idx not in to_remove]
        return '\n'.join(kept)
    return markdown


def extract_markdown(crawl4ai_result) -> str:
    """
    从 Crawl4AI 结果中提取 markdown，带智能回退和导航噪音过滤：

    1. 优先 fit_markdown（PruningContentFilter 去噪后）
    2. 当 fit_markdown 不足 raw_markdown 的 30% 时回退 raw_markdown
       （说明 Pruning 过度裁剪）
    3. 对结果应用导航噪音过滤（移除高链接密度区块）
    4. 最终 fallback 到 str(result.markdown)
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

    selected = ""
    if fit and raw:
        ratio = len(fit) / len(raw) if len(raw) > 0 else 1.0
        if ratio < _FIT_MIN_RATIO:
            logger.info(
                "[Markdown] fit/raw ratio=%.1f%% < %s, "
                "falling back to raw_markdown (fit=%s, raw=%s)",
                ratio * 100, _FIT_MIN_RATIO, len(fit), len(raw)
            )
            selected = raw
        else:
            selected = fit
    elif fit:
        selected = fit
    elif raw:
        selected = raw
    else:
        selected = str(md_obj) if md_obj else ""

    return _filter_nav_noise(selected) if selected else ""
