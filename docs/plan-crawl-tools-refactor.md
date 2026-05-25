# 爬虫工具层架构调整与问题修复方案

> 2026-05-24 | Phase E: CrawlerAgent → Crawl Tools 调用链优化

---

## Context

Phase C 完成了 Agent 分层（SourceAgent 分析 → CrawlerAgent 执行），Phase D 完成了爬虫工具层的全面分析。
当前 CrawlerAgent 通过兼容桥接方式调用 digest.py 中的遗留函数，存在以下问题：

1. URL/RSS 爬取函数仍留在 digest.py，跨模块调用链混乱
2. 去重逻辑重复（crawl_by_keyword 内部去重 + CrawlerAgent 板块去重 + Orchestrator 跨板块去重）
3. 内容指纹窗口参数不一致，可能产生不同 SimHash
4. CrawlerAgent 的 `_to_raw_section()` 是临时兼容桥接

---

## 修改文件清单

### 新建

| 文件 | 用途 |
|------|------|
| `crawler-service/crawler/source_crawler.py` | URL/RSS 爬取函数（从 digest.py 迁出） |

### 修改

| 文件 | 改动 |
|------|------|
| `crawler-service/crawler/crawler_agent.py` | 导入迁移；传去重参数；去掉内部冗余去重 |
| `crawler-service/crawler/search.py` | crawl_by_keyword 新增 `skip_dedup` 参数 |
| `crawler-service/crawler/dedup.py` | dedup_results 参数默认值改为从 settings 读取 |
| `crawler-service/crawler/digest.py` | 删除迁出函数，改为委托 source_crawler |
| `crawler-service/optimization/bubble_breaker.py` | 导入路径迁移 |

### 不修改（仅观察）

| 文件 | 原因 |
|------|------|
| `crawler-service/crawler/deep.py` | 日报流程不调用，架构完整无需改动 |
| `crawler-service/crawler/single.py` | 底层工具，被上层正确调用 |
| `crawler-service/crawler/feed.py` | 底层工具，被上层正确调用 |

---

## 4 个修复项

---

### Fix 1: URL/RSS 爬取函数迁出 digest.py → source_crawler.py

**问题**：`_crawl_url_sources`（digest.py:440）和 `_crawl_rss_sources`（digest.py:494）是通用爬取函数，但放在 digest.py 中。CrawlerAgent 和 bubble_breaker.py 都需要从 digest.py 导入，造成不必要的模块耦合。

**方案**：

1. 创建 `crawler/source_crawler.py`，迁入两个函数
2. 函数改名：`_crawl_url_sources` → `crawl_url_sources`（去掉下划线前缀，成为模块级公开函数）
3. digest.py 保留薄委托层（向后兼容，避免遗漏调用方）：

```python
# digest.py — 委托层
from crawler.source_crawler import crawl_url_sources, crawl_rss_sources

# 保留旧名称的委托（bubble_breaker.py 等旧调用方）
async def _crawl_url_sources(section, config, crawler):
    return await crawl_url_sources(section, config, crawler)

async def _crawl_rss_sources(section, config, crawler):
    return await crawl_rss_sources(section, config, crawler)
```

4. 更新调用方导入：
   - `crawler_agent.py`: `from crawler.source_crawler import crawl_url_sources, crawl_rss_sources`
   - `bubble_breaker.py`: `from crawler.source_crawler import crawl_url_sources, crawl_rss_sources`

**影响范围**：3 个调用方（crawler_agent / digest / bubble_breaker），函数签名不变，纯迁出。

**迁出后 digest.py 保留的函数**（仍然需要的）：
- `execute_digest_crawl()` — 旧日报入口（向后兼容）
- `_is_truly_dead()` — 委托 source_analysis.py
- `build_digest_history_engine()` — 构建历史去重引擎
- `save_digest_fingerprints()` — 指纹持久化
- `run_digest_optimization()` — 事后优化
- `_copy_config()` — 配置拷贝
- `_apply_overrides()` — bubble_breaker 用

**迁出后 digest.py 删除的函数**：
- `_crawl_url_sources()` — 迁到 source_crawler.py
- `_crawl_rss_sources()` — 迁到 source_crawler.py
- 保留薄委托（3行）防止遗漏

---

### Fix 2: crawl_by_keyword 内部去重冗余

**问题**：crawl_by_keyword（search.py:825）末尾调用 `dedup_results(results)` 做本地去重（无 history_engine）。CrawlerAgent._crawl()（crawler_agent.py:125）又调用 `dedup_results(results, history_engine=history_engine)` 做板块级去重。

调用链中**同一个结果集被去重两次**：
1. search.py:825 — 本地 DedupEngine（阈值 12），无历史
2. crawler_agent.py:125 — 本地 DedupEngine（阈值 12）+ history_engine

第一次去重完全被第二次覆盖（第二次的本地引擎会重复过滤同样的内容）。

**方案**：

search.py 的 `crawl_by_keyword` 新增 `skip_dedup: bool = False` 参数：

