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
        tokens = keyword.split()[:3]
        if not tokens:
            return None

        conditions = " OR ".join(["search_keyword LIKE ? ESCAPE '!'" for _ in tokens])
        params = [f"%{_escape_like(t)}%" for t in tokens] + [time_range]

        async with get_db() as db:
            cursor = await db.execute(
                f"""SELECT search_engine, strategy_type, score_delta,
                          search_keyword, time_range
                   FROM optimization_record
                   WHERE round_num > 1
                     AND ({conditions} OR time_range = ?)
                   ORDER BY score_delta DESC
                   LIMIT 50""",
                params,
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
            if r["search_keyword"] != keyword and delta > 0:
                related_keywords.add(r["search_keyword"])

        def _best(scores: dict[str, list[float]]) -> str | None:
            if not scores:
                return None
            return max(scores, key=lambda k: sum(scores[k]) / len(scores[k]))

        def _best_normalized(scores: dict[str, list[float]]) -> str | None:
            """z-score 归一化后选最佳，避免不同策略类型的 delta 量级差异"""
            if not scores:
                return None
            flat = [d for ds in scores.values() for d in ds]
            if len(flat) < 3:
                return _best(scores)  # 数据不足时退化为原始 avg
            mean = sum(flat) / len(flat)
            std = (sum((d - mean) ** 2 for d in flat) / max(1, len(flat) - 1)) ** 0.5
            if std < 0.001:
                return _best(scores)
            normalized = {
                k: (sum(v) / len(v) - mean) / std
                for k, v in scores.items()
            }
            return max(normalized, key=normalized.get)

        return {
            "recommended_engine": _best(engine_deltas),
            "engine_scores": {k: round(sum(v) / len(v), 4) for k, v in engine_deltas.items()},
            "recommended_strategy_type": _best_normalized(type_deltas),
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
                    WHERE round_num > 1 AND ({conditions})
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

    # ============== 日报弱点反馈 ==============

    async def get_last_digest_weaknesses(self) -> dict | None:
        """读取最近一次日报优化轮次的弱点/建议（供下次规划参考）"""
        async with get_db() as db:
            cursor = await db.execute(
                """SELECT weaknesses, suggestions, created_at
                   FROM optimization_record
                   WHERE strategy_type = 'digest_final_eval'
                     AND suggestions IS NOT NULL
                     AND suggestions != '[]'
                   ORDER BY created_at DESC
                   LIMIT 1""",
            )
            row = await cursor.fetchone()
        if not row:
            return None
        import json
        weaknesses = row["weaknesses"]
        suggestions = row["suggestions"]
        return {
            "weaknesses": json.loads(weaknesses) if isinstance(weaknesses, str) else (weaknesses or []),
            "suggestions": json.loads(suggestions) if isinstance(suggestions, str) else (suggestions or []),
            "created_at": row["created_at"],
        }

    # ============== 日报后评估（Phase 4 闭环） ==============

    async def save_digest_evaluation(self, task_id: int, digest_date: str,
                                     overall_score: float,
                                     dimension_scores: dict,
                                     section_scores: list[dict] | None = None,
                                     suggestions: list[str] | None = None) -> None:
        """保存日报最终质量评估记录，供下次 _build_plan() 消费"""
        import json as _json
        weak_dims = [
            dim for dim, score in dimension_scores.items()
            if score is not None and float(score) < 0.5
        ]
        async with get_db() as db:
            await db.execute(
                """INSERT INTO optimization_record
                   (task_id, round_num,
                    angle_coverage, source_diversity, depth_coverage,
                    temporal_coverage, perspective_balance, language_coverage,
                    overall_score,
                    search_keyword, search_engine, time_range,
                    strategy_type, strategy_detail,
                    weaknesses, suggestions,
                    urls_before, urls_after, score_delta)
                   VALUES (?, 0, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0.0)""",
                (task_id,
                 dimension_scores.get("angle", 0),
                 dimension_scores.get("source_diversity", 0),
                 dimension_scores.get("depth", 0),
                 dimension_scores.get("temporal", 0),
                 dimension_scores.get("perspective", 0),
                 dimension_scores.get("language", 0),
                 overall_score,
                 digest_date, "digest", "",
                 "digest_final_eval",
                 _json.dumps(section_scores or [], ensure_ascii=False),
                 _json.dumps(weak_dims, ensure_ascii=False),
                 _json.dumps(suggestions or [], ensure_ascii=False)),
            )
            await db.commit()

    async def get_digest_quality_trend(self, limit: int = 10) -> list[dict]:
        """查询最近 N 次日报的最终质量评估趋势"""
        async with get_db() as db:
            cursor = await db.execute(
                """SELECT search_keyword AS digest_date,
                          overall_score,
                          angle_coverage, source_diversity, depth_coverage,
                          temporal_coverage, perspective_balance, language_coverage,
                          strategy_detail, suggestions, created_at
                   FROM optimization_record
                   WHERE strategy_type = 'digest_final_eval'
                   ORDER BY created_at DESC
                   LIMIT ?""",
                (limit,),
            )
            rows = await cursor.fetchall()
        import json as _json
        results = []
        for r in rows:
            d = dict(r)
            for field in ("strategy_detail", "suggestions"):
                raw = d.get(field)
                if raw and isinstance(raw, str):
                    try:
                        d[field] = _json.loads(raw)
                    except _json.JSONDecodeError:
                        pass
            results.append(d)
        return results

    # ============== 跨运行疲劳感知 ==============

    async def get_recent_dimension_fatigue(self, limit: int = 3) -> dict[str, list[float]]:
        """查询最近 N 次日报评估中各维度的改善情况，用于跨运行疲劳预填充。

        返回持续下降/不变的维度及其分数列表（最近在前）。
        """
        async with get_db() as db:
            cursor = await db.execute(
                """SELECT source_diversity, depth_coverage, angle_coverage,
                          temporal_coverage, perspective_balance, language_coverage,
                          created_at
                   FROM optimization_record
                   WHERE strategy_type = 'digest_final_eval'
                   ORDER BY created_at DESC
                   LIMIT ?""",
                (limit,),
            )
            rows = await cursor.fetchall()
        if not rows:
            return {}

        dims = ["source_diversity", "depth", "angle", "temporal", "perspective", "language"]
        dim_cols = [
            "source_diversity", "depth_coverage", "angle_coverage",
            "temporal_coverage", "perspective_balance", "language_coverage",
        ]
        result: dict[str, list[float]] = {}
        for dim, col in zip(dims, dim_cols):
            scores = [r[col] for r in rows if r[col] is not None]
            if len(scores) >= 2:
                # 最早（列表末尾）到最近（列表开头）持续下降或不变
                declining = all(scores[i] <= scores[-1] for i in range(len(scores) - 1))
                if declining:
                    result[dim] = scores
        return result

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
