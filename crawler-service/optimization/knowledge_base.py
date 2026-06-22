"""策略知识库 — 基于历史数据的策略推荐引擎"""

import json as _json
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


def _parse_json_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = _json.loads(value)
        except _json.JSONDecodeError:
            return []
        return parsed if isinstance(parsed, list) else []
    return []


def _score_status(score: float | None) -> str:
    if score is None:
        return "unknown"
    if score >= 0.75:
        return "success"
    if score >= 0.6:
        return "warning"
    return "danger"


def _normalize_source_score(score) -> float | None:
    if score is None:
        return None
    try:
        value = float(score)
    except (TypeError, ValueError):
        return None
    if value > 1:
        value = value / 100.0
    return max(0.0, min(value, 1.0))


def _normalize_source_id(source_id) -> int | str | None:
    if source_id is None or source_id == "":
        return None
    try:
        return int(source_id)
    except (TypeError, ValueError):
        return str(source_id)


def _normalize_source_url(source_url) -> str | None:
    if source_url is None:
        return None
    value = str(source_url).strip()
    return value or None


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
                          strategy_detail, weaknesses, suggestions, created_at
                   FROM optimization_record
                   WHERE strategy_type = 'digest_final_eval'
                   ORDER BY created_at DESC
                   LIMIT ?""",
                (limit,),
            )
            rows = await cursor.fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["strategy_detail"] = _parse_json_list(d.get("strategy_detail"))
            d["weaknesses"] = _parse_json_list(d.get("weaknesses"))
            d["suggestions"] = _parse_json_list(d.get("suggestions"))
            results.append(d)
        return results

    async def get_digest_quality_overview(self, limit: int = 10) -> dict:
        """Build a dashboard-ready digest quality summary from final evaluations."""
        trend = await self.get_digest_quality_trend(limit=limit)
        next_run_actions = await self.get_digest_source_actions()
        if not trend:
            return {
                "trend": [],
                "count": 0,
                "summary": {
                    "average_score": None,
                    "latest_score": None,
                    "score_delta": None,
                    "status": "unknown",
                },
                "latest": None,
                "weak_dimensions": {},
                "suggestions": [],
                "next_run_actions": next_run_actions,
            }

        scores = [
            float(item["overall_score"])
            for item in trend
            if item.get("overall_score") is not None
        ]
        latest = trend[0]
        latest_score = float(latest["overall_score"]) if latest.get("overall_score") is not None else None
        oldest_score = float(trend[-1]["overall_score"]) if trend[-1].get("overall_score") is not None else None
        score_delta = None
        if latest_score is not None and oldest_score is not None and len(scores) >= 2:
            score_delta = round(latest_score - oldest_score, 4)

        weak_counts: dict[str, int] = {}
        for item in trend:
            for dim in item.get("weaknesses") or []:
                dim_key = str(dim)
                weak_counts[dim_key] = weak_counts.get(dim_key, 0) + 1

        suggestions = [
            str(suggestion).strip()
            for suggestion in latest.get("suggestions") or []
            if str(suggestion).strip()
        ]

        return {
            "trend": trend,
            "count": len(trend),
            "summary": {
                "average_score": round(sum(scores) / len(scores), 4) if scores else None,
                "latest_score": latest_score,
                "score_delta": score_delta,
                "status": _score_status(latest_score),
            },
            "latest": latest,
            "weak_dimensions": dict(sorted(weak_counts.items(), key=lambda item: item[1], reverse=True)),
            "suggestions": suggestions[:5],
            "next_run_actions": next_run_actions,
        }

    # ============== 跨运行疲劳感知 ==============

    async def get_digest_source_actions(self) -> dict:
        """Derive conservative next-run source actions from the latest digest evaluation."""
        async with get_db() as db:
            cursor = await db.execute(
                """SELECT task_id, search_keyword AS digest_date, strategy_detail,
                          weaknesses, suggestions, created_at
                   FROM optimization_record
                   WHERE strategy_type = 'digest_final_eval'
                   ORDER BY created_at DESC
                   LIMIT 1""",
            )
            row = await cursor.fetchone()
        if not row:
            return self._empty_digest_source_actions()

        latest = dict(row)
        task_id = latest.get("task_id")
        diagnostics: list[dict] = []
        if task_id is not None:
            try:
                from standalone import repository as repo
                diagnostics = await repo.get_digest_source_diagnostics(int(task_id))
            except Exception as exc:
                logger.debug("[KnowledgeBase] source diagnostics lookup failed: %s", exc)
                diagnostics = []
        if not diagnostics:
            diagnostics = [
                item for item in _parse_json_list(latest.get("strategy_detail"))
                if isinstance(item, dict) and (
                    "source_id" in item or "source_url" in item or "quality_verdict" in item
                )
            ]

        weaknesses = _parse_json_list(latest.get("weaknesses"))
        suggestions = _parse_json_list(latest.get("suggestions"))
        action_outcomes = []
        if task_id is not None:
            try:
                from standalone import repository as repo
                task = await repo.get_task(int(task_id))
                action_outcomes = self._extract_digest_action_outcomes_from_task(task)
            except Exception as exc:
                logger.debug("[KnowledgeBase] action outcome lookup failed: %s", exc)
                action_outcomes = []
        return self.derive_digest_source_actions(
            diagnostics=diagnostics,
            weaknesses=weaknesses,
            suggestions=suggestions,
            digest_date=latest.get("digest_date"),
            created_at=latest.get("created_at"),
            action_outcomes=action_outcomes,
        )

    @classmethod
    def derive_digest_source_actions(
        cls,
        diagnostics: list[dict] | None,
        weaknesses: list | None = None,
        suggestions: list | None = None,
        digest_date=None,
        created_at=None,
        action_outcomes: list[dict] | None = None,
    ) -> dict:
        """Derive next-run source actions from already loaded source diagnostics."""
        diagnostics = diagnostics or []
        weaknesses = weaknesses or []
        suggestions = suggestions or []
        actions = cls._empty_digest_source_actions(
            digest_date=digest_date,
            created_at=created_at,
            weaknesses=weaknesses,
            suggestions=suggestions,
        )
        actions["boost_sections"] = [str(dim) for dim in weaknesses if str(dim).strip()][:6]

        skip_ids: list[int | str] = []
        deprioritize_ids: list[int | str] = []
        skip_urls: list[str] = []
        deprioritize_urls: list[str] = []
        sources: dict[int | str, dict] = {}
        section_source_counts: dict[str, int] = {}

        for item in diagnostics:
            source_id = _normalize_source_id(item.get("source_id"))
            source_url = _normalize_source_url(item.get("source_url"))
            if source_id is None and source_url is None:
                continue
            section = str(item.get("section") or "")
            section_source_counts[section] = section_source_counts.get(section, 0) + 1
            score = _normalize_source_score(item.get("quality_score"))
            verdict = str(item.get("quality_verdict") or "").lower()
            action = ""
            reason = ""
            if verdict == "filter" or (score is not None and score < 0.4):
                action = "skip"
                reason = "quality_score < 40 or filter verdict"
            elif verdict == "review" or (score is not None and score < 0.6):
                action = "deprioritize"
                reason = "quality_score < 60 or review verdict"
            if not action:
                continue

            if source_id is not None:
                target = skip_ids if action == "skip" else deprioritize_ids
                if source_id not in target:
                    target.append(source_id)
                source_key: int | str = source_id
            else:
                target_url = skip_urls if action == "skip" else deprioritize_urls
                if source_url not in target_url:
                    target_url.append(source_url)
                source_key = f"url:{source_url}"
            sources[source_key] = {
                "source_id": source_id,
                "source_name": item.get("source_name") or "",
                "source_url": source_url or "",
                "section": section,
                "item_count": item.get("item_count") or 0,
                "quality_score": score,
                "quality_verdict": verdict or None,
                "action": action,
                "reason": reason,
            }

        actions["source_ids"] = {
            "skip": skip_ids,
            "deprioritize": deprioritize_ids,
        }
        actions["source_urls"] = {
            "skip": skip_urls,
            "deprioritize": deprioritize_urls,
        }
        actions["sources"] = sources
        if skip_ids or deprioritize_ids or skip_urls or deprioritize_urls:
            actions["confidence"] = "medium" if len(diagnostics) >= 2 else "low"
        actions["safety"] = cls._apply_digest_source_action_safety(
            actions, section_source_counts
        )
        cls._apply_digest_action_outcome_safety(actions, action_outcomes)
        actions["reasons"] = [
            f"{src.get('source_name') or src.get('source_url') or sid}: {src['reason']}"
            for sid, src in sources.items()
        ][:8]
        return actions

    @staticmethod
    def _extract_digest_action_outcomes_from_task(task: dict | None) -> list[dict]:
        if not task:
            return []
        raw_meta = task.get("ai_search_metadata")
        if not raw_meta:
            return []
        try:
            import json as _json
            metadata = _json.loads(raw_meta) if isinstance(raw_meta, str) else raw_meta
        except Exception:
            return []
        if not isinstance(metadata, dict):
            return []
        plan = metadata.get("orchestrator_plan")
        if not isinstance(plan, dict):
            return []
        outcome = plan.get("optimization_action_outcome")
        return [outcome] if isinstance(outcome, dict) else []

    @classmethod
    def _apply_digest_action_outcome_safety(
        cls,
        actions: dict,
        action_outcomes: list[dict] | None = None,
    ) -> None:
        negative = cls._latest_negative_action_outcome(action_outcomes)
        if not negative:
            return

        safety = actions.setdefault("safety", {})
        safety.setdefault("applied", [])
        safety.setdefault("downgraded", [])
        safety.setdefault("section_source_counts", {})
        if "negative-outcome-circuit-breaker" not in safety["applied"]:
            safety["applied"].append("negative-outcome-circuit-breaker")

        suppressed_boosts = list(actions.get("boost_sections") or [])
        if suppressed_boosts:
            actions["boost_sections"] = []
            safety["suppressed_boost_sections"] = suppressed_boosts

        downgraded = cls._downgrade_matching_skips(
            actions,
            lambda _key, _src: True,
            "negative-outcome-circuit-breaker",
        )
        if downgraded:
            safety["downgraded"].extend(downgraded)

        result = negative.get("result") if isinstance(negative.get("result"), dict) else {}
        safety["last_negative_outcome"] = {
            "overall_score": result.get("overall_score"),
            "section_fill_ratio": result.get("section_fill_ratio"),
            "verdict": negative.get("verdict"),
        }
        actions["confidence"] = "low"

    @staticmethod
    def _latest_negative_action_outcome(action_outcomes: list[dict] | None) -> dict | None:
        for outcome in action_outcomes or []:
            if not isinstance(outcome, dict):
                continue
            if outcome.get("applied") is not True:
                continue
            if str(outcome.get("verdict") or "").lower() == "negative":
                return outcome
        return None

    @classmethod
    def _apply_digest_source_action_safety(
        cls,
        actions: dict,
        section_source_counts: dict[str, int] | None = None,
    ) -> dict:
        """Attach deterministic guardrails so feedback cannot starve a section."""
        safety = {
            "applied": [],
            "downgraded": [],
            "section_source_counts": section_source_counts or {},
        }

        if actions.get("confidence") == "low":
            downgraded = cls._downgrade_matching_skips(
                actions,
                lambda _key, _src: True,
                "low-confidence",
            )
            if downgraded:
                safety["applied"].append("low-confidence-skip-downgrade")
                safety["downgraded"].extend(downgraded)

        skips_by_section: dict[str, list[tuple[int | str, dict]]] = {}
        for source_key, src in (actions.get("sources") or {}).items():
            if not isinstance(src, dict) or src.get("action") != "skip":
                continue
            section = str(src.get("section") or "")
            skips_by_section.setdefault(section, []).append((source_key, src))

        for section, section_skips in skips_by_section.items():
            source_count = (section_source_counts or {}).get(section, len(section_skips))
            max_skip = max(0, int(source_count) // 2)
            if int(source_count) <= 1:
                max_skip = 0
            if len(section_skips) <= max_skip:
                continue
            section_skips.sort(key=lambda item: cls._source_action_quality(item[1]))
            keep_keys = {key for key, _src in section_skips[:max_skip]}
            downgraded = cls._downgrade_matching_skips(
                actions,
                lambda key, _src, keep=keep_keys: key not in keep,
                f"section-skip-cap:{section}:{len(section_skips)}->{max_skip}",
            )
            if downgraded:
                safety["applied"].append(
                    f"section-skip-cap:{section}:{len(section_skips)}->{max_skip}"
                )
                safety["downgraded"].extend(downgraded)

        return safety

    @classmethod
    def _downgrade_matching_skips(cls, actions: dict, predicate, reason: str) -> list[dict]:
        downgraded: list[dict] = []
        for source_key, src in (actions.get("sources") or {}).items():
            if not isinstance(src, dict) or src.get("action") != "skip":
                continue
            if not predicate(source_key, src):
                continue
            cls._downgrade_source_action(actions, source_key, src, reason)
            downgraded.append({
                "source_id": src.get("source_id"),
                "source_url": src.get("source_url") or "",
                "section": src.get("section") or "",
                "reason": reason,
            })
        return downgraded

    @classmethod
    def _downgrade_source_action(cls, actions: dict, source_key, src: dict, reason: str) -> None:
        source_id = _normalize_source_id(src.get("source_id"))
        source_url = _normalize_source_url(src.get("source_url"))
        source_ids = actions.setdefault("source_ids", {})
        source_urls = actions.setdefault("source_urls", {})

        if source_id is not None:
            source_ids["skip"] = [
                item for item in source_ids.get("skip", []) or []
                if _normalize_source_id(item) != source_id
            ]
            cls._append_unique_source_id(source_ids.setdefault("deprioritize", []), source_id)
        elif source_url is not None:
            source_urls["skip"] = [
                item for item in source_urls.get("skip", []) or []
                if _normalize_source_url(item) != source_url
            ]
            cls._append_unique_url(source_urls.setdefault("deprioritize", []), source_url)

        src["action"] = "deprioritize"
        src["reason"] = f"{reason}; {src.get('reason', 'source feedback')}"
        sources = actions.get("sources") or {}
        if source_key in sources:
            sources[source_key] = src

    @staticmethod
    def _source_action_quality(src: dict) -> float:
        score = src.get("quality_score")
        try:
            return float(score)
        except (TypeError, ValueError):
            return 1.0

    @staticmethod
    def _append_unique_source_id(target: list, source_id) -> None:
        normalized = _normalize_source_id(source_id)
        if all(_normalize_source_id(item) != normalized for item in target):
            target.append(source_id)

    @staticmethod
    def _append_unique_url(target: list, source_url) -> None:
        normalized = _normalize_source_url(source_url)
        if normalized and all(_normalize_source_url(item) != normalized for item in target):
            target.append(normalized)

    @staticmethod
    def _empty_digest_source_actions(
        digest_date=None,
        created_at=None,
        weaknesses: list | None = None,
        suggestions: list | None = None,
    ) -> dict:
        return {
            "digest_date": digest_date,
            "created_at": created_at,
            "source_ids": {"skip": [], "deprioritize": []},
            "source_urls": {"skip": [], "deprioritize": []},
            "boost_sections": weaknesses or [],
            "sources": {},
            "reasons": [],
            "suggestions": suggestions or [],
            "confidence": "none",
            "safety": {"applied": [], "downgraded": [], "section_source_counts": {}},
        }

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
