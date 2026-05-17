"""Tests for source scheduling in scheduler.py."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from standalone.scheduler import parse_cron, _make_source_job


class TestParseCron:
    def test_valid_cron(self):
        result = parse_cron("0 8 * * 1-5")
        assert result == {"minute": "0", "hour": "8", "day": "*", "month": "*", "day_of_week": "1-5"}

    def test_invalid_cron_too_few_fields(self):
        with pytest.raises(ValueError, match="expected 5 fields"):
            parse_cron("0 8 * *")

    def test_invalid_cron_too_many_fields(self):
        with pytest.raises(ValueError, match="expected 5 fields"):
            parse_cron("0 8 * * 1-5 extra")


class TestMakeSourceJob:
    @pytest.mark.asyncio
    async def test_creates_callable(self):
        source_config = {"type": "keyword", "value": "test"}
        job_fn = _make_source_job(42, source_config)
        assert callable(job_fn)


class TestRefreshSourceSchedules:
    @pytest.mark.asyncio
    async def test_registers_jobs_for_scheduled_sources(self):
        from standalone.scheduler import refresh_source_schedules
        mock_scheduler = MagicMock()
        with patch("standalone.scheduler._scheduler", mock_scheduler), \
             patch("standalone.scheduler._fetch_active_sources", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = [
                {"id": 1, "name": "Source 1", "type": "keyword", "value": "test",
                 "scheduleCron": "0 9 * * 1-5", "isActive": True},
                {"id": 2, "name": "Source 2", "type": "url", "value": "https://example.com",
                 "scheduleCron": None, "isActive": True},
            ]
            await refresh_source_schedules()

        # Only source 1 has scheduleCron, so only 1 job should be added
        assert mock_scheduler.add_job.call_count == 1
        call_kwargs = mock_scheduler.add_job.call_args
        assert call_kwargs[1]["id"] == "source_1"

    @pytest.mark.asyncio
    async def test_no_java_api_returns_early(self):
        from standalone.scheduler import refresh_source_schedules, _scheduler
        with patch("standalone.scheduler._scheduler", MagicMock()), \
             patch("standalone.scheduler._fetch_active_sources", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = None
            await refresh_source_schedules()

    @pytest.mark.asyncio
    async def test_inactive_sources_skipped(self):
        from standalone.scheduler import refresh_source_schedules
        mock_scheduler = MagicMock()
        with patch("standalone.scheduler._scheduler", mock_scheduler), \
             patch("standalone.scheduler._fetch_active_sources", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = [
                {"id": 1, "name": "Inactive", "type": "keyword", "value": "test",
                 "scheduleCron": "0 9 * * *", "isActive": False},
            ]
            await refresh_source_schedules()

        assert mock_scheduler.add_job.call_count == 0


class TestUpdateSourceRunStatus:
    @pytest.mark.asyncio
    async def test_success_status(self):
        from standalone.scheduler import _update_source_run_status
        mock_client = AsyncMock()
        mock_client.post.return_value = MagicMock(status_code=200)

        with patch("standalone.scheduler.settings") as mock_settings, \
             patch("httpx.AsyncClient") as mock_client_cls:
            mock_settings.java_api_url = "http://localhost:8081"
            mock_settings.callback_api_key = "test-key"
            mock_settings.callback_timeout = 5.0

            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=None)
            await _update_source_run_status(42, "success")

    @pytest.mark.asyncio
    async def test_no_java_url_skips(self):
        from standalone.scheduler import _update_source_run_status
        with patch("standalone.scheduler.settings") as mock_settings:
            mock_settings.java_api_url = ""
            # Should not raise
            await _update_source_run_status(42, "success")


# ============== 极端/边界情况测试 ==============


class TestParseCronExtreme:
    """parse_cron 极端测试"""

    def test_every_minute(self):
        result = parse_cron("* * * * *")
        assert result == {"minute": "*", "hour": "*", "day": "*", "month": "*", "day_of_week": "*"}

    def test_specific_datetime(self):
        result = parse_cron("30 14 1 6 *")
        assert result["minute"] == "30"
        assert result["hour"] == "14"
        assert result["day"] == "1"
        assert result["month"] == "6"

    def test_range_expression(self):
        result = parse_cron("0 9 * * 1-5")
        assert result["day_of_week"] == "1-5"

    def test_step_expression(self):
        result = parse_cron("*/15 * * * *")
        assert result["minute"] == "*/15"

    def test_whitespace_handling(self):
        result = parse_cron("  0   8   *   *   1-5  ")
        assert result["minute"] == "0"
        assert result["hour"] == "8"

    def test_four_fields_raises(self):
        with pytest.raises(ValueError, match="expected 5 fields"):
            parse_cron("0 8 * *")

    def test_six_fields_raises(self):
        with pytest.raises(ValueError, match="expected 5 fields"):
            parse_cron("0 8 * * 1-5 extra")

    def test_empty_string_raises(self):
        with pytest.raises(ValueError, match="expected 5 fields"):
            parse_cron("")

    def test_only_spaces_raises(self):
        with pytest.raises(ValueError, match="expected 5 fields"):
            parse_cron("   ")


class TestRefreshSourceSchedulesExtreme:
    """refresh_source_schedules 极端测试"""

    @pytest.mark.asyncio
    async def test_invalid_cron_skipped(self):
        """无效 cron 表达式的源被跳过，不影响其他源"""
        from standalone.scheduler import refresh_source_schedules
        mock_scheduler = MagicMock()
        with patch("standalone.scheduler._scheduler", mock_scheduler), \
             patch("standalone.scheduler._fetch_active_sources", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = [
                {"id": 1, "name": "Bad Cron", "type": "keyword", "value": "test",
                 "scheduleCron": "invalid", "isActive": True},
                {"id": 2, "name": "Good Cron", "type": "keyword", "value": "test",
                 "scheduleCron": "0 9 * * *", "isActive": True},
            ]
            await refresh_source_schedules()

        # Good cron 应成功注册，Bad cron 被跳过
        assert mock_scheduler.add_job.call_count == 1
        call_kwargs = mock_scheduler.add_job.call_args
        assert call_kwargs[1]["id"] == "source_2"

    @pytest.mark.asyncio
    async def test_empty_cron_skipped(self):
        """scheduleCron 为空字符串的源被跳过"""
        from standalone.scheduler import refresh_source_schedules
        mock_scheduler = MagicMock()
        with patch("standalone.scheduler._scheduler", mock_scheduler), \
             patch("standalone.scheduler._fetch_active_sources", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = [
                {"id": 1, "name": "Empty", "type": "keyword", "value": "test",
                 "scheduleCron": "", "isActive": True},
            ]
            await refresh_source_schedules()

        assert mock_scheduler.add_job.call_count == 0

    @pytest.mark.asyncio
    async def test_source_without_id_skipped(self):
        """缺少 id 字段的源被跳过"""
        from standalone.scheduler import refresh_source_schedules
        mock_scheduler = MagicMock()
        with patch("standalone.scheduler._scheduler", mock_scheduler), \
             patch("standalone.scheduler._fetch_active_sources", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = [
                {"name": "No ID", "type": "keyword", "value": "test",
                 "scheduleCron": "0 9 * * *", "isActive": True},
            ]
            await refresh_source_schedules()

        assert mock_scheduler.add_job.call_count == 0

    @pytest.mark.asyncio
    async def test_stale_jobs_removed(self):
        """不再活跃的源任务被移除"""
        from standalone.scheduler import refresh_source_schedules, _registered_source_jobs
        mock_scheduler = MagicMock()
        # 模拟之前已注册的 job
        with patch("standalone.scheduler._scheduler", mock_scheduler), \
             patch("standalone.scheduler._fetch_active_sources", new_callable=AsyncMock) as mock_fetch, \
             patch("standalone.scheduler._registered_source_jobs", {"source_99"}):
            mock_fetch.return_value = [
                {"id": 1, "name": "New", "type": "keyword", "value": "test",
                 "scheduleCron": "0 9 * * *", "isActive": True},
            ]
            await refresh_source_schedules()

        # source_99 应被移除
        mock_scheduler.remove_job.assert_called_once_with("source_99")

    @pytest.mark.asyncio
    async def test_api_returns_empty_list(self):
        """API 返回空列表时不注册任何任务"""
        from standalone.scheduler import refresh_source_schedules
        mock_scheduler = MagicMock()
        with patch("standalone.scheduler._scheduler", mock_scheduler), \
             patch("standalone.scheduler._fetch_active_sources", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = []
            await refresh_source_schedules()

        assert mock_scheduler.add_job.call_count == 0


class TestExecuteScheduledSourceExtreme:
    """execute_scheduled_source 极端测试"""

    @pytest.mark.asyncio
    async def test_empty_value_skips(self):
        """value 为空时跳过不崩溃"""
        from standalone.scheduler import execute_scheduled_source
        with patch("standalone.scheduler.repo") as mock_repo:
            await execute_scheduled_source(1, {"type": "keyword", "value": ""})
            mock_repo.create_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_unknown_type_skips(self):
        """未知 type 时跳过"""
        from standalone.scheduler import execute_scheduled_source
        with patch("standalone.scheduler.repo") as mock_repo:
            await execute_scheduled_source(1, {"type": "podcast", "value": "https://example.com/feed"})
            mock_repo.create_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_url_type_creates_single_task(self):
        """url type crawlMode=single 创建 single 任务"""
        from standalone.scheduler import execute_scheduled_source
        with patch("standalone.scheduler.repo") as mock_repo, \
             patch("standalone.scheduler.executor") as mock_executor, \
             patch("standalone.scheduler._wait_and_update_source_status", new_callable=AsyncMock):
            mock_repo.create_task = AsyncMock(return_value=42)
            await execute_scheduled_source(1, {
                "type": "url", "value": "https://example.com", "crawlMode": "single",
            })
            mock_repo.create_task.assert_called_once()
            call_kwargs = mock_repo.create_task.call_args[1]
            assert call_kwargs["task_type"] == "single"
            assert call_kwargs["source_url"] == "https://example.com"

    @pytest.mark.asyncio
    async def test_url_deep_creates_deep_task(self):
        """url type crawlMode=deep 创建 deep 任务"""
        from standalone.scheduler import execute_scheduled_source
        with patch("standalone.scheduler.repo") as mock_repo, \
             patch("standalone.scheduler.executor") as mock_executor, \
             patch("standalone.scheduler._wait_and_update_source_status", new_callable=AsyncMock):
            mock_repo.create_task = AsyncMock(return_value=42)
            await execute_scheduled_source(1, {
                "type": "url", "value": "https://example.com", "crawlMode": "deep",
            })
            call_kwargs = mock_repo.create_task.call_args[1]
            assert call_kwargs["task_type"] == "deep"

    @pytest.mark.asyncio
    async def test_exception_updates_status_failed(self):
        """任务创建异常时更新状态为 failed"""
        from standalone.scheduler import execute_scheduled_source
        with patch("standalone.scheduler.repo") as mock_repo, \
             patch("standalone.scheduler._update_source_run_status", new_callable=AsyncMock) as mock_status:
            mock_repo.create_task = AsyncMock(side_effect=Exception("DB error"))
            await execute_scheduled_source(1, {"type": "keyword", "value": "test"})
            mock_status.assert_called_once_with(1, "failed", "DB error")
