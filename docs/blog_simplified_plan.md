# 个人技术博客系统 - 简化版开发方案
## 基于 Spring Boot 3.5 + Vue 3 + 阿里云ECS（无评论模块）

---

## 一、项目定位

### 1.1 核心定位
- **个人技术博客**：记录技术学习、分享技术文章
- **个人展示网站**：展示个人技能、项目经历
- **技术日志**：每日技术笔记、学习总结

### 1.2 用户角色
- **仅有一个管理员**：自己
- **访客**：只能浏览，不能互动（无评论）

### 1.3 核心功能
1. ✅ 文章管理（Markdown编辑、发布、分类、标签）
2. ✅ 技术日志（快速记录、时间线展示）
3. ✅ 个人展示（关于页面、技能展示、项目展示）
4. ✅ 内容搜索（全文搜索）
5. ✅ AI辅助（智能标签、文章摘要）
6. ✅ 数据统计（访问量、文章统计）

---

## 二、技术架构

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        个人技术博客系统                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────────┐         ┌──────────────────────────┐ │
│  │       前端层          │         │          后端层           │ │
│  │  ┌────────────────┐  │         │  ┌────────────────────┐   │ │
│  │  │   Vue 3        │  │         │  │  Spring Boot 3.5   │   │ │
│  │  │   + Vite       │  │◄───────►│  │  + Java 21         │   │ │
│  │  │   + TypeScript │  │  HTTP   │  │  + MyBatis Plus    │   │ │
│  │  │   + Tailwind   │  │         │  │  + Sa-Token        │   │ │
│  │  │   + Pinia      │  │         │  │  + Validation      │   │ │
│  │  │   + Element+   │  │         │  └────────────────────┘   │ │
│  │  └────────────────┘  │         └───────────┬───────────────┘ │
│  └──────────────────────┘                     │                 │
│  ┌──────────────────────┐         ┌───────────▼───────────┐    │
│  │    客户端搜索         │         │       数据层           │    │
│  │  ┌────────────────┐  │         │  ┌─────────────────┐   │    │
│  │  │   Pagefind     │  │         │  │   PostgreSQL    │   │    │
│  │  │   (全文搜索)    │  │         │  │   (主数据库)     │   │    │
│  │  └────────────────┘  │         │  └─────────────────┘   │    │
│  └──────────────────────┘         │  ┌─────────────────┐   │    │
│                                     │  │     Redis       │   │    │
│  ┌──────────────────────┐         │  │   (缓存/会话)    │   │    │
│  │    AI能力层          │         │  └─────────────────┘   │    │
│  │  ┌────────────────┐  │         └────────────────────────┘    │
│  │  │  Spring AI     │  │                                      │
│  │  │  + DashScope   │  │                                      │
│  │  │  (通义千问)     │  │                                      │
│  │  └────────────────┘  │                                      │
│  └──────────────────────┘                                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 技术栈

| 层级 | 技术选型 | 版本 |
|------|----------|------|
| **后端** | Spring Boot | 3.5.x |
| **JDK** | Java | 21 |
| **ORM** | MyBatis Plus | 3.5.5 |
| **数据库** | PostgreSQL | 15+ |
| **缓存** | Redis | 7+ |
| **认证** | Sa-Token | 1.44+ |
| **API文档** | Knife4j | 4.4+ |
| **工具库** | Hutool | 5.8+ |
| **前端** | Vue | 3.4+ |
| **构建** | Vite | 5+ |
| **类型** | TypeScript | 5+ |
| **样式** | Tailwind CSS | 3.4+ |
| **UI组件** | Element Plus | 2.5+ |
| **状态** | Pinia | 2+ |
| **Markdown** | md-editor-v3 | 4+ |
| **搜索** | Pagefind | 1+ |
| **AI** | Spring AI | 0.8+ |
| **AI模型** | DashScope | - |

---

## 三、数据库设计（简化版）

### 3.1 表结构概览

| 表名 | 说明 | 数据量预估 |
|------|------|------------|
| sys_user | 用户表（仅管理员） | < 5 |
| sys_login_log | 登录日志 | < 1,000 |
| sys_file | 文件表 | < 2,000 |
| sys_config | 系统配置 | < 30 |
| sys_operation_log | 操作日志 | < 10,000 |
| article | 文章表 | < 500 |
| article_draft | 草稿表 | < 50 |
| daily_log | 技术日志表 | < 1,000 |
| category | 分类表 | < 15 |
| tag | 标签表 | < 50 |
| article_tag | 文章标签关联表 | < 2,000 |
| project_showcase | 项目展示表 | < 20 |
| skill | 技能表 | < 30 |
| ai_generation | AI生成记录表 | < 1,000 |
| article_vector | 文章向量表 | < 500 |

### 3.2 数据库表详细设计

#### 3.2.1 用户模块

