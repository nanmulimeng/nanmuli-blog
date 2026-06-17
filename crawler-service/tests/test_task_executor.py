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

@asynccontextmanager
async def _noop_scoped_db():
    """透传的 task_scoped_db mock，不创建真实连接"""
    yield


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


def _mock_crawler_factory():
    return lambda config=None: _mock_crawler()


def _passing_quality_result(*_args, **_kwargs):
    return {
        "verdict": "pass",
        "final_score": 88,
        "source": {"level": "medium", "reason": "test source"},
        "quality": {"total_score": 82},
    }


# ============== Digest Quality Filter Tests ==============

class TestDigestQualityFilter:

    def test_digest_rejects_low_value_dictionary_qna_and_error_pages(self, monkeypatch):
        monkeypatch.setattr("standalone.task_executor.settings.page_classifier_enabled", False)
        monkeypatch.setattr("standalone.task_executor.settings.digest_filter_min_content", 80)
        monkeypatch.setattr("standalone.task_executor.settings.digest_eval_reject_threshold", 40)

        long_content = "# Content\n\n" + "substantial technical article body " * 30
        results = [
            make_crawl_result(
                url="https://cn.bing.com/dict/search?q=tutorial",
                title="Tutorial - 必应词典",
                markdown=long_content,
            ),
            make_crawl_result(
                url="https://zhidao.baidu.com/question/763846006257527404.html",
                title="tutorial是什么意思？_百度知道",
                markdown=long_content,
            ),
            make_crawl_result(
                url="https://wenku.baidu.com/error.html?status=404",
                title="百度文库--您的访问出错了",
                markdown=long_content,
            ),
            make_crawl_result(
                url="https://martinfowler.com/articles/patterns-of-distributed-systems/",
                title="Patterns of Distributed Systems",
                markdown=long_content,
            ),
        ]

        with patch("crawler.quality.evaluate_content", side_effect=_passing_quality_result):
            filtered = TaskExecutor()._filter_low_quality(results, task_type="digest")

        assert filtered[0].success is False
        assert "Low-value digest candidate" in filtered[0].error_message
        assert filtered[1].success is False
        assert "Low-value digest candidate" in filtered[1].error_message
        assert filtered[2].success is False
        assert "Low-value digest candidate" in filtered[2].error_message
        assert filtered[3].success is True
        assert filtered[3].metadata["quality_score"] == 88

    def test_digest_rejects_generic_tutorial_and_hardware_promo_pages(self, monkeypatch):
        monkeypatch.setattr("standalone.task_executor.settings.page_classifier_enabled", False)
        monkeypatch.setattr("standalone.task_executor.settings.digest_filter_min_content", 80)
        monkeypatch.setattr("standalone.task_executor.settings.digest_eval_reject_threshold", 40)

        long_content = "# Content\n\n" + "substantial article body " * 30
        results = [
            make_crawl_result(
                url="https://blog.csdn.net/u014158430/article/details/141093791",
                title="Tutorial and Sandbox are common terms in programming learning",
                markdown=long_content,
            ),
            make_crawl_result(
                url="https://blog.csdn.net/gitblog_00388/article/details/148375675",
                title="Technical documentation content creation guide",
                markdown=long_content,
            ),
            make_crawl_result(
                url="https://www.techpowerup.com/349500/godeal24-unveils-6th-anniversary-sale-office-2024-at-just-usd-16-99",
                title="GoDeal24 unveils anniversary sale: Office 2024 at USD 16.99",
                markdown=long_content,
            ),
            make_crawl_result(
                url="https://www.techpowerup.com/review/asrock-radeon-rx-9070-gre-steel-legend/",
                title="ASRock Radeon RX 9070 GRE Steel Legend Review",
                markdown=long_content,
            ),
            make_crawl_result(
                url="https://martinfowler.com/articles/patterns-of-distributed-systems/",
                title="Patterns of Distributed Systems",
                markdown=long_content,
            ),
        ]

        with patch("crawler.quality.evaluate_content", side_effect=_passing_quality_result):
            filtered = TaskExecutor()._filter_low_quality(results, task_type="digest")

        assert filtered[0].success is False
        assert "Low-value digest candidate" in filtered[0].error_message
        assert filtered[1].success is False
        assert "Low-value digest candidate" in filtered[1].error_message
        assert filtered[2].success is False
        assert "Low-value digest candidate" in filtered[2].error_message
        assert filtered[3].success is False
        assert "Low-value digest candidate" in filtered[3].error_message
        assert filtered[4].success is True

    def test_digest_rejects_jobs_certifications_basic_definitions_and_download_directories(self, monkeypatch):
        monkeypatch.setattr("standalone.task_executor.settings.page_classifier_enabled", False)
        monkeypatch.setattr("standalone.task_executor.settings.digest_filter_min_content", 80)
        monkeypatch.setattr("standalone.task_executor.settings.digest_eval_reject_threshold", 40)

        long_content = "# Content\n\n" + "substantial page body " * 30
        results = [
            make_crawl_result(
                url="https://my.jobstreet.com/security-jobs/in-Penang",
                title="Security Jobs in Penang - June 2026 | Jobstreet",
                markdown=long_content,
            ),
            make_crawl_result(
                url="https://www.comptia.org/en-us/certifications/security/",
                title="Security+ (Plus) Certification | CompTIA",
                markdown=long_content,
            ),
            make_crawl_result(
                url="https://www.simplilearn.com/tutorials/programming-tutorial/what-is-software",
                title="What is Software? Definition, Examples, & Types Explained",
                markdown=long_content,
            ),
            make_crawl_result(
                url="https://www.sciencedaily.com/terms/computer_software.htm",
                title="Computer software",
                markdown=long_content,
            ),
            make_crawl_result(
                url="https://en.softonic.com/windows",
                title="Download software for Windows",
                markdown=long_content,
            ),
            make_crawl_result(
                url="https://github.blog/changelog/2026-06-01-copilot-coding-agent-updates/",
                title="GitHub Copilot coding agent updates",
                markdown=long_content,
            ),
        ]

        with patch("crawler.quality.evaluate_content", side_effect=_passing_quality_result):
            filtered = TaskExecutor()._filter_low_quality(results, task_type="digest")

        for result in filtered[:5]:
            assert result.success is False
            assert "Low-value digest candidate" in result.error_message
        assert filtered[5].success is True

    def test_single_task_does_not_apply_digest_low_value_prefilter(self, monkeypatch):
        monkeypatch.setattr("standalone.task_executor.settings.page_classifier_enabled", False)
        monkeypatch.setattr("standalone.task_executor.settings.min_content_length", 80)

        result = make_crawl_result(
            url="https://cn.bing.com/dict/search?q=tutorial",
            title="Tutorial - 必应词典",
            markdown="# Content\n\n" + "dictionary content " * 30,
        )

        with patch("crawler.quality.evaluate_content", side_effect=_passing_quality_result):
            filtered = TaskExecutor()._filter_low_quality([result], task_type="single")

        assert filtered[0].success is True
        assert filtered[0].metadata["quality_score"] == 88


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

    async def _get_pages_by_task(tid):
        return [
            {"url": "https://example.com", "page_title": "Test Page",
             "raw_markdown": "# Test\n\nContent here.", "crawl_status": 2,
             "word_count": 100}
        ]

    repo.get_pages_by_task = _get_pages_by_task

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
             patch("standalone.organizer_helper.repo", mock_db), \
             patch("crawler.single.crawl_single_page", new_callable=AsyncMock, return_value=make_crawl_result()), \
             patch("crawler.config.get_browser_config", new_callable=AsyncMock, return_value=MagicMock()), \
             patch("crawler.dependencies.get_async_web_crawler", return_value=_mock_crawler_factory()), \
             patch("ai.content_organizer._settings", MagicMock(is_configured=True)), \
             patch("ai.content_organizer.organize", new_callable=AsyncMock, return_value=make_organizer_result()), \
             patch.object(TaskExecutor, "_filter_low_quality", lambda self, results, task_type=None, dedup_engine=None: results):

            await tx._execute(tid)

        assert mock_db._tasks[tid]["status"] == TaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_single_crawl_fails(self, tx, mock_db):
        tid = mock_db.add_task(task_type="single")

        with patch("standalone.task_executor.repo", mock_db), \
             patch("crawler.single.crawl_single_page", new_callable=AsyncMock, return_value=make_crawl_result(success=False, error_message="Connection refused")), \
             patch("crawler.config.get_browser_config", new_callable=AsyncMock, return_value=MagicMock()), \
             patch("crawler.dependencies.get_async_web_crawler", return_value=_mock_crawler_factory()):

            await tx._execute(tid)

        assert mock_db._tasks[tid]["status"] == TaskStatus.FAILED

    @pytest.mark.asyncio
    async def test_single_ai_fails_still_completes(self, tx, mock_db):
        tid = mock_db.add_task(task_type="single")

        with patch("standalone.task_executor.repo", mock_db), \
             patch("standalone.organizer_helper.repo", mock_db), \
             patch("crawler.single.crawl_single_page", new_callable=AsyncMock, return_value=make_crawl_result()), \
             patch("crawler.config.get_browser_config", new_callable=AsyncMock, return_value=MagicMock()), \
             patch("crawler.dependencies.get_async_web_crawler", return_value=_mock_crawler_factory()), \
             patch("ai.content_organizer._settings", MagicMock(is_configured=True)), \
             patch("ai.content_organizer.organize", new_callable=AsyncMock, side_effect=Exception("AI timeout")), \
             patch.object(TaskExecutor, "_filter_low_quality", lambda self, results, task_type=None, dedup_engine=None: results):

            await tx._execute(tid)

        assert mock_db._tasks[tid]["status"] == TaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_single_ai_not_configured(self, tx, mock_db):
        """AI 未配置时跳过整理，直接 COMPLETED"""
        tid = mock_db.add_task(task_type="single")

        with patch("standalone.task_executor.repo", mock_db), \
             patch("crawler.single.crawl_single_page", new_callable=AsyncMock, return_value=make_crawl_result()), \
             patch("crawler.config.get_browser_config", new_callable=AsyncMock, return_value=MagicMock()), \
             patch("crawler.dependencies.get_async_web_crawler", return_value=_mock_crawler_factory()), \
             patch("ai.content_organizer._settings", MagicMock(is_configured=False)), \
             patch.object(TaskExecutor, "_filter_low_quality", lambda self, results, task_type=None, dedup_engine=None: results):

            await tx._execute(tid)

        assert mock_db._tasks[tid]["status"] == TaskStatus.COMPLETED


