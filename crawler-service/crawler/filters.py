"""
共享过滤规则模块

统一维护域名排除列表和负向关键词，供 search.py 和 quality.py 共同引用。
单一数据源消除维护两份列表的漂移风险。
"""

from urllib.parse import urlparse


# ============ 域名黑名单（精确匹配）============

EXCLUDED_DOMAINS = {
    # 搜索引擎
    'duckduckgo.com',
    # 社交媒体
    'youtube.com', 'facebook.com', 'twitter.com', 'x.com',
    'instagram.com', 'linkedin.com', 'pinterest.com',
    'weibo.com', 'xiaohongshu.com', 'tumblr.com',
    # 视频网站
    'bilibili.com', 'youku.com', 'iqiyi.com',
    'tv.sohu.com', 'le.com', 'pptv.com',
    # 电商平台
    'taobao.com', 'tmall.com', 'jd.com',
    'aliexpress.com', '1688.com', 'pdd.com', 'suning.com',
    # 内容农场 / 低质量平台
    'toutiao.com',
    'mp.weixin.qq.com',     # 公众号质量参差且反爬强
    'baike.sogou.com',      # 搜狗百科
    'ima.qq.com',           # 腾讯ima AI知识库
    'baijiahao.baidu.com',  # 百家号
    'haokan.baidu.com',     # 好看视频
    'mbd.baidu.com',        # 百度信息流/媒体内容
    'sohu.com',             # 搜狐号
    '163.com',              # 网易号
    'ifeng.com',            # 凤凰号
    'sina.com.cn',          # 新浪看点
    # 占星/运势
    'astrologyanswers.com', 'astrology.com', 'horoscope.com',
    'chinesefortunecalendar.com', 'yourchineseastrology.com',
    # 健康/医疗
    'webmd.com', 'mayoclinic.org', 'healthline.com',
    # 婚恋/情感
    'match.com', 'eharmony.com', 'tinder.com',
}

# ============ 域名后缀黑名单 ============

EXCLUDED_DOMAIN_SUFFIXES = [
    '.baijiahao.baidu.com',
    '.haokan.baidu.com',
    '.sina.com.cn',
    '.k.sina.com.cn',
    '.astro.com',       # 占星站点（但保留 astronomy 等科学域名）
    '.horoscope.com',
    '.zodiac.com',
    '.tarot.com',
]

# ============ 域名限定路径排除 ============

DOMAIN_PATH_EXCLUSIONS = [
    ('sohu.com', '/a/'),        # 搜狐号
    ('163.com', '/dy/'),        # 网易号
    ('ifeng.com', '/c/'),       # 凤凰号
    ('baidu.com', '/p/'),       # 百度贴吧
    ('baidu.com', '/thread-'),  # 百度贴吧
]

# ============ 通用低价值路径（任何域名）============

GENERIC_PATH_PATTERNS = [
    '/tag/', '/tags/',
    '/category/', '/categories/',
    '/search?', '/query?', '/s?', '/find?',
    '/login', '/register', '/signup', '/auth/',
    '/cart', '/checkout', '/order', '/buy',
    '/rss', '/feed', '/atom',
    '/print', '/share', '/email',
    '/amp/', '/promo', '/affiliate', '/ref=', '/utm_',
]

# ============ 文件扩展名排除 ============

EXCLUDED_EXTENSIONS = [
    '.pdf', '.doc', '.docx', '.ppt', '.pptx',
    '.xls', '.xlsx', '.zip', '.rar', '.tar.gz',
]

# ============ 负向关键词（标题/摘要过滤）============

EXCLUDED_KEYWORDS = [
    'horoscope', 'zodiac', 'astrology', 'tarot',
    'daily horoscope', 'weekly horoscope', 'birth chart',
    'love compatibility',
]


def is_excluded_domain(url: str) -> bool:
    """
    检查 URL 是否属于排除列表（广告、低质量站点、非文本内容等）

    采用域名级精确匹配 + 路径模式匹配，避免简单子串误杀。
    """
    parsed = urlparse(url.lower())
    domain = parsed.netloc
    path = parsed.path
    if parsed.query:
        path = path + '?' + parsed.query

    # 去掉 www 前缀用于域名匹配
    domain_no_www = domain[4:] if domain.startswith('www.') else domain

    # 精确域名匹配
    if domain_no_www in EXCLUDED_DOMAINS:
        return True

    # 域名后缀匹配
    dotted_domain = '.' + domain_no_www
    for suffix in EXCLUDED_DOMAIN_SUFFIXES:
        if dotted_domain.endswith(suffix):
            return True

    # 搜索引擎路径排除
    if 'google.com' in domain and '/search' in path:
        return True
    if 'bing.com' in domain and '/search' in path:
        return True
    if 'baidu.com' in domain and ('/s?' in path or '/search' in path):
        return True

    # Amazon/eBay 按域名前缀匹配
    if domain_no_www.startswith('amazon.') or domain_no_www.startswith('ebay.'):
        return True

    # 知乎：完全排除（反爬极强）
    if 'zhihu.com' in domain:
        return True

    # 腾讯/优酷视频域名
    if domain_no_www in ('v.qq.com', 'v.youku.com'):
        return True

    # 域名限定的低价值路径
    for dom_pat, path_pat in DOMAIN_PATH_EXCLUSIONS:
        if dom_pat in domain and path_pat in path:
            return True

    # 通用低价值路径
    for pattern in GENERIC_PATH_PATTERNS:
        if pattern in path:
            return True

    # 文件扩展名排除
    for ext in EXCLUDED_EXTENSIONS:
        if path.endswith(ext):
            return True

    return False


def has_excluded_keywords(text: str) -> bool:
    """检查文本是否包含负向关键词（星座/运势等非技术内容）"""
    text_lower = text.lower()
    return any(kw in text_lower for kw in EXCLUDED_KEYWORDS)
