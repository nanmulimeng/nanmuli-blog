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
                 'excluded_selector', 'prune_threshold', 'wait_until', 'page_timeout',
                 'remove_overlay_elements', 'max_retries', 'wait_for',
                 'delay_before_return_html', 'mean_delay', 'max_range',
                 'remove_consent_popups')

    def __init__(self, config: Optional[object] = None):
        if config is None:
            self.text_mode = True
            self.light_mode = False
            self.word_count_threshold = 10
            self.excluded_tags = DEFAULT_EXCLUDED_TAGS.copy()
            self.excluded_selector = ".sidebar,.nav-links,.footer-links,.related-posts,.recommendations,#sidebar,#comments,.comment-list,.sidebar-block,.left-sidebar,#left-sidebar,.right-sidebar,#right-sidebar,.side-navigator-wrap,.side-navigator,.breadcrumb,.breadcrumbs,.cookie-banner,.cookie-consent,.newsletter-signup,.newsletter,.social-share,.share-buttons,.pagination,.page-nav,.copyright,.site-footer,.site-footer--copyright,.site-footer--nav,.feedback-widget,.read-more,.related-articles,.author-bio,.toc,.table-of-contents,.ad-container,.advertisement,.s-sidebarwidget,.entry-footer,.download-app,.download-popover,.global-component-box,.top-banners-container,[role='complementary'],[role='contentinfo'],[aria-label='Cookie notice'],[aria-label='Cookie banner']"
            self.prune_threshold = 0.5
            self.wait_until = "networkidle"
            self.page_timeout = 60000
            self.remove_overlay_elements = True
            self.max_retries = 2
            self.wait_for = None
            self.delay_before_return_html = 1.0
            self.mean_delay = 0.5
            self.max_range = 0.5
            self.remove_consent_popups = True
        else:
            self.text_mode = getattr(config, 'text_mode', True)
            self.light_mode = getattr(config, 'light_mode', False)
            self.word_count_threshold = getattr(config, 'word_count_threshold', 10)
            self.excluded_tags = getattr(config, 'excluded_tags', DEFAULT_EXCLUDED_TAGS.copy())
            self.excluded_selector = getattr(config, 'excluded_selector', ".sidebar,.nav-links,.footer-links,.related-posts,.recommendations,#sidebar,#comments,.comment-list,.sidebar-block,.left-sidebar,#left-sidebar,.right-sidebar,#right-sidebar,.side-navigator-wrap,.side-navigator,.breadcrumb,.breadcrumbs,.cookie-banner,.cookie-consent,.newsletter-signup,.newsletter,.social-share,.share-buttons,.pagination,.page-nav,.copyright,.site-footer,.site-footer--copyright,.site-footer--nav,.feedback-widget,.read-more,.related-articles,.author-bio,.toc,.table-of-contents,.ad-container,.advertisement,.s-sidebarwidget,.entry-footer,.download-app,.download-popover,.global-component-box,.top-banners-container,[role='complementary'],[role='contentinfo'],[aria-label='Cookie notice'],[aria-label='Cookie banner']")
            self.prune_threshold = getattr(config, 'prune_threshold', 0.5)
            self.wait_until = getattr(config, 'wait_until', "networkidle")
            self.page_timeout = getattr(config, 'page_timeout', 60000)
            self.remove_overlay_elements = getattr(config, 'remove_overlay_elements', True)
            self.max_retries = getattr(config, 'max_retries', 2)
            self.wait_for = getattr(config, 'wait_for', None)
            self.delay_before_return_html = getattr(config, 'delay_before_return_html', 1.0)
            self.mean_delay = getattr(config, 'mean_delay', 0.5)
            self.max_range = getattr(config, 'max_range', 0.5)
            self.remove_consent_popups = getattr(config, 'remove_consent_popups', True)
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
        viewport_width=1920,
        viewport_height=1080,
        user_agent_mode="random",
        headers={
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Sec-CH-UA": '"Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"',
            "Sec-CH-UA-Platform": '"Windows"',
        },
        enable_stealth=True,
        avoid_ads=True,
        ignore_https_errors=True,
        extra_args=extra_args
    )


def get_crawler_run_config(
    word_count_threshold: int = 3,
    excluded_tags: list[str] = None,
    excluded_selector: str = "",
    prune_threshold: float = 0.5,
    wait_until: str = "networkidle",
    page_timeout: int = 60000,
    remove_overlay_elements: bool = True,
    max_retries: int = 2,
    mean_delay: float = 0.5,
    max_range: float = 0.5,
    delay_before_return_html: float = 1.0,
    remove_consent_popups: bool = True,
    wait_for: str = None,
    wait_for_timeout: int = None,
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
        max_retries: 爬取失败自动重试次数
        mean_delay: BFS 请求间平均延迟（秒）
        max_range: BFS 请求延迟随机范围（秒）
        delay_before_return_html: 返回 HTML 前额外等待时间（秒）
        remove_consent_popups: 是否自动移除 GDPR/Cookie 弹窗

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
        simulate_user=True,
        override_navigator=True,
        scan_full_page=True,
        scroll_delay=0.5,
        max_retries=max_retries,
        mean_delay=mean_delay,
        max_range=max_range,
        delay_before_return_html=delay_before_return_html,
        remove_consent_popups=remove_consent_popups,
        wait_for=wait_for,
        wait_for_timeout=wait_for_timeout,
        markdown_generator=DefaultMarkdownGenerator(
            content_filter=PruningContentFilter(
                threshold=prune_threshold,
                threshold_type="fixed"
            )
        )
    )


