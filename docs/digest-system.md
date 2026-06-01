# 日报系统完整技术文档

> 最后更新：2026-06-01
> 覆盖范围：Python 爬虫服务 + Java 后端 + Vue 前端
> 当前状态：MVP Beta 试用版，可初步上线使用

---

## 一、系统概述

日报系统是博客项目中一个自动化的技术资讯聚合模块，每日定时（或手动触发）从多种来源（搜索引擎、URL、RSS Feed）爬取技术内容，经 OpenAI 兼容 AI 模型整理为结构化技术日报，包含分类章节、条目摘要和亮点推荐。当前试用环境使用 `deepseek-v4-pro`。

### 1.0 MVP Beta 基线（2026-06-01）

当前版本已经具备试用版上线能力：

| 能力 | 状态 | 说明 |
|------|------|------|
| 后台手动生成日报 | ✅ 已通过 | 管理端可触发强制生成，并查看任务详情 |
| 工作日定时生成 | ✅ 已启用 | scheduler cron: `0 8 * * 1-5` |
| 公开日报展示 | ✅ 已通过 | `/api/digest/latest` 可返回最新日报 |
| 多来源采集 | ✅ 已通过 | 支持 keyword/url/rss/mixed section |
| 结构化日报保存 | ✅ 已通过 | 保存 `digest_section` 与 `digest_item` |
| 自动优化评估 | ✅ 已接入 | 保存 `digest_final_eval`，可查询趋势 |
| 历史质量反馈 | ✅ 初步可用 | 计划阶段读取趋势和历史弱点 |
| 独立服务调用 | ✅ 已具备 | `crawler-service` 可被博客或其他服务通过 HTTP/API Key 调用 |

最近一次真实任务：`task_id=71`，日期 `2026-06-01`，状态 `COMPLETED(3)`，采集 `21` 页，AI 耗时约 `68s`，生成 3 个 section、8 个条目。最新质量评估 `overall_score=0.896`，结构化输出评分 `0.981`。

试用版仍需继续优化的问题：

- `open_source` 板块仍可能出现多个条目共用 `https://github.com/trending` 的来源 URL，需要 repo 级 URL 展开。
- `tech_article` 原始候选池可能混入泛化定义页，需要增强通用内容惩罚和站点白名单。
- 自动优化已能评估和记录，但对下一轮采集策略的强制纠偏还不够。
- 已完成任务的进度展示应统一归一为 `100%`，避免 `COMPLETED` 但 `progress_percent=95` 的观感问题。

### 1.1 三层架构

```
┌──────────────┐     HTTP/REST      ┌──────────────┐     HTTP/Callback    ┌──────────────┐
│   Vue 前端    │ ──────────────────→ │  Java 后端    │ ←────────────────── │ Python 爬虫   │
│  (Vue3+EP)   │ ←────────────────── │ (Spring Boot) │ ──────────────────→ │  (FastAPI)   │
└──────────────┘     JSON/Proxy      └──────────────┘     Task+Callback   └──────────────┘
      │                                    │                                      │
      │  轮询(5s)                          │  PostgreSQL                         │  SQLite
      └── status polling                   │  任务/指纹/来源/可信度                │  任务/页面/章节
```

**职责分工**：

| 层 | 职责 |
|---|------|
| **Python 爬虫服务** | 任务执行引擎（爬取 + AI整理 + 优化）、日报数据存储、调度器 |
| **Java 后端** | 配置中心、来源管理、可信度数据、指纹持久化、REST API 网关（代理日报请求） |
| **Vue 前端** | 日报展示、状态轮询、手动触发生成 |

### 1.2 双模式运行

Python 爬虫服务有两种运行模式：
- **API-only 模式**：仅提供爬取 API，由 Java 后端调用（无调度、无日报功能）
- **Standalone 模式**：完整的任务管理 + 日报调度 + 信息源调度（`settings.standalone=True`）

日报功能**仅在 Standalone 模式**下可用。

---

## 二、核心数据结构

### 2.1 Python 端数据类

#### 日报页面内容（输入 AI）

```python
# crawler-service/ai/organizer.py:274-281
@dataclass
class DigestPageContent:
    url: str = ""
    title: str = ""
    markdown: str = ""
    summary: str = ""           # 正文首段提取
    category: str = ""          # infer_category() 推断
    source_name: str = ""       # metadata.source_name > 域名解析
    source_level: str = ""      # official / high / medium / spam
```

#### 日报结构化输出（AI 输出）

```python
# crawler-service/ai/organizer.py:284-309
@dataclass
class DigestSection:
    category: str = ""          # hot_trend / open_source / tech_article / dev_tool / paper / creative
    category_name: str = ""     # 热点动态 / 开源项目 / ...
    emoji: str = ""             # 🔥 / 🌟 / 📖 / ...
    items: list[DigestItem] = field(default_factory=list)

@dataclass
class DigestItem:
    title: str = ""
    one_liner: str = ""         # 一句话核心信息
    source_url: str = ""        # 原文链接
    source_name: str = ""       # 来源名

@dataclass
class DigestContent:
    title: str = ""
    summary: str = ""
    sections: list[DigestSection] = field(default_factory=list)
    highlight: str = ""         # 今日亮点
    tags: list[str] = field(default_factory=list)
    full_content: str = ""      # 完整 Markdown
    tokens_used: int = 0
    duration_ms: int = 0
```

