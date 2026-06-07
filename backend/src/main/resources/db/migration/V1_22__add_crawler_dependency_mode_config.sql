-- V1.22: add crawler dependency compatibility mode.

INSERT INTO sys_config (
    config_key, config_value, default_value, description,
    group_name, is_public, input_type, is_encrypted, is_sensitive
)
SELECT *
FROM (VALUES
    ('crawler.dependency_mode', 'degraded', 'degraded', 'Crawler dependency mode: degraded keeps service up; strict fails startup when dependency is unavailable', 'crawler', FALSE, 'text', FALSE, FALSE)
) AS v(config_key, config_value, default_value, description, group_name, is_public, input_type, is_encrypted, is_sensitive)
WHERE NOT EXISTS (
    SELECT 1 FROM sys_config sc WHERE sc.config_key = v.config_key AND sc.is_deleted = FALSE
);