```python
async def crawl_by_keyword(
    keyword: str,
    engine: str = "bing",
    max_results: int = 10,
    time_range: str = "week",
    config: Optional[object] = None,
    crawler: Optional[AsyncWebCrawler] = None,
    skip_dedup: bool = False,       # ← 新增
) -> List[CrawlResult]:
```

- `skip_dedup=False`（默认）：保持现有行为，其他调用方不受影响
- `skip_dedup=True`：跳过 search.py:824-831 的内部去重

CrawlerAgent 调用时传 `skip_dedup=True`：

```python
# crawler_agent.py _crawl()
kw_results = await crawl_by_keyword(
    keyword=kw,
    engine=plan.recommended_engine,
    max_results=per_kw_max,
    time_range=self.section.time_range,
    config=self._config,
    crawler=crawler,
    skip_dedup=True,       # ← Agent 层自行去重
)
```

**为什么不用更激进方案（直接删除内部去重）**：
- `api/crawl.py:157` 直接调用 crawl_by_keyword，不经过 Agent 层，需要内部去重
- `task_executor.py:303` 同样直接调用
- 删除会破坏这些调用方

---

### Fix 3: 内容指纹窗口参数统一

**问题**：

| 调用位置 | skip_header | preview_length | 来源 |
|----------|-------------|----------------|------|
| dedup_results 默认值 | 200 | 800 | 硬编码 |
| Orchestrator._merge_results | settings.xxx | settings.xxx | 配置 |
| CrawlerAgent._crawl | 200 | 800 | 默认值 |

dedup_results 的硬编码默认值恰好等于 settings 默认值（200/800），但**如果用户修改了 settings 配置**：
- CrawlerAgent 板块内去重仍用 200/800
- Orchestrator 跨板块去重用新值
- **同一内容产生不同的 SimHash**，跨板块去重失效

**方案**：

dedup_results 参数默认值改为 `None`，运行时从 settings 读取：

```python
# dedup.py
def dedup_results(
    results: list,
    content_preview_length: int | None = None,
    skip_header_chars: int | None = None,
    history_engine: Optional[DedupEngine] = None
) -> list:
    # 统一从 settings 读取默认值
    if skip_header_chars is None:
        from config import settings
        skip_header_chars = settings.filter_skip_header_chars
    if content_preview_length is None:
        from config import settings
        content_preview_length = settings.filter_content_preview_length
    ...
```

这样所有调用点自动获得一致的参数，无需逐个修改。显式传参仍可覆盖。

**影响**：
- search.py 内部去重：自动使用 settings 值 ✓
- CrawlerAgent._crawl：自动使用 settings 值 ✓
- Orchestrator._merge_results：已显式传 settings 值，不受影响 ✓
- 其他调用方（test 等）：默认值行为不变（settings 默认值 = 旧硬编码值）

---

### Fix 4: CrawlerAgent 去重参数统一 + 兼容桥接清理

**问题**：CrawlerAgent._crawl() 调用 dedup_results 时未传 fingerprint 参数，导致板块内去重可能与跨板块去重使用不同窗口。

**方案**：

Fix 3 统一了 dedup_results 的默认值后，此问题自动解决。无需额外改动。

同时清理 CrawlerAgent 的导入：

```python
# crawler_agent.py — 修改前
from crawler.digest import _crawl_url_sources, _crawl_rss_sources

# crawler_agent.py — 修改后
from crawler.source_crawler import crawl_url_sources, crawl_rss_sources
```

`_to_raw_section()` 保留（它构造的 dict 仍被 crawl_url_sources/crawl_rss_sources 接受），但更新注释说明。

---

## 实施顺序

```
Phase E-1: 基础层 — dedup.py 参数统一 (Fix 3)
Phase E-2: 迁移层 — source_crawler.py + digest.py 委托 (Fix 1)
Phase E-3: 调用层 — search.py skip_dedup + crawler_agent.py 导入更新 (Fix 2 + Fix 4)
Phase E-4: 验证 — 测试 + grep 确认
```

---

## 验证清单

1. `pytest crawler-service/tests/` — 全量回归通过
2. Grep 确认：
   - `_crawl_url_sources` 和 `_crawl_rss_sources` 只在 digest.py 委托层存在（或完全消除）
   - `crawl_url_sources` 和 `crawl_rss_sources` 在 source_crawler.py 定义，所有调用方导入路径正确
3. crawl_by_keyword `skip_dedup=True` 测试：Agent 调用路径不触发内部去重
4. dedup_results 参数测试：settings 修改后所有调用点行为一致
5. 端到端验证：日报任务正常运行，去重率与修改前无显著差异

---

## 风险评估

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| digest.py 委托遗漏调用方 | 低 | 旧路径崩溃 | Grep 全量搜索确认所有调用方 |
| skip_dedup 默认值语义反转 | 极低 | 功能回退 | 默认 False 保持旧行为 |
| settings 循环导入 | 低 | 启动失败 | dedup.py 延迟 import settings |
| bubble_breaker 导入路径变化 | 低 | 优化模块报错 | bubble_breaker.py 同步更新导入 |
