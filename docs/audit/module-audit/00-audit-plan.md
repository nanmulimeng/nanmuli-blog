# Nanmuli Blog 全模块地毯式排查计划

> 版本：v1.1（v1.0 → v1.1：补基线状态/命令边界/不查依赖源码/编号规则/主模块归属/risk-register 关系/契约主题/prompt 骨架/安全清单/改动面/工作量）
> 制定日期：2026-06-23
> 维护者：审计执行 Agent
> 关联：本目录 `module-audit/` 与既有 `docs/audit/full-project-risk-register.md` 互补——关系见 §1.5。

---

## 1. 目标与原则

### 1.1 目标

对 Nanmuli Blog（博客基础 + Web 采集器 + AI 技术日报 + 自动优化闭环的复合系统）进行**地毯式、按小模块**的排查，找出隐藏的问题与需要升级/调整的地方，产出**每模块独立报告 + 总索引页**，为后续修复排期提供分级清晰、定位精确、方向明确的依据。

### 1.2 原则（不可妥协）

1. **只读诊断**：本轮**不改任何业务代码**，不跑重型验证（构建/测试/smoke 仅在必要时用于佐证单一结论），不引入新依赖。
2. **证据先行**：每个发现必须有 `file:line` 定位或可复现的操作路径，禁止臆测。无法确认的标 `[需查证]`。
3. **统一格式**：所有模块报告严格遵循 [_template.md](./_template.md)，严重度与维度标签口径一致，便于横向汇总。
4. **最小必要**：聚焦"问题与修复方向"，不写具体补丁代码（修复方案在后续单独评估）。
5. **保护现状**：不评判既有设计的好坏对错，只记录"在真实使用场景下是否合理、是否需要调整"。

### 1.3 不做什么（范围与命令边界）

**不修改**：业务代码、配置文件、数据库、CI、依赖声明。仅允许写本目录（`docs/audit/module-audit/`）下的报告与索引。

**命令边界（固化，agent 不得自行扩大）**：

| 允许 | 禁止 |
|---|---|
| `grep` / `rg` / `Glob` 搜索 | `mvn test` / `mvn compile` / `mvn verify` |
| `Read` 读取项目文件 | `python -m pytest` / 任何 pytest 调用 |
| 单文件语法/类型检查（如 `npx tsc --noEmit <file>`、`python -m py_compile <file>`）**仅用于佐证单一结论** | `npm run build` / `npm run lint` / `vite build` |
| `git log` / `git show` / `git blame`（理解历史） | `docker compose ...` / 任何容器构建运行 |
| 读取依赖**声明文件**（pom.xml / package.json / requirements.txt / Dockerfile / compose / lock 文件） | 外网请求（`curl`/`pip install`/`npm install`/`WebFetch` 探测外部服务） |
| | 深入依赖源码（`node_modules/` / `.venv/` / `~/.m2/`）—— **见 §1.3.1** |

**不重复已知结论**：已在上一轮调研报告确认的全局事实（Flyway 未集成、Java AI 是 NoOp、无 CI 等），模块报告里**只补充该模块视角的新细节**，不重复铺陈。

#### 1.3.1 不深入依赖源码

排查**只看自有代码 + 依赖声明文件**（pom.xml / package.json / package-lock.json / requirements.txt / Dockerfile / docker-compose.yml / lock 文件）。**不**进入：

- `frontend/node_modules/`
- `crawler-service/.venv/`
- `~/.m2/repository/`、`~/.gradle/`
- 任何第三方库的源码实现

依赖相关排查（`[Deps]` 维度）只基于：声明文件里的版本号 + 已知公开 CVE/废弃信息（来自 agent 训练知识或 `npm audit`/`pip-audit` 的**只读输出**，若需运行须先获授权）+ 项目中的使用方式。涉及"库内部行为"的判断标 `[需查证]`。

### 1.4 基线状态约定

- **审计基线 = 当前工作区状态（含未提交改动）**，不限于 HEAD。原因：工作区已有进行中的修改，忽略会导致结论对不上代码。
- **当前分支**：`codex/digest-generation-closure`，工作区有未提交改动（`backend/.../ConfigRepositoryImpl.java`、`WebCollectPageMapper.java`、`crawler-service/...` 多个、`deploy/README.md`、`docs/audit/full-project-risk-register.md`、`scripts/release/release-gate.ps1`，及新增 `backend/src/test/.../webcollector/`）。
- **每份报告必须记录**：①基线 commit SHA（`git rev-parse HEAD`）②工作区是否脏（`git status --porcelain` 非空则脏，列出涉及本模块的改动文件）③排查日期。
- **时效风险**：项目仍在活跃提交，报告可能较快过时。索引页记录审计基线 commit，复核前先 `git log` 确认代码未变。

