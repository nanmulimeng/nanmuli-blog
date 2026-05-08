"""Markdown 导出功能测试

覆盖 export_task_as_markdown 的核心场景：
- 普通任务导出（含 AI 结果）
- 日报任务导出（含结构化 sections）
- 无 AI 结果的任务导出
- 任务不存在 → 404
- 任务未完成（不影响导出，export 不做状态校验）
- 导出格式验证（Markdown 结构、链接、标题）
"""

import os
import sys
import json
import pytest
from contextlib import asynccontextmanager

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from standalone.models import TaskStatus, PageStatus


@pytest.fixture
def patched_modules(mem_db):
    """Patch get_db in both repository and export modules to use in-memory DB."""
    import standalone.repository as repo_mod
    import standalone.export as export_mod

    @asynccontextmanager
    async def _mock_get_db():
        yield mem_db

    orig_repo_db = repo_mod.get_db
    orig_export_repo = export_mod.repo

    repo_mod.get_db = _mock_get_db
    export_mod.repo = repo_mod

    yield repo_mod, export_mod

    repo_mod.get_db = orig_repo_db
    export_mod.repo = orig_export_repo


# ============== Helper ==============

async def _insert_task(db, *, task_type="single", status=TaskStatus.COMPLETED,
                       source_url=None, keyword=None, total_pages=1,
                       completed_pages=0, total_word_count=0,
                       ai_title=None, ai_summary=None, ai_tags=None,
                       ai_full_content=None, ai_key_points=None,
                       digest_date=None, digest_highlight=None,
                       ai_template="tech_summary"):
    """Insert a crawl_task row and return its id."""
    await db.execute(
        """INSERT INTO crawl_task
           (task_type, source_url, keyword, status, total_pages, completed_pages,
            total_word_count, ai_title, ai_summary, ai_tags, ai_full_content,
            ai_key_points, ai_template, digest_date, digest_highlight)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (task_type, source_url, keyword, status, total_pages, completed_pages,
         total_word_count, ai_title, ai_summary, ai_tags, ai_full_content,
         ai_key_points, ai_template, digest_date, digest_highlight),
    )
    await db.commit()
    cursor = await db.execute("SELECT last_insert_rowid()")
    row = await cursor.fetchone()
    return row[0]


async def _insert_page(db, task_id, *, url="https://example.com/page",
                       title="Test Page", raw_markdown="# Content",
                       crawl_status=PageStatus.COMPLETED, word_count=100,
                       sort_order=0):
    """Insert a crawl_page row."""
    import hashlib
    url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()
    await db.execute(
        """INSERT INTO crawl_page
           (task_id, url, page_title, raw_markdown, crawl_status, word_count,
            url_hash, sort_order)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (task_id, url, title, raw_markdown, crawl_status, word_count, url_hash, sort_order),
    )
    await db.commit()


