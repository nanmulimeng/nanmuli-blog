# B13 AI 骨架 AiService/NoOp 排查报告

> **模块编号**：B13
> **排查范围**：AI 领域端口 `AiService`、空实现 `NoOpAiService`、`ArticleEventHandler` 异步事件订阅、`article_vector` 表落地缺口、`ai_generation` 死表、Java 侧 AI 配置（`crawler.ai.*` 经 `sys_config`）、pgvector 依赖
> **基线 commit**：`6ae930098405f4d0553d96a852f3345d0f39682e`
> **工作区状态**：脏（工作区有未提交改动，但**均与本模块无关**：`ConfigRepositoryImpl.java`、`WebCollectPageMapper.java`、`crawler-service/*`、`deploy/README.md`、`risk-register.md`、`release-gate.ps1`、新增 webcollector 测试目录）。本模块文件（`AiService.java`/`NoOpAiService.java`/`ArticleEventHandler.java`/`AsyncConfig.java`）均干净。
> **排查日期**：2026-06-23
> **排查人**：B13 排查 agent
> **状态**：待复核

---

## 模块概览

**职责**：声明"后端直接调用 AI 提供商"的领域端口（生成标签/摘要/向量/优化标题），并通过发布事件触发异步增强。当前实现为空壳（NoOp），真实 AI 调用全部迁移到 Python crawler 侧。

**关键文件**：
- `backend/src/main/java/com/nanmuli/blog/domain/ai/AiService.java:10` —— AI 领域端口接口，4 个方法全 `CompletableFuture`
- `backend/src/main/java/com/nanmuli/blog/infrastructure/ai/NoOpAiService.java:15` —— 唯一实现，4 个方法返回空（`List.of()` / `""` / `float[0]`）
- `backend/src/main/java/com/nanmuli/blog/application/event/ArticleEventHandler.java:20` —— 订阅 `ArticlePublishedEvent`，异步触发标签/摘要/向量（产物多数丢弃）
- `backend/src/main/java/com/nanmuli/blog/infrastructure/config/ai/AsyncConfig.java:37` —— `aiTaskExecutor` 线程池（core=2/max=5/queue=50）
- `backend/src/main/java/com/nanmuli/blog/domain/article/event/ArticlePublishedEvent.java:12` —— 事件类
- `deploy/db/init-scripts/schema.sql:529-576` —— `ai_generation` + `article_vector` 表与 ivfflat 索引（schema 归 B15，本报告引用）

**对外接口 / 依赖**：
- 对外：无 Controller，纯内部端口；事件由 `ArticleAppService.create()` 发布（`ArticleAppService.java:128`）
- 依赖：`article` 表（读摘要、读内容）、`article_vector` 表（**未建 Repository**）、`ai_generation` 表（**未建 Repository**）、pgvector 0.1.4（**未使用**）、`aiTaskExecutor` 线程池（B17）、`crawler.ai.*` 配置（**Java 业务代码不读**，仅 `SystemConfigInitializer` 种子写入）

**已读文件清单**：
- `backend/src/main/java/com/nanmuli/blog/domain/ai/AiService.java` —— 通读（45 行）
- `backend/src/main/java/com/nanmuli/blog/infrastructure/ai/NoOpAiService.java` —— 通读（40 行）
- `backend/src/main/java/com/nanmuli/blog/application/event/ArticleEventHandler.java` —— 通读（97 行）
- `backend/src/main/java/com/nanmuli/blog/infrastructure/config/ai/AsyncConfig.java` —— 通读（69 行）
- `backend/src/main/java/com/nanmuli/blog/domain/article/event/ArticlePublishedEvent.java` —— 通读
- `backend/src/main/java/com/nanmuli/blog/application/article/ArticleAppService.java` —— 片段（`create` 事件发布 `:95-138`、`update` 无事件 `:149-208`）
- `backend/src/main/java/com/nanmuli/blog/infrastructure/config/initializer/SystemConfigInitializer.java` —— 通读（AI 配置仅种子写入 `:42-49`）
- `backend/src/main/java/com/nanmuli/blog/domain/article/Article.java` —— 片段（字段/`@Version`）
- `deploy/db/init-scripts/schema.sql:525-577` —— `ai_generation` + `article_vector` 表定义
- 仅 grep：`AiService`/`ArticlePublishedEvent`/`article_vector`/`ai_generation`/`optimizeTitle`/`crawler.ai`/`pgvector` 全仓引用

