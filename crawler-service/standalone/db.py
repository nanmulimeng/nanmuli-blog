"""SQLite 数据库连接管理 + DDL"""

import os
import aiosqlite
import logging
from contextlib import asynccontextmanager
from config import settings

logger = logging.getLogger(__name__)

DDL = """
CREATE TABLE IF NOT EXISTS crawl_task (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    task_type       TEXT NOT NULL DEFAULT 'single',
    source_url      TEXT,
    keyword         TEXT,
    search_engine   TEXT DEFAULT 'bing',
    max_depth       INTEGER DEFAULT 1,
    max_pages       INTEGER DEFAULT 10,
    crawl_config    TEXT,
    status          INTEGER NOT NULL DEFAULT 0,
    error_message   TEXT,
    total_pages     INTEGER DEFAULT 1,
    completed_pages INTEGER DEFAULT 0,
    crawl_duration  INTEGER,
    total_word_count INTEGER,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_task_status ON crawl_task(status);
CREATE INDEX IF NOT EXISTS idx_task_created ON crawl_task(created_at DESC);

CREATE TABLE IF NOT EXISTS crawl_page (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id         INTEGER NOT NULL REFERENCES crawl_task(id) ON DELETE CASCADE,
    url             TEXT NOT NULL,
    page_title      TEXT,
    raw_markdown    TEXT,
    page_metadata   TEXT,
    crawl_status    INTEGER DEFAULT 0,
    error_message   TEXT,
    crawl_duration  INTEGER,
    word_count      INTEGER,
    url_hash        TEXT NOT NULL,
    sort_order      INTEGER DEFAULT 0,
    depth           INTEGER DEFAULT 0,
    search_rank     INTEGER DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_page_task ON crawl_page(task_id, sort_order);
CREATE INDEX IF NOT EXISTS idx_page_url_hash ON crawl_page(url_hash);
"""


async def init_db():
    """启动时初始化数据库（建表）"""
    db_dir = os.path.dirname(settings.db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    async with aiosqlite.connect(settings.db_path) as db:
        db.text_factory = lambda b: b.decode("utf-8", errors="replace")
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA foreign_keys=ON")
        await db.execute("PRAGMA busy_timeout=5000")
        await db.execute("PRAGMA encoding = 'UTF-8'")
        await db.executescript(DDL)
        await db.commit()

    logger.info(f"Database initialized: {settings.db_path}")


@asynccontextmanager
async def get_db():
    """返回 aiosqlite 连接（在连接打开后设置 UTF-8 text_factory）"""
    async with aiosqlite.connect(settings.db_path) as db:
        db.text_factory = lambda b: b.decode("utf-8", errors="replace")
        await db.execute("PRAGMA foreign_keys=ON")
        await db.execute("PRAGMA busy_timeout=5000")
        yield db
