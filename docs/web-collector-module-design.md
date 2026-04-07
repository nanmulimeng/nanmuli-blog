# Web Collector 模块 — 产品设计与开发方案

> **模块名称**: 网页内容采集与智能整理（Web Collector）  
> **文档版本**: v2.0  
> **创建日期**: 2026-04-07  
> **更新日期**: 2026-04-07  
> **作者**: nanmuli  
> **状态**: 方案设计阶段

### v2.0 更新记录

| 变更 | 说明 |
|------|------|
| 数据模型重构 | 单表拆分为 3 表（source + task + page），支持 1:N 多页面存储 |
| 新增订阅源管理 | `web_collect_source` 表，统一管理 URL/关键词/日报源 |
| 新增每日技术日报 | 定时爬取热点动态、开源项目、技术文章、开发工具、创意发现 |
| 新增关键词爬取 | 基于关键词搜索引擎爬取 + 多源综合整理 |
| 增强多页面爬取 | 深度爬取支持按页进度追踪 |
| 新增去重与时效性策略 | URL 指纹 + 内容哈希 + 标题相似度三级去重；源级时效窗口 |
| Python 服务扩展 | 3 端点：single / deep / search |
| 实施计划扩展 | 从 4 阶段扩展为 5 阶段 |

---

## 一、产品定义

### 1.1 一句话描述

用户提供 **URL / 关键词 / 订阅源**，系统通过 **Crawl4AI** 自动爬取网页内容，再由 **AI（DashScope/通义千问）** 智能整理输出结构化知识摘要，并支持**每日自动生成技术日报**。

### 1.2 解决谁的什么问题

| 维度 | 回答 |
|------|------|
| **目标用户** | 博客管理员（仅 1 人） |
| **核心场景** | ① 看到好文章想快速整理为笔记/素材 ② 想追踪某技术关键词的最新动态 ③ 每天自动汇总技术圈热点 |
| **当前痛点** | 手动复制→整理→提炼要 30-60 分钟；技术热点需逐个网站翻阅；无自动化信息聚合手段 |
| **期望效果** | 提交 URL → 1-2 分钟出结果；关键词搜索 → 多源综合报告；每日 8:00 自动推送技术日报 |

### 1.3 核心价值主张

**从 URL 到知识，一步到位；从碎片到日报，自动聚合。**

### 1.4 三大使用场景

```
场景 A：单页/多页采集（手动触发）
  管理员粘贴 URL → 选择单页/深度爬取 → AI 整理 → 转为文章草稿

场景 B：关键词搜索采集（手动触发）
  管理员输入关键词 "Spring AI RAG" → 搜索引擎找到 Top N 结果
  → 逐个爬取 → AI 横向对比整理 → 生成综合知识报告

场景 C：每日技术日报（定时/手动触发）
  系统每日 8:00 自动遍历已订阅的技术源 → 爬取当日新内容
  → 去重过滤 → AI 汇总生成日报 → 可选自动转为技术日志
```

---

## 二、功能设计

### 2.1 核心用户流程

```
┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│  粘贴 URL /  │   │  选择模式    │   │  查看结果    │   │  转为文章 /  │
│  输入关键词  │ → │  (可跳过)    │ → │  Markdown    │ → │  存为日志    │
│  管理订阅源  │   │              │   │  预览        │   │              │
└──────────────┘   └──────────────┘   └──────────────┘   └──────────────┘
```

### 2.2 功能清单

#### P0 — MVP 核心（必须有）

| # | 功能 | 描述 |
|---|------|------|
| F1 | **URL 提交与爬取** | 输入 URL，调用 Crawl4AI 爬取，返回 Markdown |
| F2 | **AI 内容整理** | 爬取内容送入 AI，按模板输出结构化结果（摘要+要点+标签） |
| F3 | **结果展示与预览** | 前端 Markdown 预览，Tab 切换原始/整理内容 |
| F4 | **任务状态追踪** | 异步任务全生命周期状态（排队→爬取→整理→完成/失败） |
| F5 | **历史记录** | 分页查看、按状态筛选、删除 |
| F6 | **一键转文章** | 整理结果直接创建博客文章草稿，预填标题/内容/标签/分类 |

#### P1 — 多页面 + 关键词（第二迭代）

| # | 功能 | 描述 |
|---|------|------|
| F7 | **深度爬取** | BFS 多页爬取（max_depth=2），每页独立状态追踪，汇总整理 |
| F8 | **关键词搜索爬取** | 输入关键词 → 搜索引擎找结果 → 爬取 Top N → AI 综合报告 |
| F9 | **整理模式选择** | 多种 AI 模板：技术摘要 / 教程提炼 / 对比分析 / 知识报告 / 自定义 |
| F10 | **结果在线编辑** | Markdown 编辑器修改 AI 整理结果 |
| F11 | **按页进度展示** | 深度爬取/关键词爬取时显示 `3/15 页已完成` 进度 |

#### P2 — 每日技术日报（第三迭代）

| # | 功能 | 描述 |
|---|------|------|
| F12 | **订阅源管理** | CRUD 管理订阅源（URL/关键词/RSS），配置抓取频率和 AI 模板 |
| F13 | **定时日报生成** | 按 cron 表达式自动触发，爬取订阅源当日新内容 |
| F14 | **三级去重** | URL 指纹 + 内容哈希 + 标题相似度，确保日报不重复 |
| F15 | **日报预览与发布** | 日报生成后管理员审阅，可编辑后一键转为技术日志 |
| F16 | **日报内容分类** | 按热点动态/开源项目/技术文章/开发工具/创意发现分类展示 |

