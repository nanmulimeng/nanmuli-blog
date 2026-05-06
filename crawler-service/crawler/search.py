"""
关键词搜索爬取模块

基于搜索引擎的关键词搜索，爬取搜索结果页面的内容
"""

import asyncio
import random
import re
import time
import logging
from typing import List, Optional
from urllib.parse import quote_plus, urlparse, parse_qs

import httpx
from bs4 import BeautifulSoup

from crawl4ai import AsyncWebCrawler

from .config import get_browser_config, RunParams
from .single import CrawlResult, crawl_single_page
from .quality import evaluate_content
from .dedup import dedup_results

logger = logging.getLogger(__name__)

# 搜索引擎配置
SEARCH_ENGINES = {
    'sogou': {
        'result_selector': '.vrwrap',
        'title_selector': '.vrTitle a, h3 a',
        'link_selector': '.vrTitle a, h3 a',
        'snippet_selector': '.str-text, .star-w',
    },
    'bing': {
        'result_selector': 'li.b_algo',
        'title_selector': 'h2 a',
        'link_selector': 'h2 a',
        'snippet_selector': 'p',
    },
    'duckduckgo': {
        'url': 'https://html.duckduckgo.com/html/?q={query}&kl=us-en',
        'result_selector': '.result',
        'title_selector': '.result__a',
        'link_selector': '.result__a',
        'snippet_selector': '.result__snippet',
    },
    'google': {
        'result_selector': 'div.g',
        'title_selector': 'h3 a',
        'link_selector': 'h3 a',
        'snippet_selector': '.VwiC3b, .s3v94d',
    },
}

# 引擎优先级（主引擎失败时按此顺序自动轮换）
ENGINE_PRIORITY = ['sogou', 'bing', 'duckduckgo', 'google']


async def crawl_by_keyword(
    keyword: str,
    engine: str = 'sogou',
    max_results: int = 10,
    time_range: str = 'week',
    config: Optional[object] = None
) -> List[CrawlResult]:
    """
    通过搜索引擎查找关键词，爬取前 N 个结果。
    支持多引擎自动轮换：当主引擎返回 0 结果时，自动按优先级尝试其他引擎。

    Args:
        keyword: 搜索关键词
        engine: 首选搜索引擎
        max_results: 最大结果数
        time_range: 时间范围过滤 ('day'|'week'|'month'|'year'|'all')
        config: 爬取配置

    Returns:
        CrawlResult 列表
    """
    # 参数校验
    valid_time_ranges = {'day', 'week', 'month', 'year', 'all'}
    if time_range not in valid_time_ranges:
        raise ValueError(f"Invalid time_range '{time_range}'. Must be one of: {valid_time_ranges}")

    start_time = time.time()

    logger.info(f"[Search] Keyword: '{keyword}', engine: {engine}, max_results={max_results}, time_range={time_range}")

    # 构建引擎尝试顺序：首选引擎优先，其余按 ENGINE_PRIORITY 排序
    engines_to_try = [engine]
    for e in ENGINE_PRIORITY:
        if e != engine and e not in engines_to_try:
            engines_to_try.append(e)

    url_set: set = set()
    all_search_urls: list = []
    url_source_map: dict = {}  # url -> 来源引擎
    tried_engines = []

    # 阶段1：尝试各搜索引擎获取 URL 列表
    for idx, current_engine in enumerate(engines_to_try):
        try:
            logger.info(f"[Search] Trying engine '{current_engine}' for keyword: '{keyword}'")
            search_urls = await _get_search_results(
                keyword=keyword,
                engine=current_engine,
                max_results=max_results,
                time_range=time_range
            )
            tried_engines.append(current_engine)

            if search_urls:
                # 合并去重（跨引擎），set保证O(1)查找
                new_urls = [u for u in search_urls if u not in url_set]
                for u in new_urls:
                    url_set.add(u)
                    url_source_map[u] = current_engine
                all_search_urls.extend(new_urls)
                logger.info(
                    f"[Search] Engine '{current_engine}' returned {len(search_urls)} URLs "
                    f"({len(new_urls)} new, total unique={len(all_search_urls)})"
                )

                # 如果已经拿到足够结果，提前停止
                if len(all_search_urls) >= max_results:
                    break
            else:
                logger.warning(f"[Search] Engine '{current_engine}' returned 0 results for '{keyword}'")

        except Exception as e:
            logger.warning(f"[Search] Engine '{current_engine}' failed for '{keyword}': {e}")
            tried_engines.append(current_engine)

        # 引擎间随机间隔，避免连续请求触发频率限制（验证码）
        if idx < len(engines_to_try) - 1:
            await asyncio.sleep(random.uniform(2.0, 5.0))

    if not all_search_urls:
        logger.error(f"[Search] All engines failed for keyword: '{keyword}'. Tried: {tried_engines}")
        return [CrawlResult(
            success=False,
            url="",
            error_message=f"No search results found for keyword: '{keyword}' (tried engines: {', '.join(tried_engines)})"
        )]

    # 截断到 max_results
    all_search_urls = all_search_urls[:max_results]
    logger.info(f"[Search] Total {len(all_search_urls)} unique URLs from {len(tried_engines)} engine(s) for '{keyword}'")

    # 阶段2：用共享浏览器实例并发爬取
    params = RunParams(config)
    browser_config = get_browser_config(text_mode=params.text_mode, light_mode=params.light_mode)

    results = await _crawl_urls_with_shared_browser(
        urls=all_search_urls, keyword=keyword,
        url_source_map=url_source_map,
        config=config, browser_config=browser_config
    )

    # 阶段3：内容去重（P3: 重复性要低）
    try:
        deduped = dedup_results(results)
        removed = len(results) - len(deduped)
        if removed > 0:
            logger.info(f"[Search] Dedup removed {removed} duplicate results")
        results = deduped
    except Exception as de:
        # 去重失败隔离：不打断主流程
        logger.warning(f"[Search] Dedup failed: {de}")

    total_time = int((time.time() - start_time) * 1000)
    success_count = sum(1 for r in results if r.success)
    logger.info(f"[Search] Completed: {success_count}/{len(results)} pages crawled, keyword='{keyword}', time={total_time}ms")

    return results


