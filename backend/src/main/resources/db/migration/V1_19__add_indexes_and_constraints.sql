-- Callback lookup index for Python task synchronization.
CREATE INDEX IF NOT EXISTS idx_task_python_id
    ON web_collect_task(python_task_id)
    WHERE python_task_id IS NOT NULL AND is_deleted = FALSE;

-- Prevent duplicate digest fingerprints for the same digest date.
CREATE UNIQUE INDEX IF NOT EXISTS idx_digest_fp_unique
    ON digest_fingerprint(url_hash, digest_date);

-- Optimistic lock field for mutable source aggregate.
ALTER TABLE web_collect_source ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 0;
