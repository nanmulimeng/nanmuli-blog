# WebCollector 架构设计 v3.0

> 版本：v3.0
> 日期：2026-05-06
> 目标：从博客附属模块升级为独立可用的智能信息聚合系统

---

## 一、核心定位

### 1.1 愿景

打造一个**能够自我进化、主动突破信息茧房**的智能信息聚合系统。

### 1.2 三大铁律（不可妥协）

| 优先级 | 原则 | 技术映射 |
|--------|------|---------|
| **P1** | **内容正确，质量要高** | 来源可信度评分 > 低质量过滤 > AI整理准确性 |
| **P2** | **信息不能滞后，最前沿** | 时间过滤器优先 > 增量抓取 |
| **P3** | **重复性不能太高** | URL去重 > 内容相似度去重 > 跨任务历史去重 |

**决策原则**：P1 > P2 > P3。质量不合格即使最新也丢弃；过时的高质量内容优先级低于最新的合格内容。

### 1.3 两种使用场景

**场景A：作为博客系统的采集模块（当前）**
```
博客前端 → 创建采集任务 → WebCollector服务 → AI整理 → 转为文章/日志
                               ↑
                        自动优化引擎提升内容质量
```

**场景B：作为独立产品使用（未来）**
```
用户 → WebCollector API/CLI → 自动聚合每日资讯 → Markdown/JSON输出
                                              ↓
                                        自动优化引擎持续改进策略
```

---

## 二、当前架构盘点

### 2.1 已有组件

| 组件 | 位置 | 功能 | 状态 |
|------|------|------|------|
| Crawler Service | `crawler-service/` | FastAPI服务，提供爬取API | ✅ 成熟 |
| AsyncWebCrawler | `crawler/` | 基于Crawl4AI的无头浏览器爬取 | ✅ 成熟 |
| Search Engine | `crawler/search.py` | Bing/Sogou/Google/DDG搜索，含时间过滤 | ✅ 已完成 |
| Content Deduplication | `crawler/dedup.py` | 三层去重：URL→SimHash→标题Jaccard | ✅ 已完成 |
| Quality Scoring | `crawler/quality.py` | 来源可信度+内容质量多维度评分+自动过滤 | ✅ 已完成 |
| Keyword Expansion | Java后端 | AI生成2-3个变体，语境判断优先 | ✅ 已上线 |
| Keyword Optimization | Java后端 | AI优化原始关键词 | ✅ 已上线 |
| AI Content Organizer | Java后端 | OpenAI兼容API内容整理 | ✅ 成熟 |
| Async Executor | Java后端 | Spring @Async任务编排 | ✅ 成熟 |

### 2.2 数据流

```
[用户输入] → [Java后端创建任务] → [事务提交] → [@Async执行器]
                                              ↓
                                    [AI优化关键词] → [AI扩展关键词]
                                              ↓
                                    [调用Python爬虫服务]
                                              ↓
                                    [搜索引擎抓取URL] → [Crawl4AI爬取页面]
                                              ↓
                                    [三层去重+质量评分过滤]
                                              ↓
                                    [Java后端AI整理] → [保存结果]
                                              ↓
                                    [转为文章/日志/日报]
```

### 2.3 任务类型

| 类型 | 说明 | 数据源 |
|------|------|--------|
| `SINGLE` | 单页爬取 | 指定URL |
| `DEEP` | BFS深度爬取 | 指定URL及其链接 |
| `KEYWORD` | 关键词搜索爬取 | 搜索引擎 |
| `DAILY_DIGEST` | 定时综合日报 | 搜索引擎+多板块关键词 | 规划中 |

---

## 三、核心架构

### 3.1 总体架构