**主模块归属**：**B13 是 AI 空壳链路主模块**（§8.6），深查全貌。下列共享对象在本报告定性：
- **X02-07**（article_vector 零 Repository）→ 在本报告定性严重度与修复方向（B13-04）
- **B15-11**（ai_generation 死表）→ 在本报告定性 Java 侧零引用（B13-03）
- **B01-02**（草稿→发布不触发事件致 AI 断裂）→ 在本报告记 AI 视角影响（B13-06）
- **X05-08**（架构图把 NoOp 画成活跃）→ 在本报告给 Design 定性（B13-08）
- pgvector 0.1.4 → X02-12/B15-13 已记版本，本报告补"Java 侧零使用"视角（Deps 节）

---

## `[Bug]` 代码正确性与潜在缺陷

> 排查范围：`AiService`/`NoOpAiService`/`ArticleEventHandler` 全文、`ArticleAppService` 事件发布点、`AsyncConfig` 线程池、`crawler.ai.*` 配置读写链。

### [P3] [Bug] `AiService.optimizeTitle()` 端口方法零调用方，是死接口   <!-- 编号：B13-01 -->
- **定位**：`backend/.../domain/ai/AiService.java:44`（声明）、`backend/.../infrastructure/ai/NoOpAiService.java:36`（空实现）
- **现象**：`AiService` 声明 4 个方法（`generateTags`/`generateSummary`/`generateEmbedding`/`optimizeTitle`），但全仓 grep `optimizeTitle` 仅命中端口声明 + NoOp 实现，**无任何业务调用方**。其余 3 个方法均被 `ArticleEventHandler` 调用（`ArticleEventHandler.java:36/50/63`）。
- **影响**：低。死接口本身无害（NoOp 返回 `""`），但暴露端口设计未与消费方对齐——"优化标题"功能从未接入 UI 或业务流程，是 YAGNI 式的预留。
- **根因/分析**：早期端口设计时按"AI 能力全集"声明（标签/摘要/向量/标题优化），但只接了 3 个消费点。结合 git 历史（见 B13-02），Java AI 已迁 Python，这 4 个方法整体都不会再被实现，`optimizeTitle` 连形式上的消费都没有。
- **修复方向**：随 B13-02 决策一并处理——若废弃 Java AI 端口，整接口删除（连带 NoOp）；若保留端口，至少删除 `optimizeTitle` 减少误导。改动面：**小**。
- **关联**：[[B13-02]] / 横向主题"AI 空壳链路"

---

## `[Security]` 安全漏洞

> 排查范围：AI 链路是否有密钥泄漏、`crawler.ai.api_key` 加密落库、异步事件是否泄漏内容、`@Async` 异常是否吞掉敏感信息。本模块未发现 Security 级别问题。

本模块不直接处理鉴权、外部输入、文件上传。`crawler.ai.api_key` 经 `SystemConfigInitializer` 写入 `sys_config`，`is_encrypted=true`（`init.sql:983`、`SystemConfigInitializer.java:44-45`），加密逻辑归 **B07（AesEncryptor）** 深查，本报告只确认"声明了加密"。

`ArticleEventHandler` 异步处理时日志记录了文章 `title`/`articleId`（`ArticleEventHandler.java:32/39/53/66`），但 `title` 是公开字段、未记录 `content`/摘要原文，无敏感信息泄漏。

**未发现**本模块特有的 Security 漏洞。

---

## `[Arch]` 架构与技术债

> 排查范围：Java AI 端口/表/事件链路的整体落地状态、双轨（Java NoOp vs Python 真实）、配置消费链、与已知全局结论（§9 [Arch/P1] Java AI NoOp）的关系。

