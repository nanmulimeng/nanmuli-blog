-- Web Collector 模块数据库表
-- 支持：单页爬取、深度爬取、关键词搜索、每日技术日报
-- 版本: v1.1.0

-- ============================================
-- 1. 订阅源表 (web_collect_source)
-- ============================================
CREATE TABLE IF NOT EXISTS web_collect_source (
    id              BIGINT PRIMARY KEY,
    name            VARCHAR(200) NOT NULL,          -- 源名称（如 "Hacker News 热榜"）
    type            VARCHAR(20) NOT NULL,           -- url / keyword / rss
    value           VARCHAR(2048) NOT NULL,         -- URL / 关键词 / RSS 地址

    -- 内容分类（日报用）
    content_category VARCHAR(50),                   -- hot_trend / open_source / tech_article / dev_tool / creative

    -- 爬取配置
    crawl_mode      VARCHAR(20) DEFAULT 'single',   -- single / deep
    max_depth       SMALLINT DEFAULT 1,             -- 深度爬取层数
    max_pages       SMALLINT DEFAULT 10,            -- 最大页面数
    css_selector    VARCHAR(500),                   -- 列表页内容选择器（可选，精确提取）
    ai_template     VARCHAR(50) DEFAULT 'tech_summary',

    -- 调度配置
    schedule_cron   VARCHAR(50),                    -- cron 表达式（null=仅手动触发）
    freshness_hours INTEGER DEFAULT 24,             -- 时效窗口（小时），超过此时间的内容视为过期

    -- 状态
    is_active       BOOLEAN DEFAULT TRUE,           -- 是否启用
    last_run_at     TIMESTAMP,                      -- 上次执行时间
    last_run_status VARCHAR(20),                    -- 上次执行结果 success / failed
    run_count       INTEGER DEFAULT 0,              -- 累计执行次数

    -- 审计
    user_id         BIGINT NOT NULL,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    is_deleted      BOOLEAN NOT NULL DEFAULT FALSE,

    CONSTRAINT fk_source_user FOREIGN KEY (user_id) REFERENCES sys_user(id)
);

-- 订阅源索引
CREATE INDEX IF NOT EXISTS idx_source_active ON web_collect_source(is_active, schedule_cron) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_source_category ON web_collect_source(content_category) WHERE is_deleted = FALSE;

-- ============================================
-- 2. 采集任务表 (web_collect_task)
-- ============================================
CREATE TABLE IF NOT EXISTS web_collect_task (
    id              BIGINT PRIMARY KEY,

    -- 任务类型与输入
    task_type       VARCHAR(20) NOT NULL DEFAULT 'single',  -- single / deep / keyword / digest
    source_url      VARCHAR(2048),                  -- URL（single/deep 模式）
    keyword         VARCHAR(500),                   -- 关键词（keyword 模式）
    search_engine   VARCHAR(50),                    -- bing / duckduckgo（keyword 模式）
    trigger_type    VARCHAR(20) DEFAULT 'manual',   -- manual / scheduled

    -- 关联
    source_id       BIGINT,                         -- FK → web_collect_source（可选，日报任务关联）
    article_id      BIGINT,                         -- 转为文章后的关联 ID
    daily_log_id    BIGINT,                         -- 转为日志后的关联 ID
    user_id         BIGINT NOT NULL,

    -- AI 整理结果（汇总级别）
    ai_title        VARCHAR(500),                   -- AI 生成的标题
    ai_summary      TEXT,                           -- AI 生成的汇总摘要
    ai_key_points   JSONB,                          -- 关键要点 ["point1", "point2"]
    ai_tags         JSONB,                          -- 标签建议 ["tag1", "tag2"]
    ai_category     VARCHAR(100),                   -- 分类建议
    ai_full_content TEXT,                           -- AI 整理后的完整 Markdown

    -- 任务状态
    status          SMALLINT NOT NULL DEFAULT 0,    -- 0=待处理 1=爬取中 2=整理中 3=已完成 4=失败
    error_message   TEXT,

    -- 配置
    crawl_mode      VARCHAR(20) DEFAULT 'single',
    ai_template     VARCHAR(50) DEFAULT 'tech_summary',
    max_depth       SMALLINT DEFAULT 1,
    max_pages       SMALLINT DEFAULT 10,

    -- 进度追踪
    total_pages     INTEGER DEFAULT 1,              -- 总页面数
    completed_pages INTEGER DEFAULT 0,              -- 已完成爬取的页面数

    -- 统计
    crawl_duration  INTEGER,                        -- 爬取总耗时（毫秒）
    ai_duration     INTEGER,                        -- AI 整理耗时（毫秒）
    tokens_used     INTEGER,                        -- AI 消耗 token 数
    total_word_count INTEGER,                       -- 所有页面总字数

    -- 审计
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    is_deleted      BOOLEAN NOT NULL DEFAULT FALSE,

    CONSTRAINT fk_task_user FOREIGN KEY (user_id) REFERENCES sys_user(id),
    CONSTRAINT fk_task_source FOREIGN KEY (source_id) REFERENCES web_collect_source(id)
);