```
┌─────────────────────────────────────────────────────────────┐
│                        接入层                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ REST API     │  │ Web UI       │  │ 定时调度         │  │
│  │ (FastAPI)    │  │ (博客后台)   │  │ (APScheduler)    │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                      任务调度层                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │ 即时任务    │  │ 定时任务    │  │ 自动优化任务        │ │
│  │ (用户触发)  │  │ (Cron)      │  │ (系统触发)          │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                   自动优化引擎 (★核心创新)                    │
│  ┌──────────────────┐    ┌──────────────────┐              │
│  │ Coverage Evaluator│ → │ Strategy Generator│            │
│  │ 覆盖度评估器      │    │ 策略生成器         │            │
│  └──────────────────┘    └──────────────────┘              │
│           ↑                      │                         │
│           └──── Feedback Loop ←──┘                        │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              Information Bubble Breaker               │  │
│  │  ├─ Source Diversity Monitor (Shannon熵)              │  │
│  │  ├─ Perspective Balance Detector                      │  │
│  │  └─ Cross-Language Expander                           │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                      数据采集层                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Search Strategy (Bing/Sogou/Google/DDG)            │   │
│  │  ├── AI关键词扩展 (2-3个变体)                        │   │
│  │  ├── 时间范围过滤 (day/week/month/year/all)         │   │
│  │  └── 多引擎自动轮换                                 │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Web Crawler (Crawl4AI)                             │   │
│  │  ├── 无头浏览器渲染                                 │   │
│  │  ├── 反爬伪装 (UA/间隔/引擎轮换)                    │   │
│  │  └── 内容提取 (Markdown)                            │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                      内容处理层                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Deduplication│  │ Quality      │  │ AI           │      │
│  │ 三层去重     │  │ Scoring      │  │ Organization │      │
│  │ URL/SimHash/ │  │ 来源40%+质量 │  │ 整理/摘要    │      │
│  │ 标题Jaccard  │  │ 60%综合评分  │  │              │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                        输出层                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Blog Article │  │ Daily Log    │  │ Daily Digest │      │
│  │ (文章草稿)   │  │ (技术日志)   │  │ (技术日报)   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 核心创新：自动优化引擎

#### 3.2.1 覆盖度评估器

每次搜索完成后，AI对结果进行多维度评估：

```python
@dataclass
class CoverageEvaluation:
    angle_coverage: float      # 0-1，主题多方面覆盖
    source_diversity: float    # 0-1，基于Shannon熵的域名分布
    depth_coverage: float      # 0-1，浅层到深度分析覆盖
    temporal_coverage: float   # 0-1，历史背景+最新进展
    perspective_balance: float # 0-1，观点均衡度
    language_coverage: float   # 0-1，跨语言信息
    overall_score: float       # 0-1，综合评分
    weaknesses: List[str]      # 短板列表
    suggestions: List[str]     # 改进建议
```

**评估Prompt核心**：给定关键词和搜索结果来源列表，让AI按6维度评分并给出改进建议。

#### 3.2.2 策略生成器

根据评估短板，生成下一轮搜索的改进策略：

| 评估发现 | 策略调整 |
|---------|---------|
| 来源多样性低 | 轮换搜索引擎，添加`site:`限定词引入新来源 |
| 时效性覆盖低 | 调整时间过滤范围，添加年份限定词 |
| 深度覆盖低 | 添加"tutorial"、"deep dive"、"architecture"等深度词 |
| 观点平衡低 | 添加"vs"、"comparison"、"limitation"等对比词 |
| 缺少官方文档 | 添加`site:docs.*`或`site:github.com` |

#### 3.2.3 反馈循环

```
第1轮搜索 → Coverage Evaluator评估 → overall: 5.5
                ↑                           │
                └──── Strategy Generator ←──┘
                          │
                          ▼
              生成改进策略（英文关键词/site限定/引擎切换）
                          │
                          ▼
              第2轮搜索（补充缺失维度）→ overall: 7.2 ✅
                          │
                          ▼
              知识库更新（记录有效策略组合）
