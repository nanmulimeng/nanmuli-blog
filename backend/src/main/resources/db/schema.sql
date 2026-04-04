-- ============================================
-- 个人技术博客系统 - 数据库Schema
-- PostgreSQL 15+ (含pgvector扩展)
-- ============================================

-- 启用pgvector扩展（用于AI向量搜索）
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================
-- 用户模块
-- ============================================

-- 用户表（仅管理员）
CREATE TABLE IF NOT EXISTS sys_user (
    id BIGSERIAL PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password VARCHAR(100) NOT NULL,
    nickname VARCHAR(50),
    avatar VARCHAR(255),
    email VARCHAR(100),
    phone VARCHAR(20),
    role VARCHAR(20) NOT NULL DEFAULT 'ADMIN' COMMENT '角色：ADMIN-管理员',
    status INT NOT NULL DEFAULT 1 COMMENT '状态：1-正常 0-禁用',
    login_ip VARCHAR(50) COMMENT '最后登录IP',
    login_time TIMESTAMP COMMENT '最后登录时间',
    create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted BOOLEAN NOT NULL DEFAULT FALSE COMMENT '逻辑删除标记'
);

COMMENT ON TABLE sys_user IS '用户表（仅管理员）';
COMMENT ON COLUMN sys_user.username IS '用户名';
COMMENT ON COLUMN sys_user.password IS '密码（BCrypt加密）';
COMMENT ON COLUMN sys_user.nickname IS '昵称';
COMMENT ON COLUMN sys_user.avatar IS '头像URL';
COMMENT ON COLUMN sys_user.email IS '邮箱';
COMMENT ON COLUMN sys_user.phone IS '手机号';
COMMENT ON COLUMN sys_user.role IS '角色：ADMIN-管理员';
COMMENT ON COLUMN sys_user.status IS '状态：1-正常 0-禁用';
COMMENT ON COLUMN sys_user.login_ip IS '最后登录IP';
COMMENT ON COLUMN sys_user.login_time IS '最后登录时间';
COMMENT ON COLUMN sys_user.deleted IS '逻辑删除标记';

CREATE INDEX IF NOT EXISTS idx_sys_user_username ON sys_user(username);
CREATE INDEX IF NOT EXISTS idx_sys_user_status ON sys_user(status);
CREATE INDEX IF NOT EXISTS idx_sys_user_deleted ON sys_user(deleted);

