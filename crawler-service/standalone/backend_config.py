"""从 Java 后端拉取爬虫配置，支持运行时刷新"""

from __future__ import annotations

import logging
from config import settings

logger = logging.getLogger(__name__)

_config_cache: dict[str, str] = {}

# 保存 env 原始值，以便禁用代理后恢复
_ENV_PROXY_URL: str = settings.proxy_url or ""


def _java_api_url() -> str:
    url = settings.java_api_url
    if url:
        return url.rstrip("/")
    return "http://host.docker.internal:8080"


def _apply_proxy_config(config: dict[str, str]) -> None:
    """根据后端配置动态切换代理开关"""
    enabled = config.get("proxy.enabled", "").lower() in ("true", "1", "yes", "on")
    proxy_url = config.get("proxy.url", "")

    if enabled and proxy_url:
        settings.proxy_url = proxy_url
        logger.info("[BackendConfig] Proxy enabled: %s", proxy_url)
    elif not enabled:
        settings.proxy_url = ""
        logger.info("[BackendConfig] Proxy disabled by backend config")
    elif enabled and not proxy_url:
        # 启用但未配置 URL，回退到 env 原始值
        settings.proxy_url = _ENV_PROXY_URL
        if _ENV_PROXY_URL:
            logger.info("[BackendConfig] Proxy enabled, using env fallback: %s", _ENV_PROXY_URL)


async def fetch_from_backend() -> dict[str, str]:
    """从 Java 后端拉取 crawler 配置"""
    global _config_cache

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
                    _apply_proxy_config(_config_cache)
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
    old_proxy_enabled = get_bool("proxy.enabled")
    old_proxy_url = settings.proxy_url

    result = await fetch_from_backend()

    if result:
        new_digest = get_bool("digest.enabled")
        new_ai = get_bool("ai.enabled")
        new_proxy_enabled = get_bool("proxy.enabled")

        if old_digest != new_digest or old_ai != new_ai:
            logger.info("Scheduler-relevant config changed, restarting scheduler")
            try:
                from standalone.scheduler import stop_scheduler, start_scheduler
                stop_scheduler()
                start_scheduler()
            except Exception:
                logger.warning("Failed to restart scheduler", exc_info=True)

        if old_proxy_enabled != new_proxy_enabled or old_proxy_url != settings.proxy_url:
            logger.info("Proxy config changed: enabled=%s, url=%s", new_proxy_enabled, settings.proxy_url)

    return result
