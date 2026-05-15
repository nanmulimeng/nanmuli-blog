-- ============================================
-- V1.12: sys_config 表统合与扩展
-- 1. 合并 init.sql 与 deploy/db/init-scripts/schema.sql 的列分歧
-- 2. 新增 is_encrypted / is_sensitive 列
-- 3. 标记已有敏感配置
-- 4. 新增 Java 侧 DB 化所需的种子数据
-- ============================================

-- 1. 补齐 deploy/schema.sql 缺失的 input_type 列
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'sys_config' AND column_name = 'input_type'
    ) THEN
        ALTER TABLE sys_config ADD COLUMN input_type VARCHAR(20) NOT NULL DEFAULT 'text';
        COMMENT ON COLUMN sys_config.input_type IS '输入控件类型: text/textarea/switch/image/password';
    END IF;
END $$;

-- 2. 补齐 init.sql 缺失的 default_value 列
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'sys_config' AND column_name = 'default_value'
    ) THEN
        ALTER TABLE sys_config ADD COLUMN default_value TEXT;
        COMMENT ON COLUMN sys_config.default_value IS '默认值';
    END IF;
END $$;

-- 3. 新增 is_encrypted 列（AES-128 加密存储标记）
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'sys_config' AND column_name = 'is_encrypted'
    ) THEN
        ALTER TABLE sys_config ADD COLUMN is_encrypted BOOLEAN NOT NULL DEFAULT FALSE;
        COMMENT ON COLUMN sys_config.is_encrypted IS '是否加密存储（AES-128），敏感值如 API Key 设为 true';
    END IF;
END $$;

-- 4. 新增 is_sensitive 列（前端遮罩显示标记）
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'sys_config' AND column_name = 'is_sensitive'
    ) THEN
        ALTER TABLE sys_config ADD COLUMN is_sensitive BOOLEAN NOT NULL DEFAULT FALSE;
        COMMENT ON COLUMN sys_config.is_sensitive IS '是否敏感配置，前端显示为脱敏值';
    END IF;
END $$;

-- 5. 标记已有敏感配置（API Key 等需要加密存储的）
UPDATE sys_config
SET is_encrypted = TRUE, is_sensitive = TRUE, input_type = 'password'
WHERE config_key IN (
    'crawler.ai.api_key'
);

-- 6. 统一 group_name: 确保 crawler.ai.* 配置都在 crawler 组
UPDATE sys_config
SET group_name = 'crawler'
WHERE config_key LIKE 'crawler.%' AND group_name != 'crawler';

-- 7. 清理 deploy/schema.sql 遗留的旧 AI 配置（与 crawler.ai.* 重复）
DELETE FROM sys_config
WHERE config_key IN ('ai.enabled', 'ai.model', 'ai.autoTags', 'ai.autoSummary')
  AND EXISTS (
    SELECT 1 FROM sys_config sc2
    WHERE sc2.config_key LIKE 'crawler.ai.%'
);

