"""集成测试：验证完整链路（任务创建 → 爬取 → AI 整理 → 查询）

Mock 爬虫和 AI，用内存 SQLite，验证状态机流转和结果持久化。
"""

import os
import sys
import pytest
import json
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch, MagicMock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from standalone.models import TaskStatus


class MockCrawlResult:
    """模拟爬取结果"""
    def __init__(self, url, title, markdown, success=True):
        self.url = url
        self.title = title
        self.markdown = markdown
        self.success = success
        self.word_count = len(markdown) if markdown else 0
        self.crawl_time_ms = 100
        self.error_message = None if success else "Failed"
        self.depth = 0
        self.metadata = {}

    def to_dict(self):
        return {
            "url": self.url, "title": self.title, "markdown": self.markdown,
            "success": self.success, "word_count": self.word_count,
            "crawl_time_ms": self.crawl_time_ms, "error_message": self.error_message,
            "depth": self.depth, "metadata": self.metadata,
        }


@pytest.fixture
def patched_repo(mem_db):
    """返回一个使用内存 DB 的 repository 模块"""
    import standalone.repository as repo_mod

    @asynccontextmanager
    async def _mock_get_db():
        yield mem_db

    # Patch at module level where it's used (repository.py imported get_db at top)
    original = repo_mod.get_db
    repo_mod.get_db = _mock_get_db
    yield repo_mod
    repo_mod.get_db = original


# ============== 完整 single 任务链路 ==============

class TestSingleTaskIntegration:
    @pytest.mark.asyncio
    async def test_full_single_task_without_ai(self, patched_repo):
        """Single 任务：爬取成功，AI 未配置 → 跳过 AI → COMPLETED"""
        repo = patched_repo

        task_id = await repo.create_task(
            task_type="single", source_url="https://example.com/docker",
            ai_template="tech_summary"
        )
        assert task_id > 0

        await repo.update_task_status(task_id, TaskStatus.CRAWLING)
        result = MockCrawlResult("https://example.com/docker", "Docker Guide", "# Docker\nContent here.")

        total_words = await repo.save_pages(task_id, [result])
        await repo.complete_crawl(task_id, total_pages=1, completed_pages=1,
                                   crawl_duration=100, total_word_count=total_words)
        await repo.save_ai_error(task_id, "AI not configured")
        await repo.complete_task(task_id)

        task = await repo.get_task(task_id)
        assert task["status"] == TaskStatus.COMPLETED
        assert task["total_pages"] == 1
        assert task["ai_error_message"] == "AI not configured"

        pages = await repo.get_pages_by_task(task_id)
        assert len(pages) == 1
        assert pages[0]["page_title"] == "Docker Guide"

    @pytest.mark.asyncio
    async def test_full_single_task_with_ai(self, patched_repo):
        """Single 任务：爬取 + AI 整理成功 → COMPLETED with AI results"""
        repo = patched_repo

        task_id = await repo.create_task(
            task_type="single", source_url="https://example.com/spring",
            ai_template="tech_summary"
        )

        await repo.update_task_status(task_id, TaskStatus.CRAWLING)
        result = MockCrawlResult("https://example.com/spring", "Spring Boot", "# Spring\nFull content.")
        total_words = await repo.save_pages(task_id, [result])
        await repo.complete_crawl(task_id, 1, 1, 100, total_words)

        await repo.update_task_status(task_id, TaskStatus.PROCESSING)
        await repo.save_ai_results(
            task_id,
            ai_title="Spring Boot 3 指南",
            ai_summary="Spring Boot 3 核心特性解析",
            ai_key_points=["特性1", "特性2"],
            ai_tags=["spring", "java"],
            ai_category="后端开发",
            ai_full_content="## Spring Boot 3\n\n完整内容...",
            ai_duration=2000,
            ai_tokens_used=500,
        )
        await repo.complete_task(task_id)

        task = await repo.get_task(task_id)
        assert task["status"] == TaskStatus.COMPLETED
        assert task["ai_title"] == "Spring Boot 3 指南"
        assert json.loads(task["ai_key_points"]) == ["特性1", "特性2"]
        assert task["ai_category"] == "后端开发"
        assert task["ai_duration"] == 2000

    @pytest.mark.asyncio
    async def test_crawl_failure_marks_task_failed(self, patched_repo):
        """爬取全部失败 → FAILED"""
        repo = patched_repo

        task_id = await repo.create_task(task_type="single", source_url="https://example.com/bad")
        await repo.update_task_status(task_id, TaskStatus.CRAWLING)

        failed_result = MockCrawlResult("https://example.com/bad", "", "", success=False)
        await repo.save_pages(task_id, [failed_result])
        await repo.fail_task(task_id, "所有页面爬取失败")

        task = await repo.get_task(task_id)
        assert task["status"] == TaskStatus.FAILED
        assert "爬取失败" in task["error_message"]

    @pytest.mark.asyncio
    async def test_retry_resets_task(self, patched_repo):
        """失败任务重试 → 重置所有 AI 字段 → PENDING"""
        repo = patched_repo

        task_id = await repo.create_task(task_type="keyword", keyword="docker")
        await repo.update_task_status(task_id, TaskStatus.CRAWLING)

        result = MockCrawlResult("https://example.com/docker", "Docker", "# Docker")
        await repo.save_pages(task_id, [result])
        await repo.save_ai_results(task_id, "Title", "Summary", ["p1"], ["t1"], "cat", "content", 100, 50)
        await repo.save_ai_error(task_id, "Rate limited")
        await repo.fail_task(task_id, "AI failed")

        task = await repo.get_task(task_id)
        assert task["status"] == TaskStatus.FAILED

        await repo.reset_task_for_retry(task_id)
        task = await repo.get_task(task_id)
        assert task["status"] == TaskStatus.PENDING
        assert task["ai_title"] is None
        assert task["ai_error_message"] is None
        assert task["completed_pages"] == 0