### [P1] [Arch] Java AI 端口/表/事件链路全建但实现全 NoOp，且 git 历史证实是"已迁移走"而非"待实现"   <!-- 编号：B13-02 -->
- **定位**：
  - `backend/.../domain/ai/AiService.java:10`（端口，4 方法全 `CompletableFuture`）
  - `backend/.../infrastructure/ai/NoOpAiService.java:15`（唯一 `@Service` 实现，4 方法返回空）
  - `backend/.../application/event/ArticleEventHandler.java:29-79`（订阅事件 → 调 3 个 AI 方法 → 标签丢弃/摘要仅空时写/向量丢弃）
  - git 历史（`git log` on 三个文件）：
    - `4b1dada refactor(backend): 架构调整 - 引入领域事件、AI防腐层和Redis缓存`（建端口）
    - `9e14868 refactor(ai): 禁用Spring AI功能并添加序列化支持`（禁用）
    - `0374b1b refactor(backend): AI能力迁移Python，移除Java本地AI实现`（**关键：AI 迁 Python，Java 移除真实实现**）
    - `8cdcab6 chore(backend): 补充提交AI模块空实现Bean`（补 NoOp 占位 Bean）
- **现象**：`AiService` 端口存在、`NoOpAiService` 作为 `@Service` 默认注入、`ArticleEventHandler` 注入 `AiService` 并在事件触发时调 3 个方法、`article_vector`/`ai_generation` 表和 ivfflat 索引全建、`aiTaskExecutor` 线程池配置完整。**但所有 AI 方法返回空**：标签→`List.of()`、摘要→`""`、向量→`float[0]`。git 历史明确显示这是**主动迁移决策**（`AI能力迁移Python`），而非"骨架先行、实现待补"。
- **影响**：①读者（包括依赖文档做决策的人、排障者）误以为后端有 AI 能力，实际整条"发布文章→AI 增强"链路在 Java 侧无任何功能产出；②`ArticleEventHandler` 每次发布文章都会占用 `aiTaskExecutor` 线程跑 3 个 NoOp future + 6 条 log（含 3 条 `log.warn` "暂未持久化"），虽然成本低但是纯噪音；③与 Python 侧（crawler `ai/organizer.py` 等，归 C05）形成"Java AI vs Python AI 双轨"，维护者需理解"Java 的 AI 是死的、真的在 Python"才能正确排障。
- **根因/分析**：这是**已执行的架构决策**（不是未完成），但决策执行不彻底——把真实实现删了，却保留了端口、NoOp Bean、事件订阅、表、索引、线程池、配置，形成完整但空转的骨架。对照计划 §9 已知线索 [Arch/P1]，本报告补充的关键新细节是 **git 历史证明"迁移走"而非"待实现"**，这改变了 Design 判定（见 B13-08）。
- **修复方向**（按决策分叉）：
  - **方向 A（推荐，对齐既成事实）**：废弃 Java AI 端口。删除 `AiService`/`NoOpAiService`/`ArticleEventHandler`，DROP `article_vector` + `ai_generation` 表与 ivfflat 索引，从 `sys_config` 移除 Java 不读的 `crawler.ai.*`（仅保留 Python 侧消费）。改动面：**中**（删代码 + schema migration，需确认 Python 侧不依赖）。
  - **方向 B（保留端口留扩展）**：保留 `AiService` 接口作为"未来后端直连 AI"的防腐层，但删除 `ArticleEventHandler` 中明显无意义的 NoOp 调用日志噪音，给接口加 `@Deprecated` 或文档注释明确"当前由 Python 侧承担"。改动面：**小**。
  - 无论 A/B，都不应维持"端口+事件+表+索引全建却零产出"的当前状态。
- **关联**：[[B13-01]] / [[B13-03]] / [[B13-04]] / [[B13-08]] / 横向主题"AI 空壳链路" / 已知线索 §9 [Arch/P1] Java AI NoOp（本条补 git 历史新证据）