```sql
-- ============================================
-- 用户表 (sys_user)
-- ============================================
CREATE TABLE sys_user (
    id BIGSERIAL PRIMARY KEY COMMENT '用户ID',
    username VARCHAR(50) NOT NULL UNIQUE COMMENT '用户名',
    password VARCHAR(100) NOT NULL COMMENT '密码（BCrypt加密）',
    nickname VARCHAR(50) COMMENT '昵称',
    avatar VARCHAR(255) COMMENT '头像URL',
    email VARCHAR(100) COMMENT '邮箱',
    phone VARCHAR(20) COMMENT '手机号',
    role VARCHAR(20) NOT NULL DEFAULT 'ADMIN' COMMENT '角色：ADMIN-管理员',
    status INT NOT NULL DEFAULT 1 COMMENT '状态：1-正常 0-禁用',
    login_ip VARCHAR(50) COMMENT '最后登录IP',
    login_time TIMESTAMP COMMENT '最后登录时间',
    create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '更新时间',
    deleted BOOLEAN NOT NULL DEFAULT FALSE COMMENT '逻辑删除'
);

COMMENT ON TABLE sys_user IS '用户表（仅管理员）';

-- 索引
CREATE INDEX idx_sys_user_username ON sys_user(username);
CREATE INDEX idx_sys_user_deleted ON sys_user(deleted);

-- ============================================
-- 用户登录日志表 (sys_login_log)
-- ============================================
CREATE TABLE sys_login_log (
    id BIGSERIAL PRIMARY KEY COMMENT '日志ID',
    user_id BIGINT COMMENT '用户ID',
    username VARCHAR(50) COMMENT '用户名',
    ip VARCHAR(50) COMMENT '登录IP',
    location VARCHAR(100) COMMENT '登录地点',
    user_agent VARCHAR(500) COMMENT '浏览器UA',
    status INT NOT NULL DEFAULT 1 COMMENT '状态：1-成功 0-失败',
    message VARCHAR(200) COMMENT '消息',
    create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'
);

COMMENT ON TABLE sys_login_log IS '用户登录日志表';

CREATE INDEX idx_login_log_user_id ON sys_login_log(user_id);
CREATE INDEX idx_login_log_create_time ON sys_login_log(create_time);
```

#### 3.2.2 文章模块

```sql
-- ============================================
-- 文章表 (article)
-- ============================================
CREATE TABLE article (
    id BIGSERIAL PRIMARY KEY COMMENT '文章ID',
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
    create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '更新时间',
    deleted BOOLEAN NOT NULL DEFAULT FALSE COMMENT '逻辑删除',
    
    CONSTRAINT fk_article_category FOREIGN KEY (category_id) REFERENCES category(id),
    CONSTRAINT fk_article_user FOREIGN KEY (user_id) REFERENCES sys_user(id)
);

COMMENT ON TABLE article IS '文章表';
COMMENT ON COLUMN article.status IS '状态：1-已发布 2-草稿 3-回收站';

-- 索引
CREATE INDEX idx_article_category_id ON article(category_id);
CREATE INDEX idx_article_status ON article(status);
CREATE INDEX idx_article_is_top ON article(is_top);
CREATE INDEX idx_article_publish_time ON article(publish_time DESC);
CREATE INDEX idx_article_deleted ON article(deleted);
CREATE INDEX idx_article_create_time ON article(create_time DESC);

-- 全文搜索索引
CREATE INDEX idx_article_content_search ON article USING GIN (to_tsvector('chinese', content));
CREATE INDEX idx_article_title_search ON article USING GIN (to_tsvector('chinese', title));

-- ============================================
-- 文章草稿表 (article_draft)
-- ============================================
CREATE TABLE article_draft (
    id BIGSERIAL PRIMARY KEY COMMENT '草稿ID',
    article_id BIGINT COMMENT '关联的文章ID（新建时为null）',
    title VARCHAR(200) COMMENT '标题',
    content TEXT COMMENT '内容',
    category_id BIGINT COMMENT '分类ID',
    tags TEXT COMMENT '标签JSON数组',
    auto_save BOOLEAN DEFAULT FALSE COMMENT '是否自动保存',
    create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '更新时间',
    
    CONSTRAINT fk_draft_article FOREIGN KEY (article_id) REFERENCES article(id) ON DELETE CASCADE,
    CONSTRAINT fk_draft_category FOREIGN KEY (category_id) REFERENCES category(id)
);

COMMENT ON TABLE article_draft IS '文章草稿表';

CREATE INDEX idx_draft_article_id ON article_draft(article_id);
CREATE INDEX idx_draft_update_time ON article_draft(update_time DESC);

-- ============================================
-- 技术日志表 (daily_log)
-- 用于快速记录每日技术笔记
-- ============================================
CREATE TABLE daily_log (
    id BIGSERIAL PRIMARY KEY COMMENT '日志ID',
    content TEXT NOT NULL COMMENT '日志内容（Markdown）',
    content_html TEXT COMMENT 'HTML渲染后内容',
    mood VARCHAR(20) COMMENT '心情：happy-开心 excited-兴奋 normal-平静 tired-疲惫',
    weather VARCHAR(20) COMMENT '天气',
    tags TEXT COMMENT '标签JSON数组',
    word_count INT COMMENT '字数',
    log_date DATE NOT NULL COMMENT '日志日期',
    create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '更新时间',
    deleted BOOLEAN NOT NULL DEFAULT FALSE COMMENT '逻辑删除'
);

COMMENT ON TABLE daily_log IS '技术日志表（每日技术笔记）';
COMMENT ON COLUMN daily_log.mood IS '心情：happy-开心 excited-兴奋 normal-平静 tired-疲惫';

-- 索引
CREATE INDEX idx_daily_log_log_date ON daily_log(log_date DESC);
CREATE INDEX idx_daily_log_deleted ON daily_log(deleted);
```

#### 3.2.3 分类标签模块

