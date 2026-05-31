-- Digest dedupe fingerprints for cross-day URL and SimHash matching.
CREATE TABLE IF NOT EXISTS digest_fingerprint (
    id          BIGINT PRIMARY KEY,
    task_id     BIGINT,
    url_hash    VARCHAR(64) NOT NULL,
    url         VARCHAR(2048),
    title       VARCHAR(500),
    simhash     BIGINT,
    digest_date DATE,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_deleted  BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_digest_fp_date ON digest_fingerprint(digest_date);
CREATE INDEX IF NOT EXISTS idx_digest_fp_url_hash ON digest_fingerprint(url_hash);

COMMENT ON TABLE digest_fingerprint IS 'Digest dedupe fingerprints for cross-day URL and SimHash matching';