### [P3] [Arch] `ArticleEventHandler` 标签与向量产物无落地，摘要落地的 `updateArticleSummaryIfNeeded` 因 NoOp 永不触发   <!-- 编号：B13-05 -->
- **定位**：`backend/.../application/event/ArticleEventHandler.java:36-74`（标签 `:36-47`、摘要 `:50-60`、向量 `:62-74`）、`updateArticleSummaryIfNeeded` `:84-96`
- **现象**：
  - 标签：`generateTags` 返回 `List.of()` → `.thenAccept(tags -> if(!tags.isEmpty()))` 条件不成立 → 走不到 `log.warn("暂未持久化")` 分支，但标签为空 → 文章永不获得 AI 标签。
  - 摘要：`generateSummary` 返回 `""` → `if(!summary.isEmpty())` 不成立 → `updateArticleSummaryIfNeeded` **从不被调用**。该方法读 `articleRepository` 并在摘要为空时写入——逻辑写对了，但 NoOp 永远让它进不来。
  - 向量：`generateEmbedding` 返回 `float[0]` → `if(embedding.length>0)` 不成立 → 永不进 `log.warn` 分支，向量永不持久化。
- **影响**：①三段"生成→检查→落地"代码逻辑完整，但全部因 NoOp 返回空值而在第一个 `if` 处短路，从功能角度看三段都是死代码；②真正生效的摘要是 `ArticleAppService.create():97` 和 `update():176` 调的 `markdownUtil.generateSummary()`（非 AI，纯文本截断，`MarkdownUtil.java:109`），与 `ArticleEventHandler` 的 AI 摘要路径完全无关。
- **根因/分析**：EventHandler 假设 `AiService` 会返回真实结果，写了完整的 `thenAccept` 链。NoOp 实现后这些链全部短路，但代码没删。属 B13-02 决策执行不彻底的细节表现。
- **修复方向**：随 B13-02 决策处理——方向 A 删整个 EventHandler；方向 B 至少删除三段 NoOp 永不触发的 `thenAccept` 链，改为单条 `log.debug("AI disabled, skip")`。改动面：**小**。
- **关联**：[[B13-02]] / [[B13-04]] / 已知线索 §9（标签/向量无落地）

### [P3] [Arch] `crawler.ai.*` 配置写入 `sys_config` 但 Java 业务代码零消费，仅 SystemConfigInitializer 种子写入   <!-- 编号：B13-07 -->
- **定位**：
  - 写入：`backend/.../infrastructure/config/initializer/SystemConfigInitializer.java:42-49`（从 env `AI_ENABLED`/`AI_API_KEY`/`AI_BASE_URL`/`AI_MODEL` 种子到 `crawler.ai.*`，`is_encrypted=true` 仅 `api_key`）
  - 通用读写：`ConfigAppService`（通用配置 CRUD，非 AI 专属）
  - **业务消费**：grep `crawler.ai`/`@Value(".*ai\."` 在 `backend/src/main/java` 业务代码中**零命中**（仅命中 `AsyncConfig` 的 `async.executor.ai.*`，那是线程池配置不是 AI 提供商配置）
- **现象**：`crawler.ai.*`（共 18 个 key，含 `enabled`/`api_key`/`base_url`/`model`/`temperature`/`max_tokens` 等）存在于 `sys_config` 表，Java 侧仅做"env→sys_config"的种子写入和通用配置管理界面读写，**没有任何 Java 代码读取这些 key 去 call AI 提供商**。真实消费方是 Python crawler（`crawler-service/` 经 backend_config 拉取，归 C11）。
- **影响**：①形成"配置在 Java 管、消费在 Python"的跨服务配置链，增加了理解成本（改 AI 配置要去 Java 管理界面，生效在 Python）；②`crawler.ai.model` 的默认值在 `init.sql:993` 是 `deepseek-v4-pro`、`V1_12:217` 也是 `deepseek-v4-pro`，但 env `.env.example` 是 `qwen-plus`——三处不一致归 **X06-01** 深查，本条只记"Java 不消费"这一 B13 视角。
- **根因/分析**：这是与 B13-02 同源的决策结果——AI 迁 Python 后，配置管理仍留在 Java `sys_config`（统一配置中心定位），Python 通过 `backend_config.py` 回拉。设计上合理（配置集中），但 Java 侧保留了已不属于自己的 AI 配置项，且 `SystemConfigInitializer` 仍在启动时种子写入，给人"Java 在用"的错觉。
- **修复方向**：配置集中管理本身合理，**不建议**把 `crawler.ai.*` 从 Java 移走。但建议：①在 `sys_config.group_name='crawler'` 的注释里明确"由 Python crawler 消费，Java 仅管理"；②若走 B13-02 方向 A（废弃 Java AI 端口），保留配置不动即可。改动面：**小**（文档/注释）。
- **关联**：[[B13-02]] / [[X06-01]]（AI_MODEL 三处不一致）/ 横向主题"配置一致性"

