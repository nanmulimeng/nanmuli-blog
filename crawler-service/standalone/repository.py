"""独立模式数据访问层（CRUD）"""

import json
import sqlite3
import hashlib
import logging
from typing import Optional

from standalone.db import get_db
from standalone.models import TaskStatus, PageStatus

logger = logging.getLogger(__name__)


def _hash_url(url: str) -> str:
    """URL 标准化 SHA-256 哈希"""
    normalized = url.lower().strip()
    normalized = normalized.rstrip("/")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _row_to_dict(row) -> Optional[dict]:
    """将 sqlite3.Row 转为 dict"""
    if row is None:
        return None
    return dict(row)


# ============== Task CRUD ==============

async def create_task(task_type: str, source_url: str = None, keyword: str = None,
                      search_engine: str = "bing", max_depth: int = 1,
                      max_pages: int = 10) -> int:
    """创建任务，返回 task_id"""
    async with get_db() as db:
        db.row_factory = sqlite3.Row
        await db.execute(
            """INSERT INTO crawl_task (task_type, source_url, keyword, search_engine, max_depth, max_pages)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (task_type, source_url, keyword, search_engine, max_depth, max_pages)
        )
        await db.commit()
        cursor = await db.execute("SELECT last_insert_rowid()")
        row = await cursor.fetchone()
        return row[0]


async def get_task(task_id: int) -> Optional[dict]:
    async with get_db() as db:
        db.row_factory = sqlite3.Row
        cursor = await db.execute("SELECT * FROM crawl_task WHERE id = ?", (task_id,))
        return _row_to_dict(await cursor.fetchone())


async def list_tasks(status: int = None, task_type: str = None,
                     page: int = 1, size: int = 10) -> tuple[list[dict], int]:
    """返回 (records, total)"""
    async with get_db() as db:
        db.row_factory = sqlite3.Row

        where_clauses = []
        params = []
        if status is not None:
            where_clauses.append("status = ?")
            params.append(status)
        if task_type:
            where_clauses.append("task_type = ?")
            params.append(task_type)

        where = " AND ".join(where_clauses) if where_clauses else "1=1"

        count_cursor = await db.execute(f"SELECT COUNT(*) FROM crawl_task WHERE {where}", params)
        total = (await count_cursor.fetchone())[0]

        offset = (page - 1) * size
        cursor = await db.execute(
            f"SELECT * FROM crawl_task WHERE {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params + [size, offset]
        )
        rows = await cursor.fetchall()
        return [_row_to_dict(r) for r in rows], total


async def update_task_status(task_id: int, status: int, error_message: str = None):
    async with get_db() as db:
        await db.execute(
            "UPDATE crawl_task SET status = ?, error_message = ?, updated_at = datetime('now') WHERE id = ?",
            (status, error_message, task_id)
        )
        await db.commit()


async def complete_task(task_id: int, total_pages: int, completed_pages: int,
                        crawl_duration: int, total_word_count: int):
    async with get_db() as db:
        await db.execute(
            """UPDATE crawl_task
               SET status = ?, total_pages = ?, completed_pages = ?,
                   crawl_duration = ?, total_word_count = ?, updated_at = datetime('now')
               WHERE id = ?""",
            (TaskStatus.COMPLETED, total_pages, completed_pages, crawl_duration, total_word_count, task_id)
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
        await db.execute("DELETE FROM crawl_page WHERE task_id = ?", (task_id,))
        await db.execute("DELETE FROM crawl_task WHERE id = ?", (task_id,))
        await db.commit()


async def reset_task_for_retry(task_id: int):
    """重置失败任务为待处理状态"""
    async with get_db() as db:
        await db.execute("DELETE FROM crawl_page WHERE task_id = ?", (task_id,))
        await db.execute(
            """UPDATE crawl_task SET status = ?, error_message = NULL,
               crawl_duration = NULL, total_word_count = NULL,
               completed_pages = 0, updated_at = datetime('now')
               WHERE id = ?""",
            (TaskStatus.PENDING, task_id)
        )
        await db.commit()


# ============== Page CRUD ==============

async def save_pages(task_id: int, results: list) -> int:
    """批量保存爬取结果页面，返回总字数"""
    total_words = 0
    async with get_db() as db:
        for i, r in enumerate(results):
            rdict = r.to_dict() if hasattr(r, 'to_dict') else r
            status = PageStatus.COMPLETED if rdict.get("success") else PageStatus.FAILED
            metadata_json = json.dumps(rdict.get("metadata", {}), ensure_ascii=False) if rdict.get("metadata") else None
            wc = rdict.get("word_count", 0)
            total_words += wc

            await db.execute(
                """INSERT INTO crawl_page
                   (task_id, url, page_title, raw_markdown, page_metadata,
                    crawl_status, error_message, crawl_duration, word_count,
                    url_hash, sort_order, depth, search_rank)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
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
                )
            )
        await db.commit()
    return total_words


async def get_pages_by_task(task_id: int) -> list[dict]:
    async with get_db() as db:
        db.row_factory = sqlite3.Row
        cursor = await db.execute(
            "SELECT * FROM crawl_page WHERE task_id = ? ORDER BY sort_order",
            (task_id,)
        )
        rows = await cursor.fetchall()
        return [_row_to_dict(r) for r in rows]


async def exists_url_hash(url_hash: str) -> bool:
    async with get_db() as db:
        cursor = await db.execute("SELECT 1 FROM crawl_page WHERE url_hash = ? LIMIT 1", (url_hash,))
        return await cursor.fetchone() is not None


# ============== Stats ==============

async def get_stats() -> dict:
    async with get_db() as db:
        total = (await (await db.execute("SELECT COUNT(*) FROM crawl_task")).fetchone())[0]
        completed = (await (await db.execute("SELECT COUNT(*) FROM crawl_task WHERE status = ?", (TaskStatus.COMPLETED,))).fetchone())[0]
        failed = (await (await db.execute("SELECT COUNT(*) FROM crawl_task WHERE status = ?", (TaskStatus.FAILED,))).fetchone())[0]
        pending = (await (await db.execute("SELECT COUNT(*) FROM crawl_task WHERE status IN (?, ?)", (TaskStatus.PENDING, TaskStatus.CRAWLING))).fetchone())[0]
        total_words = (await (await db.execute("SELECT COALESCE(SUM(total_word_count), 0) FROM crawl_task")).fetchone())[0]
    return {
        "total_tasks": total,
        "completed_tasks": completed,
        "failed_tasks": failed,
        "pending_tasks": pending,
        "total_words": total_words,
    }
