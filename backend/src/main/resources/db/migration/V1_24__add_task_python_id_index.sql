-- V1_24: 补 schema.sql 漂移——idx_task_python_id 索引
-- 背景：V1_19 引入 web_collect_task.python_task_id（用于 Python 任务回调查询），
--   但 deploy/db/init-scripts/schema.sql 漏建该索引（B15-05 发现），Python 任务回调查询全表扫。
-- 仅在 Flyway 启用后执行（baseline-version=1.0.23 之后的第一个增量）。
-- 幂等：IF NOT EXISTS 防止已手工补过的环境报错。
CREATE INDEX IF NOT EXISTS idx_task_python_id ON web_collect_task (python_task_id);