---

## `[Deps]` 依赖升级与版本

### 本模块依赖清单（基于声明文件，未翻依赖源码）

| 依赖 | 版本 | 声明位置 | 已知风险/可升级 | 备注 |
|---|---|---|---|---|
| com.pgvector:pgvector | 0.1.4 | `backend/pom.xml:23,54-56` | 偏旧，可升至 0.3.x | **Java 业务代码零使用**（见 B13-04） |

> 排查范围：本模块 AI 相关依赖。其余 Spring/MyBatis 等通用依赖归各基础模块（B14/B16）。

### [P3] [Deps] pgvector 0.1.4 偏旧，且 Java 侧零使用   <!-- 编号：B13-13 -->
- **定位**：`backend/pom.xml:23`（`<pgvector.version>0.1.4</pgvector.version>`）、`backend/pom.xml:54-56`（声明）、`backend/src/main/java` grep `pgvector`/`com.pgvector` **零业务命中**
- **现象**：声明了 pgvector Java 绑定 0.1.4，但全 Java 业务代码无任何 `import com.pgvector.*`。`article_vector` 表（schema.sql:557）用了 `vector(1536)` 类型，但 Java 侧无 Repository/实体操作它（X02-07）。
- **影响**：当前零功能影响（依赖在 classpath 但不调用）。版本偏旧（0.1.4 vs 最新 0.3.x），未来若落地 AI 推荐（B13-02 方向 B），旧绑定可能缺 HNSW 索引支持、性能优化、API 改进。
- **根因/分析**：随 B13-02 决策——AI 迁 Python 时，pgvector Java 绑定未一并移除，留在 pom 里。X02-12/B15-13 已记版本风险，本报告补"Java 侧零使用"确认。
- **修复方向**：随 B13-02 方向 A 一并从 pom 移除；若方向 B 则升至 0.3.x。改动面：**小**。
- **关联**：[[B13-02]] / [[B13-04]] / [[X02-12]] / [[B15-13]]

---

## `[Design]` 功能设计合理性

> **审视结论**：

1. **场景适配（§2.5-1）**：单人维护的技术博客 + 每工作日 AI 日报场景下，"后端直连 AI 做文章标签/摘要/向量"是**过度设计**——日报 AI 已经在 Python crawler 侧完整实现（C04/C05），文章摘要用 `MarkdownUtil` 纯文本截断已够用（`ArticleAppService.java:97/176`），向量推荐对单人博客价值极低。这套 Java AI 骨架对应的场景，要么已被 Python 侧覆盖，要么不是当前优先级。
2. **闭环完整性（§2.5-2）**：即便 NoOp 不空，闭环也不完整——标签生成后无标签系统保存（`ArticleEventHandler.java:40` TODO 自认"标签系统尚未实现"）、向量生成后无 Repository（`:67` TODO 自认"article_vector 表和 Repository 开发后保存"）。闭环缺口不是"少 AI 实现"，而是"少标签模块 + 少向量 Repository"，AI 实现只是其中一环。
3. **MVP 假设检验（§2.5-4）**：README/CLAUDE 声称"自动优化系统 MVP Beta"——这个 MVP **不包括** Java AI 骨架（真实 AI 在 Python）。但 AGENTS.md/CLAUDE.md 架构图把 `Backend --> AI` 画成活跃链路（X05-08），会让人误以为"文章 AI 增强"是 MVP 能力之一，实际跑起来**该链路零产出**。这是"看起来能用实则跑不通"的半成品呈现。
4. **废弃/预留判定（任务核心问题）**：**git 历史给出明确答案——这是"已迁移走后留下的空壳"，不是"待实现的未来计划"**。提交 `0374b1b refactor(backend): AI能力迁移Python，移除Java本地AI实现` 清楚表明 Java AI 曾经真实存在、后被主动移除、Python 取而代之。因此当前 Java AI 骨架的准确属性是**"迁移残留"**（abandoned-but-not-cleaned），而非"预留扩展点"（reserved-for-future）。端口若要留作防腐层，应显式标注；现状是既不实现也不清理的悬空态。