# ============== 关键词任务链路 ==============

class TestKeywordTaskIntegration:
    @pytest.mark.asyncio
    async def test_keyword_search_metadata_saved(self, patched_repo):
        """关键词任务：AI 搜索元数据正确保存"""
        repo = patched_repo

        task_id = await repo.create_task(task_type="keyword", keyword="docker")
        await repo.save_ai_search_metadata(task_id, {
            "originalKeyword": "docker",
            "optimizedKeyword": "docker 容器技术",
            "searchVariants": ["docker 容器技术", "docker tutorial", "docker compose"],
        })

        task = await repo.get_task(task_id)
        meta = json.loads(task["ai_search_metadata"])
        assert meta["originalKeyword"] == "docker"
        assert meta["optimizedKeyword"] == "docker 容器技术"
        assert len(meta["searchVariants"]) == 3

    @pytest.mark.asyncio
    async def test_multi_keyword_results(self, patched_repo):
        """多关键词结果保存"""
        repo = patched_repo

        task_id = await repo.create_task(task_type="keyword", keyword="spring boot")
        results = [
            MockCrawlResult("https://a.com", "A", "Content A"),
            MockCrawlResult("https://b.com", "B", "Content B"),
            MockCrawlResult("https://c.com", "C", "Content C"),
        ]
        await repo.save_pages(task_id, results)

        pages = await repo.get_pages_by_task(task_id)
        assert len(pages) == 3


# ============== TaskExecutor Helpers ==============

class TestTaskExecutorHelpers:
    def test_extract_source_name(self):
        from standalone.task_executor import extract_source_name
        assert extract_source_name("https://github.com/user/repo") == "github.com"
        assert extract_source_name("https://www.example.com/path") == "example.com"
        assert extract_source_name("") == "未知来源"

    def test_infer_category(self):
        from standalone.task_executor import infer_category
        assert infer_category("https://github.com/x", "") == "open_source"
        assert infer_category("https://arxiv.com/x", "") == "paper"
        assert infer_category("https://example.com", "Tool release") == "dev_tool"
        assert infer_category("https://news.com/x", "") == "hot_trend"
        assert infer_category("https://blog.com/x", "Spring Boot") == "tech_article"

    @pytest.mark.asyncio
    async def test_get_digest_sections(self):
        from standalone.task_executor import get_digest_sections
        sections = await get_digest_sections()
        assert len(sections) >= 3
        names = [s["name"] for s in sections]
        assert "news" in names
        assert "opensource" in names


