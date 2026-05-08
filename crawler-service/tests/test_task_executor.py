"""TaskExecutor 核心执行路径测试

覆盖 TaskExecutor._execute 的核心逻辑：
- single/keyword 任务类型
- 状态流转: PENDING → CRAWLING → PROCESSING → COMPLETED
- 爬取全部失败 → FAILED
- AI 整理成功/失败路径
- 并发信号量控制
- shutdown 取消运行中任务
"""

import os
import sys
import json
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from contextlib import asynccontextmanager

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from standalone.models import TaskStatus
from standalone.task_executor import TaskExecutor


# ============== Helpers ==============

def make_crawl_result(url="https://example.com", title="Test",
                       markdown=None,
                       success=True, word_count=100, crawl_time_ms=500, error_message=None):
    r = MagicMock()
    r.url = url
    r.title = title
    r.markdown = markdown or ("# Test Article\n\n" + "Lorem ipsum dolor sit amet. " * 10)
    r.success = success
    r.word_count = word_count
    r.crawl_time_ms = crawl_time_ms
    r.error_message = error_message
    r.depth = 0
    r.metadata = {}
    return r


def make_organizer_result(title="AI Title", summary="AI Summary",
                           key_points=["p1"], tags=["t1"], category="programming",
                           full_content="# AI Content", duration_ms=1000, tokens_used=500):
    r = MagicMock()
    r.title = title
    r.summary = summary
    r.key_points = key_points
    r.tags = tags
    r.category = category
    r.full_content = full_content
    r.duration_ms = duration_ms
    r.tokens_used = tokens_used
    r.sections = []
    r.highlight = None
    return r


def _mock_crawler():
    """创建 mock AsyncWebCrawler 上下文管理器"""
    mock_crawler = AsyncMock()
    mock_crawler.__aenter__ = AsyncMock(return_value=mock_crawler)
    mock_crawler.__aexit__ = AsyncMock(return_value=False)
    return mock_crawler


# ============== Fixtures ==============

@pytest.fixture
def mock_db():
    tasks = {}
    ai_results = {}
    task_id_counter = [1]

    repo = MagicMock()

    async def _get_task(tid):
        return tasks.get(tid)

    async def _update_task_status(tid, status):
        if tid in tasks:
            tasks[tid]["status"] = status

    async def _fail_task(tid, error):
        if tid in tasks:
            tasks[tid]["status"] = TaskStatus.FAILED
            tasks[tid]["error_message"] = error

    async def _save_pages(tid, results):
        successful = [r for r in results if getattr(r, 'success', False)]
        total_words = sum(getattr(r, 'word_count', 0) for r in successful)
        return total_words

    async def _complete_crawl(tid, **kwargs):
        if tid in tasks:
            tasks[tid].update(kwargs)

    async def _complete_task(tid):
        if tid in tasks:
            tasks[tid]["status"] = TaskStatus.COMPLETED

    async def _save_ai_results(tid, **kwargs):
        ai_results[tid] = kwargs

    async def _save_ai_error(tid, error):
        if tid in tasks:
            tasks[tid]["ai_error_message"] = error

    repo.get_task = _get_task
    repo.update_task_status = _update_task_status
    repo.fail_task = _fail_task
    repo.save_pages = _save_pages
    repo.complete_crawl = _complete_crawl
    repo.complete_task = _complete_task
    repo.save_ai_results = _save_ai_results
    repo.save_ai_error = _save_ai_error
    repo.save_ai_search_metadata = AsyncMock()
    repo.save_digest_results = AsyncMock()
    repo.update_task_progress = AsyncMock()

    repo._tasks = tasks
    repo._ai_results = ai_results

    def add_task(task_type="single", source_url="https://example.com",
                 keyword=None, status=TaskStatus.PENDING, **kwargs):
        tid = task_id_counter[0]
        task_id_counter[0] += 1
        tasks[tid] = {
            "id": tid, "task_type": task_type, "source_url": source_url,
            "keyword": keyword, "search_engine": "sogou", "max_depth": 1,
            "max_pages": 10, "ai_template": "tech_summary", "status": status,
            "crawl_config": None, "ai_search_metadata": None, **kwargs,
        }
        return tid

    repo.add_task = add_task
    return repo


@pytest.fixture
def tx(mock_db):
    return TaskExecutor(max_concurrent=2)


