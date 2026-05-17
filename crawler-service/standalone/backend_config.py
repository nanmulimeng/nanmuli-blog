"""从 Java 后端拉取爬虫配置，支持运行时刷新"""

from __future__ import annotations

import logging
from config import settings

logger = logging.getLogger(__name__)

_config_cache: dict[str, str] = {}

# 保存 env 原始值，以便禁用代理后恢复
_ENV_PROXY_URL: str = settings.proxy_url or ""


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


# ============================================================
# 各配置组的映射函数
# ============================================================

def _apply_ai_settings(config: dict[str, str]) -> None:
    """AI 配置: ai.* → ai_*"""
    if config.get("ai.enabled", ""):
        settings.ai_enabled = _to_bool(config["ai.enabled"])
    if config.get("ai.model", ""):
        settings.ai_model = config["ai.model"]
    if config.get("ai.temperature", ""):
        settings.ai_temperature = _to_float(config["ai.temperature"])
    if config.get("ai.max_tokens", ""):
        settings.ai_max_tokens = _to_int(config["ai.max_tokens"])
    if config.get("ai.max_key_points", ""):
        settings.ai_max_key_points = _to_int(config["ai.max_key_points"])
    if config.get("ai.base_url", ""):
        settings.ai_base_url = config["ai.base_url"]
    if config.get("ai.api_key", ""):
        settings.ai_api_key = config["ai.api_key"]
    if config.get("ai.connect_timeout", ""):
        settings.ai_connect_timeout = _to_int(config["ai.connect_timeout"])
    if config.get("ai.read_timeout", ""):
        settings.ai_read_timeout = _to_int(config["ai.read_timeout"])
    if config.get("ai.max_retries", ""):
        settings.ai_max_retries = _to_int(config["ai.max_retries"])
    if config.get("ai.rate_limit_backoff_ms", ""):
        settings.ai_rate_limit_backoff_ms = _to_int(config["ai.rate_limit_backoff_ms"])
    if config.get("ai.single_page_max_chars", ""):
        settings.ai_single_page_max_chars = _to_int(config["ai.single_page_max_chars"])
    if config.get("ai.multi_page_per_max_chars", ""):
        settings.ai_multi_page_per_max_chars = _to_int(config["ai.multi_page_per_max_chars"])
    if config.get("ai.multi_page_total_budget", ""):
        settings.ai_multi_page_total_budget = _to_int(config["ai.multi_page_total_budget"])
    # Digest 专用 AI 参数
    if config.get("ai.digest_per_max_chars", ""):
        settings.ai_digest_per_max_chars = _to_int(config["ai.digest_per_max_chars"])
    if config.get("ai.digest_total_budget", ""):
        settings.ai_digest_total_budget = _to_int(config["ai.digest_total_budget"])
    if config.get("ai.digest_max_tokens", ""):
        settings.ai_digest_max_tokens = _to_int(config["ai.digest_max_tokens"])
    if config.get("ai.min_summary_length", ""):
        settings.ai_min_summary_length = _to_int(config["ai.min_summary_length"])
    if config.get("ai.min_full_content_length", ""):
        settings.ai_min_full_content_length = _to_int(config["ai.min_full_content_length"])
    if config.get("ai.max_tags", ""):
        settings.ai_max_tags = _to_int(config["ai.max_tags"])


def _apply_search_settings(config: dict[str, str]) -> None:
    """搜索配置: search.* → search_*（含部分特殊映射）"""
    if config.get("search.page_timeout_ms", ""):
        settings.search_page_timeout_ms = _to_int(config["search.page_timeout_ms"])
    if config.get("search.browser_fetch_timeout_ms", ""):
        settings.search_browser_fetch_timeout_ms = _to_int(config["search.browser_fetch_timeout_ms"])
    if config.get("search.httpx_fallback_timeout", ""):
        settings.search_httpx_fallback_timeout = _to_int(config["search.httpx_fallback_timeout"])
    if config.get("search.client_timeout", ""):
        settings.search_client_timeout = _to_int(config["search.client_timeout"])
    if config.get("search.warmup_timeout", ""):
        settings.search_warmup_timeout = _to_int(config["search.warmup_timeout"])
    if config.get("search.page_retries", ""):
        settings.search_page_retries = _to_int(config["search.page_retries"])
    if config.get("search.max_pages_per_engine", ""):
        settings.search_max_pages_per_engine = _to_int(config["search.max_pages_per_engine"])
    if config.get("search.min_word_count", ""):
        settings.search_min_word_count = _to_int(config["search.min_word_count"])
    if config.get("search.engine_switch_delay_min", ""):
        settings.search_engine_switch_delay_min = _to_float(config["search.engine_switch_delay_min"])
    if config.get("search.engine_switch_delay_max", ""):
        settings.search_engine_switch_delay_max = _to_float(config["search.engine_switch_delay_max"])
    if config.get("search.page_delay_min", ""):
        settings.search_page_delay_min = _to_float(config["search.page_delay_min"])
    if config.get("search.page_delay_max", ""):
        settings.search_page_delay_max = _to_float(config["search.page_delay_max"])
    if config.get("search.crawl_deadline_seconds", ""):
        settings.search_crawl_deadline_seconds = _to_int(config["search.crawl_deadline_seconds"])
    if config.get("search.progressive_fallback_enabled", ""):
        settings.search_progressive_fallback_enabled = _to_bool(config["search.progressive_fallback_enabled"])
    # 特殊映射: search.max_domain_dedup → max_domain_dedup
    if config.get("search.max_domain_dedup", ""):
        settings.max_domain_dedup = _to_int(config["search.max_domain_dedup"])
    # 特殊映射: search.optimization_round_delay_* → optimization_round_delay_*
    if config.get("search.optimization_round_delay_min", ""):
        settings.optimization_round_delay_min = _to_float(config["search.optimization_round_delay_min"])
    if config.get("search.optimization_round_delay_max", ""):
        settings.optimization_round_delay_max = _to_float(config["search.optimization_round_delay_max"])


