"""独立模式数据访问层（CRUD）"""

import json
import hashlib
import logging
from typing import Optional

from standalone.db import get_db
from standalone.models import TaskStatus, PageStatus
from crawler.utils import normalize_url

logger = logging.getLogger(__name__)


def _hash_url(url: str) -> str:
    """URL 标准化 + SHA-256 哈希"""
    normalized = normalize_url(url)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _row_to_dict(row) -> Optional[dict]:
    """将 sqlite3.Row 转为 dict"""
    if row is None:
        return None
    return dict(row)


# ============== Task CRUD ==============

async def create_task(
    task_type: str, source_url: str = None, keyword: str = None,
    search_engine: str = "bing", max_depth: int = 1,
    max_pages: int = 10, config_json: str = None,
    ai_template: str = "tech_summary"
) -> int:
    """创建任务，返回 task_id"""
    async with get_db() as db:

        await db.execute(
            """INSERT INTO crawl_task
               (task_type, source_url, keyword, search_engine, max_depth, max_pages,
                crawl_config, ai_template)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (task_type, source_url, keyword, search_engine, max_depth, max_pages,
             config_json, ai_template)
        )
        await db.commit()
        cursor = await db.execute("SELECT last_insert_rowid()")
        row = await cursor.fetchone()
        return row[0]


async def get_task(task_id: int) -> Optional[dict]:
    async with get_db() as db:

        cursor = await db.execute("SELECT * FROM crawl_task WHERE id = ?", (task_id,))
        return _row_to_dict(await cursor.fetchone())


async def list_tasks(status: int = None, task_type: str = None,
                     page: int = 1, size: int = 10) -> tuple[list[dict], int]:
    """返回 (records, total)"""
    async with get_db() as db:
        where_clauses = []
        params = []
        if status is not None:
            where_clauses.append("status = ?")
            params.append(status)
        if task_type:
            where_clauses.append("task_type = ?")
            params.append(task_type)

        where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        count_cursor = await db.execute(
            "SELECT COUNT(*) FROM crawl_task" + where_sql, params
        )
        total = (await count_cursor.fetchone())[0]

        offset = max(0, (page - 1) * size)
        cursor = await db.execute(
            "SELECT * FROM crawl_task" + where_sql + " ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params + [size, offset]
        )
        rows = await cursor.fetchall()
        return [_row_to_dict(r) for r in rows], total


async def get_digest_by_date(digest_date: str) -> dict | None:
    """按日期精确查询日报任务"""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM crawl_task WHERE task_type = 'digest' AND digest_date = ? ORDER BY created_at DESC LIMIT 1",
            (digest_date,)
        )
        row = await cursor.fetchone()
        return _row_to_dict(row) if row else None


async def get_latest_completed_digest() -> dict | None:
    """获取最近一条完成的日报任务"""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM crawl_task WHERE task_type = 'digest' AND status = 3 ORDER BY created_at DESC LIMIT 1"
        )
        row = await cursor.fetchone()
        return _row_to_dict(row) if row else None


async def get_digest_today_pending_or_running() -> list[dict]:
    """获取今日已有的活跃日报任务（PENDING/CRAWLING/PROCESSING，防并发 + 防重复）"""
    import datetime
    today = datetime.date.today().isoformat()
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM crawl_task WHERE task_type = 'digest' AND digest_date = ? AND status IN (?, ?, ?)",
            (today, TaskStatus.PENDING, TaskStatus.CRAWLING, TaskStatus.PROCESSING)
        )
        rows = await cursor.fetchall()
        return [_row_to_dict(r) for r in rows]


async def update_task_status(task_id: int, status: int, error_message: str = None):
    async with get_db() as db:
        await db.execute(
            "UPDATE crawl_task SET status = ?, error_message = ?, updated_at = datetime('now') WHERE id = ?",
            (status, error_message, task_id)
        )
        await db.commit()


async def update_task_progress(task_id: int, completed_pages: int):
    """更新爬取进度"""
    async with get_db() as db:
        await db.execute(
            "UPDATE crawl_task SET completed_pages = ?, updated_at = datetime('now') WHERE id = ?",
            (completed_pages, task_id)
        )
        await db.commit()


async def complete_crawl(task_id: int, total_pages: int, completed_pages: int,
                         crawl_duration: int, total_word_count: int):
    """爬取完成，更新统计（不改变状态，后续进入 AI 整理）"""
    async with get_db() as db:
        await db.execute(
            """UPDATE crawl_task
               SET total_pages = ?, completed_pages = ?,
                   crawl_duration = ?, total_word_count = ?,
                   updated_at = datetime('now')
               WHERE id = ?""",
            (total_pages, completed_pages, crawl_duration, total_word_count, task_id)
        )
        await db.commit()


async def complete_task(task_id: int):
    """任务全部完成（爬取+AI），标记 COMPLETED"""
    async with get_db() as db:
        await db.execute(
            "UPDATE crawl_task SET status = ?, updated_at = datetime('now') WHERE id = ?",
            (TaskStatus.COMPLETED, task_id)
        )
        await db.commit()


async def fail_task(task_id: int, error_message: str):
    async with get_db() as db:
        await db.execute(
            """UPDATE crawl_task SET status = ?, error_message = ?,
               updated_at = datetime('now') WHERE id = ?""",
            (TaskStatus.FAILED, error_message, task_id)
        )
        await db.commit()


async def delete_task(task_id: int):
    async with get_db() as db:
        # CASCADE 会自动删除 digest_section/digest_item，但显式删除更安全
        await db.execute("DELETE FROM crawl_page WHERE task_id = ?", (task_id,))
        await db.execute("DELETE FROM crawl_task WHERE id = ?", (task_id,))
        await db.commit()


async def reset_task_for_retry(task_id: int):
    """重置失败任务为待处理状态"""
    async with get_db() as db:
        await db.execute("DELETE FROM crawl_page WHERE task_id = ?", (task_id,))
        await db.execute("DELETE FROM digest_section WHERE task_id = ?", (task_id,))
        await db.execute(
            """UPDATE crawl_task SET status = ?, error_message = NULL,
               crawl_duration = NULL, total_word_count = NULL,
               completed_pages = 0,
               ai_title = NULL, ai_summary = NULL, ai_key_points = NULL,
               ai_tags = NULL, ai_category = NULL, ai_full_content = NULL,
               ai_duration = NULL, ai_tokens_used = NULL, ai_error_message = NULL,
               ai_search_metadata = NULL,
               digest_date = NULL, digest_highlight = NULL,
               updated_at = datetime('now')
               WHERE id = ?""",
            (TaskStatus.PENDING, task_id)
        )
        await db.commit()


# ============== AI Results ==============

async def save_ai_results(
    task_id: int,
    ai_title: str, ai_summary: str, ai_key_points: list[str],
    ai_tags: list[str], ai_category: str, ai_full_content: str,
    ai_duration: int, ai_tokens_used: int
):
    """保存 AI 整理结果"""
    async with get_db() as db:
        await db.execute(
            """UPDATE crawl_task SET
               ai_title = ?, ai_summary = ?, ai_key_points = ?,
               ai_tags = ?, ai_category = ?, ai_full_content = ?,
               ai_duration = ?, ai_tokens_used = ?,
               updated_at = datetime('now')
               WHERE id = ?""",
            (ai_title, ai_summary,
             json.dumps(ai_key_points, ensure_ascii=False) if ai_key_points else None,
             json.dumps(ai_tags, ensure_ascii=False) if ai_tags else None,
             ai_category, ai_full_content,
             ai_duration, ai_tokens_used, task_id)
        )
        await db.commit()


async def save_ai_error(task_id: int, error_message: str):
    """保存 AI 整理失败信息"""
    async with get_db() as db:
        await db.execute(
            "UPDATE crawl_task SET ai_error_message = ?, updated_at = datetime('now') WHERE id = ?",
            (error_message, task_id)
        )
        await db.commit()


async def save_ai_search_metadata(task_id: int, metadata: dict):
    """保存关键词搜索的 AI 元数据"""
    async with get_db() as db:
        await db.execute(
            "UPDATE crawl_task SET ai_search_metadata = ?, updated_at = datetime('now') WHERE id = ?",
            (json.dumps(metadata, ensure_ascii=False), task_id)
        )
        await db.commit()


# ============== Digest Results ==============

async def save_digest_results(
    task_id: int,
    ai_title: str, ai_summary: str, ai_tags: list[str],
    ai_full_content: str, ai_duration: int, ai_tokens_used: int,
    digest_date: str, highlight: str,
    sections: list[dict],
):
    """保存日报结构化结果（AI 通用字段 + sections/items）"""
    async with get_db() as db:
        # 1. 更新 crawl_task 通用字段
        await db.execute(
            """UPDATE crawl_task SET
               ai_title = ?, ai_summary = ?, ai_tags = ?,
               ai_full_content = ?, ai_duration = ?, ai_tokens_used = ?,
               digest_date = ?, digest_highlight = ?,
               updated_at = datetime('now')
               WHERE id = ?""",
            (ai_title, ai_summary,
             json.dumps(ai_tags, ensure_ascii=False) if ai_tags else None,
             ai_full_content, ai_duration, ai_tokens_used,
             digest_date, highlight,
             task_id)
        )

        # 2. 清除旧的 sections/items（重试场景）
        await db.execute("DELETE FROM digest_section WHERE task_id = ?", (task_id,))

        # 3. 插入 sections 和 items
        for sec_idx, sec in enumerate(sections):
            cursor = await db.execute(
                """INSERT INTO digest_section (task_id, category, category_name, emoji, sort_order)
                   VALUES (?, ?, ?, ?, ?)""",
                (task_id, sec.get("category", ""),
                 sec.get("category_name", ""), sec.get("emoji", ""), sec_idx)
            )
            section_id = cursor.lastrowid

            items = sec.get("items", [])
            item_rows = [
                (section_id,
                 item.get("title", ""), item.get("one_liner", ""),
                 item.get("source_url", ""), item.get("source_name", ""),
                 item.get("page_id"), item_idx)
                for item_idx, item in enumerate(items)
            ]
            if item_rows:
                await db.executemany(
                    """INSERT INTO digest_item
                       (section_id, title, one_liner, source_url, source_name, page_id, sort_order)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    item_rows
                )

        await db.commit()