def _patch_ai(available=True, organizer_return=None, organizer_side_effect=None):
    """创建 AI mock 上下文管理器列表，正确处理 ContentOrganizer 单例"""
    import ai.content_organizer as co_mod
    patches = []

    # Patch 模块的 _settings.is_configured（控制 is_available property）
    if available:
        settings_mock = MagicMock()
        settings_mock.is_configured = True
        patches.append(patch.object(co_mod.ContentOrganizer, '_settings', settings_mock))
    else:
        settings_mock = MagicMock()
        settings_mock.is_configured = False
        patches.append(patch.object(co_mod.ContentOrganizer, '_settings', settings_mock))

    if organizer_return is not None:
        patches.append(patch.object(co_mod.ContentOrganizer, 'organize', new_callable=AsyncMock, return_value=organizer_return))
        patches.append(patch.object(co_mod.ContentOrganizer, 'organize_multiple', new_callable=AsyncMock, return_value=organizer_return))

    if organizer_side_effect is not None:
        patches.append(patch.object(co_mod.ContentOrganizer, 'organize', new_callable=AsyncMock, side_effect=organizer_side_effect))

    return patches


# ============== Single Task Tests ==============

class TestSingleTask:

    @pytest.mark.asyncio
    async def test_single_success_with_ai(self, tx, mock_db):
        tid = mock_db.add_task(task_type="single")

        with patch("standalone.task_executor.repo", mock_db), \
             patch("crawler.single.crawl_single_page", new_callable=AsyncMock, return_value=make_crawl_result()), \
             patch("crawler.config.get_browser_config", return_value=MagicMock()), \
             patch("crawl4ai.AsyncWebCrawler", return_value=_mock_crawler()), \
             patch("ai.content_organizer._settings", MagicMock(is_configured=True)), \
             patch("ai.content_organizer.organize", new_callable=AsyncMock, return_value=make_organizer_result()), \
             patch.object(TaskExecutor, "_filter_low_quality", staticmethod(lambda results: results)):

            await tx._execute(tid)

        assert mock_db._tasks[tid]["status"] == TaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_single_crawl_fails(self, tx, mock_db):
        tid = mock_db.add_task(task_type="single")

        with patch("standalone.task_executor.repo", mock_db), \
             patch("crawler.single.crawl_single_page", new_callable=AsyncMock, return_value=make_crawl_result(success=False, error_message="Connection refused")), \
             patch("crawler.config.get_browser_config", return_value=MagicMock()), \
             patch("crawl4ai.AsyncWebCrawler", return_value=_mock_crawler()):

            await tx._execute(tid)

        assert mock_db._tasks[tid]["status"] == TaskStatus.FAILED

    @pytest.mark.asyncio
    async def test_single_ai_fails_still_completes(self, tx, mock_db):
        tid = mock_db.add_task(task_type="single")

        with patch("standalone.task_executor.repo", mock_db), \
             patch("crawler.single.crawl_single_page", new_callable=AsyncMock, return_value=make_crawl_result()), \
             patch("crawler.config.get_browser_config", return_value=MagicMock()), \
             patch("crawl4ai.AsyncWebCrawler", return_value=_mock_crawler()), \
             patch("ai.content_organizer._settings", MagicMock(is_configured=True)), \
             patch("ai.content_organizer.organize", new_callable=AsyncMock, side_effect=Exception("AI timeout")), \
             patch.object(TaskExecutor, "_filter_low_quality", staticmethod(lambda results: results)):

            await tx._execute(tid)

        assert mock_db._tasks[tid]["status"] == TaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_single_ai_not_configured(self, tx, mock_db):
        """AI 未配置时跳过整理，直接 COMPLETED"""
        tid = mock_db.add_task(task_type="single")

        with patch("standalone.task_executor.repo", mock_db), \
             patch("crawler.single.crawl_single_page", new_callable=AsyncMock, return_value=make_crawl_result()), \
             patch("crawler.config.get_browser_config", return_value=MagicMock()), \
             patch("crawl4ai.AsyncWebCrawler", return_value=_mock_crawler()), \
             patch("ai.content_organizer._settings", MagicMock(is_configured=False)), \
             patch.object(TaskExecutor, "_filter_low_quality", staticmethod(lambda results: results)):

            await tx._execute(tid)

        assert mock_db._tasks[tid]["status"] == TaskStatus.COMPLETED


# ============== State Transition Tests ==============