#### P3 — 锦上添花（未来迭代）

| # | 功能 | 描述 |
|---|------|------|
| F17 | **向量化存储** | 爬取内容向量化存入 pgvector，语义搜索已采集知识 |
| F18 | **SSE 实时推送** | 替代轮询，任务状态变更实时推送前端 |
| F19 | **内容变更监控** | 定期重爬 URL，检测内容变化并通知 |

### 2.3 不做的事

| 不做 | 原因 |
|------|------|
| 不做通用爬虫平台 | 个人博客工具，不是 SaaS |
| 不做实时聊天交互 | 异步任务模式足够 |
| 不做内容原创性检测 | 管理员自行判断 |
| 不暴露给访客 | 仅管理员后台功能 |
| 不考虑 token 成本优化 | 个人使用量极低，月成本 < 5 元 |

### 2.4 每日技术日报 — 内容分类与推荐源

| 分类 | 说明 | 推荐订阅源 | 爬取策略 |
|------|------|-----------|----------|
| **热点动态** | 技术圈今日热议话题 | Hacker News、V2EX/hot、Reddit r/programming | 爬首页/热榜，提取标题+链接+热度 |
| **开源项目** | 新兴/趋势开源项目 | GitHub Trending（daily）、HelloGitHub | 爬 trending 页，提取项目名+描述+star 数 |
| **技术文章** | 高质量技术博文 | 掘金/推荐、dev.to/top、InfoQ/首页 | 爬列表页，提取标题+摘要+作者 |
| **开发工具** | 新工具、新服务发现 | Product Hunt/tech、ToolHunt | 爬新品列表，提取工具名+介绍+链接 |
| **创意发现** | 有趣的技术应用/想法 | 少数派/首页、36kr/tech | 爬首页，提取创意内容标题+简介 |

---

## 三、技术架构设计

### 3.1 整体架构

```
┌──────────────────────────────────────────────────────────────────┐
│                        前端 (Vue 3)                              │
│  ┌───────────┐  ┌───────────┐  ┌──────────┐  ┌──────────────┐  │
│  │ 采集表单   │  │ 任务列表   │  │ 结果预览  │  │ 订阅源管理   │  │
│  └───────────┘  └───────────┘  └──────────┘  └──────────────┘  │
├──────────────────────────────────────────────────────────────────┤
│                     后端 (Spring Boot)                           │
│                                                                  │
│  ┌─ WebCollectorController ────────────────────────────────────┐ │
│  │  任务 CRUD + 提交 + 转文章 + 转日志                         │ │
│  └─────────────────────────────────────────────────────────────┘ │
│  ┌─ CollectSourceController ───────────────────────────────────┐ │
│  │  订阅源 CRUD + 手动触发 + 启用/禁用                         │ │
│  └─────────────────────────────────────────────────────────────┘ │
│  ┌─ DigestController ─────────────────────────────────────────┐  │
│  │  手动触发日报 + 日报列表 + 日报转日志                       │  │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌─ WebCollectorAppService ────────────────────────────────────┐ │
│  │  任务编排：创建→爬取→AI整理→保存→去重检查                    │ │
│  └─────────────────────────────────────────────────────────────┘ │
│  ┌─ DigestScheduler ──────────────────────────────────────────┐  │
│  │  @Scheduled 定时扫描订阅源 → 创建日报任务 → 汇总生成        │  │
│  └─────────────────────────────────────────────────────────────┘ │
│  ┌─ DeduplicationService ─────────────────────────────────────┐  │
│  │  URL指纹 + 内容哈希 + 标题相似度 三级去重                    │  │
│  └─────────────────────────────────────────────────────────────┘ │
├──────────────────────────────────────────────────────────────────┤
│                  Python 爬虫服务 (Crawl4AI + FastAPI)             │
│  POST /crawl/single    ← 单页爬取                               │
│  POST /crawl/deep      ← BFS 深度爬取，逐页回调                  │
│  POST /crawl/search    ← 关键词搜索 → 结果列表 → 逐个爬取       │
├──────────────────────────────────────────────────────────────────┤
│                  AI 服务 (Spring AI + DashScope)                  │
│  AiContentOrganizer: 单页整理 / 多页汇总 / 日报生成              │
├──────────────────────────────────────────────────────────────────┤
│                        数据层                                    │
│  PostgreSQL: web_collect_source + web_collect_task + page        │
│  Redis: 任务状态缓存 + URL 指纹去重 + 防重复提交                 │
└──────────────────────────────────────────────────────────────────┘
```

### 3.2 核心技术选型

| 层级 | 技术 | 选型理由 |
|------|------|----------|
| **网页爬取** | Crawl4AI (Python) | LLM-First 设计；Markdown 原生输出；Playwright 动态渲染 |
| **AI 整理** | Spring AI + DashScope | pom.xml 已预留；国内可用；qwen-turbo 成本低 |
| **跨语言通信** | HTTP REST (Java → Python) | 最简跨语言方案；FastAPI 性能优秀 |
| **异步任务** | Spring @Async + DB 状态机 | 项目已有 AsyncConfig；单用户不需要 MQ |
| **定时调度** | Spring @Scheduled | 轻量；cron 表达式可配置化存入 sys_config |
| **去重存储** | Redis SET + PostgreSQL | URL 指纹用 Redis 快速判断；历史记录用 DB 持久化 |

### 3.3 AI 服务设计：独立接口，不污染原 AiService