-- 8. Phase 2-3: 全量爬虫配置种子数据（开发环境自动就绪）
INSERT INTO sys_config (config_key, config_value, default_value, description, group_name, is_public, input_type, is_encrypted, is_sensitive)
VALUES
    -- AI 配置 (18)
    ('crawler.ai.api_key', '', '', 'AI API密钥（DashScope）', 'crawler', FALSE, 'password', TRUE, TRUE),
    ('crawler.ai.base_url', 'https://api.deepseek.com/v1', '', 'AI API 端点地址', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.ai.connect_timeout', '10', '', 'AI API 连接超时(秒)', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.ai.enabled', 'false', 'false', '爬虫AI功能开关', 'crawler', FALSE, 'switch', FALSE, FALSE),
    ('crawler.ai.max_key_points', '10', '', '最大要点数', 'crawler', FALSE, 'text', TRUE, TRUE),
    ('crawler.ai.max_retries', '2', '', 'AI 调用最大重试次数', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.ai.max_tags', '10', '', '最大标签数', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.ai.max_tokens', '8000', '', 'AI 最大输出 Token', 'crawler', FALSE, 'text', TRUE, TRUE),
    ('crawler.ai.min_full_content_length', '20', '', '全文最小长度(字符)', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.ai.min_summary_length', '10', '', '摘要最小长度(字符)', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.ai.model', 'deepseek-v4-pro', 'qwen-plus', 'AI模型名称', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.ai.multi_page_per_max_chars', '20000', '', '多页每页最大字符数', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.ai.multi_page_total_budget', '150000', '', '多页总字符预算', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.ai.rate_limit_backoff_ms', '10000', '', '限流后退等待(毫秒)', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.ai.read_timeout', '90', '', 'AI API 读取超时(秒)', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.ai.single_page_max_chars', '80000', '', '单页最大字符数', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.ai.temperature', '0.3', '', 'LLM 温度参数 (0-2)', 'crawler', FALSE, 'text', FALSE, FALSE),
    -- 认证配置 (4)
    ('crawler.auth.api_keys', '', '', 'API密钥列表(逗号分隔)', 'crawler', FALSE, 'password', TRUE, TRUE),
    ('crawler.auth.enabled', 'true', 'true', '认证开关', 'crawler', FALSE, 'switch', FALSE, FALSE),
    ('crawler.auth.header_name', 'X-API-Key', 'X-API-Key', '认证头名称', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.auth.protected_prefixes', '/api/v1,/crawl,/organize,/keyword', '/api/v1,/crawl,/organize,/keyword', '受保护路径前缀', 'crawler', FALSE, 'text', FALSE, FALSE),
    -- 茧房突破 (4)
    ('crawler.bubble.cross_language', 'true', 'true', '跨语言搜索', 'crawler', FALSE, 'switch', FALSE, FALSE),
    ('crawler.bubble.enabled', 'false', 'false', '信息茧房突破开关', 'crawler', FALSE, 'switch', FALSE, FALSE),
    ('crawler.bubble.max_translate_tokens', '200', '200', '最大翻译Token数', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.bubble.min_source_diversity', '0.6', '0.6', '最小来源多样性', 'crawler', FALSE, 'text', FALSE, FALSE),
    -- 回调/外部服务 (4)
    ('crawler.callback.api-key', '', '', '回调认证密钥（Java/Python共享）', 'crawler', FALSE, 'password', TRUE, TRUE),
    ('crawler.callback.sources_timeout', '5.0', '5.0', '订阅源API超时(秒)', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.callback.timeout', '5.0', '5.0', '回调超时(秒)', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.callback.url', '', '', '任务完成回调URL', 'crawler', FALSE, 'text', FALSE, FALSE),
    -- SQLite 数据库 (3)
    ('crawler.db.busy_timeout', '5000', '5000', 'SQLite忙等待超时(ms)', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.db.max_concurrent_tasks', '3', '3', '最大并发任务数', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.db.path', 'data/crawler.db', 'data/crawler.db', 'SQLite数据库路径', 'crawler', FALSE, 'text', FALSE, FALSE),
    -- 服务基础 (5)
    ('crawler.debug', 'false', 'false', 'Debug模式', 'crawler', FALSE, 'switch', FALSE, FALSE),
    ('crawler.host', '0.0.0.0', '0.0.0.0', '爬虫服务监听地址', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.log_level', 'INFO', 'INFO', '日志级别', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.port', '8500', '8500', '爬虫服务监听端口', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.standalone', 'true', 'true', '独立模式', 'crawler', FALSE, 'switch', FALSE, FALSE),
    -- 日报 (7)
    ('crawler.digest.cron', '0 8 * * 1-5', '0 8 * * 1-5', '日报CRON表达式', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.digest.enabled', 'false', 'false', '定时日报生成开关', 'crawler', FALSE, 'switch', FALSE, FALSE),
    ('crawler.digest.history_load_count', '3', '3', '加载最近N期日报去重', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.digest.inter_section_delay', '2.0', '2.0', '日报板块间延迟(秒)', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.digest.search_engine', 'bing', 'bing', '日报专用搜索引擎', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.digest.section_result_multiplier', '2', '2', '日报板块结果倍数', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.digest.sections', '[{"name":"news","keyword":"tech news","time_range":"day","max_items":5}]', '[{"name":"news","keyword":"tech news","time_range":"day","max_items":5}]', '日报板块配置(JSON)', 'crawler', FALSE, 'textarea', FALSE, FALSE),
    -- Java 侧 HTTP 连接池 (2)
    ('crawler.http.pool.max-per-route', '10', '10', '单路由最大连接数', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.http.pool.max-total', '20', '20', 'HTTP连接池最大连接数', 'crawler', FALSE, 'text', FALSE, FALSE),
    -- 关键词搜索 (3)
    ('crawler.keyword.inter_search_delay', '2.0', '2.0', '多关键词搜索间隔(秒)', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.keyword.max_consecutive_empty', '2', '2', '连续空结果停止阈值', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.keyword.max_variants', '4', '4', 'AI扩展关键词最大变体数', 'crawler', FALSE, 'text', FALSE, FALSE),
    -- 爬取限制 (3)
    ('crawler.limit.max_concurrent', '3', '3', '最大并发爬取数', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.limit.max_depth', '3', '3', '最大爬取深度', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.limit.max_pages', '20', '20', '最大爬取页数', 'crawler', FALSE, 'text', FALSE, FALSE),
    -- 搜索优化 (5)
    ('crawler.optimization.enabled', 'false', 'false', '自动优化引擎开关', 'crawler', FALSE, 'switch', FALSE, FALSE),
    ('crawler.optimization.max_rounds', '3', '3', '最大优化轮数', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.optimization.min_improvement', '0.03', '0.03', '最小改进阈值', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.optimization.mode', 'keyword', 'keyword', '优化模式(keyword/digest/both)', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.optimization.target_score', '0.7', '0.7', '优化目标分数', 'crawler', FALSE, 'text', FALSE, FALSE),
    -- 代理 (3)
    ('crawler.proxy.enabled', 'false', '', '是否启用代理', 'crawler', FALSE, 'switch', FALSE, FALSE),
    ('crawler.proxy.subscription_url', '', '', '代理订阅地址', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.proxy.url', '', '', 'HTTP代理地址', 'crawler', FALSE, 'text', FALSE, FALSE),
    -- 质量关键词 (3)
    ('crawler.quality.ad_keywords', '限时优惠,点击购买,立即下单,免费试用,优惠券,折扣码,推广链接,affiliate,赞助内容,广告合作,扫码领取,关注公众号,限量,秒杀,抢购,不容错过,错过等一年', '限时优惠,点击购买,立即下单', '广告关键词(逗号分隔)', 'crawler', FALSE, 'textarea', FALSE, FALSE),
    ('crawler.quality.clickbait_keywords', '震惊,绝了,逆天,炸裂,颠覆,史诗,神级,99%的人不知道,看完我沉默了,后悔没早点,太可怕了,万万没想到,不可思议,惊人,史上最强,全网首发,独家揭秘,内幕,震惊中外,轰动,爆款,疯传,shocking,unbelievable,mind-blowing,epic,you will not believe,this changes everything', '震惊,绝了,逆天,炸裂,颠覆,史诗,神级', '标题党关键词(逗号分隔)', 'crawler', FALSE, 'textarea', FALSE, FALSE),
    ('crawler.quality.paywall_indicators', 'subscribe to read,membership required,premium content,登录后阅读,订阅后查看,会员专属,付费阅读,sign up to continue,create an account', 'subscribe to read,membership required', '付费墙关键词(逗号分隔)', 'crawler', FALSE, 'textarea', FALSE, FALSE),
    -- 质量评估权重/阈值 (13)
    ('crawler.quality.content_weight', '0.6', '0.6', '内容质量权重', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.quality.deep_eval_review_threshold', '25', '25', '深度爬取审查阈值', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.quality.eval_pass_threshold', '65', '65', '综合评分:通过阈值', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.quality.eval_review_threshold', '45', '45', '综合评分:审查阈值', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.quality.keep_threshold', '70', '70', '质量推荐:保留阈值', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.quality.min_content_length', '100', '100', '最低内容字符数', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.quality.review_threshold', '50', '50', '质量推荐:审查阈值', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.quality.source_weight', '0.4', '0.4', '来源可信度权重', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.quality.weight_angle', '0.25', '0.25', '评估权重:角度', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.quality.weight_depth', '0.15', '0.15', '评估权重:深度', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.quality.weight_language', '0.10', '0.10', '评估权重:语言', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.quality.weight_perspective', '0.15', '0.15', '评估权重:视角', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.quality.weight_source', '0.20', '0.20', '评估权重:来源', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.quality.weight_temporal', '0.15', '0.15', '评估权重:时效', 'crawler', FALSE, 'text', FALSE, FALSE),
    -- 搜索超时/延迟 (17)
    ('crawler.search.browser_fetch_timeout_ms', '20000', '20000', '浏览器抓取超时(ms)', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.search.client_timeout', '30', '30', '共享搜索客户端超时(秒)', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.search.crawl_deadline_seconds', '300', '300', '整体爬取超时(秒)', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.search.engine_switch_delay_max', '5.0', '5.0', '引擎切换最大延迟(秒)', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.search.engine_switch_delay_min', '2.0', '2.0', '引擎切换最小延迟(秒)', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.search.httpx_fallback_timeout', '15', '15', 'httpx降级超时(秒)', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.search.max_domain_dedup', '2', '2', '同域名去重上限', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.search.max_pages_per_engine', '5', '5', '每个搜索引擎最大翻页数', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.search.min_word_count', '50', '50', '搜索结果最小词数', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.search.optimization_round_delay_max', '4.0', '4.0', '优化轮次最大延迟(秒)', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.search.optimization_round_delay_min', '2.0', '2.0', '优化轮次最小延迟(秒)', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.search.page_delay_max', '2.0', '2.0', '翻页最大延迟(秒)', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.search.page_delay_min', '0.8', '0.8', '翻页最小延迟(秒)', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.search.page_retries', '2', '2', '搜索页获取重试次数', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.search.page_timeout_ms', '15000', '15000', '搜索结果页超时(ms)', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.search.progressive_fallback_enabled', 'true', 'true', '渐进式回退开关', 'crawler', FALSE, 'switch', FALSE, FALSE),
    ('crawler.search.warmup_timeout', '10', '10', '搜狗预热超时(秒)', 'crawler', FALSE, 'text', FALSE, FALSE),
    -- Java 侧服务连接 (4)
    ('crawler.service.api-key', '', '', 'Python API认证密钥', 'crawler', FALSE, 'password', TRUE, TRUE),
    ('crawler.service.base-url', 'http://localhost:8500', 'http://localhost:8500', 'Python爬虫服务地址', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.service.connect-timeout', '10000', '10000', '连接超时(毫秒)', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.service.read-timeout', '30000', '30000', '读取超时(毫秒)', 'crawler', FALSE, 'text', FALSE, FALSE),
    -- AES 加密密钥 (1)
    ('blog.security.encryption-key', 'nanmuli-blog-key', 'nanmuli-blog-key', 'AES-128加密密钥（16字节）', 'blog', FALSE, 'password', TRUE, TRUE)
ON CONFLICT DO NOTHING;

-- 9. 对已存在的配置行补齐新字段（覆盖 description/group_name/is_encrypted 等元数据）
UPDATE sys_config SET
    description = v.description,
    group_name = v.group_name,
    is_encrypted = v.is_encrypted,
    is_sensitive = v.is_sensitive,
    input_type = v.input_type,
    default_value = v.default_value
FROM (VALUES
    ('crawler.ai.api_key', '', 'AI API密钥（DashScope）', 'crawler', TRUE, TRUE, 'password', ''),
    ('crawler.ai.base_url', 'https://api.deepseek.com/v1', 'AI API 端点地址', 'crawler', FALSE, FALSE, 'text', ''),
    ('crawler.ai.connect_timeout', '10', 'AI API 连接超时(秒)', 'crawler', FALSE, FALSE, 'text', ''),
    ('crawler.ai.enabled', 'false', '爬虫AI功能开关', 'crawler', FALSE, FALSE, 'switch', 'false'),
    ('crawler.ai.max_key_points', '10', '最大要点数', 'crawler', TRUE, TRUE, 'text', ''),
    ('crawler.ai.max_retries', '2', 'AI 调用最大重试次数', 'crawler', FALSE, FALSE, 'text', ''),
    ('crawler.ai.max_tags', '10', '最大标签数', 'crawler', FALSE, FALSE, 'text', ''),
    ('crawler.ai.max_tokens', '8000', 'AI 最大输出 Token', 'crawler', TRUE, TRUE, 'text', ''),
    ('crawler.ai.min_full_content_length', '20', '全文最小长度(字符)', 'crawler', FALSE, FALSE, 'text', ''),
    ('crawler.ai.min_summary_length', '10', '摘要最小长度(字符)', 'crawler', FALSE, FALSE, 'text', ''),
    ('crawler.ai.model', 'deepseek-v4-pro', 'AI模型名称', 'crawler', FALSE, FALSE, 'text', 'qwen-plus'),
    ('crawler.ai.multi_page_per_max_chars', '20000', '多页每页最大字符数', 'crawler', FALSE, FALSE, 'text', ''),
    ('crawler.ai.multi_page_total_budget', '150000', '多页总字符预算', 'crawler', FALSE, FALSE, 'text', ''),
    ('crawler.ai.rate_limit_backoff_ms', '10000', '限流后退等待(毫秒)', 'crawler', FALSE, FALSE, 'text', ''),
    ('crawler.ai.read_timeout', '90', 'AI API 读取超时(秒)', 'crawler', FALSE, FALSE, 'text', ''),
    ('crawler.ai.single_page_max_chars', '80000', '单页最大字符数', 'crawler', FALSE, FALSE, 'text', ''),
    ('crawler.ai.temperature', '0.3', 'LLM 温度参数 (0-2)', 'crawler', FALSE, FALSE, 'text', ''),
    ('crawler.auth.api_keys', '', 'API密钥列表(逗号分隔)', 'crawler', TRUE, TRUE, 'password', ''),
    ('crawler.auth.enabled', 'true', '认证开关', 'crawler', FALSE, FALSE, 'switch', 'true'),
    ('crawler.auth.header_name', 'X-API-Key', '认证头名称', 'crawler', FALSE, FALSE, 'text', 'X-API-Key'),
    ('crawler.auth.protected_prefixes', '/api/v1,/crawl,/organize,/keyword', '受保护路径前缀', 'crawler', FALSE, FALSE, 'text', '/api/v1,/crawl,/organize,/keyword'),
    ('crawler.bubble.cross_language', 'true', '跨语言搜索', 'crawler', FALSE, FALSE, 'switch', 'true'),
    ('crawler.bubble.enabled', 'false', '信息茧房突破开关', 'crawler', FALSE, FALSE, 'switch', 'false'),
    ('crawler.bubble.max_translate_tokens', '200', '最大翻译Token数', 'crawler', FALSE, FALSE, 'text', '200'),
    ('crawler.bubble.min_source_diversity', '0.6', '最小来源多样性', 'crawler', FALSE, FALSE, 'text', '0.6'),
    ('crawler.callback.api-key', '', '回调认证密钥（Java/Python共享）', 'crawler', TRUE, TRUE, 'password', ''),
    ('crawler.callback.sources_timeout', '5.0', '订阅源API超时(秒)', 'crawler', FALSE, FALSE, 'text', '5.0'),
    ('crawler.callback.timeout', '5.0', '回调超时(秒)', 'crawler', FALSE, FALSE, 'text', '5.0'),
    ('crawler.callback.url', '', '任务完成回调URL', 'crawler', FALSE, FALSE, 'text', ''),
    ('crawler.db.busy_timeout', '5000', 'SQLite忙等待超时(ms)', 'crawler', FALSE, FALSE, 'text', '5000'),
    ('crawler.db.max_concurrent_tasks', '3', '最大并发任务数', 'crawler', FALSE, FALSE, 'text', '3'),
    ('crawler.db.path', 'data/crawler.db', 'SQLite数据库路径', 'crawler', FALSE, FALSE, 'text', 'data/crawler.db'),
    ('crawler.debug', 'false', 'Debug模式', 'crawler', FALSE, FALSE, 'switch', 'false'),
    ('crawler.host', '0.0.0.0', '爬虫服务监听地址', 'crawler', FALSE, FALSE, 'text', '0.0.0.0'),
    ('crawler.log_level', 'INFO', '日志级别', 'crawler', FALSE, FALSE, 'text', 'INFO'),
    ('crawler.port', '8500', '爬虫服务监听端口', 'crawler', FALSE, FALSE, 'text', '8500'),
    ('crawler.standalone', 'true', '独立模式', 'crawler', FALSE, FALSE, 'switch', 'true'),
    ('crawler.digest.cron', '0 8 * * 1-5', '日报CRON表达式', 'crawler', FALSE, FALSE, 'text', '0 8 * * 1-5'),
    ('crawler.digest.enabled', 'false', '定时日报生成开关', 'crawler', FALSE, FALSE, 'switch', 'false'),
    ('crawler.digest.history_load_count', '3', '加载最近N期日报去重', 'crawler', FALSE, FALSE, 'text', '3'),
    ('crawler.digest.inter_section_delay', '2.0', '日报板块间延迟(秒)', 'crawler', FALSE, FALSE, 'text', '2.0'),
    ('crawler.digest.search_engine', 'bing', '日报专用搜索引擎', 'crawler', FALSE, FALSE, 'text', 'bing'),
    ('crawler.digest.section_result_multiplier', '2', '日报板块结果倍数', 'crawler', FALSE, FALSE, 'text', '2'),
    ('crawler.digest.sections', '[{"name":"news","keyword":"tech news","time_range":"day","max_items":5}]', '日报板块配置(JSON)', 'crawler', FALSE, FALSE, 'textarea', '[{"name":"news","keyword":"tech news","time_range":"day","max_items":5}]'),
    ('crawler.http.pool.max-per-route', '10', '单路由最大连接数', 'crawler', FALSE, FALSE, 'text', '10'),
    ('crawler.http.pool.max-total', '20', 'HTTP连接池最大连接数', 'crawler', FALSE, FALSE, 'text', '20'),
    ('crawler.keyword.inter_search_delay', '2.0', '多关键词搜索间隔(秒)', 'crawler', FALSE, FALSE, 'text', '2.0'),
    ('crawler.keyword.max_consecutive_empty', '2', '连续空结果停止阈值', 'crawler', FALSE, FALSE, 'text', '2'),
    ('crawler.keyword.max_variants', '4', 'AI扩展关键词最大变体数', 'crawler', FALSE, FALSE, 'text', '4'),
    ('crawler.limit.max_concurrent', '3', '最大并发爬取数', 'crawler', FALSE, FALSE, 'text', '3'),
    ('crawler.limit.max_depth', '3', '最大爬取深度', 'crawler', FALSE, FALSE, 'text', '3'),
    ('crawler.limit.max_pages', '20', '最大爬取页数', 'crawler', FALSE, FALSE, 'text', '20'),
    ('crawler.optimization.enabled', 'false', '自动优化引擎开关', 'crawler', FALSE, FALSE, 'switch', 'false'),
    ('crawler.optimization.max_rounds', '3', '最大优化轮数', 'crawler', FALSE, FALSE, 'text', '3'),
    ('crawler.optimization.min_improvement', '0.03', '最小改进阈值', 'crawler', FALSE, FALSE, 'text', '0.03'),
    ('crawler.optimization.mode', 'keyword', '优化模式(keyword/digest/both)', 'crawler', FALSE, FALSE, 'text', 'keyword'),
    ('crawler.optimization.target_score', '0.7', '优化目标分数', 'crawler', FALSE, FALSE, 'text', '0.7'),
    ('crawler.proxy.enabled', 'false', '是否启用代理', 'crawler', FALSE, FALSE, 'switch', ''),
    ('crawler.proxy.subscription_url', '', '代理订阅地址', 'crawler', FALSE, FALSE, 'text', ''),
    ('crawler.proxy.url', '', 'HTTP代理地址', 'crawler', FALSE, FALSE, 'text', ''),
    ('crawler.service.api-key', '', 'Python API认证密钥', 'crawler', TRUE, TRUE, 'password', ''),
    ('crawler.service.base-url', 'http://localhost:8500', 'Python爬虫服务地址', 'crawler', FALSE, FALSE, 'text', 'http://localhost:8500'),
    ('crawler.service.connect-timeout', '10000', '连接超时(毫秒)', 'crawler', FALSE, FALSE, 'text', '10000'),
    ('crawler.service.read-timeout', '30000', '读取超时(毫秒)', 'crawler', FALSE, FALSE, 'text', '30000'),
    ('blog.security.encryption-key', 'nanmuli-blog-key', 'AES-128加密密钥（16字节）', 'blog', TRUE, TRUE, 'password', 'nanmuli-blog-key')
) AS v(config_key, default_value, description, group_name, is_encrypted, is_sensitive, input_type, dv)
WHERE sys_config.config_key = v.config_key
  AND sys_config.is_deleted = FALSE
  AND (sys_config.description IS DISTINCT FROM v.description
    OR sys_config.group_name IS DISTINCT FROM v.group_name
    OR sys_config.is_encrypted IS DISTINCT FROM v.is_encrypted
    OR sys_config.is_sensitive IS DISTINCT FROM v.is_sensitive
    OR sys_config.input_type IS DISTINCT FROM v.input_type
    OR sys_config.default_value IS DISTINCT FROM v.dv);
