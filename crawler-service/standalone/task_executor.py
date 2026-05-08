"""异步任务执行器（爬取 + AI 整理）"""

import asyncio
import datetime
import json
import logging
import os
from typing import Dict

from config import settings
from standalone.models import TaskStatus
from standalone import repository as repo

logger = logging.getLogger(__name__)


class TaskExecutor:
    """管理异步爬取 + AI 整理任务"""

    def __init__(self, max_concurrent: int = 3):
        self._running: Dict[int, asyncio.Task] = {}
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def submit(self, task_id: int):
        if task_id in self._running:
            raise ValueError(f"Task {task_id} is already running")

        async_task = asyncio.create_task(self._execute_with_semaphore(task_id))
        self._running[task_id] = async_task
        # 清理在 _execute 末尾主动完成，done_callback 作为安全兜底
        async_task.add_done_callback(lambda t: self._running.pop(task_id, None))

    async def _execute_with_semaphore(self, task_id: int):
        async with self._semaphore:
            try:
                await self._execute(task_id)
            finally:
                # 主动清理，避免 retry 时 done_callback 延迟导致竞态
                self._running.pop(task_id, None)

    async def shutdown(self):
        """取消所有运行中的任务，将其标记为 FAILED"""
        task_ids = list(self._running.keys())
        for tid in task_ids:
            task = self._running.get(tid)
            if task and not task.done():
                task.cancel()
        if task_ids:
            await asyncio.gather(*[self._running.pop(tid, asyncio.sleep(0)) for tid in task_ids], return_exceptions=True)
            for tid in task_ids:
                try:
                    await repo.fail_task(tid, "Service shutting down")
                except Exception:
                    pass
        logger.info("TaskExecutor shutdown: %d tasks cancelled", len(task_ids))

    async def _execute(self, task_id: int):
        from crawler.single import crawl_single_page
        from crawler.deep import crawl_deep_pages
        from crawler.search import crawl_by_keyword
        from crawler.config import get_browser_config, RunParams
        from api.crawl import CrawlConfig
        from crawl4ai import AsyncWebCrawler

        task = await repo.get_task(task_id)
        if not task:
            return

        try:
            await repo.update_task_status(task_id, TaskStatus.CRAWLING)

            # 从 DB 恢复用户提交的 config
            config_json = task.get("crawl_config")
            if config_json:
                config = CrawlConfig.model_validate_json(config_json)
            else:
                config = CrawlConfig()

            params = RunParams(config)

            # ========== Phase 1: 爬取 ==========
            if task["task_type"] == "single":
                browser_config = get_browser_config(
                    text_mode=params.text_mode, light_mode=params.light_mode,
                    proxy=settings.proxy_url,
                )
                async with AsyncWebCrawler(config=browser_config) as crawler:
                    result = await crawl_single_page(url=task["source_url"], config=config, crawler=crawler)
                results = [result]

            elif task["task_type"] == "deep":
                browser_config = get_browser_config(
                    text_mode=params.text_mode, light_mode=params.light_mode,
                    proxy=settings.proxy_url,
                )
                async with AsyncWebCrawler(config=browser_config) as crawler:
                    results = await crawl_deep_pages(
                        url=task["source_url"],
                        max_depth=task["max_depth"],
                        max_pages=task["max_pages"],
                        config=config,
                        crawler=crawler
                    )

            elif task["task_type"] == "keyword":
                results = await self._execute_keyword_crawl(task, config)

            elif task["task_type"] == "digest":
                results = await self._execute_digest_crawl(task, config)

            else:
                await repo.fail_task(task_id, f"Unknown task type: {task['task_type']}")
                return

            # 质量过滤（日报跳过：来源已由搜索结果保证质量）
            if task["task_type"] != "digest":
                results = self._filter_low_quality(results)

            # 保存爬取结果
            total_words = await repo.save_pages(task_id, results)

            success_count = sum(1 for r in results if r.success)
            crawl_duration = sum(r.crawl_time_ms for r in results)

            if success_count == 0:
                error = next((r.error_message for r in results if r.error_message), "所有页面爬取失败")
                await repo.fail_task(task_id, error)
                return

            # 更新爬取统计（不改变状态，进入 AI 阶段）
            await repo.complete_crawl(
                task_id,
                total_pages=len(results),
                completed_pages=success_count,
                crawl_duration=crawl_duration,
                total_word_count=total_words
            )

            logger.info("Task %d crawl done: %d/%d pages, %d words. Starting AI organization.",
                        task_id, success_count, len(results), total_words)

            # ========== Phase 2: AI 整理 ==========
            await repo.update_task_status(task_id, TaskStatus.PROCESSING)
            ai_success = await self._organize_with_ai(task_id, task, results)
            if not ai_success:
                logger.warning("Task %d AI organization failed, task still marked complete with raw content.", task_id)

            await repo.complete_task(task_id)
            logger.info("Task %d completed.", task_id)

        except Exception as e:
            logger.error("Task %d failed: %s", task_id, e, exc_info=True)
            await repo.fail_task(task_id, str(e))

    async def _execute_keyword_crawl(self, task: dict, config) -> list:
        """关键词搜索爬取（含 AI 关键词优化/扩展）"""
        from ai import content_organizer as organizer

        keyword = task["keyword"]
        engine = task.get("search_engine", "sogou")
        max_pages = task.get("max_pages", 10)

        keywords = [keyword]
        optimized_keyword = None

        # AI 关键词优化
        if organizer.is_available:
            try:
                optimized = await organizer.optimize_keyword(keyword)
                if optimized and optimized != keyword:
                    optimized_keyword = optimized
                    keywords = [optimized]
                    logger.info("Keyword optimized: '%s' -> '%s'", keyword, optimized)
            except Exception as e:
                logger.warning("Keyword optimization failed: %s", e)

            # AI 关键词扩展
            try:
                expanded = await organizer.expand_keywords(keywords[0])
                for kw in expanded:
                    if kw.lower() not in {k.lower() for k in keywords}:
                        keywords.append(kw)
                        if len(keywords) >= 4:
                            break
                logger.info("Keywords expanded to %d variants: %s", len(keywords), keywords)
            except Exception as e:
                logger.warning("Keyword expansion failed: %s", e)

        # 保存 AI 搜索元数据
        await repo.save_ai_search_metadata(task["id"], {
            "originalKeyword": keyword,
            "optimizedKeyword": optimized_keyword,
            "searchVariants": keywords,
        })

        # 对每个关键词搜索，合并去重
        seen_urls = set()
        all_results = []
        consecutive_no_new = 0

        for kw in keywords:
            before = len(all_results)
            try:
                results = await crawl_by_keyword(
                    keyword=kw, engine=engine,
                    max_results=max(8, max_pages),
                    time_range="week", config=config
                )
                for r in results:
                    url = getattr(r, "url", None)
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        all_results.append(r)

                new = len(all_results) - before
                logger.info("Keyword '%s' added %d new URLs (total=%d/%d)",
                            kw, new, len(all_results), max_pages)

                if len(keywords) > 1 and new == 0:
                    consecutive_no_new += 1
                    if consecutive_no_new >= 2:
                        break
                else:
                    consecutive_no_new = 0

                if len(all_results) >= max_pages:
                    break

                if len(keywords) > 1:
                    await asyncio.sleep(2)

            except Exception as e:
                logger.warning("Keyword search failed for '%s': %s", kw, e)

        return all_results[:max_pages]

    async def _execute_digest_crawl(self, task: dict, config) -> list:
        """日报板块爬取（含跨日去重）"""
        from crawler.search import crawl_by_keyword
        from crawler.dedup import DedupEngine, dedup_results

        sections = get_digest_sections()
        if not sections:
            raise ValueError("日报功能未配置")

        # 构建跨日去重引擎：加载上一次成功日报的 URL/标题
        history_engine = await self._build_digest_history_engine()

        seen_urls = set()
        all_results = []
        engine = settings.digest_search_engine
        completed_count = 0

        for i, section in enumerate(sections):
            config_copy = copy_config(config)

            try:
                results = await crawl_by_keyword(
                    keyword=section["keyword"],
                    engine=engine,
                    max_results=section.get("max_items", 5) * 2,
                    time_range=section.get("time_range", "week"),
                    config=config_copy
                )

                # 板块内去重
                results = dedup_results(results, history_engine=history_engine)

                new = 0
                for r in results:
                    url = getattr(r, "url", None)
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        all_results.append(r)
                        new += 1

                completed_count += new
                logger.info("Digest section '%s' added %d new URLs (total=%d)",
                            section["name"], new, len(all_results))

                await repo.update_task_progress(task["id"], completed_count)

                if i < len(sections) - 1:
                    await asyncio.sleep(2)

            except Exception as e:
                logger.warning("Digest section '%s' failed: %s", section["name"], e)

        return all_results

    async def _build_digest_history_engine(self):
        """从上一次成功日报中加载 URL/标题指纹，用于跨日去重"""
        from crawler.dedup import DedupEngine

        engine = DedupEngine()
        try:
            records, _ = await repo.list_tasks(task_type="digest", page=1, size=1)
            for r in records:
                if r.get("status") != TaskStatus.COMPLETED:
                    continue
                pages = await repo.get_pages_by_task(r["id"])
                for p in pages:
                    url = p.get("url", "")
                    title = p.get("page_title", "")
                    if url:
                        engine.add_reference(url, title=title)
                logger.info("Loaded %d history URLs from digest task %d", len(pages), r["id"])
                break  # 只取最近一次
        except Exception as e:
            logger.warning("Failed to load digest history for dedup: %s", e)
        return engine

    async def _organize_with_ai(self, task_id: int, task: dict, crawl_results: list) -> bool:
        """AI 内容整理（含重试）"""
        from ai import content_organizer as organizer
        from ai.organizer import (
            PageContent, DigestPageContent,
            OrganizerError, RateLimitError, TruncatedError, UnrecoverableError, InvalidOutputError,
        )

        if not organizer.is_available:
            logger.info("AI not configured, skipping organization for task %d", task_id)
            await repo.save_ai_error(task_id, "AI not configured")
            return False

        template = task.get("ai_template", "tech_summary")
        task_type = task["task_type"]
        max_retries = settings.ai_max_retries

        for attempt in range(max_retries + 1):
            try:
                if task_type == "digest":
                    result = await self._organize_digest(organizer, crawl_results, task)
                    await self._save_digest_result(task_id, task, result)
                else:
                    result = await self._organize_content(organizer, crawl_results, task, template)
                    await repo.save_ai_results(
                        task_id,
                        ai_title=result.title,
                        ai_summary=result.summary,
                        ai_key_points=result.key_points,
                        ai_tags=result.tags,
                        ai_category=getattr(result, "category", ""),
                        ai_full_content=result.full_content,
                        ai_duration=result.duration_ms,
                        ai_tokens_used=result.tokens_used,
                    )
                logger.info("Task %d AI organized: title='%s', duration=%dms, tokens=%d",
                            task_id, result.title, result.duration_ms, result.tokens_used)
                return True

            except (TruncatedError, UnrecoverableError, InvalidOutputError) as e:
                logger.warning("Task %d AI unrecoverable error: %s, skipping retry", task_id, e)
                await repo.save_ai_error(task_id, str(e))
                break

            except RateLimitError as e:
                backoff = 10.0
                logger.warning("Task %d AI rate limited, retry in %.0fs (attempt %d/%d)",
                               task_id, backoff, attempt + 1, max_retries + 1)
                if attempt < max_retries:
                    await asyncio.sleep(backoff)

            except OrganizerError as e:
                backoff = 2 ** attempt
                logger.warning("Task %d AI error, retry in %ds (attempt %d/%d): %s",
                               task_id, backoff, attempt + 1, max_retries + 1, e)
                if attempt < max_retries:
                    await asyncio.sleep(backoff)

            except Exception as e:
                logger.error("Task %d AI unexpected error: %s", task_id, e, exc_info=True)
                if attempt < max_retries:
                    await asyncio.sleep(2 ** attempt)

        await repo.save_ai_error(task_id, "AI organization failed after retries")
        return False

    async def _organize_content(self, organizer, crawl_results, task, template):
        """整理单页/多页内容"""
        from ai.organizer import PageContent

        successful = [r for r in crawl_results if getattr(r, "success", False)]

        if len(successful) == 1:
            r = successful[0]
            markdown = getattr(r, "markdown", None)
            if not markdown:
                raise ValueError("No markdown content to organize")

            # 构建关键词上下文
            keyword_context = None
            metadata_json = task.get("ai_search_metadata")
            if metadata_json:
                try:
                    meta = json.loads(metadata_json)
                    parts = []
                    if meta.get("originalKeyword"):
                        parts.append(f"原始关键词：{meta['originalKeyword']}")
                    if meta.get("optimizedKeyword") and meta["optimizedKeyword"] != meta.get("originalKeyword"):
                        parts.append(f"优化关键词：{meta['optimizedKeyword']}")
                    if meta.get("searchVariants"):
                        parts.append(f"实际搜索词变体：{' | '.join(meta['searchVariants'])}")
                    keyword_context = "\n".join(parts) if parts else None
                except Exception:
                    pass

            return await organizer.organize(markdown, template, keyword_context)

        pages = [
            PageContent(
                url=getattr(r, "url", ""),
                title=getattr(r, "title", ""),
                markdown=getattr(r, "markdown", ""),
                word_count=getattr(r, "word_count", 0),
                depth=getattr(r, "depth", 0),
            )
            for r in successful
        ]

        if not pages:
            raise ValueError("No successful pages to organize")

        return await organizer.organize_multiple(pages, template)

    async def _organize_digest(self, organizer, crawl_results, task):
        """整理日报内容"""
        from ai.organizer import DigestPageContent

        pages = []
        for r in crawl_results:
            if not getattr(r, "success", False):
                continue
            pages.append(DigestPageContent(
                url=getattr(r, "url", ""),
                title=getattr(r, "title", ""),
                markdown=getattr(r, "markdown", ""),
                category=infer_category(getattr(r, "url", ""), getattr(r, "title", "")),
                source_name=extract_source_name(getattr(r, "url", "")),
            ))

        if not pages:
            raise ValueError("No successful pages for digest")

        date = task.get("keyword") or datetime.date.today().isoformat()
        return await organizer.generate_digest(pages, date)

    async def _save_digest_result(self, task_id: int, task: dict, result):
        """将 DigestContent 持久化为结构化数据"""
        digest_date = task.get("keyword") or datetime.date.today().isoformat()
        sections_data = []
        for sec in result.sections:
            items_data = [
                {
                    "title": item.title,
                    "one_liner": item.one_liner,
                    "source_url": item.source_url,
                    "source_name": item.source_name,
                }
                for item in sec.items
            ]
            sections_data.append({
                "category": sec.category,
                "category_name": sec.category_name,
                "emoji": sec.emoji,
                "items": items_data,
            })

        await repo.save_digest_results(
            task_id,
            ai_title=result.title,
            ai_summary=result.summary,
            ai_tags=result.tags,
            ai_full_content=result.full_content,
            ai_duration=result.duration_ms,
            ai_tokens_used=result.tokens_used,
            digest_date=digest_date,
            highlight=result.highlight,
            sections=sections_data,
        )

    def is_running(self, task_id: int) -> bool:
        return task_id in self._running

    @property
    def running_count(self) -> int:
        return len(self._running)

    @staticmethod
    def _filter_low_quality(results: list) -> list:
        """过滤低质量/垃圾内容，避免浪费 AI token"""
        from crawler.quality import evaluate_content

        filtered = []
        for r in results:
            if not getattr(r, "success", False):
                filtered.append(r)
                continue

            url = getattr(r, "url", "")
            title = getattr(r, "title", "") or ""
            markdown = getattr(r, "markdown", "") or ""

            # 内容太短直接标记失败
            if len(markdown) < 100:
                r.success = False
                r.error_message = f"Content too short ({len(markdown)} chars)"
                filtered.append(r)
                continue

            evaluation = evaluate_content(url, title, markdown)
            verdict = evaluation["verdict"]

            if verdict == "reject":
                r.success = False
                r.error_message = f"Low quality content (score={evaluation['final_score']:.0f}, verdict={verdict})"
                logger.info("Filtered low-quality: %s (score=%.0f, reason=%s)",
                            url, evaluation["final_score"], evaluation["source"]["reason"])
            else:
                # 附加评估信息到 metadata
                metadata = getattr(r, "metadata", {}) or {}
                metadata["quality_score"] = evaluation["final_score"]
                metadata["quality_verdict"] = verdict
                r.metadata = metadata

            filtered.append(r)

        return filtered


