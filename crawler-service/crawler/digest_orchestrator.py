"""日报生成总管 Agent — 规划、执行、监控、优化一体化编排

将原有的"无脑全爬 → 事后优化"模式升级为：
  Phase 0: 事前规划（历史分析 + 源筛选 + 参数自适应）
  Phase 1: 按计划爬取（优先级排序 + 实时监控 + 失败 fallback）
  Phase 2: 事后补充（仅在覆盖度不足时触发）
  Phase 3: 持久化指纹

替代原有 execute_digest_crawl() 成为日报爬取的新入口。
"""

import asyncio
import logging
from dataclasses import dataclass, field

from config import settings

logger = logging.getLogger(__name__)


# ============== 数据结构 ==============

@dataclass
class PlannedSection:
    """事前规划后的板块"""
    name: str
    source_type: str               # keyword / url / rss / mixed
    keywords: list[str] = field(default_factory=list)   # 独立的关键词列表（不 OR 合并）
    keyword_details: list[dict] = field(default_factory=list)  # keyword 级效能数据
    url_sources: list[dict] = field(default_factory=list)
    rss_sources: list[dict] = field(default_factory=list)
    max_items: int = 5
    time_range: str = "week"       # keyword 搜索独立计算的时间范围
    priority: int = 0              # 0=最高优先级
    engine: str = ""               # 推荐搜索引擎
    effectiveness: dict = field(default_factory=dict)
    # 爬取结果追踪
    result_count: int = 0
    status: str = "pending"        # pending / crawling / ok / failed / skipped


@dataclass
class DigestCrawlPlan:
    """事前规划生成的爬取计划"""
    sections: list[PlannedSection] = field(default_factory=list)
    total_budget: float = 600.0
    config_snapshot: dict = field(default_factory=dict)
    # KB 推荐信息
    kb_hint: dict = field(default_factory=dict)
    # 规划日志（供前端展示）
    plan_log: list[str] = field(default_factory=list)


def _calculate_digest_output_quality(digest_content) -> dict:
    """对最终日报成品做轻量质量评分，用于 Phase 4 闭环反馈。"""
    if not digest_content:
        return {
            "name": "__digest_output__",
            "score": 0.0,
            "item_count": 0,
            "section_count": 0,
            "duplicate_source_count": 0,
            "sourced_item_ratio": 0.0,
            "avg_one_liner_length": 0,
            "has_markdown_heading": False,
            "suggestions": ["日报生成结果为空"],
        }

    sections = getattr(digest_content, "sections", []) or []
    items = [
        item
        for sec in sections
        for item in (getattr(sec, "items", []) or [])
    ]
    item_count = len(items)
    section_count = len([sec for sec in sections if getattr(sec, "items", None)])
    urls = [getattr(item, "source_url", "") for item in items if getattr(item, "source_url", "")]
    unique_urls = set(urls)
    duplicate_source_count = max(0, len(urls) - len(unique_urls))
    sourced_item_ratio = round(len(urls) / item_count, 3) if item_count else 0.0
    one_liners = [getattr(item, "one_liner", "") or "" for item in items]
    avg_one_liner_length = int(sum(len(x) for x in one_liners) / item_count) if item_count else 0
    full_content = getattr(digest_content, "full_content", "") or ""
    has_markdown_heading = "#" in full_content

    unique_url_ratio = len(unique_urls) / len(urls) if urls else 0.0
    score = (
        min(item_count / 5, 1.0) * 0.25
        + min(section_count / 2, 1.0) * 0.15
        + sourced_item_ratio * 0.20
        + unique_url_ratio * 0.15
        + min(avg_one_liner_length / 30, 1.0) * 0.10
        + (0.15 if has_markdown_heading else 0.0)
    )

    suggestions = []
    if item_count < 5:
        suggestions.append("日报条目数偏少，建议增加有效来源或降低重复内容占比")
    if section_count < 2:
        suggestions.append("日报覆盖板块偏少，建议补充不同主题板块的信息源")
    if duplicate_source_count:
        suggestions.append("日报存在重复 sourceUrl，建议加强事件合并和来源去重")
    if sourced_item_ratio < 1.0:
        suggestions.append("部分日报条目缺少 sourceUrl，建议强化来源引用约束")
    if avg_one_liner_length < 30:
        suggestions.append("oneLiner 信息密度偏低，建议明确影响、动作和适用对象")
    if not has_markdown_heading:
        suggestions.append("fullContent 缺少 Markdown 标题结构")
    if not suggestions:
        suggestions.append("日报成品结构良好，保持当前生成策略")

    return {
        "name": "__digest_output__",
        "score": round(score, 3),
        "item_count": item_count,
        "section_count": section_count,
        "duplicate_source_count": duplicate_source_count,
        "sourced_item_ratio": sourced_item_ratio,
        "avg_one_liner_length": avg_one_liner_length,
        "has_markdown_heading": has_markdown_heading,
        "suggestions": suggestions,
    }


