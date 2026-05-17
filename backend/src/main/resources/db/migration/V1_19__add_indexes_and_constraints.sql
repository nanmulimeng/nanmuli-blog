-- V1.19: 补充关键索引、约束和乐观锁字段

-- 1. python_task_id 索引（Python 回调高频查询路径）
CREATE INDEX IF NOT EXISTS idx_task_python_id
    ON web_collect_task(python_task_id)
    WHERE python_task_id IS NOT NULL AND is_deleted = FALSE;

-- 2. digest_fingerprint 唯一约束（防止重复指纹）
CREATE UNIQUE INDEX IF NOT EXISTS idx_digest_fp_unique
    ON digest_fingerprint(url_hash, digest_date);

-- 3. WebCollectSource 乐观锁字段
ALTER TABLE web_collect_source ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 0;
