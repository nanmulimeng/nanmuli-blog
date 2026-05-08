"""共享 fixtures：内存 SQLite + Mock AI 配置"""

import os
import sys
import pytest_asyncio
import aiosqlite

# 将 crawler-service 根目录加入 sys.path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from standalone.db import DDL, _MIGRATIONS


@pytest_asyncio.fixture
async def mem_db():
    """内存 SQLite，初始化完整 DDL + 迁移"""
    db = await aiosqlite.connect(":memory:")
    db.text_factory = lambda b: b.decode("utf-8", errors="replace")
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys=ON")
    await db.executescript(DDL)
    await db.commit()

    # 模拟增量迁移（对新库是幂等的）
    cursor = await db.execute("PRAGMA table_info(crawl_task)")
    existing = {row[1] for row in await cursor.fetchall()}
    for col_name, sql in _MIGRATIONS:
        if col_name not in existing:
            try:
                await db.execute(sql)
            except Exception:
                pass
    await db.commit()

    yield db
    await db.close()