```java
// 新增独立接口（domain/webcollector/ 下）— 不修改原 AiService
public interface AiContentOrganizer {
    /** 单页内容整理 */
    CompletableFuture<OrganizedContent> organize(String rawMarkdown, AiTemplate template);
    /** 多页/多源内容汇总整理 */
    CompletableFuture<OrganizedContent> organizeMultiple(List<PageContent> pages, AiTemplate template);
    /** 每日日报生成 */
    CompletableFuture<DigestContent> generateDigest(List<PageContent> pages, LocalDate date);
}
```

原 `AiService` 继续服务文章聚合，新接口服务 WebCollector 聚合，**职责隔离**。

---

## 四、数据模型设计

### 4.1 表关系总览

```
web_collect_source (订阅源)
  │
  │ 1:N (source_id 可选)
  ▼
web_collect_task (采集任务)
  │
  │ 1:N
  ▼
web_collect_page (爬取页面)
```

### 4.2 web_collect_source — 订阅源表

```sql
CREATE TABLE web_collect_source (
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

CREATE INDEX idx_source_active ON web_collect_source(is_active, schedule_cron) WHERE is_deleted = FALSE;
CREATE INDEX idx_source_category ON web_collect_source(content_category) WHERE is_deleted = FALSE;
```

#### 内容分类枚举

| 值 | 中文 | 典型源 |
|----|------|--------|
| `hot_trend` | 热点动态 | Hacker News, V2EX, Reddit |
| `open_source` | 开源项目 | GitHub Trending, HelloGitHub |
| `tech_article` | 技术文章 | 掘金, dev.to, InfoQ |
| `dev_tool` | 开发工具 | Product Hunt, ToolHunt |
| `creative` | 创意发现 | 少数派, 36kr/tech |

### 4.3 web_collect_task — 采集任务表

```sql
CREATE TABLE web_collect_task (
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

CREATE INDEX idx_task_status ON web_collect_task(status) WHERE is_deleted = FALSE;
CREATE INDEX idx_task_user ON web_collect_task(user_id, created_at DESC) WHERE is_deleted = FALSE;
CREATE INDEX idx_task_type ON web_collect_task(task_type, created_at DESC) WHERE is_deleted = FALSE;
CREATE INDEX idx_task_source ON web_collect_task(source_id) WHERE source_id IS NOT NULL AND is_deleted = FALSE;
```

### 4.4 web_collect_page — 爬取页面表

```sql
CREATE TABLE web_collect_page (
    id              BIGINT PRIMARY KEY,
    task_id         BIGINT NOT NULL,                -- FK → web_collect_task
    
    -- 页面信息
    url             VARCHAR(2048) NOT NULL,
    page_title      VARCHAR(500),                   -- 网页原始标题
    raw_markdown    TEXT,                            -- Crawl4AI 爬取的原始 Markdown
    page_metadata   JSONB,                          -- 元数据 { description, keywords, language, author }
    
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

CREATE INDEX idx_page_task ON web_collect_page(task_id, sort_order);
CREATE INDEX idx_page_url_hash ON web_collect_page(url_hash);
CREATE INDEX idx_page_content_hash ON web_collect_page(content_hash) WHERE content_hash IS NOT NULL;
```

### 4.5 状态机

```
任务级状态 (web_collect_task.status):

  PENDING(0) ──→ CRAWLING(1) ──→ PROCESSING(2) ──→ COMPLETED(3)
      │               │                │
      └───────────────┴────────────────┴──→ FAILED(4)

页面级状态 (web_collect_page.crawl_status):

  PENDING(0) ──→ CRAWLING(1) ──→ COMPLETED(2)
      │               │
      └───────────────┴──→ FAILED(3)
```

### 4.6 触发器

```sql
CREATE TRIGGER update_web_collect_source_updated_at
    BEFORE UPDATE ON web_collect_source
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_web_collect_task_updated_at
    BEFORE UPDATE ON web_collect_task
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

---

## 五、去重与时效性策略

### 5.1 三级去重机制

```
Level 1: URL 指纹去重（最快，Redis）
  ↓ 通过
Level 2: 内容哈希去重（爬取后，DB）
  ↓ 通过
Level 3: 标题相似度去重（AI 整理前，内存计算）
  ↓ 通过
→ 进入 AI 整理流程
```

#### Level 1 — URL 指纹去重

```
策略：SHA-256(normalize(url))
存储：Redis SET key = "collector:url_seen:{yyyy-MM}" TTL = 30天
时机：任务提交时立即检查
规则：同一 URL 30 天内不重复爬取（可配置）
标准化：去除 query 参数中的追踪参数(utm_*)、去除尾部斜杠、统一小写域名
```

#### Level 2 — 内容哈希去重

```
策略：SHA-256(normalize(content[:500]))
存储：web_collect_page.content_hash 字段 + 数据库索引
时机：每页爬取完成后、AI 整理前
规则：内容前 500 字标准化（去空白、去HTML标签、去标点）后哈希相同 → 标记为重复跳过
适用：不同 URL 指向相同内容的场景（镜像站、转载等）
```

#### Level 3 — 标题相似度去重

```
策略：Jaccard 相似度（标题分词后的词集合交并比）
阈值：相似度 > 0.75 视为重复
时机：日报生成的汇总阶段
规则：同一批日报内容中标题过于相似的条目只保留第一条
适用：多个源报道同一事件（如多家媒体报道同一开源项目发布）
```

### 5.2 时效性保障

#### 源级时效窗口

每个订阅源配置 `freshness_hours`（默认 24 小时）：
- 爬取列表页后，提取每条内容的发布时间
- 发布时间早于 `now() - freshness_hours` 的内容自动跳过
- 无法提取发布时间的内容默认保留（宁可多收不漏收）

#### 发布时间提取策略

```python
# Python 爬虫服务负责提取，按优先级尝试：
1. HTML meta 标签: <meta property="article:published_time">
2. JSON-LD 结构化数据: datePublished
3. <time> 标签的 datetime 属性
4. URL 中的日期模式: /2026/04/07/
5. 页面文本中的日期模式（正则匹配）
6. 无法提取 → published_at = NULL（保留该内容）
```

#### 日报内容新鲜度检查流程

```
遍历订阅源
  → 爬取列表页获取条目列表
  → 对每个条目：
     ① URL 指纹去重 → 重复则跳过
     ② 检查 published_at → 超出时效窗口则跳过
     ③ 爬取正文内容
     ④ 内容哈希去重 → 重复则跳过
     ⑤ 存入 web_collect_page
  → 所有源爬取完成后
  → 标题相似度去重（跨源）
  → AI 汇总生成日报
