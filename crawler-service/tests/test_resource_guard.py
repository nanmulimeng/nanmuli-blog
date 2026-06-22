import asyncio

import pytest

from crawler import resource_guard


@pytest.mark.asyncio
async def test_browser_crawl_slot_limits_process_wide_concurrency(monkeypatch):
    monkeypatch.setattr(resource_guard.settings, "max_concurrent_crawls", 2)
    resource_guard.reset_browser_crawl_limiter_for_tests()
    active = 0
    peak = 0

    async def guarded_work():
        nonlocal active, peak
        async with resource_guard.browser_crawl_slot():
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.01)
            active -= 1

    await asyncio.gather(*(guarded_work() for _ in range(8)))

    assert peak == 2


@pytest.mark.asyncio
async def test_browser_crawl_slot_picks_up_runtime_limit_changes(monkeypatch):
    monkeypatch.setattr(resource_guard.settings, "max_concurrent_crawls", 1)
    resource_guard.reset_browser_crawl_limiter_for_tests()
    first = resource_guard._get_browser_crawl_limiter()

    monkeypatch.setattr(resource_guard.settings, "max_concurrent_crawls", 3)
    second = resource_guard._get_browser_crawl_limiter()

    assert first is not second
    assert second.limit == 3
