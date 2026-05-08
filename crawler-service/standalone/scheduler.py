"""定时日报调度器（APScheduler）"""

import datetime
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config import settings
from standalone.models import TaskStatus
from standalone import repository as repo
from standalone.task_executor import executor

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


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


async def generate_scheduled_digest(force: bool = False):
    """定时日报生成入口

    Args:
        force: 为 True 时跳过防重复检查，允许重新生成当天日报
    """
    today = datetime.date.today().isoformat()
    logger.info("Scheduled digest generation triggered for %s (force=%s)", today, force)

    try:
        # 检查今天是否已有日报任务（防重复）
        if not force:
            # 有活跃任务 → 跳过
            active = await repo.get_digest_today_pending_or_running()
            if active:
                r = active[0]
                logger.info("Digest for %s already running (task_id=%d, status=%d), skipping.",
                            today, r["id"], r["status"])
                return
            # 有已完成任务 → 跳过
            completed = await repo.get_digest_by_date(today)
            if completed and completed.get("status") == TaskStatus.COMPLETED:
                logger.info("Digest for %s already completed (task_id=%d), skipping.",
                            today, completed["id"])
                return

        task_id = await repo.create_task(
            task_type="digest",
            ai_template="daily_digest",
            keyword=today,
        )
        await executor.submit(task_id)
        logger.info("Scheduled digest task created: task_id=%d, date=%s", task_id, today)

    except Exception as e:
        logger.error("Scheduled digest generation failed: %s", e, exc_info=True)


def start_scheduler():
    """启动定时调度器"""
    global _scheduler

    if _scheduler is not None:
        logger.warning("Scheduler already running")
        return

    if not settings.digest_enabled:
        logger.info("Digest scheduling disabled (DIGEST_ENABLED=false)")
        return

    if not settings.digest_cron:
        logger.warning("DIGEST_CRON not configured, scheduler not started")
        return

    try:
        cron_params = parse_cron(settings.digest_cron)
    except ValueError as e:
        logger.error("Invalid DIGEST_CRON '%s': %s", settings.digest_cron, e)
        return

    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(
        generate_scheduled_digest,
        trigger=CronTrigger(**cron_params),
        id="digest_daily",
        name="Daily Digest Generation",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("Digest scheduler started: cron='%s'", settings.digest_cron)


def stop_scheduler():
    """停止定时调度器"""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Digest scheduler stopped")


def get_scheduler_status() -> dict:
    """获取调度器状态"""
    if _scheduler is None:
        return {"running": False, "cron": settings.digest_cron, "enabled": settings.digest_enabled}

    jobs = _scheduler.get_jobs()
    next_run = None
    if jobs:
        next_run = str(jobs[0].next_run_time) if jobs[0].next_run_time else None

    return {
        "running": True,
        "cron": settings.digest_cron,
        "enabled": settings.digest_enabled,
        "next_run": next_run,
    }