#### 分类体系

```python
DIGEST_CATEGORY_MAP = {
    "hot_trend":    ("热点动态", "🔥"),
    "open_source":  ("开源项目", "🌟"),
    "tech_article": ("技术文章", "📖"),
    "dev_tool":     ("开发工具", "🔧"),
    "creative":     ("创意发现", "💡"),
    "paper":        ("学术论文", "📄"),
}

_DIGEST_CATEGORY_ORDER = ["hot_trend", "open_source", "tech_article", "dev_tool", "paper", "creative"]
```

### 2.2 SQLite 表结构

```sql
-- 日报任务（crawl_task 的子集，task_type='digest'）
crawl_task (
    id, task_type, keyword, ai_template, status, error_message,
    total_pages, completed_pages, crawl_duration, total_word_count,
    ai_title, ai_summary, ai_key_points, ai_tags, ai_category,
    ai_full_content, ai_duration, ai_tokens_used, ai_error_message,
    ai_search_metadata,
    digest_date,           -- 日报专属：日期字符串 (YYYY-MM-DD)
    digest_highlight,      -- 日报专属：今日亮点
    time_range, created_at, updated_at
)

-- 日报结构化章节
digest_section (
    id, task_id,           -- FK → crawl_task(id) ON DELETE CASCADE
    category,              -- hot_trend / open_source / ...
    category_name,         -- 热点动态 / ...
    emoji,                 -- 🔥 / ...
    sort_order,
    created_at
)

-- 日报条目
digest_item (
    id, section_id,        -- FK → digest_section(id) ON DELETE CASCADE
    title,                 -- 事件标题
    one_liner,             -- 一句话核心信息
    source_url,            -- 原文链接
    source_name,           -- 来源域名
    page_id,               -- 可选，关联 crawl_page
    sort_order,
    created_at
)

-- 优化记录（日报和关键词任务共用）
optimization_record (
    id, task_id, round_num,
    angle_coverage, source_diversity, depth_coverage,
    temporal_coverage, perspective_balance, language_coverage,
    overall_score,
    search_keyword, search_engine, time_range,
    strategy_type, strategy_detail,
    weaknesses (JSON), suggestions (JSON),
    urls_before, urls_after, score_delta,
    created_at
)
```

### 2.3 PostgreSQL 表结构（Java 端）

```sql
-- 来源可信度评分
source_authority (
    id, domain, score, level,  -- official(95) / high(80) / medium(60)
    is_active, is_deleted, created_at, updated_at
)

-- 日报指纹（跨日去重）
digest_fingerprint (
    id, task_id, url_hash,     -- SHA-256，UNIQUE(url_hash, digest_date) ON CONFLICT DO NOTHING
    url, title, simhash,       -- SimHash 长整型
    digest_date,               -- LocalDate
    is_deleted, created_at
)

-- 信息源（Section 配置来源）
web_collect_source (
    id, name, type,            -- keyword / url / rss
    value,                     -- 关键词 / URL / Feed URL
    content_category,          -- hot_trend / open_source / ...
    crawl_mode, max_depth, max_pages,
    css_selector, ai_template, schedule_cron,
    freshness_hours, is_active,
    last_run_at, last_run_status,
    run_count, success_count, fail_count,
    avg_quality_score,         -- EMA(α=0.3) 质量分
    last_result_count, last_error,
    user_id, version           -- 乐观锁
)
```

---

## 三、任务生命周期

### 3.1 状态机（5态）

```
PENDING(0) → CRAWLING(1) → PROCESSING(2) → COMPLETED(3)
                 │               │
                 └───────────────→ FAILED(4)
```

- `isTerminal()`: COMPLETED(3) 或 FAILED(4)
- 终态不可逆转：`updateStatus()` 强制只进不退

### 3.2 完整时序