```sql
-- ============================================
-- 分类表 (category)
-- ============================================
CREATE TABLE category (
    id BIGSERIAL PRIMARY KEY COMMENT '分类ID',
    name VARCHAR(50) NOT NULL COMMENT '分类名称',
    slug VARCHAR(50) UNIQUE COMMENT 'URL别名',
    description VARCHAR(200) COMMENT '描述',
    icon VARCHAR(50) COMMENT '图标',
    color VARCHAR(20) COMMENT '颜色',
    sort INT NOT NULL DEFAULT 0 COMMENT '排序',
    parent_id BIGINT COMMENT '父分类ID（支持多级）',
    article_count INT NOT NULL DEFAULT 0 COMMENT '文章数量',
    status INT NOT NULL DEFAULT 1 COMMENT '状态：1-正常 0-禁用',
    create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '更新时间',
    deleted BOOLEAN NOT NULL DEFAULT FALSE COMMENT '逻辑删除',
    
    CONSTRAINT fk_category_parent FOREIGN KEY (parent_id) REFERENCES category(id)
);

COMMENT ON TABLE category IS '分类表';

CREATE INDEX idx_category_parent_id ON category(parent_id);
CREATE INDEX idx_category_sort ON category(sort);
CREATE INDEX idx_category_status ON category(status);
CREATE INDEX idx_category_deleted ON category(deleted);

-- ============================================
-- 标签表 (tag)
-- ============================================
CREATE TABLE tag (
    id BIGSERIAL PRIMARY KEY COMMENT '标签ID',
    name VARCHAR(50) NOT NULL UNIQUE COMMENT '标签名称',
    slug VARCHAR(50) UNIQUE COMMENT 'URL别名',
    color VARCHAR(20) COMMENT '颜色',
    icon VARCHAR(50) COMMENT '图标',
    description VARCHAR(200) COMMENT '描述',
    article_count INT NOT NULL DEFAULT 0 COMMENT '文章数量',
    status INT NOT NULL DEFAULT 1 COMMENT '状态：1-正常 0-禁用',
    create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '更新时间',
    deleted BOOLEAN NOT NULL DEFAULT FALSE COMMENT '逻辑删除'
);

COMMENT ON TABLE tag IS '标签表';

CREATE INDEX idx_tag_name ON tag(name);
CREATE INDEX idx_tag_status ON tag(status);
CREATE INDEX idx_tag_deleted ON tag(deleted);

-- ============================================
-- 文章-标签关联表 (article_tag)
-- ============================================
CREATE TABLE article_tag (
    article_id BIGINT NOT NULL COMMENT '文章ID',
    tag_id BIGINT NOT NULL COMMENT '标签ID',
    create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    
    PRIMARY KEY (article_id, tag_id),
    CONSTRAINT fk_at_article FOREIGN KEY (article_id) REFERENCES article(id) ON DELETE CASCADE,
    CONSTRAINT fk_at_tag FOREIGN KEY (tag_id) REFERENCES tag(id) ON DELETE CASCADE
);

COMMENT ON TABLE article_tag IS '文章-标签关联表';

CREATE INDEX idx_at_tag_id ON article_tag(tag_id);
```

#### 3.2.4 个人展示模块

```sql
-- ============================================
-- 项目展示表 (project_showcase)
-- 用于展示个人项目
-- ============================================
CREATE TABLE project_showcase (
    id BIGSERIAL PRIMARY KEY COMMENT '项目ID',
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
    create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '更新时间',
    deleted BOOLEAN NOT NULL DEFAULT FALSE COMMENT '逻辑删除'
);

COMMENT ON TABLE project_showcase IS '项目展示表';

CREATE INDEX idx_project_sort ON project_showcase(sort);
CREATE INDEX idx_project_status ON project_showcase(status);
CREATE INDEX idx_project_deleted ON project_showcase(deleted);

-- ============================================
-- 技能表 (skill)
-- 用于展示个人技能
-- ============================================
CREATE TABLE skill (
    id BIGSERIAL PRIMARY KEY COMMENT '技能ID',
    name VARCHAR(50) NOT NULL COMMENT '技能名称',
    category VARCHAR(50) COMMENT '技能分类：language-语言 framework-框架 tool-工具 other-其他',
    proficiency INT COMMENT '熟练度：1-5',
    icon VARCHAR(255) COMMENT '图标',
    color VARCHAR(20) COMMENT '颜色',
    description VARCHAR(200) COMMENT '描述',
    sort INT NOT NULL DEFAULT 0 COMMENT '排序',
    status INT NOT NULL DEFAULT 1 COMMENT '状态：1-展示中 0-隐藏',
    create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '更新时间',
    deleted BOOLEAN NOT NULL DEFAULT FALSE COMMENT '逻辑删除'
);

COMMENT ON TABLE skill IS '技能表';
COMMENT ON COLUMN skill.category IS '技能分类：language-语言 framework-框架 tool-工具 other-其他';
COMMENT ON COLUMN skill.proficiency IS '熟练度：1-5';

CREATE INDEX idx_skill_category ON skill(category);
CREATE INDEX idx_skill_sort ON skill(sort);
CREATE INDEX idx_skill_status ON skill(status);
CREATE INDEX idx_skill_deleted ON skill(deleted);
```

#### 3.2.5 文件管理模块

```sql
-- ============================================
-- 文件表 (sys_file)
-- ============================================
CREATE TABLE sys_file (
    id BIGSERIAL PRIMARY KEY COMMENT '文件ID',
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
    create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    deleted BOOLEAN NOT NULL DEFAULT FALSE COMMENT '逻辑删除',
    
    CONSTRAINT fk_file_user FOREIGN KEY (user_id) REFERENCES sys_user(id)
);

COMMENT ON TABLE sys_file IS '文件表';

CREATE INDEX idx_file_user_id ON sys_file(user_id);
CREATE INDEX idx_file_md5 ON sys_file(md5);
CREATE INDEX idx_file_usage_type ON sys_file(usage_type);
CREATE INDEX idx_file_ref_id ON sys_file(ref_id);
CREATE INDEX idx_file_deleted ON sys_file(deleted);
```

