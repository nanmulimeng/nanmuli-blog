"""内容质量评分极端测试：SourceAuthority、ContentQuality、evaluate_content 边界情况"""

import os
import sys
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from crawler.quality import SourceAuthority, ContentQuality, evaluate_content


# ============== SourceAuthority 极端测试 ==============


class TestSourceAuthorityExtreme:
    """来源可信度评分极端测试"""

    def test_official_domains_get_95(self):
        for domain in ["docs.spring.io", "kubernetes.io", "python.org"]:
            result = SourceAuthority.score(f"https://{domain}/some/path")
            assert result["score"] == 95
            assert result["level"] == "official"

    def test_high_quality_communities_get_80(self):
        for domain in ["stackoverflow.com", "infoq.com", "news.ycombinator.com"]:
            result = SourceAuthority.score(f"https://{domain}/question/123")
            assert result["score"] == 80
            assert result["level"] == "high"

    def test_github_pages_suffix_match(self):
        result = SourceAuthority.score("https://myproject.github.io/repo/")
        assert result["score"] == 60
        assert result["level"] == "medium"
        assert "技术博客" in result["reason"]

    def test_unknown_domain_gets_50(self):
        result = SourceAuthority.score("https://random-unknown-site.xyz/article")
        assert result["score"] == 50
        assert result["level"] == "medium"

    def test_www_prefix_stripped(self):
        r1 = SourceAuthority.score("https://www.python.org/docs")
        r2 = SourceAuthority.score("https://python.org/docs")
        assert r1["score"] == r2["score"] == 95

    def test_excluded_domain_gets_5(self):
        result = SourceAuthority.score("https://youtube.com/watch?v=123")
        assert result["score"] == 5
        assert result["level"] == "spam"

    def test_empty_url_no_crash(self):
        result = SourceAuthority.score("")
        assert result["score"] == 50  # unknown

    def test_very_long_url(self):
        url = "https://example.com/path?" + "a" * 5000
        result = SourceAuthority.score(url)
        assert result["score"] == 50

    def test_url_with_port(self):
        result = SourceAuthority.score("https://docs.spring.io:8443/guide")
        # 端口导致精确匹配失败，回退到 unknown
        assert result["score"] >= 50

    def test_url_with_auth(self):
        result = SourceAuthority.score("https://user:pass@docs.spring.io/guide")
        # auth+host 导致精确匹配失败，回退到 unknown
        assert result["score"] >= 50

    def test_case_insensitive_domain(self):
        result = SourceAuthority.score("https://DOCS.SPRING.IO/guide")
        assert result["score"] == 95

    def test_ip_address_url(self):
        result = SourceAuthority.score("https://192.168.1.100:8080/docs")
        assert result["level"] in ("medium", "spam")
        assert result["score"] >= 5


# ============== ContentQuality 极端测试 ==============


