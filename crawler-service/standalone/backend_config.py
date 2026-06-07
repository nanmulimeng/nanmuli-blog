"""从 Java 后端拉取爬虫配置，支持运行时刷新

仅保留 33 项核心管理配置的映射，其余配置由 config.py 默认值兜底。
删除的配置类别：搜索调参、质量评估调参、AI内部调参、日报内部调参、
优化引擎调参、管线调参、部署级配置、DB调参、HTTP连接池、关键词调参。
"""

from __future__ import annotations

import logging
from urllib.parse import urlparse
from config import settings

logger = logging.getLogger(__name__)

_config_cache: dict[str, str] = {}

# 保存 env 原始值，以便禁用代理后恢复
_ENV_PROXY_URL: str = settings.proxy_url or ""
_ENV_API_KEYS: str = settings.api_keys or ""
_ENV_CALLBACK_URL: str = settings.callback_url or ""
_ENV_JAVA_API_URL: str = settings.java_api_url or ""


# ============================================================
# 类型转换辅助
# ============================================================

def _to_bool(val: str) -> bool:
    return val.lower() in ("true", "1", "yes", "on")


def _to_int(val: str, default: int = 0) -> int:
    if not val:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def _to_float(val: str, default: float = 0.0) -> float:
    if not val:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _java_api_url() -> str:
    url = settings.java_api_url
    if url:
        return url.rstrip("/")
    return "http://host.docker.internal:8080"


def _is_localhost_url(url: str) -> bool:
    try:
        host = urlparse(url).hostname or ""
        return host in {"localhost", "127.0.0.1", "::1"}
    except Exception:
        return False


# ============================================================
# 核心配置映射（仅 33 项）
# ============================================================

def _apply_ai_settings(config: dict[str, str]) -> None:
    """AI 核心配置: enabled, api_key, base_url, model, max_tokens"""
    if config.get("ai.enabled", ""):
        settings.ai_enabled = _to_bool(config["ai.enabled"])
    if config.get("ai.model", ""):
        settings.ai_model = config["ai.model"]
    if config.get("ai.max_tokens", ""):
        settings.ai_max_tokens = _to_int(config["ai.max_tokens"])
    if config.get("ai.section_cleanup_timeout", ""):
        settings.ai_section_cleanup_timeout = _to_int(config["ai.section_cleanup_timeout"])
    if config.get("ai.section_cleanup_per_max_chars", ""):
        settings.ai_section_cleanup_per_max_chars = _to_int(config["ai.section_cleanup_per_max_chars"])
    if config.get("ai.section_cleanup_total_budget", ""):
        settings.ai_section_cleanup_total_budget = _to_int(config["ai.section_cleanup_total_budget"])
    if config.get("ai.section_cleanup_max_output_chars", ""):
        settings.ai_section_cleanup_max_output_chars = _to_int(config["ai.section_cleanup_max_output_chars"])
    if config.get("ai.digest_per_max_chars", ""):
        settings.ai_digest_per_max_chars = _to_int(config["ai.digest_per_max_chars"])
    if config.get("ai.digest_total_budget", ""):
        settings.ai_digest_total_budget = _to_int(config["ai.digest_total_budget"])
    if config.get("ai.digest_max_tokens", ""):
        settings.ai_digest_max_tokens = _to_int(config["ai.digest_max_tokens"])
    if "ai.base_url" in config:
        settings.ai_base_url = config["ai.base_url"]
    if "ai.api_key" in config:
        settings.ai_api_key = config["ai.api_key"]


def _apply_digest_settings(config: dict[str, str]) -> None:
    """日报核心配置: enabled, cron, sections, search_engine, parallel_sections"""
    if config.get("digest.enabled", ""):
        settings.digest_enabled = _to_bool(config["digest.enabled"])
    if config.get("digest.cron", ""):
        settings.digest_cron = config["digest.cron"]
    if config.get("digest.search_engine", ""):
        settings.digest_search_engine = config["digest.search_engine"]
    if config.get("digest.sections", ""):
        settings.digest_sections = config["digest.sections"]
    if config.get("digest.parallel_sections", ""):
        settings.digest_parallel_sections = _to_int(config["digest.parallel_sections"])
    if config.get("digest.global_timeout", ""):
        settings.digest_global_timeout = _to_int(config["digest.global_timeout"])
    if config.get("digest.filter_min_content", ""):
        settings.digest_filter_min_content = _to_int(config["digest.filter_min_content"])
    if config.get("digest.optimization_enabled", ""):
        settings.digest_optimization_enabled = _to_bool(config["digest.optimization_enabled"])
    if config.get("digest.optimization_min_sections", ""):
        settings.digest_optimization_min_sections = _to_int(config["digest.optimization_min_sections"])
    if config.get("digest.optimization_min_results_per_section", ""):
        settings.digest_optimization_min_results_per_section = _to_int(
            config["digest.optimization_min_results_per_section"]
        )
    if config.get("digest.optimization_target_score", ""):
        settings.digest_optimization_target_score = _to_float(
            config["digest.optimization_target_score"]
        )