#### 3.2.6 系统配置模块

```sql
-- ============================================
-- 系统配置表 (sys_config)
-- ============================================
CREATE TABLE sys_config (
    id BIGSERIAL PRIMARY KEY COMMENT '配置ID',
    config_key VARCHAR(100) NOT NULL UNIQUE COMMENT '配置键',
    config_value TEXT COMMENT '配置值',
    default_value TEXT COMMENT '默认值',
    description VARCHAR(200) COMMENT '描述',
    group_name VARCHAR(50) COMMENT '分组',
    is_public BOOLEAN DEFAULT FALSE COMMENT '是否公开',
    create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '更新时间'
);

COMMENT ON TABLE sys_config IS '系统配置表';

CREATE INDEX idx_config_key ON sys_config(config_key);
CREATE INDEX idx_config_group ON sys_config(group_name);

-- ============================================
-- 友链表 (friend_link)
-- ============================================
CREATE TABLE friend_link (
    id BIGSERIAL PRIMARY KEY COMMENT '友链ID',
    name VARCHAR(50) NOT NULL COMMENT '网站名称',
    url VARCHAR(200) NOT NULL COMMENT '网站链接',
    logo VARCHAR(255) COMMENT '网站Logo',
    description VARCHAR(200) COMMENT '描述',
    email VARCHAR(100) COMMENT '联系邮箱',
    sort INT NOT NULL DEFAULT 0 COMMENT '排序',
    status INT NOT NULL DEFAULT 1 COMMENT '状态：1-正常 2-待审核 0-禁用',
    create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '更新时间'
);

COMMENT ON TABLE friend_link IS '友链表';

CREATE INDEX idx_fl_status ON friend_link(status);
CREATE INDEX idx_fl_sort ON friend_link(sort);

-- ============================================
-- 操作日志表 (sys_operation_log)
-- ============================================
CREATE TABLE sys_operation_log (
    id BIGSERIAL PRIMARY KEY COMMENT '日志ID',
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
    create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'
);

COMMENT ON TABLE sys_operation_log IS '操作日志表';

CREATE INDEX idx_ol_user_id ON sys_operation_log(user_id);
CREATE INDEX idx_ol_module ON sys_operation_log(module);
CREATE INDEX idx_ol_create_time ON sys_operation_log(create_time DESC);
```

#### 3.2.7 AI模块

```sql
-- ============================================
-- AI生成记录表 (ai_generation)
-- ============================================
CREATE TABLE ai_generation (
    id BIGSERIAL PRIMARY KEY COMMENT '记录ID',
    article_id BIGINT NOT NULL COMMENT '文章ID',
    type VARCHAR(20) NOT NULL COMMENT '类型：tags-标签 summary-摘要 recommend-推荐 content-内容生成',
    prompt TEXT COMMENT '提示词',
    content TEXT COMMENT '生成内容',
    tokens_used INT COMMENT '使用的token数',
    model VARCHAR(50) COMMENT '使用的模型',
    status INT NOT NULL DEFAULT 1 COMMENT '状态：1-成功 0-失败',
    error_msg TEXT COMMENT '错误信息',
    create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    
    CONSTRAINT fk_ag_article FOREIGN KEY (article_id) REFERENCES article(id) ON DELETE CASCADE
);

COMMENT ON TABLE ai_generation IS 'AI生成记录表';
COMMENT ON COLUMN ai_generation.type IS '类型：tags-标签 summary-摘要 recommend-推荐 content-内容生成';

CREATE INDEX idx_ag_article_id ON ai_generation(article_id);
CREATE INDEX idx_ag_type ON ai_generation(type);
CREATE INDEX idx_ag_create_time ON ai_generation(create_time DESC);

-- ============================================
-- 文章内容向量表 (article_vector)
-- 用于AI推荐和语义搜索
-- ============================================
CREATE TABLE article_vector (
    id BIGSERIAL PRIMARY KEY COMMENT 'ID',
    article_id BIGINT NOT NULL UNIQUE COMMENT '文章ID',
    content_vector vector(1536) COMMENT '内容向量（使用OpenAI或DashScope嵌入）',
    summary_vector vector(1536) COMMENT '摘要向量',
    keywords TEXT COMMENT '关键词JSON数组',
    create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '更新时间',
    
    CONSTRAINT fk_av_article FOREIGN KEY (article_id) REFERENCES article(id) ON DELETE CASCADE
);

COMMENT ON TABLE article_vector IS '文章内容向量表（用于AI推荐）';

CREATE INDEX idx_av_article_id ON article_vector(article_id);
CREATE INDEX idx_av_content_vector ON article_vector USING ivfflat (content_vector vector_cosine_ops);
```

### 3.3 数据库初始化脚本

