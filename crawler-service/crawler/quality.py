"""
内容质量评估模块

提供来源可信度评分 + 内容质量评分 + 低质量过滤能力

决策权重（领主将军阁下明确）：
  P1: 内容正确，质量要高 > P2: 信息不滞后 > P3: 重复性低
  宁可少而不可错
"""

import re
import datetime
from typing import Dict, List, Optional
from urllib.parse import urlparse

from .utils import count_words
from .filters import is_excluded_domain
from config import settings



# ============ 来源可信度数据库 ============

class SourceAuthority:
    """来源可信度评分体系

    优先从 Java API 查询数据库中的评分（缓存 1 小时），兜底使用硬编码列表。
    """

    # API 缓存：domain -> (score_dict, timestamp)
    _api_cache: dict[str, tuple[dict, float]] = {}
    _cache_ttl: float = 3600.0  # 1 小时

    # 官方/权威来源 (90-100分)
    OFFICIAL_DOMAINS = {
        'docs.spring.io', 'spring.io',
        'docs.python.org', 'python.org',
        'developer.mozilla.org', 'mdn.dev',
        'kubernetes.io', 'istio.io', 'envoyproxy.io',
        'react.dev', 'vuejs.org', 'angular.io',
        'docs.github.com', 'github.blog',
        'aws.amazon.com', 'cloud.google.com', 'azure.microsoft.com',
        'docs.oracle.com', 'dev.mysql.com',
        'postgresql.org', 'redis.io', 'mongodb.com',
        'prometheus.io', 'grafana.com',
        'openai.com', 'anthropic.com', 'platform.openai.com',
        'huggingface.co', 'paperswithcode.com',
        'arxiv.org', 'dl.acm.org', 'ieeexplore.ieee.org',
        'academic.microsoft.com', 'scholar.google.com',
    }

    # 高质量技术社区/媒体 (70-89分)
    HIGH_QUALITY_COMMUNITIES = {
        'medium.com', 'dev.to', 'hashnode.dev',
        'stackoverflow.com', 'stackexchange.com',
        'infoq.com', 'infoq.cn',
        'juejin.cn', 'segmentfault.com',
        'csdn.net', 'blog.csdn.net',
        'zhihu.com',  # 知乎专栏/问题页
        'v2ex.com',
        'lobste.rs',
        'news.ycombinator.com',
        'reddit.com',  # r/programming, r/MachineLearning等
        'producthunt.com',
        'hackernewsletter.com',
        'ruanyifeng.com',
        'draveness.me',
        'cnblogs.com',
    }

    # 技术博客/个人站点 (50-69分，需内容质量辅助判断)
    TECH_BLOGS = {
        'github.io', 'github.com',  # GitHub Pages / 项目README
        'gitlab.io',
        'netlify.app', 'vercel.app',
    }

    @classmethod
    def score(cls, url: str) -> Dict:
        """
        评估来源可信度（优先 Java API，兜底硬编码）
        """
        domain = cls._extract_domain(url)

        # 0. 优先从 Java API 查询（带缓存）
        api_result = cls._query_from_api(domain)
        if api_result:
            return api_result

        # 1. 硬编码兜底
        domain = cls._extract_domain(url)

        # 精确匹配
        if domain in cls.OFFICIAL_DOMAINS:
            return {"score": 95, "level": "official", "reason": f"官方文档/权威来源: {domain}"}

        if domain in cls.HIGH_QUALITY_COMMUNITIES:
            return {"score": 80, "level": "high", "reason": f"高质量技术社区: {domain}"}

        if is_excluded_domain(url):
            return {"score": 5, "level": "spam", "reason": f"低质量/营销来源: {domain}"}

        # 后缀匹配（GitHub Pages等）
        for suffix in cls.TECH_BLOGS:
            if domain.endswith(suffix):
                return {"score": 60, "level": "medium", "reason": f"技术博客/项目页: {domain}"}

        # 默认：未知来源
        return {"score": 50, "level": "medium", "reason": f"未知来源: {domain}"}

    @staticmethod
    def _extract_domain(url: str) -> str:
        """提取域名（去www前缀）"""
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if domain.startswith('www.'):
            domain = domain[4:]
        return domain

    @classmethod
    def _query_from_api(cls, domain: str) -> Dict | None:
        """从内存缓存查询来源可信度（预热后不发起网络请求）"""
        import time as _time
        cached = cls._api_cache.get(domain)
        if cached:
            result, ts = cached
            if _time.time() - ts < cls._cache_ttl:
                return result
        return None

    @classmethod
    async def preload_authority_cache(cls):
        """从 Java API 一次性加载全量来源可信度到内存缓存。

        应在日报任务开始前调用，后续 score() 只读缓存，不阻塞事件循环。
        """
        try:
            from config import settings
            import httpx
            java_url = getattr(settings, 'java_api_url', '')
            if not java_url:
                return
            headers = {"Content-Type": "application/json"}
            api_key = getattr(settings, 'callback_api_key', '')
            if api_key:
                headers["X-Callback-Key"] = api_key
            timeout = getattr(settings, 'sources_api_timeout', 5.0)
            import time as _time
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.get(
                    f"{java_url}/api/internal/collector/source-authority/all",
                    headers=headers,
                )
                if resp.status_code == 200:
                    data_list = resp.json().get("data", [])
                    now = _time.time()
                    for item in data_list:
                        if isinstance(item, dict) and item.get("domain"):
                            cls._api_cache[item["domain"]] = ({
                                "score": item.get("score", 50),
                                "level": item.get("level", "medium"),
                                "reason": f"数据库来源({item.get('level', 'medium')}): {item['domain']}",
                            }, now)
                    logger.info("[SourceAuthority] Preloaded %d authority records", len(data_list))
        except Exception as e:
            logger.debug("[SourceAuthority] Preload failed (will use hardcoded): %s", e)