### [P1] [Design] Java AI 骨架应定性为"迁移残留"而非"预留扩展"，建议清理而非补实现   <!-- 编号：B13-08 -->
- **定位**：整条 AI 空壳链路（B13-02）+ 架构图叙事（X05-08）
- **现象**：见 B13-02 + 审视结论第 4 点。git 提交 `0374b1b` 明确"AI 能力迁移 Python，移除 Java 本地 AI 实现"，证明 Java AI 是被替代而非待建。
- **影响**：定性决定了修复方向——若是"预留"，则应补实现或至少保持骨架整洁；若是"迁移残留"（本报告结论），则应**清理**（删 Java 端口 + 表 + 事件 + 线程池配置），让 schema 和代码与"AI 在 Python"的事实一致。当前悬空态持续越久，读者误解、维护者困惑、配置漂移（如 X06-01 AI_MODEL 三处不一致）累积越多。
- **建议方向**：**采纳方向 A（废弃清理）**，理由：①Python 侧 AI 已完整且在跑；②单人博客无需后端 AI 推荐；③清理后 schema 噪音大幅降低（删 article_vector/ai_generation 两表 + ivfflat 索引）；④消除"双轨 AI"的认知负担。**不建议方向 B（补 Java 实现）**，除非未来明确要"后端独立 AI 能力脱离 crawler"，目前无此需求。改动面：**中**（见 B13-02）。
- **关联**：[[B13-02]] / [[X05-08]] / 横向主题"AI 空壳链路"

### [P4] [Design] `ArticlePublishedEvent` 仅在 `create()` 发布，草稿→发布路径 AI 断裂（与 B01-02 协同）   <!-- 编号：B13-06 -->
- **定位**：`backend/.../application/article/ArticleAppService.java:128`（`create` 发布事件，受 `article.isPublished()` 守卫 `:127`）、`ArticleAppService.java:149-208`（`update` 方法**无** `publishEvent(ArticlePublishedEvent)`）
- **现象**：`ArticlePublishedEvent` 全仓仅 1 处发布（`create():128`）。`update()` 方法（`:149-208`）即使把文章从草稿（status=2）改为发布（status=1，`:181-186`），也**不发布** `ArticlePublishedEvent`。
- **影响**：草稿→发布是最自然的写作流程，此路径下 `ArticleEventHandler` 不被唤醒。当前因 NoOp（B13-02）影响被完全掩盖（AI 本就空），**但一旦 B13-02 走方向 B 补真实 AI 实现，此 bug 立即显现**为"草稿发布后无 AI 增强"。属 B01-02 的 AI 视角佐证，B01 已详记。
- **建议方向**：随 B13-02 决策——若方向 A（废弃 Java AI），本 bug 自动消失（EventHandler 删了）；若方向 B（补实现），必须同步在 `update()` 的 `wasPublished → isPublished` 状态转换处补发事件。改动面：**小**（单方法加事件发布，归 B01）。
- **关联**：[[B13-02]] / [[B01-02]]（B01 主记草稿→发布事件断裂）/ 横向主题"AI 空壳链路"

