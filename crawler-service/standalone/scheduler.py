"""定时日报 + 信息源调度器（APScheduler）"""

import asyncio
import datetime
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config import settings

# 日报生成防重入锁（防止 trigger_digest 并发创建重复日报）
_digest_lock = asyncio.Lock()
from standalone.models import TaskStatus
from standalone import repository as repo
from standalone.task_executor import executor
from standalone import backend_config

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None
_registered_source_jobs: set[str] = set()

# 任务完成事件注册表（供 _wait_and_update_source_status 使用）
_task_completion_events: dict[int, asyncio.Event] = {}


def register_task_event(task_id: int) -> asyncio.Event:
    """注册任务完成事件，供 TaskExecutor 完成时 set"""
    event = asyncio.Event()
    _task_completion_events[task_id] = event
    return event


def notify_task_completion(task_id: int):
    """任务完成时通知等待者"""
    event = _task_completion_events.pop(task_id, None)
    if event:
        event.set()


def parse_cron(expr: str) -> dict:
    """将 5 字段 cron 表达式解析为 APScheduler CronTrigger 参数

    格式: minute hour day month day_of_week
    例: '0 8 * * 1-5' → 工作日 8:00
    """
    parts = expr.strip().split()
    if len(parts) != 5:
        raise ValueError(f"Invalid cron expression (expected 5 fields): {expr}")
    return {
        "minute": parts[0],
        "hour": parts[1],
        "day": parts[2],
        "month": parts[3],
        "day_of_week": parts[4],
    }


# ============== 日报调度 ==============

async def generate_scheduled_digest(force: bool = False):
    """定时日报生成入口

    Args:
        force: 为 True 时跳过防重复检查，允许重新生成当天日报
    """
    if _digest_lock.locked():
        logger.info("Digest generation already in progress, skipping")
        return

    async with _digest_lock:
        today = datetime.date.today().isoformat()
        logger.info("Scheduled digest generation triggered for %s (force=%s)", today, force)

        try:
            # 原子防重复检查：一条 SQL 检查活跃 + 已完成任务
            if not force:
                existing = await repo.get_digest_existing_non_failed(today)
                if existing:
                    logger.info("Digest for %s already exists (task_id=%d, status=%d), skipping.",
                                today, existing["id"], existing["status"])
                    return

            task_id = await repo.create_task(
                task_type="digest",
                ai_template="daily_digest",
                keyword=today,
                digest_date=today,
            )
            await executor.submit(task_id)
            logger.info("Scheduled digest task created: task_id=%d, date=%s", task_id, today)

        except Exception as e:
            logger.error("Scheduled digest generation failed: %s", e, exc_info=True)


# ============== 信息源调度 ==============

async def refresh_source_schedules():
    """从 Java API 拉取带 cron 的活跃信息源，注册/更新 APScheduler 任务。

    每 5 分钟被调度器调用一次，同步源的增删改。
    """
    global _registered_source_jobs

    if _scheduler is None:
        return

    try:
        sources = await _fetch_active_sources()
    except Exception as e:
        logger.warning("Source schedule refresh failed (Java API): %s", e)
        return

    if sources is None:
        return

    # 收集需要调度的源
    scheduled_ids: set[str] = set()
    for src in sources:
        cron_expr = src.get("scheduleCron") or ""
        if not cron_expr or not src.get("isActive", True):
            continue

        source_id = src.get("id")
        if not source_id:
            continue

        job_id = f"source_{source_id}"
        scheduled_ids.add(job_id)

        try:
            cron_params = parse_cron(cron_expr)
            _scheduler.add_job(
                _make_source_job(source_id, src),
                trigger=CronTrigger(**cron_params),
                id=job_id,
                name=f"Source: {src.get('name', source_id)}",
                replace_existing=True,
            )
        except (ValueError, Exception) as e:
            logger.warning("Failed to schedule source %s: %s", source_id, e)

    # 移除不再活跃或已删除的源任务
    stale = _registered_source_jobs - scheduled_ids
    for job_id in stale:
        try:
            _scheduler.remove_job(job_id)
            logger.info("Removed stale source job: %s", job_id)
        except Exception:
            pass

    _registered_source_jobs = scheduled_ids
    if scheduled_ids:
        logger.info("Source schedules refreshed: %d active", len(scheduled_ids))