# ============== Helpers ==============

def extract_source_name(url: str) -> str:
    if not url:
        return "未知来源"
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain or "未知来源"
    except Exception:
        return "未知来源"


def infer_category(url: str, title: str) -> str:
    lower = (url + " " + title).lower()
    if "github" in lower or "开源" in lower:
        return "open_source"
    if "arxiv" in lower or "论文" in lower or "paper" in lower:
        return "paper"
    if "tool" in lower or "工具" in lower:
        return "dev_tool"
    if "news" in lower or "新闻" in lower or "动态" in lower:
        return "hot_trend"
    if "creative" in lower or "创意" in lower or "有趣" in lower or "hackathon" in lower:
        return "creative"
    return "tech_article"


def get_digest_sections() -> list[dict]:
    """获取日报板块配置（优先环境变量 DIGEST_SECTIONS，回退到 config.py）"""
    config_str = os.getenv("DIGEST_SECTIONS", "") or settings.digest_sections
    if config_str:
        try:
            return json.loads(config_str)
        except Exception as e:
            logger.warning("Failed to parse DIGEST_SECTIONS JSON: %s", e)
    return []


def copy_config(config):
    """深拷贝 CrawlConfig"""
    from api.crawl import CrawlConfig
    if config is None:
        return CrawlConfig()
    return config.model_copy(deep=True)


# 全局单例
executor = TaskExecutor(max_concurrent=settings.max_concurrent_tasks)