def _apply_callback_settings(config: dict[str, str]) -> None:
    """回调配置: url, timeout, api-key + java-api-url"""
    if "callback.url" in config:
        backend_url = config["callback.url"]
        if _ENV_CALLBACK_URL and _is_localhost_url(backend_url):
            settings.callback_url = _ENV_CALLBACK_URL
        else:
            settings.callback_url = backend_url
    if config.get("callback.timeout", ""):
        settings.callback_timeout = _to_float(config["callback.timeout"])
    if "callback.api-key" in config:
        settings.callback_api_key = config["callback.api-key"]
    if "service.java-api-url" in config:
        backend_url = config["service.java-api-url"]
        if _ENV_JAVA_API_URL and _is_localhost_url(backend_url):
            settings.java_api_url = _ENV_JAVA_API_URL
        else:
            settings.java_api_url = backend_url


def _apply_optimization_settings(config: dict[str, str]) -> None:
    """优化引擎核心配置: enabled, mode, max_rounds"""
    if config.get("optimization.enabled", ""):
        settings.optimization_enabled = _to_bool(config["optimization.enabled"])
    if config.get("optimization.mode", ""):
        settings.optimization_mode = config["optimization.mode"]
    if config.get("optimization.max_rounds", ""):
        settings.optimization_max_rounds = _to_int(config["optimization.max_rounds"])
    if config.get("optimization.breadth_max_rounds", ""):
        settings.breadth_max_rounds = _to_int(config["optimization.breadth_max_rounds"])
    if config.get("optimization.total_budget_seconds", ""):
        settings.optimization_total_budget_seconds = _to_int(
            config["optimization.total_budget_seconds"]
        )
    if config.get("optimization.min_improvement", ""):
        settings.optimization_min_improvement = _to_float(config["optimization.min_improvement"])
    if config.get("optimization.depth_target_score", ""):
        settings.optimization_depth_target_score = _to_float(
            config["optimization.depth_target_score"]
        )
    if config.get("optimization.breadth_target_score", ""):
        settings.optimization_breadth_target_score = _to_float(
            config["optimization.breadth_target_score"]
        )


def _apply_bubble_settings(config: dict[str, str]) -> None:
    """茧房突破核心配置: 仅 enabled 开关"""
    if config.get("bubble.enabled", ""):
        settings.bubble_breaker_enabled = _to_bool(config["bubble.enabled"])


def _apply_auth_settings(config: dict[str, str]) -> None:
    """认证核心配置: enabled, api_keys, protected_prefixes"""
    if config.get("auth.enabled", ""):
        settings.auth_enabled = _to_bool(config["auth.enabled"])
    if config.get("auth.protected_prefixes", ""):
        settings.auth_protected_prefixes = config["auth.protected_prefixes"]
    if config.get("auth.api_keys", "").strip():
        settings.api_keys = config["auth.api_keys"]
    elif _ENV_API_KEYS:
        settings.api_keys = _ENV_API_KEYS


def _apply_limit_settings(config: dict[str, str]) -> None:
    """爬取限制: max_concurrent, max_depth, max_pages"""
    if config.get("limit.max_concurrent", ""):
        settings.max_concurrent_crawls = _to_int(config["limit.max_concurrent"])
    if config.get("limit.max_depth", ""):
        settings.max_depth_limit = _to_int(config["limit.max_depth"])
    if config.get("limit.max_pages", ""):
        settings.max_pages_limit = _to_int(config["limit.max_pages"])


def _apply_dependency_settings(config: dict[str, str]) -> None:
    """外部爬虫依赖策略: degraded / strict"""
    mode = config.get("dependency_mode", "").strip().lower()
    if mode in ("degraded", "strict"):
        if settings.crawler_dependency_mode != mode:
            settings.crawler_dependency_mode = mode
            try:
                from crawler.dependencies import crawl4ai_status
                crawl4ai_status.cache_clear()
            except Exception:
                logger.debug("[BackendConfig] Failed to clear Crawl4AI status cache", exc_info=True)
    elif mode:
        logger.warning("[BackendConfig] Ignoring invalid dependency_mode=%s", mode)


def _apply_pipeline_settings(config: dict[str, str]) -> None:
    """管线开关: ai_organization_enabled, page_classifier_enabled, content_dedup_enabled"""
    if config.get("pipeline.ai_organization_enabled", ""):
        settings.ai_organization_enabled = _to_bool(config["pipeline.ai_organization_enabled"])
    if config.get("pipeline.page_classifier_enabled", ""):
        settings.page_classifier_enabled = _to_bool(config["pipeline.page_classifier_enabled"])
    if config.get("pipeline.content_dedup_enabled", ""):
        settings.content_dedup_enabled = _to_bool(config["pipeline.content_dedup_enabled"])


