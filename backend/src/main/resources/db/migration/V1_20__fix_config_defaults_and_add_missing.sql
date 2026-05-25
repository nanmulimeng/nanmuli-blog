-- ============================================
-- V1.20: Fix config default value mismatches & add missing config
-- 1. Fix ai.digest_max_tokens (10000 → 16000, Python 设计需要更多空间给5板块+条目)
-- 2. Fix digest.search_engine (bing → sogou, 中文技术内容搜索效果更优)
-- 3. Add missing pipeline.filter_content_preview_length
-- 4. Add missing service.java-api-url（Python 回调 Java 后端的地址）
-- ============================================

-- 1. 日报 AI 输出上限对齐 Python 默认值
UPDATE sys_config
SET config_value = '16000', default_value = '16000'
WHERE config_key = 'crawler.ai.digest_max_tokens' AND is_deleted = FALSE;

-- 2. 日报搜索引擎对齐 Python 默认值（sogou 对中文技术内容搜索效果优于 bing）
UPDATE sys_config
SET config_value = 'sogou', default_value = 'sogou'
WHERE config_key = 'crawler.digest.search_engine' AND is_deleted = FALSE;

-- 3. 添加缺失的过滤管线配置（幂等）
INSERT INTO sys_config (config_key, config_value, default_value, description, group_name, is_public, input_type, is_encrypted, is_sensitive)
VALUES ('crawler.pipeline.filter_content_preview_length', '800', '800', '去重指纹预览长度', 'crawler', FALSE, 'text', FALSE, FALSE)
ON CONFLICT (config_key) DO NOTHING;

-- 4. 添加 Java 后端地址配置（Python 侧用于回调/拉取配置的目标地址）
INSERT INTO sys_config (config_key, config_value, default_value, description, group_name, is_public, input_type, is_encrypted, is_sensitive)
VALUES ('crawler.service.java-api-url', 'http://localhost:8081', 'http://localhost:8081', 'Java后端地址（供Python回调/拉取配置）', 'crawler', FALSE, 'text', FALSE, FALSE)
ON CONFLICT (config_key) DO NOTHING;
