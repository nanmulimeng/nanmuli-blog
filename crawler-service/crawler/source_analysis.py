"""信息源分析共享工具

从 digest.py 提取并修复时区问题的 is_truly_dead()。
供 source_agent.py、digest.py、task_executor.py 共同使用。
"""

import datetime
import logging

logger = logging.getLogger(__name__)

_DEAD_SOURCE_RECOVERY_DAYS = 7


def is_truly_dead(eff: dict) -> bool:
    """判断信息源是否应该被跳过。

    dead 状态持续超过恢复窗口（7天）后自动解除，给源一次重试机会。
    修复版：正确处理 Java LocalDateTime 返回的无时区 ISO 字符串。
    """
    if not eff.get("dead"):
        return False
    last_run = eff.get("last_run_at")
    if last_run:
        try:
            if isinstance(last_run, str):
                cleaned = last_run.replace("Z", "+00:00")
                last_dt = datetime.datetime.fromisoformat(cleaned)
                # Java LocalDateTime 返回无时区字符串，假设为 UTC
                if last_dt.tzinfo is None:
                    last_dt = last_dt.replace(tzinfo=datetime.timezone.utc)
            else:
                last_dt = last_run

            now = datetime.datetime.now(datetime.timezone.utc)
            if last_dt.tzinfo is not None:
                last_dt = last_dt.astimezone(datetime.timezone.utc)

            diff_days = (now - last_dt).days
            if diff_days > _DEAD_SOURCE_RECOVERY_DAYS:
                logger.info(
                    "Dead source recovery: last_run=%s, %d days elapsed > %d day window, retrying",
                    last_run, diff_days, _DEAD_SOURCE_RECOVERY_DAYS,
                )
                return False
        except (ValueError, TypeError) as e:
            logger.debug("Dead source check failed for last_run=%s: %s", last_run, e)
    return True