```
触发(scheduler/routes)
    │
    ▼
[1] 防重复检查（SQL原子检查：今日非FAILED记录是否存在）
    │
    ▼
[2] 创建 SQLite 任务（PENDING, task_type='digest'）
    │
    ▼
[3] executor.submit(task_id)
    │  └─ Semaphore(3) 控制全局并发
    │  └─ task_scoped_db() 整个任务复用连接
    │
    ▼
[4] status → CRAWLING
    │
    ▼
[5] DigestOrchestrator.run() / execute_digest_crawl()
    │  ├─ 获取 Section 配置（Java API → 本地 JSON fallback）
    │  ├─ 深拷贝配置快照（防执行中修改）
    │  ├─ 构建历史去重引擎（Java指纹 → 本地SQLite fallback）
    │  ├─ 多 Section 并行爬取（Semaphore=2）
    │  │   ├─ keyword: 拆分 OR 关键词 → 搜索引擎搜索
    │  │   ├─ url: 跳过死源 → single/deep 爬取
    │  │   └─ rss: parse_feed → freshness过滤 → 逐篇爬取
    │  ├─ URL规范化去重 + SimHash内容去重（跨板块）
    │  ├─ 全局超时保护（600s，超时返回部分结果）
    │  ├─ [可选] 自动优化（广度→深度，需4个开关同时启用）
    │  └─ 保存指纹到 Java PostgreSQL
    │
    ▼
[6] 质量过滤（日报独立阈值：spam直接拒绝，min_content=50）
    │
    ▼
[7] 保存爬取结果到 SQLite crawl_page
    │
    ▼
[8] status → PROCESSING
    │
    ▼
[9] AI 整理（organize_digest_and_save）
    │  ├─ 构建 DigestPageContent（分类推断+来源可信度+摘要提取）
    │  ├─ 获取最近3条highlight（AI多样性防护）
    │  ├─ 构建 Prompt（分类均分Token预算，可信度排序，超量仅发summary）
    │  ├─ 调用 OpenAI 兼容 AI 模型（当前试用环境：deepseek-v4-pro，max_tokens=16K）
    │  ├─ 解析 JSON → 5层验证（必填/长度/分类/URL去重/URL合法性）
    │  ├─ 保存到 SQLite digest_section + digest_item
    │  └─ 失败重试：Truncated→1.5x tokens，RateLimit→指数退避
    │
    ▼
[10] status → COMPLETED
    │
    ▼
[11] Callback 通知 Java（POST /api/internal/collector/callback）
    │  └─ 指数退避重试3次，4xx不重试
    │
    ▼
[12] Java 同步 Python 数据到 PostgreSQL
    │  ├─ handleCallback() → findByPythonTaskId()
    │  ├─ syncFromPythonSilent() → GET /api/v1/tasks/{id}
    │  ├─ updateTaskFromPython() → 映射所有字段
    │  └─ 乐观锁冲突视为正常（并发同步先到先赢）
    │
    ▼
[13] Java Reconciliation 定时器（10分钟轮询超时任务）
```

---

## 四、Section 配置体系

### 4.1 配置获取

```python
# task_executor.py:894-924
async def get_digest_sections() -> list[dict]:
    # 1. 优先从 Java API: GET /api/internal/collector/sources
    #    → _sources_to_sections() 转换
    # 2. 回退到本地: settings.digest_sections (JSON字符串)
```

### 4.2 来源转换逻辑

Java 的 `WebCollectSource` 按 `contentCategory` 分组，同分类多源合并：

```
Source(type=keyword, category=hot_trend, value="AI OR 人工智能")
Source(type=url,     category=hot_trend, value="https://news.ycombinator.com")
                                ↓
Section(name="hot_trend", source_type="mixed",
        keyword="AI OR 人工智能",
        url_sources=[{url, crawl_mode, max_depth, ...}])
```

**source_type 推断规则**：
- 有2种以上来源类型 → `mixed`
- 仅 keyword → `keyword`
- 仅 url → `url`
- 仅 rss → `rss`

### 4.3 效能数据聚合

```python
# task_executor.py:1021-1038
def _compute_section_effectiveness(group: dict) -> dict:
    # 从 url_sources + rss_sources 聚合
    return {
        "avg_quality": float,    # 非零质量分的均值
        "success_rate": float,   # success / (success + fail)
        "total_runs": int,       # success + fail
        "dead": bool,            # success_rate < 0.2 且 total_runs >= 3
    }
```

死源（`dead=True`）在爬取时被跳过（`_crawl_url_sources` 和 `_crawl_rss_sources` 中检查）。

### 4.4 freshness → time_range 映射

```python
def _freshness_to_time_range(hours: int) -> str:
    if hours <= 24:   return "day"
    if hours <= 168:  return "week"     # 7天
    if hours <= 720:  return "month"    # 30天
    return "year"
```

---

## 五、爬取引擎

### 5.1 关键词搜索（keyword / mixed 类型）

