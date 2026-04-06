-- 为article表添加乐观锁版本号字段
ALTER TABLE article ADD COLUMN version INT DEFAULT 1;

-- 为已存在的数据设置版本号为1
UPDATE article SET version = 1 WHERE version IS NULL;