```

**终止条件**：
- `overall_score >= 7.0` → 达标终止
- `max_attempts >= 3` → 防无限循环
- 单轮提升 < 0.3 且总轮数 >= 2 → 收益递减终止

#### 3.2.4 信息茧房突破机制

**来源多样性监控**：使用Shannon熵计算域名分布，低于0.6触发补充搜索。

**观点平衡检测**：基于正/负/中立信号词统计，检测到单向偏向时主动搜索对立观点。

**跨语言扩展**：中文搜索后自动翻译为英文补充搜索，结果合并去重。

---

## 四、关键模块设计

### 4.1 搜索引擎策略（`crawler/search.py`）

**核心设计**：搜索引擎是通用数据源，不维护独立API客户端。

- 支持引擎：Bing（默认）/ Sogou / Google / DuckDuckGo
- 多引擎自动轮换：首选引擎失败时按优先级自动切换
- 时间过滤：`day`/`week`/`month`/`year`/`all`，各引擎原生参数映射
- 反爬策略：引擎间随机间隔2-5秒、翻页间隔0.8-2秒、UA伪装
- 结果预筛选：标题/摘要相关性检查 + 域名黑名单过滤 + 同域名去重

### 4.2 内容去重（`crawler/dedup.py`）

**三层去重，够用即可，不堆复杂度**：

| 层级 | 方法 | 阈值 | 用途 |
|------|------|------|------|
| Layer 1 | URL标准化精确匹配 | 100%相同 | 完全相同的链接 |
| Layer 2 | SimHash（64位） | 汉明距离 ≤3 | 内容改写/转载 |
| Layer 3 | 标题Jaccard系数 | 相似度 ≥0.8 | 标题高度相似 |

**不引入**：TF-IDF语义相似度（对短文本效果差）、LDA事件聚类（需要预设K值）。

### 4.3 质量评分（`crawler/quality.py`）

**来源可信度评分**：

| 等级 | 分数 | 示例 |
|------|------|------|
| 官方文档 | 95 | docs.spring.io, react.dev, arxiv.org |
| 高质量社区 | 80 | stackoverflow.com, medium.com, juejin.cn |
| 技术博客 | 60 | github.io, vercel.app |
| 内容农场 | 20 | baijiahao.baidu.com, toutiao.com |
| 垃圾/营销 | 5 | mp.weixin.qq.com |
| 未知来源 | 50 | 默认 |

**内容质量评分**：
- 字数评分（0-25）：2000字以上满分
- 结构评分（0-25）：标题层级+代码块+列表
- 代码密度评分（0-25）：代码占比5%-50%为最佳
- 广告占比评分（0-25）：广告词越少分越高
- 惩罚项：标题党（每个-15，上限50）、广告（每个-10，上限40）

**综合决策**：`final_score = 来源40% + 质量60%`，verdict分为 pass/review/reject。

### 4.4 AI关键词扩展（Java后端）

**设计原则**：
- 最多3个变体，避免过多请求触发反爬
- 语境判断优先：技术语境下保持技术含义（Gemini=Google AI模型）
- 歧义词处理：多义词至少生成一个带技术限定词的变体
- 输出JSON数组，解析失败回退到原关键词

### 4.5 日报模块设计（`DAILY_DIGEST`）

**核心原则**：不复建数据源，全部走搜索引擎+关键词。

**板块配置**：

```yaml
daily_digest:
  sections:
    - name: "news"
      keyword: "科技新闻"
      time_range: "day"
      max_items: 5
    - name: "articles"
      keyword: "技术博客"
      time_range: "week"
      max_items: 3
    - name: "papers"
      keyword: "arxiv"
      time_range: "week"
      max_items: 2
    - name: "opensource"
      keyword: "GitHub trending"
      time_range: "week"
      max_items: 3