### [P2] [Arch] `article_vector` 表 + ivfflat 索引全建但零 Repository，向量从不写入（X02-07 在此定性）   <!-- 编号：B13-04 -->
- **定位**：`deploy/db/init-scripts/schema.sql:557-576`（article_vector 表 + `content_vector vector(1536)` + `summary_vector vector(1536)` + ivfflat 索引 `:576`）、`backend/src/main/java` grep `ArticleVector`/`INSERT INTO article_vector` **零业务命中**、`ArticleEventHandler.java:62-74`（注释自认"向量存储模块尚未实现，待article_vector表和Repository开发后保存"）
- **现象**：PG 建了 `article_vector` 表（含两个 1536 维向量列）+ ivfflat 余弦相似度索引 + `article_id` 唯一约束，但 Java 侧**无对应实体、Mapper、Repository**。`ArticleEventHandler` 调 `aiService.generateEmbedding()` 拿到向量后，注释写"暂未持久化"直接丢弃（且 NoOp 连向量都不产生）。
- **影响**：①表和 ivfflat 索引空转，schema 复杂度噪音；②**ivfflat 索引在空表上创建**——pgvector 官方要求"数据导入后再建索引"才能正确聚类（项目自带文档 `docs/postgresql_pgvector_tutorial_supplemented.md:907-926` 明确此点），即使后续补 Repository 填数据，召回质量也极差，必须 REINDEX；③结合 B13-02，整条"发布→向量→语义推荐"链路空壳。
- **根因/分析**：属 B13-02 决策的 schema 侧残留——AI 迁 Python 时，Java 侧的 article_vector 表未随实现一并移除。X02-07 已记此条，本报告作为 AI 空壳链路主模块，定性为 **P1**（与 B13-02 同级，因为它是 B13-02 决策在 schema 层的具体表现，清理时必须一并处理）。
- **修复方向**：随 B13-02 方向 A 一并 DROP `article_vector` 表 + ivfflat 索引；若方向 B 落地 AI 推荐，补 `ArticleVectorRepository` + 实体 + **在数据批量导入后 REINDEX**。改动面：**小**（DROP）/ **大**（补全链路 + 重建索引）。
- **关联**：[[B13-02]] / [[X02-07]]（X02 已记，本报告作为主模块确认 P1 定级）/ [[B13-08]] / [[B15-11]]（init.sql 缺此表，三轨漂移）/ 横向主题"AI 空壳链路" / "schema 漂移"

### [P2] [Arch] `ai_generation` 表为死表：schema.sql 有定义但全代码零 `AiGeneration` 类引用（B15-11 在此定性 Java 侧）   <!-- 编号：B13-03 -->
- **定位**：`deploy/db/init-scripts/schema.sql:529-554`（`ai_generation` 表定义，含 `article_id`/`type`/`prompt`/`content`/`tokens_used`/`model`/`status`/`error_msg` + 3 个索引）、`backend/src/main/java` grep `ai_generation`/`AiGeneration` **零业务命中**、`init.sql` grep `ai_generation` **零命中**（init.sql 完全缺此表，三轨漂移归 B15-05）
- **现象**：schema.sql 定义了 AI 生成记录表（用于记录每次 AI 调用的 prompt/输出/token/模型/成功与否），注释类型含 `tags`/`summary`/`recommend`/`content`，但 Java 侧无任何 `AiGeneration` 实体/Mapper/Repository。`ArticleEventHandler` 调 AI 后**不记录**到 `ai_generation`（既无 Repository可写、NoOp 也无真实调用可记）。
- **影响**：①死表占 schema 空间与认知负担；②若未来要审计"哪些文章 AI 生成了什么、用了多少 token"，当前无任何数据（因为从未写入）；③与 article_vector（B13-04）同为 AI 骨架的 schema 残留，性质相同。
- **根因/分析**：与 B13-04 同源——AI 迁 Python 时，`ai_generation` 设计用于"Java 调 AI 时记录"，迁移后 Java 不再调 AI，此表失去写入方，沦为死表。B15-11 已记，本报告补充 Java 侧零引用确认 + 与 B13-02 决策绑定。
- **修复方向**：随 B13-02 方向 A 一并 DROP `ai_generation` 表；若 Python 侧需要 AI 调用审计表，应单独设计（Python 侧已有自己的 SQLite 记录，归 C09）。改动面：**小**（DROP）。
- **关联**：[[B13-02]] / [[B15-11]]（B15 主记，本报告确认 Java 视角）/ [[B13-04]] / 横向主题"AI 空壳链路" / "schema 漂移"