async def _crawl_urls_with_shared_browser(
    urls: List[str],
    keyword: str,
    url_source_map: dict,
    config: Optional[object],
    browser_config,
    is_fallback: bool = False
) -> List[CrawlResult]:
    """共享浏览器实例 + 并发信号量爬取多个 URL"""
    sem = asyncio.Semaphore(3)

    async def _crawl_one(rank: int, url: str) -> CrawlResult:
        async with sem:
            try:
                result = await crawl_single_page(url=url, config=config, crawler=crawler)

                # 内容质量后处理：字数过少的视为低质量
                if result.success and result.word_count < 50:
                    logger.warning(
                        f"[Search] Content too short ({result.word_count} words), "
                        f"marking as low quality: {url}"
                    )
                    result.success = False
                    result.error_message = f"Content too short ({result.word_count} words, min 50)"

                # 多维度质量评估（P1: 宁可少而不可错）
                if result.success and result.markdown:
                    try:
                        eval_result = evaluate_content(
                            url=result.url,
                            title=result.title or '',
                            content=result.markdown
                        )
                        result.metadata['quality_eval'] = eval_result
                        source_level = eval_result.get('source', {}).get('level', '')
                        verdict = eval_result.get('verdict', 'pass')

                        # spam/低质量来源 + 质量差 → 直接拒绝
                        if verdict == 'reject':
                            reason = eval_result.get('quality', {}).get('recommendation', 'low quality')
                            logger.warning(
                                f"[Search] Quality reject (source={source_level}, verdict={verdict}): {url}"
                            )
                            result.success = False
                            result.error_message = f"Quality rejected: {reason}"
                        elif verdict == 'review':
                            # 标记为需 review，但不阻止，后续可由调用方决定是否保留
                            logger.info(f"[Search] Quality review flagged: {url}")
                    except Exception as qe:
                        # 质量评估失败隔离：不打断主流程
                        logger.debug(f"[Search] Quality eval failed for {url}: {qe}")

                result.search_rank = rank
                result.metadata['search_keyword'] = keyword
                # 精确记录该URL来自哪个搜索引擎
                result.metadata['search_engine'] = url_source_map.get(url, 'unknown')
                if is_fallback:
                    result.metadata['fallback'] = True
                return result
            except Exception as e:
                logger.warning(f"[Search] Failed to crawl {url}: {e}")
                meta = {
                    'search_rank': rank,
                    'search_keyword': keyword,
                    'search_engine': url_source_map.get(url, 'unknown')
                }
                if is_fallback:
                    meta['fallback'] = True
                return CrawlResult(
                    success=False,
                    url=url,
                    error_message=str(e),
                    search_rank=rank,
                    metadata=meta
                )

    async with AsyncWebCrawler(config=browser_config) as crawler:
        tasks = [_crawl_one(rank, url) for rank, url in enumerate(urls, 1)]
        results = await asyncio.gather(*tasks)
        return list(results)


