"""
内容质量评估模块

提供来源可信度评分 + 内容质量评分 + 低质量过滤能力

决策权重（领主将军阁下明确）：
  P1: 内容正确，质量要高 > P2: 信息不滞后 > P3: 重复性低
  宁可少而不可错
"""

import re
from typing import Dict, List, Optional
from urllib.parse import urlparse


# ============ 来源可信度数据库 ============

class SourceAuthority:
    """来源可信度评分体系"""

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

    # 内容农场/低质量来源 (0-30分，直接降权)
    CONTENT_FARMS = {
        'baijiahao.baidu.com',
        'haokan.baidu.com',
        'toutiao.com',
        'sohu.com',      # 搜狐号文章 /a/
        '163.com',       # 网易号文章 /dy/
        'ifeng.com',     # 凤凰号 /c/
        'sina.com.cn',   # 新浪看点
    }

    # 广告/营销/非技术站点 (直接过滤)
    SPAM_DOMAINS = {
        'mp.weixin.qq.com',   # 公众号质量参差
    }

    @classmethod
    def score(cls, url: str) -> Dict:
        """
        评估来源可信度

        Returns:
            {
                "score": float,        # 0-100
                "level": str,          # "official" | "high" | "medium" | "low" | "spam"
                "reason": str,         # 评分理由
            }
        """
        domain = cls._extract_domain(url)

        # 精确匹配
        if domain in cls.OFFICIAL_DOMAINS:
            return {"score": 95, "level": "official", "reason": f"官方文档/权威来源: {domain}"}

        if domain in cls.HIGH_QUALITY_COMMUNITIES:
            return {"score": 80, "level": "high", "reason": f"高质量技术社区: {domain}"}

        if domain in cls.CONTENT_FARMS:
            return {"score": 20, "level": "low", "reason": f"内容农场: {domain}"}

        if domain in cls.SPAM_DOMAINS:
            return {"score": 5, "level": "spam", "reason": f"低质量/营销来源: {domain}"}

        # 后缀匹配（GitHub Pages等）
        for suffix in cls.TECH_BLOGS:
            if domain.endswith(suffix):
                return {"score": 60, "level": "medium", "reason": f"技术博客/项目页: {domain}"}

        # 路径检测（内容农场路径）
        path = urlparse(url).path
        if '/a/' in path and 'sohu.com' in domain:
            return {"score": 20, "level": "low", "reason": "搜狐号内容农场路径"}
        if '/dy/' in path and '163.com' in domain:
            return {"score": 20, "level": "low", "reason": "网易号内容农场路径"}

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


# ============ 内容质量评分 ============