def _apply_quality_settings(config: dict[str, str]) -> None:
    """质量评估配置: quality.* → quality_* / eval_*（含命名不一致的映射）"""
    # 直接映射
    if config.get("quality.source_weight", ""):
        settings.quality_source_weight = _to_float(config["quality.source_weight"])
    if config.get("quality.content_weight", ""):
        settings.quality_content_weight = _to_float(config["quality.content_weight"])
    if config.get("quality.keep_threshold", ""):
        settings.quality_keep_threshold = _to_int(config["quality.keep_threshold"])
    if config.get("quality.review_threshold", ""):
        settings.quality_review_threshold = _to_int(config["quality.review_threshold"])
    if config.get("quality.clickbait_keywords", ""):
        settings.quality_clickbait_keywords = config["quality.clickbait_keywords"]
    if config.get("quality.ad_keywords", ""):
        settings.quality_ad_keywords = config["quality.ad_keywords"]
    if config.get("quality.paywall_indicators", ""):
        settings.quality_paywall_indicators = config["quality.paywall_indicators"]
    # 特殊: quality.min_content_length → min_content_length（无 quality_ 前缀）
    if config.get("quality.min_content_length", ""):
        settings.min_content_length = _to_int(config["quality.min_content_length"])
    # 特殊: quality.eval_* → eval_*（无 quality_ 前缀）
    if config.get("quality.eval_pass_threshold", ""):
        settings.eval_pass_threshold = _to_int(config["quality.eval_pass_threshold"])
    if config.get("quality.eval_review_threshold", ""):
        settings.eval_review_threshold = _to_int(config["quality.eval_review_threshold"])
    if config.get("quality.deep_eval_review_threshold", ""):
        settings.deep_eval_review_threshold = _to_int(config["quality.deep_eval_review_threshold"])
    # 特殊: quality.weight_* → eval_weight_*（quality_ → eval_ 前缀变更）
    if config.get("quality.weight_angle", ""):
        settings.eval_weight_angle = _to_float(config["quality.weight_angle"])
    if config.get("quality.weight_source", ""):
        settings.eval_weight_source = _to_float(config["quality.weight_source"])
    if config.get("quality.weight_depth", ""):
        settings.eval_weight_depth = _to_float(config["quality.weight_depth"])
    if config.get("quality.weight_temporal", ""):
        settings.eval_weight_temporal = _to_float(config["quality.weight_temporal"])
    if config.get("quality.weight_perspective", ""):
        settings.eval_weight_perspective = _to_float(config["quality.weight_perspective"])
    if config.get("quality.weight_language", ""):
        settings.eval_weight_language = _to_float(config["quality.weight_language"])


