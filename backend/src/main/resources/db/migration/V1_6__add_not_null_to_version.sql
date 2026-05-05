-- 为 article 和 web_collect_task 的 version 字段补加 NOT NULL 约束
-- V1_3/V1_4 仅设置了 DEFAULT 1,未加 NOT NULL,旧数据迁移或并发写入存在 NULL 风险
-- @Version 乐观锁字段必须非空

-- 1. 防御性回填(理论上 DEFAULT 1 已覆盖,此处幂等保护)
UPDATE article SET version = 1 WHERE version IS NULL;
UPDATE web_collect_task SET version = 1 WHERE version IS NULL;

-- 2. 加 NOT NULL 约束
ALTER TABLE article ALTER COLUMN version SET NOT NULL;
ALTER TABLE web_collect_task ALTER COLUMN version SET NOT NULL;

-- 3. 确保 DEFAULT 仍然存在(SET NOT NULL 不影响 DEFAULT,此处声明性确认)
ALTER TABLE article ALTER COLUMN version SET DEFAULT 1;
ALTER TABLE web_collect_task ALTER COLUMN version SET DEFAULT 1;