class ContentQuality:
    """内容质量评分体系"""

    # 标题党关键词
    CLICKBAIT_KEYWORDS = [
        '震惊', '绝了', '逆天', '炸裂', '颠覆', '史诗', '神级',
        '99%的人不知道', '看完我沉默了', '后悔没早点',
        '太可怕了', '万万没想到', '不可思议', '惊人',
        '史上最强', '全网首发', '独家揭秘', '内幕',
        '震惊中外', '轰动', '爆款', '疯传',
        'shocking', 'unbelievable', 'mind-blowing', 'epic',
        'you won\'t believe', 'this changes everything',
    ]

    # 广告/营销关键词
    AD_KEYWORDS = [
        '限时优惠', '点击购买', '立即下单', '免费试用',
        '优惠券', '折扣码', '推广链接', 'affiliate',
        '赞助内容', '广告合作', '扫码领取', '关注公众号',
        '限量', '秒杀', '抢购', '不容错过', '错过等一年',
    ]

    # 付费墙指示词
    PAYWALL_INDICATORS = [
        'subscribe to read', 'membership required', 'premium content',
        '登录后阅读', '订阅后查看', '会员专属', '付费阅读',
        'sign up to continue', 'create an account',
    ]

    @classmethod
    def score(cls, title: str, content: str, url: str) -> Dict:
        """
        综合内容质量评分

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
        word_count = cls._count_words(content)
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
        if re.search(r'#{2,4}\s+\S', content):
            structure_score += 8
        # 有代码块
        if '```' in content:
            structure_score += 8
        # 有列表
        if re.search(r'^[\s]*[-*]\s+\S', content, re.MULTILINE):
            structure_score += 4
        # 有多级列表（嵌套结构，说明内容组织清晰）
        if re.search(r'^[\s]*[-*]\s+.*\n[\s]{2,}[-*]\s+', content, re.MULTILINE):
            structure_score += 3
        # 有表格
        if '|' in content and re.search(r'\|[\s\-:]+\|', content):
            structure_score += 2
        dimensions['structure'] = min(structure_score, 25)

        # 3. 代码密度评分 (0-25分，平滑曲线)
        code_blocks = re.findall(r'```[\s\S]*?```', content)
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

        # 4. 广告占比评分 (0-25分，反向：25=无广告)
        ad_count = sum(1 for kw in cls.AD_KEYWORDS if kw in content)
        ad_ratio = min(ad_count / 5, 1.0)  # 5个以上广告词视为满广告
        dimensions['ad_ratio'] = 25 * (1 - ad_ratio)

        # 5. 标题党惩罚
        clickbait_count = sum(1 for kw in cls.CLICKBAIT_KEYWORDS if kw in title.lower())
        clickbait_penalty = min(clickbait_count * 15, 50)
        penalties['clickbait_penalty'] = clickbait_penalty

        # 6. 广告惩罚
        ad_penalty = min(ad_count * 10, 40)
        penalties['ad_penalty'] = ad_penalty

        # 7. 付费墙检测
        paywall_flag = any(ind in content.lower() for ind in cls.PAYWALL_INDICATORS)
        penalties['paywall_flag'] = paywall_flag

        # 8. 时效性检测（P2: 信息不滞后）
        freshness = cls._detect_freshness(url, content)

        # 总分计算（时效性作为 bonus，不直接扣分）
        base_score = sum(dimensions.values())
        total_score = base_score - clickbait_penalty - ad_penalty + freshness.get('bonus', 0)
        total_score = max(0, min(100, total_score))

        # 推荐决策
        if total_score >= 70 and not paywall_flag:
            recommendation = "keep"
        elif total_score >= 50 or (paywall_flag and total_score >= 60):
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
        import datetime
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

    @staticmethod
    def _count_words(text: str) -> int:
        """统计字数：中文字符 + 英文单词（英文单词信息密度较低，加权1.5x）"""
        if not text:
            return 0
        cn_chars = len(re.findall(r'[一-鿿]', text))
        en_words = len(re.findall(r'[a-zA-Z]+', text))
        return int(cn_chars + en_words * 1.5)


# ============ 便捷函数 ============

def evaluate_content(url: str, title: str, content: str) -> Dict:
    """
    一站式内容评估：来源可信度 + 内容质量

    Returns:
        {
            "source": SourceAuthority.score结果,
            "quality": ContentQuality.score结果,
            "final_score": float,  # 综合评分
            "verdict": str,        # "pass" | "review" | "reject"
        }
    """
    source = SourceAuthority.score(url)
    quality = ContentQuality.score(title, content, url)

    # 综合评分：来源权重40% + 质量权重60%
    final_score = source["score"] * 0.4 + quality["total_score"] * 0.6

    # 决策（P1: 宁可少而不可错）
    if source["level"] == "spam":
        verdict = "reject"
    elif source["level"] == "low":
        # 内容农场来源更严格：质量分<50直接拒绝，50-60 review，>=60才考虑pass
        if quality["total_score"] < 50:
            verdict = "reject"
        elif final_score >= 60:
            verdict = "review"  # 内容农场即使分数高也不直接pass
        else:
            verdict = "reject"
    elif final_score >= 65:
        verdict = "pass"
    elif final_score >= 45:
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