[digest.py:82-100](crawler-service/crawler/digest.py#L82-L100)

```python
kw_list = [kw.strip() for kw in kw_raw.split(" OR ") if kw.strip()]
per_kw_max = max(3, section["max_items"] * digest_section_result_multiplier // len(kw_list))
for kw in kw_list:
    results = await crawl_by_keyword(keyword=kw, engine=engine, max_results=per_kw_max, ...)
    await asyncio.sleep(1)  # 关键词间延迟
```

- OR 合并的关键词拆分为独立搜索
- `per_kw_max` 按关键词数量均分配额
- 默认搜索引擎由 `crawler.digest.search_engine` 控制；试用任务实测使用 `bing`

### 5.2 URL 直爬（url / mixed 类型）

[digest.py:426-477](crawler-service/crawler/digest.py#L426-L477)

```python
for src in url_sources[:max_items]:
    if eff.get("dead"): continue  # 跳过死源
    if crawl_mode == "deep":
        pages = await crawl_deep_pages(url, max_depth, max_pages, ...)
    else:
        result = await crawl_single_page(url, config, crawler)
    # 注入 source_name 和 source_id 到 metadata
```

### 5.3 RSS Feed（rss 类型）

[digest.py:480-557](crawler-service/crawler/digest.py#L480-L557) + [feed.py](crawler-service/crawler/feed.py)

**两阶段处理**：
1. `parse_feed(feed_url, freshness_hours, max_entries)` — 用 `feedparser` 解析 XML
   - 用 httpx 获取 XML（不需要浏览器）
   - 按 freshness 过滤（有日期的条目）+ 保留少量无日期条目（`max_entries // 5`）
   - 未来日期过滤（容差1小时）
   - URL 用 `urljoin` 解析相对路径
2. 逐篇 `crawl_single_page()` 获取 Markdown（并发受 `max_concurrent_crawls` 信号量控制）

### 5.4 板块并行模型

```python
sem = asyncio.Semaphore(digest_parallel_sections)  # 默认 2
lock = asyncio.Lock()   # 保护 seen_urls + all_results
content_dedup = DedupEngine(simhash_threshold=5)    # 板块间去重

async def crawl_section(i, section):
    async with sem:
        if i > 0:
            await asyncio.sleep(i * digest_inter_section_delay)  # 错开启动
        # ... 爬取 ...
        async with lock:
            # URL规范化去重 → SimHash去重 → 加入 all_results
```

### 5.5 全局超时

```python
await asyncio.wait_for(
    asyncio.gather(*[crawl_section(i, s) for i, s in enumerate(sections)]),
    timeout=settings.digest_global_timeout,  # 默认 600 秒
)
```

超时不抛异常，返回已收集的部分结果。

---

## 六、去重体系

### 6.1 三层去重

| 层级 | 机制 | 阈值 | 存储位置 |
|------|------|------|---------|
| URL 去重 | SHA-256 + 规范化（协议/www/尾部斜杠/追踪参数） | 精确匹配 | `seen_urls` (内存 set) |
| 内容去重 | SimHash（跳过头部导航区，取核心段做指纹） | 汉明距离 ≤ 5 | `DedupEngine` (进程内) |
| 跨日去重 | SimHash + URL Hash 持久化 | 查最近3天 | Java `digest_fingerprint` (PostgreSQL) |

### 6.2 指纹生命周期

```
生成前：build_digest_history_engine()
  → GET /api/internal/collector/digest/fingerprints?days=3
  → 回退: 本地 SQLite 历史

生成后：save_digest_fingerprints()
  → POST /api/internal/collector/digest/fingerprints
  → PostgreSQL: ON CONFLICT (url_hash, digest_date) DO NOTHING
```

---

## 七、AI 内容整理

### 7.1 Prompt 构建

[organizer.py:546-643](crawler-service/ai/organizer.py#L546-L643)

**Token 预算管理**：
1. 总预算：`ai_digest_total_budget`（100,000 字符）
2. 预留 system prompt 开销：扣除 8,000 字符
3. 分类均分：`per_cat_budget = (budget - 8000) // num_categories`
4. 每页上限：`ai_digest_per_max_chars`（8,000 字符）
5. 超量条目仅发 summary（`per_cat_full_count = len(cat_pages) // 2`）
6. 全局预算耗尽检查：保留未用到50%配额的分类

**来源可信度排序**（同一分类内）：
```
official(0) > high(1) > medium(2) > low(3) > spam(4)
```
高可信度排前面，优先获得完整 token 配额。

**多样性防护**：追加最近 3 条 `highlight`，提示 AI 避免重复主题。

### 7.2 AI 输出验证（5层）

| 层 | 检查 | 失败处理 |
|----|------|---------|
| 1. 必填字段 | title, summary, fullContent, tags 非空 | `InvalidOutputError` |
| 2. 最小长度 | summary ≥ `min_summary_length`, fullContent ≥ `min_full_content_length` | `InvalidOutputError` |
| 3. 分类校验 | 未知 category → 映射到 `tech_article` | 自动修正 |
| 4. URL去重 | 跨 section 的 `sourceUrl` 去重，保留 `oneLiner` 最完整的 | 自动去重 |
| 5. URL合法性 | 正则 `^https?://...` + `_validate_source_urls()` 与原始输入校对 | 无匹配则清空 |

### 7.3 URL 校对（防 LLM 篡改）

```python
# organizer.py:888-920
# 匹配策略：精确匹配 → 前缀匹配 → 路径后缀匹配
# 无法匹配时清空 sourceUrl（不带错误 URL）
```

### 7.4 重试策略

| 异常 | 处理 | 最大重试 |
|------|------|---------|
| `TruncatedError` | 1.5× `max_tokens` 立即重试 | 1 次 |
| `UnrecoverableError` | 不重试 | 0 |
| `InvalidOutputError` | 不重试 | 0 |
| `RateLimitError` | `backoff_ms × (attempt+1)` | `ai_max_retries`（默认 2） |
| `OrganizerError` | `2^attempt` 秒 | `ai_max_retries`（默认 2） |

**AI 失败不阻塞**：任务仍标记 COMPLETED，原始爬取结果保留，`ai_error_message` 记录错误。

---

## 八、自动优化系统

### 8.1 架构

```
初始爬取结果
     │
     ▼
Phase 1: BreadthExpander（广度扩展 — 突破茧房）
  维度: source_diversity / perspective / language
  策略: 引擎切换 / site限定 / 跨语言翻译 / RSS源扩展
     │
     ▼
Phase 2: FeedbackLoop（深度优化 — 挖掘内容）
  维度: depth / angle / temporal
  策略: 深度限定词 / 角度变体 / 扩展时间范围
     │
     ▼
优化后结果
```

### 8.2 触发条件

日报路径需**同时满足 4 个条件**：

```python
settings.optimization_enabled                       # 总开关
settings.optimization_mode in ("digest", "both")    # 模式匹配
settings.digest_optimization_enabled                # 日报独立开关
len(all_results) >= min_sections * min_results_per_section  # 最低结果数
```

优化失败是 non-critical 的（try/except 包裹，原始结果返回）。

### 8.3 6 维覆盖度评估

| 维度 | 权重 | 评估方式 |
|------|------|---------|
| angle（角度覆盖） | 0.25 | AI 评分（启发式 fallback 上限 0.8） |
| source（来源多样性） | 0.20 | Shannon 熵（纯计算） |
| depth（深度覆盖） | 0.15 | AI 评分（启发式 fallback 上限 0.65） |
| temporal（时效性） | 0.15 | AI 评分（启发式 fallback 上限 0.6） |
| perspective（观点均衡） | 0.15 | AI 评分（启发式：30% 域名多样性 + 70% 标题情感词） |
| language（语言覆盖） | 0.10 | 调和平均（中英混合 × 1.4） |

**广度得分** = source×0.40 + perspective×0.35 + language×0.25
**深度得分** = depth×0.40 + angle×0.35 + temporal×0.25

### 8.4 终止条件（4种）

1. 目标达成：score ≥ target_score
2. 收益递减：round ≥ 3 且 delta < min_improvement（0.03）
3. 超时：`time.monotonic() > deadline`
4. 连续失败：搜索失败 ≥2 或源扩展失败 ≥2

### 8.5 知识库

基于 SQLite `optimization_record` 的策略推荐引擎：
- 将关键词拆分为 token，LIKE 匹配历史记录
- 按 engine 和 strategy_type 聚合，z-score 归一化选推荐
- 90 天自动清理

### 8.6 当前试用版反馈方式

自动优化系统目前已经接入日报主流程，但属于“轻反馈”阶段：

1. `DigestOrchestrator` 在规划阶段读取历史质量趋势、上一轮弱点和策略提示。
2. `OptimizationAgent` 在采集后评估各 section 覆盖度，必要时补采并合并结果。
3. 日报成品生成后写入 `digest_final_eval`，用于趋势面板和下一轮规划参考。
4. `get_strategy_hint()` 当前主要消费有效优化轮次记录；最终成品评估更多通过 `get_last_digest_weaknesses()` 和 `get_digest_quality_trend()` 影响下一轮。

这意味着系统已经可以“知道哪里差”，但仍需要继续把评估建议转化为更强的采集约束，例如强制跨语言补采、强制来源去重、强制 tech_article 过滤泛化页面。

---

## 九、质量过滤

### 9.1 日报独立阈值

```python
# task_executor.py:518-609
is_digest = (task_type == "digest")
# 日报：跳过 SimHash 二次去重（已在 digest.py 内完成）
# 日报：spam 来源直接拒绝（不管质量分多少）
# 日报：digest_eval_reject_threshold = 35（比 deep 更严格）
# 日报：digest_filter_min_content = 50（比通用 100 宽松）
```

### 9.2 过滤管线

```
[1] 内容过短 → 标记失败（digest: 50 chars, general: 100 chars, deep: 20 chars）
[2] 页面分类器 → SERP/列表/论坛 → 拒绝
[3] SimHash 去重 → 跳过头部导航区 → 取核心段做指纹（日报跳过此步）
[4] 质量评分 → 低于阈值拒绝（spam来源特殊处理）
```

---

## 十、Java 后端角色

### 10.1 API 端点总览

**公开日报接口**（`PublicDigestController`，无需认证）：

| 端点 | 作用 |
|------|------|
| `GET /api/digest` | 日报列表（代理 Python） |
| `GET /api/digest/latest` | 最近一期（代理 Python） |
| `GET /api/digest/{date}` | 按日期查询（代理 Python） |

**管理日报接口**（`WebCollectorController`，Sa-Token 认证）：

| 端点 | 作用 |
|------|------|
| `POST /api/admin/collector/digest/trigger` | 手动触发生成（代理 Python） |
| `GET /api/admin/collector/digest` | 管理日报列表 |
| `GET /api/admin/collector/digest/latest` | 管理最近日报 |
| `GET /api/admin/collector/digest/{date}` | 管理按日期查询 |
| `GET /api/admin/collector/digest/task/{taskId}` | 管理按任务ID查询 |
| `GET /api/admin/collector/digest/scheduler/status` | 调度器状态 |
| `GET /api/admin/collector/digest/config/sections` | 板块配置 |

**内部回调接口**（`InternalCallbackController`，X-Callback-Key 认证）：

| 端点 | 方向 | 作用 |
|------|------|------|
| `POST /api/internal/collector/callback` | Python → Java | 任务完成回调 |
| `GET /api/internal/collector/sources` | Python → Java | 获取活跃信息源 |
| `GET /api/internal/collector/config` | Python → Java | 获取爬虫配置（含解密） |
| `POST /api/internal/collector/sources/{id}/run-status` | Python → Java | 更新源运行状态 |
| `GET /api/internal/collector/digest/fingerprints` | Python → Java | 查询跨日指纹 |
| `POST /api/internal/collector/digest/fingerprints` | Python → Java | 保存指纹 |
| `GET /api/internal/collector/source-authority` | Python → Java | 单域名可信度 |
| `GET /api/internal/collector/source-authority/all` | Python → Java | 全量可信度预热 |

### 10.2 代理模式

Java 对日报数据**不存储**，所有日报 CRUD 请求直接代理到 Python：

```java
// PublicDigestController / WebCollectorController
return Result.success(crawlerTaskClient.proxyGet("/api/v1/digests/..."));
```

Python 不可用时返回 503（`BusinessException(503, "服务暂时不可用")`）。

### 10.3 质量分反馈（EMA）

```java
// WebCollectSourceAppService.java:122-164
double prev = source.getAvgQualityScore() != null ? source.getAvgQualityScore() : 0;
double avg = prev == 0 ? qualityScore : 0.7 * prev + 0.3 * qualityScore;
```

每次 Python 回调 `run-status` 时，用 EMA(α=0.3) 更新源的 `avgQualityScore`，乐观锁 3 次重试。

### 10.4 回调认证安全

```java
// 空 API key → 阻止所有内部端点（不是"允许所有"）
if (expectedKey.isBlank()) { return true; }  // authRequired = true = 阻止
```

必须设置 `crawler.callback.api-key` 才能启用内部端点。

### 10.5 对账定时器

```java
// TaskReconciliationScheduler.java
@Scheduled(fixedDelayString = "${crawler.reconciliation.interval-ms:600000}")  // 默认10分钟
// 查找 pythonTaskId != null AND status IN (0,1,2) AND updatedAt < 30分钟前
// → syncFromPythonSilent()
```

安全网：callback 失败时最终会通过轮询同步。

---

## 十一、前端集成

### 11.1 路由

**公开页面**：
- `/digest` → 日报列表（按日期倒序卡片）
- `/digest/latest` → 最近一期
- `/digest/:date` → 按日期查看

**管理页面**：
- `/admin/digest` → 管理列表 + "生成日报"按钮
- `/admin/digest/latest` → 管理最近一期
- `/admin/digest/:date` → 管理按日期
- `/admin/digest/task/:id` → 管理按任务ID
- `/admin/source` → 信息源管理
- `/admin/collector` → 采集器任务（taskType=digest 也出现于此）

### 11.2 状态轮询

```typescript
// usePolling composable — 递归 setTimeout，避免慢网络请求堆叠
const { start, stop } = usePolling(
  fetchDigest,
  5000,  // POLLING_INTERVAL.DIGEST_STATUS
  {
    immediate: false,
    condition: () => isActive.value && !loading.value,
    // isActive: status === 0 || 1 || 2（非终态时才轮询）
  },
)
```

轮询在以下情况自动停止：
- `condition()` 返回 false（任务到达终态）
- 组件 unmount

### 11.3 日报颜色映射

```typescript
// constants/digest.ts
DIGEST_CATEGORY_COLORS = {
  hot_trend:    '#FF6B6B',  // 红
  open_source:  '#FFD93D',  // 黄
  tech_article: '#6BCB77',  // 绿
  dev_tool:     '#4D96FF',  // 蓝
  creative:     '#FF6EC7',  // 粉
  paper:        '#A66CFF',  // 紫
}
```

---

## 十二、配置参数

### 12.1 日报核心配置

| 配置键 | 默认值 | 说明 |
|--------|--------|------|
| `crawler.digest.enabled` | `false` | 日报总开关（Python调度用） |
| `crawler.digest.cron` | `0 8 * * 1-5` | 定时cron（工作日早8点） |
| `crawler.digest.search_engine` | `sogou`（配置中心可覆盖，试用环境实测为 `bing`） | 日报默认搜索引擎 |
| `crawler.digest.parallel_sections` | `2` | 板块并行数 |
| `crawler.digest.global_timeout` | `600` | 全局超时（秒） |
| `crawler.digest.inter_section_delay` | `2.0` | 板块间延迟（秒） |
| `crawler.digest.history_load_count` | `3` | 历史指纹加载天数 |
| `crawler.digest.filter_min_content` | `50` | 日报最短内容 |
| `crawler.digest.section_result_multiplier` | `2` | 搜索结果倍数 |
| `crawler.digest.optimization_enabled` | `false` | 日报优化独立开关 |
| `crawler.digest.optimization_min_sections` | `2` | 触发优化最少板块数 |
| `crawler.digest.optimization_target_score` | `0.65` | 日报优化目标分 |
| `crawler.digest.optimization_min_results_per_section` | `3` | 每板块最少结果数 |

### 12.2 优化系统配置

| 配置键 | 默认值 | 说明 |
|--------|--------|------|
| `crawler.optimization.enabled` | `false` | 优化总开关 |
| `crawler.optimization.mode` | `both` | keyword/digest/both |
| `crawler.optimization.max_rounds` | `3` | 深度循环最大轮次 |
| `crawler.optimization.breadth_max_rounds` | `3` | 广度循环最大轮次 |
| `crawler.optimization.total_budget_seconds` | `120` | 总时间预算 |
| `crawler.optimization.min_improvement` | `0.03` | 收益递减阈值 |
| `crawler.optimization.depth_target_score` | `0.7` | 深度目标分 |
| `crawler.optimization.breadth_target_score` | `0.7` | 广度目标分 |
| `crawler.optimization.round_delay_min` | `2.0` | 轮间延迟下限 |
| `crawler.optimization.round_delay_max` | `4.0` | 轮间延迟上限 |

### 12.3 AI 配置

| 配置键 | 默认值 | 说明 |
|--------|--------|------|
| `crawler.ai.digest_per_max_chars` | `8000` | 每页最大输入字符 |
| `crawler.ai.digest_total_budget` | `100000` | 总输入预算 |
| `crawler.ai.digest_max_tokens` | `16000` | AI 输出 token 上限 |
| `crawler.ai.max_retries` | `2` | AI 重试次数 |

### 12.4 来源可信度

| 配置键 | 默认值 | 说明 |
|--------|--------|------|
| `crawler.quality.weight_source` | `0.20` | 来源多样性权重 |
| `crawler.quality.source_weight` | `0.4` | 来源在质量分中的权重 |
| `crawler.quality.content_weight` | `0.6` | 内容在质量分中的权重 |
| `crawler.quality.eval_pass_threshold` | `65` | 通过阈值 |
| `crawler.quality.eval_review_threshold` | `45` | 审查阈值 |

### 12.5 茧房突破

| 配置键 | 默认值 | 说明 |
|--------|--------|------|
| `crawler.bubble.enabled` | `false` | 茧房突破开关 |
| `crawler.bubble.cross_language` | `true` | 跨语言翻译 |
| `crawler.bubble.max_translate_tokens` | `200` | 翻译 token 上限 |
| `crawler.bubble.min_source_diversity` | `0.6` | 最低来源多样性 |

### 12.6 配置下发机制

所有 `crawler.*` 配置存储在 Java 端 `sys_config` 表，Python 通过以下方式获取：

```
Python 启动 → GET /api/internal/collector/config → Map<stripped_key, value>
Python 运行中 → POST /api/v1/config/refresh → 重新拉取
```

Java 端自动处理加密值解密（`AesEncryptor.decrypt()`）。

---

## 十三、错误处理与可靠性

### 13.1 回调可靠性

```
Python 完成 → _fire_callback() → POST /api/internal/collector/callback
  ├─ 2xx: 成功
  ├─ 4xx: 不可恢复，停止重试
  └─ 5xx / 网络错误: 指数退避重试 (2^attempt 秒), 最多3次
```

兜底：Java `TaskReconciliationScheduler` 每 10 分钟轮询超时 30 分钟的非终态任务。

### 13.2 服务重启恢复

```python
# db.py:189-199 — 启动时重置孤儿任务
UPDATE crawl_task SET status = 4, error_message = '服务重启：任务被中断'
WHERE status IN (1, 2)  -- CRAWLING / PROCESSING
```

### 13.3 防并发生成

```python
# scheduler.py:68-72
async with _digest_lock:  # asyncio.Lock
    existing = await repo.get_digest_existing_non_failed(today)
    if existing: return  # SQL原子检查
```

### 13.4 乐观锁

Java 端 `WebCollectTask` 和 `WebCollectSource` 使用 `@Version` 字段。并发更新冲突被视为正常（先到先赢），`OptimisticLockingFailureException` 静默处理。

---

## 十四、开发陷阱清单

| 陷阱 | 位置 | 说明 |
|------|------|------|
| **AI 失败≠任务失败** | task_executor.py:222-224 | AI 失败后任务仍 COMPLETED，前端需检查 `ai_error_message` |
| **日报不做 SimHash 二次去重** | task_executor.py:186-187 | 日报跳过 DedupEngine，依赖 digest.py 内部去重 |
| **配置深拷贝** | digest.py:41 | `copy.deepcopy(sections)` 防执行中管理员修改 |
| **重试幂等** | repository.py:334 | `DELETE FROM digest_section WHERE task_id=?` 先清后插 |
| **空 API key = 全部阻止** | InternalCallbackController:46-50 | 必须设置 `crawler.callback.api-key` |
| **触发是异步的** | routes.py:449 | `trigger_digest()` 不等待完成，前端需轮询 |
| **keyword 字段存日期** | scheduler.py:89 | 日报任务 `keyword=today`，不是搜索词 |
| **全局超时返回部分结果** | digest.py:173-177 | 不抛异常，返回已收集内容 |
| **乐观锁冲突正常** | WebCollectorAppService:381-383 | 并发同步视为正常，先到先赢 |
| **服务启动重置孤儿** | db.py:189-199 | CRAWLING/PROCESSING → FAILED |
| **AI Prompt 预留 8000 字符** | organizer.py:563 | 从总预算扣除，不是全量可用 |
| **highlight 兜底** | organizer.py:864 | AI 未返回时取首条 oneLiner |
| **死源跳过** | digest.py:444,518 | success_rate < 20% 且 runs ≥ 3 跳过 |
| **无日期 RSS 条目** | feed.py:102-114 | 保留 `max_entries // 5` 条无日期条目 |

---

## 十五、关键文件索引

### Python 爬虫服务

| 文件 | 职责 |
|------|------|
| `crawler-service/standalone/task_executor.py` | 任务执行引擎（爬取 + AI + 优化） |
| `crawler-service/standalone/organizer_helper.py` | AI 整理桥接（DTO 转换 + save） |
| `crawler-service/standalone/scheduler.py` | 定时调度 + 信息源调度 |
| `crawler-service/standalone/repository.py` | SQLite 持久化 |
| `crawler-service/standalone/routes.py` | FastAPI 端点 |
| `crawler-service/standalone/db.py` | SQLite DDL + 连接管理 |
| `crawler-service/standalone/models.py` | TaskStatus 枚举 |
| `crawler-service/crawler/digest_orchestrator.py` | 日报总编排：规划、采集调度、优化、评估入库 |
| `crawler-service/crawler/digest_gen_agent.py` | 日报结构化生成 Agent |
| `crawler-service/crawler/optimization_agent.py` | 日报自动优化 Agent：弱板块识别、补采、合并 |
| `crawler-service/crawler/digest.py` | 日报爬取编排 + 优化入口 |
| `crawler-service/crawler/search.py` | 搜索引擎集成 |
| `crawler-service/crawler/feed.py` | RSS/Atom 解析 |
| `crawler-service/ai/organizer.py` | AI 内容整理（Prompt + 解析 + 验证） |
| `crawler-service/ai/config.py` | AI 设置 facade |
| `crawler-service/optimization/evaluator.py` | 6 维覆盖度评估 |
| `crawler-service/optimization/strategy.py` | 深度/广度策略生成 |
| `crawler-service/optimization/feedback.py` | 深度反馈循环 |
| `crawler-service/optimization/bubble_breaker.py` | 广度扩展 + 跨语言 |
| `crawler-service/optimization/knowledge_base.py` | 策略知识库 |
| `crawler-service/config.py` | 全局配置（Pydantic Settings） |

### Java 后端

| 文件 | 职责 |
|------|------|
| `interfaces/rest/PublicDigestController.java` | 公开日报代理 |
| `interfaces/rest/WebCollectorController.java` | 管理日报代理 + 来源 CRUD |
| `interfaces/rest/InternalCallbackController.java` | Python 回调端点 |
| `application/webcollector/WebCollectorAppService.java` | 任务编排 + 同步 |
| `application/webcollector/WebCollectSourceAppService.java` | 来源管理 + 质量反馈 |
| `infrastructure/crawler/CrawlerTaskClient.java` | Python HTTP 客户端 |
| `infrastructure/scheduler/TaskReconciliationScheduler.java` | 对账定时器 |
| `domain/webcollector/WebCollectTask.java` | 任务实体 |
| `domain/webcollector/WebCollectSource.java` | 来源实体 |
| `domain/webcollector/DigestFingerprint.java` | 指纹实体 |
| `domain/webcollector/SourceAuthority.java` | 可信度实体 |

### Vue 前端

| 文件 | 职责 |
|------|------|
| `views/digest/List.vue` | 公开日报列表 |
| `views/digest/Detail.vue` | 公开日报详情 |
| `views/admin/digest/List.vue` | 管理日报列表 + 触发 |
| `views/admin/digest/Detail.vue` | 管理日报详情 + 轮询 |
| `views/admin/collector/SourceList.vue` | 信息源管理 |
| `api/collector.ts` | API 层 |
| `types/collector.ts` | TypeScript 类型定义 |
| `composables/usePolling.ts` | 轮询 composable |
| `constants/digest.ts` | 分类颜色映射 |

---

## 十六、部署检查清单

### 16.1 必须配置

- [ ] `crawler.callback.api-key` — 非空，否则内部端点全部阻止
- [ ] `crawler.service.base-url` — Python 服务地址
- [ ] `crawler.digest.enabled` — `true` 启用日报调度
- [ ] `crawler.ai.base-url` — AI API 地址
- [ ] `crawler.ai.api-key` — AI API Key

### 16.2 数据库初始化

- [ ] PostgreSQL: 执行 Flyway 迁移（V1_12 至 V1_18）
- [ ] Python SQLite: 自动创建（`init_db()` 启动时执行）
- [ ] `source_authority` 表预置 30 个域名评分（V1_18）

### 16.3 信息源配置

- [ ] 在管理后台 `/admin/source` 创建至少 1 个信息源
- [ ] 信息源 `isActive=true` 才会被日报使用
- [ ] `contentCategory` 决定板块分组

---

> 文档版本：v1.1
> 生成日期：2026-05-23
> 最近更新：2026-06-01
> 当前基线：MVP Beta 试用版