def _apply_digest_settings(config: dict[str, str]) -> None:
    """日报配置: digest.* → digest_*"""
    if config.get("digest.enabled", ""):
        settings.digest_enabled = _to_bool(config["digest.enabled"])
    if config.get("digest.cron", ""):
        settings.digest_cron = config["digest.cron"]
    if config.get("digest.search_engine", ""):
        settings.digest_search_engine = config["digest.search_engine"]
    if config.get("digest.sections", ""):
        settings.digest_sections = config["digest.sections"]
    if config.get("digest.section_result_multiplier", ""):
        settings.digest_section_result_multiplier = _to_int(config["digest.section_result_multiplier"])
    if config.get("digest.inter_section_delay", ""):
        settings.digest_inter_section_delay = _to_float(config["digest.inter_section_delay"])
    if config.get("digest.history_load_count", ""):
        settings.digest_history_load_count = _to_int(config["digest.history_load_count"])
    # 日报质量过滤与优化
    if config.get("digest.filter_min_content", ""):
        settings.digest_filter_min_content = _to_int(config["digest.filter_min_content"])
    if config.get("digest.optimization_enabled", ""):
        settings.digest_optimization_enabled = _to_bool(config["digest.optimization_enabled"])
    if config.get("digest.optimization_min_sections", ""):
        settings.digest_optimization_min_sections = _to_int(config["digest.optimization_min_sections"])
    if config.get("digest.optimization_target_score", ""):
        settings.digest_optimization_target_score = _to_float(config["digest.optimization_target_score"])
    if config.get("digest.parallel_sections", ""):
        settings.digest_parallel_sections = _to_int(config["digest.parallel_sections"])
    if config.get("digest.optimization_min_results_per_section", ""):
        settings.digest_optimization_min_results_per_section = _to_int(config["digest.optimization_min_results_per_section"])
    if config.get("digest.global_timeout", ""):
        settings.digest_global_timeout = _to_int(config["digest.global_timeout"])


def _apply_callback_settings(config: dict[str, str]) -> None:
    """回调配置: callback.* → callback_* / sources_api_timeout"""
    if config.get("callback.url", ""):
        settings.callback_url = config["callback.url"]
    if config.get("callback.timeout", ""):
        settings.callback_timeout = _to_float(config["callback.timeout"])
    # 特殊: callback.sources_timeout → sources_api_timeout（命名不一致）
    if config.get("callback.sources_timeout", ""):
        settings.sources_api_timeout = _to_float(config["callback.sources_timeout"])


def _apply_optimization_settings(config: dict[str, str]) -> None:
    """优化引擎配置: optimization.* → optimization_*"""
    if config.get("optimization.enabled", ""):
        settings.optimization_enabled = _to_bool(config["optimization.enabled"])
    if config.get("optimization.target_score", ""):
        settings.optimization_target_score = _to_float(config["optimization.target_score"])
    if config.get("optimization.max_rounds", ""):
        settings.optimization_max_rounds = _to_int(config["optimization.max_rounds"])
    if config.get("optimization.min_improvement", ""):
        settings.optimization_min_improvement = _to_float(config["optimization.min_improvement"])
    if config.get("optimization.mode", ""):
        settings.optimization_mode = config["optimization.mode"]
    if config.get("optimization.breadth_max_rounds", ""):
        settings.breadth_max_rounds = _to_int(config["optimization.breadth_max_rounds"])


def _apply_bubble_settings(config: dict[str, str]) -> None:
    """茧房突破配置: bubble.* → bubble_*（特殊: bubble.enabled → bubble_breaker_enabled）"""
    # 特殊: bubble.enabled → bubble_breaker_enabled（命名不一致）
    if config.get("bubble.enabled", ""):
        settings.bubble_breaker_enabled = _to_bool(config["bubble.enabled"])
    if config.get("bubble.min_source_diversity", ""):
        settings.bubble_min_source_diversity = _to_float(config["bubble.min_source_diversity"])
    if config.get("bubble.cross_language", ""):
        settings.bubble_cross_language = _to_bool(config["bubble.cross_language"])
    if config.get("bubble.max_translate_tokens", ""):
        settings.bubble_max_translate_tokens = _to_int(config["bubble.max_translate_tokens"])


def _apply_auth_settings(config: dict[str, str]) -> None:
    """认证配置: auth.* → auth_* / api_keys"""
    if config.get("auth.enabled", ""):
        settings.auth_enabled = _to_bool(config["auth.enabled"])
    if config.get("auth.protected_prefixes", ""):
        settings.auth_protected_prefixes = config["auth.protected_prefixes"]
    if config.get("auth.header_name", ""):
        settings.auth_header_name = config["auth.header_name"]
    # 特殊: auth.api_keys → api_keys（无 auth_ 前缀）
    if config.get("auth.api_keys", ""):
        settings.api_keys = config["auth.api_keys"]


def _apply_db_settings(config: dict[str, str]) -> None:
    """SQLite 配置: db.* → db_* / max_concurrent_tasks"""
    if config.get("db.path", ""):
        logger.warning("db.path change ignored at runtime — requires service restart")
    if config.get("db.busy_timeout", ""):
        settings.db_busy_timeout = _to_int(config["db.busy_timeout"])
    # 特殊: db.max_concurrent_tasks → max_concurrent_tasks（无 db_ 前缀）
    if config.get("db.max_concurrent_tasks", ""):
        settings.max_concurrent_tasks = _to_int(config["db.max_concurrent_tasks"])