# ============== Routes Helper ==============

class TestRoutesHelper:
    def test_enrich_task_parses_ai_json(self):
        """验证 _enrich_task 正确解析 AI JSON 字段"""
        from standalone.routes import _enrich_task

        task = {
            "task_type": "keyword",
            "status": TaskStatus.COMPLETED,
            "total_pages": 3,
            "completed_pages": 3,
            "ai_key_points": '["point 1", "point 2"]',
            "ai_tags": '["java", "spring"]',
            "ai_search_metadata": '{"originalKeyword": "docker"}',
            "ai_template": "tech_summary",
        }

        enriched = _enrich_task(task)
        assert enriched["ai_key_points"] == ["point 1", "point 2"]
        assert enriched["ai_tags"] == ["java", "spring"]
        assert enriched["ai_search_metadata"]["originalKeyword"] == "docker"
        assert enriched["progress_percent"] == 100
        assert enriched["task_type_label"] == "关键词搜索"
        assert enriched["status_label"] == "已完成"
        assert enriched["ai_template_label"] == "技术摘要"

    def test_enrich_task_handles_bad_json(self):
        """验证 _enrich_task 容错处理无效 JSON"""
        from standalone.routes import _enrich_task

        task = {
            "task_type": "single",
            "status": TaskStatus.FAILED,
            "total_pages": 0,
            "completed_pages": 0,
            "ai_key_points": "invalid json{{{",
            "ai_tags": None,
            "ai_search_metadata": "bad",
            "ai_template": "tech_summary",
        }

        enriched = _enrich_task(task)
        # Invalid JSON should be left as-is
        assert enriched["ai_key_points"] == "invalid json{{{"
        assert enriched["status_label"] == "失败"


# ============== Digest Structured Persistence ==============

class TestDigestPersistence:
    @pytest.mark.asyncio
    async def test_save_and_get_digest_sections(self, patched_repo):
        """日报结构化数据保存与查询"""
        repo = patched_repo

        task_id = await repo.create_task(
            task_type="digest", keyword="2026-05-08", ai_template="daily_digest"
        )

        # 模拟 AI 日报结果
        sections = [
            {
                "category": "hot_trend",
                "category_name": "热点动态",
                "emoji": "🔥",
                "items": [
                    {"title": "React 19 正式发布", "one_liner": "全新编译器",
                     "source_url": "https://react.dev/blog", "source_name": "react.dev"},
                    {"title": "Go 1.23 发布", "one_liner": "改进迭代器支持",
                     "source_url": "https://go.dev/blog", "source_name": "go.dev"},
                ],
            },
            {
                "category": "open_source",
                "category_name": "开源项目",
                "emoji": "🌟",
                "items": [
                    {"title": "Bun 1.2", "one_liner": "高速 JS 运行时",
                     "source_url": "https://github.com/oven-sh/bun", "source_name": "github.com"},
                ],
            },
        ]

        await repo.save_digest_results(
            task_id,
            ai_title="技术日报 | 2026-05-08",
            ai_summary="今日技术圈重点动态",
            ai_tags=["React", "Go", "Bun"],
            ai_full_content="## 技术日报\n\n...",
            ai_duration=3000,
            ai_tokens_used=800,
            digest_date="2026-05-08",
            highlight="React 19 正式发布，带来全新编译器",
            sections=sections,
        )

        # 验证 task 字段
        task = await repo.get_task(task_id)
        assert task["ai_title"] == "技术日报 | 2026-05-08"
        assert task["digest_date"] == "2026-05-08"
        assert task["digest_highlight"] == "React 19 正式发布，带来全新编译器"
        assert json.loads(task["ai_tags"]) == ["React", "Go", "Bun"]

        # 验证结构化 sections
        db_sections = await repo.get_digest_sections(task_id)
        assert len(db_sections) == 2

        hot_section = db_sections[0]
        assert hot_section["category"] == "hot_trend"
        assert hot_section["category_name"] == "热点动态"
        assert len(hot_section["items"]) == 2
        assert hot_section["items"][0]["title"] == "React 19 正式发布"
        assert hot_section["items"][0]["one_liner"] == "全新编译器"

        oss_section = db_sections[1]
        assert oss_section["category"] == "open_source"
        assert len(oss_section["items"]) == 1

    @pytest.mark.asyncio
    async def test_reset_digest_task_clears_sections(self, patched_repo):
        """重试日报任务应清除结构化数据"""
        repo = patched_repo

        task_id = await repo.create_task(task_type="digest", keyword="2026-05-08")
        await repo.save_digest_results(
            task_id, "Title", "Summary", ["t1"], "Content", 100, 50,
            "2026-05-08", "highlight",
            [{"category": "hot_trend", "category_name": "热点", "emoji": "🔥", "items": []}],
        )
        await repo.fail_task(task_id, "AI failed")

        # 重试前有 sections
        sections = await repo.get_digest_sections(task_id)
        assert len(sections) == 1

        # 重试后清除
        await repo.reset_task_for_retry(task_id)
        task = await repo.get_task(task_id)
        assert task["status"] == TaskStatus.PENDING
        assert task["digest_date"] is None
        assert task["digest_highlight"] is None

        sections = await repo.get_digest_sections(task_id)
        assert len(sections) == 0

    @pytest.mark.asyncio
    async def test_save_digest_replaces_old_sections(self, patched_repo):
        """重新整理日报应替换旧 sections"""
        repo = patched_repo

        task_id = await repo.create_task(task_type="digest", keyword="2026-05-08")

        # 第一次保存
        await repo.save_digest_results(
            task_id, "Title v1", "Summary", ["t1"], "Content", 100, 50,
            "2026-05-08", "highlight v1",
            [{"category": "hot_trend", "category_name": "热点", "emoji": "🔥", "items": []}],
        )
        assert len(await repo.get_digest_sections(task_id)) == 1

        # 第二次保存（重新整理）
        await repo.save_digest_results(
            task_id, "Title v2", "Summary", ["t2"], "Content", 200, 80,
            "2026-05-08", "highlight v2",
            [
                {"category": "hot_trend", "category_name": "热点", "emoji": "🔥", "items": []},
                {"category": "open_source", "category_name": "开源", "emoji": "🌟", "items": []},
            ],
        )

        task = await repo.get_task(task_id)
        assert task["ai_title"] == "Title v2"
        assert task["digest_highlight"] == "highlight v2"

        sections = await repo.get_digest_sections(task_id)
        assert len(sections) == 2  # 替换而非追加


