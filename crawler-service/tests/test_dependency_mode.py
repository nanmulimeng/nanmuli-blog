"""Crawler dependency compatibility mode tests."""

import pytest


def test_deep_filter_imports_without_crawl4ai_filter_base(monkeypatch):
    import builtins
    import importlib
    import sys

    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "crawl4ai.deep_crawling.filters":
            raise ImportError("filters module moved")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    sys.modules.pop("crawler.deep_filters", None)

    module = importlib.import_module("crawler.deep_filters")

    assert module.ExcludedDomainFilter().apply("https://example.com/article") is True
    sys.modules.pop("crawler.deep_filters", None)


def test_crawl4ai_status_reports_unavailable(monkeypatch):
    from crawler import dependencies

    dependencies.crawl4ai_status.cache_clear()

    def fake_import_module(name):
        if name == "crawl4ai":
            raise ImportError("crawl4ai removed")
        return __import__(name)

    monkeypatch.setattr(dependencies, "import_module", fake_import_module)

    status = dependencies.crawl4ai_status()

    assert status.available is False
    assert status.error == "crawl4ai removed"
    with pytest.raises(RuntimeError, match="Crawl4AI is unavailable"):
        dependencies.require_crawl4ai()

    dependencies.crawl4ai_status.cache_clear()


def test_backend_config_applies_dependency_mode(monkeypatch):
    from config import settings
    from crawler import dependencies
    from standalone import backend_config

    original = settings.crawler_dependency_mode
    try:
        settings.crawler_dependency_mode = "degraded"
        dependencies.crawl4ai_status.cache_clear()
        assert dependencies.crawl4ai_status().mode == "degraded"

        backend_config._apply_all_settings({"dependency_mode": "strict"})
        assert settings.crawler_dependency_mode == "strict"
        assert dependencies.crawl4ai_status().mode == "strict"

        backend_config._apply_all_settings({"dependency_mode": "unknown"})
        assert settings.crawler_dependency_mode == "strict"
    finally:
        settings.crawler_dependency_mode = original
        dependencies.crawl4ai_status.cache_clear()
