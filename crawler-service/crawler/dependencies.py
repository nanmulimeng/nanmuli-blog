"""Runtime dependency probes for crawler integrations."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from importlib import import_module
from typing import Any


@dataclass(frozen=True)
class DependencyStatus:
    available: bool
    name: str
    version: str | None = None
    error: str | None = None
    mode: str = "degraded"


@lru_cache(maxsize=1)
def crawl4ai_status() -> DependencyStatus:
    from config import settings

    try:
        module = import_module("crawl4ai")
        version = getattr(module, "__version__", None)
        if version is not None and not isinstance(version, str):
            version = getattr(version, "__version__", None) or getattr(version, "version", None) or str(version)
        return DependencyStatus(
            available=True,
            name="crawl4ai",
            version=version,
            mode=settings.crawler_dependency_mode,
        )
    except Exception as exc:
        return DependencyStatus(
            available=False,
            name="crawl4ai",
            error=str(exc),
            mode=settings.crawler_dependency_mode,
        )


def require_crawl4ai() -> Any:
    status = crawl4ai_status()
    if not status.available:
        raise RuntimeError(
            "Crawl4AI is unavailable; crawler is running in degraded mode. "
            f"Install/fix Crawl4AI or set crawler_dependency_mode=strict. detail={status.error}"
        )
    return import_module("crawl4ai")


def get_async_web_crawler() -> Any:
    return require_crawl4ai().AsyncWebCrawler
