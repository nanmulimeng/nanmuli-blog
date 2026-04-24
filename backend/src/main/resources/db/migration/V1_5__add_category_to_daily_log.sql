-- 为 daily_log 表添加 category_id 和 is_public 列
ALTER TABLE daily_log ADD COLUMN IF NOT EXISTS category_id BIGINT;
ALTER TABLE daily_log ADD COLUMN IF NOT EXISTS is_public BOOLEAN NOT NULL DEFAULT FALSE;

COMMENT ON COLUMN daily_log.category_id IS '分类ID';
COMMENT ON COLUMN daily_log.is_public IS '是否公开';

CREATE INDEX IF NOT EXISTS idx_daily_log_category_id ON daily_log(category_id);