```

---

## 六、接口设计

### 6.1 采集任务接口

#### 提交采集任务

```
POST /api/admin/collector/task

Request:
{
    "taskType": "single",                    // single | deep | keyword
    "sourceUrl": "https://example.com",      // single/deep 必填
    "keyword": "Spring AI RAG",              // keyword 必填
    "searchEngine": "bing",                  // keyword 可选，默认 bing
    "crawlMode": "single",                   // single | deep
    "maxDepth": 1,                           // 1-3，deep 模式
    "maxPages": 10,                          // 1-20
    "aiTemplate": "tech_summary"             // 整理模板
}

Response (202): { "code": 200, "data": { "taskId": "19123...", "status": 0 } }
```

#### 查询任务详情

```
GET /api/admin/collector/task/{taskId}

Response: { 任务主体信息 + AI 整理结果 + 页面列表摘要 + 进度 }
```

#### 任务列表

```
GET /api/admin/collector/task/list?current=1&size=10&status=3&taskType=single
```

#### 删除任务

```
DELETE /api/admin/collector/task/{taskId}
```

#### 转为文章草稿

```
POST /api/admin/collector/task/{taskId}/to-article
Request (可选): { "title": "自定义标题", "categoryId": 123 }
Response: { "code": 200, "data": { "articleId": "19123..." } }
```

#### 转为技术日志

```
POST /api/admin/collector/task/{taskId}/to-daily-log
Request (可选): { "mood": "excited", "isPublic": true, "categoryId": 123 }
Response: { "code": 200, "data": { "dailyLogId": "19123..." } }
```

### 6.2 订阅源接口（P2 阶段）

```
POST   /api/admin/collector/source              创建订阅源
GET    /api/admin/collector/source/list          订阅源列表
PUT    /api/admin/collector/source/{id}          更新订阅源
DELETE /api/admin/collector/source/{id}          删除订阅源
POST   /api/admin/collector/source/{id}/toggle   启用/禁用
POST   /api/admin/collector/source/{id}/run      手动触发
```

### 6.3 日报接口（P2 阶段）

```
POST   /api/admin/collector/digest/generate      手动触发生成今日日报
GET    /api/admin/collector/digest/list           日报列表（按日期）
GET    /api/admin/collector/digest/{date}         查看某日日报
POST   /api/admin/collector/digest/{date}/to-daily-log  日报转为技术日志
```

### 6.4 Python 爬虫服务接口

#### 单页爬取

```
POST http://localhost:8500/crawl/single
Request: { "url": "...", "config": { ... } }
Response: {
    "success": true,
    "url": "...",
    "markdown": "...",
    "metadata": { "title", "description", "language", "published_time" },
    "links": { "internal": [...], "external": [...] },
    "word_count": 15234,
    "crawl_time_ms": 5400
}
```

#### 深度爬取

```
POST http://localhost:8500/crawl/deep
Request: { "url": "...", "max_depth": 2, "max_pages": 20, "config": { ... } }
Response: {
    "success": true,
    "pages": [
        { "url": "...", "markdown": "...", "metadata": {...}, "depth": 0 },
        { "url": "...", "markdown": "...", "metadata": {...}, "depth": 1 },
        ...
    ],
    "total_pages": 15,
    "total_crawl_time_ms": 45000
}
```

#### 关键词搜索爬取

```
POST http://localhost:8500/crawl/search
Request: {
    "keyword": "Spring AI RAG 实战",
    "engine": "bing",            // bing | duckduckgo
    "max_results": 10,
    "config": { ... }
}
Response: {
    "success": true,
    "keyword": "Spring AI RAG 实战",
    "pages": [
        { "url": "...", "markdown": "...", "metadata": {...}, "search_rank": 1 },
        ...
    ],
    "total_pages": 8,
    "total_crawl_time_ms": 60000
}
```

---

## 七、AI 整理 Prompt 设计

### 7.1 单页技术摘要（`tech_summary`）

```
你是一位资深技术内容编辑。请对以下网页内容进行深度阅读和结构化整理。

## 原始内容
{crawled_markdown}

## 输出要求（严格 JSON 格式）
{
    "title": "吸引人的中文标题（15-30字）",
    "summary": "200-300字核心摘要，概述主题、核心价值和适用场景",
    "keyPoints": ["要点1（一句话）", "要点2", ...],  // 5-10 个
    "tags": ["标签1", ...],                           // 3-8 个技术标签
    "category": "后端开发/前端开发/数据库/DevOps/AI与机器学习/安全/其他",
    "fullContent": "完整 Markdown 格式整理文章：概述→核心内容→代码示例→总结"
}

