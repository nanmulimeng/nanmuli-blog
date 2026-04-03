-- ============================================
-- 用户模块
-- ============================================
CREATE TABLE IF NOT EXISTS sys_user (
    id BIGSERIAL PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password VARCHAR(100) NOT NULL,
    nickname VARCHAR(50),
    avatar VARCHAR(255),
    email VARCHAR(100),
    phone VARCHAR(20),
    role VARCHAR(20) NOT NULL DEFAULT 'ADMIN',
    status INT NOT NULL DEFAULT 1,
    login_ip VARCHAR(50),
    login_time TIMESTAMP,
    create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_sys_user_username ON sys_user(username);
CREATE INDEX IF NOT EXISTS idx_sys_user_deleted ON sys_user(deleted);

CREATE TABLE IF NOT EXISTS sys_login_log (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT,
    username VARCHAR(50),
    ip VARCHAR(50),
    location VARCHAR(100),
    user_agent VARCHAR(500),
    status INT NOT NULL DEFAULT 1,
    message VARCHAR(200),
    create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_login_log_user_id ON sys_login_log(user_id);
CREATE INDEX IF NOT EXISTS idx_login_log_create_time ON sys_login_log(create_time);

-- ============================================
-- 文章模块
-- ============================================
CREATE TABLE IF NOT EXISTS article (
    id BIGSERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    slug VARCHAR(200) UNIQUE,
    content TEXT NOT NULL,
    content_html TEXT,
    summary VARCHAR(500),
    cover VARCHAR(255),
    category_id BIGINT,
    user_id BIGINT NOT NULL,
    view_count INT NOT NULL DEFAULT 0,
    like_count INT NOT NULL DEFAULT 0,
    word_count INT,
    reading_time INT,
    status INT NOT NULL DEFAULT 1,
    is_top BOOLEAN NOT NULL DEFAULT FALSE,
    is_original BOOLEAN NOT NULL DEFAULT TRUE,
    original_url VARCHAR(500),
    publish_time TIMESTAMP,
    create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_article_category_id ON article(category_id);
CREATE INDEX IF NOT EXISTS idx_article_status ON article(status);
CREATE INDEX IF NOT EXISTS idx_article_is_top ON article(is_top);
CREATE INDEX IF NOT EXISTS idx_article_publish_time ON article(publish_time DESC);
CREATE INDEX IF NOT EXISTS idx_article_deleted ON article(deleted);
CREATE INDEX IF NOT EXISTS idx_article_create_time ON article(create_time DESC);

CREATE TABLE IF NOT EXISTS article_draft (
    id BIGSERIAL PRIMARY KEY,
    article_id BIGINT,
    title VARCHAR(200),
    content TEXT,
    category_id BIGINT,
    tags TEXT,
    auto_save BOOLEAN DEFAULT FALSE,
    create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_draft_article_id ON article_draft(article_id);
CREATE INDEX IF NOT EXISTS idx_draft_update_time ON article_draft(update_time DESC);

CREATE TABLE IF NOT EXISTS daily_log (
    id BIGSERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    content_html TEXT,
    mood VARCHAR(20),
    weather VARCHAR(20),
    tags TEXT,
    word_count INT,
    log_date DATE NOT NULL,
    create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_daily_log_log_date ON daily_log(log_date DESC);
CREATE INDEX IF NOT EXISTS idx_daily_log_deleted ON daily_log(deleted);

-- ============================================
-- 分类标签模块
-- ============================================
CREATE TABLE IF NOT EXISTS category (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    slug VARCHAR(50) UNIQUE,
    description VARCHAR(200),
    icon VARCHAR(50),
    color VARCHAR(20),
    sort INT NOT NULL DEFAULT 0,
    parent_id BIGINT,
    article_count INT NOT NULL DEFAULT 0,
    status INT NOT NULL DEFAULT 1,
    create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_category_parent_id ON category(parent_id);
CREATE INDEX IF NOT EXISTS idx_category_sort ON category(sort);
CREATE INDEX IF NOT EXISTS idx_category_status ON category(status);
CREATE INDEX IF NOT EXISTS idx_category_deleted ON category(deleted);

CREATE TABLE IF NOT EXISTS tag (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    slug VARCHAR(50) UNIQUE,
    color VARCHAR(20),
    icon VARCHAR(50),
    description VARCHAR(200),
    article_count INT NOT NULL DEFAULT 0,
    status INT NOT NULL DEFAULT 1,
    create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_tag_name ON tag(name);
CREATE INDEX IF NOT EXISTS idx_tag_status ON tag(status);
CREATE INDEX IF NOT EXISTS idx_tag_deleted ON tag(deleted);

CREATE TABLE IF NOT EXISTS article_tag (
    article_id BIGINT NOT NULL,
    tag_id BIGINT NOT NULL,
    create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (article_id, tag_id)
);

CREATE INDEX IF NOT EXISTS idx_at_tag_id ON article_tag(tag_id);

-- ============================================
-- 个人展示模块
-- ============================================
CREATE TABLE IF NOT EXISTS project_showcase (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    slug VARCHAR(100) UNIQUE,
    description TEXT,
    cover VARCHAR(255),
    screenshots TEXT,
    tech_stack TEXT,
    github_url VARCHAR(500),
    demo_url VARCHAR(500),
    doc_url VARCHAR(500),
    sort INT NOT NULL DEFAULT 0,
    status INT NOT NULL DEFAULT 1,
    start_date DATE,
    end_date DATE,
    create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_project_sort ON project_showcase(sort);
CREATE INDEX IF NOT EXISTS idx_project_status ON project_showcase(status);
CREATE INDEX IF NOT EXISTS idx_project_deleted ON project_showcase(deleted);

CREATE TABLE IF NOT EXISTS skill (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    category VARCHAR(50),
    proficiency INT,
    icon VARCHAR(255),
    color VARCHAR(20),
    description VARCHAR(200),
    sort INT NOT NULL DEFAULT 0,
    status INT NOT NULL DEFAULT 1,
    create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_skill_category ON skill(category);
CREATE INDEX IF NOT EXISTS idx_skill_sort ON skill(sort);
CREATE INDEX IF NOT EXISTS idx_skill_status ON skill(status);
CREATE INDEX IF NOT EXISTS idx_skill_deleted ON skill(deleted);

-- ============================================
-- 文件管理模块
-- ============================================
CREATE TABLE IF NOT EXISTS sys_file (
    id BIGSERIAL PRIMARY KEY,
    original_name VARCHAR(255) NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    file_url VARCHAR(500) NOT NULL,
    file_type VARCHAR(50),
    file_size BIGINT,
    mime_type VARCHAR(100),
    md5 VARCHAR(32),
    width INT,
    height INT,
    user_id BIGINT,
    storage_type VARCHAR(20) DEFAULT 'local',
    usage_type VARCHAR(50),
    ref_id BIGINT,
    create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_file_user_id ON sys_file(user_id);
CREATE INDEX IF NOT EXISTS idx_file_md5 ON sys_file(md5);
CREATE INDEX IF NOT EXISTS idx_file_usage_type ON sys_file(usage_type);
CREATE INDEX IF NOT EXISTS idx_file_ref_id ON sys_file(ref_id);
CREATE INDEX IF NOT EXISTS idx_file_deleted ON sys_file(deleted);

-- ============================================
-- 系统配置模块
-- ============================================
CREATE TABLE IF NOT EXISTS sys_config (
    id BIGSERIAL PRIMARY KEY,
    config_key VARCHAR(100) NOT NULL UNIQUE,
    config_value TEXT,
    default_value TEXT,
    description VARCHAR(200),
    group_name VARCHAR(50),
    is_public BOOLEAN DEFAULT FALSE,
    create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_config_key ON sys_config(config_key);
CREATE INDEX IF NOT EXISTS idx_config_group ON sys_config(group_name);

CREATE TABLE IF NOT EXISTS friend_link (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    url VARCHAR(200) NOT NULL,
    logo VARCHAR(255),
    description VARCHAR(200),
    email VARCHAR(100),
    sort INT NOT NULL DEFAULT 0,
    status INT NOT NULL DEFAULT 1,
    create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_fl_status ON friend_link(status);
CREATE INDEX IF NOT EXISTS idx_fl_sort ON friend_link(sort);

CREATE TABLE IF NOT EXISTS sys_operation_log (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT,
    username VARCHAR(50),
    module VARCHAR(50),
    type VARCHAR(50),
    description VARCHAR(200),
    request_method VARCHAR(10),
    request_url VARCHAR(500),
    request_params TEXT,
    response_data TEXT,
    ip VARCHAR(50),
    location VARCHAR(100),
    user_agent VARCHAR(500),
    execute_time BIGINT,
    status INT,
    error_msg TEXT,
    create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ol_user_id ON sys_operation_log(user_id);
CREATE INDEX IF NOT EXISTS idx_ol_module ON sys_operation_log(module);
CREATE INDEX IF NOT EXISTS idx_ol_create_time ON sys_operation_log(create_time);

-- ============================================
-- AI 模块
-- ============================================
CREATE TABLE IF NOT EXISTS ai_generation (
    id BIGSERIAL PRIMARY KEY,
    article_id BIGINT NOT NULL,
    type VARCHAR(20) NOT NULL,
    prompt TEXT,
    content TEXT,
    tokens_used INT,
    model VARCHAR(50),
    status INT NOT NULL DEFAULT 1,
    error_msg TEXT,
    create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ag_article_id ON ai_generation(article_id);
CREATE INDEX IF NOT EXISTS idx_ag_type ON ai_generation(type);
CREATE INDEX IF NOT EXISTS idx_ag_create_time ON ai_generation(create_time);

-- ============================================
-- 初始化数据
-- ============================================
INSERT INTO sys_user (id, username, password, nickname, email, role, status)
VALUES (1, 'admin', '$2a$10$N.zmdr9k7uOCQb376NoUnuTJ8iAt6Z5EHsM8lE9lBOsl7iAt6Z5EO', '管理员', 'admin@example.com', 'ADMIN', 1)
ON CONFLICT (username) DO NOTHING;

INSERT INTO category (id, name, slug, description, sort)
VALUES
    (1, '后端开发', 'backend', 'Java后端开发相关文章', 1),
    (2, '前端技术', 'frontend', '前端开发技术分享', 2),
    (3, '数据库', 'database', '数据库技术与优化', 3),
    (4, 'DevOps', 'devops', '运维与部署', 4),
    (5, '技术日志', 'daily-log', '每日技术笔记', 5),
    (6, '项目展示', 'projects', '个人项目介绍', 6)
ON CONFLICT DO NOTHING;

INSERT INTO tag (id, name, slug, color, description)
VALUES
    (1, 'Java', 'java', '#007396', 'Java编程语言'),
    (2, 'Spring Boot', 'spring-boot', '#6DB33F', 'Spring Boot框架'),
    (3, 'Vue', 'vue', '#4FC08D', 'Vue.js前端框架'),
    (4, 'PostgreSQL', 'postgresql', '#336791', 'PostgreSQL数据库'),
    (5, 'Redis', 'redis', '#DC382D', 'Redis缓存'),
    (6, 'Docker', 'docker', '#2496ED', 'Docker容器'),
    (7, 'Linux', 'linux', '#FCC624', 'Linux系统'),
    (8, 'AI', 'ai', '#FF6B6B', '人工智能')
ON CONFLICT DO NOTHING;

INSERT INTO sys_config (config_key, config_value, default_value, description, group_name, is_public)
VALUES
    ('site.name', '我的技术博客', '我的技术博客', '网站名称', 'site', TRUE),
    ('site.description', '记录技术成长，分享学习心得', '记录技术成长，分享学习心得', '网站描述', 'site', TRUE),
    ('site.logo', '', '', '网站Logo', 'site', TRUE),
    ('site.favicon', '', '', '网站Favicon', 'site', TRUE),
    ('site.icp', '', '', 'ICP备案号', 'site', TRUE),
    ('site.footer', '2025 我的技术博客', '2025 我的技术博客', '页脚信息', 'site', TRUE),
    ('site.about', '', '', '关于页面内容（Markdown）', 'site', TRUE),
    ('site.avatar', '', '', '个人头像', 'site', TRUE),
    ('site.email', '', '', '联系邮箱', 'site', TRUE),
    ('site.github', '', '', 'GitHub链接', 'site', TRUE),
    ('ai.enabled', 'false', 'false', '是否启用AI功能', 'ai', FALSE),
    ('ai.model', 'qwen-turbo', 'qwen-turbo', 'AI模型', 'ai', FALSE),
    ('ai.autoTags', 'true', 'true', '是否自动生成标签', 'ai', FALSE),
    ('ai.autoSummary', 'true', 'true', '是否自动生成摘要', 'ai', FALSE)
ON CONFLICT (config_key) DO NOTHING;

INSERT INTO skill (id, name, category, proficiency, color, description, sort)
VALUES
    (1, 'Java', 'language', 4, '#007396', '熟练掌握Java编程', 1),
    (2, 'Spring Boot', 'framework', 4, '#6DB33F', 'Spring Boot开发', 2),
    (3, 'Vue.js', 'framework', 3, '#4FC08D', 'Vue前端开发', 3),
    (4, 'PostgreSQL', 'tool', 3, '#336791', 'PostgreSQL数据库', 4),
    (5, 'Redis', 'tool', 3, '#DC382D', 'Redis缓存', 5),
    (6, 'Docker', 'tool', 3, '#2496ED', 'Docker容器化', 6),
    (7, 'Linux', 'tool', 3, '#FCC624', 'Linux系统管理', 7)
ON CONFLICT DO NOTHING;
