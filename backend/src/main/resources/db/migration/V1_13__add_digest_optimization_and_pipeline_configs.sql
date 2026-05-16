-- ============================================
-- V1.13: 新增日报优化 + 过滤管线配置种子
-- 1. 修复 optimization.mode 默认值 keyword → both
-- 2. 新增日报优化独立开关和阈值
-- 3. 新增过滤管线配置（pipeline.*）
-- ============================================

-- 1. 修复 optimization.mode 默认值
UPDATE sys_config
SET config_value = 'both', default_value = 'both'
WHERE config_key = 'crawler.optimization.mode' AND is_deleted = FALSE;

-- 2. 新增日报优化配置（幂等：ON CONFLICT DO NOTHING）
INSERT INTO sys_config (config_key, config_value, default_value, description, group_name, is_public, input_type, is_encrypted, is_sensitive)
VALUES
    ('crawler.digest.filter_min_content', '50', '50', '日报质量过滤最低字符数', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.digest.optimization_enabled', 'false', 'false', '日报优化独立开关', 'crawler', FALSE, 'switch', FALSE, FALSE),
    ('crawler.digest.optimization_min_sections', '2', '2', '触发优化最少板块数', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.digest.optimization_target_score', '0.65', '0.65', '日报优化目标分', 'crawler', FALSE, 'text', FALSE, FALSE)
ON CONFLICT (config_key) DO NOTHING;

-- 3. 新增过滤管线配置（幂等：ON CONFLICT DO NOTHING）
INSERT INTO sys_config (config_key, config_value, default_value, description, group_name, is_public, input_type, is_encrypted, is_sensitive)
VALUES
    ('crawler.pipeline.ai_organization_enabled', 'true', 'true', 'AI整理开关', 'crawler', FALSE, 'switch', FALSE, FALSE),
    ('crawler.pipeline.content_dedup_enabled', 'true', 'true', '内容去重开关', 'crawler', FALSE, 'switch', FALSE, FALSE),
    ('crawler.pipeline.content_dedup_simhash_threshold', '5', '5', '去重汉明距离阈值', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.pipeline.content_dedup_deep_threshold', '3', '3', '深度爬取去重汉明距离', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.pipeline.filter_deep_min_content', '20', '20', '深度爬取最小内容长度', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.pipeline.page_classifier_enabled', 'true', 'true', '页面分类器开关', 'crawler', FALSE, 'switch', FALSE, FALSE),
    ('crawler.pipeline.filter_skip_header_chars', '200', '200', '去重指纹跳过头部字符数', 'crawler', FALSE, 'text', FALSE, FALSE)
ON CONFLICT (config_key) DO NOTHING;
