-- ============================================
-- V1.21: 清理系统配置模块
-- 保留 33 项 admin 实际需要管理的核心配置
-- 删除 64 项过度暴露的调参、部署级配置、死字段
-- Python config.py 默认值作为 fallback 仍然生效
-- ============================================

-- ============================
-- 1. AI 内部调参 (15 项)
-- admin 只需管理: enabled, api_key, base_url, model, max_tokens
-- ============================
DELETE FROM sys_config WHERE config_key IN (
    'crawler.ai.temperature',
    'crawler.ai.connect_timeout',
    'crawler.ai.read_timeout',
    'crawler.ai.max_retries',
    'crawler.ai.rate_limit_backoff_ms',
    'crawler.ai.single_page_max_chars',
    'crawler.ai.multi_page_per_max_chars',
    'crawler.ai.multi_page_total_budget',
    'crawler.ai.max_key_points',
    'crawler.ai.max_tags',
    'crawler.ai.min_summary_length',
    'crawler.ai.min_full_content_length',
    'crawler.ai.digest_per_max_chars',
    'crawler.ai.digest_total_budget',
    'crawler.ai.digest_max_tokens'
) AND is_deleted = FALSE;

-- ============================
-- 2. 搜索调参 (17 项) — 全部删除
-- admin 不需要管理毫秒级延迟和翻页参数
-- ============================
DELETE FROM sys_config WHERE config_key IN (
    'crawler.search.page_timeout_ms',
    'crawler.search.browser_fetch_timeout_ms',
    'crawler.search.httpx_fallback_timeout',
    'crawler.search.client_timeout',
    'crawler.search.warmup_timeout',
    'crawler.search.page_retries',
    'crawler.search.max_pages_per_engine',
    'crawler.search.min_word_count',
    'crawler.search.engine_switch_delay_min',
    'crawler.search.engine_switch_delay_max',
    'crawler.search.page_delay_min',
    'crawler.search.page_delay_max',
    'crawler.search.crawl_deadline_seconds',
    'crawler.search.progressive_fallback_enabled',
    'crawler.search.max_domain_dedup',
    'crawler.search.optimization_round_delay_min',
    'crawler.search.optimization_round_delay_max'
) AND is_deleted = FALSE;

-- ============================
-- 3. 质量评估调参 (16 项) — 全部删除
-- 权重/阈值是算法调参，不应暴露给 admin
-- ============================
DELETE FROM sys_config WHERE config_key IN (
    'crawler.quality.source_weight',
    'crawler.quality.content_weight',
    'crawler.quality.keep_threshold',
    'crawler.quality.review_threshold',
    'crawler.quality.min_content_length',
    'crawler.quality.eval_pass_threshold',
    'crawler.quality.eval_review_threshold',
    'crawler.quality.deep_eval_review_threshold',
    'crawler.quality.weight_angle',
    'crawler.quality.weight_source',
    'crawler.quality.weight_depth',
    'crawler.quality.weight_temporal',
    'crawler.quality.weight_perspective',
    'crawler.quality.weight_language',
    'crawler.quality.clickbait_keywords',
    'crawler.quality.ad_keywords',
    'crawler.quality.paywall_indicators'
) AND is_deleted = FALSE;

-- ============================
-- 4. 日报内部调参 (9 项)
-- admin 只需管理: enabled, cron, sections, search_engine, parallel_sections
-- ============================
DELETE FROM sys_config WHERE config_key IN (
    'crawler.digest.history_load_count',
    'crawler.digest.inter_section_delay',
    'crawler.digest.section_result_multiplier',
    'crawler.digest.filter_min_content',
    'crawler.digest.optimization_enabled',
    'crawler.digest.optimization_min_sections',
    'crawler.digest.optimization_min_results_per_section',
    'crawler.digest.optimization_target_score',
    'crawler.digest.global_timeout'
) AND is_deleted = FALSE;

-- ============================
-- 5. 优化引擎调参 (3 项)
-- admin 只需管理: enabled, mode, max_rounds
-- ============================
DELETE FROM sys_config WHERE config_key IN (
    'crawler.optimization.min_improvement',
    'crawler.optimization.target_score',
    'crawler.optimization.breadth_max_rounds'
) AND is_deleted = FALSE;

-- ============================
-- 6. 管线调参 (5 项)
-- admin 只需管理: 三个开关
-- ============================
DELETE FROM sys_config WHERE config_key IN (
    'crawler.pipeline.content_dedup_simhash_threshold',
    'crawler.pipeline.content_dedup_deep_threshold',
    'crawler.pipeline.filter_deep_min_content',
    'crawler.pipeline.filter_skip_header_chars',
    'crawler.pipeline.filter_content_preview_length'
) AND is_deleted = FALSE;

-- ============================
-- 7. 茧房突破调参 (3 项)
-- admin 只需管理: enabled 开关
-- ============================
DELETE FROM sys_config WHERE config_key IN (
    'crawler.bubble.min_source_diversity',
    'crawler.bubble.cross_language',
    'crawler.bubble.max_translate_tokens'
) AND is_deleted = FALSE;

-- ============================
-- 8. 认证调参 (1 项)
-- header_name 极少修改，删除
-- ============================
DELETE FROM sys_config WHERE config_key = 'crawler.auth.header_name' AND is_deleted = FALSE;

-- ============================
-- 9. 回调调参 (1 项)
-- sources_timeout 极少修改，删除
-- ============================
DELETE FROM sys_config WHERE config_key = 'crawler.callback.sources_timeout' AND is_deleted = FALSE;

-- ============================
-- 10. 部署级配置 (5 项)
-- host/port/debug/standalone/db_path 应走 .env 或部署配置，不应在 DB 管理
-- ============================
DELETE FROM sys_config WHERE config_key IN (
    'crawler.host',
    'crawler.port',
    'crawler.debug',
    'crawler.standalone',
    'crawler.db.path'
) AND is_deleted = FALSE;

-- ============================
-- 11. DB 调参 (2 项)
-- busy_timeout 和 max_concurrent_tasks 极少修改
-- ============================
DELETE FROM sys_config WHERE config_key IN (
    'crawler.db.busy_timeout',
    'crawler.db.max_concurrent_tasks'
) AND is_deleted = FALSE;

-- ============================
-- 12. Java HTTP 连接池 (2 项)
-- Java 侧连接池调参，admin 不需要管理
-- ============================
DELETE FROM sys_config WHERE config_key IN (
    'crawler.http.pool.max-per-route',
    'crawler.http.pool.max-total'
) AND is_deleted = FALSE;

-- ============================
-- 13. Java 服务超时 (2 项)
-- connect-timeout/read-timeout Java 侧有合理默认值
-- ============================
DELETE FROM sys_config WHERE config_key IN (
    'crawler.service.connect-timeout',
    'crawler.service.read-timeout'
) AND is_deleted = FALSE;

-- ============================
-- 14. 关键词搜索调参 (3 项)
-- 搜索行为调参，admin 不需要管理
-- ============================
DELETE FROM sys_config WHERE config_key IN (
    'crawler.keyword.max_consecutive_empty',
    'crawler.keyword.max_variants',
    'crawler.keyword.inter_search_delay'
) AND is_deleted = FALSE;

-- ============================
-- 15. 加密密钥 (1 项)
-- blog.security.encryption-key 通过 @Value 从 application.yml 读取
-- DB 中的值完全无效（改了也不生效），删除避免误导
-- ============================
DELETE FROM sys_config WHERE config_key = 'blog.security.encryption-key' AND is_deleted = FALSE;