```

**生成流程**：
1. 读取板块配置
2. 对每个板块执行 `KEYWORD` 任务（复用已有异步执行器）
3. 各板块结果经过去重+质量评分过滤
4. AI `organizeMultiple` 整理为结构化日报
5. 输出Markdown格式

**不做的**：
- ❌ 不维护42个独立数据源
- ❌ 不引入实时流监控（Twitter API成本过高）
- ❌ 不要求人工审核（用质量评分置信度替代）

---

## 五、独立拆分方案

### 5.1 拆分目标

当前 `crawler-service` 已具备独立运行基础，拆分目标：

| 耦合点 | 当前状态 | 拆分目标 |
|--------|---------|---------|
| 数据库 | 独立SQLite（standalone模式） | 保留SQLite，可选PostgreSQL |
| AI整理 | Java后端调用 | 保持现状（Java端AI能力已成熟） |
| 用户系统 | 依赖博客Sa-Token | 拆分后内置API Key认证 |
| 部署 | Docker Compose内嵌 | 独立Docker镜像 |

### 5.2 拆分后项目结构

```
webcollector/
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
│
├── src/
│   ├── main.py                    # FastAPI入口
│   ├── config.py                  # 配置管理
│   │
│   ├── api/                       # API层
│   │   ├── crawl.py               # /crawl/* 端点
│   │   └── task.py                # /task/* 端点（定时任务管理）
│   │
│   ├── crawler/                   # 爬虫核心
│   │   ├── single.py              # 单页爬取
│   │   ├── deep.py                # 深度爬取
│   │   ├── search.py              # 搜索爬取（含时间过滤/引擎轮换）
│   │   ├── dedup.py               # 三层去重
│   │   ├── quality.py             # 来源可信度+内容质量评分
│   │   └── config.py              # 爬虫配置
│   │
│   ├── optimization/              # 自动优化引擎
│   │   ├── evaluator.py           # 覆盖度评估器
│   │   ├── strategy.py            # 策略生成器
│   │   └── knowledge_base.py      # 策略知识库（SQLite）
│   │
│   └── output/                    # 输出格式化
│       ├── markdown.py            # Markdown导出
│       └── digest.py              # 日报生成
│
├── tests/                         # 测试
└── docs/                          # 文档
```

### 5.3 与博客系统集成

拆分后博客系统通过HTTP API调用：

```java
@Service
public class WebCollectorClient {
    public Long createKeywordTask(String keyword, String timeRange) {
        Map<String, Object> request = Map.of(
            "task_type", "keyword",
            "keyword", keyword,
            "time_range", timeRange,      // day/week/month/year/all
            "max_pages", 10
        );
        return restClient.post()
            .uri("/crawl/search")
            .body(request)
            .retrieve()
            .body(TaskResponse.class)
            .getId();
    }
}
```

---

## 六、技术实现路线图

### 已完成 ✅

| Phase | 目标 | 状态 |
|-------|------|------|
| Phase 1（P2） | 搜索引擎时间过滤 | ✅ `search.py`/`api/crawl.py` |
| Phase 2（P3） | 三层去重引擎 | ✅ `dedup.py` |
| Phase 3（P1） | 来源可信度+质量评分+自动过滤 | ✅ `quality.py` |
| time_range传递 | Java端到Python端全链路 | ✅ 10个文件已改 |

### 规划中

| Phase | 目标 | 预计周期 | 关键文件 |
|-------|------|---------|---------|
| **Phase 4** | **日报任务类型** | 1-2周 | `CollectTaskType.DAILY_DIGEST` + `WebCollectorAsyncExecutor` |
| Phase 5 | 自动优化引擎（覆盖度评估→策略生成→反馈循环） | 2-3周 | `optimization/evaluator.py` + `strategy.py` |
| Phase 6 | 信息茧房突破（来源多样性/观点平衡/跨语言） | 1-2周 | `optimization/bubble_breaker.py` |
| Phase 7 | 定时调度（APScheduler每日自动生成日报） | 1周 | `task/scheduler.py` |
| Phase 8 | 独立项目拆分 | 2周 | 目录重构 + Docker独立镜像 |

**Phase 4-5是当前重点**：日报是自动优化引擎的第一个真实用例，每次生成都让系统更聪明。

---

## 七、关键设计决策

### 7.1 为什么全部走搜索引擎，不维护独立数据源？

| 方案 | 维护成本/月 | 失效风险 |
|------|------------|---------|
| 维护40+独立数据源（RSS/API/爬虫） | 2-3人天 | 高（每月2-5个失效） |
| 搜索引擎+AI关键词扩展 | 0.5人天 | 极低 |

搜索引擎是通用数据源，永远不会"失效"。AI关键词扩展自动适配语境，无需为每个数据源写解析器。

### 7.2 为什么三层去重够用了？

实测覆盖度：
- URL精确去重：覆盖80%的重复（同一URL多次出现）
- SimHash：覆盖15%的重复（内容改写/转载）
- 标题Jaccard：覆盖4%的重复（标题高度相似的转载）
- **合计覆盖99%**

不引入TF-IDF语义相似度和LDA聚类：计算成本高、对短文本效果差、需要人工调参。

### 7.3 自动优化的成本控制

| 项目 | Token消耗 | 成本(按Qwen) |
|------|-----------|-------------|
| 覆盖度评估 | ~800 tokens | ¥0.003 |
| 策略生成 | ~600 tokens | ¥0.002 |
| 3轮完整循环 | ~4200 tokens | ¥0.015 |
| 每日10个任务 | ~42K tokens | ¥0.15/天 |

**结论**：自动优化引擎AI调用成本极低，每天约0.15元，完全可接受。

---

## 八、与竞品对比

| 维度 | agents-radar | arxiv-digest | **WebCollector v3** |
|------|-------------|-------------|---------------------|
| **数据源** | 10源独立维护 | 1源(ArXiv) | **搜索引擎+AI扩展，零维护** |
| **定时调度** | GitHub Actions | GitHub Actions | **内置APScheduler** |
| **去重** | URL去重 | 无 | **三层去重（URL+SimHash+标题）** |
| **质量过滤** | 无 | 无 | **来源可信度+内容质量评分** |
| **自动优化** | ❌ | ❌ | ✅ **核心特色** |
| **茧房突破** | ❌ | ❌ | ✅ **核心特色** |
| **独立部署** | ❌ | ❌ | ✅ **支持** |

---

## 九、附录

### 附录A：术语表

| 术语 | 说明 |
|------|------|
| 覆盖度评估 | 对搜索结果多维度完整性的评估 |
| 信息茧房 | 算法或人为因素导致的信息单一化现象 |
| 反馈循环 | 基于结果评估自动调整策略的循环机制 |
| 策略知识库 | 长期积累的搜索策略效果记录 |

### 附录B：配置示例

```yaml
webcollector:
  # 自动优化
  auto_optimization:
    enabled: true
    target_coverage_score: 7.0
    max_feedback_rounds: 3

  # 信息茧房突破
  bubble_breaker:
    enabled: true
    min_source_diversity: 0.6
    cross_language_search: true

  # 日报配置
  daily_digest:
    enabled: true
    cron: "0 8 * * 1-5"           # 工作日8点
    sections:
      - name: "news"
        keyword: "科技新闻"
        time_range: "day"
        max_items: 5
      - name: "articles"
        keyword: "技术博客"
        time_range: "week"
        max_items: 3

  # LLM
  llm:
    provider: "dashscope"
    model: "qwen-plus"
    api_key: "${DASHSCOPE_API_KEY}"
```