class TestDigestTask:

    @pytest.mark.asyncio
    async def test_digest_ai_failure_marks_task_failed(self, tx, mock_db):
        tid = mock_db.add_task(
            task_type="digest",
            keyword="2026-06-16",
            ai_template="daily_digest",
            digest_date="2026-06-16",
        )

        with patch("standalone.task_executor.repo", mock_db), \
             patch("standalone.digest_post_processor.repo", mock_db), \
             patch("crawler.digest_orchestrator.DigestOrchestrator") as orch_cls, \
             patch.object(TaskExecutor, "_filter_low_quality", lambda self, results, task_type=None, dedup_engine=None: results):
            orch = orch_cls.return_value
            orch.execute = AsyncMock(return_value=[make_crawl_result()])
            orch.get_plan.return_value = None
            orch.get_section_documents.return_value = []
            orch.get_digest_result.return_value = None
            with patch(
                "standalone.digest_post_processor.DigestPostProcessor.organize_with_ai",
                new_callable=AsyncMock,
                return_value=False,
            ):
                await tx._execute(tid)

        assert mock_db._tasks[tid]["status"] == TaskStatus.FAILED
        assert "AI" in mock_db._tasks[tid]["error_message"]

    @pytest.mark.asyncio
    async def test_digest_ai_failure_preserves_specific_error(self, tx, mock_db):
        tid = mock_db.add_task(
            task_type="digest",
            keyword="2026-06-16",
            ai_template="daily_digest",
            digest_date="2026-06-16",
        )

        async def _organize_with_specific_error(task_id, task):
            await mock_db.save_ai_error(task_id, "AI not configured")
            return False

        with patch("standalone.task_executor.repo", mock_db), \
             patch("standalone.digest_post_processor.repo", mock_db), \
             patch("crawler.digest_orchestrator.DigestOrchestrator") as orch_cls, \
             patch.object(TaskExecutor, "_filter_low_quality", lambda self, results, task_type=None, dedup_engine=None: results):
            orch = orch_cls.return_value
            orch.execute = AsyncMock(return_value=[make_crawl_result()])
            orch.get_plan.return_value = None
            orch.get_section_documents.return_value = []
            orch.get_digest_result.return_value = None
            with patch(
                "standalone.digest_post_processor.DigestPostProcessor.organize_with_ai",
                new_callable=AsyncMock,
                side_effect=_organize_with_specific_error,
            ):
                await tx._execute(tid)

        assert mock_db._tasks[tid]["status"] == TaskStatus.FAILED
        assert mock_db._tasks[tid]["error_message"] == "AI not configured"


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
             patch("standalone.organizer_helper.repo", mock_db), \
             patch("crawler.single.crawl_single_page", new_callable=AsyncMock, return_value=make_crawl_result()), \
             patch("crawler.config.get_browser_config", new_callable=AsyncMock, return_value=MagicMock()), \
             patch("crawler.dependencies.get_async_web_crawler", return_value=_mock_crawler_factory()), \
             patch("ai.content_organizer._settings", MagicMock(is_configured=True)), \
             patch("ai.content_organizer.organize", new_callable=AsyncMock, return_value=make_organizer_result()), \
             patch.object(TaskExecutor, "_filter_low_quality", lambda self, results, task_type=None, dedup_engine=None: results):

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
             patch.object(TaskExecutor, "_filter_low_quality", lambda self, results, task_type=None, dedup_engine=None: results):

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
             patch("crawler.config.get_browser_config", new_callable=AsyncMock, return_value=MagicMock()), \
             patch("crawler.dependencies.get_async_web_crawler", return_value=_mock_crawler_factory()):

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
             patch("standalone.task_executor.task_scoped_db", _noop_scoped_db), \
             patch("crawler.single.crawl_single_page", new_callable=AsyncMock, side_effect=slow_crawl), \
             patch("crawler.config.get_browser_config", new_callable=AsyncMock, return_value=MagicMock()), \
             patch("crawler.dependencies.get_async_web_crawler", return_value=_mock_crawler_factory()), \
             patch("ai.content_organizer._settings", MagicMock(is_configured=False)), \
             patch.object(TaskExecutor, "_filter_low_quality", lambda self, results, task_type=None, dedup_engine=None: results):

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