## 规则
1. 输出合法 JSON，fullContent 中代码块用 ```language 标记
2. 保留原文有价值的代码示例
3. 英文内容翻译为中文，保留专有名词原文
4. 标签是技术关键词，不要太泛也不要太窄
```

### 7.2 多源知识报告（`knowledge_report`，关键词爬取用）

```
你是一位技术研究专家。以下是围绕关键词「{keyword}」从多个来源收集的内容。
请进行横向对比分析，生成综合知识报告。

## 来源内容
{各页面内容，标注来源 URL}

## 输出要求（严格 JSON 格式）
{
    "title": "关于「{keyword}」的综合技术报告",
    "summary": "300-500字综合概述",
    "keyPoints": ["共识要点", "争议/差异点", ...],
    "comparison": "对比表格（Markdown 格式，如有多个方案/工具）",
    "tags": [...],
    "fullContent": "完整报告：背景→各方观点→对比分析→最佳实践→结论"
}
```

### 7.3 每日技术日报（`daily_digest`）

```
你是一位技术媒体编辑，负责编写每日技术日报。
以下是 {date} 从各个技术源收集的今日新鲜内容。

## 今日收集内容

### 热点动态
{hot_trend_items}

### 开源项目
{open_source_items}

### 技术文章
{tech_article_items}

### 开发工具
{dev_tool_items}

### 创意发现
{creative_items}

## 输出要求（严格 JSON 格式）
{
    "title": "技术日报 {date}：{一句话概括今日亮点}",
    "summary": "100-150字今日概览",
    "sections": [
        {
            "category": "hot_trend",
            "categoryName": "🔥 热点动态",
            "items": [
                {
                    "title": "条目标题",
                    "oneLiner": "一句话速览（≤50字）",
                    "sourceUrl": "原文链接",
                    "sourceName": "来源名"
                }
            ]
        },
        // ... 其他分类
    ],
    "highlight": "今日最值得关注的 1 条内容及推荐理由（100字）",
    "tags": ["今日关键词标签"],
    "fullContent": "完整日报 Markdown，适合直接发布为博客日志"
}

## 日报编写规则
1. 每个分类精选 3-5 条最有价值的内容，不要全部罗列
2. 每条必须有一句话速览，让读者 3 秒判断是否感兴趣
3. 语言风格：简洁、专业、有态度，偶尔带点幽默
4. 去除广告性质、水文、低质量内容
5. 如果某分类今日无新鲜内容，该分类可以省略
6. highlight 选择今天最有启发性/影响力最大的一条
```

### 7.4 教程提炼（`tutorial`）

```
你是一位技术教育专家。请将以下内容整理为 step-by-step 教程。

重点：循序渐进的学习路径、每步配代码和预期结果、常见坑和注意事项、快速开始和完整示例。

（输出格式同 tech_summary）
```

### 7.5 对比分析（`comparison`）

```
你是一位技术选型顾问。请对以下内容进行分析，提取技术方案对比信息。

输出包含：技术方案概述、对比表格（功能/性能/成本/适用场景）、推荐场景、注意事项。

（输出格式同 tech_summary）
```

---

## 八、DDD 分层实现计划

### 8.1 后端新增文件清单

```
com.nanmuli.blog
├── domain/webcollector/                            # 领域层
│   ├── WebCollectTask.java                         # 任务聚合根
│   ├── WebCollectPage.java                         # 页面实体（属于 Task 聚合）
│   ├── WebCollectSource.java                       # 订阅源聚合根
│   ├── CollectTaskStatus.java                      # 任务状态枚举
│   ├── PageCrawlStatus.java                        # 页面爬取状态枚举
│   ├── CollectTaskType.java                        # 任务类型枚举 single/deep/keyword/digest
│   ├── SourceType.java                             # 源类型枚举 url/keyword/rss
│   ├── ContentCategory.java                        # 内容分类枚举
│   ├── AiTemplate.java                             # AI 模板枚举
│   ├── AiContentOrganizer.java                     # AI 整理接口（领域层定义）
│   ├── WebCollectTaskRepository.java               # 任务仓储接口
│   ├── WebCollectPageRepository.java               # 页面仓储接口
│   └── WebCollectSourceRepository.java             # 订阅源仓储接口
│
├── application/webcollector/                       # 应用层
│   ├── WebCollectorAppService.java                 # 核心编排（爬取+整理+保存）
│   ├── DigestAppService.java                       # 日报生成编排
│   ├── CollectSourceAppService.java                # 订阅源管理
│   ├── command/
│   │   ├── CreateCollectTaskCommand.java            # 创建任务
│   │   ├── CreateCollectSourceCommand.java          # 创建订阅源
│   │   ├── ConvertToArticleCommand.java             # 转文章
│   │   └── ConvertToDailyLogCommand.java            # 转日志
│   ├── query/
│   │   ├── CollectTaskPageQuery.java                # 任务分页查询
│   │   └── CollectSourcePageQuery.java              # 订阅源分页查询
│   └── dto/
│       ├── CollectTaskDTO.java                      # 任务详情
│       ├── CollectTaskListDTO.java                  # 任务列表（不含大文本）
│       ├── CollectPageDTO.java                      # 页面详情
│       ├── CollectSourceDTO.java                    # 订阅源详情
│       └── DigestDTO.java                           # 日报详情
│
├── interfaces/rest/
│   ├── WebCollectorController.java                 # 任务 REST 接口
│   ├── CollectSourceController.java                # 订阅源 REST 接口
│   └── DigestController.java                       # 日报 REST 接口
│
├── infrastructure/
│   ├── persistence/webcollector/
│   │   ├── WebCollectTaskMapper.java
│   │   ├── WebCollectTaskRepositoryImpl.java
│   │   ├── WebCollectPageMapper.java
│   │   ├── WebCollectPageRepositoryImpl.java
│   │   ├── WebCollectSourceMapper.java
│   │   └── WebCollectSourceRepositoryImpl.java
│   ├── crawler/
│   │   ├── CrawlerService.java                     # 爬虫调用接口
│   │   ├── Crawl4AiCrawlerService.java             # Crawl4AI HTTP 实现
│   │   └── CrawlResult.java                        # 爬取结果 DTO
│   ├── ai/
│   │   └── DashScopeContentOrganizer.java          # AiContentOrganizer 实现
│   ├── dedup/
│   │   └── DeduplicationService.java               # 三级去重服务
│   └── scheduler/
│       └── DigestScheduler.java                    # 日报定时调度
```

