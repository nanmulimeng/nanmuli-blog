"""
页面类型分类器

在质量评分之前检测非文章页面（SERP/列表/论坛），节省 CPU 和 AI token。
分类为 serp/listing/forum 的页面直接标记失败，不进入质量评分和 AI 整理。
"""

import re
import logging
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# 搜索引擎结果页 URL 特征
_SERP_URL_PATTERNS = [
    '/search?', '/s?', '/query?', '/find?',
    'baidu.com/s', 'baidu.com/search',
    'google.com/search',
    'bing.com/search',
    'sogou.com/web',
    'so.com/s',           # 360 搜索
    'm.sm.cn/s',          # 神马搜索
]

# 搜索引擎首页域名（根路径 `/` 或空）= 无内容价值
_SERP_ROOT_DOMAINS = {
    'baidu.com', 'www.baidu.com', 'm.baidu.com',
    'google.com', 'www.google.com',
    'bing.com', 'www.bing.com',
    'sogou.com', 'www.sogou.com',
    'so.com', 'www.so.com',     # 360 搜索
    'sm.cn', 'm.sm.cn',         # 神马搜索
}

# SERP UI 元素关键词
_SERP_UI_PATTERNS = [
    r'约[\d,]+条结果', r'约[\d,]+个结果',
    r'相关搜索', r'相关推荐', r'大家还在搜',
    r'下一页', r'上一页',
    r'People also ask', r'Related searches',
]

# 搜索引擎首页标题特征
_SERP_HOMEPAGE_TITLES = [
    '百度一下', '百度搜索',
    'Google', 'google',
    'Bing', 'bing',
    '搜狗搜索', '搜狗',
]

# 列表/目录页 URL 特征
_LISTING_URL_PATTERNS = [
    '/tag/', '/tags/', '/category/', '/categories/',
    '/archives/', '/archive/', '/page/', '/author/',
]

# 论坛 URL 特征
_FORUM_URL_PATTERNS = [
    '/forum-', '/thread-', '/f/', '/t/',
    '/topic-', '/board-',
]

# 论坛 UI 元素
_FORUM_UI_PATTERNS = [
    r'\d+\s*(回复|条回复|评论)', r'\d+\s*(浏览|查看)',
    r'最后回复', r'最后发表', r'置顶', r'精华', r'加精',
    r'版主', r'楼主', r'沙发', r'板凳', r'地板',
]

# 登录/认证页 URL 特征
_LOGIN_URL_PATTERNS = [
    '/login', '/signin', '/sign-in', '/auth/',
    '/register', '/signup', '/sign-up',
    '/oauth/', '/sso/', '/cas/',
]

# 登录页内容特征
_LOGIN_CONTENT_PATTERNS = [
    r'忘记密码', r'找回密码', r'重置密码',
    r'注册账号', r'还没有账号', r'新用户注册',
    r'Forgot password', r'Reset password',
    r'Create account', r'Sign up',
    r'记住我', r'Remember me',
]

# 404/错误页标题特征（避免宽泛的"error"/"错误"以免误杀正常文章标题）
_ERROR_TITLE_PATTERNS = [
    '404', 'page not found', '页面未找到', '找不到页面',
    'not found', '页面不存在',
    '403', 'forbidden', '禁止访问',
    '500', 'internal server error', '服务器错误',
    '服务器内部错误', 'bad request', 'service unavailable',
]

# 付费墙内容特征（每个匹配独立计分，允许多个信号累加）
_PAYWALL_CONTENT_PATTERNS = [
    r'解锁全文', r'展开剩余', r'展开全文', r'查看完整内容',
    r'会员免费读', r'开通会员', r'订阅全文',
    r'购买后查看', r'付费阅读', r'VIP\s*(专享|免费|特权)',
    r'剩余\s*\d+%\s*内容', r'已加载\s*\d+%',
]

# 付费墙 URL 特征
_PAYWALL_URL_PATTERNS = [
    '/premium/', '/paywall/', '/member/', '/subscribe/',
    '/purchase/', '/vip/', '/paid/',
]


@dataclass
class PageClassification:
    """页面分类结果"""
    page_type: str  # "article" | "serp" | "listing" | "forum" | "unknown"
    confidence: float  # 0-1
    signals: list = field(default_factory=list)

    @property
    def is_non_article(self) -> bool:
        return self.page_type in ("serp", "listing", "forum", "login", "error", "paywall")