class TestStateTransitions:

    @pytest.mark.asyncio
    async def test_status_goes_through_crawling_to_completed(self, tx, mock_db):
        tid = mock_db.add_task(task_type="single")
        status_changes = []
        orig_update = mock_db.update_task_status

        async def track_status(tid_, status):
            status_changes.append(status)
            await orig_update(tid_, status)

        mock_db.update_task_status = track_status

        with patch("standalone.task_executor.repo", mock_db), \
             patch("crawler.single.crawl_single_page", new_callable=AsyncMock, return_value=make_crawl_result()), \
             patch("crawler.config.get_browser_config", return_value=MagicMock()), \
             patch("crawl4ai.AsyncWebCrawler", return_value=_mock_crawler()), \
             patch("ai.content_organizer._settings", MagicMock(is_configured=True)), \
             patch("ai.content_organizer.organize", new_callable=AsyncMock, return_value=make_organizer_result()), \
             patch.object(TaskExecutor, "_filter_low_quality", staticmethod(lambda results: results)):

            await tx._execute(tid)

        assert status_changes == [TaskStatus.CRAWLING, TaskStatus.PROCESSING]
        assert mock_db._tasks[tid]["status"] == TaskStatus.COMPLETED


# ============== Keyword Task Tests ==============

class TestKeywordTask:

    @pytest.mark.asyncio
    async def test_keyword_success(self, tx, mock_db):
        tid = mock_db.add_task(task_type="keyword", keyword="python async")

        results = [make_crawl_result(url=f"https://example.com/{i}")
                   for i in range(3)]

        with patch("standalone.task_executor.repo", mock_db), \
             patch("crawler.search.crawl_by_keyword", new_callable=AsyncMock, return_value=results), \
             patch("ai.content_organizer._settings", MagicMock(is_configured=False)), \
             patch.object(TaskExecutor, "_filter_low_quality", staticmethod(lambda results: results)):

            await tx._execute(tid)

        assert mock_db._tasks[tid]["status"] == TaskStatus.COMPLETED


# ============== Error Handling Tests ==============

class TestErrorHandling:

    @pytest.mark.asyncio
    async def test_unknown_task_type_fails(self, tx, mock_db):
        tid = mock_db.add_task(task_type="unknown_type")

        with patch("standalone.task_executor.repo", mock_db):
            await tx._execute(tid)

        assert mock_db._tasks[tid]["status"] == TaskStatus.FAILED
        assert "Unknown task type" in mock_db._tasks[tid]["error_message"]

    @pytest.mark.asyncio
    async def test_task_not_found_does_nothing(self, tx, mock_db):
        with patch("standalone.task_executor.repo", mock_db):
            await tx._execute(99999)

    @pytest.mark.asyncio
    async def test_exception_during_crawl_fails_task(self, tx, mock_db):
        tid = mock_db.add_task(task_type="single")

        with patch("standalone.task_executor.repo", mock_db), \
             patch("crawler.single.crawl_single_page", new_callable=AsyncMock, side_effect=RuntimeError("Browser crash")), \
             patch("crawler.config.get_browser_config", return_value=MagicMock()), \
             patch("crawl4ai.AsyncWebCrawler", return_value=_mock_crawler()):

            await tx._execute(tid)

        assert mock_db._tasks[tid]["status"] == TaskStatus.FAILED
        assert "Browser crash" in mock_db._tasks[tid]["error_message"]


# ============== Concurrency Tests ==============

class TestConcurrency:

    @pytest.mark.asyncio
    async def test_semaphore_limits_concurrency(self, mock_db):
        tx = TaskExecutor(max_concurrent=1)

        tid1 = mock_db.add_task(task_type="single")
        tid2 = mock_db.add_task(task_type="single")

        execution_order = []
        barrier = asyncio.Event()

        async def slow_crawl(**kwargs):
            execution_order.append("start")
            await asyncio.sleep(0.05)
            execution_order.append("end")
            return make_crawl_result()

        with patch("standalone.task_executor.repo", mock_db), \
             patch("crawler.single.crawl_single_page", new_callable=AsyncMock, side_effect=slow_crawl), \
             patch("crawler.config.get_browser_config", return_value=MagicMock()), \
             patch("crawl4ai.AsyncWebCrawler", return_value=_mock_crawler()), \
             patch("ai.content_organizer._settings", MagicMock(is_configured=False)), \
             patch.object(TaskExecutor, "_filter_low_quality", staticmethod(lambda results: results)):

            await asyncio.gather(tx._execute_with_semaphore(tid1, "test-eid-1"), tx._execute_with_semaphore(tid2, "test-eid-2"))

        assert execution_order == ["start", "end", "start", "end"]

    @pytest.mark.asyncio
    async def test_running_count(self, tx):
        assert tx.running_count == 0


# ============== Shutdown Tests ==============

class TestShutdown:

    @pytest.mark.asyncio
    async def test_shutdown_with_no_tasks(self, mock_db):
        tx = TaskExecutor(max_concurrent=3)
        with patch("standalone.task_executor.repo", mock_db):
            await tx.shutdown()
        assert tx.running_count == 0