### 8.2 Python 爬虫服务文件

```
crawler-service/                        # 项目根目录下
├── requirements.txt                    # crawl4ai, fastapi, uvicorn, beautifulsoup4
├── main.py                             # FastAPI 入口，3 个路由
├── crawler/
│   ├── __init__.py
│   ├── single.py                       # 单页爬取逻辑
│   ├── deep.py                         # 深度爬取逻辑（BFS）
│   ├── search.py                       # 关键词搜索爬取逻辑
│   ├── config.py                       # 共享配置（BrowserConfig/RunConfig）
│   └── metadata.py                     # 发布时间提取工具
├── Dockerfile
└── README.md
```

### 8.3 前端新增文件

```
frontend/src/
├── api/collector.ts                    # 采集任务 API
├── api/collectSource.ts                # 订阅源 API（P2）
├── types/collector.ts                  # TypeScript 类型
├── views/admin/collector/
│   ├── TaskList.vue                    # 任务列表页
│   ├── TaskDetail.vue                  # 任务详情/结果页
│   ├── SourceList.vue                  # 订阅源管理页（P2）
│   └── DigestView.vue                  # 日报查看页（P2）
└── composables/useCollectorPolling.ts  # 任务状态轮询
```

---

## 九、实施步骤（分阶段）

### Phase 1：基础管道（预计 2-3 天）

> **目标**：URL 进去 → Markdown 出来 → 存入数据库

| Step | 任务 | 产出 |
|------|------|------|
| 1.1 | 创建 3 张数据库表（source + task + page） | SQL DDL |
| 1.2 | 搭建 Python 爬虫服务，实现 `POST /crawl/single` | crawler-service/ |
| 1.3 | 领域层：Task + Page 实体 + 状态枚举 + Repository 接口 | domain/ |
| 1.4 | 基础设施层：Mapper + RepositoryImpl + CrawlerService HTTP 调用 | infrastructure/ |
| 1.5 | 应用服务：创建任务 → 异步爬取 → 存储页面 → 更新状态 | WebCollectorAppService |
| 1.6 | Controller：提交任务 + 查询状态 + 任务列表 + 删除 | REST API |

**验证**：Knife4j 提交 URL，数据库 task 状态变为 COMPLETED，page 表有 Markdown 内容。

### Phase 2：AI 整理 + 转文章（预计 2-3 天）

> **目标**：爬取的 Markdown → AI 整理 → 结构化输出 → 可转为文章

| Step | 任务 | 产出 |
|------|------|------|
| 2.1 | 取消 pom.xml 中 Spring AI DashScope 注释 | 依赖可用 |
| 2.2 | 配置 DashScope API Key | application-dev.yml |
| 2.3 | 实现 DashScopeContentOrganizer（Prompt + JSON 解析） | AI 整理服务 |
| 2.4 | 串联爬取→AI 整理→保存结果 | 完整管道 |
| 2.5 | 实现"转为文章草稿"（复用 ArticleAppService.create） | 转文章接口 |
| 2.6 | 错误处理：AI 超时/JSON 异常/token 超限 fallback | 健壮性 |

**验证**：提交 URL 后，task 表 ai_summary/ai_tags 等字段有内容；可转为文章草稿。

### Phase 3：前端界面（预计 2-3 天）

> **目标**：后台可视化操作

| Step | 任务 | 产出 |
|------|------|------|
| 3.1 | 新增路由 + 侧边栏菜单项"内容采集" | 路由配置 |
| 3.2 | api/collector.ts + types/collector.ts | API 层 |
| 3.3 | TaskList.vue：表格 + 状态标签 + 提交弹窗 + 筛选 | 列表页 |
| 3.4 | TaskDetail.vue：原始/AI 整理 Tab + Markdown 预览 + 进度条 | 详情页 |
| 3.5 | 状态轮询：未完成任务 5 秒自动刷新 | 体验优化 |
| 3.6 | "转文章"/"转日志"按钮 | 闭环 |

**验证**：前端提交 URL → 看到进度 → 查看 AI 结果 → 一键转文章/日志。

### Phase 4：多页面 + 关键词爬取（预计 3-4 天）

> **目标**：深度爬取 + 关键词搜索 + 多页进度追踪

