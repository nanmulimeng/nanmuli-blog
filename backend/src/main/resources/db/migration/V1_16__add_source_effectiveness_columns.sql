-- V1.16: add source effectiveness tracking fields.

ALTER TABLE web_collect_source ADD COLUMN IF NOT EXISTS success_count INTEGER DEFAULT 0;
ALTER TABLE web_collect_source ADD COLUMN IF NOT EXISTS fail_count INTEGER DEFAULT 0;
ALTER TABLE web_collect_source ADD COLUMN IF NOT EXISTS avg_quality_score DOUBLE PRECISION DEFAULT 0;
ALTER TABLE web_collect_source ADD COLUMN IF NOT EXISTS last_result_count INTEGER DEFAULT 0;
ALTER TABLE web_collect_source ADD COLUMN IF NOT EXISTS last_error TEXT;

COMMENT ON COLUMN web_collect_source.success_count IS 'Successful run count';
COMMENT ON COLUMN web_collect_source.fail_count IS 'Failed run count';
COMMENT ON COLUMN web_collect_source.avg_quality_score IS 'Moving average quality score';
COMMENT ON COLUMN web_collect_source.last_result_count IS 'Valid page count from latest successful run';
COMMENT ON COLUMN web_collect_source.last_error IS 'Latest failure error';

INSERT INTO sys_config (
    config_key, config_value, default_value, description,
    group_name, is_public, input_type, is_encrypted, is_sensitive
)
SELECT *
FROM (VALUES
    ('crawler.optimization.breadth_max_rounds', '3', '3', 'Breadth expansion maximum rounds', 'crawler', FALSE, 'text', FALSE, FALSE)
) AS v(config_key, config_value, default_value, description, group_name, is_public, input_type, is_encrypted, is_sensitive)
WHERE NOT EXISTS (
    SELECT 1 FROM sys_config sc WHERE sc.config_key = v.config_key AND sc.is_deleted = FALSE
);