### 1.5 与既有风险登记册的关系（防双轨漂移）

项目最大隐患之一就是 schema 双轨漂移；审计文档自己不能重蹈。明确**单向证据链**：

| 文档 | 角色 | 粒度 |
|---|---|---|
| `docs/audit/full-project-risk-register.md`（既有） | **汇总层 / 风险登记册** | 跨模块、主题级、面向决策 |
| `docs/audit/module-audit/<编号>-*.md`（本目录） | **证据层 / 详细排查** | 单模块、条目级、含 file:line |

**同步规则**：
1. 排查阶段，发现**只在模块报告里详细记录**（含证据）。
2. **全部 42 模块完成后**，协调者统一把 P0/P1 和跨模块主题**回写对齐**到 risk-register（更新既有条目状态、补充新条目、标注证据指向哪份模块报告）。
3. 排查进行中**不**边查边改 risk-register，避免半成品污染汇总层。
4. risk-register 既有的、本次复核仍成立的条目，模块报告里用"关联"字段反向指向，不重写。

---

## 2. 排查维度（5 大类 + 横向主题 + 标签）

每条发现打**一个主维度标签**。跨维度时按"**最严重后果类型**"定主维度（如"SQL 漏洞导致数据泄露"主维度是 `[Security]` 而非 `[Bug]`），次维度在"关联"字段标注。

### 2.1 `[Bug]` 代码正确性与潜在缺陷
查：逻辑错误、边界条件（空集合/越界/除零）、空指针与 Optional 误用、并发与共享状态、状态机非法流转、异常吞掉或传播错误、资源未释放（流/连接/锁）、事务边界错误、时区/字符编码、ID 精度（snowflake Long→前端 Number）、缓存失效与脏读。

### 2.2 `[Security]` 安全漏洞
通用查：越权、注入、SSRF、敏感信息泄露、鉴权绕过、密钥管理、文件上传、CSRF、不安全反序列化、Cookie 安全属性、限流可绕过。

**本项目技术栈特定重点**（agent 必须逐项覆盖）：

- **Sa-Token（Cookie 模式 + `is-concurrent=false` 单点登录）**：token 失效边界、`alone-redis`（db1）隔离是否被业务缓存污染、登出是否清干净、**路由拦截器规则是否漏配 admin 路径**（鉴权纯靠 URL 前缀是已知薄弱点）、`StpUtil` 直接调用点是否绕过拦截器。
- **MyBatis Plus**：`${}`（字符串拼接，SQLi 风险）vs `#{}`（预编译）误用、`QueryWrapper.apply()/last()` 的字符串拼接、分页 + 逻辑删除组合下的越权查询、乐观锁 `@Version` 是否真生效、`SELECT *` 投影泄漏。
- **Cookie + CSRF**：Sa-Token 用 Cookie 携带 token，管理端写操作有无 CSRF token 或 `SameSite=Lax` 兜底；CORS `allowCredentials` 与白名单是否配套。
- **CORS**：`CORS_ALLOWED_ORIGINS` 是否过宽（`*` + `allowCredentials`）、是否反射任意 Origin。
- **AES 加密（`AesEncryptor`）**：是否拒绝默认值/弱密钥、密文前缀 `{AES}`、IV 是否随机、敏感配置是否真加密落库 vs 明文。
- **SSRF**：crawler `ssrf_guard`（已声明**不防 DNS rebinding**）、backend `CrawlerTaskClient`/callback_url、用户可控 URL 的回环/保留地址过滤。
- **文件上传**：路径遍历、扩展名/MIME 双校验、md5 去重可否绕过、上传目录是否可执行。
- **跨服务双向 key**：`X-API-Key`（Java→Python）与 `X-Callback-Key`（Python→Java）强度、是否恒定时间比较、是否随请求日志泄漏。

### 2.3 `[Arch]` 架构与技术债
查：DDD 分层违反（领域层泄漏 MyBatis 注解、Controller 写业务）、上帝类/上帝服务（>500 行 AppService）、过度耦合、循环依赖、硬编码（域名表/降级链/过滤规则）、双轨/多轨漂移（schema 三轨、env 三处）、重复实现（keyword 优化循环 vs digest 优化循环）、隐式约定（`round_num=0` 语义）、可测试性差、缺失抽象。

### 2.4 `[Deps]` 依赖升级与版本
查：过时依赖与已知 CVE（基于声明文件 + 公开信息）、大版本升级路径（Spring Boot 3.3→3.4/4.x、Vue 3.4、Crawl4AI 0.8、Element Plus、Sa-Token、MyBatis Plus）、废弃 API 使用、Java/Python/Node 版本要求是否陈旧、构建产物提交（`dist/`、`.venv/`）、镜像基线与固定 tag。**约束**：只看声明文件，不翻依赖源码（§1.3.1）。