```sql
-- ============================================
-- 初始化数据
-- ============================================

-- 插入默认管理员
INSERT INTO sys_user (username, password, nickname, email, role, status) VALUES
('admin', '$2a$10$N.zmdr9k7uOCQb376NoUnuTJ8iAt6Z5EHsM8lE9lBOsl7iAt6Z5EO', '管理员', 'admin@example.com', 'ADMIN', 1);

-- 插入默认分类
INSERT INTO category (name, slug, description, sort) VALUES
('后端开发', 'backend', 'Java后端开发相关文章', 1),
('前端技术', 'frontend', '前端开发技术分享', 2),
('数据库', 'database', '数据库技术与优化', 3),
('DevOps', 'devops', '运维与部署', 4),
('技术日志', 'daily-log', '每日技术笔记', 5),
('项目展示', 'projects', '个人项目介绍', 6);

-- 插入默认标签
INSERT INTO tag (name, slug, color, description) VALUES
('Java', 'java', '#007396', 'Java编程语言'),
('Spring Boot', 'spring-boot', '#6DB33F', 'Spring Boot框架'),
('Vue', 'vue', '#4FC08D', 'Vue.js前端框架'),
('PostgreSQL', 'postgresql', '#336791', 'PostgreSQL数据库'),
('Redis', 'redis', '#DC382D', 'Redis缓存'),
('Docker', 'docker', '#2496ED', 'Docker容器'),
('Linux', 'linux', '#FCC624', 'Linux系统'),
('AI', 'ai', '#FF6B6B', '人工智能');

-- 插入系统配置
INSERT INTO sys_config (config_key, config_value, default_value, description, group_name, is_public) VALUES
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
('ai.autoSummary', 'true', 'true', '是否自动生成摘要', 'ai', FALSE);

-- 插入示例技能
INSERT INTO skill (name, category, proficiency, color, description, sort) VALUES
('Java', 'language', 4, '#007396', '熟练掌握Java编程', 1),
('Spring Boot', 'framework', 4, '#6DB33F', 'Spring Boot开发', 2),
('Vue.js', 'framework', 3, '#4FC08D', 'Vue前端开发', 3),
('PostgreSQL', 'tool', 3, '#336791', 'PostgreSQL数据库', 4),
('Redis', 'tool', 3, '#DC382D', 'Redis缓存', 5),
('Docker', 'tool', 3, '#2496ED', 'Docker容器化', 6),
('Linux', 'tool', 3, '#FCC624', 'Linux系统管理', 7);
```

---

## 四、后端项目结构

### 4.1 项目结构