# ============== Digest Category Inference ==============

class TestDigestCategoryInference:
    def test_creative_category_detected(self):
        """creative 分类应被正确识别"""
        from standalone.task_executor import infer_category
        assert infer_category("https://example.com", "一个有趣的创意项目") == "creative"
        assert infer_category("https://hackathon.io/project", "") == "creative"

    def test_all_categories_reachable(self):
        """所有 6 个分类都应可达"""
        from standalone.task_executor import infer_category
        from ai.organizer import DIGEST_CATEGORY_MAP

        test_cases = {
            "open_source": ("https://github.com/user/repo", ""),
            "paper": ("https://arxiv.org/abs/2401", ""),
            "dev_tool": ("https://example.com", "New tool for developers"),
            "hot_trend": ("https://news.example.com", "tech news today"),
            "creative": ("https://example.com", "创意编程实验"),
            "tech_article": ("https://blog.example.com/post", "Spring Boot 教程"),
        }

        for expected_cat, (url, title) in test_cases.items():
            assert infer_category(url, title) == expected_cat, \
                f"Expected {expected_cat} for ({url}, {title})"
            assert expected_cat in DIGEST_CATEGORY_MAP


# ============== Scheduler ==============

class TestScheduler:
    def test_parse_cron_valid(self):
        from standalone.scheduler import parse_cron
        result = parse_cron("0 8 * * 1-5")
        assert result == {"minute": "0", "hour": "8", "day": "*", "month": "*", "day_of_week": "1-5"}

    def test_parse_cron_invalid(self):
        from standalone.scheduler import parse_cron
        import pytest
        with pytest.raises(ValueError):
            parse_cron("invalid")
        with pytest.raises(ValueError):
            parse_cron("0 8 *")

    def test_scheduler_status_when_not_started(self):
        from standalone.scheduler import get_scheduler_status
        status = get_scheduler_status()
        assert status["running"] is False
        assert "cron" in status