### 2.5 `[Design]` 功能设计合理性（重点维度）
**从真实使用出发审视，不是技术债视角。** 每个模块回答以下问题中**相关**的部分（**至少 2 个**）：

1. **场景适配**：单人维护的技术博客 + 每工作日 AI 日报场景下，该功能是过度设计还是过于简陋？
2. **闭环完整性**：功能是否形成完整闭环？哪一环缺人工干预入口（采集结果无法人工剔除/合并、日报不可编辑、配置无变更历史、优化建议无法人工覆盖）？
3. **可运维性**：故障时能否快速定位/恢复/回滚？有无必要运营工具（重试、手动修正、审计、告警）？
4. **MVP 假设检验**：README/CLAUDE.md 声称的能力真实跑起来是否成立？有无"看起来能用实则跑不通"的半成品？
5. **缺失功能**：基于真实使用，哪些"该有而没有"会导致体验断层？
6. **交互合理性**：前端流程是否符合真实习惯？有无反直觉或低效路径？
7. **单点与扩展**：为 ≤2 内部服务设计的假设，真实增长时哪里先成为硬阻塞？

**无问题时的写法**（强制）：Design 节即便无 P0–P3 发现，也**必须写 2–3 句审视结论**，并显式标注 `无需调整` 或列为 `[Design/P4]` 建议条目。禁止留空或硬凑问题。

### 2.6 横向检查主题（跨模块，汇总到索引页）

部分问题天然跨模块，不归属单一维度，作为**横向主题**在索引页统一追踪，各相关模块报告里只记本模块视角的发现并标注主题归属：

- **跨服务契约一致性**（最高优先横向主题）：前端 API 调用 ↔ 后端 Controller/DTO 字段；crawler callback ↔ backend InternalCallback 字段；crawler ↔ backend 配置 key 命名。**字段类型/必填/枚举值不对齐是 bug 高发区**。
- **鉴权机制一致性**：哪些接口靠 URL 前缀、哪些用了 `StpUtil`、有无漏网。
- **schema 漂移**：init.sql / migration / schema.sql 三轨差异（主模块 B15，其余引用）。
- **配置一致性**：env 三处、AI_MODEL 等（主模块 X06）。
- **AI 空壳链路**：NoOpAiService / ArticleEventHandler / article_vector（主模块 B13）。

---

## 3. 严重度分级标准

每条发现定一个严重度，**必须有判定依据**（影响面 + 触发条件），不接受"感觉严重"。

| 级别 | 名称 | 判定标准 | 处置建议 |
|---|---|---|---|
| **P0** | 阻断 Critical | 数据损坏/丢失、可被利用的安全漏洞、主链路不可用、生产事故风险 | 必须修，上线前阻断 |
| **P1** | 高 High | 功能性 bug、潜在数据不一致、明显安全薄弱点、会导致线上故障的设计缺陷 | 应尽快修 |
| **P2** | 中 Medium | 技术债、可维护性、边界场景异常、文档/配置漂移、测试缺失影响关键路径 | 计划修 |
| **P3** | 低 Low | 代码风格、轻微性能、可选优化、命名/注释 | 有空再修 |
| **P4** | 建议 Info | 功能设计优化建议、未来升级方向、非问题但有更好做法 | 记录备选 |

**判定示例**：
- 默认 admin 密码 `admin123` 进生产 → **P1**（可利用，但需忘改才触发，不到 P0）。
- Flyway 未集成 + schema 三轨漂移 + 缺列 → **P1**（全新初始化库会缺列致运行时错误，非数据丢失）。
- 前端 `isAuthenticated` 靠 localStorage 标记、首次导航回探前有窗口 → **P2**（守卫已规避，低概率）。
- `WebCollectorAppService` 787 行 → **P2**（可维护性，非 bug）。
- `@EnableAsync` 重复声明 → **P3**（无害冗余）。
- 优化看板无独立入口 → **P4**（设计建议）。

---

## 4. 发现条目标准格式与编号规则

### 4.1 条目编号

每条发现全局唯一编号：**`<模块编号>-<两位序号>`**，按报告内出现顺序递增。例如 `B06-02` = 鉴权模块第 2 条发现。

- 跨模块引用统一用此编号（如 B13 报告引用鉴权问题写 `关联：B06-02`）。
- 索引页 Top 风险清单用此编号定位。
- `[需查证]` 条目同样编号，登记到索引页待复核区。

### 4.2 条目结构

