"""Backend crawler config mapping tests."""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def test_default_backend_integration_is_disabled_for_generic_service():
    from config import Settings

    assert Settings.model_fields["java_api_url"].default == ""
    assert Settings.model_fields["callback_url"].default == ""


def test_backend_config_applies_runtime_digest_ai_and_optimization_settings():
    from config import settings
    from standalone import backend_config

    original = {
        "ai_digest_per_max_chars": settings.ai_digest_per_max_chars,
        "ai_digest_total_budget": settings.ai_digest_total_budget,
        "ai_digest_max_tokens": settings.ai_digest_max_tokens,
        "digest_global_timeout": settings.digest_global_timeout,
        "digest_filter_min_content": settings.digest_filter_min_content,
        "digest_optimization_enabled": settings.digest_optimization_enabled,
        "digest_optimization_min_sections": settings.digest_optimization_min_sections,
        "digest_optimization_min_results_per_section": settings.digest_optimization_min_results_per_section,
        "digest_optimization_target_score": settings.digest_optimization_target_score,
        "optimization_total_budget_seconds": settings.optimization_total_budget_seconds,
        "breadth_max_rounds": settings.breadth_max_rounds,
        "optimization_min_improvement": settings.optimization_min_improvement,
        "optimization_depth_target_score": settings.optimization_depth_target_score,
        "optimization_breadth_target_score": settings.optimization_breadth_target_score,
    }

    try:
        backend_config._apply_all_settings({
            "ai.digest_per_max_chars": "1234",
            "ai.digest_total_budget": "56789",
            "ai.digest_max_tokens": "4321",
            "digest.global_timeout": "345",
            "digest.filter_min_content": "77",
            "digest.optimization_enabled": "true",
            "digest.optimization_min_sections": "4",
            "digest.optimization_min_results_per_section": "5",
            "digest.optimization_target_score": "0.82",
            "optimization.total_budget_seconds": "99",
            "optimization.breadth_max_rounds": "7",
            "optimization.min_improvement": "0.08",
            "optimization.depth_target_score": "0.74",
            "optimization.breadth_target_score": "0.76",
        })

        assert settings.ai_digest_per_max_chars == 1234
        assert settings.ai_digest_total_budget == 56789
        assert settings.ai_digest_max_tokens == 4321
        assert settings.digest_global_timeout == 345
        assert settings.digest_filter_min_content == 77
        assert settings.digest_optimization_enabled is True
        assert settings.digest_optimization_min_sections == 4
        assert settings.digest_optimization_min_results_per_section == 5
        assert settings.digest_optimization_target_score == 0.82
        assert settings.optimization_total_budget_seconds == 99
        assert settings.breadth_max_rounds == 7
        assert settings.optimization_min_improvement == 0.08
        assert settings.optimization_depth_target_score == 0.74
        assert settings.optimization_breadth_target_score == 0.76
    finally:
        for key, value in original.items():
            setattr(settings, key, value)


def test_blank_backend_auth_keys_do_not_clear_env_api_keys(monkeypatch):
    from config import settings
    from standalone import backend_config

    original_keys = settings.api_keys
    try:
        settings.api_keys = "env-key"
        monkeypatch.setattr(backend_config, "_ENV_API_KEYS", "env-key")

        backend_config._apply_all_settings({
            "auth.enabled": "true",
            "auth.api_keys": "",
        })

        assert settings.api_keys == "env-key"
    finally:
        settings.api_keys = original_keys


def test_backend_localhost_urls_do_not_override_env_container_urls(monkeypatch):
    from config import settings
    from standalone import backend_config

    original_callback_url = settings.callback_url
    original_java_api_url = settings.java_api_url
    try:
        settings.callback_url = "http://backend:8081/api/internal/collector/callback"
        settings.java_api_url = "http://backend:8081"
        monkeypatch.setattr(
            backend_config,
            "_ENV_CALLBACK_URL",
            "http://backend:8081/api/internal/collector/callback",
        )
        monkeypatch.setattr(backend_config, "_ENV_JAVA_API_URL", "http://backend:8081")

        backend_config._apply_all_settings({
            "callback.url": "http://localhost:8081/api/internal/collector/callback",
            "service.java-api-url": "http://localhost:8081",
        })

        assert settings.callback_url == "http://backend:8081/api/internal/collector/callback"
        assert settings.java_api_url == "http://backend:8081"
    finally:
        settings.callback_url = original_callback_url
        settings.java_api_url = original_java_api_url