```
clever-blog/
├── clever-blog-backend/
│   ├── src/
│   │   ├── main/
│   │   │   ├── java/
│   │   │   │   └── com/cleverblog/
│   │   │   │       ├── CleverBlogApplication.java
│   │   │   │       │
│   │   │   │       ├── config/                    # 配置类
│   │   │   │       │   ├── MyBatisPlusConfig.java
│   │   │   │       │   ├── SaTokenConfig.java
│   │   │   │       │   ├── WebMvcConfig.java
│   │   │   │       │   ├── RedisConfig.java
│   │   │   │       │   ├── Knife4jConfig.java
│   │   │   │       │   ├── AsyncConfig.java
│   │   │   │       │   └── AiConfig.java
│   │   │   │       │
│   │   │   │       ├── controller/                # 控制器层
│   │   │   │       │   ├── AuthController.java
│   │   │   │       │   ├── UserController.java
│   │   │   │       │   ├── ArticleController.java
│   │   │   │       │   ├── DailyLogController.java
│   │   │   │       │   ├── CategoryController.java
│   │   │   │       │   ├── TagController.java
│   │   │   │       │   ├── FileController.java
│   │   │   │       │   ├── ConfigController.java
│   │   │   │       │   ├── ProjectShowcaseController.java
│   │   │   │       │   ├── SkillController.java
│   │   │   │       │   ├── FriendLinkController.java
│   │   │   │       │   └── AiController.java
│   │   │   │       │
│   │   │   │       ├── service/                   # 业务层
│   │   │   │       │   ├── impl/
│   │   │   │       │   │   ├── UserServiceImpl.java
│   │   │   │       │   │   ├── ArticleServiceImpl.java
│   │   │   │       │   │   ├── DailyLogServiceImpl.java
│   │   │   │       │   │   ├── CategoryServiceImpl.java
│   │   │   │       │   │   ├── TagServiceImpl.java
│   │   │   │       │   │   ├── FileServiceImpl.java
│   │   │   │       │   │   ├── ConfigServiceImpl.java
│   │   │   │       │   │   ├── ProjectShowcaseServiceImpl.java
│   │   │   │       │   │   ├── SkillServiceImpl.java
│   │   │   │       │   │   └── AiServiceImpl.java
│   │   │   │       │   ├── UserService.java
│   │   │   │       │   ├── ArticleService.java
│   │   │   │       │   ├── DailyLogService.java
│   │   │   │       │   ├── CategoryService.java
│   │   │   │       │   ├── TagService.java
│   │   │   │       │   ├── FileService.java
│   │   │   │       │   ├── ConfigService.java
│   │   │   │       │   ├── ProjectShowcaseService.java
│   │   │   │       │   ├── SkillService.java
│   │   │   │       │   └── AiService.java
│   │   │   │       │
│   │   │   │       ├── mapper/                    # 数据访问层
│   │   │   │       │   ├── UserMapper.java
│   │   │   │       │   ├── ArticleMapper.java
│   │   │   │       │   ├── DailyLogMapper.java
│   │   │   │       │   ├── CategoryMapper.java
│   │   │   │       │   ├── TagMapper.java
│   │   │   │       │   ├── ArticleTagMapper.java
│   │   │   │       │   ├── FileMapper.java
│   │   │   │       │   ├── ConfigMapper.java
│   │   │   │       │   ├── ProjectShowcaseMapper.java
│   │   │   │       │   ├── SkillMapper.java
│   │   │   │       │   ├── FriendLinkMapper.java
│   │   │   │       │   └── AiGenerationMapper.java
│   │   │   │       │
│   │   │   │       ├── entity/                    # 实体类
│   │   │   │       │   ├── User.java
│   │   │   │       │   ├── Article.java
│   │   │   │       │   ├── DailyLog.java
│   │   │   │       │   ├── Category.java
│   │   │   │       │   ├── Tag.java
│   │   │   │       │   ├── ArticleTag.java
│   │   │   │       │   ├── File.java
│   │   │   │       │   ├── Config.java
│   │   │   │       │   ├── ProjectShowcase.java
│   │   │   │       │   ├── Skill.java
│   │   │   │       │   ├── FriendLink.java
│   │   │   │       │   └── AiGeneration.java
│   │   │   │       │
│   │   │   │       ├── dto/                       # 数据传输对象
│   │   │   │       │   ├── LoginDTO.java
│   │   │   │       │   ├── ArticleCreateDTO.java
│   │   │   │       │   ├── ArticleUpdateDTO.java
│   │   │   │       │   ├── ArticleQueryDTO.java
│   │   │   │       │   ├── DailyLogCreateDTO.java
│   │   │   │       │   └── FileUploadDTO.java
│   │   │   │       │
│   │   │   │       ├── vo/                        # 视图对象
│   │   │   │       │   ├── UserVO.java
│   │   │   │       │   ├── ArticleVO.java
│   │   │   │       │   ├── ArticleListVO.java
│   │   │   │       │   ├── DailyLogVO.java
│   │   │   │       │   ├── CategoryVO.java
│   │   │   │       │   ├── TagVO.java
│   │   │   │       │   ├── ProjectShowcaseVO.java
│   │   │   │       │   ├── SkillVO.java
│   │   │   │       │   └── ResultVO.java
│   │   │   │       │
│   │   │   │       ├── common/                    # 通用类
│   │   │   │       │   ├── Result.java
│   │   │   │       │   ├── PageResult.java
│   │   │   │       │   ├── BusinessException.java
│   │   │   │       │   ├── GlobalExceptionHandler.java
│   │   │   │       │   ├── BaseEntity.java
│   │   │   │       │   ├── Constants.java
│   │   │   │       │   └── enums/
│   │   │   │       │       ├── ArticleStatus.java
│   │   │   │       │       ├── DailyLogMood.java
│   │   │   │       │       └── SkillCategory.java
│   │   │   │       │
│   │   │   │       ├── utils/                     # 工具类
│   │   │   │       │   ├── JwtUtils.java
│   │   │   │       │   ├── FileUtils.java
│   │   │   │       │   ├── MarkdownUtils.java
│   │   │   │       │   ├── IpUtils.java
│   │   │   │       │   └── AiPromptUtils.java
│   │   │   │       │
│   │   │   │       ├── aspect/                    # AOP
│   │   │   │       │   └── LogAspect.java
│   │   │   │       │
│   │   │   │       └── job/                       # 定时任务
│   │   │   │           ├── ArticleViewCountJob.java
│   │   │   │           └── AiSummaryJob.java
│   │   │   │
│   │   │   └── resources/
│   │   │       ├── mapper/                        # XML映射文件
│   │   │       ├── application.yml
│   │   │       ├── application-dev.yml
│   │   │       ├── application-prod.yml
│   │   │       └── logback-spring.xml
│   │   │
│   │   └── test/
│   │
│   ├── pom.xml
│   └── Dockerfile
│
```

---

## 五、前端项目结构

### 5.1 项目结构

