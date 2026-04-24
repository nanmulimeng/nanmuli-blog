-- 为 web_collect_task 添加乐观锁 version 字段
ALTER TABLE web_collect_task ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 1;

COMMENT ON COLUMN web_collect_task.version IS '乐观锁版本号';