# ============ 预编译正则 ============

_RE_HEADINGS = re.compile(r'#{2,4}\s+\S')
_RE_CODE_BLOCKS = re.compile(r'```[\s\S]*?```')
_RE_LIST = re.compile(r'^[\s]*[-*]\s+\S', re.MULTILINE)
_RE_NESTED_LIST = re.compile(r'^[\s]*[-*]\s+.*\n[\s]{2,}[-*]\s+', re.MULTILINE)
_RE_TABLE = re.compile(r'\|[\s\-:]+\|')


def _build_combined_pattern(keywords: list[str]) -> re.Pattern | None:
    """将关键词列表编译为单个交替正则，用于一次扫描"""
    escaped = [re.escape(kw) for kw in keywords if kw]
    if not escaped:
        return None
    return re.compile("|".join(escaped))


# ============ 内容质量评分 ============

class ContentQuality:
    """内容质量评分体系"""

    # 缓存：避免每次调用都 split + 编译
    _cached_clickbait_raw: str | None = None
    _cached_ad_raw: str | None = None
    _cached_paywall_raw: str | None = None
    _cached_clickbait_list: list[str] = []
    _cached_ad_list: list[str] = []
    _cached_paywall_list: list[str] = []
    _cached_clickbait_re: re.Pattern | None = None
    _cached_ad_re: re.Pattern | None = None
    _cached_paywall_re: re.Pattern | None = None

    @classmethod
    def _clickbait_keywords(cls) -> list[str]:
        raw = settings.quality_clickbait_keywords
        if raw != cls._cached_clickbait_raw:
            cls._cached_clickbait_raw = raw
            cls._cached_clickbait_list = [kw.strip() for kw in raw.split(",") if kw.strip()]
            cls._cached_clickbait_re = _build_combined_pattern(cls._cached_clickbait_list)
        return cls._cached_clickbait_list

    @classmethod
    def _ad_keywords(cls) -> list[str]:
        raw = settings.quality_ad_keywords
        if raw != cls._cached_ad_raw:
            cls._cached_ad_raw = raw
            cls._cached_ad_list = [kw.strip() for kw in raw.split(",") if kw.strip()]
            cls._cached_ad_re = _build_combined_pattern(cls._cached_ad_list)
        return cls._cached_ad_list

    @classmethod
    def _paywall_indicators(cls) -> list[str]:
        raw = settings.quality_paywall_indicators
        if raw != cls._cached_paywall_raw:
            cls._cached_paywall_raw = raw
            cls._cached_paywall_list = [kw.strip() for kw in raw.split(",") if kw.strip()]
            cls._cached_paywall_re = _build_combined_pattern(cls._cached_paywall_list)
        return cls._cached_paywall_list

    @classmethod
    def score(cls, title: str, content: str, url: str, digest_mode: bool = False) -> Dict:
        """
        综合内容质量评分

        Args:
            digest_mode: 日报模式，降低代码密度权重（新闻类内容通常无代码）

        Returns:
            {
                "total_score": float,      # 0-100
                "dimensions": {
                    "length": float,       # 字数评分
                    "structure": float,    # 结构评分（标题层级、代码块等）
                    "code_density": float, # 代码密度评分
                    "ad_ratio": float,     # 广告占比评分
                    "clickbait": float,    # 标题党评分
                },
                "penalties": {
                    "clickbait_penalty": float,
                    "ad_penalty": float,
                    "paywall_flag": bool,
                },
                "recommendation": str,     # "keep" | "review" | "filter"
            }
        """
        dimensions = {}
        penalties = {}

        # 1. 字数评分 (0-25分)
        word_count = count_words(content)
        if word_count >= 2000:
            dimensions['length'] = 25
        elif word_count >= 1000:
            dimensions['length'] = 20
        elif word_count >= 500:
            dimensions['length'] = 15
        elif word_count >= 200:
            dimensions['length'] = 10
        else:
            dimensions['length'] = max(0, word_count / 20)

        # 2. 结构评分 (0-25分)
        structure_score = 0
        # 有标题层级
        if _RE_HEADINGS.search(content):
            structure_score += 8
        # 有代码块
        if '```' in content:
            structure_score += 8
        # 有列表
        if _RE_LIST.search(content):
            structure_score += 4
        # 有多级列表（嵌套结构，说明内容组织清晰）
        if _RE_NESTED_LIST.search(content):
            structure_score += 3
        # 有表格
        if '|' in content and _RE_TABLE.search(content):
            structure_score += 2
        dimensions['structure'] = min(structure_score, 25)

        # 3. 代码密度评分 (0-25分，平滑曲线)
        code_blocks = _RE_CODE_BLOCKS.findall(content)
        code_chars = sum(len(block) for block in code_blocks)
        total_chars = len(content) if content else 1
        code_ratio = code_chars / total_chars if total_chars > 0 else 0

        # 平滑评分：5%-50% 为最佳区间，偏离时线性降分
        if 0.05 <= code_ratio <= 0.5:
            dimensions['code_density'] = 25
        elif code_ratio > 0.5:
            # 代码过多：线性降分，最低保留5分
            dimensions['code_density'] = max(5, int(25 - (code_ratio - 0.5) * 30))
        elif code_ratio > 0.01:
            # 代码偏少：按占比线性给分
            dimensions['code_density'] = max(5, int(code_ratio / 0.05 * 25))
        else:
            dimensions['code_density'] = 5  # 几乎无代码

        # 日报模式补偿：新闻/公告类内容无代码是正常的，给予中性分
        if digest_mode and dimensions['code_density'] < 10:
            dimensions['code_density'] = 15

        # 4. 广告占比评分 (0-25分，反向：25=无广告)
        cls._ad_keywords()  # ensure cache populated
        ad_re = cls._cached_ad_re
        ad_count = len(ad_re.findall(content)) if ad_re else 0
        ad_ratio = min(ad_count / 5, 1.0)  # 5个以上广告词视为满广告
        dimensions['ad_ratio'] = 25 * (1 - ad_ratio)

        # 日报模式：增加来源权威性维度，用来源评分替代代码密度
        if digest_mode:
            source_auth = SourceAuthority.score(url)
            dimensions['source_authority'] = min(25, int(source_auth['score'] / 4))
            # 总分 = 字数 + 结构 + 来源权威 + 广告（去掉代码密度）
            base_score = (
                dimensions['length']
                + dimensions['structure']
                + dimensions['source_authority']
                + dimensions['ad_ratio']
            )
        else:
            base_score = sum(dimensions.values())

        # 5. 标题党惩罚
        cls._clickbait_keywords()  # ensure cache populated
        clickbait_re = cls._cached_clickbait_re
        title_lower = title.lower()
        clickbait_count = len(clickbait_re.findall(title_lower)) if clickbait_re else 0
        clickbait_penalty = min(clickbait_count * 15, 50)
        penalties['clickbait_penalty'] = clickbait_penalty

        # 6. 广告惩罚
        ad_penalty = min(ad_count * 10, 40)
        penalties['ad_penalty'] = ad_penalty

        # 7. 付费墙检测
        cls._paywall_indicators()  # ensure cache populated
        paywall_re = cls._cached_paywall_re
        content_lower = content.lower()
        paywall_flag = bool(paywall_re.search(content_lower)) if paywall_re else False
        penalties['paywall_flag'] = paywall_flag

        # 8. 时效性检测（P2: 信息不滞后）
        freshness = cls._detect_freshness(url, content)

        # 总分计算（时效性作为 bonus，不直接扣分）
        total_score = base_score - clickbait_penalty - ad_penalty + freshness.get('bonus', 0)
        total_score = max(0, min(100, total_score))

        # 推荐决策
        if total_score >= settings.quality_keep_threshold and not paywall_flag:
            recommendation = "keep"
        elif total_score >= settings.quality_review_threshold or (paywall_flag and total_score >= settings.quality_keep_threshold - 10):
            recommendation = "review"
        else:
            recommendation = "filter"

        return {
            "total_score": round(total_score, 1),
            "dimensions": dimensions,
            "penalties": penalties,
            "freshness": freshness,
            "recommendation": recommendation,
        }

    @staticmethod
    def _detect_freshness(url: str, content: str) -> dict:
        """
        检测内容时效性（P2: 信息不能滞后）

        从 URL 路径和内容中尝试提取发布年份/日期，评估内容新旧。
        Returns:
            {"bonus": int, "age_years": int|None, "source": str}
            bonus: 近年内容 +5~10，过时内容 0，无法判断 +3（中性）
        """
        current_year = datetime.datetime.now().year

        # 策略1: URL 路径中的年份（如 /2024/01/xxx.html）
        year_match = re.search(r'/(20\d{2})/', url)
        if year_match:
            year = int(year_match.group(1))
            age = current_year - year
            if age <= 1:
                return {"bonus": 5, "age_years": age, "source": "url_year"}
            elif age <= 2:
                return {"bonus": 2, "age_years": age, "source": "url_year"}
            else:
                return {"bonus": 0, "age_years": age, "source": "url_year"}

        # 策略2: 内容中的日期标记（如 "Updated: 2024-05", "Published: Jan 2024"）
        date_patterns = [
            r'(?:updated?|published|posted|modified)[\s:]+(\d{4})[-/]\d{1,2}',
            r'(\d{4})[-/]\d{1,2}[-/]\d{1,2}',
            r'(\d{4})年\d{1,2}月',
        ]
        for pattern in date_patterns:
            m = re.search(pattern, content[:3000], re.IGNORECASE)
            if m:
                year = int(m.group(1))
                if 2010 <= year <= current_year + 1:
                    age = current_year - year
                    if age <= 1:
                        return {"bonus": 5, "age_years": age, "source": "content_date"}
                    elif age <= 2:
                        return {"bonus": 2, "age_years": age, "source": "content_date"}
                    else:
                        return {"bonus": 0, "age_years": age, "source": "content_date"}

        # 无法判断时给中性分，不惩罚也不奖励
        return {"bonus": 3, "age_years": None, "source": "unknown"}