def _apply_proxy_config(config: dict[str, str]) -> None:
    """代理配置: enabled, url"""
    enabled = config.get("proxy.enabled", "").lower() in ("true", "1", "yes", "on")
    proxy_url = config.get("proxy.url", "")

    if enabled and proxy_url:
        settings.proxy_url = proxy_url
        logger.info("[BackendConfig] Proxy enabled: %s", proxy_url)
    elif not enabled:
        settings.proxy_url = ""
        logger.info("[BackendConfig] Proxy disabled by backend config")
    elif enabled and not proxy_url:
        settings.proxy_url = _ENV_PROXY_URL
        if _ENV_PROXY_URL:
            logger.info("[BackendConfig] Proxy enabled, using env fallback: %s", _ENV_PROXY_URL)


# ============================================================
# 全量配置应用（入口）
# ============================================================

def _apply_all_settings(config: dict[str, str]) -> None:
    """将核心 DB 配置映射到 Pydantic settings 属性"""
    if not config:
        return

    _apply_ai_settings(config)
    _apply_digest_settings(config)
    _apply_callback_settings(config)
    _apply_optimization_settings(config)
    _apply_bubble_settings(config)
    _apply_auth_settings(config)
    _apply_limit_settings(config)
    _apply_dependency_settings(config)
    _apply_pipeline_settings(config)

    # log_level（唯一保留的顶级配置）
    if config.get("log_level", ""):
        settings.log_level = config["log_level"]

    _apply_proxy_config(config)

    logger.info(
        "[BackendConfig] Applied %d config keys to settings",
        len(config),
    )


# ============================================================
# 公共 API
# ============================================================

async def fetch_from_backend() -> dict[str, str]:
    """从 Java 后端拉取 crawler 配置（java_api_url 为空则跳过）"""
    global _config_cache

    if not settings.java_api_url:
        logger.debug("Java backend URL not configured, skipping config fetch")
        return {}

    url = f"{_java_api_url()}/api/internal/collector/config"
    api_key = settings.callback_api_key

    try:
        import httpx
        headers = {}
        if api_key:
            headers["X-Callback-Key"] = api_key
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") == 200:
                    _config_cache = data.get("data", {})
                    logger.info("Fetched %d crawler configs from backend", len(_config_cache))
                    _apply_all_settings(_config_cache)
                    return _config_cache
    except Exception:
        logger.warning("Failed to fetch crawler config from backend", exc_info=True)

    return {}


def get(key: str, default: str = "") -> str:
    """获取配置值，优先从后端拉取的配置，fallback 到 env/Pydantic"""
    if key in _config_cache and _config_cache[key]:
        return _config_cache[key]
    env_key = key.replace(".", "_")
    val = getattr(settings, env_key, None)
    if val is not None and val != "":
        return str(val)
    return default


def get_bool(key: str, default: bool = False) -> bool:
    val = get(key)
    if not val:
        return default
    return val.lower() in ("true", "1", "yes", "on")


async def refresh() -> dict[str, str]:
    """刷新配置，由 /api/v1/config/refresh 端点调用"""
    old_digest = get_bool("digest.enabled")
    old_ai = get_bool("ai.enabled")
    old_cron = get("digest.cron")
    old_proxy_enabled = get_bool("proxy.enabled")
    old_proxy_url = settings.proxy_url

    result = await fetch_from_backend()

    if result:
        new_digest = get_bool("digest.enabled")
        new_ai = get_bool("ai.enabled")
        new_cron = get("digest.cron")
        new_proxy_enabled = get_bool("proxy.enabled")
        cron_changed = old_cron != new_cron

        if old_digest != new_digest or old_ai != new_ai or cron_changed:
            logger.info("Scheduler-relevant config changed (digest=%s, ai=%s, cron=%s), restarting scheduler",
                        old_digest != new_digest, old_ai != new_ai, cron_changed)
            try:
                import asyncio
                from standalone.scheduler import stop_scheduler, start_scheduler
                async def _restart():
                    stop_scheduler()
                    start_scheduler()
                asyncio.get_event_loop().call_soon(lambda: asyncio.ensure_future(_restart()))
            except Exception:
                logger.warning("Failed to restart scheduler", exc_info=True)

        if old_proxy_enabled != new_proxy_enabled or old_proxy_url != settings.proxy_url:
            logger.info("Proxy config changed: enabled=%s, url=%s", new_proxy_enabled, settings.proxy_url)

    return result
