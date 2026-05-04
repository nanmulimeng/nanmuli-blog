"""异步任务执行器"""

import asyncio
import logging
from typing import Dict

from config import settings
from standalone.models import TaskStatus
from standalone import repository as repo

logger = logging.getLogger(__name__)


class TaskExecutor:
    """管理异步爬取任务"""

    def __init__(self, max_concurrent: int = 3):
        self._running: Dict[int, asyncio.Task] = {}
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def submit(self, task_id: int):
        if task_id in self._running:
            raise ValueError(f"Task {task_id} is already running")

        async_task = asyncio.create_task(self._execute_with_semaphore(task_id))
        self._running[task_id] = async_task
        async_task.add_done_callback(lambda t: self._running.pop(task_id, None))

    async def _execute_with_semaphore(self, task_id: int):
        async with self._semaphore:
            await self._execute(task_id)

    async def _execute(self, task_id: int):
        from crawler.single import crawl_single_page
        from crawler.deep import crawl_deep_pages
        from crawler.search import crawl_by_keyword
        from api.crawl import CrawlConfig

        task = await repo.get_task(task_id)
        if not task:
            return

        try:
            await repo.update_task_status(task_id, TaskStatus.CRAWLING)

            # 从 DB 恢复用户提交的 config，若无则用默认值
            config_json = task.get("crawl_config")
            if config_json:
                config = CrawlConfig.model_validate_json(config_json)
            else:
                config = CrawlConfig()

            if task["task_type"] == "single":
                result = await crawl_single_page(url=task["source_url"], config=config)
                results = [result]

            elif task["task_type"] == "deep":
                results = await crawl_deep_pages(
                    url=task["source_url"],
                    max_depth=task["max_depth"],
                    max_pages=task["max_pages"],
                    config=config
                )

            elif task["task_type"] == "keyword":
                results = await crawl_by_keyword(
                    keyword=task["keyword"],
                    engine=task["search_engine"],
                    max_results=task["max_pages"],
                    config=config
                )
            else:
                await repo.fail_task(task_id, f"Unknown task type: {task['task_type']}")
                return

            total_words = await repo.save_pages(task_id, results)

            success_count = sum(1 for r in results if r.success)
            if success_count == 0:
                error = next((r.error_message for r in results if r.error_message), "所有页面爬取失败")
                await repo.fail_task(task_id, error)
            else:
                duration = sum(r.crawl_time_ms for r in results)
                await repo.complete_task(
                    task_id,
                    total_pages=len(results),
                    completed_pages=success_count,
                    crawl_duration=duration,
                    total_word_count=total_words
                )

            logger.info(f"Task {task_id} completed: {success_count}/{len(results)} pages")

        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}", exc_info=True)
            await repo.fail_task(task_id, str(e))

    def is_running(self, task_id: int) -> bool:
        return task_id in self._running

    @property
    def running_count(self) -> int:
        return len(self._running)


# 全局单例
executor = TaskExecutor(max_concurrent=settings.max_concurrent_tasks)
