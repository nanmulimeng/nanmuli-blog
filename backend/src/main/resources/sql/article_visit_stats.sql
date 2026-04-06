-- 文章访问统计系统 - 包含PV（访问量）、UV（访客数）、今日访问

-- 1. 文章独立访客记录表（UV统计）
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

CREATE INDEX IF NOT EXISTS idx_article_view_record_article_id
    ON article_view_record(article_id)
    WHERE is_deleted = FALSE;

-- 2. 文章访问日志表（PV统计）
CREATE TABLE IF NOT EXISTS article_visit_log (
    id BIGSERIAL PRIMARY KEY,
    article_id BIGINT NOT NULL REFERENCES article(id) ON DELETE CASCADE,
    visitor_id VARCHAR(64) NOT NULL,
    ip_address VARCHAR(45),
    user_agent VARCHAR(500),
    visit_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引优化查询
CREATE INDEX IF NOT EXISTS idx_article_visit_log_article_id
    ON article_visit_log(article_id);

CREATE INDEX IF NOT EXISTS idx_article_visit_log_visit_time
    ON article_visit_log(visit_time);

-- 创建日期索引（用于今日访问统计）
CREATE INDEX IF NOT EXISTS idx_article_visit_log_date
    ON article_visit_log(DATE(visit_time));

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
