-- ============================================
-- V1.15: 补充优化系统缺失配置项
-- 1. 日报专用 AI 参数（3 项）
-- 2. 日报并行与超时配置（2 项）
-- 3. 日报优化补充配置（1 项）
-- 幂等：ON CONFLICT (config_key) DO NOTHING
-- ============================================

-- 1. 日报专用 AI 参数（归入 AI 整理 section）
INSERT INTO sys_config (config_key, config_value, default_value, description, group_name, is_public, input_type, is_encrypted, is_sensitive)
VALUES
    ('crawler.ai.digest_per_max_chars', '8000', '8000', '日报每页输入字符上限', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.ai.digest_total_budget', '100000', '100000', '日报总输入字符预算', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.ai.digest_max_tokens', '10000', '10000', '日报AI输出最大Token数', 'crawler', FALSE, 'text', FALSE, FALSE)
ON CONFLICT (config_key) DO NOTHING;

-- 2. 日报并行与超时配置（归入日报 section）
INSERT INTO sys_config (config_key, config_value, default_value, description, group_name, is_public, input_type, is_encrypted, is_sensitive)
VALUES
    ('crawler.digest.parallel_sections', '2', '2', '日报板块并行爬取上限', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.digest.global_timeout', '600', '600', '日报全局超时(秒)', 'crawler', FALSE, 'text', FALSE, FALSE)
ON CONFLICT (config_key) DO NOTHING;

-- 3. 日报优化补充配置（归入日报 section）
INSERT INTO sys_config (config_key, config_value, default_value, description, group_name, is_public, input_type, is_encrypted, is_sensitive)
VALUES
    ('crawler.digest.optimization_min_results_per_section', '3', '3', '每板块最少结果数触发优化', 'crawler', FALSE, 'text', FALSE, FALSE)
ON CONFLICT (config_key) DO NOTHING;
