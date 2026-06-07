-- V1.20: fix crawler config defaults and add missing config.

UPDATE sys_config
SET config_value = '16000', default_value = '16000'
WHERE config_key = 'crawler.ai.digest_max_tokens' AND is_deleted = FALSE;

UPDATE sys_config
SET config_value = 'sogou', default_value = 'sogou'
WHERE config_key = 'crawler.digest.search_engine' AND is_deleted = FALSE;

INSERT INTO sys_config (
    config_key, config_value, default_value, description,
    group_name, is_public, input_type, is_encrypted, is_sensitive
)
SELECT *
FROM (VALUES
    ('crawler.pipeline.filter_content_preview_length', '800', '800', 'Dedup fingerprint preview length', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.service.java-api-url', 'http://localhost:8081', 'http://localhost:8081', 'Java backend URL for crawler callback and config fetch', 'crawler', FALSE, 'text', FALSE, FALSE)
) AS v(config_key, config_value, default_value, description, group_name, is_public, input_type, is_encrypted, is_sensitive)
WHERE NOT EXISTS (
    SELECT 1 FROM sys_config sc WHERE sc.config_key = v.config_key AND sc.is_deleted = FALSE
);
