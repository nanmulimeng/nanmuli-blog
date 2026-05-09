"""策略知识库 — 基于历史数据的策略推荐引擎"""

import logging

from standalone.db import get_db

logger = logging.getLogger(__name__)

# LIKE 通配符安全转义 — 使用 ! 作为转义字符避免反斜杠在不同层级的转义问题
_LIKE_ESCAPE_CHAR = "!"

def _escape_like(text: str) -> str:
    """转义 SQL LIKE 通配符，防止 LIKE 注入"""
    return (
        text.replace("!", "!!")
            .replace("%", "!%")
            .replace("_", "!_")
    )


class KnowledgeBase:
    """策略知识库 — 持久化优化记录，提供策略推荐和效能统计"""

    # ============== 策略推荐 ==============

    async def get_strategy_hint(
        self,
        keyword: str,
        engine: str,
        time_range: str,
    ) -> dict | None:
        """
        为当前搜索上下文推荐最佳策略提示。

        单次查询 + Python 端聚合，避免多次数据库访问。
        知识库为空或无有效数据时返回 None。
        """
        tokens = keyword.split()
        like_pattern = f"%{_escape_like(tokens[0])}%" if tokens else "%"

        async with get_db() as db:
            cursor = await db.execute(
                """SELECT search_engine, strategy_type, score_delta,
                          search_keyword, time_range
                   FROM optimization_record
                   WHERE score_delta > 0
                     AND (search_keyword LIKE ? ESCAPE '!' OR time_range = ?)
                   ORDER BY score_delta DESC
                   LIMIT 50""",
                (like_pattern, time_range),
            )
            rows = await cursor.fetchall()

        if not rows:
            return None

        engine_deltas: dict[str, list[float]] = {}
        type_deltas: dict[str, list[float]] = {}
        related_keywords: set[str] = set()

        for r in rows:
            e = r["search_engine"]
            st = r["strategy_type"]
            delta = r["score_delta"]
            engine_deltas.setdefault(e, []).append(delta)
            type_deltas.setdefault(st, []).append(delta)
            if r["search_keyword"] != keyword:
                related_keywords.add(r["search_keyword"])

        def _best(scores: dict[str, list[float]]) -> str | None:
            if not scores:
                return None
            return max(scores, key=lambda k: sum(scores[k]) / len(scores[k]))

        return {
            "recommended_engine": _best(engine_deltas),
            "engine_scores": {k: round(sum(v) / len(v), 4) for k, v in engine_deltas.items()},
            "recommended_strategy_type": _best(type_deltas),
            "strategy_type_scores": {k: round(sum(v) / len(v), 4) for k, v in type_deltas.items()},
            "related_keywords": sorted(related_keywords)[:5],
        }

    # ============== 效能统计 ==============

    async def get_engine_effectiveness(self, limit: int = 10) -> list[dict]:
        """各搜索引擎的平均改善分数"""
        async with get_db() as db:
            cursor = await db.execute(
                """SELECT search_engine,
                          COUNT(*) AS rounds,
                          ROUND(AVG(score_delta), 4) AS avg_delta,
                          ROUND(AVG(overall_score), 4) AS avg_score,
                          SUM(CASE WHEN score_delta > 0 THEN 1 ELSE 0 END) AS improved
                   FROM optimization_record
                   WHERE round_num > 1
                   GROUP BY search_engine
                   ORDER BY avg_delta DESC
                   LIMIT ?""",
                (limit,),
            )
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_strategy_type_effectiveness(self, limit: int = 10) -> list[dict]:
        """各策略类型的改善效果统计"""
        async with get_db() as db:
            cursor = await db.execute(
                """SELECT strategy_type,
                          COUNT(*) AS rounds,
                          ROUND(AVG(score_delta), 4) AS avg_delta,
                          ROUND(MAX(score_delta), 4) AS max_delta,
                          SUM(CASE WHEN score_delta > 0 THEN 1 ELSE 0 END) AS improved
                   FROM optimization_record
                   WHERE score_delta > 0 AND round_num > 1
                   GROUP BY strategy_type
                   ORDER BY avg_delta DESC
                   LIMIT ?""",
                (limit,),
            )
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_similar_keyword_strategies(
        self, keyword: str, limit: int = 5,
    ) -> list[dict]:
        """关键词相似匹配：找到与当前关键词有共同词段的历史有效策略"""
        # 输入长度限制（DoS 防护）
        if len(keyword) > 200:
            keyword = keyword[:200]

        tokens = keyword.split()
        if not tokens:
            return []

        # 硬限制：最多 5 个 OR 子句（DoS 防护）
        max_clauses = 5
        tokens = tokens[:max_clauses]

        conditions = " OR ".join(["search_keyword LIKE ? ESCAPE '!'" for _ in tokens])
        params = [f"%{_escape_like(t)}%" for t in tokens] + [limit]

        async with get_db() as db:
            cursor = await db.execute(
                f"""SELECT search_keyword, search_engine, time_range,
                           strategy_type, overall_score, score_delta, created_at
                    FROM optimization_record
                    WHERE score_delta > 0 AND ({conditions})
                    ORDER BY score_delta DESC
                    LIMIT ?""",
                params,
            )
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    # ============== 聚合统计 ==============

    async def get_stats(self) -> dict:
        """优化引擎全局统计"""
        async with get_db() as db:
            cursor = await db.execute("""
                SELECT COUNT(*) AS total_rounds,
                       COUNT(DISTINCT task_id) AS total_tasks,
                       ROUND(AVG(overall_score), 4) AS avg_score,
                       ROUND(AVG(score_delta), 4) AS avg_delta,
                       SUM(CASE WHEN score_delta > 0 THEN 1 ELSE 0 END) AS improved_rounds
                FROM optimization_record
            """)
            row = await cursor.fetchone()
            if not row:
                return {}
            d = dict(row)
            total = d.get("total_rounds", 0) or 0
            improved = d.get("improved_rounds", 0) or 0
            d["improvement_rate"] = round(improved / total, 2) if total > 0 else 0.0
            return d

    # ============== 任务级查询 ==============

    async def get_records_for_task(self, task_id: int) -> list[dict]:
        """查询指定任务的优化轮次记录"""
        from standalone import repository as repo
        return await repo.get_optimization_records(task_id)

    # ============== 数据维护 ==============

    async def cleanup_old_records(self, days: int = 90) -> int:
        """清理 N 天前的优化记录，返回删除行数"""
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT COUNT(*) AS cnt FROM optimization_record WHERE created_at < datetime('now', ?)",
                (f"-{days} days",),
            )
            row = await cursor.fetchone()
            count = row["cnt"] if row else 0

            if count > 0:
                await db.execute(
                    "DELETE FROM optimization_record WHERE created_at < datetime('now', ?)",
                    (f"-{days} days",),
                )
                await db.commit()
                logger.info("[KnowledgeBase] Cleaned up %d old records (older than %d days)", count, days)

            return count