-- 用户登录日志表
CREATE TABLE IF NOT EXISTS sys_login_log (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT COMMENT '用户ID',
    username VARCHAR(50) COMMENT '用户名',
    ip VARCHAR(50) COMMENT '登录IP',
    location VARCHAR(100) COMMENT '登录地点',
    user_agent VARCHAR(500) COMMENT '浏览器UA',
    status INT NOT NULL DEFAULT 1 COMMENT '状态：1-成功 0-失败',
    message VARCHAR(200) COMMENT '消息',
    create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE sys_login_log IS '用户登录日志表';
COMMENT ON COLUMN sys_login_log.user_id IS '用户ID';
COMMENT ON COLUMN sys_login_log.ip IS '登录IP';
COMMENT ON COLUMN sys_login_log.location IS '登录地点';
COMMENT ON COLUMN sys_login_log.user_agent IS '浏览器UA';
COMMENT ON COLUMN sys_login_log.status IS '状态：1-成功 0-失败';

CREATE INDEX IF NOT EXISTS idx_login_log_user_id ON sys_login_log(user_id);
CREATE INDEX IF NOT EXISTS idx_login_log_create_time ON sys_login_log(create_time);

-- ============================================
-- 文章模块
-- ============================================

-- 文章表
CREATE TABLE IF NOT EXISTS article (
    id BIGSERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL COMMENT '标题',
    slug VARCHAR(200) UNIQUE COMMENT 'URL别名（用于SEO）',
    content TEXT NOT NULL COMMENT '内容（Markdown）',
    content_html TEXT COMMENT '内容（HTML渲染后）',
    summary VARCHAR(500) COMMENT '摘要（自动生成或手动填写）',
    cover VARCHAR(255) COMMENT '封面图URL',
    category_id BIGINT COMMENT '分类ID',
    user_id BIGINT NOT NULL COMMENT '作者ID',
    view_count INT NOT NULL DEFAULT 0 COMMENT '浏览量',
    like_count INT NOT NULL DEFAULT 0 COMMENT '点赞数',
    word_count INT COMMENT '字数统计',
    reading_time INT COMMENT '阅读时间（分钟）',
    status INT NOT NULL DEFAULT 1 COMMENT '状态：1-已发布 2-草稿 3-回收站',
    is_top BOOLEAN NOT NULL DEFAULT FALSE COMMENT '是否置顶',
    is_original BOOLEAN NOT NULL DEFAULT TRUE COMMENT '是否原创',
    original_url VARCHAR(500) COMMENT '原文链接（转载时填写）',
    publish_time TIMESTAMP COMMENT '发布时间',
    create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted BOOLEAN NOT NULL DEFAULT FALSE COMMENT '逻辑删除标记'
);

COMMENT ON TABLE article IS '文章表';
COMMENT ON COLUMN article.title IS '标题';
COMMENT ON COLUMN article.slug IS 'URL别名（用于SEO）';
COMMENT ON COLUMN article.content IS '内容（Markdown）';
COMMENT ON COLUMN article.content_html IS '内容（HTML渲染后）';
COMMENT ON COLUMN article.summary IS '摘要（自动生成或手动填写）';
COMMENT ON COLUMN article.cover IS '封面图URL';
COMMENT ON COLUMN article.category_id IS '分类ID';
COMMENT ON COLUMN article.user_id IS '作者ID';
COMMENT ON COLUMN article.view_count IS '浏览量';
COMMENT ON COLUMN article.like_count IS '点赞数';
COMMENT ON COLUMN article.word_count IS '字数统计';
COMMENT ON COLUMN article.reading_time IS '阅读时间（分钟）';
COMMENT ON COLUMN article.status IS '状态：1-已发布 2-草稿 3-回收站';
COMMENT ON COLUMN article.is_top IS '是否置顶';
COMMENT ON COLUMN article.is_original IS '是否原创';
COMMENT ON COLUMN article.original_url IS '原文链接（转载时填写）';
COMMENT ON COLUMN article.publish_time IS '发布时间';
COMMENT ON COLUMN article.deleted IS '逻辑删除标记';

CREATE INDEX IF NOT EXISTS idx_article_category_id ON article(category_id);
CREATE INDEX IF NOT EXISTS idx_article_user_id ON article(user_id);
CREATE INDEX IF NOT EXISTS idx_article_status ON article(status);
CREATE INDEX IF NOT EXISTS idx_article_is_top ON article(is_top);
CREATE INDEX IF NOT EXISTS idx_article_publish_time ON article(publish_time DESC);
CREATE INDEX IF NOT EXISTS idx_article_deleted ON article(deleted);
CREATE INDEX IF NOT EXISTS idx_article_create_time ON article(create_time DESC);

-- 全文搜索索引（中文）
CREATE INDEX IF NOT EXISTS idx_article_content_search ON article USING GIN (to_tsvector('chinese', content));
CREATE INDEX IF NOT EXISTS idx_article_title_search ON article USING GIN (to_tsvector('chinese', title));

-- 复合索引：已发布文章按发布时间排序（列表页常用查询）
CREATE INDEX IF NOT EXISTS idx_article_status_publish ON article(status, publish_time DESC) WHERE status = 1 AND deleted = FALSE;

-- 文章草稿表
CREATE TABLE IF NOT EXISTS article_draft (
    id BIGSERIAL PRIMARY KEY,
    article_id BIGINT COMMENT '关联的文章ID（新建时为null）',
    title VARCHAR(200) COMMENT '标题',
    content TEXT COMMENT '内容',
    category_id BIGINT COMMENT '分类ID',
    tags TEXT COMMENT '标签JSON数组',
    auto_save BOOLEAN DEFAULT FALSE COMMENT '是否自动保存',
    create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE article_draft IS '文章草稿表';
COMMENT ON COLUMN article_draft.article_id IS '关联的文章ID（新建时为null）';
COMMENT ON COLUMN article_draft.title IS '标题';
COMMENT ON COLUMN article_draft.content IS '内容';
COMMENT ON COLUMN article_draft.category_id IS '分类ID';
COMMENT ON COLUMN article_draft.tags IS '标签JSON数组';
COMMENT ON COLUMN article_draft.auto_save IS '是否自动保存';

CREATE INDEX IF NOT EXISTS idx_draft_article_id ON article_draft(article_id);
CREATE INDEX IF NOT EXISTS idx_draft_update_time ON article_draft(update_time DESC);

-- 技术日志表
CREATE TABLE IF NOT EXISTS daily_log (
    id BIGSERIAL PRIMARY KEY,
    content TEXT NOT NULL COMMENT '日志内容（Markdown）',
    content_html TEXT COMMENT 'HTML渲染后内容',
    mood VARCHAR(20) COMMENT '心情：happy-开心 excited-兴奋 normal-平静 tired-疲惫',
    weather VARCHAR(20) COMMENT '天气',
    tags TEXT COMMENT '标签JSON数组',
    word_count INT COMMENT '字数',
    log_date DATE NOT NULL COMMENT '日志日期',
    create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted BOOLEAN NOT NULL DEFAULT FALSE COMMENT '逻辑删除标记'
);

COMMENT ON TABLE daily_log IS '技术日志表（每日技术笔记）';
COMMENT ON COLUMN daily_log.content IS '日志内容（Markdown）';
COMMENT ON COLUMN daily_log.content_html IS 'HTML渲染后内容';
COMMENT ON COLUMN daily_log.mood IS '心情：happy-开心 excited-兴奋 normal-平静 tired-疲惫';
COMMENT ON COLUMN daily_log.weather IS '天气';
COMMENT ON COLUMN daily_log.tags IS '标签JSON数组';
COMMENT ON COLUMN daily_log.word_count IS '字数';
COMMENT ON COLUMN daily_log.log_date IS '日志日期';
COMMENT ON COLUMN daily_log.deleted IS '逻辑删除标记';

CREATE INDEX IF NOT EXISTS idx_daily_log_log_date ON daily_log(log_date DESC);
CREATE INDEX IF NOT EXISTS idx_daily_log_deleted ON daily_log(deleted);

-- ============================================
-- 分类标签模块
-- ============================================

-- 分类表
CREATE TABLE IF NOT EXISTS category (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL COMMENT '分类名称',
    slug VARCHAR(50) UNIQUE COMMENT 'URL别名',
    description VARCHAR(200) COMMENT '描述',
    icon VARCHAR(50) COMMENT '图标',
    color VARCHAR(20) COMMENT '颜色',
    sort INT NOT NULL DEFAULT 0 COMMENT '排序',
    parent_id BIGINT COMMENT '父分类ID（支持多级）',
    article_count INT NOT NULL DEFAULT 0 COMMENT '文章数量',
    status INT NOT NULL DEFAULT 1 COMMENT '状态：1-正常 0-禁用',
    create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted BOOLEAN NOT NULL DEFAULT FALSE COMMENT '逻辑删除标记'
);

COMMENT ON TABLE category IS '分类表';
COMMENT ON COLUMN category.name IS '分类名称';
COMMENT ON COLUMN category.slug IS 'URL别名';
COMMENT ON COLUMN category.description IS '描述';
COMMENT ON COLUMN category.icon IS '图标';
COMMENT ON COLUMN category.color IS '颜色';
COMMENT ON COLUMN category.sort IS '排序';
COMMENT ON COLUMN category.parent_id IS '父分类ID（支持多级）';
COMMENT ON COLUMN category.article_count IS '文章数量';
COMMENT ON COLUMN category.status IS '状态：1-正常 0-禁用';
COMMENT ON COLUMN category.deleted IS '逻辑删除标记';

CREATE INDEX IF NOT EXISTS idx_category_parent_id ON category(parent_id);
CREATE INDEX IF NOT EXISTS idx_category_sort ON category(sort);
CREATE INDEX IF NOT EXISTS idx_category_status ON category(status);
CREATE INDEX IF NOT EXISTS idx_category_deleted ON category(deleted);

-- 标签表
CREATE TABLE IF NOT EXISTS tag (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE COMMENT '标签名称',
    slug VARCHAR(50) UNIQUE COMMENT 'URL别名',
    color VARCHAR(20) COMMENT '颜色',
    icon VARCHAR(50) COMMENT '图标',
    description VARCHAR(200) COMMENT '描述',
    article_count INT NOT NULL DEFAULT 0 COMMENT '文章数量',
    status INT NOT NULL DEFAULT 1 COMMENT '状态：1-正常 0-禁用',
    create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted BOOLEAN NOT NULL DEFAULT FALSE COMMENT '逻辑删除标记'
);

COMMENT ON TABLE tag IS '标签表';
COMMENT ON COLUMN tag.name IS '标签名称';
COMMENT ON COLUMN tag.slug IS 'URL别名';
COMMENT ON COLUMN tag.color IS '颜色';
COMMENT ON COLUMN tag.icon IS '图标';
COMMENT ON COLUMN tag.description IS '描述';
COMMENT ON COLUMN tag.article_count IS '文章数量';
COMMENT ON COLUMN tag.status IS '状态：1-正常 0-禁用';
COMMENT ON COLUMN tag.deleted IS '逻辑删除标记';

CREATE INDEX IF NOT EXISTS idx_tag_name ON tag(name);
CREATE INDEX IF NOT EXISTS idx_tag_status ON tag(status);
CREATE INDEX IF NOT EXISTS idx_tag_deleted ON tag(deleted);

-- 文章-标签关联表
CREATE TABLE IF NOT EXISTS article_tag (
    article_id BIGINT NOT NULL COMMENT '文章ID',
    tag_id BIGINT NOT NULL COMMENT '标签ID',
    create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (article_id, tag_id)
);

COMMENT ON TABLE article_tag IS '文章-标签关联表';
COMMENT ON COLUMN article_tag.article_id IS '文章ID';
COMMENT ON COLUMN article_tag.tag_id IS '标签ID';

CREATE INDEX IF NOT EXISTS idx_at_tag_id ON article_tag(tag_id);
CREATE INDEX IF NOT EXISTS idx_at_article_id ON article_tag(article_id);

-- ============================================
-- 个人展示模块
-- ============================================

-- 项目展示表
CREATE TABLE IF NOT EXISTS project_showcase (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL COMMENT '项目名称',
    slug VARCHAR(100) UNIQUE COMMENT 'URL别名',
    description TEXT COMMENT '项目描述',
    cover VARCHAR(255) COMMENT '项目封面',
    screenshots TEXT COMMENT '截图JSON数组',
    tech_stack TEXT COMMENT '技术栈JSON数组',
    github_url VARCHAR(500) COMMENT 'GitHub链接',
    demo_url VARCHAR(500) COMMENT '演示链接',
    doc_url VARCHAR(500) COMMENT '文档链接',
    sort INT NOT NULL DEFAULT 0 COMMENT '排序',
    status INT NOT NULL DEFAULT 1 COMMENT '状态：1-展示中 0-隐藏',
    start_date DATE COMMENT '开始日期',
    end_date DATE COMMENT '结束日期',
    create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted BOOLEAN NOT NULL DEFAULT FALSE COMMENT '逻辑删除标记'
);

COMMENT ON TABLE project_showcase IS '项目展示表';
COMMENT ON COLUMN project_showcase.name IS '项目名称';
COMMENT ON COLUMN project_showcase.slug IS 'URL别名';
COMMENT ON COLUMN project_showcase.description IS '项目描述';
COMMENT ON COLUMN project_showcase.cover IS '项目封面';
COMMENT ON COLUMN project_showcase.screenshots IS '截图JSON数组';
COMMENT ON COLUMN project_showcase.tech_stack IS '技术栈JSON数组';
COMMENT ON COLUMN project_showcase.github_url IS 'GitHub链接';
COMMENT ON COLUMN project_showcase.demo_url IS '演示链接';
COMMENT ON COLUMN project_showcase.doc_url IS '文档链接';
COMMENT ON COLUMN project_showcase.sort IS '排序';
COMMENT ON COLUMN project_showcase.status IS '状态：1-展示中 0-隐藏';
COMMENT ON COLUMN project_showcase.start_date IS '开始日期';
COMMENT ON COLUMN project_showcase.end_date IS '结束日期';
COMMENT ON COLUMN project_showcase.deleted IS '逻辑删除标记';

CREATE INDEX IF NOT EXISTS idx_project_sort ON project_showcase(sort);
CREATE INDEX IF NOT EXISTS idx_project_status ON project_showcase(status);
CREATE INDEX IF NOT EXISTS idx_project_deleted ON project_showcase(deleted);

-- 技能表
CREATE TABLE IF NOT EXISTS skill (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL COMMENT '技能名称',
    category VARCHAR(50) COMMENT '技能分类：language-语言 framework-框架 tool-工具 other-其他',
    proficiency INT COMMENT '熟练度：1-5',
    icon VARCHAR(255) COMMENT '图标',
    color VARCHAR(20) COMMENT '颜色',
    description VARCHAR(200) COMMENT '描述',
    sort INT NOT NULL DEFAULT 0 COMMENT '排序',
    status INT NOT NULL DEFAULT 1 COMMENT '状态：1-展示中 0-隐藏',
    create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted BOOLEAN NOT NULL DEFAULT FALSE COMMENT '逻辑删除标记'
);

COMMENT ON TABLE skill IS '技能表';
COMMENT ON COLUMN skill.name IS '技能名称';
COMMENT ON COLUMN skill.category IS '技能分类：language-语言 framework-框架 tool-工具 other-其他';
COMMENT ON COLUMN skill.proficiency IS '熟练度：1-5';
COMMENT ON COLUMN skill.icon IS '图标';
COMMENT ON COLUMN skill.color IS '颜色';
COMMENT ON COLUMN skill.description IS '描述';
COMMENT ON COLUMN skill.sort IS '排序';
COMMENT ON COLUMN skill.status IS '状态：1-展示中 0-隐藏';
COMMENT ON COLUMN skill.deleted IS '逻辑删除标记';

CREATE INDEX IF NOT EXISTS idx_skill_category ON skill(category);
CREATE INDEX IF NOT EXISTS idx_skill_sort ON skill(sort);
CREATE INDEX IF NOT EXISTS idx_skill_status ON skill(status);
CREATE INDEX IF NOT EXISTS idx_skill_deleted ON skill(deleted);

-- ============================================
-- 文件管理模块
-- ============================================

-- 文件表
CREATE TABLE IF NOT EXISTS sys_file (
    id BIGSERIAL PRIMARY KEY,
    original_name VARCHAR(255) NOT NULL COMMENT '原始文件名',
    file_name VARCHAR(255) NOT NULL COMMENT '存储文件名',
    file_path VARCHAR(500) NOT NULL COMMENT '文件路径',
    file_url VARCHAR(500) NOT NULL COMMENT '访问URL',
    file_type VARCHAR(50) COMMENT '文件类型',
    file_size BIGINT COMMENT '文件大小（字节）',
    mime_type VARCHAR(100) COMMENT 'MIME类型',
    md5 VARCHAR(32) COMMENT '文件MD5',
    width INT COMMENT '图片宽度',
    height INT COMMENT '图片高度',
    user_id BIGINT COMMENT '上传用户ID',
    storage_type VARCHAR(20) DEFAULT 'local' COMMENT '存储类型：local-本地 minio-Minio oss-阿里云OSS',
    usage_type VARCHAR(50) COMMENT '用途：article-文章封面 project-项目图 avatar-头像 log-日志图',
    ref_id BIGINT COMMENT '关联ID',
    create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted BOOLEAN NOT NULL DEFAULT FALSE COMMENT '逻辑删除标记'
);

COMMENT ON TABLE sys_file IS '文件表';
COMMENT ON COLUMN sys_file.original_name IS '原始文件名';
COMMENT ON COLUMN sys_file.file_name IS '存储文件名';
COMMENT ON COLUMN sys_file.file_path IS '文件路径';
COMMENT ON COLUMN sys_file.file_url IS '访问URL';
COMMENT ON COLUMN sys_file.file_type IS '文件类型';
COMMENT ON COLUMN sys_file.file_size IS '文件大小（字节）';
COMMENT ON COLUMN sys_file.mime_type IS 'MIME类型';
COMMENT ON COLUMN sys_file.md5 IS '文件MD5';
COMMENT ON COLUMN sys_file.width IS '图片宽度';
COMMENT ON COLUMN sys_file.height IS '图片高度';
COMMENT ON COLUMN sys_file.user_id IS '上传用户ID';
COMMENT ON COLUMN sys_file.storage_type IS '存储类型：local-本地 minio-Minio oss-阿里云OSS';
COMMENT ON COLUMN sys_file.usage_type IS '用途：article-文章封面 project-项目图 avatar-头像 log-日志图';
COMMENT ON COLUMN sys_file.ref_id IS '关联ID';
COMMENT ON COLUMN sys_file.deleted IS '逻辑删除标记';

CREATE INDEX IF NOT EXISTS idx_file_user_id ON sys_file(user_id);
CREATE INDEX IF NOT EXISTS idx_file_md5 ON sys_file(md5);
CREATE INDEX IF NOT EXISTS idx_file_usage_type ON sys_file(usage_type);
CREATE INDEX IF NOT EXISTS idx_file_ref_id ON sys_file(ref_id);
CREATE INDEX IF NOT EXISTS idx_file_deleted ON sys_file(deleted);

-- ============================================
-- 系统配置模块
-- ============================================

-- 系统配置表
CREATE TABLE IF NOT EXISTS sys_config (
    id BIGSERIAL PRIMARY KEY,
    config_key VARCHAR(100) NOT NULL UNIQUE COMMENT '配置键',
    config_value TEXT COMMENT '配置值',
    default_value TEXT COMMENT '默认值',
    description VARCHAR(200) COMMENT '描述',
    group_name VARCHAR(50) COMMENT '分组',
    is_public BOOLEAN DEFAULT FALSE COMMENT '是否公开',
    create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted BOOLEAN NOT NULL DEFAULT FALSE COMMENT '逻辑删除标记'
);

COMMENT ON TABLE sys_config IS '系统配置表';
COMMENT ON COLUMN sys_config.config_key IS '配置键';
COMMENT ON COLUMN sys_config.config_value IS '配置值';
COMMENT ON COLUMN sys_config.default_value IS '默认值';
COMMENT ON COLUMN sys_config.description IS '描述';
COMMENT ON COLUMN sys_config.group_name IS '分组';
COMMENT ON COLUMN sys_config.is_public IS '是否公开';
COMMENT ON COLUMN sys_config.deleted IS '逻辑删除标记';

CREATE INDEX IF NOT EXISTS idx_config_key ON sys_config(config_key);
CREATE INDEX IF NOT EXISTS idx_config_group ON sys_config(group_name);
CREATE INDEX IF NOT EXISTS idx_config_deleted ON sys_config(deleted);

-- 友链表
CREATE TABLE IF NOT EXISTS friend_link (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL COMMENT '网站名称',
    url VARCHAR(200) NOT NULL COMMENT '网站链接',
    logo VARCHAR(255) COMMENT '网站Logo',
    description VARCHAR(200) COMMENT '描述',
    email VARCHAR(100) COMMENT '联系邮箱',
    sort INT NOT NULL DEFAULT 0 COMMENT '排序',
    status INT NOT NULL DEFAULT 1 COMMENT '状态：1-正常 2-待审核 0-禁用',
    create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted BOOLEAN NOT NULL DEFAULT FALSE COMMENT '逻辑删除标记'
);

COMMENT ON TABLE friend_link IS '友链表';
COMMENT ON COLUMN friend_link.name IS '网站名称';
COMMENT ON COLUMN friend_link.url IS '网站链接';
COMMENT ON COLUMN friend_link.logo IS '网站Logo';
COMMENT ON COLUMN friend_link.description IS '描述';
COMMENT ON COLUMN friend_link.email IS '联系邮箱';
COMMENT ON COLUMN friend_link.sort IS '排序';
COMMENT ON COLUMN friend_link.status IS '状态：1-正常 2-待审核 0-禁用';
COMMENT ON COLUMN friend_link.deleted IS '逻辑删除标记';

CREATE INDEX IF NOT EXISTS idx_fl_status ON friend_link(status);
CREATE INDEX IF NOT EXISTS idx_fl_sort ON friend_link(sort);
CREATE INDEX IF NOT EXISTS idx_fl_deleted ON friend_link(deleted);

-- 操作日志表
CREATE TABLE IF NOT EXISTS sys_operation_log (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT COMMENT '用户ID',
    username VARCHAR(50) COMMENT '用户名',
    module VARCHAR(50) COMMENT '模块',
    type VARCHAR(50) COMMENT '操作类型',
    description VARCHAR(200) COMMENT '描述',
    request_method VARCHAR(10) COMMENT '请求方法',
    request_url VARCHAR(500) COMMENT '请求URL',
    request_params TEXT COMMENT '请求参数',
    response_data TEXT COMMENT '响应数据',
    ip VARCHAR(50) COMMENT 'IP地址',
    location VARCHAR(100) COMMENT '地理位置',
    user_agent VARCHAR(500) COMMENT '浏览器UA',
    execute_time BIGINT COMMENT '执行时间（毫秒）',
    status INT COMMENT '状态：1-成功 0-失败',
    error_msg TEXT COMMENT '错误信息',
    create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE sys_operation_log IS '操作日志表';
COMMENT ON COLUMN sys_operation_log.user_id IS '用户ID';
COMMENT ON COLUMN sys_operation_log.username IS '用户名';
COMMENT ON COLUMN sys_operation_log.module IS '模块';
COMMENT ON COLUMN sys_operation_log.type IS '操作类型';
COMMENT ON COLUMN sys_operation_log.description IS '描述';
COMMENT ON COLUMN sys_operation_log.request_method IS '请求方法';
COMMENT ON COLUMN sys_operation_log.request_url IS '请求URL';
COMMENT ON COLUMN sys_operation_log.request_params IS '请求参数';
COMMENT ON COLUMN sys_operation_log.response_data IS '响应数据';
COMMENT ON COLUMN sys_operation_log.ip IS 'IP地址';
COMMENT ON COLUMN sys_operation_log.location IS '地理位置';
COMMENT ON COLUMN sys_operation_log.user_agent IS '浏览器UA';
COMMENT ON COLUMN sys_operation_log.execute_time IS '执行时间（毫秒）';
COMMENT ON COLUMN sys_operation_log.status IS '状态：1-成功 0-失败';
COMMENT ON COLUMN sys_operation_log.error_msg IS '错误信息';

CREATE INDEX IF NOT EXISTS idx_ol_user_id ON sys_operation_log(user_id);
CREATE INDEX IF NOT EXISTS idx_ol_module ON sys_operation_log(module);
CREATE INDEX IF NOT EXISTS idx_ol_create_time ON sys_operation_log(create_time DESC);
CREATE INDEX IF NOT EXISTS idx_ol_status ON sys_operation_log(status);

-- ============================================
-- AI 模块
-- ============================================

-- AI生成记录表
CREATE TABLE IF NOT EXISTS ai_generation (
    id BIGSERIAL PRIMARY KEY,
    article_id BIGINT NOT NULL COMMENT '文章ID',
    type VARCHAR(20) NOT NULL COMMENT '类型：tags-标签 summary-摘要 recommend-推荐 content-内容生成',
    prompt TEXT COMMENT '提示词',
    content TEXT COMMENT '生成内容',
    tokens_used INT COMMENT '使用的token数',
    model VARCHAR(50) COMMENT '使用的模型',
    status INT NOT NULL DEFAULT 1 COMMENT '状态：1-成功 0-失败',
    error_msg TEXT COMMENT '错误信息',
    create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE ai_generation IS 'AI生成记录表';
COMMENT ON COLUMN ai_generation.article_id IS '文章ID';
COMMENT ON COLUMN ai_generation.type IS '类型：tags-标签 summary-摘要 recommend-推荐 content-内容生成';
COMMENT ON COLUMN ai_generation.prompt IS '提示词';
COMMENT ON COLUMN ai_generation.content IS '生成内容';
COMMENT ON COLUMN ai_generation.tokens_used IS '使用的token数';
COMMENT ON COLUMN ai_generation.model IS '使用的模型';
COMMENT ON COLUMN ai_generation.status IS '状态：1-成功 0-失败';
COMMENT ON COLUMN ai_generation.error_msg IS '错误信息';

CREATE INDEX IF NOT EXISTS idx_ag_article_id ON ai_generation(article_id);
CREATE INDEX IF NOT EXISTS idx_ag_type ON ai_generation(type);
CREATE INDEX IF NOT EXISTS idx_ag_create_time ON ai_generation(create_time DESC);

-- 文章内容向量表（用于AI推荐和语义搜索）
CREATE TABLE IF NOT EXISTS article_vector (
    id BIGSERIAL PRIMARY KEY,
    article_id BIGINT NOT NULL UNIQUE COMMENT '文章ID',
    content_vector vector(1536) COMMENT '内容向量（使用OpenAI或DashScope嵌入）',
    summary_vector vector(1536) COMMENT '摘要向量',
    keywords TEXT COMMENT '关键词JSON数组',
    create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE article_vector IS '文章内容向量表（用于AI推荐）';
COMMENT ON COLUMN article_vector.article_id IS '文章ID';
COMMENT ON COLUMN article_vector.content_vector IS '内容向量（使用OpenAI或DashScope嵌入）';
COMMENT ON COLUMN article_vector.summary_vector IS '摘要向量';
COMMENT ON COLUMN article_vector.keywords IS '关键词JSON数组';

CREATE INDEX IF NOT EXISTS idx_av_article_id ON article_vector(article_id);

-- 向量索引（用于余弦相似度搜索）
CREATE INDEX IF NOT EXISTS idx_av_content_vector ON article_vector USING ivfflat (content_vector vector_cosine_ops);

-- ============================================
-- 外键约束（在表创建完成后添加，避免循环依赖）
-- ============================================

-- 文章表外键
ALTER TABLE article
    ADD CONSTRAINT IF NOT EXISTS fk_article_category FOREIGN KEY (category_id) REFERENCES category(id),
    ADD CONSTRAINT IF NOT EXISTS fk_article_user FOREIGN KEY (user_id) REFERENCES sys_user(id);

-- 文章草稿表外键
ALTER TABLE article_draft
    ADD CONSTRAINT IF NOT EXISTS fk_draft_category FOREIGN KEY (category_id) REFERENCES category(id),
    ADD CONSTRAINT IF NOT EXISTS fk_draft_article FOREIGN KEY (article_id) REFERENCES article(id) ON DELETE CASCADE;

-- 分类表外键（自引用）
ALTER TABLE category
    ADD CONSTRAINT IF NOT EXISTS fk_category_parent FOREIGN KEY (parent_id) REFERENCES category(id);

-- 文章标签关联表外键
ALTER TABLE article_tag
    ADD CONSTRAINT IF NOT EXISTS fk_at_article FOREIGN KEY (article_id) REFERENCES article(id) ON DELETE CASCADE,
    ADD CONSTRAINT IF NOT EXISTS fk_at_tag FOREIGN KEY (tag_id) REFERENCES tag(id) ON DELETE CASCADE;

-- 文件表外键
ALTER TABLE sys_file
    ADD CONSTRAINT IF NOT EXISTS fk_file_user FOREIGN KEY (user_id) REFERENCES sys_user(id);

-- AI生成记录表外键
ALTER TABLE ai_generation
    ADD CONSTRAINT IF NOT EXISTS fk_ag_article FOREIGN KEY (article_id) REFERENCES article(id) ON DELETE CASCADE;

-- 文章内容向量表外键
ALTER TABLE article_vector
    ADD CONSTRAINT IF NOT EXISTS fk_av_article FOREIGN KEY (article_id) REFERENCES article(id) ON DELETE CASCADE;

-- ============================================
-- 初始化数据
-- ============================================

-- 插入默认管理员
INSERT INTO sys_user (id, username, password, nickname, email, role, status)
VALUES (1, 'admin', '$2a$10$N.zmdr9k7uOCQb376NoUnuTJ8iAt6Z5EHsM8lE9lBOsl7iAt6Z5EO', '管理员', 'admin@example.com', 'ADMIN', 1)
ON CONFLICT (username) DO NOTHING;

-- 插入默认分类
INSERT INTO category (id, name, slug, description, sort)
VALUES
    (1, '后端开发', 'backend', 'Java后端开发相关文章', 1),
    (2, '前端技术', 'frontend', '前端开发技术分享', 2),
    (3, '数据库', 'database', '数据库技术与优化', 3),
    (4, 'DevOps', 'devops', '运维与部署', 4),
    (5, '技术日志', 'daily-log', '每日技术笔记', 5),
    (6, '项目展示', 'projects', '个人项目介绍', 6)
ON CONFLICT DO NOTHING;

-- 插入默认标签
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

-- 插入系统配置
INSERT INTO sys_config (config_key, config_value, default_value, description, group_name, is_public)
VALUES
    ('site.name', '我的技术博客', '我的技术博客', '网站名称', 'site', TRUE),
    ('site.description', '记录技术成长，分享学习心得', '记录技术成长，分享学习心得', '网站描述', 'site', TRUE),
    ('site.logo', '', '', '网站Logo', 'site', TRUE),
    ('site.favicon', '', '', '网站Favicon', 'site', TRUE),
    ('site.icp', '', '', 'ICP备案号', 'site', TRUE),
    ('site.footer', '© 2025 我的技术博客', '© 2025 我的技术博客', '页脚信息', 'site', TRUE),
    ('site.about', '', '', '关于页面内容（Markdown）', 'site', TRUE),
    ('site.avatar', '', '', '个人头像', 'site', TRUE),
    ('site.email', '', '', '联系邮箱', 'site', TRUE),
    ('site.github', '', '', 'GitHub链接', 'site', TRUE),
    ('ai.enabled', 'false', 'false', '是否启用AI功能', 'ai', FALSE),
    ('ai.model', 'qwen-turbo', 'qwen-turbo', 'AI模型', 'ai', FALSE),
    ('ai.autoTags', 'true', 'true', '是否自动生成标签', 'ai', FALSE),
    ('ai.autoSummary', 'true', 'true', '是否自动生成摘要', 'ai', FALSE)
ON CONFLICT (config_key) DO NOTHING;

-- 插入示例技能
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