```
### [P级别] [主维度] 简短标题   <!-- 编号：B06-02 -->
- **定位**：`path/to/file.ext:行号`（或操作路径 / 配置 key）
- **现象**：客观描述看到什么（不掺判断）
- **影响**：在真实使用/故障场景下会造成什么后果
- **根因/分析**：为什么会这样（含已排除的误判）
- **修复方向**：1-3 条可执行方向（不写代码），标注改动面（小/中/大，见 §4.3）
- **关联**：[[模块-条目]] / 次维度标签 / 横向主题 / 配置项
```

约束：
- 一条发现 = 一个 H3 标题，不合并多个不相关问题。
- "现象"只陈述事实，"判断"放"影响/根因"。
- 不确定的标 `[需查证]`，登记到索引页待复核区。

### 4.3 改动面分级（用于横向比较，非精确估算）

修复方向标注的改动面口径：

| 改动面 | 定义 |
|---|---|
| **小** | 单文件、<50 行、无接口/签名/配置变更 |
| **中** | 跨文件或单服务内、涉及接口/DTO/配置变更、需补测试 |
| **大** | 跨服务、schema 变更、涉及数据迁移、或改动核心链路（采集/日报/优化） |

---

## 5. 模块拆分清单（核心）

共 **42 个模块**，分 4 个子系统。编号即报告文件名前缀。每个模块独立成报告。

> 预估难度：🟢轻（逻辑简单/范围小）／🟡中／🔴重（跨文件/跨服务/逻辑复杂）。

### 5.1 Backend（B01–B17，17 模块）

| 编号 | 模块 | 核心范围 | 预估 | 关键文件 |
|---|---|---|---|---|
| B01 | 文章 Article | CRUD/归档/Top/浏览统计/草稿/发布事件 | 🟡 | `application/article/`、`domain/article/`、`ArticleController` |
| B02 | 分类 Category | 树形/is_leaf/计数刷新/路径面包屑 | 🟡 | `application/category/`、`domain/category/Category` |
| B03 | 技术日志 DailyLog | CRUD/公开可见性 | 🟢 | `application/dailylog/` |
| B04 | 展示类 Project/Skill/FriendLink | 三者 CRUD + 公开展示 | 🟢 | 各自 application/domain |
| B05 | 文件 File | 上传/md5 去重/缩略图/路径遍历防护 | 🟡 | `application/file/`、`ImageThumbnailService` |
| B06 | 认证授权 Auth/Security | Sa-Token/登录/UserAppService/限流/Filter | 🔴 | `AuthController`、`UserAppService`、`SaTokenConfig`、`filter/*` |
| B07 | 系统配置 Config | DB 化/AES 加密/crawler 重载/缓存刷新 | 🟡 | `application/config/`、`AesEncryptor`、`SystemConfigInitializer` |
| B08 | WebCollector 采集编排 | 任务状态机/订阅源/转文章日志/重试 | 🔴 | `application/webcollector/`（787 行）、`domain/webcollector/*` |
| B09 | 内部回调与跨服务同步 | InternalCallback/指纹/来源权威性/双向 key | 🔴 | `InternalCallbackController`、`DigestFingerprint*`、`SourceAuthorityMapper` |
| B10 | 日报公开查询 PublicDigest | 纯透传 Python 的安全与健壮性 | 🟢 | `PublicDigestController`、`CrawlerTaskClient` |
| B11 | 代理管理 Proxy | Mihomo/Clash 控制/测速/订阅 | 🟡 | `application/proxy/`、`MihomoProxyClient` |
| B12 | 看板与首页 Dashboard/Home | 并行聚合/统计口径 | 🟢 | `DashboardController`、`HomeController` |
| B13 | AI 骨架 AiService/NoOp | 端口/NoOp/EventHandler/article_vector 落地缺口 | 🔴 | `infrastructure/ai/NoOpAiService`、`application/event/ArticleEventHandler`、`domain/ai/AiService` |
| B14 | 数据访问层 | MyBatis Plus/Mapper/乐观锁/分页/Repository 实现 | 🟡 | `infrastructure/persistence/*` |
| B15 | 数据库与迁移 | Flyway 双轨/schema 三轨/init.sql/data.sql/索引/外键 | 🔴 | `db/migration/V1_*`、`db/init.sql`、`deploy/db/init-scripts/schema.sql`、`data.sql` |
| B16 | 全局基础设施 | 异常处理/Filter 链/TraceId/访问日志/Knife4j/CORS | 🟡 | `interfaces/filter/*`、`GlobalExceptionHandler`、`config/web/*` |
| B17 | 调度与异步 | @EnableScheduling/@EnableAsync/任务对账/线程池 | 🟢 | `infrastructure/scheduler/`、`AsyncConfig` |