# 搜索引擎时间过滤参数映射
TIME_FILTER_PARAMS = {
    'bing': {
        'day': '&filters=ex1:"ez5_4251_4252"',
        'week': '&filters=ex1:"ez5_4251_4253"',
        'month': '&filters=ex1:"ez5_4251_4254"',
        'year': '&filters=ex1:"ez5_4251_4255"',
        'all': '',
    },
    'google': {
        'day': '&tbs=qdr:d',
        'week': '&tbs=qdr:w',
        'month': '&tbs=qdr:m',
        'year': '&tbs=qdr:y',
        'all': '',
    },
    'sogou': {
        'day': '&s_from=forecast&forecast=day',
        'week': '&s_from=forecast&forecast=week',
        'month': '&s_from=forecast&forecast=month',
        'year': '&s_from=forecast&forecast=year',
        'all': '',
    },
    'duckduckgo': {
        'day': '&df=d',
        'week': '&df=w',
        'month': '&df=m',
        'year': '&df=y',
        'all': '',
    },
}


async def _get_search_results(
    keyword: str,
    engine: str,
    max_results: int,
    time_range: str = 'week'
) -> List[str]:
    """
    获取搜索结果页面的 URL 列表（含预筛选与去重）
    Bing支持分页：第一页first=1，第二页first=11，以此类推

    Args:
        keyword: 搜索关键词
        engine: 搜索引擎
        max_results: 最大结果数
        time_range: 时间范围过滤 ('day'|'week'|'month'|'year'|'all')

    Returns:
        经过过滤的 URL 列表
    """
    if engine not in SEARCH_ENGINES:
        raise ValueError(f"Unsupported search engine: {engine}. Supported: {list(SEARCH_ENGINES.keys())}")

    config = SEARCH_ENGINES[engine]
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
    }

    # 搜狗反爬较强，需要额外伪装
    if engine == 'sogou':
        headers.update({
            'Referer': 'https://www.sogou.com/',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Upgrade-Insecure-Requests': '1',
        })

    urls = []
    seen_domains = set()
    total_raw = 0
    page = 0

    # 获取时间过滤参数
    time_filter = TIME_FILTER_PARAMS.get(engine, {}).get(time_range, '')
    if time_range != 'all':
        logger.info(f"[Search] Applying time filter '{time_range}' for engine '{engine}'")

    # 各引擎分页策略
    while len(urls) < max_results and page < 3:  # 最多翻3页
        if engine == 'bing':
            first = page * 10 + 1
            search_url = (
                f"https://www.bing.com/search?q={quote_plus(keyword)}"
                f"&count=50&setmkt=en-US&setlang=en&first={first}"
                f"{time_filter}"
            )
        elif engine == 'sogou':
            search_url = (
                f"https://www.sogou.com/web?query={quote_plus(keyword)}"
                f"&page={page + 1}"
                f"{time_filter}"
            )
        elif engine == 'google':
            start = page * 10
            search_url = (
                f"https://www.google.com/search?q={quote_plus(keyword)}"
                f"&num=10&start={start}&hl=en"
                f"{time_filter}"
            )
        else:
            # duckduckgo 等使用配置中的 URL 模板
            search_url = config['url'].format(query=quote_plus(keyword))
            # DDG 分页通过额外参数控制
            if page > 0:
                search_url += f"&s={page * 30}"  # DDG 每页约30条
            if time_filter:
                # 避免重复拼接?/&
                sep = '&' if '?' in search_url else '?'
                if not search_url.endswith(sep) and not search_url.endswith('&'):
                    search_url += sep
                # time_filter 已包含前缀 & 或 ?
                search_url += time_filter.lstrip('&?')

        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
                response = await client.get(search_url, headers=headers)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'lxml')
                result_items = soup.select(config['result_selector'])

                if not result_items:
                    # 检查是否被反爬/验证码拦截（页面有内容但无搜索结果）
                    page_text = soup.get_text() if soup else ''
                    if _is_anti_bot_page(page_text, response.text if response else ''):
                        raise Exception(f"Engine '{engine}' blocked by anti-bot/captcha")
                    break  # 真正没有更多结果了

                total_raw += len(result_items)
                page_new = 0

                for item in result_items:
                    if len(urls) >= max_results:
                        break

                    link_elem = item.select_one(config['link_selector'])
                    if not link_elem:
                        continue

                    href = link_elem.get('href', '')
                    title = link_elem.get_text(strip=True) or ''

                    # 提取摘要用于预筛选
                    snippet_elem = item.select_one(config['snippet_selector'])
                    snippet = snippet_elem.get_text(strip=True) if snippet_elem else ''

                    # 清理搜索引擎跳转链接
                    if engine == 'bing' and '/url?u=' in href:
                        parsed = parse_qs(urlparse(href).query)
                        if 'u' in parsed:
                            href = parsed['u'][0]
                    elif engine == 'google' and href.startswith('/url?'):
                        parsed = parse_qs(urlparse(href).query)
                        if 'q' in parsed:
                            href = parsed['q'][0]
                    elif engine == 'sogou' and 'weixin.sogou.com' in href:
                        # 跳过搜狗微信搜索结果（已在排除列表中，此处做二次防护）
                        continue

                    # 验证 URL
                    if not href or not href.startswith(('http://', 'https://')):
                        continue

                    # 排除广告/无关域名
                    if _is_excluded_domain(href):
                        continue

                    # 基于标题/摘要的相关度预筛选
                    if not _is_relevant_to_keyword(keyword, title, snippet):
                        continue

                    # 同域名去重：每个域名最多保留 1 个结果
                    domain = urlparse(href).netloc
                    if domain in seen_domains:
                        continue
                    seen_domains.add(domain)

                    urls.append(href)
                    page_new += 1

                logger.debug(f"[Search] Page {page + 1}: {page_new} new URLs from {len(result_items)} raw results")

                if len(result_items) < 5:
                    break  # 结果太少，没有更多页了

                page += 1
                # 翻页间隔随机化，降低被反爬检测的概率
                if page < 3:
                    await asyncio.sleep(random.uniform(0.8, 2.0))

        except Exception as e:
            logger.warning(f"[Search] Page {page + 1} failed for '{keyword}': {e}")
            break

    logger.info(f"[Search] Filtered {len(urls)} URLs from {total_raw} raw results (pages={page}) for keyword='{keyword}'")
    return urls