def _apply_keyword_settings(config: dict[str, str]) -> None:
    """关键词搜索配置: keyword.* → keyword_*"""
    if config.get("keyword.max_consecutive_empty", ""):
        settings.keyword_max_consecutive_empty = _to_int(config["keyword.max_consecutive_empty"])
    if config.get("keyword.max_variants", ""):
        settings.keyword_max_variants = _to_int(config["keyword.max_variants"])
    if config.get("keyword.inter_search_delay", ""):
        settings.keyword_inter_search_delay = _to_float(config["keyword.inter_search_delay"])


def _apply_limit_settings(config: dict[str, str]) -> None:
    """爬取限制配置: limit.* → max_*_limit / max_concurrent_crawls（命名不一致）"""
    if config.get("limit.max_concurrent", ""):
        settings.max_concurrent_crawls = _to_int(config["limit.max_concurrent"])
    if config.get("limit.max_depth", ""):
        settings.max_depth_limit = _to_int(config["limit.max_depth"])
    if config.get("limit.max_pages", ""):
        settings.max_pages_limit = _to_int(config["limit.max_pages"])


def _apply_top_level_settings(config: dict[str, str]) -> None:
    """顶级配置: host/port/debug/log_level/standalone
    注意: host/port/debug/standalone 需重启生效
    """
    if config.get("host", ""):
        logger.warning("host change ignored at runtime — requires service restart")
    if config.get("port", ""):
        logger.warning("port change ignored at runtime — requires service restart")
    if config.get("debug", ""):
        logger.warning("debug change ignored at runtime — requires service restart")
    if config.get("log_level", ""):
        settings.log_level = config["log_level"]
    if config.get("standalone", ""):
        logger.warning("standalone change ignored at runtime — requires service restart")


def _apply_pipeline_settings(config: dict[str, str]) -> None:
    """过滤管线配置: pipeline.* → 对应 settings 属性"""
    if config.get("pipeline.ai_organization_enabled", ""):
        settings.ai_organization_enabled = _to_bool(config["pipeline.ai_organization_enabled"])
    if config.get("pipeline.page_classifier_enabled", ""):
        settings.page_classifier_enabled = _to_bool(config["pipeline.page_classifier_enabled"])
    if config.get("pipeline.content_dedup_enabled", ""):
        settings.content_dedup_enabled = _to_bool(config["pipeline.content_dedup_enabled"])
    if config.get("pipeline.content_dedup_simhash_threshold", ""):
        settings.content_dedup_simhash_threshold = _to_int(config["pipeline.content_dedup_simhash_threshold"])
    if config.get("pipeline.content_dedup_deep_threshold", ""):
        settings.content_dedup_deep_threshold = _to_int(config["pipeline.content_dedup_deep_threshold"])
    if config.get("pipeline.filter_deep_min_content", ""):
        settings.filter_deep_min_content = _to_int(config["pipeline.filter_deep_min_content"])
    if config.get("pipeline.filter_skip_header_chars", ""):
        settings.filter_skip_header_chars = _to_int(config["pipeline.filter_skip_header_chars"])


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
        settings.proxy_url = _ENV_PROXY_URL
        if _ENV_PROXY_URL:
            logger.info("[BackendConfig] Proxy enabled, using env fallback: %s", _ENV_PROXY_URL)


# ============================================================
# 全量配置应用（入口）
# ============================================================

def _apply_all_settings(config: dict[str, str]) -> None:
    """将所有 DB 配置映射到 Pydantic settings 属性"""
    if not config:
        return

    _apply_ai_settings(config)
    _apply_search_settings(config)
    _apply_quality_settings(config)
    _apply_digest_settings(config)
    _apply_callback_settings(config)
    _apply_optimization_settings(config)
    _apply_bubble_settings(config)
    _apply_auth_settings(config)
    _apply_db_settings(config)
    _apply_keyword_settings(config)
    _apply_limit_settings(config)
    _apply_pipeline_settings(config)  # P1-P6: 过滤管线配置
    _apply_top_level_settings(config)
    _apply_proxy_config(config)  # 最后设置代理，覆盖 env 默认值

    logger.info(
        "[BackendConfig] Applied %d config keys to settings",
        len(config),
    )


# ============================================================
# 公共 API
# ============================================================

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
                from standalone.scheduler import stop_scheduler, start_scheduler
                stop_scheduler()
                start_scheduler()
            except Exception:
                logger.warning("Failed to restart scheduler", exc_info=True)

        if old_proxy_enabled != new_proxy_enabled or old_proxy_url != settings.proxy_url:
            logger.info("Proxy config changed: enabled=%s, url=%s", new_proxy_enabled, settings.proxy_url)

    return result