def _make_source_job(source_id, source_config: dict):
    """创建信息源定时任务的闭包。"""
    async def _run():
        await execute_scheduled_source(source_id, source_config)
    return _run


async def execute_scheduled_source(source_id: int, source_config: dict):
    """定时触发单个信息源爬取。

    1. 根据 source type 创建 Python 任务
    2. 提交到 TaskExecutor（RSS 类型先解析 feed 再逐篇爬取）
    3. 完成后更新源运行状态
    """
    src_type = source_config.get("type", "keyword")
    src_value = source_config.get("value", "")
    crawl_mode = source_config.get("crawlMode", "single")

    if not src_value:
        logger.warning("Source %d has empty value, skipping", source_id)
        return

    # 映射 source type → task type
    if src_type == "url":
        task_type = "deep" if crawl_mode == "deep" else "single"
    elif src_type == "keyword":
        task_type = "keyword"
    elif src_type == "rss":
        task_type = "rss_source"
    else:
        logger.warning("Unknown source type '%s' for source %d", src_type, source_id)
        return

    try:
        if task_type == "rss_source":
            await _execute_rss_source(source_id, source_config)
        else:
            task_id = await repo.create_task(
                task_type=task_type,
                source_url=src_value if src_type == "url" else None,
                keyword=src_value if src_type == "keyword" else None,
                max_depth=source_config.get("maxDepth", 1),
                max_pages=source_config.get("maxPages", 10),
                search_engine=source_config.get("searchEngine", settings.digest_search_engine),
            )
            await executor.submit(task_id)
            logger.info("Scheduled source task: source_id=%d task_id=%d type=%s", source_id, task_id, task_type)
            await _wait_and_update_source_status(source_id, task_id)

    except Exception as e:
        logger.error("Scheduled source %d failed: %s", source_id, e)
        await _update_source_run_status(source_id, "failed", str(e))


async def _wait_and_update_source_status(source_id: int, task_id: int, timeout: float = 300):
    """等待任务完成后更新源运行状态（事件通知 + 指数退避轮询 fallback）"""
    event = _task_completion_events.get(task_id)
    # 退避间隔：2→3→5→5→10→10...
    intervals = [2, 3, 5, 5, 10, 10]
    elapsed = 0.0
    idx = 0

    while elapsed < timeout:
        interval = intervals[min(idx, len(intervals) - 1)]

        # 同时等待 event 和 interval
        try:
            if event is not None:
                await asyncio.wait_for(event.wait(), timeout=interval)
        except asyncio.TimeoutError:
            pass

        elapsed += interval
        idx += 1

        task = await repo.get_task(task_id)
        if not task:
            await _update_source_run_status(source_id, "failed", error="Task not found")
            _task_completion_events.pop(task_id, None)
            return
        status = task.get("status", 0)
        if status == TaskStatus.COMPLETED:
            stats = await _collect_source_stats(task_id)
            await _update_source_run_status(
                source_id, "success",
                quality_score=stats.get("qualityScore"),
                result_count=stats.get("resultCount"),
            )
            _task_completion_events.pop(task_id, None)
            return
        if status == TaskStatus.FAILED:
            error = task.get("error_message", "Unknown error")
            await _update_source_run_status(source_id, "failed", error=error)
            _task_completion_events.pop(task_id, None)
            return

    await _update_source_run_status(source_id, "failed", error="Timeout waiting for task completion")
    _task_completion_events.pop(task_id, None)


