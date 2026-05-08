"""数据库迁移 + Repository 测试"""

import pytest
import sqlite3
import json
from standalone.models import TaskStatus, PageStatus


# ============== Migration ==============

class TestMigration:
    @pytest.mark.asyncio
    async def test_fresh_db_has_all_ai_columns(self, mem_db):
        cursor = await mem_db.execute("PRAGMA table_info(crawl_task)")
        columns = {row[1] for row in await cursor.fetchall()}
        ai_cols = [
            "ai_template", "ai_title", "ai_summary", "ai_key_points",
            "ai_tags", "ai_category", "ai_full_content", "ai_duration",
            "ai_tokens_used", "ai_error_message", "ai_search_metadata",
        ]
        for col in ai_cols:
            assert col in columns, f"Missing column: {col}"

    @pytest.mark.asyncio
    async def test_crawl_page_table_exists(self, mem_db):
        cursor = await mem_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='crawl_page'"
        )
        row = await cursor.fetchone()
        assert row is not None


# ============== Task CRUD ==============

class TestTaskCrud:
    @pytest.mark.asyncio
    async def test_create_and_get_task(self, mem_db):
        mem_db.row_factory = sqlite3.Row
        await mem_db.execute(
            """INSERT INTO crawl_task
               (task_type, source_url, keyword, ai_template, status)
               VALUES (?, ?, ?, ?, ?)""",
            ("keyword", None, "docker", "tech_summary", TaskStatus.PENDING)
        )
        await mem_db.commit()
        task_id = (await (await mem_db.execute("SELECT last_insert_rowid()")).fetchone())[0]

        cursor = await mem_db.execute("SELECT * FROM crawl_task WHERE id = ?", (task_id,))
        row = dict(await cursor.fetchone())
        assert row["task_type"] == "keyword"
        assert row["keyword"] == "docker"
        assert row["ai_template"] == "tech_summary"
        assert row["status"] == TaskStatus.PENDING

    @pytest.mark.asyncio
    async def test_status_transitions(self, mem_db):
        await mem_db.execute(
            "INSERT INTO crawl_task (task_type, status) VALUES ('single', ?)",
            (TaskStatus.PENDING,)
        )
        await mem_db.commit()
        task_id = (await (await mem_db.execute("SELECT last_insert_rowid()")).fetchone())[0]

        # PENDING → CRAWLING
        await mem_db.execute(
            "UPDATE crawl_task SET status = ? WHERE id = ?",
            (TaskStatus.CRAWLING, task_id)
        )
        await mem_db.commit()

        # CRAWLING → PROCESSING
        await mem_db.execute(
            "UPDATE crawl_task SET status = ? WHERE id = ?",
            (TaskStatus.PROCESSING, task_id)
        )
        await mem_db.commit()

        # PROCESSING → COMPLETED
        await mem_db.execute(
            "UPDATE crawl_task SET status = ? WHERE id = ?",
            (TaskStatus.COMPLETED, task_id)
        )
        await mem_db.commit()

        cursor = await mem_db.execute("SELECT status FROM crawl_task WHERE id = ?", (task_id,))
        status = (await cursor.fetchone())[0]
        assert status == TaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_failed_task(self, mem_db):
        await mem_db.execute(
            "INSERT INTO crawl_task (task_type, status, error_message) VALUES ('single', ?, ?)",
            (TaskStatus.FAILED, "Connection timeout")
        )
        await mem_db.commit()
        task_id = (await (await mem_db.execute("SELECT last_insert_rowid()")).fetchone())[0]

        cursor = await mem_db.execute("SELECT status, error_message FROM crawl_task WHERE id = ?", (task_id,))
        row = await cursor.fetchone()
        assert row[0] == TaskStatus.FAILED
        assert row[1] == "Connection timeout"


# ============== AI Results ==============