```
clever-blog-frontend/
├── public/
│   ├── favicon.ico
│   └── logo.png
│
├── src/
│   ├── api/                           # API接口
│   │   ├── auth.ts
│   │   ├── user.ts
│   │   ├── article.ts
│   │   ├── dailyLog.ts
│   │   ├── category.ts
│   │   ├── tag.ts
│   │   ├── file.ts
│   │   ├── config.ts
│   │   ├── project.ts
│   │   ├── skill.ts
│   │   └── ai.ts
│   │
│   ├── assets/                        # 静态资源
│   │   ├── images/
│   │   ├── icons/
│   │   └── styles/
│   │       ├── tailwind.css
│   │       └── variables.scss
│   │
│   ├── components/                    # 公共组件
│   │   ├── common/
│   │   │   ├── AppHeader.vue
│   │   │   ├── AppFooter.vue
│   │   │   ├── AppSidebar.vue
│   │   │   ├── AppPagination.vue
│   │   │   ├── AppLoading.vue
│   │   │   └── AppEmpty.vue
│   │   │
│   │   ├── article/
│   │   │   ├── ArticleCard.vue
│   │   │   ├── ArticleList.vue
│   │   │   ├── ArticleContent.vue
│   │   │   ├── ArticleMeta.vue
│   │   │   ├── ArticleTags.vue
│   │   │   └── ArticleToc.vue
│   │   │
│   │   ├── dailyLog/
│   │   │   ├── DailyLogCard.vue
│   │   │   └── DailyLogTimeline.vue
│   │   │
│   │   ├── editor/
│   │   │   └── MarkdownEditor.vue
│   │   │
│   │   ├── project/
│   │   │   ├── ProjectCard.vue
│   │   │   └── ProjectList.vue
│   │   │
│   │   ├── skill/
│   │   │   ├── SkillItem.vue
│   │   │   └── SkillCloud.vue
│   │   │
│   │   └── search/
│   │       └── PagefindSearch.vue
│   │
│   ├── composables/
│   │   ├── useAuth.ts
│   │   ├── useArticle.ts
│   │   ├── useDailyLog.ts
│   │   ├── useConfig.ts
│   │   └── useTheme.ts
│   │
│   ├── layouts/
│   │   ├── DefaultLayout.vue
│   │   ├── AdminLayout.vue
│   │   └── BlankLayout.vue
│   │
│   ├── router/
│   │   ├── index.ts
│   │   ├── routes.ts
│   │   └── guards.ts
│   │
│   ├── stores/
│   │   ├── index.ts
│   │   ├── modules/
│   │   │   ├── user.ts
│   │   │   ├── article.ts
│   │   │   ├── dailyLog.ts
│   │   │   ├── config.ts
│   │   │   └── app.ts
│   │   └── plugins/
│   │       └── persist.ts
│   │
│   ├── styles/
│   │   ├── index.scss
│   │   ├── markdown.scss
│   │   ├── code.scss
│   │   └── element-plus.scss
│   │
│   ├── types/
│   │   ├── user.ts
│   │   ├── article.ts
│   │   ├── dailyLog.ts
│   │   └── api.ts
│   │
│   ├── utils/
│   │   ├── request.ts
│   │   ├── storage.ts
│   │   ├── format.ts
│   │   ├── validate.ts
│   │   └── markdown.ts
│   │
│   ├── views/
│   │   ├── home/
│   │   │   └── Index.vue
│   │   │
│   │   ├── article/
│   │   │   ├── List.vue
│   │   │   ├── Detail.vue
│   │   │   └── Archive.vue
│   │   │
│   │   ├── dailyLog/
│   │   │   ├── List.vue
│   │   │   └── Detail.vue
│   │   │
│   │   ├── category/
│   │   │   └── Index.vue
│   │   │
│   │   ├── tag/
│   │   │   └── Index.vue
│   │   │
│   │   ├── about/
│   │   │   └── Index.vue
│   │   │
│   │   ├── project/
│   │   │   └── Index.vue
│   │   │
│   │   ├── auth/
│   │   │   └── Login.vue
│   │   │
│   │   └── admin/
│   │       ├── Dashboard.vue
│   │       ├── article/
│   │       │   ├── List.vue
│   │       │   ├── Create.vue
│   │       │   └── Edit.vue
│   │       ├── dailyLog/
│   │       │   ├── List.vue
│   │       │   └── Create.vue
│   │       ├── category/
│   │       │   └── Index.vue
│   │       ├── tag/
│   │       │   └── Index.vue
│   │       ├── project/
│   │       │   └── Index.vue
│   │       ├── skill/
│   │       │   └── Index.vue
│   │       ├── config/
│   │       │   └── Index.vue
│   │       └── friendLink/
│   │           └── Index.vue
│   │
│   ├── App.vue
│   ├── main.ts
│   └── env.d.ts
│
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
├── tailwind.config.js
├── postcss.config.js
├── eslint.config.js
├── .prettierrc
├── .gitignore
└── README.md
```

---

## 六、AI模块设计

### 6.1 AI功能

| 功能 | 描述 | 触发方式 |
|------|------|----------|
| **智能标签** | 根据文章内容自动生成5-8个标签 | 发布文章时异步生成 |
| **文章摘要** | 自动生成200字以内摘要 | 发布文章时异步生成 |
| **内容推荐** | 基于向量相似度推荐相关文章 | 文章详情页展示 |
| **语义搜索** | 理解搜索意图，返回相关文章 | 搜索功能 |

### 6.2 AI服务实现

```java
@Service
@Slf4j
public class AiServiceImpl implements AiService {
    
    @Autowired
    private ChatClient chatClient;
    
    @Autowired
    private ArticleVectorMapper articleVectorMapper;
    
    /**
     * 生成文章标签
     */
    @Override
    @Async("taskExecutor")
    public CompletableFuture<List<String>> generateTags(Long articleId, String content) {
        try {
            String prompt = String.format(
                "请为以下文章生成5-8个标签，用逗号分隔。标签应该简洁、相关、热门。\n\n文章内容（前500字）：\n%s",
                content.substring(0, Math.min(content.length(), 500))
            );
            
            String response = chatClient.prompt(prompt)
                .options(DashScopeChatOptions.builder()
                    .withModel("qwen-turbo")
                    .withTemperature(0.3f)
                    .build())
                .call()
                .content();
            
            List<String> tags = Arrays.stream(response.split("，|,"))
                .map(String::trim)
                .filter(s -> !s.isEmpty())
                .collect(Collectors.toList());
            
            // 保存生成记录
            saveGeneration(articleId, "tags", prompt, response);
            
            return CompletableFuture.completedFuture(tags);
        } catch (Exception e) {
            log.error("生成标签失败", e);
            return CompletableFuture.completedFuture(Collections.emptyList());
        }
    }
    
    /**
     * 生成文章摘要
     */
    @Override
    @Async("taskExecutor")
    public CompletableFuture<String> generateSummary(Long articleId, String content) {
        try {
            String prompt = String.format(
                "请为以下文章生成200字以内的摘要，要求简洁明了，突出重点。\n\n文章内容（前1000字）：\n%s",
                content.substring(0, Math.min(content.length(), 1000))
            );
            
            String summary = chatClient.prompt(prompt)
                .options(DashScopeChatOptions.builder()
                    .withModel("qwen-turbo")
                    .withTemperature(0.3f)
                    .build())
                .call()
                .content();
            
            // 保存生成记录
            saveGeneration(articleId, "summary", prompt, summary);
            
            return CompletableFuture.completedFuture(summary);
        } catch (Exception e) {
            log.error("生成摘要失败", e);
            return CompletableFuture.completedFuture("");
        }
    }
    
    /**
     * 搜索相似文章
     */
    @Override
    public List<ArticleVO> searchSimilarArticles(Long articleId, int limit) {
        ArticleVector vector = articleVectorMapper.selectByArticleId(articleId);
        if (vector == null || vector.getContentVector() == null) {
            return Collections.emptyList();
        }
        
        return articleVectorMapper.findSimilarArticles(articleId, vector.getContentVector(), limit);
    }
}
```