### 5.2 Crawler-service（C01–C12，12 模块）

| 编号 | 模块 | 核心范围 | 预估 | 关键文件 |
|---|---|---|---|---|
| C01 | API 层与中间件 | crawl/health/ssrf_guard/errors/RequestID/AccessLog | 🟡 | `api/crawl.py`、`api/health.py`、`api/ssrf_guard.py`、`api/errors.py` |
| C02 | 鉴权与服务边界 | ApiKeyMiddleware/X-Client-Id/保护前缀/限流/失败隔离 | 🟡 | `standalone/auth.py`、`config.py` |
| C03 | 采集核心 | single/deep/search 四引擎降级/RSS/feed | 🔴 | `crawler/single.py`、`crawler/deep.py`、`crawler/search.py`、`crawler/feed.py` |
| C04 | 日报生成编排 | DigestOrchestrator 4 阶段/板块/触发/补救 | 🔴 | `crawler/digest_orchestrator.py`、`crawler/digest_gen_agent.py` |
| C05 | AI 整理 | organizer/双分发/chunk 重试/清洗/校验 | 🟡 | `ai/organizer.py`、`ai/config.py` |
| C06 | 自动优化系统 | evaluator/strategy/fatigue/feedback/bubble_breaker | 🔴 | `optimization/evaluator.py`、`optimization/strategy.py`、`optimization/feedback.py`、`optimization/bubble_breaker.py` |
| C07 | 知识库与强闭环 | knowledge_base/source actions/三层护栏/circuit-breaker | 🔴 | `optimization/knowledge_base.py`、`crawler/source_agent.py` |
| C08 | 质量与去重 | quality/dedup/page_classifier/search_planner/ranker/feedback | 🟡 | `crawler/quality.py`、`crawler/dedup.py`、`crawler/page_classifier.py` |
| C09 | 数据层 SQLite | db.py/状态机/孤儿恢复/增量迁移/PRAGMA | 🟡 | `standalone/db.py`、`standalone/repository.py` |
| C10 | 调度器 | scheduler/cron/信息源同步/锁/超时 | 🟡 | `standalone/scheduler.py` |
| C11 | 配置同步 | backend_config/env vs sys_config 优先级/刷新 | 🟡 | `standalone/backend_config.py` |
| C12 | 硬编码规则与维护性 | 域名表/降级链/低价值过滤/跨库一致性窗口 | 🟡 | `standalone/task_executor.py`（硬编码段）、`crawler/search.py` |

### 5.3 Frontend（F01–F07，7 模块）

| 编号 | 模块 | 核心范围 | 预估 | 关键文件 |
|---|---|---|---|---|
| F01 | 路由与鉴权守卫 | routes/guards/Cookie 模式/跨 Tab 同步/回探窗口 | 🟡 | `router/routes.ts`、`router/guards.ts`、`stores/modules/user.ts` |
| F02 | 请求层 | request.ts/重试/abort/错误拦截/401 处理 | 🟡 | `utils/request.ts` |
| F03 | 编辑与渲染（md 双轨） | md-editor-v3 编辑/markdown-it 阅读/风格漂移/XSS | 🟡 | `components/editor/MarkdownEditor.vue`、`utils/markdown.ts` |
| F04 | 采集与日报管理页 | collector/digest admin/优化看板集成/轮询 | 🔴 | `views/admin/collector/*`、`views/admin/digest/*` |
| F05 | 配置与代理管理页 | config/proxy admin/双向刷新 | 🟡 | `views/admin/config/*`、`views/admin/proxy/*` |
| F06 | 状态管理 Pinia | store 数量/缓存策略/持久化字段 | 🟢 | `stores/modules/*` |
| F07 | 构建与依赖 | vite 配置/chunk 分包/dist 提交/依赖版本 | 🟡 | `vite.config.ts`、`package.json` |

### 5.4 横切全局（X01–X06，6 模块）

| 编号 | 模块 | 核心范围 | 预估 | 关键文件 |
|---|---|---|---|---|
| X01 | 部署架构 | docker-compose/健康检查/资源限额/启动顺序/网络 | 🟡 | `deploy/docker-compose.yml`、`deploy/nginx*`、各 Dockerfile |
| X02 | 数据库 schema 完整性（跨子系统） | PG 特性/索引/外键/种子数据/跨库一致 | 🔴 | `schema.sql` + crawler SQLite 表 |
| X03 | 测试体系 | backend 单测失衡/crawler 覆盖/frontend 无单测/形态 | 🟡 | `backend/src/test/`、`crawler-service/tests/` |
| X04 | 发布脚本与 CI | release-gate/check-deploy-env/digest-smoke/无 CI | 🟡 | `scripts/release/*` |
| X05 | 文档一致性 | docs 漂移/README 基线/误导性注释 | 🟢 | `docs/*`、各 README |
| X06 | 配置一致性 | env 三轨/AI_MODEL 不一致/敏感项默认值 | 🟡 | `deploy/.env.example`、`crawler-service/.env.example`、sys_config |