async def _collect_source_stats(task_id: int) -> dict:
    """从已完成任务的页面中采集质量统计数据。"""
    import json
    try:
        pages = await repo.get_pages_by_task(task_id)
    except Exception:
        return {"resultCount": 0, "qualityScore": None}

    successful = [p for p in pages if p.get("crawl_status") == 2]
    scores = []
    for p in successful:
        meta = p.get("page_metadata", {})
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except Exception:
                continue
        qs = meta.get("quality_score") if isinstance(meta, dict) else None
        if qs is not None:
            scores.append(float(qs))

    return {
        "resultCount": len(successful),
        "qualityScore": sum(scores) / len(scores) if scores else None,
    }


async def _update_source_run_status(
    source_id: int, status: str, error: str = None,
    quality_score: float = None, result_count: int = None,
):
    """通知 Java 后端更新信息源运行状态（fire-and-forget）。"""
    java_url = settings.java_api_url
    if not java_url:
        return

    url = f"{java_url}/api/internal/collector/sources/{source_id}/run-status"
    headers = {"Content-Type": "application/json"}
    if settings.callback_api_key:
        headers["X-Callback-Key"] = settings.callback_api_key

    payload = {"status": status}
    if error:
        payload["error"] = error[:500]
    if quality_score is not None:
        payload["qualityScore"] = round(quality_score, 1)
    if result_count is not None:
        payload["resultCount"] = result_count

    try:
        import httpx
        async with httpx.AsyncClient(timeout=settings.callback_timeout) as client:
            resp = await client.post(url, json=payload, headers=headers)
            logger.info("Source status update: source_id=%d status=%s -> %d",
                        source_id, status, resp.status_code)
    except Exception as e:
        logger.warning("Source status update failed (non-critical): source_id=%d error=%s",
                        source_id, e)


async def _execute_rss_source(source_id: int, source_config: dict):
    """RSS 信息源独立调度：解析 feed → 逐篇爬取 → 保存结果。"""
    from crawler.feed import parse_feed
    from crawler.single import crawl_single_page
    from crawler.models import CrawlResult

    feed_url = source_config.get("value", "")
    freshness_hours = source_config.get("freshnessHours", 24)
    max_entries = source_config.get("maxPages", 10) or 10
    src_name = source_config.get("name", "")

    # 1. 解析 feed 获取文章列表
    entries = await parse_feed(
        feed_url=feed_url,
        freshness_hours=freshness_hours,
        max_entries=max_entries,
        proxy=settings.proxy_url,
    )
    if not entries:
        logger.info("RSS source %d: no fresh entries from %s", source_id, feed_url)
        await _update_source_run_status(source_id, "success", result_count=0)
        return

    logger.info("RSS source %d: %d entries from %s", source_id, len(entries), feed_url)

    # 2. 创建容器任务
    task_id = await repo.create_task(
        task_type="single",
        source_url=feed_url,
        search_engine=source_config.get("searchEngine", settings.digest_search_engine),
    )

    # 3. 逐篇爬取（并发控制 + 共享浏览器实例）
    from crawl4ai import AsyncWebCrawler
    from crawler.config import get_browser_config

    sem = asyncio.Semaphore(settings.max_concurrent_crawls)
    results: list[CrawlResult] = []
    browser_config = await get_browser_config(text_mode=True, light_mode=True, proxy=settings.proxy_url)

    async with AsyncWebCrawler(config=browser_config) as shared_crawler:

        async def _crawl_entry(entry_url: str) -> CrawlResult | None:
            async with sem:
                try:
                    return await crawl_single_page(url=entry_url, config=None, crawler=shared_crawler)
                except Exception as e:
                    logger.debug("RSS entry crawl failed: url=%s error=%s", entry_url, e)
                    return None

        tasks = [_crawl_entry(e.url) for e in entries]
        page_results = await asyncio.gather(*tasks, return_exceptions=True)

    for r in page_results:
        if isinstance(r, CrawlResult):
            if src_name:
                r.metadata["source_name"] = src_name
            results.append(r)

    # 4. 保存结果
    from standalone.models import TaskStatus
    total_words = await repo.save_pages(task_id, results)
    successful = [r for r in results if r.success]
    if not successful:
        await repo.fail_task(task_id, "RSS feed 所有文章爬取失败")
        await _update_source_run_status(source_id, "failed", error="All articles failed")
        return

    await repo.complete_crawl(
        task_id,
        total_pages=len(results),
        completed_pages=len(successful),
        crawl_duration=0,
        total_word_count=total_words,
    )
    await repo.complete_task(task_id)

    stats = await _collect_source_stats(task_id)
    await _update_source_run_status(
        source_id, "success",
        quality_score=stats.get("qualityScore"),
        result_count=stats.get("resultCount"),
    )
    logger.info("RSS source %d done: task_id=%d entries=%d successful=%d",
                source_id, task_id, len(entries), len(successful))


