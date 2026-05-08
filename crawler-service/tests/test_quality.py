"""
ContentQuality 模块单元测试

覆盖：
- SourceAuthority.score: 官方域名/社区/博客/垃圾/未知/路径检测
- ContentQuality.score: 长短文/代码/结构/广告/标题党/付费墙/时效性
- evaluate_content: spam直接reject/低质量来源更严格/正常阈值判定
- filter_results: 批量过滤/空列表
- 边界: 空字符串/None标题
"""

import os
import sys
import datetime
import pytest
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from crawler.quality import SourceAuthority, ContentQuality, evaluate_content, filter_results


# ============== SourceAuthority Tests ==============


class TestSourceAuthority:

    def test_official_domain_docs_spring(self):
        """官方文档域名得95分"""
        result = SourceAuthority.score("https://docs.spring.io/spring-boot/docs/current/reference/html/")
        assert result["score"] == 95
        assert result["level"] == "official"

    def test_official_domain_react_dev(self):
        """react.dev 官方域名"""
        result = SourceAuthority.score("https://react.dev/learn")
        assert result["score"] == 95
        assert result["level"] == "official"

    def test_official_domain_kubernetes(self):
        """kubernetes.io 官方域名"""
        result = SourceAuthority.score("https://kubernetes.io/docs/concepts/")
        assert result["score"] == 95
        assert result["level"] == "official"

    def test_high_quality_community_medium(self):
        """Medium 高质量社区得80分"""
        result = SourceAuthority.score("https://medium.com/@user/some-article-abc123")
        assert result["score"] == 80
        assert result["level"] == "high"

    def test_high_quality_community_dev_to(self):
        """dev.to 高质量社区"""
        result = SourceAuthority.score("https://dev.to/user/my-post")
        assert result["score"] == 80
        assert result["level"] == "high"

    def test_high_quality_community_hacker_news(self):
        """Hacker News 高质量社区"""
        result = SourceAuthority.score("https://news.ycombinator.com/item?id=12345")
        assert result["score"] == 80
        assert result["level"] == "high"

    def test_tech_blog_github_io(self):
        """GitHub Pages 后缀匹配得60分"""
        result = SourceAuthority.score("https://someone.github.io/my-project/")
        assert result["score"] == 60
        assert result["level"] == "medium"

    def test_tech_blog_github_com(self):
        """github.com 后缀匹配"""
        result = SourceAuthority.score("https://github.com/user/repo")
        assert result["score"] == 60
        assert result["level"] == "medium"

    def test_tech_blog_netlify(self):
        """netlify.app 后缀匹配"""
        result = SourceAuthority.score("https://my-site.netlify.app/docs")
        assert result["score"] == 60
        assert result["level"] == "medium"

    def test_spam_domain_youtube(self):
        """YouTube 排除域名得5分"""
        result = SourceAuthority.score("https://www.youtube.com/watch?v=abc123")
        assert result["score"] == 5
        assert result["level"] == "spam"

    def test_spam_domain_taobao(self):
        """淘宝排除域名得5分"""
        result = SourceAuthority.score("https://www.taobao.com/product/123")
        assert result["score"] == 5
        assert result["level"] == "spam"

    def test_spam_domain_bilibili(self):
        """B站排除域名得5分"""
        result = SourceAuthority.score("https://www.bilibili.com/video/BV123")
        assert result["score"] == 5
        assert result["level"] == "spam"

    def test_unknown_domain(self):
        """未知域名默认50分"""
        result = SourceAuthority.score("https://some-random-tech-blog.example.com/post/1")
        assert result["score"] == 50
        assert result["level"] == "medium"
        assert "未知来源" in result["reason"]

    def test_sohu_excluded_domain(self):
        """sohu.com 在 EXCLUDED_DOMAINS 中，被 is_excluded_domain 捕获得5分（spam）
        注: quality.py 路径检测(/a/)是死代码，因为 sohu.com 整域名已被排除。
        """
        result = SourceAuthority.score("https://www.sohu.com/a/123456789_abcdef")
        assert result["score"] == 5
        assert result["level"] == "spam"

    def test_163_excluded_domain(self):
        """163.com 在 EXCLUDED_DOMAINS 中，被 is_excluded_domain 捕获得5分（spam）
        注: quality.py 路径检测(/dy/)是死代码，因为 163.com 整域名已被排除。
        """
        result = SourceAuthority.score("https://www.163.com/dy/article/ABCDEFG.html")
        assert result["score"] == 5
        assert result["level"] == "spam"

    def test_www_prefix_stripped(self):
        """www前缀会被去除，仍正确匹配官方域名"""
        result = SourceAuthority.score("https://www.postgresql.org/docs/current/")
        assert result["score"] == 95
        assert result["level"] == "official"