# ============ 便捷函数 ============

def evaluate_content(url: str, title: str, content: str, task_type: str = None) -> Dict:
    """
    一站式内容评估：来源可信度 + 内容质量

    Args:
        task_type: 任务类型，"digest" 时提高来源权重（新闻类内容代码密度低但来源可信）

    Returns:
        {
            "source": SourceAuthority.score结果,
            "quality": ContentQuality.score结果,
            "final_score": float,  # 综合评分
            "verdict": str,        # "pass" | "review" | "reject"
        }
    """
    source = SourceAuthority.score(url)
    quality = ContentQuality.score(title, content, url, digest_mode=(task_type == "digest"))

    # 日报任务：提高来源权重、降低内容质量权重
    # 新闻类内容天然缺少代码块和结构化格式，内容质量分低不代表无价值
    if task_type == "digest":
        src_weight = 0.55
        cnt_weight = 0.45
    else:
        src_weight = settings.quality_source_weight
        cnt_weight = settings.quality_content_weight

    final_score = source["score"] * src_weight + quality["total_score"] * cnt_weight

    # 决策（P1: 宁可少而不可错）
    if source["level"] == "spam":
        verdict = "reject"
    elif source["level"] == "low":
        # 内容农场来源更严格：质量分<50直接拒绝，50-60 review，>=60才考虑pass
        if quality["total_score"] < settings.quality_review_threshold:
            verdict = "reject"
        elif final_score >= settings.eval_review_threshold + 15:
            verdict = "review"  # 内容农场即使分数高也不直接pass
        else:
            verdict = "reject"
    elif final_score >= settings.eval_pass_threshold:
        verdict = "pass"
    elif final_score >= settings.eval_review_threshold:
        verdict = "review"
    else:
        verdict = "reject"

    return {
        "source": source,
        "quality": quality,
        "final_score": round(final_score, 1),
        "verdict": verdict,
    }


def filter_results(results: list) -> tuple:
    """
    批量过滤爬取结果

    Returns:
        (passed_results, rejected_results)
    """
    passed = []
    rejected = []

    for result in results:
        url = result.get('url', '') if isinstance(result, dict) else getattr(result, 'url', '')
        title = result.get('title', '') if isinstance(result, dict) else getattr(result, 'title', '')
        content = result.get('markdown', '') if isinstance(result, dict) else getattr(result, 'markdown', '')

        evaluation = evaluate_content(url, title, content)

        # 附加评估结果到结果对象
        if isinstance(result, dict):
            result['_evaluation'] = evaluation
        else:
            setattr(result, '_evaluation', evaluation)

        if evaluation["verdict"] == "pass":
            passed.append(result)
        else:
            rejected.append(result)

    return passed, rejected