---

## 6. 报告模板

所有模块报告复制 [_template.md](./_template.md) 起笔，文件名 `<编号>-<slug>.md`（如 `B06-auth-security.md`）。模板含：

- 头部元信息（模块编号、范围、**基线 commit + 工作区脏状态**、排查日期、状态）
- 模块概览（职责 + 关键文件 + 对外接口/依赖 + **已读文件清单**）
- 五维度小节（`[Bug]`/`[Security]`/`[Arch]`/`[Deps]`/`[Design]`），`[Deps]` 节前置"本模块依赖清单"，`[Design]` 节即便无问题也写审视结论
- 模块小结（严重度统计 + Top 风险 + 修复优先级 + 排查盲区）

---

## 7. 索引页（README.md）结构

本目录 `README.md` 作为总索引，执行时持续更新，包含：

1. **进度总览表**：42 模块状态（待查/进行中/完成）、发现数、P0/P1 计数。
2. **严重度汇总**：全项目 P0–P4 计数 + Top 10 高优发现清单（链接到各模块报告，用 §4.1 编号）。
3. **横向主题**（§2.6）：跨服务契约一致性、鉴权一致性、schema 漂移、配置一致性、AI 空壳链路——每主题聚合各模块相关条目编号。
4. **待复核清单**：所有 `[需查证]` 条目集中登记。
5. **修复排期建议**：按 P0→P1→P2 批次建议。

---

## 8. 执行策略与编排

### 8.1 总体方式

42 个模块用**并行 agent 分批**推进，协调者（主 Agent）负责派发、汇总、去重、分级、更新索引页。每批 5–7 个模块并行，单个 agent 负责 1 个模块、严格按模板与 §13 prompt 骨架产出报告。

> 使用 Agent 工具并行派发（非 Workflow），每批在单条消息内发起多个 Agent 调用以并发执行。

### 8.2 批次划分（6 批，按依赖与全局视角排序）

| 批次 | 模块 | 批次目标 |
|---|---|---|
| **批 1：基础设施底座** | B14 B15 B16 B17 X02 X05 X06 | 先建立数据/配置/文档/测试的全局基线，为业务模块排查提供准确事实底座 |
| **批 2：Backend 业务域（上）** | B01 B02 B03 B04 B05 B12 | 博客基础 CRUD 类，相对独立 |
| **批 3：Backend 业务域（下）+ 集成** | B06 B07 B08 B09 B10 B11 B13 | 鉴权/配置/采集/回调/AI 骨架，跨服务密集 |
| **批 4：Crawler 核心** | C01 C02 C03 C04 C05 | API/采集/日报编排/AI 整理 |
| **批 5：Crawler 智能与优化** | C06 C07 C08 C09 C10 C11 C12 | 优化闭环/知识库/质量去重/数据层/调度 |
| **批 6：Frontend + 部署/发布** | F01 F02 F03 F04 F05 F06 F07 X01 X03 X04 | 前端全模块 + 部署/测试/脚本收尾 |

### 8.3 单模块排查标准动作（每个 agent 必做）

1. **读**：通读模块关键文件（非片段），理解职责与数据流；记录已读文件到报告"已读文件清单"。
2. **搜引用**：改/用到的接口、字段、配置 key、枚举，grep 全部消费方。
3. **对维度**：逐条对照 §2 的 5 大维度 checklist（含 §2.2 技术栈重点），记录命中项。
4. **查依赖**：模块涉及的第三方库/版本（基于声明文件），对照 `[Deps]` 维度，列"依赖清单"。
5. **审设计**：按 §2.5 的 7 个问题，挑相关的作 `[Design]` 评估（≥2 个），无问题也写结论。
6. **定级**：按 §3 标准给每条发现定 P 级 + 编号（§4.1），写明依据 + 改动面（§4.3）。
7. **查横向主题**：对照 §2.6，本模块涉及的横向主题（尤其跨服务契约）标注归属。
8. **去重**：与 §8.6 主模块归属表对照，非主模块只引用、不重复展开。

### 8.4 协调者职责（批间）

- 收集本批所有报告，校验格式合规（§8.5）、严重度口径一致、编号无冲突。
- 识别跨模块重复，按 §8.6 主模块归属归并。
- 更新索引页进度表、严重度汇总、横向主题、待复核清单。
- 每批结束输出批次小结（本批发现数、P0/P1 清单、异常、`[需查证]` 数）。