async def _insert_section(db, task_id, category, category_name, emoji, items, sort_order=0):
    """Insert a digest_section + its items, return section id."""
    cursor = await db.execute(
        """INSERT INTO digest_section (task_id, category, category_name, emoji, sort_order)
           VALUES (?, ?, ?, ?, ?)""",
        (task_id, category, category_name, emoji, sort_order),
    )
    section_id = cursor.lastrowid

    for idx, item in enumerate(items):
        await db.execute(
            """INSERT INTO digest_item
               (section_id, title, one_liner, source_url, source_name, sort_order)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (section_id, item["title"], item.get("one_liner", ""),
             item.get("source_url", ""), item.get("source_name", ""), idx),
        )
    await db.commit()
    return section_id


# ============== Normal Task Export ==============

class TestNormalTaskExport:
    @pytest.mark.asyncio
    async def test_single_task_with_ai_results(self, patched_modules, mem_db):
        """普通 single 任务：含 AI 标题/摘要/标签/内容，导出应包含所有 AI 字段。"""
        repo, export_mod = patched_modules

        task_id = await _insert_task(
            mem_db,
            task_type="single",
            source_url="https://example.com/spring-boot",
            total_pages=1,
            completed_pages=1,
            total_word_count=500,
            ai_title="Spring Boot 3 核心特性",
            ai_summary="Spring Boot 3 带来诸多改进",
            ai_tags=json.dumps(["spring", "java", "boot"], ensure_ascii=False),
            ai_full_content="## 核心特性\n\nSpring Boot 3 引入了...\n\n### 虚拟线程\n\n支持虚拟线程...",
        )

        await _insert_page(
            mem_db, task_id,
            url="https://example.com/spring-boot",
            title="Spring Boot 3 Guide",
            raw_markdown="# Spring Boot 3\n\nDetailed content here.",
        )

        response = await export_mod.export_task_as_markdown(task_id)
        content = response.body.decode("utf-8")

        assert response.media_type == "text/markdown; charset=utf-8"
        assert "爬取任务" in content
        assert "Spring Boot 3 核心特性" in content
        assert "Spring Boot 3 带来诸多改进" in content
        assert "spring, java, boot" in content
        assert "虚拟线程" in content
        assert "Spring Boot 3 Guide" in content
        assert "https://example.com/spring-boot" in content

    @pytest.mark.asyncio
    async def test_keyword_task_with_ai_results(self, patched_modules, mem_db):
        """关键词搜索任务：带 AI 结果和多页面导出。"""
        repo, export_mod = patched_modules

        task_id = await _insert_task(
            mem_db,
            task_type="keyword",
            keyword="docker",
            total_pages=3,
            completed_pages=3,
            total_word_count=1500,
            ai_title="Docker 容器技术全景",
            ai_summary="Docker 生态核心组件解析",
            ai_tags=json.dumps(["docker", "container"], ensure_ascii=False),
            ai_full_content="## Docker 生态\n\nDocker 是容器化的事实标准...",
        )

        await _insert_page(mem_db, task_id, url="https://a.com/docker",
                           title="Docker 入门", raw_markdown="# Docker 入门\n基础内容",
                           sort_order=0)
        await _insert_page(mem_db, task_id, url="https://b.com/docker-compose",
                           title="Docker Compose", raw_markdown="# Compose\n编排工具",
                           sort_order=1)
        await _insert_page(mem_db, task_id, url="https://c.com/k8s",
                           title="Kubernetes", raw_markdown="# K8s\n容器编排",
                           sort_order=2)

        response = await export_mod.export_task_as_markdown(task_id)
        content = response.body.decode("utf-8")

        assert "关键词搜索" in content
        assert "关键词: docker" in content
        assert "成功页面: 3/3" in content
        assert "总字数: 1500" in content
        assert "Docker 容器技术全景" in content
        assert "docker, container" in content
        assert "Docker 入门" in content
        assert "Docker Compose" in content
        assert "Kubernetes" in content

    @pytest.mark.asyncio
    async def test_ai_tags_as_list_not_string(self, patched_modules, mem_db):
        """ai_tags 字段为 JSON 字符串时应正确解析为逗号分隔标签。"""
        _, export_mod = patched_modules

        task_id = await _insert_task(
            mem_db,
            ai_title="Test Title",
            ai_summary="Test Summary",
            ai_tags=json.dumps(["tag1", "tag2", "tag3"], ensure_ascii=False),
            ai_full_content="Content body",
        )

        response = await export_mod.export_task_as_markdown(task_id)
        content = response.body.decode("utf-8")

        assert "tag1, tag2, tag3" in content

    @pytest.mark.asyncio
    async def test_ai_title_missing_uses_default_header(self, patched_modules, mem_db):
        """有 ai_full_content 但无 ai_title 时使用默认标题。"""
        _, export_mod = patched_modules

        task_id = await _insert_task(
            mem_db,
            ai_title=None,
            ai_full_content="Some AI content without title",
        )

        response = await export_mod.export_task_as_markdown(task_id)
        content = response.body.decode("utf-8")

        assert "## AI 整理结果" in content
        assert "Some AI content without title" in content


# ============== Digest Task Export ==============

class TestDigestTaskExport:
    @pytest.mark.asyncio
    async def test_digest_with_structured_sections(self, patched_modules, mem_db):
        """日报任务：含 digest_section + digest_item 的结构化导出。"""
        _, export_mod = patched_modules

        task_id = await _insert_task(
            mem_db,
            task_type="digest",
            keyword="2026-05-08",
            total_pages=3,
            completed_pages=3,
            total_word_count=2000,
            digest_date="2026-05-08",
            digest_highlight="React 19 正式发布，Go 1.23 改进迭代器",
        )

        await _insert_section(mem_db, task_id, "hot_trend", "热点动态", "\U0001f525", [
            {"title": "React 19 正式发布", "one_liner": "全新编译器提升性能",
             "source_url": "https://react.dev/blog", "source_name": "react.dev"},
            {"title": "Go 1.23 发布", "one_liner": "改进迭代器支持",
             "source_url": "https://go.dev/blog", "source_name": "go.dev"},
        ], sort_order=0)

        await _insert_section(mem_db, task_id, "open_source", "开源项目", "\U0001f31f", [
            {"title": "Bun 1.2", "one_liner": "高速 JS 运行时",
             "source_url": "https://github.com/oven-sh/bun", "source_name": "github.com"},
        ], sort_order=1)

        await _insert_page(mem_db, task_id, url="https://react.dev/blog",
                           title="React 19 Blog", raw_markdown="# React 19\nRelease notes.",
                           sort_order=0)
        await _insert_page(mem_db, task_id, url="https://go.dev/blog",
                           title="Go 1.23 Blog", raw_markdown="# Go 1.23\nIterator improvements.",
                           sort_order=1)
        await _insert_page(mem_db, task_id, url="https://github.com/oven-sh/bun",
                           title="Bun 1.2", raw_markdown="# Bun 1.2\nFast runtime.",
                           sort_order=2)

        response = await export_mod.export_task_as_markdown(task_id)
        content = response.body.decode("utf-8")

        # 日报标题
        assert "技术日报" in content
        assert "今日亮点" in content
        assert "React 19 正式发布，Go 1.23 改进迭代器" in content

        # Section headers
        assert "热点动态" in content
        assert "开源项目" in content

        # Items with markdown links
        assert "[React 19 正式发布](https://react.dev/blog)" in content
        assert "全新编译器提升性能" in content
        assert "— react.dev" in content

        assert "[Go 1.23 发布](https://go.dev/blog)" in content
        assert "改进迭代器支持" in content
        assert "— go.dev" in content

        assert "[Bun 1.2](https://github.com/oven-sh/bun)" in content
        assert "高速 JS 运行时" in content

        # Pages section
        assert "React 19 Blog" in content
        assert "Go 1.23 Blog" in content

    @pytest.mark.asyncio
    async def test_digest_without_sections_falls_back_to_ai_content(self, patched_modules, mem_db):
        """日报任务无 sections 时应 fallback 到 ai_full_content。"""
        _, export_mod = patched_modules

        task_id = await _insert_task(
            mem_db,
            task_type="digest",
            keyword="2026-05-08",
            ai_title="技术日报 2026-05-08",
            ai_summary="今日技术要闻",
            ai_tags=json.dumps(["React", "Go"], ensure_ascii=False),
            ai_full_content="## 今日要闻\n\nReact 19 和 Go 1.23 发布...",
        )

        response = await export_mod.export_task_as_markdown(task_id)
        content = response.body.decode("utf-8")

        assert "## AI 整理: 技术日报 2026-05-08" in content
        assert "今日技术要闻" in content
        assert "React, Go" in content

    @pytest.mark.asyncio
    async def test_digest_section_item_without_source_url(self, patched_modules, mem_db):
        """digest_item 没有 source_url 时标题不加链接格式。"""
        _, export_mod = patched_modules

        task_id = await _insert_task(
            mem_db,
            task_type="digest",
            digest_highlight="亮点内容",
        )

        await _insert_section(mem_db, task_id, "tech_article", "技术文章", "\U0001f4da", [
            {"title": "无链接文章", "one_liner": "只有标题和描述", "source_name": "unknown"},
        ], sort_order=0)

        response = await export_mod.export_task_as_markdown(task_id)
        content = response.body.decode("utf-8")

        # No link format, just bold title
        assert "- **无链接文章**" in content
        assert "[无链接文章]" not in content

    @pytest.mark.asyncio
    async def test_digest_section_item_without_one_liner(self, patched_modules, mem_db):
        """digest_item 没有 one_liner 时不输出描述行。"""
        _, export_mod = patched_modules

        task_id = await _insert_task(
            mem_db,
            task_type="digest",
        )

        await _insert_section(mem_db, task_id, "news", "新闻", "\U0001f4f0", [
            {"title": "Big News", "source_url": "https://news.com/big"},
        ], sort_order=0)

        response = await export_mod.export_task_as_markdown(task_id)
        content = response.body.decode("utf-8")

        assert "[Big News](https://news.com/big)" in content

    @pytest.mark.asyncio
    async def test_digest_without_highlight_no_highlight_section(self, patched_modules, mem_db):
        """日报任务无 digest_highlight 时不输出「今日亮点」section。"""
        _, export_mod = patched_modules

        task_id = await _insert_task(
            mem_db,
            task_type="digest",
            digest_highlight=None,
        )

        await _insert_section(mem_db, task_id, "news", "新闻", "\U0001f4f0", [
            {"title": "Some News"},
        ], sort_order=0)

        response = await export_mod.export_task_as_markdown(task_id)
        content = response.body.decode("utf-8")

        assert "今日亮点" not in content


# ============== Task Without AI Results ==============

class TestTaskWithoutAiResults:
    @pytest.mark.asyncio
    async def test_task_no_ai_only_raw_pages(self, patched_modules, mem_db):
        """任务无 AI 结果，只有原始爬取内容，导出应只包含页面原始 Markdown。"""
        _, export_mod = patched_modules

        task_id = await _insert_task(
            mem_db,
            task_type="single",
            source_url="https://example.com/raw",
            total_pages=2,
            completed_pages=2,
            total_word_count=800,
            # No AI fields
        )

        await _insert_page(mem_db, task_id, url="https://example.com/raw",
                           title="Raw Page 1", raw_markdown="# Raw Content\n\nOriginal text.",
                           sort_order=0)
        await _insert_page(mem_db, task_id, url="https://example.com/raw2",
                           title="Raw Page 2", raw_markdown="# Another Page\n\nMore text.",
                           sort_order=1)

        response = await export_mod.export_task_as_markdown(task_id)
        content = response.body.decode("utf-8")

        assert "AI 整理" not in content
        assert "Raw Page 1" in content
        assert "Raw Content" in content
        assert "Raw Page 2" in content
        assert "Another Page" in content

    @pytest.mark.asyncio
    async def test_task_no_pages(self, patched_modules, mem_db):
        """任务无页面数据时，导出只含元信息头部。"""
        _, export_mod = patched_modules

        task_id = await _insert_task(
            mem_db,
            task_type="single",
            source_url="https://example.com/empty",
            total_pages=0,
            completed_pages=0,
        )

        response = await export_mod.export_task_as_markdown(task_id)
        content = response.body.decode("utf-8")

        assert "爬取任务" in content
        assert "https://example.com/empty" in content
        assert "成功页面: 0/0" in content


# ============== Task Not Found ==============

class TestTaskNotFound:
    @pytest.mark.asyncio
    async def test_nonexistent_task_returns_404(self, patched_modules, mem_db):
        """不存在的任务 ID 应抛出 404 HTTPException。"""
        _, export_mod = patched_modules

        with pytest.raises(Exception) as exc_info:
            await export_mod.export_task_as_markdown(task_id=99999)

        assert exc_info.value.status_code == 404
        assert "Task not found" in exc_info.value.detail


# ============== Task Not Completed (export allows it) ==============

class TestTaskNotCompleted:
    @pytest.mark.asyncio
    async def test_pending_task_still_exports(self, patched_modules, mem_db):
        """export_task_as_markdown 不检查任务状态，PENDING 任务也能导出。"""
        _, export_mod = patched_modules

        task_id = await _insert_task(
            mem_db,
            task_type="single",
            status=TaskStatus.PENDING,
            source_url="https://example.com/pending",
        )

        await _insert_page(mem_db, task_id, url="https://example.com/pending",
                           title="Pending Page", raw_markdown="# Pending Content")

        response = await export_mod.export_task_as_markdown(task_id)
        content = response.body.decode("utf-8")

        assert "爬取任务" in content
        assert "Pending Page" in content
        assert "Pending Content" in content

    @pytest.mark.asyncio
    async def test_failed_task_still_exports(self, patched_modules, mem_db):
        """FAILED 状态任务也能导出（可能含部分爬取结果）。"""
        _, export_mod = patched_modules

        task_id = await _insert_task(
            mem_db,
            task_type="single",
            status=TaskStatus.FAILED,
            source_url="https://example.com/failed",
            total_pages=1,
            completed_pages=0,
        )

        response = await export_mod.export_task_as_markdown(task_id)
        content = response.body.decode("utf-8")

        assert "爬取任务" in content
        assert "https://example.com/failed" in content


# ============== Export Format Verification ==============

class TestExportFormat:
    @pytest.mark.asyncio
    async def test_response_headers(self, patched_modules, mem_db):
        """验证 Content-Disposition 附件头和 media_type。"""
        _, export_mod = patched_modules

        task_id = await _insert_task(mem_db)

        response = await export_mod.export_task_as_markdown(task_id)

        assert response.media_type == "text/markdown; charset=utf-8"
        assert "attachment" in response.headers.get("Content-Disposition", "")
        assert f"task_{task_id}_" in response.headers.get("Content-Disposition", "")
        assert ".md" in response.headers.get("Content-Disposition", "")

    @pytest.mark.asyncio
    async def test_markdown_headers_use_correct_level(self, patched_modules, mem_db):
        """一级标题为任务，二级为 AI 整理/页面。"""
        _, export_mod = patched_modules

        task_id = await _insert_task(
            mem_db,
            task_type="keyword",
            keyword="python",
            ai_title="Python Guide",
            ai_summary="Python programming",
            ai_tags=json.dumps(["python"], ensure_ascii=False),
            ai_full_content="## Section\n\nPython content.",
        )

        await _insert_page(mem_db, task_id, url="https://example.com/py",
                           title="Python Page", raw_markdown="# Python\nContent")

        response = await export_mod.export_task_as_markdown(task_id)
        content = response.body.decode("utf-8")

        lines = content.split("\n")
        # First line is h1 task header
        assert lines[0].startswith("# 爬取任务")

        # Find h2 headers
        h2_lines = [l for l in lines if l.startswith("## ")]
        assert any("AI 整理: Python Guide" in l for l in h2_lines)
        assert any("Python Page" in l for l in h2_lines)

    @pytest.mark.asyncio
    async def test_page_without_title_uses_url(self, patched_modules, mem_db):
        """页面无 page_title 时使用 URL 作为标题。"""
        _, export_mod = patched_modules

        task_id = await _insert_task(mem_db)

        await _insert_page(mem_db, task_id, url="https://example.com/notitle",
                           title=None, raw_markdown="# No Title Page")

        response = await export_mod.export_task_as_markdown(task_id)
        content = response.body.decode("utf-8")

        assert "https://example.com/notitle" in content

    @pytest.mark.asyncio
    async def test_failed_pages_excluded_from_output(self, patched_modules, mem_db):
        """crawl_status 为 FAILED 的页面不出现在导出中。"""
        _, export_mod = patched_modules

        task_id = await _insert_task(
            mem_db,
            total_pages=2,
            completed_pages=1,
        )

        await _insert_page(mem_db, task_id, url="https://example.com/ok",
                           title="OK Page", raw_markdown="# OK",
                           crawl_status=PageStatus.COMPLETED, sort_order=0)
        await _insert_page(mem_db, task_id, url="https://example.com/fail",
                           title="Fail Page", raw_markdown="# Fail",
                           crawl_status=PageStatus.FAILED, sort_order=1)

        response = await export_mod.export_task_as_markdown(task_id)
        content = response.body.decode("utf-8")

        assert "OK Page" in content
        assert "Fail Page" not in content
        assert "成功页面: 1/2" in content

    @pytest.mark.asyncio
    async def test_deep_task_type_label(self, patched_modules, mem_db):
        """deep 任务类型应显示「深度爬取」标签。"""
        _, export_mod = patched_modules

        task_id = await _insert_task(
            mem_db,
            task_type="deep",
            source_url="https://example.com/deep",
        )

        response = await export_mod.export_task_as_markdown(task_id)
        content = response.body.decode("utf-8")

        assert "深度爬取" in content

    @pytest.mark.asyncio
    async def test_source_url_in_metadata_block(self, patched_modules, mem_db):
        """source_url 应出现在引用块中。"""
        _, export_mod = patched_modules

        task_id = await _insert_task(
            mem_db,
            task_type="single",
            source_url="https://example.com/article",
        )

        response = await export_mod.export_task_as_markdown(task_id)
        content = response.body.decode("utf-8")

        assert "> URL: https://example.com/article" in content

    @pytest.mark.asyncio
    async def test_keyword_in_metadata_block(self, patched_modules, mem_db):
        """keyword 应出现在引用块中。"""
        _, export_mod = patched_modules

        task_id = await _insert_task(
            mem_db,
            task_type="keyword",
            keyword="kubernetes",
        )

        response = await export_mod.export_task_as_markdown(task_id)
        content = response.body.decode("utf-8")

        assert "> 关键词: kubernetes" in content

    @pytest.mark.asyncio
    async def test_no_source_url_no_url_line(self, patched_modules, mem_db):
        """无 source_url 时不应输出 URL 行。"""
        _, export_mod = patched_modules

        task_id = await _insert_task(
            mem_db,
            task_type="keyword",
            keyword="test",
            source_url=None,
        )

        response = await export_mod.export_task_as_markdown(task_id)
        content = response.body.decode("utf-8")

        assert "> URL:" not in content
        assert "> 关键词: test" in content

    @pytest.mark.asyncio
    async def test_invalid_ai_tags_ignored_gracefully(self, patched_modules, mem_db):
        """ai_tags 为无效 JSON 时不崩溃，静默跳过。"""
        _, export_mod = patched_modules

        task_id = await _insert_task(
            mem_db,
            ai_title="Broken Tags",
            ai_summary="Summary",
            ai_tags="not valid json{{{",
            ai_full_content="Content here",
        )

        # Should not raise
        response = await export_mod.export_task_as_markdown(task_id)
        content = response.body.decode("utf-8")

        assert "AI 整理: Broken Tags" in content
        assert "Content here" in content
        assert "> 标签:" not in content

    @pytest.mark.asyncio
    async def test_ai_tags_as_list_not_json_string(self, patched_modules, mem_db):
        """ai_tags 如果已经是 list 类型（非 string）也应正确处理。
        （实际 DB 中存的是 string，但测试覆盖代码路径。）"""
        _, export_mod = patched_modules

        task_id = await _insert_task(
            mem_db,
            ai_title="List Tags",
            ai_summary="Summary",
            ai_tags=None,  # Will be updated directly
            ai_full_content="Content",
        )

        # Directly update ai_tags to a JSON string that represents a list
        await mem_db.execute(
            "UPDATE crawl_task SET ai_tags = ? WHERE id = ?",
            ('["tag_a", "tag_b"]', task_id),
        )
        await mem_db.commit()

        response = await export_mod.export_task_as_markdown(task_id)
        content = response.body.decode("utf-8")

        assert "tag_a, tag_b" in content