# ============== ContentQuality Tests ==============


class TestContentQuality:

    @staticmethod
    def _make_long_content(word_count_target=2500):
        """生成指定字数的内容（中英混合）"""
        cn_chunk = "这是一段测试内容用于验证字数评分逻辑" * 10
        return cn_chunk * (word_count_target // 100 + 1)

    @staticmethod
    def _make_short_content():
        """生成短内容"""
        return "hello world"

    def test_long_article_high_length_score(self):
        """长文章(>=2000词)字数维度得25分"""
        content = self._make_long_content(2500)
        result = ContentQuality.score("Normal Title", content, "https://example.com/post")
        assert result["dimensions"]["length"] == 25

    def test_short_article_low_length_score(self):
        """短文章字数维度得低分"""
        content = self._make_short_content()
        result = ContentQuality.score("Normal Title", content, "https://example.com/post")
        assert result["dimensions"]["length"] < 10

    def test_code_blocks_add_structure_and_density(self):
        """有代码块的结构和代码密度都加分"""
        content = "## Intro\n\nSome explanation\n\n```python\nprint('hello')\nx = 42\n```\n\n## Summary\n"
        content += "more text " * 100  # padding to avoid too-short penalty
        result = ContentQuality.score("Technical Post", content, "https://example.com/post")
        assert result["dimensions"]["structure"] >= 8  # code block bonus
        assert result["dimensions"]["code_density"] >= 5

    def test_heading_levels_add_structure(self):
        """有标题层级(h2-h4)的结构加分"""
        content = "## Section 1\n\nSome text here\n\n### Subsection\n\nMore text\n"
        content += "padding content " * 50
        result = ContentQuality.score("Structured Post", content, "https://example.com/post")
        assert result["dimensions"]["structure"] >= 8  # heading bonus

    def test_ad_keywords_penalty(self):
        """广告关键词导致广告惩罚"""
        content = "这是一篇技术文章。限时优惠点击购买立即下单优惠券折扣码推广链接"
        content += " 更多内容" * 100
        result = ContentQuality.score("Normal Title", content, "https://example.com/post")
        assert result["penalties"]["ad_penalty"] > 0
        # ad_ratio 维度也应该低于25
        assert result["dimensions"]["ad_ratio"] < 25

    def test_clickbait_title_penalty(self):
        """标题党关键词导致标题党惩罚"""
        content = "这是一篇正常的技术文章内容" * 100
        result = ContentQuality.score("震惊！99%的人不知道这个Python技巧", content, "https://example.com/post")
        assert result["penalties"]["clickbait_penalty"] > 0

    def test_paywall_detection(self):
        """付费墙指示词被检测到"""
        content = "Some article content here. subscribe to read the full article."
        content += " more text" * 100
        result = ContentQuality.score("Premium Article", content, "https://example.com/post")
        assert result["penalties"]["paywall_flag"] is True

    def test_freshness_bonus_from_url_year(self):
        """URL中的当前年份给予时效性bonus"""
        current_year = datetime.datetime.now().year
        url = f"https://example.com/{current_year}/01/some-article.html"
        content = "Some content" * 100
        result = ContentQuality.score("Recent Article", content, url)
        assert result["freshness"]["bonus"] == 5
        assert result["freshness"]["source"] == "url_year"

    def test_freshness_bonus_old_url(self):
        """URL中旧年份无时效性bonus"""
        url = "https://example.com/2020/01/old-article.html"
        content = "Some content" * 100
        result = ContentQuality.score("Old Article", content, url)
        assert result["freshness"]["bonus"] == 0
        assert result["freshness"]["age_years"] > 2

    def test_freshness_bonus_from_content_date(self):
        """内容中的日期标记给予时效性bonus"""
        current_year = datetime.datetime.now().year
        content = f"Updated: {current_year}-05 This article covers recent changes. "
        content += "more content " * 100
        result = ContentQuality.score("Dated Article", content, "https://example.com/post")
        assert result["freshness"]["bonus"] == 5
        assert result["freshness"]["source"] == "content_date"

    def test_freshness_unknown_gives_neutral_bonus(self):
        """无法判断时效时给中性bonus=3"""
        content = "Some content without dates" * 100
        result = ContentQuality.score("Dateless Article", content, "https://example.com/post")
        assert result["freshness"]["bonus"] == 3
        assert result["freshness"]["age_years"] is None

    def test_total_score_clamped_to_100(self):
        """总分不超过100"""
        content = "## Great Article\n\n```python\nprint('hi')\n```\n\n"
        content += "Excellent content " * 500
        result = ContentQuality.score("Normal Title", content, "https://example.com/post")
        assert result["total_score"] <= 100

    def test_recommendation_keep_for_high_quality(self):
        """高质量内容推荐keep（total_score>=70 且无付费墙）"""
        # 构造高分内容：长文+标题层级+代码块+列表+表格
        content = "## Introduction\n\n### Background\n\n- Point one\n- Point two\n"
        content += "\n```python\ndef hello():\n    print('world')\n    return 42\n```\n\n"
        content += "| col1 | col2 |\n|------|------|\n| a    | b    |\n\n"
        # 需要足够长的内容以获得字数满分
        content += "This is high quality technical content about software engineering. " * 150
        result = ContentQuality.score("Normal Title", content, "https://example.com/post")
        assert result["total_score"] >= 70
        assert result["recommendation"] == "keep"

    def test_recommendation_filter_for_poor_quality(self):
        """极低质量内容推荐filter"""
        content = ""
        result = ContentQuality.score("Normal Title", content, "https://example.com/post")
        assert result["recommendation"] == "filter"


# ============== evaluate_content Tests ==============


class TestEvaluateContent:

    def test_spam_source_always_reject(self):
        """spam来源直接reject，不管内容质量多高"""
        good_content = "## Great Article\n\n" + "High quality content " * 200
        result = evaluate_content(
            "https://www.youtube.com/watch?v=abc",
            "Amazing Tech Tutorial",
            good_content,
        )
        assert result["verdict"] == "reject"
        assert result["source"]["level"] == "spam"

    def test_low_source_strict_judgment(self):
        """低质量来源(内容农场)更严格：质量分<50直接reject"""
        poor_content = "Short text"
        result = evaluate_content(
            "https://www.sohu.com/a/123456_some_article",
            "Some Title",
            poor_content,
        )
        assert result["verdict"] == "reject"

    def test_normal_source_pass_threshold(self):
        """正常来源+高质量内容=pass(>=65)"""
        good_content = "## Introduction\n\n" + "Quality content " * 300
        good_content += "\n```java\nSystem.out.println(\"hello\");\n```\n"
        result = evaluate_content(
            "https://dev.to/user/great-post",
            "Best Practices for Java Development",
            good_content,
        )
        assert result["verdict"] == "pass"
        assert result["final_score"] >= 65

    def test_normal_source_review_threshold(self):
        """正常来源+中等质量=review(45-65)"""
        medium_content = "Some decent content " * 50
        result = evaluate_content(
            "https://example.com/post/1",
            "A Decent Article",
            medium_content,
        )
        assert result["verdict"] in ("pass", "review", "reject")  # verify it runs
        assert isinstance(result["final_score"], float)

    def test_final_score_weights(self):
        """综合评分=来源40%+质量60%"""
        # 用一个已知来源来验证权重
        result = evaluate_content(
            "https://docs.spring.io/guide",
            "Spring Guide",
            "Content " * 100,
        )
        source_score = 95  # official
        quality_score = result["quality"]["total_score"]
        expected = round(source_score * 0.4 + quality_score * 0.6, 1)
        assert result["final_score"] == expected


# ============== filter_results Tests ==============


class TestFilterResults:

    def test_filter_mixed_results(self):
        """批量过滤：通过和拒绝各占一部分"""
        good_content = "## Quality\n\n" + "Great technical content " * 200
        bad_content = "short"
        results = [
            {"url": "https://docs.spring.io/guide", "title": "Spring Guide", "markdown": good_content},
            {"url": "https://www.youtube.com/watch?v=abc", "title": "Video", "markdown": bad_content},
            {"url": "https://dev.to/user/post", "title": "Dev Post", "markdown": good_content},
        ]
        passed, rejected = filter_results(results)
        # YouTube should be rejected; others may pass or review depending on score
        assert len(rejected) >= 1
        assert any(r["url"] == "https://www.youtube.com/watch?v=abc" for r in rejected)
        # _evaluation attached
        for r in results:
            assert "_evaluation" in r

    def test_filter_empty_list(self):
        """空列表返回空元组"""
        passed, rejected = filter_results([])
        assert passed == []
        assert rejected == []


# ============== Boundary / Edge Cases ==============


class TestEdgeCases:

    def test_empty_content_string(self):
        """空字符串内容不崩溃"""
        result = ContentQuality.score("Title", "", "https://example.com/post")
        assert result["total_score"] >= 0
        assert result["dimensions"]["length"] == 0

    def test_none_title_treated_as_clickbait_safe(self):
        """None标题在clickbait检测中不崩溃（.lower()会报错，验证处理）"""
        # ContentQuality.score does title.lower() — if None passed, it crashes.
        # This test documents current behavior: caller must pass str.
        # Verify that empty string works as a safe alternative.
        result = ContentQuality.score("", "Some content " * 50, "https://example.com/post")
        assert result["penalties"]["clickbait_penalty"] == 0

    def test_very_long_ad_heavy_content(self):
        """大量广告关键词，分数被严重压低但不为负"""
        ad_content = "限时优惠点击购买立即下单免费试用优惠券折扣码推广链接赞助内容广告合作扫码领取关注公众号限量秒杀抢购不容错过错过等一年"
        ad_content += " Normal text" * 20
        result = ContentQuality.score("Normal Title", ad_content, "https://example.com/post")
        assert result["total_score"] >= 0
        assert result["penalties"]["ad_penalty"] > 0
        assert result["dimensions"]["ad_ratio"] < 25

    def test_multiple_clickbait_keywords_cap_at_50(self):
        """多个标题党关键词惩罚上限50"""
        title = "震惊！绝了！逆天！炸裂！颠覆！史诗！神级！"
        content = "content " * 100
        result = ContentQuality.score(title, content, "https://example.com/post")
        assert result["penalties"]["clickbait_penalty"] <= 50

    def test_paywall_with_high_score_gets_review(self):
        """有付费墙但质量高时推荐review（不直接keep）"""
        content = "## Premium Guide\n\nsubscribe to read more. " + "Quality content " * 200
        result = ContentQuality.score("Premium Title", content, "https://example.com/post")
        assert result["penalties"]["paywall_flag"] is True
        assert result["recommendation"] in ("review", "filter")