-- 任务表索引
CREATE INDEX IF NOT EXISTS idx_task_status ON web_collect_task(status) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_task_user ON web_collect_task(user_id, created_at DESC) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_task_type ON web_collect_task(task_type, created_at DESC) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_task_source ON web_collect_task(source_id) WHERE source_id IS NOT NULL AND is_deleted = FALSE;

-- ============================================
-- 3. 爬取页面表 (web_collect_page)
-- ============================================
CREATE TABLE IF NOT EXISTS web_collect_page (
    id              BIGINT PRIMARY KEY,
    task_id         BIGINT NOT NULL,                -- FK → web_collect_task

    -- 页面信息
    url             VARCHAR(2048) NOT NULL,
    page_title      VARCHAR(500),                   -- 网页原始标题
    raw_markdown    TEXT,                            -- Crawl4AI 爬取的原始 Markdown
    page_metadata   TEXT,                           -- 元数据 JSON 字符串

    -- 爬取状态（每页独立）
    crawl_status    SMALLINT DEFAULT 0,             -- 0=待爬取 1=爬取中 2=已完成 3=失败
    error_message   TEXT,
    crawl_duration  INTEGER,                        -- 该页爬取耗时（毫秒）
    word_count      INTEGER,                        -- 该页字数

    -- 去重字段
    url_hash        VARCHAR(64) NOT NULL,           -- URL 的 SHA-256 哈希（用于快速去重）
    content_hash    VARCHAR(64),                    -- 正文前 500 字标准化后的 SHA-256（爬取后填充）

    -- 排序
    sort_order      INTEGER DEFAULT 0,              -- 页面排序（深度爬取时按发现顺序）
    depth           SMALLINT DEFAULT 0,             -- 爬取深度层级

    -- 时效性
    published_at    TIMESTAMP,                      -- 页面发布时间（从元数据提取，可为空）

    -- 审计
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_page_task FOREIGN KEY (task_id) REFERENCES web_collect_task(id) ON DELETE CASCADE
);

-- 页面表索引
CREATE INDEX IF NOT EXISTS idx_page_task ON web_collect_page(task_id, sort_order);
CREATE INDEX IF NOT EXISTS idx_page_url_hash ON web_collect_page(url_hash);
CREATE INDEX IF NOT EXISTS idx_page_content_hash ON web_collect_page(content_hash) WHERE content_hash IS NOT NULL;

-- ============================================
-- 4. 触发器：自动更新 updated_at
-- ============================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- 订阅源表触发器
DROP TRIGGER IF EXISTS update_web_collect_source_updated_at ON web_collect_source;
CREATE TRIGGER update_web_collect_source_updated_at
    BEFORE UPDATE ON web_collect_source
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- 任务表触发器
DROP TRIGGER IF EXISTS update_web_collect_task_updated_at ON web_collect_task;
CREATE TRIGGER update_web_collect_task_updated_at
    BEFORE UPDATE ON web_collect_task
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- 5. 注释说明
-- ============================================
COMMENT ON TABLE web_collect_source IS 'Web Collector 订阅源表 - 管理 URL/关键词/RSS 订阅';
COMMENT ON TABLE web_collect_task IS 'Web Collector 采集任务表 - 记录单次采集任务的完整生命周期';
COMMENT ON TABLE web_collect_page IS 'Web Collector 爬取页面表 - 存储每个 URL 的爬取结果';

COMMENT ON COLUMN web_collect_source.content_category IS '内容分类：hot_trend-热点动态, open_source-开源项目, tech_article-技术文章, dev_tool-开发工具, creative-创意发现';
COMMENT ON COLUMN web_collect_task.task_type IS '任务类型：single-单页, deep-深度, keyword-关键词搜索, digest-每日日报';
COMMENT ON COLUMN web_collect_task.status IS '任务状态：0-待处理, 1-爬取中, 2-整理中, 3-已完成, 4-失败';
COMMENT ON COLUMN web_collect_page.crawl_status IS '页面爬取状态：0-待爬取, 1-爬取中, 2-已完成, 3-失败';