async def _fetch_active_sources() -> list[dict] | None:
    """从 Java 后端拉取所有活跃信息源。"""
    java_url = settings.java_api_url
    if not java_url:
        return None

    try:
        import httpx
        headers = {"Content-Type": "application/json"}
        if settings.callback_api_key:
            headers["X-Callback-Key"] = settings.callback_api_key
        async with httpx.AsyncClient(timeout=settings.sources_api_timeout) as client:
            resp = await client.get(f"{java_url}/api/internal/collector/sources", headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("data", [])
    except Exception as e:
        logger.warning("Failed to fetch sources from Java API: %s", e)
    return None


# ============== 调度器生命周期 ==============

def start_scheduler():
    """启动定时调度器（日报 + 信息源）"""
    global _scheduler

    if _scheduler is not None:
        logger.warning("Scheduler already running")
        return

    _scheduler = AsyncIOScheduler()

    # 日报调度
    if backend_config.get_bool("digest.enabled") and settings.digest_cron:
        try:
            cron_params = parse_cron(settings.digest_cron)
            _scheduler.add_job(
                generate_scheduled_digest,
                trigger=CronTrigger(**cron_params),
                id="digest_daily",
                name="Daily Digest Generation",
                replace_existing=True,
            )
            logger.info("Digest scheduler: cron='%s'", settings.digest_cron)
        except ValueError as e:
            logger.error("Invalid DIGEST_CRON '%s': %s", settings.digest_cron, e)
    else:
        logger.info("Digest scheduling disabled")

    # 信息源调度刷新（每 5 分钟同步一次）
    _scheduler.add_job(
        refresh_source_schedules,
        trigger="interval",
        minutes=5,
        id="source_schedule_refresh",
        name="Source Schedule Refresh",
        replace_existing=True,
    )

    # 优化记录定时清理（每天清理 90 天前的数据）
    async def _cleanup_optimization_records():
        from optimization.knowledge_base import KnowledgeBase
        try:
            kb = KnowledgeBase()
            count = await kb.cleanup_old_records(days=90)
            if count > 0:
                logger.info("Cleaned up %d old optimization records", count)
        except Exception as e:
            logger.warning("Optimization cleanup failed: %s", e)

    _scheduler.add_job(
        _cleanup_optimization_records,
        trigger="interval",
        days=1,
        id="optimization_cleanup",
        name="Optimization Records Cleanup",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info("Scheduler started (digest + source scheduling)")

    # 首次同步信息源
    try:
        asyncio.get_event_loop().create_task(refresh_source_schedules())
    except RuntimeError:
        pass


def stop_scheduler():
    """停止定时调度器"""
    global _scheduler, _registered_source_jobs
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        _registered_source_jobs.clear()
        logger.info("Scheduler stopped")


def get_scheduler_status() -> dict:
    """获取调度器状态"""
    if _scheduler is None:
        return {
            "running": False,
            "cron": settings.digest_cron,
            "enabled": backend_config.get_bool("digest.enabled"),
            "source_jobs": 0,
        }

    jobs = _scheduler.get_jobs()
    digest_job = next((j for j in jobs if j.id == "digest_daily"), None)
    next_run = str(digest_job.next_run_time) if digest_job and digest_job.next_run_time else None
    source_count = sum(1 for j in jobs if j.id.startswith("source_"))

    return {
        "running": True,
        "cron": settings.digest_cron,
        "enabled": backend_config.get_bool("digest.enabled"),
        "next_run": next_run,
        "source_jobs": source_count,
    }
