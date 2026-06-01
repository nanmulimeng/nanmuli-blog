"""优化 Agent — 板块感知的覆盖率优化

由 DigestOrchestrator 在所有 CrawlerAgent 完成后调用（Phase 1.5）。
替代旧的 run_digest_optimization() 盲补充模式。

核心改进：
  - 板块级评估：识别哪个板块在哪个维度弱
  - 定向重爬：仅对弱板块生成策略并补充爬取
  - SectionDocument 更新：新结果追加到清洗文档
  - Phase 重排序：优化先行，日报后生成
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from urllib.parse import urlparse

from config import settings
from crawler.digest_orchestrator import DigestCrawlPlan, PlannedSection
from crawler.section_document import SectionDocument, SourceEntry
from optimization.fatigue import FatigueTracker

logger = logging.getLogger(__name__)

_MAX_OPT_ROUNDS = 2
_MAX_RECRAWL_RESULTS = 5
_BREADTH_DIMS = {"source_diversity", "perspective", "language"}
_DEPTH_DIMS = {"depth", "angle", "temporal"}


@dataclass
class WeakSection:
    """被识别为需要优化的板块"""
    section: PlannedSection
    evaluation: "CoverageEvaluation"
    weakest_dimensions: list[str] = field(default_factory=list)


@dataclass
class OptimizationResult:
    """优化 Agent 执行结果"""
    all_results: list = field(default_factory=list)
    section_documents: list = field(default_factory=list)
    seen_urls: set = field(default_factory=set)
    rounds_completed: int = 0
    sections_improved: int = 0
    budget_used_seconds: float = 0.0


@dataclass
class _OptRound:
    """优化轮次记录（供 save_optimization_round 使用）"""
    round_num: int
    evaluation: "CoverageEvaluation"
    strategy: "SearchStrategy"
    urls_before: int
    urls_after: int
    score_delta: float


class OptimizationAgent:
    """板块感知优化 Agent

    复用 CoverageEvaluator / StrategyGen / KnowledgeBase 的组件，
    但编排自己的板块感知循环，而非使用 BreadthExpander/FeedbackLoop。
    """

    def __init__(self, config_snapshot: dict):
        self._snap = config_snapshot
        self._fatigue = FatigueTracker()

    async def execute(
        self,
        crawl_plan: DigestCrawlPlan,
        section_documents: list,
        all_results: list,
        seen_urls: set,
        shared_crawler,
        history_engine,
        content_dedup,
        config,
        task: dict,
    ) -> OptimizationResult:
        budget_start = time.monotonic()
        task_id = task.get("id", 0)

        # 1. 结果到板块映射
        section_map = self._map_results_to_sections(all_results, crawl_plan)

        # 2. 初始化组件
        from ai import content_organizer as organizer
        from optimization.evaluator import CoverageEvaluator
        from optimization.strategy import BreadthStrategyGen, DepthStrategyGen, SearchStrategy
        from optimization.knowledge_base import KnowledgeBase
        from optimization.utils import save_optimization_round

        evaluator = CoverageEvaluator(organizer if organizer.is_available else None)
        breadth_gen = BreadthStrategyGen()
        depth_gen = DepthStrategyGen()
        kb = KnowledgeBase()

        ctx = {
            "engine": self._snap.get("engine", "sogou"),
            "time_range": "week",
            "config": config,
            "crawler": shared_crawler,
            "task_type": "digest",
            "section_result_counts": self._section_result_counts(section_map, crawl_plan),
        }
        target_score = self._snap.get(
            "digest_optimization_target_score",
            settings.digest_optimization_target_score,
        )

        # 3. 全局评估
        from crawler.digest import _extract_digest_keyword
        eval_keyword = _extract_digest_keyword(self._raw_sections(crawl_plan)) or "技术日报"
        global_eval = await self._safe_evaluate(
            evaluator, eval_keyword, all_results, ctx,
        )
        if not global_eval:
            return OptimizationResult(
                all_results=all_results,
                section_documents=list(section_documents),
                seen_urls=seen_urls,
            )

        logger.info(
            "[OptAgent] Initial: overall=%.2f, sections=%d, results=%d",
            global_eval.overall_score, len(crawl_plan.sections), len(all_results),
        )

        # 4. 板块级评估 + 识别弱板块
        section_evals = await self._evaluate_per_section(
            section_map, crawl_plan, evaluator, ctx,
        )
        weak_sections = self._identify_weak_sections(
            section_evals, global_eval, crawl_plan, target_score,
        )

        if not weak_sections:
            logger.info("[OptAgent] No weak sections, skipping optimization")
            return OptimizationResult(
                all_results=all_results,
                section_documents=list(section_documents),
                seen_urls=seen_urls,
            )

        logger.info(
            "[OptAgent] Found %d weak sections: %s",
            len(weak_sections),
            ", ".join(f"{ws.section.name}({','.join(ws.weakest_dimensions[:2])})" for ws in weak_sections),
        )

        # 5. 定向重爬循环
        rounds_done = 0
        sections_improved = 0
        strategy_history: list = []
        self._fatigue.reset()

        # 跨运行疲劳预填充：从 KB 读取最近运行的趋势
        # 只预填 window-1 次 False，保留 1 次机会避免维度被直接跳过
        try:
            cross_run_fatigue = await kb.get_recent_dimension_fatigue(limit=3)
            for dim, scores in cross_run_fatigue.items():
                prefill_count = max(0, self._fatigue._window - 2)  # window=2 → 0 次预填，保留完整机会
                for _ in range(prefill_count):
                    self._fatigue.record(dim, False)
                logger.info(
                    "[OptAgent] Cross-run fatigue pre-filled for '%s' (%d/%d): %s",
                    dim, prefill_count, self._fatigue._window,
                    [f"{s:.2f}" for s in scores],
                )
        except Exception as e:
            logger.debug("[OptAgent] Cross-run fatigue check failed: %s", e)

        max_rounds = max(
            1,
            int(self._snap.get(
                "optimization_max_rounds",
                settings.optimization_max_rounds or _MAX_OPT_ROUNDS,
            ) or _MAX_OPT_ROUNDS),
        )
        deadline = time.monotonic() + self._optimization_budget_seconds()
        for round_num in range(1, max_rounds + 1):
            if time.monotonic() >= deadline:
                logger.info("[OptAgent] Budget exhausted at round %d", round_num)
                break

            urls_before = len(all_results)
            round_improved = 0

            for ws in weak_sections:
                if time.monotonic() >= deadline:
                    break
                added = await self._recrawl_section(
                    ws, evaluator, breadth_gen, depth_gen, kb, organizer,
                    all_results, seen_urls, section_documents, content_dedup,
                    ctx, strategy_history, round_num, deadline,
                )
                # 能力 4: 记录维度改善结果
                for dim in ws.weakest_dimensions:
                    self._fatigue.record(dim, added > 0)
                if added > 0:
                    round_improved += 1

            # 重新映射 + 全局评估。补爬结果会改变板块分布，不能沿用初始 section_map。
            section_map = self._map_results_to_sections(all_results, crawl_plan)
            ctx["section_result_counts"] = self._section_result_counts(section_map, crawl_plan)
            prev_score = global_eval.overall_score
            global_eval = await self._safe_evaluate(
                evaluator, eval_keyword, all_results, ctx,
            )

            # 轮次间重新评估弱维度，避免用过时目标浪费预算
            section_evals = await self._evaluate_per_section(
                section_map, crawl_plan, evaluator, ctx,
            )
            next_weak_sections = self._identify_weak_sections(
                section_evals, global_eval, crawl_plan, target_score,
            )

            rounds_done = round_num
            delta = (global_eval.overall_score - prev_score) if global_eval else 0
            sections_improved += round_improved

            # 能力 5: 全局优化轮次 KB 保存（关键词与评分语义一致）
            if global_eval:
                weak_desc = (
                    ", ".join(
                        f"{ws.section.name}({','.join(ws.weakest_dimensions[:2])})"
                        for ws in next_weak_sections
                    )
                    if next_weak_sections
                    else "all sections met target"
                )
                global_strategy = SearchStrategy(
                    keyword=eval_keyword,
                    engine=ctx.get("engine", "sogou"),
                    time_range=ctx.get("time_range", "week"),
                    strategy_type="digest_section_opt",
                    reason=f"Round {round_num}: optimized {round_improved} sections — {weak_desc}",
                )
                opt_round = _OptRound(
                    round_num=round_num,
                    evaluation=global_eval,
                    strategy=global_strategy,
                    urls_before=urls_before,
                    urls_after=len(all_results),
                    score_delta=delta,
                )
                await save_optimization_round(task_id, opt_round)

            logger.info(
                "[OptAgent] Round %d: score=%.2f→%.2f (delta=%.3f), +%d URLs, %d sections improved",
                round_num, prev_score,
                global_eval.overall_score if global_eval else 0,
                delta, len(all_results) - urls_before, round_improved,
            )

            weak_sections = next_weak_sections
            if not weak_sections:
                logger.info("[OptAgent] All sections meet target after round %d", round_num)
                break

            # 收敛检测（至少 2 轮后才判断收敛）
            if delta < 0.01 and round_num >= 2:
                logger.info("[OptAgent] Converged at round %d (delta=%.3f)", round_num, delta)
                break

        budget_used = time.monotonic() - budget_start

        return OptimizationResult(
            all_results=all_results,
            section_documents=list(section_documents),
            seen_urls=seen_urls,
            rounds_completed=rounds_done,
            sections_improved=sections_improved,
            budget_used_seconds=budget_used,
        )

    def _optimization_budget_seconds(self) -> float:
        """Reserve enough post-evaluation time for actual recrawl attempts."""
        return max(90.0, settings.optimization_total_budget_seconds * 0.6)

    # ============== 结果到板块映射 ==============

    def _map_results_to_sections(
        self, results: list, crawl_plan: DigestCrawlPlan,
    ) -> dict[str, list]:
        """将扁平结果列表映射到板块名称 → 结果列表

        三层匹配：
          Layer 1: metadata.search_keyword 匹配 section.keywords
          Layer 2: URL 域名匹配 section.url_sources/rss_sources
          Layer 3: 未匹配结果贡献给所有板块
        """
        section_map: dict[str, list] = {s.name: [] for s in crawl_plan.sections}

        # 预计算板块匹配索引
        kw_to_section: dict[str, str] = {}
        domain_to_sections: dict[str, list[str]] = {}
        for s in crawl_plan.sections:
            for kw in s.keywords:
                kw_to_section[kw.lower()] = s.name
            for src in s.url_sources:
                domain = self._extract_domain(src.get("url", ""))
                if domain:
                    domain_to_sections.setdefault(domain, []).append(s.name)
            for src in s.rss_sources:
                domain = self._extract_domain(src.get("feed_url", "") or src.get("url", ""))
                if domain:
                    domain_to_sections.setdefault(domain, []).append(s.name)

        section_names = set(section_map.keys())
        unmatched = []
        for r in results:
            url = self._get_url(r)
            title = self._get_title(r)

            # Layer 1: keyword
            metadata = getattr(r, "metadata", None) or {}
            search_kw = metadata.get("search_keyword", "")
            if search_kw and search_kw.lower() in kw_to_section:
                section_map[kw_to_section[search_kw.lower()]].append(r)
                continue

            # Layer 1b: title 包含板块关键词
            matched = False
            if title:
                title_lower = title.lower()
                for kw, sec_name in kw_to_section.items():
                    if kw in title_lower:
                        section_map[sec_name].append(r)
                        matched = True
                        break
            if matched:
                continue

            # Layer 2: URL 域名
            domain = self._extract_domain(url)
            if domain and domain in domain_to_sections:
                for sec_name in domain_to_sections[domain]:
                    section_map[sec_name].append(r)
                continue

            # Layer 3: 未匹配
            unmatched.append(r)

        if unmatched:
            try:
                from standalone.task_executor import infer_category
            except Exception:
                infer_category = None

            if infer_category:
                for r in unmatched:
                    inferred = infer_category(self._get_url(r), self._get_title(r))
                    if inferred in section_names:
                        section_map[inferred].append(r)

        return section_map

    @staticmethod
    def _section_result_counts(
        section_map: dict[str, list],
        crawl_plan: DigestCrawlPlan,
    ) -> dict[str, int]:
        return {
            section.name: len(section_map.get(section.name, []))
            for section in crawl_plan.sections
        }

    # ============== 板块级评估 ==============

    async def _evaluate_per_section(
        self,
        section_map: dict[str, list],
        crawl_plan: DigestCrawlPlan,
        evaluator,
        ctx: dict,
    ) -> dict[str, "CoverageEvaluation"]:
        """对每个板块独立评估覆盖率"""
        results = {}
        for section in crawl_plan.sections:
            sec_results = section_map.get(section.name, [])
            if not sec_results:
                continue
            keyword = section.keywords[0] if section.keywords else section.name
            ev = await self._safe_evaluate(evaluator, keyword, sec_results, ctx)
            if ev:
                results[section.name] = ev
        return results

    def _identify_weak_sections(
        self,
        section_evals: dict[str, "CoverageEvaluation"],
        global_eval: "CoverageEvaluation",
        crawl_plan: DigestCrawlPlan,
        target_score: float,
    ) -> list[WeakSection]:
        """识别低于目标分数的板块及其最弱维度"""
        weak = []
        for section in crawl_plan.sections:
            eval_ = section_evals.get(section.name)
            if not eval_:
                from optimization.evaluator import CoverageEvaluation
                eval_ = CoverageEvaluation(
                    overall_score=0.0,
                    source_diversity=0.0,
                    depth_coverage=0.0,
                    angle_coverage=0.0,
                    temporal_coverage=0.0,
                    perspective_balance=0.0,
                    language_coverage=0.0,
                    weaknesses=["section has no valid results"],
                    suggestions=["补充该板块的信息源或放宽搜索策略"],
                )
            if eval_.overall_score >= target_score:
                continue

            dims = {
                "source_diversity": eval_.source_diversity,
                "perspective": eval_.perspective_balance,
                "language": eval_.language_coverage,
                "depth": eval_.depth_coverage,
                "angle": eval_.angle_coverage,
                "temporal": eval_.temporal_coverage,
            }
            sorted_dims = sorted(dims.items(), key=lambda x: x[1])
            weakest = [d for d, s in sorted_dims[:2] if s < 0.6]

            weak.append(WeakSection(
                section=section,
                evaluation=eval_,
                weakest_dimensions=weakest or [sorted_dims[0][0]],
            ))
        return weak

    # ============== 定向重爬 ==============

    async def _recrawl_section(
        self,
        weak_section: WeakSection,
        evaluator,
        breadth_gen,
        depth_gen,
        kb,
        organizer,
        all_results: list,
        seen_urls: set,
        section_documents: list,
        content_dedup,
        ctx: dict,
        strategy_history: list,
        round_num: int,
        deadline: float,
    ) -> int:
        """对单个弱板块执行定向重爬，返回新增结果数"""
        section = weak_section.section
        ws_eval = weak_section.evaluation
        engine = section.engine or ctx.get("engine", "sogou")
        keyword = section.keywords[0] if section.keywords else section.name

        # 获取 KB hint（含板块级引擎推荐）
        kb_hint = {}
        try:
            kb_hint = await kb.get_strategy_hint(
                keyword, engine, section.time_range,
            )
        except Exception as e:
            logger.debug("[OptAgent] KB hint failed for '%s': %s", section.name, e)

        # 能力 5B: 板块级 similar_keyword 查询，覆盖引擎选择
        try:
            similar = await kb.get_similar_keyword_strategies(keyword, limit=3)
            if similar:
                best_engine = similar[0].get("search_engine")
                if best_engine and best_engine != engine:
                    engine = best_engine
                    logger.debug("[OptAgent] Section '%s': using KB-recommended engine %s",
                                 section.name, engine)
        except Exception:
            pass

        # 过滤已耗尽的维度（能力 4）
        active_dims = [d for d in weak_section.weakest_dimensions
                       if not self._fatigue.is_exhausted(d)]
        if not active_dims:
            logger.debug("[OptAgent] All dimensions exhausted for '%s'", section.name)
            return 0

        # 选择策略生成器
        has_breadth = any(d in _BREADTH_DIMS for d in active_dims)
        has_depth = any(d in _DEPTH_DIMS for d in active_dims)

        # 构建板块 dict（供 source_expand 策略使用）
        section_dicts = [self._planned_to_raw_dict(section)]

        strategy = None
        if has_breadth:
            strategy = breadth_gen.generate(
                keyword=keyword,
                evaluation=ws_eval,
                current_engine=engine,
                current_time_range=section.time_range,
                round_num=round_num,
                history=strategy_history,
                kb_hint=kb_hint,
                sections=section_dicts,
            )
        if strategy is None and has_depth:
            strategy = depth_gen.generate(
                keyword=keyword,
                evaluation=ws_eval,
                current_engine=engine,
                current_time_range=section.time_range,
                round_num=round_num,
                history=strategy_history,
                kb_hint=kb_hint,
            )

        if strategy is None:
            logger.debug("[OptAgent] No strategy for section '%s'", section.name)
            return 0

        # 能力 1: 跨语言扩展
        if strategy.strategy_type == "cross_language":
            from optimization.bubble_breaker import BubbleBreaker
            breaker = BubbleBreaker(organizer)
            translated = await breaker.translate_keyword(strategy.keyword)
            if translated:
                from optimization.strategy import SearchStrategy
                strategy = SearchStrategy(
                    keyword=translated, engine=strategy.engine,
                    time_range=strategy.time_range, strategy_type="cross_language",
                    reason=strategy.reason,
                )
                logger.info("[OptAgent] Cross-language for '%s': '%s' → '%s'",
                            section.name, keyword, translated)
            else:
                logger.debug("[OptAgent] Cross-language translation failed for '%s'", section.name)
                return 0

        # 执行爬取（分 source_expand 和 keyword 两条路径）
        new_results = []
        try:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return 0

            async def _crawl_with_strategy():
                crawled = []
                # 能力 2: source_expand — 利用板块已配置的 URL/RSS 源
                if strategy.strategy_type == "source_expand" and strategy.source_expand_section:
                    from crawler.digest import apply_overrides
                    from crawler.source_crawler import crawl_url_sources, crawl_rss_sources

                    sec = apply_overrides(strategy.source_expand_section, strategy.source_expand_overrides)
                    if sec.get("url_sources"):
                        crawled.extend(await crawl_url_sources(sec, ctx["config"], ctx["crawler"]))
                    if sec.get("rss_sources"):
                        crawled.extend(await crawl_rss_sources(sec, ctx["config"], ctx["crawler"]))
                else:
                    from crawler.search import crawl_by_keyword
                    crawled = await crawl_by_keyword(
                        keyword=strategy.keyword,
                        engine=strategy.engine,
                        max_results=_MAX_RECRAWL_RESULTS,
                        time_range=strategy.time_range,
                        config=ctx.get("config"),
                        crawler=ctx.get("crawler"),
                        skip_dedup=True,
                    )
                return crawled

            new_results = await asyncio.wait_for(_crawl_with_strategy(), timeout=remaining)
        except asyncio.TimeoutError:
            logger.info("[OptAgent] Recrawl timed out for '%s' within optimization budget", section.name)
            return 0
        except Exception as e:
            logger.warning("[OptAgent] Recrawl failed for '%s': %s", section.name, e)
            return 0

        if not new_results:
            return 0

        strategy_history.append(strategy)

        # 合并结果 + 更新 SectionDocument
        before_merge_count = len(all_results)
        added = self._merge_optimized_results(
            new_results, all_results, seen_urls, content_dedup,
        )
        merged_results = all_results[before_merge_count:]

        if added > 0:
            section.result_count += added
            doc = self._find_section_document(section_documents, section.name)
            if doc:
                self._rebuild_section_document(doc, merged_results, added)
            logger.debug(
                "[OptAgent] Section '%s': +%d results (strategy=%s, engine=%s)",
                section.name, added, strategy.strategy_type, strategy.engine,
            )

        return added

    # ============== SectionDocument 更新 ==============

    def _rebuild_section_document(
        self, doc: SectionDocument, new_results: list, added: int = 0,
    ):
        """将重爬结果追加到 SectionDocument（heuristic 清洗 + URL 规范化去重）"""
        from crawler.config import _filter_breadcrumbs, _filter_boilerplate, _filter_nav_noise
        from crawler.utils import normalize_url

        # 用规范化 URL 构建已存在集合，避免 http/https/www 等变体重复
        existing_urls = {normalize_url(e.url) for e in doc.entries if e.url}

        for r in new_results:
            content = getattr(r, "markdown", None) or (r.get("markdown", "") if isinstance(r, dict) else "")
            if not content or len(content) < 100:
                continue
            title = getattr(r, "title", None) or (r.get("title", "") if isinstance(r, dict) else "")
            url = getattr(r, "url", None) or (r.get("url", "") if isinstance(r, dict) else "")

            cleaned = _filter_breadcrumbs(content)
            cleaned = _filter_boilerplate(cleaned)
            cleaned = _filter_nav_noise(cleaned)
            if len(cleaned) < 100:
                continue

            # 去重：用规范化 URL 比较
            if not url or normalize_url(url) in existing_urls:
                continue
            existing_urls.add(normalize_url(url))

            doc.entries.append(SourceEntry(
                url=url,
                title=title,
                cleaned_content=cleaned,
                source_type="optimization",
                word_count=len(cleaned.split()),
            ))

        doc.cleaned_count = len(doc.entries)
        doc.total_word_count = sum(e.word_count for e in doc.entries)
        doc.merged_content = "\n\n---\n\n".join(e.cleaned_content for e in doc.entries)
        doc.source_count = doc.source_count + added

    def _merge_optimized_results(
        self, results: list, all_results: list, seen_urls: set, content_dedup,
    ) -> int:
        """合并重爬结果到全局列表（委托公共函数）"""
        from crawler.dedup import merge_results_into
        return merge_results_into(results, seen_urls, all_results, content_dedup)

    # ============== 辅助方法 ==============

    async def _safe_evaluate(self, evaluator, keyword, results, ctx):
        """安全评估，失败返回 None"""
        if not results:
            return None
        try:
            return await evaluator.evaluate(keyword, results, ctx)
        except Exception as e:
            logger.warning("[OptAgent] Evaluation failed: %s", e)
            return None

    @staticmethod
    def _find_section_document(docs: list, section_name: str):
        """查找板块对应的 SectionDocument"""
        for doc in docs:
            if getattr(doc, "section_name", "") == section_name:
                return doc
        return None

    @staticmethod
    def _planned_to_raw_dict(section: PlannedSection) -> dict:
        """将 PlannedSection 转为 dict（供 BreadthStrategyGen._strategy_source_expand 使用）"""
        sec = {
            "name": section.name,
            "source_type": section.source_type,
            "max_items": section.max_items,
            "effectiveness": section.effectiveness,
        }
        if section.url_sources:
            sec["url_sources"] = section.url_sources
        if section.rss_sources:
            sec["rss_sources"] = section.rss_sources
        return sec

    # ============== 辅助方法 ==============

    @staticmethod
    def _raw_sections(crawl_plan: DigestCrawlPlan) -> list[dict]:
        """将 PlannedSection 转为 dict（供 _extract_digest_keyword 使用）"""
        result = []
        for s in crawl_plan.sections:
            sec = {"name": s.name, "source_type": s.source_type, "keyword": ""}
            if s.keywords:
                sec["keyword"] = " OR ".join(s.keywords)
            result.append(sec)
        return result

    @staticmethod
    def _get_url(r) -> str:
        return getattr(r, "url", None) or (r.get("url", "") if isinstance(r, dict) else "")

    @staticmethod
    def _get_title(r) -> str:
        return getattr(r, "title", None) or (r.get("title", "") if isinstance(r, dict) else "")

    @staticmethod
    def _get_content(r) -> str:
        return getattr(r, "markdown", None) or (r.get("markdown", "") if isinstance(r, dict) else "")

    @staticmethod
    def _extract_domain(url: str) -> str:
        try:
            parsed = urlparse(url)
            return parsed.netloc.lower().lstrip("www.")
        except Exception:
            return ""