def classify_page(content: str, url: str = "", title: str = "") -> PageClassification:
    """分类页面类型。

    按优先级检测：
    1. SERP (搜索引擎结果页) — 信号最明确
    2. Listing (列表/目录页)
    3. Forum (论坛列表页)
    4. Unknown (fail open，放行)

    Args:
        content: 页面 markdown 内容
        url: 页面 URL
        title: 页面标题

    Returns:
        PageClassification 结果
    """
    if not content:
        return PageClassification("unknown", 0, ["empty_content"])

    url = url or ""
    title = title or ""

    # === 1. SERP 检测 ===
    serp_signals, serp_score = _detect_serp(content, url, title)
    if serp_score >= 5:
        return PageClassification("serp", min(serp_score / 8, 0.95), serp_signals)

    # === 2. 列表/目录页检测 ===
    listing_signals, listing_score = _detect_listing(content, url, title)
    if listing_score >= 5:
        return PageClassification("listing", min(listing_score / 8, 0.95), listing_signals)

    # === 3. 登录/认证页检测 ===
    login_signals, login_score = _detect_login(content, url, title)
    if login_score >= 5:
        return PageClassification("login", min(login_score / 8, 0.95), login_signals)

    # === 4. 404/错误页检测 ===
    error_signals, error_score = _detect_error(content, url, title)
    if error_score >= 5:
        return PageClassification("error", min(error_score / 8, 0.95), error_signals)

    # === 5. 付费墙预览检测 ===
    paywall_signals, paywall_score = _detect_paywall(content, url, title)
    if paywall_score >= 5:
        return PageClassification("paywall", min(paywall_score / 8, 0.95), paywall_signals)

    # === 6. 论坛列表页检测 ===
    forum_signals, forum_score = _detect_forum(content, url, title)
    if forum_score >= 5:
        return PageClassification("forum", min(forum_score / 8, 0.95), forum_signals)

    return PageClassification("unknown", 0, [])


def _detect_serp(content: str, url: str, title: str) -> tuple[list, int]:
    """检测搜索引擎结果页"""
    signals = []
    score = 0
    lower_url = url.lower()
    parsed = urlparse(lower_url)

    # 搜索引擎根路径检测（baidu.com/ 无查询参数 = 搜索首页）
    domain = parsed.netloc
    path = parsed.path.rstrip('/')
    if (domain in _SERP_ROOT_DOMAINS
            and path == ''
            and not parsed.query):
        signals.append(f"serp_root:{domain}")
        score += 5  # 直接达标

    # 搜索引擎首页标题检测
    title_lower = title.lower()
    for kw in _SERP_HOMEPAGE_TITLES:
        if kw.lower() in title_lower:
            signals.append(f"serp_homepage_title:{kw}")
            score += 3
            break

    # URL 路径匹配
    for pat in _SERP_URL_PATTERNS:
        if pat in lower_url:
            signals.append(f"serp_url:{pat}")
            score += 3
            break

    # UI 元素匹配
    for pat in _SERP_UI_PATTERNS:
        if re.search(pat, content):
            signals.append(f"serp_ui:{pat}")
            score += 2
            break

    # 独立 URL 行密度：SERP 页面通常每行一个链接
    link_lines = 0
    total_lines = 0
    for line in content.split('\n'):
        line = line.strip()
        if not line:
            continue
        total_lines += 1
        links = re.findall(r'\[([^\]]+)\]\(https?://[^\)]+\)', line)
        if links and len(line) < 200:
            link_lines += 1

    if total_lines > 0 and link_lines >= 4:
        ratio = link_lines / total_lines
        if ratio > 0.3:
            signals.append(f"serp_link_density:{ratio:.2f}")
            score += 3

    # 标题匹配
    title_lower = title.lower()
    if any(kw in title_lower for kw in ('search', '搜索', 'results', '结果')):
        signals.append("serp_title")
        score += 1

    return signals, score