def _is_excluded_domain(url: str) -> bool:
    """检查 URL 是否属于排除列表（广告、低质量站点、非文本内容等）

    采用域名级精确匹配 + 路径模式匹配，避免简单子串误杀（如 astro. 误杀 astronomy.com）。
    """
    parsed = urlparse(url.lower())
    domain = parsed.netloc
    path = parsed.path

    # 去掉 www 前缀用于域名匹配
    domain_no_www = domain[4:] if domain.startswith('www.') else domain

    # === 域名黑名单（精确匹配）===
    excluded_domains_exact = {
        # 搜索引擎
        'duckduckgo.com',
        # 社交媒体
        'youtube.com', 'facebook.com', 'twitter.com', 'x.com',
        'instagram.com', 'linkedin.com', 'pinterest.com',
        'weibo.com', 'xiaohongshu.com', 'reddit.com', 'tumblr.com',
        # 视频网站
        'bilibili.com', 'youku.com', 'iqiyi.com',
        'tv.sohu.com', 'le.com', 'pptv.com',
        # 电商平台
        'taobao.com', 'tmall.com', 'jd.com',
        'aliexpress.com', '1688.com', 'pdd.com', 'suning.com',
        # 内容农场 / 低质量平台
        'toutiao.com',
        'mp.weixin.qq.com',  # 公众号质量参差且反爬强
        'baike.sogou.com',     # 搜狗百科，内容质量低且多为非技术内容
        'ima.qq.com',          # 腾讯ima AI知识库，二手聚合内容
        # 占星/运势
        'astrologyanswers.com', 'astrology.com', 'horoscope.com',
        'chinesefortunecalendar.com', 'yourchineseastrology.com',
        # 健康/医疗
        'webmd.com', 'mayoclinic.org', 'healthline.com',
        # 婚恋/情感
        'match.com', 'eharmony.com', 'tinder.com',
    }
    if domain_no_www in excluded_domains_exact:
        return True

    # === 域名后缀黑名单（如 *.baijiahao.baidu.com）===
    excluded_domain_suffixes = [
        '.baijiahao.baidu.com',
        '.haokan.baidu.com',
        '.sina.com.cn',
        '.k.sina.com.cn',
        '.astro.com',       # 占星站点（但保留 astronomy 等科学域名）
        '.horoscope.com',
        '.zodiac.com',
        '.tarot.com',
    ]
    # 在前面加 . 确保后缀匹配覆盖根域名和子域名
    # 例：www.sina.com.cn → sina.com.cn → .sina.com.cn → endsWith(.sina.com.cn) = true
    dotted_domain = '.' + domain_no_www
    for suffix in excluded_domain_suffixes:
        if dotted_domain.endswith(suffix):
            return True

    # === 搜索引擎路径排除 ===
    if 'google.com' in domain and '/search' in path:
        return True
    if 'bing.com' in domain and '/search' in path:
        return True
    if 'baidu.com' in domain and ('/s?' in path or '/search' in path):
        return True

    # === Amazon/eBay 按域名前缀匹配 ===
    if domain_no_www.startswith('amazon.') or domain_no_www.startswith('ebay.'):
        return True

    # === 知乎：仅排除搜索页和短内容，保留问题页和专栏
    # 注：在中国大陆IP下，Bing返回中文结果中知乎占比极高，完全排除会导致大量关键词0结果
    if 'zhihu.com' in domain:
        if '/pin' in path or '/search' in path:
            return True

    # === 腾讯/优酷视频域名 ===
    if domain_no_www in ('v.qq.com', 'v.youku.com'):
        return True

    # === 域名限定的低价值路径（避免全局误杀）===
    domain_path_exclusions = [
        ('sohu.com', '/a/'),        # 搜狐号
        ('163.com', '/dy/'),        # 网易号
        ('ifeng.com', '/c/'),       # 凤凰号
        ('baidu.com', '/p/'),       # 百度贴吧
        ('baidu.com', '/thread-'),  # 百度贴吧
    ]
    for dom_pat, path_pat in domain_path_exclusions:
        if dom_pat in domain and path_pat in path:
            return True

    # === 通用低价值路径（任何域名）===
    generic_path_patterns = [
        '/tag/', '/tags/',
        '/category/', '/categories/',
        '/search?', '/query?', '/s?', '/find?',
        '/login', '/register', '/signup', '/auth/',
        '/cart', '/checkout', '/order', '/buy',
        '/rss', '/feed', '/atom',
        '/print', '/share', '/email',
        '/amp/', '/promo', '/affiliate', '/ref=', '/utm_',
    ]
    for pattern in generic_path_patterns:
        if pattern in path:
            return True

    # === 文件扩展名排除 ===
    excluded_extensions = [
        '.pdf', '.doc', '.docx', '.ppt', '.pptx',
        '.xls', '.xlsx', '.zip', '.rar', '.tar.gz',
    ]
    for ext in excluded_extensions:
        if path.endswith(ext):
            return True

    return False


