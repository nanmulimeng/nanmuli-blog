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
    ai_template     TEXT DEFAULT 'tech_summary',
    status          INTEGER NOT NULL DEFAULT 0,
    error_message   TEXT,
    total_pages     INTEGER DEFAULT 1,
    completed_pages INTEGER DEFAULT 0,
    crawl_duration  INTEGER,
    total_word_count INTEGER,

    -- AI 整理结果
    ai_title        TEXT,
    ai_summary      TEXT,
    ai_key_points   TEXT,
    ai_tags         TEXT,
    ai_category     TEXT,
    ai_full_content TEXT,
    ai_duration     INTEGER,
    ai_tokens_used  INTEGER,
    ai_error_message TEXT,
    ai_search_metadata TEXT,

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

CREATE TABLE IF NOT EXISTS digest_section (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id     INTEGER NOT NULL REFERENCES crawl_task(id) ON DELETE CASCADE,
    category    TEXT NOT NULL,
    category_name TEXT,
    emoji       TEXT,
    sort_order  INTEGER DEFAULT 0,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_section_task ON digest_section(task_id);

CREATE TABLE IF NOT EXISTS digest_item (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    section_id  INTEGER NOT NULL REFERENCES digest_section(id) ON DELETE CASCADE,
    title       TEXT NOT NULL,
    one_liner   TEXT,
    source_url  TEXT,
    source_name TEXT,
    page_id     INTEGER,
    sort_order  INTEGER DEFAULT 0,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_item_section ON digest_item(section_id);
"""

# Incremental migration for existing databases
_MIGRATIONS = [
    ("ai_template", "ALTER TABLE crawl_task ADD COLUMN ai_template TEXT DEFAULT 'tech_summary'"),
    ("ai_title", "ALTER TABLE crawl_task ADD COLUMN ai_title TEXT"),
    ("ai_summary", "ALTER TABLE crawl_task ADD COLUMN ai_summary TEXT"),
    ("ai_key_points", "ALTER TABLE crawl_task ADD COLUMN ai_key_points TEXT"),
    ("ai_tags", "ALTER TABLE crawl_task ADD COLUMN ai_tags TEXT"),
    ("ai_category", "ALTER TABLE crawl_task ADD COLUMN ai_category TEXT"),
    ("ai_full_content", "ALTER TABLE crawl_task ADD COLUMN ai_full_content TEXT"),
    ("ai_duration", "ALTER TABLE crawl_task ADD COLUMN ai_duration INTEGER"),
    ("ai_tokens_used", "ALTER TABLE crawl_task ADD COLUMN ai_tokens_used INTEGER"),
    ("ai_error_message", "ALTER TABLE crawl_task ADD COLUMN ai_error_message TEXT"),
    ("ai_search_metadata", "ALTER TABLE crawl_task ADD COLUMN ai_search_metadata TEXT"),
    ("digest_date", "ALTER TABLE crawl_task ADD COLUMN digest_date TEXT"),
    ("digest_highlight", "ALTER TABLE crawl_task ADD COLUMN digest_highlight TEXT"),
    ("idx_digest_date", "CREATE INDEX IF NOT EXISTS idx_digest_date ON crawl_task(digest_date)"),
]


async def init_db():
    """启动时初始化数据库（建表 + 增量迁移）"""
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

        # Incremental migrations: add columns if missing
        cursor = await db.execute("PRAGMA table_info(crawl_task)")
        existing_columns = {row[1] for row in await cursor.fetchall()}

        for col_name, sql in _MIGRATIONS:
            if col_name not in existing_columns:
                try:
                    await db.execute(sql)
                    logger.info("Migration applied: %s", col_name)
                except Exception as e:
                    logger.warning("Migration skipped (%s): %s", col_name, e)

        await db.commit()

    logger.info("Database initialized: %s", settings.db_path)


@asynccontextmanager
async def get_db():
    """返回 aiosqlite 连接（预设 UTF-8 text_factory + row_factory）"""
    async with aiosqlite.connect(settings.db_path) as db:
        db.text_factory = lambda b: b.decode("utf-8", errors="replace")
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys=ON")
        await db.execute("PRAGMA busy_timeout=5000")
        yield db