async def get_digest_sections(task_id: int) -> list[dict]:
    """获取日报结构化数据（sections + items）"""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM digest_section WHERE task_id = ? ORDER BY sort_order",
            (task_id,)
        )
        sections = []
        for sec_row in await cursor.fetchall():
            sec = _row_to_dict(sec_row)
            item_cursor = await db.execute(
                "SELECT * FROM digest_item WHERE section_id = ? ORDER BY sort_order",
                (sec["id"],)
            )
            sec["items"] = [_row_to_dict(r) for r in await item_cursor.fetchall()]
            sections.append(sec)
        return sections


# ============== Page CRUD ==============

async def save_pages(task_id: int, results: list) -> int:
    """批量保存爬取结果页面，返回总字数"""
    total_words = 0
    rows = []
    for i, r in enumerate(results):
        rdict = r.to_dict() if hasattr(r, 'to_dict') else r
        status = PageStatus.COMPLETED if rdict.get("success") else PageStatus.FAILED
        metadata_json = json.dumps(rdict.get("metadata", {}), ensure_ascii=False) if rdict.get("metadata") else None
        wc = rdict.get("word_count", 0)
        total_words += wc

        rows.append((
            task_id,
            rdict.get("url", ""),
            rdict.get("title"),
            rdict.get("markdown"),
            metadata_json,
            status,
            rdict.get("error_message"),
            rdict.get("crawl_time_ms"),
            wc,
            _hash_url(rdict.get("url", "")),
            i,
            rdict.get("depth", 0),
            rdict.get("search_rank", 0),
        ))

    async with get_db() as db:
        await db.execute("BEGIN")
        try:
            await db.executemany(
                """INSERT INTO crawl_page
                   (task_id, url, page_title, raw_markdown, page_metadata,
                    crawl_status, error_message, crawl_duration, word_count,
                    url_hash, sort_order, depth, search_rank)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                rows
            )
            await db.commit()
        except Exception:
            await db.execute("ROLLBACK")
            raise
    return total_words


async def get_pages_by_task(task_id: int) -> list[dict]:
    async with get_db() as db:

        cursor = await db.execute(
            "SELECT * FROM crawl_page WHERE task_id = ? ORDER BY sort_order",
            (task_id,)
        )
        rows = await cursor.fetchall()
        return [_row_to_dict(r) for r in rows]


# ============== Stats ==============

async def get_stats() -> dict:
    async with get_db() as db:
        cursor = await db.execute("""
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN status = ? THEN 1 ELSE 0 END) AS completed,
                   SUM(CASE WHEN status = ? THEN 1 ELSE 0 END) AS failed,
                   SUM(CASE WHEN status IN (?, ?, ?) THEN 1 ELSE 0 END) AS pending,
                   COALESCE(SUM(total_word_count), 0) AS total_words
            FROM crawl_task
        """, (TaskStatus.COMPLETED, TaskStatus.FAILED,
              TaskStatus.PENDING, TaskStatus.CRAWLING, TaskStatus.PROCESSING))
        row = await cursor.fetchone()
    return {
        "total_tasks": row["total"],
        "completed_tasks": row["completed"],
        "failed_tasks": row["failed"],
        "pending_tasks": row["pending"],
        "total_words": row["total_words"],
    }