### 8.5 质量门禁（单模块报告通过条件）

- ✅ 五个维度小节齐全（含"未发现"的说明）；`[Design]` 必有审视结论（无问题也写）。
- ✅ 每条发现有 `file:line` 或操作路径定位 + §4.1 编号。
- ✅ 每条发现 P 级有判定依据 + 改动面标注，非"感觉"。
- ✅ `[Deps]` 节有"本模块依赖清单"。
- ✅ `[Design]` 至少回答了 §2.5 中 ≥2 个相关问题。
- ✅ 报告含基线 commit + 工作区脏状态 + 已读文件清单。
- ✅ 无臆测，不确定项标 `[需查证]`。
- ✅ 不重复已知全局结论（仅补模块视角新细节）；非主模块对共享对象只引用。

### 8.6 跨模块"主模块"归属表（防散落重复）

共享对象只在主模块深查，其余模块只引用主模块条目编号：

| 共享对象 | 主模块 | 引用方 |
|---|---|---|
| PG 全部表 schema 定义 / Flyway / migration / init.sql / schema.sql / data.sql | **B15** | X02（跨库视角）、B08/B13（涉及具体表时） |
| SQLite vs PostgreSQL 跨库一致性 | **X02** | C09、B09 |
| 鉴权机制（Sa-Token 配置 / Filter / URL 前缀规则） | **B06** | 所有 admin Controller（查自己是否误用）、F01 |
| AES 加密 / `AesEncryptor` | **B07** | X06（一致性）、B16 |
| AI 空壳链路（NoOpAiService / AiService / ArticleEventHandler / article_vector） | **B13** | B01（发布事件）、X02（article_vector 表） |
| `CrawlerTaskClient`（backend→crawler HTTP 客户端） | **B10** | B07（配置重载）、B08/B09 |
| 内部回调端点 + 双向 key | **B09** | C01（callback 字段契约）、X06 |
| env 三处 / AI_MODEL 等配置不一致 | **X06** | C11、B07、各模块用的配置 key |
| digest_orchestrator 编排 | **C04** | C06/C07（优化部分）、C10（调度触发） |
| keyword 优化循环 vs digest 优化循环重复实现 | **C06** | C04、C07 |
| 前端请求层 `request.ts` | **F02** | 所有 F0x 调用页 |
| 路由守卫 / Cookie 鉴权 | **F01** | F04/F05（管理页） |

**跨服务契约一致性**（§2.6 横向主题）：无单一主模块，由协调者在索引页聚合。前端侧字段由各 F0x 报告记，后端侧由对应 B0x 报告记，crawler↔backend 由 B09 + C01 共同记。

### 8.7 工作量粗估（辅助决策，以批 1 实测校准）

- **轮次**：6 批顺序执行（批间需协调者去重），每批并行 5–7 agent；🔴重模块可能需 agent 内多轮读取。
- **输出体量**：每份报告预计 150–400 行，42 份合计约 8000–15000 行。
- **token 倾斜**：🔴重模块（B06/B08/B09/B13/C04/C06/C07/X02）显著高于 🟢，约占总量 50%+。
- **校准**：批 1 完成后用实测耗时/token 外推全量，更新本估算。

---

## 9. 已知线索（上一轮调研沉淀，供各模块深挖起点）

> 起点**线索**，非结论；各模块需独立验证并补充细节。

- **[Arch/P1] schema 三轨漂移**（B15/X02）：Flyway 未集成，init.sql / migration / schema.sql 漂移 731 行，schema.sql 缺 `ai_generation` 表与 7 条 crawler 配置；部分列仅 migration 有。
- **[Arch/P1] Java AI 是 NoOp 空壳**（B13）：端口/表/事件链路全建好，实现空返回；`ArticleEventHandler` 标签与向量无落地。
- **[Test/P2] 后端测试失衡**（X03）：111 个 `@Test`（非文档 75/88），全 Mockito 单测、零集成、领域层 0、Auth 零覆盖。
- **[Security/P2] 鉴权纯靠 URL 前缀**（B06）：无 `@SaCheck*`/`@PreAuthorize`，全靠 Sa-Token 路由拦截器模式判定。
- **[Security/P1] 默认弱口令**（X02/B06）：schema.sql 种子 admin 密码 `admin123`，check-deploy-env 未覆盖。
- **[Arch/P2] 无 CI**（X04）：门禁全靠手动 release-gate.ps1。
- **[Arch/P2] keyword 优化循环 vs digest 优化循环两套实现**（C06）。
- **[Doc/P2] AI_MODEL 三处不一致**（X06）：`.env.example=qwen-plus` / README 与 sys_config=`deepseek-v4-pro`。
- **[Design/P4] 优化看板无独立入口**（F04）。
- **[Bug/P2] 日报 global timeout 后 KB 不写入**（C04/C07）：超时日报质量数据不进闭环，趋势统计偏向"顺利完成的"。

