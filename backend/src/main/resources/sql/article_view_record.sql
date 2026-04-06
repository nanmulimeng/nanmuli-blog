-- 文章阅读记录表 - 用于统计独立访客(UV)
CREATE TABLE IF NOT EXISTS article_view_record (
    id BIGSERIAL PRIMARY KEY,
    article_id BIGINT NOT NULL REFERENCES article(id) ON DELETE CASCADE,
    visitor_id VARCHAR(64) NOT NULL,
    ip_address VARCHAR(45),
    user_agent VARCHAR(500),
    first_view_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_view_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    view_count INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE
);

-- 创建唯一索引：同一文章同一访客只记录一次
CREATE UNIQUE INDEX IF NOT EXISTS uk_article_visitor
    ON article_view_record(article_id, visitor_id)
    WHERE is_deleted = FALSE;

-- 创建索引优化查询性能
CREATE INDEX IF NOT EXISTS idx_article_view_record_article_id
    ON article_view_record(article_id)
    WHERE is_deleted = FALSE;

CREATE INDEX IF NOT EXISTS idx_article_view_record_visitor_id
    ON article_view_record(visitor_id)
    WHERE is_deleted = FALSE;

-- 创建更新时间触发器
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS update_article_view_record_updated_at ON article_view_record;
CREATE TRIGGER update_article_view_record_updated_at
    BEFORE UPDATE ON article_view_record
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
