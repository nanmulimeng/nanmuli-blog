-- V1.15: add missing digest and optimization configs.

INSERT INTO sys_config (
    config_key, config_value, default_value, description,
    group_name, is_public, input_type, is_encrypted, is_sensitive
)
SELECT *
FROM (VALUES
    ('crawler.ai.digest_per_max_chars', '8000', '8000', 'Digest per-page input character limit', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.ai.digest_total_budget', '100000', '100000', 'Digest total input character budget', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.ai.digest_max_tokens', '10000', '10000', 'Digest AI maximum output tokens', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.digest.parallel_sections', '2', '2', 'Digest section parallelism', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.digest.global_timeout', '600', '600', 'Digest global timeout seconds', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.digest.optimization_min_results_per_section', '3', '3', 'Minimum results per section for optimization', 'crawler', FALSE, 'text', FALSE, FALSE)
) AS v(config_key, config_value, default_value, description, group_name, is_public, input_type, is_encrypted, is_sensitive)
WHERE NOT EXISTS (
    SELECT 1 FROM sys_config sc WHERE sc.config_key = v.config_key AND sc.is_deleted = FALSE
);