### [P2] [Arch] `AiService` 端口仅 `NoOpAiService` 一个实现，无 `@Primary`/`@ConditionalOnProperty` 切换机制   <!-- 编号：B13-09 -->
- **定位**：`backend/.../infrastructure/ai/NoOpAiService.java:14`（`@Service`，无 `@ConditionalOnProperty`/`@Profile`）
- **现象**：`AiService` 端口唯一的 `@Service` 实现是 `NoOpAiService`，直接 `@Service` 注解无任何条件守卫。`ArticleEventHandler` 通过构造注入 `AiService`（`ArticleEventHandler.java:22`），Spring 启动时只会注入 NoOp。
- **影响**：①未来若要补真实实现（B13-02 方向 B），需手动切换或加 `@ConditionalOnProperty`，否则两个 `@Service` 同型 Bean 冲突；②当前 NoOp 无条件激活，意味着即使配置了真实 AI 凭证，Java 侧也不会调用——这与"配置 `crawler.ai.enabled=true` 就启用 AI"的直觉不符（直觉针对 Python，但读者易误解为 Java 也启用）。
- **根因/分析**：迁移决策后，NoOp 作为"占位 Bean"无条件存在，没设计切换机制。属 B13-02 决策执行不彻底的 IoC 细节。
- **修复方向**：随 B13-02 方向 A 删除整个端口即解决；若方向 B 补真实实现，应加 `@ConditionalOnProperty(name="ai.backend.enabled", havingValue="true", matchIfMissing=false)` 给真实实现、NoOp 作为 fallback。改动面：**小**。
- **关联**：[[B13-02]] / [[B13-08]]

---

## 模块小结

### 严重度统计

| 级别 | 数量 | 条目编号 |
|---|---|---|
| P0 | 0 | — |
| P1 | 2 | B13-02、B13-08 |
| P2 | 3 | B13-04、B13-03、B13-09 |
| P3 | 4 | B13-01、B13-05、B13-07、B13-13 |
| P4 | 1 | B13-06 |

### Top 风险（本模块最该先看的 ≤3 条）

1. **B13-02 + B13-08（AI 空壳链路定性）** —— git 历史证明 Java AI 是"迁移残留"而非"待实现"，整条端口/表/事件/索引/线程池全建但零产出，应清理而非补实现。这是本模块的**决策性结论**，直接决定 X02-07/B15-11/B13-01/03/04/05/06/09/13 九条下游条目的修复路径。
2. **B13-04（article_vector 零 Repository + ivfflat 空表索引）** —— 即使补全 Repository，ivfflat 索引也因空表创建而召回质量受损，必须 REINDEX；schema 噪音与召回质量双重风险。
3. **B13-07（配置双轨）** —— `crawler.ai.*` 在 Java 管、Python 消费，配合 X06-01 AI_MODEL 三处不一致，跨服务配置链的理解成本高。

### 修复优先级建议

- **立即（P1）**：B13-02 + B13-08——**先做定性决策**（废弃 vs 保留），这是九条下游条目的前置。建议方向 A（废弃清理，对齐 git 历史已执行的迁移）。
- **计划（P2）**：决策后按方向落地——方向 A 则 DROP `article_vector`/`ai_generation` 两表 + ivfflat 索引（B13-04/B13-03）+ 删 NoOp 切换机制（B13-09）；方向 B 则补 Repository/实体 + REINDEX + 加 `@ConditionalOnProperty`。
- **择机（P3/P4）**：B13-01（删 optimizeTitle 死方法）、B13-05（删 EventHandler 死代码链）、B13-07（配置注释明确消费方）、B13-13（pgvector 0.1.4 升级或移除）、B13-06（草稿→发布事件断裂，随决策自动消解或需在 update 补发）。

### 排查盲区 / 待复核

- **[需查证] B13-08**：git 提交 `0374b1b refactor(backend): AI能力迁移Python` 的完整 commit body 与同期 crawler 改动未展开，"迁移决策"的边界（是否明确写了"保留 Java 端口作防腐层"）需查 commit body 原文确认。本轮仅凭 commit message 推断为"迁移残留"。
- **[需查证] B13-07**：`crawler.ai.*` 配置是否在 Java 管理界面有专属展示/编辑入口（`config` admin 页面归 F05/B07），以及 Python `backend_config.py` 拉取这些 key 的完整映射未逐项核对（归 C11）。本报告只确认"Java 业务代码零消费"。
- **[需查证] B13-04**：`article_vector` 表的 `keywords JSONB` 列（schema.sql:562）是否曾计划由"标签系统"（CLAUDE.md 声称"未上线"）写入——即向量表与标签系统的设计耦合关系，需查早期设计文档。