class TestContentQualityExtreme:
    """内容质量评分极端测试"""

    def test_empty_content(self):
        result = ContentQuality.score("标题", "", "https://example.com")
        assert result["total_score"] >= 0
        assert "dimensions" in result

    def test_empty_title_and_content(self):
        result = ContentQuality.score("", "", "https://example.com")
        assert result["total_score"] >= 0

    def test_very_short_content(self):
        result = ContentQuality.score("标题", "短内容", "https://example.com")
        assert result["dimensions"]["length"] < 10

    def test_long_well_structured_content(self):
        content = (
            "# Title\n\n## Section 1\n\n"
            + "技术内容段落。 " * 100
            + "\n\n```python\nprint('hello')\n```\n\n"
            + "- 列表项1\n- 列表项2\n- 列表项3\n\n"
            + "| A | B |\n|---|---|\n| 1 | 2 |\n"
        )
        result = ContentQuality.score("技术文章", content, "https://example.com/2026/article")
        assert result["dimensions"]["structure"] >= 15
        assert result["dimensions"]["code_density"] >= 5
        assert result["total_score"] > 40

    def test_pure_code_content(self):
        code = "```python\n" + "\n".join(f"def func_{i}(): pass" for i in range(50)) + "\n```"
        result = ContentQuality.score("代码片段", code, "https://example.com")
        # 代码密度高但可能>50%
        assert result["dimensions"]["code_density"] >= 5

    def test_clickbait_title_penalized(self):
        normal = ContentQuality.score("Spring Boot 配置指南", "内容", "https://example.com")
        clickbait = ContentQuality.score("震惊！99%的人不知道的 Spring Boot 秘密", "内容", "https://example.com")
        assert clickbait["penalties"]["clickbait_penalty"] > 0

    def test_ad_heavy_content_penalized(self):
        from unittest.mock import patch
        with patch("crawler.quality.settings") as mock_settings:
            mock_settings.quality_ad_keywords = "广告,推广,赞助,购买,优惠,折扣"
            mock_settings.quality_clickbait_keywords = ""
            mock_settings.quality_paywall_indicators = ""
            mock_settings.quality_keep_threshold = 60
            mock_settings.quality_review_threshold = 40
            mock_settings.quality_source_weight = 0.4
            mock_settings.quality_content_weight = 0.6
            # 清缓存
            ContentQuality._cached_ad_raw = None
            ContentQuality._cached_ad_re = None
            ContentQuality._cached_clickbait_raw = None
            ContentQuality._cached_clickbait_re = None
            ContentQuality._cached_paywall_raw = None
            ContentQuality._cached_paywall_re = None
            content = "技术内容。" + "点击购买广告推广优惠折扣。" * 10
            result = ContentQuality.score("标题", content, "https://example.com")
            assert result["penalties"]["ad_penalty"] > 0

    def test_old_url_gets_zero_freshness_bonus(self):
        result = ContentQuality.score("标题", "内容", "https://example.com/2020/01/old-article")
        assert result["freshness"]["bonus"] == 0
        assert result["freshness"]["age_years"] == 6

    def test_recent_url_gets_freshness_bonus(self):
        result = ContentQuality.score("标题", "内容", "https://example.com/2026/05/new-article")
        assert result["freshness"]["bonus"] >= 2

    def test_no_year_in_url_neutral_bonus(self):
        result = ContentQuality.score("标题", "内容", "https://example.com/article-no-date")
        assert result["freshness"]["bonus"] == 3  # neutral

    def test_huge_content_no_crash(self):
        huge = "技术内容段落。 " * 50000
        result = ContentQuality.score("标题", huge, "https://example.com")
        assert result["total_score"] > 0

    def test_unicode_content_no_crash(self):
        content = "# 标题\n\n中文内容 🚀\n\nこんにちは\n\n한글 테스트"
        result = ContentQuality.score(content, content, "https://example.com")
        assert result["total_score"] >= 0

    def test_nested_list_bonus(self):
        content = (
            "# Title\n\nContent.\n\n"
            "- Item 1\n  - Nested 1\n  - Nested 2\n- Item 2\n"
        )
        result = ContentQuality.score("标题", content, "https://example.com")
        assert result["dimensions"]["structure"] >= 4  # list bonus


# ============== evaluate_content 极端测试 ==============


class TestEvaluateContentExtreme:
    """evaluate_content 综合评估极端测试"""

    def test_spam_domain_rejected(self):
        result = evaluate_content("https://youtube.com/watch?v=123", "标题", "内容")
        assert result["verdict"] == "reject"

    def test_official_domain_with_good_content(self):
        content = "# Guide\n\n" + "技术内容。 " * 100 + "\n\n```yaml\nkey: value\n```"
        result = evaluate_content("https://docs.spring.io/guide", "Spring Boot 配置", content)
        assert result["verdict"] == "pass"
        assert result["source"]["level"] == "official"

    def test_digest_mode_higher_source_weight(self):
        content = "技术新闻内容。"
        normal = evaluate_content("https://example.com/news", "新闻", content)
        digest = evaluate_content("https://example.com/news", "新闻", content, task_type="digest")
        # digest 模式 source 权重 0.6，应更依赖来源可信度
        assert digest["final_score"] != normal["final_score"]

    def test_empty_inputs_no_crash(self):
        result = evaluate_content("", "", "")
        assert "verdict" in result
        assert "final_score" in result

    def test_all_fields_none_handled(self):
        # ContentQuality.score 不接受 content=None，传空字符串
        result = evaluate_content("https://example.com", "标题", "")
        assert "verdict" in result
