-- V1.13: add digest optimization and pipeline configs.

UPDATE sys_config
SET config_value = 'both', default_value = 'both'
WHERE config_key = 'crawler.optimization.mode' AND is_deleted = FALSE;

INSERT INTO sys_config (
    config_key, config_value, default_value, description,
    group_name, is_public, input_type, is_encrypted, is_sensitive
)
SELECT *
FROM (VALUES
    ('crawler.digest.filter_min_content', '50', '50', 'Digest minimum content length', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.digest.optimization_enabled', 'false', 'false', 'Digest optimization enabled', 'crawler', FALSE, 'switch', FALSE, FALSE),
    ('crawler.digest.optimization_min_sections', '2', '2', 'Minimum sections for digest optimization', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.digest.optimization_target_score', '0.65', '0.65', 'Digest optimization target score', 'crawler', FALSE, 'text', FALSE, FALSE)
) AS v(config_key, config_value, default_value, description, group_name, is_public, input_type, is_encrypted, is_sensitive)
WHERE NOT EXISTS (
    SELECT 1 FROM sys_config sc WHERE sc.config_key = v.config_key AND sc.is_deleted = FALSE
);

INSERT INTO sys_config (
    config_key, config_value, default_value, description,
    group_name, is_public, input_type, is_encrypted, is_sensitive
)
SELECT *
FROM (VALUES
    ('crawler.pipeline.ai_organization_enabled', 'true', 'true', 'AI organization enabled', 'crawler', FALSE, 'switch', FALSE, FALSE),
    ('crawler.pipeline.content_dedup_enabled', 'true', 'true', 'Content dedup enabled', 'crawler', FALSE, 'switch', FALSE, FALSE),
    ('crawler.pipeline.content_dedup_simhash_threshold', '5', '5', 'Content dedup SimHash threshold', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.pipeline.content_dedup_deep_threshold', '3', '3', 'Deep crawl dedup SimHash threshold', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.pipeline.filter_deep_min_content', '20', '20', 'Deep crawl minimum content length', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.pipeline.page_classifier_enabled', 'true', 'true', 'Page classifier enabled', 'crawler', FALSE, 'switch', FALSE, FALSE),
    ('crawler.pipeline.filter_skip_header_chars', '200', '200', 'Fingerprint skipped header characters', 'crawler', FALSE, 'text', FALSE, FALSE)
) AS v(config_key, config_value, default_value, description, group_name, is_public, input_type, is_encrypted, is_sensitive)
WHERE NOT EXISTS (
    SELECT 1 FROM sys_config sc WHERE sc.config_key = v.config_key AND sc.is_deleted = FALSE
);