class TestAiResults:
    @pytest.mark.asyncio
    async def test_save_ai_results(self, mem_db):
        await mem_db.execute(
            "INSERT INTO crawl_task (task_type, status) VALUES ('single', ?)",
            (TaskStatus.PROCESSING,)
        )
        await mem_db.commit()
        task_id = (await (await mem_db.execute("SELECT last_insert_rowid()")).fetchone())[0]

        key_points = ["point 1", "point 2"]
        tags = ["java", "spring"]

        await mem_db.execute(
            """UPDATE crawl_task SET
               ai_title = ?, ai_summary = ?, ai_key_points = ?,
               ai_tags = ?, ai_category = ?, ai_full_content = ?,
               ai_duration = ?, ai_tokens_used = ?,
               status = ?
               WHERE id = ?""",
            ("Spring Guide", "A summary",
             json.dumps(key_points, ensure_ascii=False),
             json.dumps(tags, ensure_ascii=False),
             "后端开发", "Full content here",
             1234, 567,
             TaskStatus.COMPLETED,
             task_id)
        )
        await mem_db.commit()

        cursor = await mem_db.execute("SELECT * FROM crawl_task WHERE id = ?", (task_id,))
        row = dict(await cursor.fetchone())

        assert row["ai_title"] == "Spring Guide"
        assert json.loads(row["ai_key_points"]) == ["point 1", "point 2"]
        assert json.loads(row["ai_tags"]) == ["java", "spring"]
        assert row["ai_category"] == "后端开发"
        assert row["ai_duration"] == 1234
        assert row["ai_tokens_used"] == 567
        assert row["status"] == TaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_save_ai_search_metadata(self, mem_db):
        await mem_db.execute(
            "INSERT INTO crawl_task (task_type, status) VALUES ('keyword', ?)",
            (TaskStatus.CRAWLING,)
        )
        await mem_db.commit()
        task_id = (await (await mem_db.execute("SELECT last_insert_rowid()")).fetchone())[0]

        metadata = {
            "originalKeyword": "docker",
            "optimizedKeyword": "docker 容器",
            "searchVariants": ["docker 容器", "docker tutorial"],
        }

        await mem_db.execute(
            "UPDATE crawl_task SET ai_search_metadata = ? WHERE id = ?",
            (json.dumps(metadata, ensure_ascii=False), task_id)
        )
        await mem_db.commit()

        cursor = await mem_db.execute(
            "SELECT ai_search_metadata FROM crawl_task WHERE id = ?", (task_id,)
        )
        raw = (await cursor.fetchone())[0]
        parsed = json.loads(raw)
        assert parsed["originalKeyword"] == "docker"
        assert len(parsed["searchVariants"]) == 2

    @pytest.mark.asyncio
    async def test_reset_for_retry_clears_ai(self, mem_db):
        await mem_db.execute(
            """INSERT INTO crawl_task
               (task_type, status, ai_title, ai_summary, ai_key_points, ai_tags,
                ai_category, ai_full_content, ai_duration, ai_tokens_used,
                ai_search_metadata, error_message, crawl_duration, total_word_count)
               VALUES ('keyword', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (TaskStatus.FAILED, "Title", "Summary", '["a"]', '["b"]',
             "cat", "content", 100, 50, '{"k":"v"}', "error", 200, 300)
        )
        await mem_db.commit()
        task_id = (await (await mem_db.execute("SELECT last_insert_rowid()")).fetchone())[0]

        await mem_db.execute(
            """UPDATE crawl_task SET status = ?, error_message = NULL,
               crawl_duration = NULL, total_word_count = NULL,
               completed_pages = 0,
               ai_title = NULL, ai_summary = NULL, ai_key_points = NULL,
               ai_tags = NULL, ai_category = NULL, ai_full_content = NULL,
               ai_duration = NULL, ai_tokens_used = NULL, ai_error_message = NULL,
               ai_search_metadata = NULL
               WHERE id = ?""",
            (TaskStatus.PENDING, task_id)
        )
        await mem_db.commit()

        cursor = await mem_db.execute("SELECT * FROM crawl_task WHERE id = ?", (task_id,))
        row = dict(await cursor.fetchone())

        assert row["status"] == TaskStatus.PENDING
        assert row["ai_title"] is None
        assert row["ai_summary"] is None
        assert row["ai_search_metadata"] is None
        assert row["error_message"] is None
        assert row["crawl_duration"] is None


# ============== Page CRUD ==============

class TestPageCrud:
    @pytest.mark.asyncio
    async def test_save_and_query_pages(self, mem_db):
        await mem_db.execute(
            "INSERT INTO crawl_task (task_type, status) VALUES ('single', ?)",
            (TaskStatus.CRAWLING,)
        )
        await mem_db.commit()
        task_id = (await (await mem_db.execute("SELECT last_insert_rowid()")).fetchone())[0]

        await mem_db.execute(
            """INSERT INTO crawl_page
               (task_id, url, page_title, crawl_status, word_count, url_hash, sort_order)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (task_id, "https://example.com", "Example", PageStatus.COMPLETED, 100, "abc123", 0)
        )
        await mem_db.commit()

        cursor = await mem_db.execute(
            "SELECT * FROM crawl_page WHERE task_id = ? ORDER BY sort_order",
            (task_id,)
        )
        rows = await cursor.fetchall()
        assert len(rows) == 1
        assert dict(rows[0])["page_title"] == "Example"

    @pytest.mark.asyncio
    async def test_cascade_delete_pages(self, mem_db):
        await mem_db.execute("PRAGMA foreign_keys=ON")
        await mem_db.execute(
            "INSERT INTO crawl_task (task_type, status) VALUES ('single', ?)",
            (TaskStatus.COMPLETED,)
        )
        await mem_db.commit()
        task_id = (await (await mem_db.execute("SELECT last_insert_rowid()")).fetchone())[0]

        await mem_db.execute(
            """INSERT INTO crawl_page
               (task_id, url, crawl_status, url_hash, sort_order)
               VALUES (?, ?, ?, ?, ?)""",
            (task_id, "https://example.com", PageStatus.COMPLETED, "abc", 0)
        )
        await mem_db.commit()

        # Delete pages first, then task
        await mem_db.execute("DELETE FROM crawl_page WHERE task_id = ?", (task_id,))
        await mem_db.execute("DELETE FROM crawl_task WHERE id = ?", (task_id,))
        await mem_db.commit()

        cursor = await mem_db.execute("SELECT COUNT(*) FROM crawl_page WHERE task_id = ?", (task_id,))
        count = (await cursor.fetchone())[0]
        assert count == 0


# ============== Models ==============

class TestModels:
    def test_task_status_labels(self):
        assert TaskStatus.label(TaskStatus.PENDING) == "待处理"
        assert TaskStatus.label(TaskStatus.CRAWLING) == "爬取中"
        assert TaskStatus.label(TaskStatus.PROCESSING) == "AI整理中"
        assert TaskStatus.label(TaskStatus.COMPLETED) == "已完成"
        assert TaskStatus.label(TaskStatus.FAILED) == "失败"

    def test_is_terminal(self):
        assert TaskStatus.is_terminal(TaskStatus.COMPLETED) is True
        assert TaskStatus.is_terminal(TaskStatus.FAILED) is True
        assert TaskStatus.is_terminal(TaskStatus.PENDING) is False
        assert TaskStatus.is_terminal(TaskStatus.PROCESSING) is False

    def test_is_active(self):
        assert TaskStatus.is_active(TaskStatus.PENDING) is True
        assert TaskStatus.is_active(TaskStatus.CRAWLING) is True
        assert TaskStatus.is_active(TaskStatus.PROCESSING) is True
        assert TaskStatus.is_active(TaskStatus.COMPLETED) is False
