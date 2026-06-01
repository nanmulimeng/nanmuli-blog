"""爬虫 Agent — 接收总管调度的 SourceCrawlPlan，执行具体内容爬取

由 DigestOrchestrator 在收集所有 SourceAgent 报告后创建和调度。
负责：keyword 搜索、URL 直爬、RSS 解析、fallback 降级。
"""

import asyncio
import logging
from dataclasses import dataclass, field

from config import settings
from crawler.digest_orchestrator import PlannedSection
from crawler.source_agent import SourceCrawlPlan

logger = logging.getLogger(__name__)


@dataclass
class CrawlerAgentResult:
    """爬虫 Agent 执行结果"""
    section_name: str
    success: bool
    results: list = field(default_factory=list)
    error: str | None = None
    fallback_used: bool = False
    section_document: "SectionDocument | None" = None


class CrawlerAgent:
    """爬虫 Agent：按 SourceCrawlPlan 执行内容爬取

    由总管 Agent 在分析阶段完成后创建和调度。
    不做信息源分析（那是 SourceAgent 的职责），只负责执行爬取。
    """

    def __init__(self, section: PlannedSection, crawl_plan: SourceCrawlPlan,
                 config, config_snapshot: dict):
        self.section = section
        self.crawl_plan = crawl_plan
        self.config_snapshot = config_snapshot
        self._config = self._copy_config(config)

    async def execute(self, crawler, history_engine) -> CrawlerAgentResult:
        """执行爬取：按计划爬取活跃源，零结果时 fallback，生成清洗文档"""
        from crawler.section_document import SectionDocument
        self.section.status = "crawling"

        try:
            results = await self._crawl(crawler, history_engine)
            fallback_used = False

            if not results:
                logger.info("[CrawlerAgent] Section '%s' got 0 results, triggering fallback",
                            self.section.name)
                fallback_results = await self._fallback(crawler, history_engine)
                if fallback_results:
                    results = fallback_results
                    fallback_used = True

            success = bool(results)
            self.section.status = "ok" if success else "failed"

            doc = await self._build_section_document(results) if success else None

            return CrawlerAgentResult(
                section_name=self.section.name,
                success=success,
                results=results,
                fallback_used=fallback_used,
                section_document=doc,
            )

        except asyncio.CancelledError:
            self.section.status = "cancelled"
            raise
        except Exception as e:
            self.section.status = "failed"
            logger.warning("[CrawlerAgent] Section '%s' failed: %s", self.section.name, e)
            return CrawlerAgentResult(
                section_name=self.section.name,
                success=False,
                results=[],
                error=str(e),
            )

    async def _crawl(self, crawler, history_engine) -> list:
        """核心爬取：keyword 搜索 + URL 直爬 + RSS 解析"""
        from crawler.search import crawl_by_keyword
        from crawler.source_crawler import crawl_url_sources, crawl_rss_sources
        from crawler.dedup import dedup_results

        plan = self.crawl_plan
        results = []

        # keyword 搜索：逐个活跃关键词独立搜索
        if plan.active_keywords:
            total_budget = plan.adjusted_max_items * settings.digest_section_result_multiplier
            kw_count = len(plan.active_keywords)
            base_per_kw = max(3, total_budget // kw_count)
            remainder = total_budget - base_per_kw * kw_count
            for i, kw in enumerate(plan.active_keywords):
                per_kw_max = base_per_kw + (1 if i < remainder else 0)
                try:
                    kw_results = await crawl_by_keyword(
                        keyword=kw,
                        engine=plan.recommended_engine,
                        max_results=per_kw_max,
                        time_range=self.section.time_range,
                        config=self._config,
                        crawler=crawler,
                        skip_dedup=True,
                    )
                    results.extend(kw_results)
                except Exception as e:
                    logger.warning("[CrawlerAgent] Keyword '%s' search failed: %s", kw, e)
                await asyncio.sleep(1)

        # URL 直爬（仅活跃源）
        if plan.active_url_sources:
            url_sec = self._to_raw_section()
            url_results = await crawl_url_sources(url_sec, self._config, crawler)
            results.extend(url_results)

        # RSS Feed（仅活跃源）
        if plan.active_rss_sources:
            rss_sec = self._to_raw_section()
            rss_results = await crawl_rss_sources(rss_sec, self._config, crawler)
            results.extend(rss_results)

        return dedup_results(results, history_engine=history_engine)

    async def _fallback(self, crawler, history_engine) -> list:
        """零结果降级：换引擎 + 放宽时间范围"""
        from crawler.search import crawl_by_keyword
        from crawler.dedup import dedup_results

        plan = self.crawl_plan
        if not plan.active_keywords:
            return []

        fallback_engines = ["bing", "sogou", "baidu"]
        fallback_engine = next(
            (e for e in fallback_engines if e != plan.recommended_engine), "bing"
        )

        time_map = {"day": "week", "week": "month", "month": "year", "year": "all"}
        fallback_time = time_map.get(self.section.time_range, "month")

        logger.info("[CrawlerAgent] Fallback for '%s': engine=%s→%s, time=%s→%s",
                     self.section.name, plan.recommended_engine, fallback_engine,
                     self.section.time_range, fallback_time)

        results = []
        for kw in plan.active_keywords[:2]:
            try:
                kw_results = await crawl_by_keyword(
                    keyword=kw,
                    engine=fallback_engine,
                    max_results=5,
                    time_range=fallback_time,
                    config=self._config,
                    crawler=crawler,
                    skip_dedup=True,
                )
                results.extend(kw_results)
            except Exception as e:
                logger.debug("[CrawlerAgent] Fallback keyword '%s' failed: %s", kw, e)

        return dedup_results(results, history_engine=history_engine)

    # ============== 板块清洗文档 ==============

    async def _build_section_document(self, results: list):
        """对爬取结果生成清洗文档（AI 优先，降级 heuristic）"""
        from crawler.section_document import SectionDocument, SourceEntry

        doc = SectionDocument(
            section_name=self.section.name,
            source_count=len(results),
        )

        # 准备有内容的条目
        raw_entries = []
        for r in results:
            content = r.markdown if hasattr(r, "markdown") else r.get("markdown", "")
            title = r.title if hasattr(r, "title") else r.get("title", "")
            url = r.url if hasattr(r, "url") else r.get("url", "")
            if self.section.name == "open_source":
                from crawler.digest_gen_agent import _is_open_source_digest_page
                if not _is_open_source_digest_page(url):
                    logger.info("[CrawlerAgent] Skip non-project open_source page: %s", url)
                    continue
            if content and len(content) >= 100:
                raw_entries.append({"url": url, "title": title, "content": content})

        if not raw_entries:
            doc.cleanup_method = "none"
            return doc

        # AI 清洗
        if self._should_use_ai():
            try:
                from ai.organizer import ContentOrganizer
                organizer = ContentOrganizer()
                try:
                    cleaned, tokens, duration = await asyncio.wait_for(
                        organizer.clean_section_content(raw_entries),
                        timeout=settings.ai_section_cleanup_timeout,
                    )
                finally:
                    await organizer.close()
                if cleaned:
                    doc.cleanup_method = "ai"
                    doc.cleanup_tokens_used = tokens
                    doc.cleanup_duration_ms = duration
                    url_to_cleaned = {
                        c["url"]: c["cleaned_content"] for c in cleaned if c.get("url")
                    }
                    for raw_entry in raw_entries:
                        cc = url_to_cleaned.get(raw_entry["url"], raw_entry["content"])
                        doc.entries.append(SourceEntry(
                            url=raw_entry["url"], title=raw_entry["title"],
                            cleaned_content=cc, source_type="unknown",
                            word_count=len(cc.split()),
                        ))
                    self._finalize_document(doc)
                    return doc
            except (asyncio.TimeoutError, Exception) as e:
                logger.warning("[CrawlerAgent] AI cleanup failed for '%s', "
                               "falling back to heuristic: %s", self.section.name, e)

        # Heuristic 回退
        doc.cleanup_method = "heuristic"
        doc.entries = self._heuristic_cleanup(raw_entries)
        self._finalize_document(doc)
        return doc

    def _finalize_document(self, doc):
        """计算聚合字段"""
        doc.cleaned_count = len(doc.entries)
        doc.total_word_count = sum(e.word_count for e in doc.entries)
        doc.merged_content = "\n\n---\n\n".join(e.cleaned_content for e in doc.entries)

    def _should_use_ai(self) -> bool:
        try:
            from ai.config import ai_settings
            return ai_settings.is_configured
        except Exception:
            return False

    @staticmethod
    def _heuristic_cleanup(results: list):
        """复用已有 3 层正则过滤器做 heuristic 清洗"""
        from crawler.config import _filter_breadcrumbs, _filter_boilerplate, _filter_nav_noise
        from crawler.section_document import SourceEntry

        entries = []
        for r in results:
            content = r.markdown if hasattr(r, "markdown") else r.get("markdown", "") or r.get("content", "")
            title = r.title if hasattr(r, "title") else r.get("title", "")
            url = r.url if hasattr(r, "url") else r.get("url", "")
            if not content:
                continue
            cleaned = _filter_breadcrumbs(content)
            cleaned = _filter_boilerplate(cleaned)
            cleaned = _filter_nav_noise(cleaned)
            if len(cleaned) < 100:
                continue
            entries.append(SourceEntry(
                url=url, title=title,
                cleaned_content=cleaned,
                source_type="unknown",
                word_count=len(cleaned.split()),
            ))
        return entries

    # ============== 辅助方法 ==============

    def _to_raw_section(self) -> dict:
        """将活跃源转为 section dict（供 crawl_url_sources/crawl_rss_sources 使用）"""
        plan = self.crawl_plan
        return {
            "name": self.section.name,
            "source_type": self.section.source_type,
            "max_items": plan.adjusted_max_items,
            "url_sources": plan.active_url_sources,
            "rss_sources": plan.active_rss_sources,
        }

    @staticmethod
    def _copy_config(config):
        """深拷贝配置"""
        from crawler.digest import copy_config
        return copy_config(config)