---

## 10. 交付物清单

执行完成后，本目录包含：

1. `README.md` —— 总索引页（进度/严重度/横向主题/待复核/排期）。
2. `_template.md` —— 报告模板。
3. `00-audit-plan.md` —— 本计划文档。
4. `backend/B01..B17-*.md` —— 17 份后端报告。
5. `crawler/C01..C12-*.md` —— 12 份爬虫报告。
6. `frontend/F01..F07-*.md` —— 7 份前端报告。
7. `crosscutting/X01..X06-*.md` —— 6 份横切报告。

合计 42 份模块报告 + 索引页 + 计划 + 模板。

---

## 11. 风险与缓解

| 风险 | 缓解 |
|---|---|
| 42 模块工作量大、轮次多 | 分 6 批并行，每批产出即可用；批 1 实测校准估算（§8.7） |
| 跨模块重复/口径不一 | 统一模板 + §8.6 主模块归属 + 协调者批间去重 + 索引页横向主题 |
| 误报（臆测当结论） | §8.5 质量门禁强制证据 + `[需查证]` 机制 |
| 漂移结论（代码已改） | §1.4 基线状态约定，每报告记 commit + 工作区状态 |
| 只读约束被破坏 | §1.3 命令边界固化，agent 明确禁止业务代码 Edit/Write 与重型命令 |
| 审计文档自身漂移 | §1.5 与 risk-register 单向证据链，排查中不改汇总层 |
| agent 风格漂移 | §13 统一 prompt 骨架 |

---

## 12. 执行授权确认

本计划为**设计阶段产物**。开始执行前需确认：

1. 模块拆分（42 个）粒度是否合适？是否要合并/增删？
2. 批次顺序（底座优先）是否认可？
3. 执行节奏：先跑批 1 看效果，还是一次性跑完全部 6 批？
4. 命令边界（§1.3）是否认可？是否额外授权某类轻量命令？

确认后即按 §8 编排执行。

---

## 13. 附录：模块排查 Agent 标准 Prompt 骨架

> 派发每个模块 agent 时，套用本骨架（替换 `<...>` 占位），保证 42 模块执行风格一致。

```
你是 Nanmuli Blog 项目的模块排查 agent，负责 <编号> <模块名> 的地毯式排查。

## 任务
对模块 <编号>（<核心范围>）进行只读排查，按模板产出报告到
docs/audit/module-audit/<子系统>/<编号>-<slug>.md。

## 硬约束
- 只读：禁止修改任何业务代码/配置/数据库。只允许写上述报告文件。
- 命令边界：允许 grep/glob/read/git log/单文件语法检查（仅佐证单一结论）；
  禁止 mvn test/pytest/npm build/docker/外网请求/深入 node_modules 或 .venv。
- 不臆测：无法确认标 [需查证]。每条发现必须有 file:line 定位。
- 不重复：已知全局结论（见计划 §9）只补本模块视角新细节；
  共享对象按 §8.6 主模块归属，非主模块只引用编号。

## 模块范围
关键文件：<列出关键文件>
预估难度：<🟢/🟡/🔴>
主模块归属（若本模块是某共享对象主模块，需深查；否则只引用）：<见 §8.6>

## 必做（计划 §8.3）
1. 通读关键文件，记录"已读文件清单"。
2. grep 所有引用/消费方。
3. 逐条对照 §2 五维度（含 §2.2 技术栈安全重点）。
4. [Deps] 节列"本模块依赖清单"（基于声明文件，不翻依赖源码）。
5. [Design] 节回答 §2.5 至少 2 问，无问题也写审视结论。
6. 每条发现按 §4 定 P 级 + 编号 <编号>-NN + 改动面（§4.3）。
7. 对照 §2.6 横向主题（跨服务契约等）标注归属。

## 产出格式
严格复制 docs/audit/module-audit/_template.md，含：
- 头部：基线 commit（git rev-parse HEAD）+ 工作区脏状态 + 排查日期 + 状态
- 五维度小节 + 模块小结（严重度统计/Top 风险/修复优先级/盲区）

## 质量门禁（§8.5，自查全部 ✅ 后再返回）
<列出 §8.5 的 8 条>

完成后返回：报告路径 + 本模块发现数 + P0/P1 清单 + [需查证] 数。
```