# 负向关键词：标题或摘要中出现这些词，视为低质量/不相关结果（技术搜索场景）
_EXCLUDED_KEYWORDS = [
    'horoscope', 'zodiac', 'astrology', 'tarot', '星座', '运势',
    'daily horoscope', 'weekly horoscope', 'birth chart',
    'love compatibility', '星座配对', '今日运势',
]


def _is_whole_word_match(text: str, keyword: str) -> bool:
    """检查关键词在文本中是否作为整词出现（避免子串误匹配）"""
    if not keyword:
        return False
    # 多词关键词或含中文：直接子串匹配
    if len(keyword.split()) > 1 or any('一' <= c <= '鿿' for c in keyword):
        return keyword in text
    # 单英文单词：用词边界\b匹配，避免 "Java" 匹配 "JavaScript"
    return bool(re.search(r'\b' + re.escape(keyword) + r'\b', text))


def _is_relevant_to_keyword(keyword: str, title: str, snippet: str) -> bool:
    """
    基于标题和摘要判断搜索结果是否与关键词相关。

    策略：
    1. 标题整词匹配权重最高 → 直接通过
    2. 摘要整词匹配 → 直接通过
    3. 标题中出现拆分词 → 直接通过（标题是相关性最强信号）
    4. 摘要中需匹配多数拆分词 → 才通过（防止泛化匹配）
    5. 标题为空或"No Title"视为不相关
    6. 标题/摘要包含明显非技术内容（星座/运势等）视为不相关
    """
    if not title or title.strip().lower() in ('no title', '无标题', ''):
        return False

    title_lower = title.lower()
    snippet_lower = snippet.lower()

    # 负向过滤：星座/运势等非技术内容直接排除
    combined_text = title_lower + ' ' + snippet_lower
    for excluded in _EXCLUDED_KEYWORDS:
        if excluded in combined_text:
            return False

    keyword_lower = keyword.lower().strip()

    # 整词匹配优先（标题权重最高）
    if _is_whole_word_match(title_lower, keyword_lower):
        return True
    if _is_whole_word_match(snippet_lower, keyword_lower):
        return True

    # 拆分关键词（空格分隔）后分级检查
    keyword_parts = [p for p in keyword_lower.split() if len(p) >= 2]
    if not keyword_parts:
        # 关键词太短（如 "Go"），直接放行，依赖后续域名/内容过滤
        return True

    # 标题中出现任意拆分词 → 强信号，直接通过
    title_matches = sum(1 for p in keyword_parts if _is_whole_word_match(title_lower, p))
    if title_matches >= 1:
        return True

    # 摘要中需匹配多数拆分词（避免单个常见词如 "the" "and" 导致误过）
    snippet_matches = sum(1 for p in keyword_parts if _is_whole_word_match(snippet_lower, p))
    min_required = max(1, int(len(keyword_parts) * 0.5 + 0.5))  # 向上取整的50%
    return snippet_matches >= min_required


def _is_anti_bot_page(page_text: str, raw_html: str = '') -> bool:
    """检测页面是否为反爬虫/验证码拦截页"""
    text_lower = page_text.lower()
    html_lower = raw_html.lower()
    indicators = [
        '验证码', 'captcha', 'security check', 'verify you are human',
        'unusual traffic', 'automated requests', 'ip address has been blocked',
        'please verify', 'i\'m not a robot', 'recaptcha',
    ]
    return any(ind in text_lower or ind in html_lower for ind in indicators)


# 降级搜索策略（如果主搜索引擎失败）
async def _fallback_search(
    keyword: str,
    max_results: int
) -> List[str]:
    """
    搜索引擎失败时的降级策略

    尝试使用 DuckDuckGo（通常限制较少）
    """
    logger.info(f"[Search] Attempting fallback search for: '{keyword}'")
    try:
        return await _get_search_results(keyword, 'duckduckgo', max_results)
    except Exception as e:
        logger.error(f"[Search] Fallback also failed: {e}")
        return []