def _detect_listing(content: str, url: str, title: str) -> tuple[list, int]:
    """检测列表/目录/归档页面"""
    signals = []
    score = 0
    lower_url = url.lower()

    # URL 路径匹配
    for pat in _LISTING_URL_PATTERNS:
        if pat in lower_url:
            signals.append(f"listing_url:{pat}")
            score += 3
            break

    # 日期列表项 ≥ 5 个
    date_items = re.findall(r'\d{4}[-/]\d{2}[-/]\d{2}', content)
    if len(date_items) >= 5:
        signals.append(f"listing_dates:{len(date_items)}")
        score += 2

    # "阅读全文" 链接
    read_more = len(re.findall(r'阅读全文|Read more|继续阅读|查看全文', content))
    if read_more >= 3:
        signals.append(f"listing_readmore:{read_more}")
        score += 2

    # 标题/段落比过高（>5 个标题但 <2 个正文段落）
    headings = len(re.findall(r'^#{1,3}\s', content, re.MULTILINE))
    paragraphs = len(re.findall(r'^[A-Za-z一-鿿].{80,}', content, re.MULTILINE))
    if headings > 5 and paragraphs < 2:
        signals.append(f"listing_hp_ratio:{headings}/{paragraphs}")
        score += 2

    # 分页文本
    pagination = len(re.findall(r'第\s*\d+\s*页|page\s*\d+\s*of\s*\d+|共\s*\d+\s*页', content, re.IGNORECASE))
    if pagination >= 1:
        signals.append(f"listing_pagination:{pagination}")
        score += 2

    # 链接密度
    lines = [l for l in content.split('\n') if l.strip()]
    if lines:
        link_lines = sum(1 for l in lines if '[' in l and '](' in l)
        if link_lines / len(lines) > 0.4 and link_lines >= 5:
            signals.append(f"listing_link_density:{link_lines}/{len(lines)}")
            score += 2

    return signals, score


def _detect_forum(content: str, url: str, title: str) -> tuple[list, int]:
    """检测论坛列表页面"""
    signals = []
    score = 0
    lower_url = url.lower()

    # URL 路径匹配
    for pat in _FORUM_URL_PATTERNS:
        if pat in lower_url:
            signals.append(f"forum_url:{pat}")
            score += 3
            break

    # UI 元素匹配
    for pat in _FORUM_UI_PATTERNS:
        if re.search(pat, content):
            signals.append(f"forum_ui:{pat}")
            score += 2
            break

    return signals, score


def _detect_login(content: str, url: str, title: str) -> tuple[list, int]:
    """检测登录/认证页面"""
    signals = []
    score = 0
    lower_url = url.lower()

    # URL 路径段匹配（避免 /login-security-guide 等误匹配）
    parsed = urlparse(lower_url)
    path_segments = [s for s in parsed.path.split('/') if s]
    for pat in _LOGIN_URL_PATTERNS:
        if any(seg == pat.lstrip('/') for seg in path_segments):
            signals.append(f"login_url:{pat}")
            score += 3
            break

    # 内容特征匹配
    for pat in _LOGIN_CONTENT_PATTERNS:
        if re.search(pat, content, re.IGNORECASE):
            signals.append(f"login_content:{pat}")
            score += 2
            break

    return signals, score


def _detect_error(content: str, url: str, title: str) -> tuple[list, int]:
    """检测 404/错误页面"""
    signals = []
    score = 0
    title_lower = (title or "").lower()

    # 标题特征
    for pat in _ERROR_TITLE_PATTERNS:
        if pat in title_lower:
            signals.append(f"error_title:{pat}")
            score += 3
            break

    # 内容特征：页面非常短 + 错误关键词
    content_stripped = content.strip()
    if len(content_stripped) < 500:
        for pat in _ERROR_TITLE_PATTERNS:
            if pat in content_stripped.lower():
                signals.append(f"error_content:{pat}")
                score += 2
                break

    return signals, score


def _detect_paywall(content: str, url: str, title: str) -> tuple[list, int]:
    """检测付费墙预览页面（多信号累加）"""
    signals = []
    score = 0
    lower_url = url.lower()

    # URL 路径匹配
    for pat in _PAYWALL_URL_PATTERNS:
        if pat in lower_url:
            signals.append(f"paywall_url:{pat}")
            score += 3
            break

    # 内容特征匹配（累加多个信号，不 break）
    for pat in _PAYWALL_CONTENT_PATTERNS:
        if re.search(pat, content):
            signals.append(f"paywall_content:{pat}")
            score += 2

    # 截断：最多计 3 个内容信号，避免计分过高
    return signals, score
