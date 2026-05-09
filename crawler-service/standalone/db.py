"""SQLite 数据库连接管理 + DDL

连接复用策略：
  - 通过 get_db() 获取上下文管理器，支持嵌套调用复用同一连接
  - 外层 async with get_db() as db: 建立真实连接
  - 内层嵌套的 async with get_db() as db: 复用外层连接（引用计数）
  - TaskExecutor._execute 等长流程使用 task_scoped_db() 在整个任务期间保持连接
"""

import os
import asyncio
import aiosqlite
import logging
from contextlib import asynccontextmanager
from contextvars import ContextVar
from config import settings

logger = logging.getLogger(__name__)

# ContextVar 用于在同一次异步调用链中复用数据库连接
_db_connection: ContextVar[aiosqlite.Connection | None] = ContextVar("_db_connection", default=None)
_db_depth: ContextVar[int] = ContextVar("_db_depth", default=0)

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

    time_range      TEXT DEFAULT 'week',

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

CREATE TABLE IF NOT EXISTS optimization_record (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id         INTEGER NOT NULL REFERENCES crawl_task(id) ON DELETE CASCADE,
    round_num       INTEGER NOT NULL,
    angle_coverage  REAL,
    source_diversity REAL,
    depth_coverage  REAL,
    temporal_coverage REAL,
    perspective_balance REAL,
    language_coverage REAL,
    overall_score   REAL,
    search_keyword  TEXT,
    search_engine   TEXT,
    time_range      TEXT,
    strategy_type   TEXT,
    strategy_detail TEXT,
    weaknesses      TEXT,
    suggestions     TEXT,
    urls_before     INTEGER,
    urls_after      INTEGER,
    score_delta     REAL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_opt_record_task ON optimization_record(task_id);
CREATE INDEX IF NOT EXISTS idx_opt_record_delta ON optimization_record(score_delta DESC);
CREATE INDEX IF NOT EXISTS idx_opt_record_engine ON optimization_record(search_engine, score_delta DESC);
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
    ("time_range", "ALTER TABLE crawl_task ADD COLUMN time_range TEXT DEFAULT 'week'"),
]


async def init_db():
    """启动时初始化数据库（建表 + 增量迁移）"""
    db_dir = os.path.dirname(settings.db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    async with aiosqlite.connect(settings.db_path) as db:
        db.text_factory = lambda b: b.decode("utf-8", errors="replace")
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA foreign_keys=ON")
        await db.execute(f"PRAGMA busy_timeout={settings.db_busy_timeout}")
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

        # 恢复孤儿任务：将上次崩溃时 CRAWLING(1)/PROCESSING(2) 的任务重置为 FAILED
        cursor = await db.execute("""
            UPDATE crawl_task
            SET status = 4, error_message = '服务重启：任务被中断'
            WHERE status IN (1, 2)
        """)
        reset_count = cursor.rowcount
        await db.commit()

    if reset_count > 0:
        logger.warning("Recovered %d orphaned tasks (set to FAILED)", reset_count)

    logger.info("Database initialized: %s", settings.db_path)


@asynccontextmanager
async def get_db():
    """返回 aiosqlite 连接（支持嵌套复用）。

    外层 async with 建立真实连接，内层嵌套调用复用同一连接。
    这样同一个任务流程中的多次 repository 调用共享一个连接，
    减少频繁开关连接的开销，同时避免事务冲突。
    """
    existing = _db_connection.get()
    depth = _db_depth.get()

    if existing is not None and depth > 0:
        # 嵌套调用：复用外层连接
        _db_depth.set(depth + 1)
        try:
            yield existing
        finally:
            _db_depth.set(_db_depth.get() - 1)
    else:
        # 外层调用：创建新连接
        async with aiosqlite.connect(settings.db_path) as db:
            db.text_factory = lambda b: b.decode("utf-8", errors="replace")
            db.row_factory = aiosqlite.Row
            await db.execute("PRAGMA foreign_keys=ON")
            await db.execute(f"PRAGMA busy_timeout={settings.db_busy_timeout}")
            _db_connection.set(db)
            _db_depth.set(1)
            try:
                yield db
            finally:
                _db_depth.set(0)
                _db_connection.set(None)


@asynccontextmanager
async def task_scoped_db():
    """任务级别的连接作用域：在整个任务执行期间复用同一连接。

    用法：在 TaskExecutor._execute 入口处使用：
        async with task_scoped_db():
            ...  # 所有内部 repo.xxx() 调用共享连接
    """
    async with get_db() as db:
        yield db