---

## 七、开发路线图

### 7.1 阶段一：基础架构（2周）

| 周次 | 任务 | 产出 |
|------|------|------|
| 1 | 环境搭建 + 数据库设计 | 开发环境、数据库脚本 |
| 2 | 后端基础架构 + 前端基础架构 | 项目骨架、基础配置 |

### 7.2 阶段二：核心功能（4周）

| 周次 | 任务 | 产出 |
|------|------|------|
| 3 | 用户认证 + 文章管理 | 登录注册、文章CRUD |
| 4 | 分类标签 + 文章展示 | 分类管理、标签云、文章列表/详情 |
| 5 | 技术日志 + 个人展示 | 日志CRUD、关于页面、技能展示 |
| 6 | 文件上传 + 项目展示 | 图片上传、项目展示 |

### 7.3 阶段三：功能增强（2周）

| 周次 | 任务 | 产出 |
|------|------|------|
| 7 | 搜索功能 + 数据统计 | Pagefind搜索、访问量统计 |
| 8 | 性能优化 + 部署 | Redis缓存、阿里云部署 |

### 7.4 阶段四：AI集成（2周）

| 周次 | 任务 | 产出 |
|------|------|------|
| 9 | Spring AI集成 | AI服务基础 |
| 10 | 智能功能 | 标签生成、摘要生成、推荐 |

---

## 八、部署架构

### 8.1 阿里云服务器部署

```
┌─────────────────────────────────────────┐
│           阿里云ECS (2核2G3M)            │
│                                         │
│  ┌─────────────┐    ┌───────────────┐  │
│  │   Nginx     │    │  Spring Boot  │  │
│  │   :80/:443  │◄──►│  :8080        │  │
│  │  (静态资源)  │    │  (JVM 512MB)  │  │
│  └─────────────┘    └───────────────┘  │
│                              │          │
│  ┌─────────────┐    ┌───────────────┐  │
│  │  PostgreSQL │    │     Redis     │  │
│  │   :5432     │    │    :6379      │  │
│  │  (400MB)    │    │  (限制100MB)  │  │
│  └─────────────┘    └───────────────┘  │
│                                         │
└─────────────────────────────────────────┘
```

### 8.2 JVM参数

```bash
java -Xms256m -Xmx512m \
     -XX:MetaspaceSize=128m \
     -XX:MaxMetaspaceSize=256m \
     -XX:+UseG1GC \
     -XX:MaxGCPauseMillis=200 \
     -jar clever-blog.jar
```

---

## 九、总结

### 9.1 技术栈总览

| 层级 | 技术选型 |
|------|----------|
| **后端** | Spring Boot 3.5 + Java 21 + MyBatis Plus + Sa-Token + PostgreSQL + Redis |
| **前端** | Vue 3 + Vite + TypeScript + Tailwind CSS + Element Plus + Pinia |
| **AI** | Spring AI + 阿里云DashScope + pgvector |
| **部署** | 阿里云ECS 2核2G + Nginx |

### 9.2 数据库表清单（简化版）

| 表名 | 说明 |
|------|------|
| sys_user | 用户表（仅管理员） |
| sys_login_log | 登录日志 |
| sys_file | 文件表 |
| sys_config | 系统配置 |
| sys_operation_log | 操作日志 |
| article | 文章表 |
| article_draft | 草稿表 |
| **daily_log** | **技术日志表（新增）** |
| category | 分类表 |
| tag | 标签表 |
| article_tag | 文章标签关联表 |
| **project_showcase** | **项目展示表（新增）** |
| **skill** | **技能表（新增）** |
| ai_generation | AI生成记录表 |
| article_vector | 文章向量表 |

### 9.3 与完整版对比

| 功能 | 完整版 | 简化版（本方案） |
|------|--------|------------------|
| 评论系统 | ✅ | ❌ 移除 |
| 评论点赞 | ✅ | ❌ 移除 |
| 技术日志 | ❌ | ✅ 新增 |
| 项目展示 | ❌ | ✅ 新增 |
| 技能展示 | ❌ | ✅ 新增 |
| 友链管理 | ✅ | ✅ 保留 |

### 9.4 预期成果

- ✅ 简洁的个人技术博客系统
- ✅ Markdown文章编辑与代码高亮
- ✅ 技术日志（每日笔记）
- ✅ 个人展示（技能、项目）
- ✅ 全文搜索（Pagefind）
- ✅ AI智能标签与摘要
- ✅ 阿里云服务器部署
- ✅ 适合2核2G服务器的优化配置

---

**开发周期：** 10周（每周10-15小时）
**难度等级：** 中等
**学习价值：** ⭐⭐⭐⭐⭐

