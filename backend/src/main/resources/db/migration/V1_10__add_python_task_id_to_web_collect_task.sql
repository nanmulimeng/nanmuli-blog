ALTER TABLE web_collect_task ADD COLUMN IF NOT EXISTS python_task_id INTEGER;
COMMENT ON COLUMN web_collect_task.python_task_id IS 'Python crawler-service 任务ID（新任务走Python编排）';