| Step | 任务 | 产出 |
|------|------|------|
| 4.1 | Python: 实现 `POST /crawl/deep`（BFS 深度爬取） | 深度爬取端点 |
| 4.2 | Python: 实现 `POST /crawl/search`（关键词搜索） | 搜索爬取端点 |
| 4.3 | 后端：支持 deep/keyword 任务类型，逐页存储+进度更新 | 多页编排 |
| 4.4 | AI：多页汇总 Prompt（knowledge_report 模板） | 多源整理 |
| 4.5 | 前端：任务类型选择 + 进度条 `3/15` + 整理模式选择 | UI 增强 |
| 4.6 | 去重：实现 Level 1（URL 指纹）+ Level 2（内容哈希） | 去重服务 |

**验证**：提交深度爬取任务，多页独立追踪；关键词搜索返回综合报告；重复 URL 被正确拦截。

### Phase 5：每日技术日报（预计 3-4 天）

> **目标**：订阅源管理 + 定时爬取 + 日报生成 + 去重

| Step | 任务 | 产出 |
|------|------|------|
| 5.1 | 新增 `@EnableScheduling` + DigestScheduler | 定时调度 |
| 5.2 | 订阅源 CRUD（CollectSourceAppService + Controller） | 源管理 |
| 5.3 | 日报生成流程：扫描源→创建 digest 任务→爬取→去重→AI 汇总 | 日报管道 |
| 5.4 | 实现 Level 3 去重（标题 Jaccard 相似度） | 完整去重 |
| 5.5 | 日报转技术日志（复用 DailyLogAppService.create） | 转日志 |
| 5.6 | 前端：SourceList.vue + DigestView.vue | 日报 UI |
| 5.7 | 预置推荐订阅源（HN/GitHub Trending/掘金等） | 开箱即用 |

**验证**：配置订阅源 → 手动触发日报 → 生成分类日报内容 → 无重复 → 转为技术日志。

---

## 十、异常场景设计

| 场景 | 处理策略 | 用户看到什么 |
|------|----------|------------|
| URL 不可达 | 爬虫返回 error → FAILED | "网页无法访问：HTTP 404"，可重试 |
| 网页需要登录 | 爬虫返回空内容 | "此网页需要登录，暂不支持" |
| 爬取超时（>60s） | Python page_timeout + Java HTTP 超时 | "爬取超时，请稍后重试" |
| 内容为空 | word_count < 50 视为空 | "未提取到有效内容" |
| AI 返回非 JSON | 重试 1 次带严格格式提示；仍失败保留原文 | "AI 整理失败，可查看原始内容" |
| AI 超时（>120s） | 保留爬取结果，整理标记失败 | "AI 整理超时，可重试整理" |
| Python 服务不可用 | HTTP 连接失败 → FAILED | "爬虫服务未启动" |
| 搜索引擎反爬 | 降级 Bing→DuckDuckGo；仍失败→FAILED | "搜索服务暂时受限" |
| 深度爬取部分页面失败 | 单页标记 FAILED，其他页继续；有足够页面仍整理 | "15 页中 2 页失败，已基于 13 页生成报告" |
| 日报源全部爬取失败 | 标记该源 last_run_status=failed | "今日日报：XX 源爬取失败" |
| 重复内容检测 | 跳过重复页，日志记录 | 日报中不出现重复条目 |

---

## 十一、风险评估

| 风险 | 概率 | 影响 | 缓解方案 |
|------|------|------|----------|
| 目标网站反爬 | 中 | 中 | enable_stealth + text_mode；失败提示用户 |
| DashScope API 不稳定 | 低 | 中 | 重试 1 次；失败保留原文 |
| Python 服务崩溃 | 低 | 高 | Docker restart=always；Java 超时保护 |
| 2G 服务器内存不足 | 中 | 高 | text_mode + light_mode；限并发为 1；max_pages ≤ 10 |
| 搜索引擎封 IP | 中 | 中 | 限频 + 降级策略；关键词爬取标记为 beta 功能 |
| 日报源网站改版 | 中 | 低 | css_selector 可配置；管理员手动调整 |
| 爬取内容版权 | 中 | 低 | 仅个人学习；注明来源；不公开原文 |

---

## 十二、开发环境准备

### 12.1 Python 环境

```bash
cd nanmuli-blog
python -m venv crawler-service/.venv
cd crawler-service
pip install crawl4ai fastapi uvicorn[standard] beautifulsoup4
crawl4ai-setup
crawl4ai-doctor
uvicorn main:app --host 0.0.0.0 --port 8500 --reload
```

### 12.2 Spring AI 依赖

```xml
<!-- pom.xml: 取消注释 -->
<dependency>
    <groupId>org.springframework.ai</groupId>
    <artifactId>spring-ai-dashscope-spring-boot-starter</artifactId>
    <version>1.0.0-M6</version>
</dependency>
```

### 12.3 配置项追加

```yaml
# application-dev.yml
spring:
  ai:
    dashscope:
      api-key: ${AI_DASHSCOPE_KEY:sk-xxx}
      chat:
        options:
          model: qwen-turbo
          temperature: 0.3

# 爬虫服务
crawler:
  service:
    base-url: http://localhost:8500
    timeout: 60000

# 日报调度
collector:
  digest:
    enabled: true
    cron: "0 0 8 * * ?"            # 每日 8:00
    default-freshness-hours: 24    # 默认时效窗口
  dedup:
    url-ttl-days: 30               # URL 指纹保留天数
    title-similarity-threshold: 0.75
```

### 12.4 定时调度基础设施

```java
// 新增文件：infrastructure/config/scheduler/SchedulingConfig.java
@Configuration
@EnableScheduling
public class SchedulingConfig {
    // 启用 Spring 调度能力
}
```

### 12.5 线程池调整建议