def get_search_run_config(page_timeout: int = 15000, delay_before_return_html: float = 0.5) -> CrawlerRunConfig:
    """
    获取搜索引擎结果页专用的轻量爬虫配置。

    针对搜索页优化：
    - 无需模拟人类交互（simulate_user=False）
    - 无需 magic 模式
    - 只需 DOM 加载完成即可解析（domcontentloaded）
    - 不生成 markdown，只取 raw HTML
    - 小延迟等待 JS 渲染搜索结果
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
        delay_before_return_html=delay_before_return_html,
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


# 内联导航最小链接数：单行包含≥此数的 markdown 链接视为导航
_MIN_INLINE_LINKS = 3
# 内联导航链接密度阈值：链接文本占行文本比超过此值视为导航
_MAX_INLINE_RATIO = 0.7
# 小导航组最小链接行数（3-7项，密度 > 此阈值时触发过滤）
_MIN_SMALL_NAV_LINES = 3
_MAX_SMALL_NAV_RATIO = 0.80


def _is_inline_nav(line: str) -> bool:
    """检测管道/逗号分隔的内联导航行

    如: [Home](/) | [Blog](/b) | [About](/a)
    """
    import re
    s = line.strip()
    links = re.findall(r'\[([^\]]*)\]\([^)]+\)', s)
    if len(links) < _MIN_INLINE_LINKS:
        return False
    # 先将 [text](url) 替换为纯文本，再计算链接密度
    clean = re.sub(r'\[([^\]]*)\]\([^)]+\)', r'\1', s)
    clean = re.sub(r'[#*>\-\[\]\(\)\!`|~\s]', '', clean)
    if len(clean) == 0:
        return False
    link_len = sum(len(l) for l in links)
    return link_len / len(clean) > _MAX_INLINE_RATIO


def _filter_nav_noise(markdown: str) -> str:
    """过滤导航/侧边栏噪音：移除高链接密度的连续性列表行"""
    import re
    lines = markdown.split('\n')
    if not markdown.strip():
        return markdown

    # 标记每行是否为"链接型列表行"（含编号列表）
    def _is_link_bullet(line: str) -> bool:
        s = line.strip()
        if not s:
            return False
        # - * + 或 1. 2) 3) 等编号格式
        return bool(re.match(r'^([-*+]|\d+[.)]\s)', s)) and '[' in s and '](' in s

    # 扫描连续链接行组
    to_remove = set()
    i = 0
    while i < len(lines):
        # 跳过单独的内联导航行
        if _is_inline_nav(lines[i]):
            to_remove.add(i)
            logger.debug("[Filter] Dropped inline nav line %d", i)
            i += 1
            continue

        if _is_link_bullet(lines[i]):
            start = i
            while i < len(lines) and (_is_link_bullet(lines[i]) or lines[i].strip() == ''):
                i += 1
            group = lines[start:i]
            link_lines = [l for l in group if _is_link_bullet(l)]
            if len(link_lines) >= _MIN_NAV_BLOCK_LINES:
                group_text = '\n'.join(group)
                ratio = _link_text_ratio(group_text)
                if ratio > _MAX_LINK_RATIO:
                    for j in range(start, i):
                        to_remove.add(j)
                    logger.debug(
                        "[Filter] Dropped nav group: %d link lines, ratio=%.2f",
                        len(link_lines), ratio
                    )
            elif len(link_lines) >= _MIN_SMALL_NAV_LINES:
                # 小导航组（3-7项）用更高密度阈值
                group_text = '\n'.join(group)
                ratio = _link_text_ratio(group_text)
                if ratio > _MAX_SMALL_NAV_RATIO:
                    for j in range(start, i):
                        to_remove.add(j)
                    logger.debug(
                        "[Filter] Dropped small nav group: %d link lines, ratio=%.2f",
                        len(link_lines), ratio
                    )
        else:
            i += 1

    if to_remove:
        kept = [l for idx, l in enumerate(lines) if idx not in to_remove]
        return '\n'.join(kept)
    return markdown


_BOILERPLATE_PATTERNS = [
    (r'(?i)^.*\b(we use cookies|accept cookies|cookie policy|privacy policy|'
     r'cookie consent|this site uses cookies|consent preferences)\b.*$', 'cookie'),
    (r'(?i)^.*\b(subscribe to|newsletter|sign up for|email updates|'
     r'join our mailing|get notified|never miss a post)\b.*$', 'newsletter'),
    (r'(?i)^.*\b(share on|share this|follow us on|tweet this|'
     r'pin this|share this post|share this article)\b.*$', 'social'),
    (r'(?i)^.*\b(copyright\s+\d{4}|all rights reserved|\(c\)|©)\b.*$', 'copyright'),
    (r'(?i)^.*\b(page \d+ of \d+|previous page|next page|pagination|'
     r'load more|show more)\b.*$', 'pagination'),
]


def _filter_boilerplate(markdown: str) -> str:
    """移除常见文案噪音：Cookie/Newsletter/社交分享/版权/分页"""
    import re
    lines = markdown.split('\n')
    kept = []
    for line in lines:
        is_boilerplate = False
        for pattern, _tag in _BOILERPLATE_PATTERNS:
            if re.match(pattern, line):
                is_boilerplate = True
                logger.debug("[Filter] Dropped boilerplate (%s): %s", _tag, line[:80])
                break
        if not is_boilerplate:
            kept.append(line)
    return '\n'.join(kept)


def _filter_breadcrumbs(markdown: str) -> str:
    """移除面包屑导航行

    模式: [Home](/) > [Blog](/b) > [Post](/p)
          Home / Blog / Post
          Home > Blog > Post
    """
    import re
    lines = markdown.split('\n')
    kept = []
    for line in lines:
        s = line.strip()
        skip = False

        # 检测 markdown 链接形式的面包屑: [text](url) [>/>] [text](url) ...
        links = re.findall(r'\[([^\]]*)\]\([^)]+\)', s)
        if len(links) >= 2:
            separators = re.findall(r'\s*[>\/]\s*', s)
            if len(separators) >= len(links) - 1:
                # 先将 [text](url) 替换为纯文本，再计算链接密度
                clean = re.sub(r'\[([^\]]*)\]\([^)]+\)', r'\1', s)
                clean = re.sub(r'[#*>\-\[\]\(\)\!`|~\s]', '', clean)
                if len(clean) > 0:
                    link_total = sum(len(l) for l in links)
                    if link_total / len(clean) > 0.85:
                        logger.debug("[Filter] Dropped breadcrumbs: %s", s[:80])
                        skip = True
        elif len(links) == 0:
            # 检测纯文本面包屑: Home / Blog / Current Post
            parts = re.split(r'\s*[>\/]\s*', s)
            if len(parts) >= 3 and all(len(p.strip()) < 30 for p in parts):
                clean_parts = ''.join(p.strip() for p in parts)
                clean_line = re.sub(r'[>\/\s]', '', s)
                if len(clean_line) > 0 and len(clean_parts) / len(clean_line) > 0.85:
                    logger.debug("[Filter] Dropped text breadcrumbs: %s", s[:80])
                    skip = True

        if not skip:
            kept.append(line)
    return '\n'.join(kept)


def extract_markdown(crawl4ai_result) -> str:
    """
    从 Crawl4AI 结果中提取 markdown，带智能回退和噪音过滤：

    1. 优先 fit_markdown（PruningContentFilter 去噪后）
    2. 当 fit_markdown 不足 raw_markdown 的 30% 时回退 raw_markdown
    3. 过滤面包屑 / 文案噪音 / 导航区块
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
            # Progressive fallback: 先过滤 raw 再比较，避免直接使用未过滤 raw
            raw_filtered = _filter_breadcrumbs(raw)
            raw_filtered = _filter_boilerplate(raw_filtered)
            raw_filtered = _filter_nav_noise(raw_filtered)
            if raw_filtered and len(fit) / max(len(raw_filtered), 1) >= _FIT_MIN_RATIO:
                # 过滤后 fit 与 raw_filtered 已接近，fit 质量更优
                logger.info(
                    "[Markdown] fit/raw=%.1f%% but fit/raw_filtered=%.1f%%, "
                    "keeping fit (fit=%s, raw=%s, raw_filtered=%s)",
                    ratio * 100, len(fit) / max(len(raw_filtered), 1) * 100,
                    len(fit), len(raw), len(raw_filtered)
                )
                selected = fit
            else:
                logger.info(
                    "[Markdown] fit/raw=%.1f%%, using filtered raw "
                    "(fit=%s, raw=%s, raw_filtered=%s)",
                    ratio * 100, len(fit), len(raw), len(raw_filtered)
                )
                selected = raw_filtered if raw_filtered else raw
                # raw_filtered 已过滤，直接返回
                return selected
        else:
            selected = fit
    elif fit:
        selected = fit
    elif raw:
        selected = raw
    else:
        selected = ""

    if not selected:
        return ""

    # 噪音过滤链：面包屑 → 文案噪音 → 导航区块
    selected = _filter_breadcrumbs(selected)
    selected = _filter_boilerplate(selected)
    return _filter_nav_noise(selected)