# ============== 总管 Agent ==============

class DigestOrchestrator:
    """日报生成总管 Agent"""

    def __init__(self):
        self._crawl_plan: DigestCrawlPlan | None = None
        self._section_documents: list = []
        self._digest_result = None
        self._global_timeout_reached = False

    async def execute(self, task: dict, config, task_executor) -> list:
        """总入口：替代原有 execute_digest_crawl()"""
        from crawler.dedup import DedupEngine
        from crawler.config import get_browser_config, RunParams
        from crawler.dependencies import get_async_web_crawler

        task_id = task.get("id", "?")
        self._global_timeout_reached = False

        # Phase 0: 事前规划
        self._crawl_plan = await self._build_plan(task)
        if not self._crawl_plan.sections:
            raise ValueError("日报功能未配置或无可用信息源")

        logger.info(
            "[Orchestrator] Plan for task %s: %d sections, engine=%s",
            task_id, len(self._crawl_plan.sections),
            self._crawl_plan.config_snapshot.get("engine", "?"),
        )

        # 配置快照（防止运行中配置变更）
        snap = self._crawl_plan.config_snapshot

        # 去重引擎
        from crawler.digest import build_digest_history_engine
        history_engine = await build_digest_history_engine()
        seen_urls: set[str] = set()
        all_results: list = []
        lock = asyncio.Lock()
        content_dedup = DedupEngine(simhash_threshold=5)

        params = RunParams(config)
        browser_config = await get_browser_config(
            text_mode=params.text_mode, light_mode=params.light_mode,
            proxy=snap.get("proxy_url", ""),
        )

        AsyncWebCrawler = get_async_web_crawler()
        async with AsyncWebCrawler(config=browser_config) as shared_crawler:

            # Phase 1: 派出信息源 Agent
            all_results, seen_urls = await self._dispatch(
                config, shared_crawler, history_engine,
                content_dedup, task, lock, seen_urls, all_results,
            )

            # Phase 1.5: 板块感知优化 Agent（替代旧的盲补充）
            if self._should_run_optimization(snap, all_results):
                try:
                    from crawler.optimization_agent import OptimizationAgent
                    opt_agent = OptimizationAgent(snap)
                    opt_result = await opt_agent.execute(
                        crawl_plan=self._crawl_plan,
                        section_documents=self._section_documents,
                        all_results=all_results, seen_urls=seen_urls,
                        shared_crawler=shared_crawler,
                        history_engine=history_engine,
                        content_dedup=content_dedup,
                        config=config, task=task,
                    )
                    all_results = opt_result.all_results
                    seen_urls = opt_result.seen_urls
                    self._section_documents = opt_result.section_documents
                    logger.info(
                        "[Orchestrator] Optimization: %d rounds, %d sections improved, %.1fs",
                        opt_result.rounds_completed, opt_result.sections_improved,
                        opt_result.budget_used_seconds,
                    )
                except Exception as e:
                    logger.warning("[Orchestrator] OptimizationAgent failed (non-critical): %s", e)

            # Phase 2: 日报生成 Agent（优化后再生成，获得完整数据）
            # 注：超时后仍允许生成日报（不完整数据生成的日报比没有好）
            if self._global_timeout_reached:
                logger.warning("[Orchestrator] Generating digest with incomplete data due to global timeout")
            if self._section_documents:
                try:
                    from crawler.digest_gen_agent import DigestGenAgent
                    digest_agent = DigestGenAgent(snap)
                    date = task.get("digest_date") or task.get("keyword") or ""
                    if not date:
                        import datetime
                        date = datetime.date.today().isoformat()
                    self._digest_result = await digest_agent.execute(
                        self._section_documents, date,
                    )
                    if self._digest_result.success:
                        logger.info(
                            "[Orchestrator] Digest pre-generated: title='%s', sections=%d",
                            self._digest_result.digest_content.title if self._digest_result.digest_content else "?",
                            len(self._digest_result.digest_content.sections) if self._digest_result.digest_content else 0,
                        )
                    else:
                        logger.warning("[Orchestrator] DigestGenAgent failed: %s", self._digest_result.error)
                        self._digest_result = None
                except Exception as e:
                    logger.warning("[Orchestrator] DigestGenAgent error (non-critical, will fallback): %s", e)
                    self._digest_result = None

        # Phase 3: 持久化指纹
        digest_date = task.get("digest_date", "")
        if digest_date and all_results:
            try:
                from crawler.digest import save_digest_fingerprints
                await save_digest_fingerprints(task["id"], all_results, digest_date)
            except Exception as e:
                logger.warning("[Orchestrator] Fingerprint save failed (non-critical): %s", e)

        # Phase 4: 日报后评估 → 写入 KB（闭环）
        # 超时时跳过 KB 写入，避免不完整数据污染知识库推荐
        if self._digest_result and self._digest_result.success:
            if self._global_timeout_reached:
                logger.warning("[Orchestrator] Skipping Phase 4 KB write due to global timeout (incomplete data)")
            else:
                try:
                    await self._evaluate_digest_quality(
                        self._digest_result, self._crawl_plan, task,
                        all_results,
                    )
                except Exception as e:
                    logger.warning("[Orchestrator] Phase 4 digest evaluation failed (non-critical): %s", e)

        return all_results

    # ============== Phase 0: 事前规划 ==============

    async def _build_plan(self, task: dict) -> DigestCrawlPlan:
        """Phase 0: 事前规划 — 分析历史、筛选源、生成爬取计划"""
        plan = DigestCrawlPlan(
            total_budget=settings.digest_global_timeout,
            config_snapshot=self._snapshot_config(),
        )

        # 1. 获取板块配置
        from standalone.task_executor import get_digest_sections
        sections = await get_digest_sections()
        if not sections:
            return plan

        # 2. KB 历史推荐 + 上次评估弱点（复用同一 KB 实例）
        kb_hint = {}
        try:
            from optimization.knowledge_base import KnowledgeBase
            from crawler.digest import _extract_digest_keyword
            eval_keyword = _extract_digest_keyword(sections) or "技术日报"
            kb = KnowledgeBase()
            kb_hint = await kb.get_strategy_hint(
                eval_keyword, settings.digest_search_engine, "week"
            )
            if kb_hint is None:
                kb_hint = {}
            plan.kb_hint = kb_hint
            plan.plan_log.append(f"KB hint: engine={kb_hint.get('recommended_engine')}, strategy={kb_hint.get('recommended_strategy_type')}")

            # 能力 6: 读取上次日报的评估弱点 → 传递给 SourceAgent 自适应
            last_weaknesses = await kb.get_last_digest_weaknesses()
            if last_weaknesses:
                kb_hint["last_weaknesses"] = last_weaknesses.get("weaknesses", [])
                kb_hint["last_suggestions"] = last_weaknesses.get("suggestions", [])
                plan.plan_log.append(f"Last eval weaknesses: {last_weaknesses.get('weaknesses', [])[:3]}")

            # 能力 7: 读取日报质量趋势 → 影响板块优先级和参数
            trend = await kb.get_digest_quality_trend(limit=5)
            if trend:
                avg_score = sum(t.get("overall_score", 0) for t in trend) / len(trend)
                plan.plan_log.append(f"Quality trend: avg={avg_score:.2f} over {len(trend)} runs")
                if avg_score < 0.5:
                    weak_dims = []
                    dim_fields = {
                        "source_diversity": "source_diversity",
                        "depth": "depth_coverage",
                        "angle": "angle_coverage",
                        "temporal": "temporal_coverage",
                        "perspective": "perspective_balance",
                        "language": "language_coverage",
                    }
                    for dim, field in dim_fields.items():
                        dim_avg = sum(t.get(field, 0) for t in trend) / len(trend)
                        if dim_avg < 0.5:
                            weak_dims.append(dim)
                    if weak_dims:
                        kb_hint["persistent_weak_dims"] = weak_dims
                        plan.plan_log.append(f"Persistent weak dimensions: {weak_dims}")
        except Exception as e:
            logger.debug("[Orchestrator] KB plan building failed: %s", e)

        recommended_engine = kb_hint.get("recommended_engine") or settings.digest_search_engine

        # 3. 转换板块为 PlannedSection
        for i, sec in enumerate(sections):
            planned = PlannedSection(
                name=sec.get("name", f"section_{i}"),
                source_type=sec.get("source_type", "keyword"),
                keyword_details=sec.get("keyword_details", []),
                url_sources=sec.get("url_sources", []),
                rss_sources=sec.get("rss_sources", []),
                max_items=sec.get("max_items", 5),
                time_range=sec.get("time_range", "week"),
                engine=recommended_engine,
                effectiveness=sec.get("effectiveness", {}),
            )

            # keyword 处理：拆分 OR 为独立关键词
            kw_raw = sec.get("keyword", "")
            if kw_raw:
                planned.keywords = [kw.strip() for kw in kw_raw.split(" OR ") if kw.strip()]

            # 计算优先级：基于板块效能
            eff = planned.effectiveness
            health = (eff.get("avg_quality", 50) / 100.0) * 0.5 + eff.get("success_rate", 0.5) * 0.5
            # 无历史数据的板块给中等优先级
            if eff.get("total_runs", 0) == 0:
                health = 0.5
            planned.priority = int((1.0 - health) * 10)  # 越低分优先级越高

            # 参数自适应已下沉到 SourceAgent.analyze()，此处不再重复调整

            plan.sections.append(planned)

        # 4. 按优先级排序（低 priority 值 = 高优先级）
        plan.sections.sort(key=lambda s: s.priority)

        plan.plan_log.append(f"Planned {len(plan.sections)} sections, engine={recommended_engine}")
        for s in plan.sections:
            plan.plan_log.append(
                f"  [{s.priority}] {s.name} ({s.source_type}): "
                f"max_items={s.max_items}, engine={s.engine}, eff={s.effectiveness.get('avg_quality', '?')}"
            )

        return plan

    # ============== Phase 1: 分析 + 调度 ==============

    async def _dispatch(self, config, crawler, history_engine, content_dedup, task, lock, seen_urls, all_results):
        """Phase 1: 收集信息源报告 → 综合决策 → 派出爬虫 Agent"""

        snap = self._crawl_plan.config_snapshot

        # Step 1: 信息源分析 — 每个 SourceAgent 产出 SourceCrawlPlan 报告
        reports = self._collect_reports(config, snap)

        # Step 2: 综合决策 — 记录报告汇总
        self._log_reports(reports)

        # Step 3: 派出爬虫 Agent — 按 SourceCrawlPlan 执行爬取
        await self._dispatch_crawlers(config, crawler, history_engine, content_dedup, task, lock, seen_urls, all_results, reports)

        # 汇总日志
        ok = sum(1 for s in self._crawl_plan.sections if s.status == "ok" or s.status.startswith("ok-"))
        fail = sum(1 for s in self._crawl_plan.sections if s.status == "failed")
        logger.info(
            "[Orchestrator] Summary: %d sections, %d ok, %d failed → %d results",
            len(self._crawl_plan.sections), ok, fail, len(all_results),
        )

        return all_results, seen_urls

    def _collect_reports(self, config, snap: dict) -> list:
        """Step 1: 每个 SourceAgent 分析信息源，产出 SourceCrawlPlan 报告"""
        from crawler.source_agent import SourceAgent

        reports = []
        for section in self._crawl_plan.sections:
            agent = SourceAgent(section, config, snap)
            report = agent.analyze(kb_hint=self._crawl_plan.kb_hint)
            reports.append((section, report))
        return reports

    def _log_reports(self, reports: list):
        """Step 2: 综合报告 — 记录汇总日志"""
        total_sources = sum(
            len(r.active_keywords) + len(r.active_url_sources) + len(r.active_rss_sources)
            for _, r in reports
        )
        total_skipped = sum(len(r.skipped_source_ids) for _, r in reports)
        self._crawl_plan.plan_log.append(
            f"Reports collected: {len(reports)} sections, "
            f"{total_sources} active sources, {total_skipped} dead skipped"
        )
        for section, report in reports:
            self._crawl_plan.plan_log.append(
                f"  [{section.priority}] {section.name}: "
                f"{len(report.active_keywords)}kw + {len(report.active_url_sources)}url + "
                f"{len(report.active_rss_sources)}rss, engine={report.recommended_engine}, "
                f"max_items={report.adjusted_max_items}"
            )

    async def _dispatch_crawlers(self, config, crawler, history_engine, content_dedup, task, lock, seen_urls, all_results, reports):
        """Step 3: 派出 CrawlerAgent 执行爬取"""
        from crawler.crawler_agent import CrawlerAgent
        from standalone import repository as repo

        snap = self._crawl_plan.config_snapshot
        sem = asyncio.Semaphore(snap.get("max_parallel", 2))

        async def run_crawler(section: PlannedSection, report):
            async with sem:
                crawler_agent = CrawlerAgent(section, report, config, snap)
                result = await crawler_agent.execute(crawler, history_engine)

                async with lock:
                    added = self._merge_results(
                        result.results, seen_urls, all_results, content_dedup
                    )
                    await repo.update_task_progress(task["id"], len(all_results))
                    if result.section_document:
                        self._section_documents.append(result.section_document)

                section.result_count = added
                if result.success:
                    section.status = "ok-fallback" if result.fallback_used else "ok"
                else:
                    section.status = "failed"

                # 实时覆盖率快速评估
                if added > 0 and len(all_results) >= 3:
                    self._quick_coverage_check(all_results, section.name, plan_log=self._crawl_plan.plan_log)

                logger.info("[Orchestrator] Section '%s' [%s]: %d results (fallback=%s)",
                            section.name, section.source_type, section.result_count,
                            result.fallback_used)

        # 全局超时保护
        section_tasks = [
            asyncio.create_task(run_crawler(s, r))
            for s, r in reports
        ]
        try:
            await asyncio.wait_for(
                asyncio.gather(*section_tasks),
                timeout=snap.get("global_timeout", 600),
            )
        except asyncio.TimeoutError:
            self._global_timeout_reached = True
            logger.warning("[Orchestrator] Global timeout reached, cancelling %d tasks", len(section_tasks))
            for t in section_tasks:
                if not t.done():
                    t.cancel()
            await asyncio.gather(*section_tasks, return_exceptions=True)
            completed = sum(1 for s in self._crawl_plan.sections if s.status in ("ok", "ok-fallback"))
            logger.warning(
                "[Orchestrator] All tasks cancelled: %d/%d sections ok, %d results, %d section docs (may be incomplete)",
                completed, len(self._crawl_plan.sections), len(all_results), len(self._section_documents),
            )

    def _merge_results(self, results, seen_urls, all_results, content_dedup) -> int:
        """合并板块结果到全局列表（委托公共函数）"""
        from crawler.dedup import merge_results_into
        return merge_results_into(results, seen_urls, all_results, content_dedup)

    # ============== 辅助方法 ==============

    def _should_run_optimization(self, snap: dict, all_results: list) -> bool:
        """检查是否满足优化触发条件（按板块统计达标数，非全局总数）"""
        if self._global_timeout_reached:
            logger.info("[Orchestrator] Skip optimization because global timeout was reached")
            return False
        if not (snap.get("optimization_enabled")
                and snap.get("optimization_mode") in ("digest", "both")
                and snap.get("digest_optimization_enabled")):
            return False
        min_sections = snap.get("digest_optimization_min_sections", 2)
        min_per_sec = snap.get("digest_optimization_min_results_per_section", 3)
        qualified = sum(1 for s in self._crawl_plan.sections
                        if s.result_count >= min_per_sec) if self._crawl_plan else 0
        return qualified >= min_sections

    def _snapshot_config(self) -> dict:
        """快照配置值，防止运行中配置变更"""
        return {
            "engine": settings.digest_search_engine,
            "max_parallel": getattr(settings, "digest_parallel_sections", 2),
            "global_timeout": settings.digest_global_timeout,
            "proxy_url": settings.proxy_url,
            "optimization_enabled": settings.optimization_enabled,
            "optimization_mode": settings.optimization_mode,
            "optimization_max_rounds": settings.optimization_max_rounds,
            "digest_optimization_enabled": settings.digest_optimization_enabled,
            "digest_optimization_min_sections": settings.digest_optimization_min_sections,
            "digest_optimization_min_results_per_section": settings.digest_optimization_min_results_per_section,
            "digest_optimization_target_score": settings.digest_optimization_target_score,
        }

    def get_plan(self) -> DigestCrawlPlan | None:
        """获取当前规划（供 API 查询）"""
        return self._crawl_plan

    def get_section_documents(self) -> list:
        """获取所有板块清洗文档"""
        return self._section_documents

    def get_digest_result(self):
        """获取预生成的日报结果（如果可用）"""
        return self._digest_result

    async def _evaluate_digest_quality(self, digest_result, plan, task, all_results):
        """Phase 4: 日报后评估 — 对最终日报质量评分并写入 KB，形成闭环"""
        from optimization.evaluator import CoverageEvaluator, _get_weights

        # 1. 用所有爬取结果做6维评估（复用评估器）
        from ai import content_organizer as organizer

        # 创建独立实例用于评估，避免与 DigestGenAgent 共享状态导致 close 后不可用
        eval_organizer = None
        try:
            if organizer.is_available:
                eval_organizer = organizer
        except Exception:
            pass
        evaluator = CoverageEvaluator(eval_organizer)
        keyword = " ".join(
            kw for s in plan.sections for kw in s.keywords[:2]
        ) if plan.sections else "技术日报"
        eval_results = self._build_digest_eval_results(self._section_documents) or all_results
        section_result_counts = {sec.name: 0 for sec in plan.sections}
        for r in eval_results:
            meta = r.get("metadata", {}) if isinstance(r, dict) else getattr(r, "metadata", {}) or {}
            category = meta.get("section_category")
            if category:
                section_result_counts[category] = section_result_counts.get(category, 0) + 1
        if not any(section_result_counts.values()):
            section_result_counts = {sec.name: sec.result_count for sec in plan.sections}

        eval_ctx = {
            "engine": plan.config_snapshot.get("engine", "unknown"),
            "time_range": "week",
            "task_type": "digest",
            "section_result_counts": section_result_counts,
        }
        evaluation = await evaluator.evaluate(keyword, eval_results, eval_ctx)

        # 2. 计算各板块得分
        section_scores = []
        min_per_section = int(
            plan.config_snapshot.get(
                "digest_optimization_min_results_per_section",
                settings.digest_optimization_min_results_per_section,
            )
            if plan.config_snapshot else settings.digest_optimization_min_results_per_section
        )
        min_per_section = max(1, min_per_section)
        section_fill_scores = []
        for sec in plan.sections:
            fill_score = min(1.0, max(0, sec.result_count) / min_per_section)
            section_fill_scores.append(fill_score)
            section_scores.append({
                "name": sec.name,
                "result_count": sec.result_count,
                "status": sec.status,
                "fill_score": round(fill_score, 3),
            })
        section_fill_ratio = (
            sum(section_fill_scores) / len(section_fill_scores)
            if section_fill_scores else 1.0
        )

        # 3. 生成改进建议（基于弱维度）
        suggestions = []
        dims = {
            "angle": evaluation.angle_coverage,
            "source_diversity": evaluation.source_diversity,
            "depth": evaluation.depth_coverage,
            "temporal": evaluation.temporal_coverage,
            "perspective": evaluation.perspective_balance,
            "language": evaluation.language_coverage,
        }
        for dim, score in sorted(dims.items(), key=lambda x: x[1]):
            if score < 0.5:
                suggestions.append(f"{dim}={score:.2f} 偏低，建议下次优先优化此维度")
        if not suggestions:
            suggestions.append("整体覆盖度良好，保持当前策略")
        if section_fill_ratio < 0.8:
            suggestions.append(
                f"板块有效结果不足，当前充足度 {section_fill_ratio:.2f}，"
                f"建议补足每板块至少 {min_per_section} 条有效来源"
            )

        output_quality = _calculate_digest_output_quality(
            getattr(digest_result, "digest_content", None)
        )
        section_scores.append(output_quality)
        suggestions.extend(output_quality.get("suggestions", []))
        # 覆盖度权重默认 0.7，成品质量权重默认 0.3，可通过配置调整
        coverage_weight = plan.config_snapshot.get("digest_coverage_weight", 0.7) if plan.config_snapshot else 0.7
        output_weight = 1.0 - coverage_weight
        final_score = round(
            evaluation.overall_score * coverage_weight + output_quality["score"] * output_weight,
            3,
        )
        if section_fill_ratio < 0.8:
            # 成品格式再好，也不能掩盖信息源覆盖不足；保留轻量惩罚避免趋势分虚高。
            final_score = round(final_score * (0.7 + 0.3 * section_fill_ratio), 3)

        # 4. 写入 KB
        digest_date = task.get("digest_date", "")
        task_id = task.get("id", 0)
        try:
            from optimization.knowledge_base import KnowledgeBase
            kb = KnowledgeBase()
            await kb.save_digest_evaluation(
                task_id=task_id,
                digest_date=digest_date,
                overall_score=final_score,
                dimension_scores=dims,
                section_scores=section_scores,
                suggestions=suggestions,
            )
            logger.info(
                "[Orchestrator] Phase 4: coverage=%.2f, output=%.2f, final=%.2f, saved to KB (date=%s)",
                evaluation.overall_score, output_quality["score"], final_score, digest_date,
            )
        except Exception as e:
            logger.warning("[Orchestrator] Phase 4 KB write failed: %s", e)

    @staticmethod
    def _build_digest_eval_results(section_documents: list) -> list[dict]:
        """Build evaluation inputs from cleaned digest candidates instead of raw crawl pages."""
        if not section_documents:
            return []
        try:
            from crawler.digest_gen_agent import DigestGenAgent
            pages = DigestGenAgent({})._build_digest_pages(section_documents)
        except Exception as e:
            logger.debug("[Orchestrator] Build digest eval results failed: %s", e)
            return []

        results = []
        for page in pages:
            markdown = getattr(page, "markdown", "") or getattr(page, "summary", "") or ""
            if not markdown:
                continue
            results.append({
                "success": True,
                "url": getattr(page, "url", "") or "",
                "title": getattr(page, "title", "") or "",
                "markdown": markdown,
                "metadata": {
                    "section_category": getattr(page, "category", "") or "",
                    "source_level": getattr(page, "source_level", "") or "",
                },
            })
        return results

    def _quick_coverage_check(self, results: list, section_name: str, plan_log: list):
        """板块完成后的快速覆盖率评估（纯计算维度，无 AI 调用）"""
        from optimization.evaluator import CoverageEvaluator
        from urllib.parse import urlparse

        domains = []
        titles = []
        for r in results:
            url = r.url if hasattr(r, 'url') else (r.get('url', '') if isinstance(r, dict) else '')
            title = r.title if hasattr(r, 'title') else (r.get('title', '') if isinstance(r, dict) else '')
            try:
                parsed = urlparse(url)
                domain = parsed.netloc.lower().lstrip("www.")
                if domain:
                    domains.append(domain)
            except Exception:
                pass
            if title:
                titles.append(title)

        diversity = CoverageEvaluator.calc_shannon_entropy(domains)
        language = CoverageEvaluator.calc_language_mix(titles)

        if diversity < 0.3:
            msg = f"[Coverage] After '{section_name}': source_diversity={diversity:.2f} (low)"
            plan_log.append(msg)
            logger.info(msg)
        if language < 0.2:
            msg = f"[Coverage] After '{section_name}': language_coverage={language:.2f} (low)"
            plan_log.append(msg)
            logger.info(msg)