```java
// AsyncConfig.java — 建议新增爬虫专用执行器
@Bean(name = "crawlerTaskExecutor")
public Executor crawlerTaskExecutor() {
    ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
    executor.setCorePoolSize(1);    // 2G 服务器限制并发
    executor.setMaxPoolSize(2);
    executor.setQueueCapacity(20);
    executor.setThreadNamePrefix("crawler-");
    executor.setRejectedExecutionHandler(new ThreadPoolExecutor.CallerRunsPolicy());
    executor.setWaitForTasksToCompleteOnShutdown(true);
    executor.setAwaitTerminationSeconds(120);
    executor.initialize();
    return executor;
}
```

---

## 十三、验收标准

### Phase 1-3 验收（MVP）

- [ ] 管理员侧边栏可见"内容采集"入口
- [ ] 提交 URL 后，状态依次：排队 → 爬取 → 整理 → 完成
- [ ] 完成后可查看：AI 标题/摘要/要点/标签/完整内容
- [ ] 可切换查看原始 Markdown
- [ ] "转文章"创建草稿，跳转编辑页内容已预填
- [ ] 无效 URL 有明确错误提示
- [ ] Python 服务未启动时有友好提示
- [ ] 单页爬取 + AI 整理总耗时 < 2 分钟

### Phase 4 验收（多页 + 关键词）

- [ ] 深度爬取显示进度 `3/15`，多页内容各自存储
- [ ] 关键词搜索返回多源综合报告
- [ ] 重复 URL 30 天内被正确拦截
- [ ] 内容哈希去重有效（不同 URL 相同内容被识别）

### Phase 5 验收（日报）

- [ ] 可创建/编辑/删除/启用/禁用订阅源
- [ ] 手动触发日报生成成功
- [ ] 日报按 5 大分类展示，每分类 3-5 条精选
- [ ] 同一内容不在日报中重复出现
- [ ] 超出时效窗口的旧内容被过滤
- [ ] 日报可一键转为技术日志
- [ ] 定时任务每日 8:00 自动触发（可在 sys_config 修改 cron）

---

## 附录 A：Crawl4AI 推荐配置

```python
# 个人博客场景（2G 服务器优化）
browser_config = BrowserConfig(
    headless=True,
    browser_type="chromium",
    text_mode=True,         # 不加载图片
    light_mode=True,        # 轻量模式
    java_script_enabled=True,
    viewport_width=1920,
    viewport_height=1080,
)

run_config = CrawlerRunConfig(
    cache_mode=CacheMode.BYPASS,
    word_count_threshold=10,
    excluded_tags=["nav", "footer", "aside", "header", "script", "style"],
    remove_overlay_elements=True,
    remove_forms=True,
    exclude_external_links=False,
    wait_until="networkidle",
    page_timeout=30000,
    markdown_generator=DefaultMarkdownGenerator(
        content_filter=PruningContentFilter(threshold=0.48, threshold_type="fixed")
    ),
)
```

## 附录 B：深度爬取配置

```python
from crawl4ai.deep_crawling import BFSDeepCrawlStrategy
from crawl4ai.deep_crawling.filters import FilterChain, DomainFilter

deep_config = CrawlerRunConfig(
    deep_crawl_strategy=BFSDeepCrawlStrategy(
        max_depth=2,
        max_pages=10,           # 2G 服务器限制
        include_external=False,
        filter_chain=FilterChain([
            DomainFilter(allowed_domains=["目标域名"]),
        ]),
    ),
)
```

## 附录 C：预置订阅源清单

| 源名称 | type | value | content_category | freshness_hours | schedule_cron |
|--------|------|-------|-----------------|-----------------|---------------|
| Hacker News 热榜 | url | https://news.ycombinator.com | hot_trend | 24 | 0 0 8 * * ? |
| GitHub Trending (Daily) | url | https://github.com/trending?since=daily | open_source | 24 | 0 0 8 * * ? |
| 掘金热门 | url | https://juejin.cn/hot/articles | tech_article | 24 | 0 0 8 * * ? |
| Product Hunt Tech | url | https://www.producthunt.com/topics/developer-tools | dev_tool | 48 | 0 0 8 * * ? |
| HelloGitHub 月刊 | url | https://hellogithub.com | open_source | 720 | 0 0 8 1 * ? |

> **注意**：以上源的实际 CSS 选择器和爬取策略需在实施时根据页面结构调整。

## 附录 D：日报 Markdown 输出示例

```markdown
# 🗞️ 技术日报 2026-04-07：Spring AI 1.1 正式发布

> 今日概览：Spring AI 迎来重大更新；Rust 编译器性能提升 30%；一款新的终端文件管理器引发关注。

## 🔥 热点动态

- **Spring AI 1.1 正式发布，全面支持 Tool Calling**
  → 重写了函数调用机制，新增 MCP 协议支持。[来源: Hacker News](...)

- **Rust 1.85 编译速度提升 30%**
  → 新的增量编译策略大幅缩短大型项目编译时间。[来源: Reddit](...)

## 🌟 开源项目

- **yazi：Rust 编写的终端文件管理器**（⭐ 2.3k）
  → 速度极快，支持图片预览和插件系统。[GitHub](...)

## 📖 技术文章

- **RAG 系统的 10 个常见陷阱及解决方案**
  → 从 chunking 策略到 reranking，实战经验总结。[来源: 掘金](...)

## 🔧 开发工具

- **Cursor 0.40：AI 代码编辑器重大更新**
  → 新增多文件编辑和 Agent 模式。[Product Hunt](...)

---
*由 Web Collector AI 自动生成 | 共处理 5 个源，筛选 12 条内容*
```
