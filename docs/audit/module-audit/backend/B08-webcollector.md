# B08 WebCollector 采集编排 排查报告

> **模块编号**：B08
> **排查范围**：采集任务生命周期（状态机）、订阅源管理、Python 任务同步编排（create/retry/delete 的 afterCommit）、转文章/日志、卡死任务对账触发点
> **基线 commit**：`6ae930098405f4d0553d96a852f3345d0f39682e`
> **工作区状态**：脏。涉及本模块的未提交改动：
>   - `backend/src/main/java/com/nanmuli/blog/infrastructure/persistence/webcollector/WebCollectPageMapper.java`（`SELECT *` → 显式列清单 `WEB_COLLECT_PAGE_COLUMNS`）
>   - 新增未跟踪 `backend/src/test/java/com/nanmuli/blog/infrastructure/persistence/webcollector/WebCollectPageMapperProjectionTest.java`（锁死"不用 SELECT *"）
>   - 其余脏文件（`ConfigRepositoryImpl.java`、crawler `search.py`/`knowledge_base.py`、release 脚本等）不触及本模块主链路
> **排查日期**：2026-06-23
> **排查人**：B08 模块排查 agent
> **状态**：草稿

---

## 模块概览

**职责**：WebCollector 是 Java 侧的采集编排层——创建/重试/删除采集任务时先落 MySQL 记录，事务提交后通过 `CrawlerTaskClient` 委托 Python 执行爬取+AI 整理；Python 回调或定时对账（B17）把结果同步回 MySQL；用户可把完成任务转为文章草稿或技术日志。本模块只编排"任务-Python-文章/日志"这条链路，**不含**内部回调端点本身（B09）、`CrawlerTaskClient` 实现（B10）、调度器（B17）、schema 定义（B15）。

**关键文件**：
- `backend/src/main/java/com/nanmuli/blog/application/webcollector/WebCollectorAppService.java`（787 行，上帝服务，采集任务全链路编排）—— 通读
- `backend/src/main/java/com/nanmuli/blog/application/webcollector/WebCollectSourceAppService.java`（231 行，订阅源 CRUD + 运行状态统计）—— 通读
- `backend/src/main/java/com/nanmuli/blog/domain/webcollector/WebCollectTask.java`（强充血状态机 `updateStatus` 单向流转 + `@Version` 乐观锁）—— 通读
- `backend/src/main/java/com/nanmuli/blog/domain/webcollector/CollectTaskStatus.java` / `CollectTaskType.java` / `PageCrawlStatus.java`（枚举）—— 通读
- `backend/src/main/java/com/nanmuli/blog/domain/webcollector/WebCollectSource.java`（订阅源聚合根，含统计字段）—— 通读
- `backend/src/main/java/com/nanmuli/blog/domain/webcollector/WebCollectPage.java`（页面实体）—— 通读
- `backend/src/main/java/com/nanmuli/blog/interfaces/rest/WebCollectorController.java`（唯一用 `StpUtil.getLoginIdAsLong` 的 Controller）—— 通读
- `backend/src/main/java/com/nanmuli/blog/infrastructure/persistence/webcollector/WebCollectTaskRepositoryImpl.java` / `WebCollectSourceRepositoryImpl.java` / `WebCollectPageRepositoryImpl.java` / `WebCollectPageMapper.java`（脏）—— 通读
- `backend/src/main/java/com/nanmuli/blog/application/webcollector/command/*`（Create/Convert 命令）—— 通读

**对外接口 / 依赖**：
- 对外（经 `WebCollectorController` `/api/admin/collector/**`，全 admin）：任务 CRUD、重试、转文章/日志、订阅源 CRUD/toggle/test、digest 代理（纯透传 Python）
- 依赖：`CrawlerTaskClient`（→ B10）、`ArticleAppService` / `DailyLogAppService`（转文章/日志）、`WebCollectTaskRepository` / `WebCollectSourceRepository` / `WebCollectPageRepository`、PG 表 `web_collect_task` / `web_collect_source` / `web_collect_page`（schema → B15）、`ObjectMapper`
- 被依赖：`InternalCallbackController`（B09，调 `handleCallback` / `syncFromPythonSilent`）、`TaskReconciliationScheduler`（B17，调 `syncFromPythonSilent`）

**已读文件清单**：
- `WebCollectorAppService.java` —— 通读（787 行）
- `WebCollectSourceAppService.java` —— 通读
- `WebCollectTask.java` / `WebCollectSource.java` / `WebCollectPage.java` / `CollectTaskStatus.java` / `CollectTaskType.java` / `PageCrawlStatus.java` —— 通读
- `WebCollectorController.java` —— 通读
- `WebCollectTaskRepositoryImpl.java` / `WebCollectSourceRepositoryImpl.java` / `WebCollectPageRepositoryImpl.java` / `WebCollectPageMapper.java`（含脏改动 diff）—— 通读
- `WebCollectTaskRepository.java`（接口）—— 通读
- `CrawlerTaskClient.java`（B10 主模块，仅读 B08 调用面）—— 通读
- `InternalCallbackController.java`（B09 主模块，仅读 B08 交互面）—— 通读
- `TaskReconciliationScheduler.java`（B17，读 B08 触发点）—— 通读
- `CreateCollectTaskCommand.java` / `ConvertToArticleCommand.java` / `ConvertToDailyLogCommand.java` —— 通读
- `BaseAggregateRoot.java`（`@TableLogic` / `@Version` 基类）—— 通读
- `MyBatisPlusConfig.java` / `application.yml` mybatis-plus 段 —— 通读（确认拦截器与逻辑删除配置）
- `deploy/db/init-scripts/schema.sql:655-733`（web_collect_* 三表定义）—— 通读
- `WebCollectPageMapperProjectionTest.java`（新增测试）—— 通读
- `git diff WebCollectPageMapper.java` —— 通读

**主模块归属**：本模块是**采集任务编排的主模块**，对"任务状态机 / 转文章日志事务 / Python 同步 afterCommit 编排 / 订阅源 CRUD"深查。共享对象只引用：
- schema（web_collect_* 表）→ 引用 B15
- 任务对账调度（`TaskReconciliationScheduler`）→ 引用 B17
- `CrawlerTaskClient`（Java→Python HTTP）→ 引用 B10
- 内部回调端点 + 双向 key → 引用 B09（B09 已详查 `handleCallback`/`updateSourceRunStatus`/指纹/来源权威性，本报告不重复）
- Sa-Token 鉴权一致性 → 引用 B06

---

## `[Bug]` 代码正确性与潜在缺陷

> 排查范围：任务状态机流转、retry/delete/create 的 afterCommit 编排、转文章/日志事务原子性、Python 同步字段映射、重复转换防护、并发更新。

### [P1] [Bug] `web_collect_task.source_id` 列+索引+外键全部悬空，实体无对应字段 <!-- 编号：B08-01 -->
- **定位**：schema `deploy/db/init-scripts/schema.sql:662`（`source_id BIGINT`）、`:702`（`idx_task_source`）、`:877`（`fk_task_source` 外键 → `web_collect_source(id)`）；实体 `WebCollectTask.java` 无 `sourceId` 字段
- **现象**：`grep -rn "setSourceId\|sourceId" backend/src/main/java/com/nanmuli/blog/domain/webcollector/` 无任何匹配。`WebCollectorAppService.createTask`（:66-119）从不设置 `source_id`。schema 有列、有索引、有外键，Java 实体与 AppService 完全不感知。
- **影响**：①订阅源（`web_collect_source`）触发的采集任务无法关联回源——`source_id` 永远 NULL，`idx_task_source` 索引（`WHERE source_id IS NOT NULL`）永不命中、`fk_task_source` 外键从不触发；②按源统计任务、按源聚合质量趋势等能力在 Java 侧无法实现（只能靠 Python 侧 SQLite 自维护）；③删除订阅源时无法级联清理/检查关联任务。
- **根因/分析**：典型的 schema 与实体漂移（B15 schema 三轨问题的具体表现之一）。已排除：①不是 Python 侧回填（Python 不写 MySQL web_collect_task）；②不是 `BeanUtils.copyProperties` 漏拷（命令对象 `CreateCollectTaskCommand` 也无 sourceId 字段）。
- **修复方向**：①若设计上确需关联，给 `WebCollectTask` 补 `sourceId` 字段 + `createTask` 接收 sourceId 参数 + 订阅源触发路径设值（改动面 中，涉及 createTask 签名/Python 同步/crawler 侧）；②若 MVP 阶段不打算用，应在 schema 移除该列+索引+外键，避免误导（归 B15，改动面 中）。当前是"建好但不用"的半成品。
- **关联**：[[B15 schema 三轨漂移]] / 横向主题"schema 漂移" / 次维度 [Arch]

### [P1] [Bug] retryTask 用 setStatus 绕过状态机，FAILED→PENDING 不变式失效 <!-- 编号：B08-02 -->
- **定位**：`WebCollectorAppService.java:210`（`task.setStatus(CollectTaskStatus.PENDING.getValue())`）；状态机 `WebCollectTask.updateStatus`（:72-97）显式拒绝回退
- **现象**：`retryTask` 在重置任务时直接调 `task.setStatus(...)`，而非 `task.updateStatus(...)`。原因：`updateStatus` 的 switch 对 `PENDING` 分支要求 `current == PENDING`，从 FAILED 无法回到 PENDING，会抛 `IllegalStateException`。开发者用 setter 绕过。
- **影响**：①领域状态机的不变量（"终态不可逆""单向前进"）在 retry 路径被静默打破，状态机变成"除 retry 外都守规则"的半残；②未来若有人给 retry 加并发竞态（callback 同时把状态往前推），retry 的 setStatus 会无条件覆盖，可能把一个已经在 CRAWLING 的任务强行拉回 PENDING；③`markFailed`/`markAiCompleted` 都走 `updateStatus`，唯独 retry 不走，一致性差。
- **根因/分析**：状态机缺少"重置到 PENDING"的合法迁移。重试在业务上是合理的回退，但状态机设计时没预留 `RESET`/`RETRY` 通道，只能绕过。已排除：①不是 bug 绕过（重置字段+回到 PENDING 是 retry 必需语义），问题在于状态机表达力不足而非 retry 逻辑错误。
- **修复方向**：①在 `updateStatus` 增加 `RETRY` 上下文参数或在 `WebCollectTask` 加 `resetForRetry()` 领域方法，内部 setStatus 但同时校验"当前必须是 FAILED"（改动面 中）；②retry 前先校验 `task.getStatus() == FAILED`（已在 :190 校验），再把重置逻辑下沉到领域方法，避免 AppService 直接碰 setter（改动面 小-中）。
- **关联**：次维度 [Arch]（领域方法泄漏到 AppService）

### [P2] [Bug] retryTask 硬重置清空 aiSearchMetadata 字段名写错，实际清的是对的但语义混乱 <!-- 编号：B08-03 -->
- **定位**：`WebCollectorAppService.java:197-210`
- **现象**：retryTask 重置时调用 `task.setAiSearchMetadata(null)`（:207），但同时 `task.setAiKeyPoints/setAiTags/setAiCategory/setAiFullContent(null)` 等。重置字段清单与 `updateTaskFromPython`（:429-481）写入的字段清单**不完全对齐**：retry 没重置 `aiSummary`、`aiTitle`，但重置了 `aiFullContent`/`aiSearchMetadata`。
- **影响**：重试后若新一次 Python 任务尚未回写（用户在 CRAWLING 阶段查看详情），DTO 会展示"旧的 aiTitle/aiSummary + 空的 aiFullContent"的混合状态，可能造成 UI 闪烁或误导。属轻微展示问题，不致数据损坏。
- **根因/分析**：重置字段清单是手工维护的，没和 `updateTaskFromPython` 的字段集做对称约束，随时间漂移。已排除：①不是致命问题（终态前用户少看详情；终态后 Python 回写会覆盖）。
- **修复方向**：在 `WebCollectTask` 加 `resetForRetry()` 领域方法统一清空所有 AI 字段+统计字段+errorMessage，AppService 只调它（改动面 小，与 B08-02 合并修复）。
- **关联**：[[B08-02]]

### [P2] [Bug] deleteTask 不清理 articleId/dailyLogId 反向引用，转文章后删任务留悬空 <!-- 编号：B08-04 -->
- **定位**：`WebCollectorAppService.java:160-184`（deleteTask）
- **现象**：deleteTask 只 `pageRepository.deleteByTaskId` + `taskRepository.deleteById`（逻辑删除），不检查/清理 `task.articleId` / `task.dailyLogId` 指向的文章/日志。任务被删后，生成的文章/日志仍存在，但失去"来源任务"溯源。
- **影响**：①已转为文章/日志的采集任务被删后，文章 `originalUrl` 还在但无法回查采集元数据（AI 关键要点/标签等prepend 进 content 的部分还在，但任务级元数据丢失）；②若用户误删，无回溯入口。属数据可追溯性问题，非数据损坏（文章本身完好）。
- **根因/分析**：deleteTask 设计假设"删任务=清掉采集痕迹"，但没区分"已转换"和"未转换"。已排除：①不是外键问题（article_id/daily_log_id 无外键约束，schema 里 task→article 是逻辑关联非物理外键）。
- **修复方向**：①deleteTask 在已转换（articleId/dailyLogId 非空）时拒绝删除或要求二次确认（改动面 小）；②或在删除前把 articleId/dailyLogId 记日志便于审计（改动面 小）。
- **关联**：次维度 [Design]（可运维性）

### [P3] [Bug] hashUrl 的 utm 参数正则只清理首个分隔符，多 utm 参数清理不彻底 <!-- 编号：B08-05 -->
- **定位**：`WebCollectorAppService.java:759-766`（`hashUrl`）
- **现象**：`normalized.replaceAll("([?&])(utm_[^&=]*=[^&]*&?)+", "$1")` 用 `+` 匹配连续 utm，但替换回 `$1`（首个 `?` 或 `&`）。对 `?utm_a=1&utm_b=2&keep=3`，匹配段是 `?utm_a=1&utm_b=2&`，替换成 `?`，结果 `?keep=3` 正确；但对 `?keep=1&utm_a=2`（utm 在中间），匹配 `&utm_a=2`，替换成 `&`，结果 `?keep=1&`——尾部残留 `&`，再被 `[?&]+$` 清掉，OK。对 `?utm_a=1&keep=2&utm_b=3`（utm 夹 keep），匹配 `&utm_b=3`→`&`，结果 `?utm_a=1&keep=2&`……但 `utm_a=1` 没被匹配（因为它前面是 `?`，正则要求 `utm_` 前有 `?` 或 `&`，这里 `?utm_a` 匹配首段 `?utm_a=1&` → 替换 `?` → `?keep=2&utm_b=3` → 第二轮 replaceAll 才匹配 `&utm_b=3`，replaceAll 全局替换会处理）。
- **影响**：实际 `replaceAll` 是全局的，多轮匹配基本能清干净，尾部 `&`/`?` 也有兜底清理。仅在极端嵌套场景可能有残留，对去重精度影响很小。属代码可读性/健壮性问题，非实际 bug。
- **根因/分析**：正则边界条件复杂，依赖 `replaceAll` 的全局重扫和后续 `replaceAll("[?&]+$", "")` 兜底。逻辑能用但难维护。
- **修复方向**：用 `URI`/`URIBuilder` 解析 query 后剔除 utm_* 参数再规范化，更清晰（改动面 小，但需注意 URL 解析对非标准 URL 的容错）。
- **关联**：无

---

## `[Security]` 安全漏洞

> 排查范围：越权（任务/源 user 归属）、SSRF（Python 侧负责，本模块仅传 sourceUrl）、SQL 注入（Mapper）、鉴权一致性。逐项覆盖 §2.2 技术栈重点中本模块相关项。

### [P1] [Security] WebCollectPageMapper 脏改动后原生 @Select 不受逻辑删除插件保护，查到已删页面 <!-- 编号：B08-06 -->
- **定位**：`WebCollectPageMapper.java:39-49`（脏改动后 `selectByTaskIdOrderBySortOrder`/`selectByTaskId`/`selectByUrlHash` 均 `@Select` 原生 SQL，显式列含 `is_deleted` 但 WHERE 无 `is_deleted = false`）；拦截器 `MyBatisPlusConfig.java:24-30`（仅 Pagination + OptimisticLocker，**无逻辑删除 SQL 改写拦截器**）；配置 `application.yml:50-52`（`logic-delete-field: isDeleted`）
- **现象**：MyBatis-Plus 的全局逻辑删除（`logic-delete-field` 配置）**只对 Wrapper 和 MP 自动生成的 SQL 生效**，对 `@Select`/`@Insert`/`@Delete` 手写注解 SQL **不会自动追加 `is_deleted = false`**。`MyBatisPlusConfig` 也没注册任何逻辑删除改写拦截器。原 `SELECT *` 同样无过滤（脏改动前后行为一致），但脏改动把列写死后，开发者更易误以为"is_deleted 在列里=会被过滤"。
- **影响**：`listTaskPages`（旧任务路径）、`getTaskContent`（旧任务回退路径）、`findByUrlHash` 去重查询，都会把**已逻辑删除的页面**查出来参与展示/去重判断。去重场景下，一个被删的页面 url_hash 仍命中 `selectByUrlHash` → `existsByUrlHash` 返回 true → 新任务被误判为重复。属数据可见性/去重准确性问题，非越权（仍按 taskId/userId 限定）。
- **根因/分析**：这是既有问题（原 `SELECT *` 也无过滤），脏改动未引入新风险但也没修复。已排除：①不是脏改动引入的（原 SQL 同样漏）；②不是越权（user 归属校验在 AppService 层 `loadTaskForUser`）。
- **修复方向**：①在 3 条 `@Select` 的 WHERE 子句显式加 `AND is_deleted = false`（改动面 小）；②或改用 `LambdaQueryWrapper` 让逻辑删除自动生效（但失去显式列投影收益，需权衡）；③补一个集成测试验证逻辑删除页面不被查出。归本模块（B08 用此 Mapper），schema 侧归 B15。
- **关联**：[[B08-07 同列漂移]] / 次维度 [Bug] / 横向主题"MyBatis 逻辑删除盲区"

### [P2] [Security] 脏改动显式列清单靠人工维护，schema 加列后静默漏投影 <!-- 编号：B08-07 -->
- **定位**：`WebCollectPageMapper.java:18-37`（`WEB_COLLECT_PAGE_COLUMNS` 显式列）；新增 `WebCollectPageMapperProjectionTest.java`（仅断言含 5 列 + 不含 `*`）
- **现象**：脏改动把 `SELECT *` 换成 18 列显式清单，与当前 schema（`schema.sql:705-724`，18 列）完全对齐。但新增测试 `pageProjectionUsesExplicitKnownColumns`（:21-26）只断言含 `task_id/url/page_title/raw_markdown/crawl_status` 5 列，**不校验列清单与实体字段全等**。未来 schema 给 `web_collect_page` 加列（如 `ai_summary`），实体加字段，但 Mapper 列清单漏更新 → 查询返回 null，编译期/测试期发现不了。
- **影响**：本质是把"`SELECT *` 投影泄漏"风险换成了"显式列漂移漏字段"风险。当前 MVP 阶段表结构稳定，风险低；长期看测试断言太弱，不能锁死列对齐。
- **根因/分析**：脏改动意图是收紧投影（避免 `SELECT *` 带未知列），方向正确，但测试只锁了"不用星号"+ 5 个核心列，没锁"列清单 == 实体字段集"。已排除：①不是当前 bug（当前列对齐）。
- **修复方向**：①测试里反射读 `WebCollectPage` 所有 `@TableField` 字段，断言列清单包含全部字段（改动面 小）；②或改用 MyBatis-Plus 的 `selectList` + Wrapper，让列由实体驱动（但失去 `@Select` 直观性，需权衡）。
- **关联**：[[B08-06]] / [[B15 schema 漂移]] / 横向主题"schema 漂移"

### [P2] [Security] WebCollectorController 是唯一用 StpUtil.getLoginIdAsLong 的 Controller，user 归属校验下沉到 AppService <!-- 编号：B08-08 -->
- **定位**：`WebCollectorController.java:170-172`（`getCurrentUserId` 直接 `StpUtil.getLoginIdAsLong()`，全 Controller 17 个端点共用）；校验 `WebCollectorAppService.loadTaskForUser:561-568` / `WebCollectSourceAppService.getSourceOrThrow:211-215`
- **现象**：本 Controller 不依赖 Sa-Token 路由拦截器的 admin 前缀鉴权（B06 主模块），而是在每个端点主动取 loginId 并在 AppService 校验 `task.userId.equals(userId)` / `source.userId.equals(userId)`。其他 Controller 普遍不取 userId（靠 `/api/admin/**` 前缀鉴权放行所有 admin）。
- **影响**：**正向**：本模块做了别的模块没做的多租户隔离（即使两个 admin 账号也互不可见任务/源），安全性反而更好。**反向风险**：①digest 代理端点（`:241-380`，10+ 个 `/digest/*`）**只取 userId 但不用于过滤**——这些是纯透传 Python，Python 侧 `include_all=true`（`:245`）会返回所有人的日报，任意 admin 可见全量日报（设计如此，单人博客场景无害）；②`crawlerHealth`（`:149`）等不需 userId 的端点也调 `getCurrentUserId`，多一次 Sa-Token 查询开销（极小）。
- **根因/分析**：本模块显式做 user 隔离是因为任务/源是用户私有数据（与文章/日志不同），设计意图合理。已排除：①不是鉴权漏配（admin 前缀拦截器 + user 校验双保险）。
- **修复方向**：①若未来多用户，digest 代理也应按 user 过滤（需 Python 支持，改动面 大，当前 MVP 无需）；②现状无需调整。标 P2 是提示"本模块的 user 隔离是项目里少有的正向案例，可作为其他模块参考"。
- **关联**：[[B06 鉴权一致性]] / 横向主题"鉴权机制一致性"

### [P3] [Security] ConvertToArticleCommand.title 用 @Size(max=200) 但 ArticleAppService 侧标题约束未知，约束可能被前端绕过 <!-- 编号：B08-09 -->
- **定位**：`ConvertToArticleCommand.java:12-13`（`@Size(max=200)`）；fallback 标题 `WebCollectorAppService.java:288`（`task.getAiTitle()` 或 `truncateUrl` 截 60 字符）
- **现象**：command 标题校验 max=200，但 fallback 用 AI 生成的 `aiTitle`（Python 侧无长度约束，schema 列 `ai_title VARCHAR(500)`）。若 Python 返回 300 字标题，convertToArticle 用它作为文章标题，可能超出 article 表 title 列约束。
- **影响**：极端场景下文章创建可能因 DB 列长度溢出失败（需 article.title 列 < 300）。属边界场景，触发需 Python 返回超长标题。
- **根因/分析**：标题长度约束在多个环节不一致（command 200 / aiTitle schema 500 / article title 列未知）。已排除：①不是注入（参数化查询）。
- **修复方向**：①fallback 时对 aiTitle 也做长度截断（改动面 小）；②统一标题约束常量（改动面 小）。[需查证] article 表 title 列实际长度。
- **关联**：[[B01 文章模块]] / 横向主题"跨服务契约"

---

## `[Arch]` 架构与技术债

> 排查范围：上帝服务职责拆分、DDD 分层、REQUIRES_NEW 自代理、afterCommit 编排、重复实现。共享对象按 §8.6 引用，非主模块只引用编号。

### [P2] [Arch] WebCollectorAppService 787 行上帝服务，6 类职责混合 <!-- 编号：B08-10 -->
- **定位**：`WebCollectorAppService.java`（787 行）
- **现象**：单类混合 6 类职责：①任务 CRUD（createTask/getTask/listTasks/deleteTask）；②转文章/日志（convertToArticle/convertToDailyLog）；③Python 同步编排（syncFromPython*/handleCallback）；④Python→实体字段映射（updateTaskFromPython）；⑤DTO 转换（convertToDTO/convertToListDTO/convertToPageDTO，~150 行）；⑥工具方法（hashUrl/hashContent/sha256/safeErrMsg/truncateUrl/prependAiMetadata）。还注入 6 个依赖 + self 自代理。
- **影响**：可维护性差，单测需 mock 6 个依赖，改动任一职责都需通读 787 行。DTO 转换和工具方法本可下沉到独立类。
- **根因/分析**：典型 AppService 上帝类。已排除：①不是功能 bug（逻辑正确）。
- **修复方向**：①抽出 `WebCollectorDtoAssembler`（DTO 转换）、`WebCollectTaskSyncService`（Python 同步）、`WebCollectHashUtil`（hash 工具，可放 shared）（改动面 中，需保证事务边界不变）；②convertToArticle/convertToDailyLog 可拆到 `WebCollectConversionService`（改动面 中）。
- **关联**：计划 §9 已知线索"787 行"对应本条

### [P3] [Arch] REQUIRES_NEW 自代理事务 + afterCommit 回调嵌套，事务边界复杂难追踪 <!-- 编号：B08-11 -->
- **定位**：`WebCollectorAppService.java:59-61`（`@Lazy self`）、`:349/357/390`（`REQUIRES_NEW` 三处）、`:102/176/225`（`registerSynchronization afterCommit` 三处）
- **现象**：createTask/retryTask/deleteTask 都用"主事务提交后 → afterCommit 里调 Python → Python 成功后 self.updatePythonTaskId（REQUIRES_NEW 新事务）更新 pythonTaskId"。三层事务/回调嵌套：主事务→afterCommit（无事务）→REQUIRES_NEW（新事务）。
- **影响**：①事务边界复杂，新人难理解"为什么 updatePythonTaskId 要 REQUIRES_NEW"（答：afterCommit 已无事务上下文，REQUIRES_NEW 开新事务保证 pythonTaskId 落库）；②afterCommit 里 Python 调用失败时 `self.markTaskFailed` 又开一个 REQUIRES_NEW，若此时 DB 也挂了，失败状态无法落库，任务永久卡 PENDING（靠 B17 对账兜底）；③`@Lazy` 自代理是 Spring 解决自调用事务失效的标准手段，但增加了心智负担。
- **根因/分析**：设计是为保证"主任务记录先落库（用户可见）+ Python 调用不阻塞事务 + Python id 回填独立"，目标合理，但实现复杂度高。已排除：①不是事务失效（@Lazy self 正确规避了自调用问题）。
- **修复方向**：①抽 `WebCollectTaskSyncService` 独立 bean 承载 Python 同步，消除 @Lazy self（改动面 中）；②加结构化日志标注每次事务/回调切换（改动面 小）；③补一个"Python 宕机+DB 正常"的集成测试验证 markTaskFailed 兜底。当前逻辑正确，标 P3 是可维护性提示。
- **关联**：[[B08-10]] / [[B17 任务对账]]

### [P3] [Arch] updateTaskFromPython 字段映射用 Map<String,Object> 弱类型，Python 字段变更无编译期保护 <!-- 编号：B08-12 -->
- **定位**：`WebCollectorAppService.java:429-481`（`updateTaskFromPython`）
- **现象**：Python 任务响应以 `Map<String,Object>` 接收（CrawlerTaskClient.getTask 返回 `Optional<Map<String,Object>>`），逐字段 `pythonTask.get("ai_title")` 字符串 key 取值。Python 侧字段改名（如 `ai_title` → `title`）Java 编译期无感，运行时静默变 null。
- **影响**：跨服务契约纯靠字符串 key，无 schema 约束。Python 改字段名后，Java 同步静默失败（字段变 null，任务看似完成但 AI 结果空），需用户手动转换才发现。属跨服务契约薄弱（§2.6 横向主题）。
- **根因/分析**：弱类型 Map 是快速集成的代价。已排除：①不是 Java 侧 bug。
- **修复方向**：①定义 `PythonTaskResponse` POJO + Jackson 反序列化（改动面 中，需与 Python 字段对齐文档化）；②至少加单元测试断言关键字段名（改动面 小）。归本模块 + 横向主题"跨服务契约"。
- **关联**：[[B10 CrawlerTaskClient]] / [[B09 callback 字段契约]] / 横向主题"跨服务契约一致性"

---

## `[Deps]` 依赖升级与版本

### 本模块依赖清单（基于声明文件，未翻依赖源码）

| 依赖 | 版本 | 声明位置 | 已知风险/可升级 | 备注 |
|---|---|---|---|---|
| Spring Boot | 3.3.5 | `backend/pom.xml` | 可升至 3.3.x 最新补丁 / 3.4 | `@Transactional`/`TransactionSynchronizationManager` 标准 API |
| MyBatis Plus | 3.5.9 | `backend/pom.xml` | 3.5.x 最新 | `@Version`/`@TableLogic`/`LambdaQueryWrapper` 重度使用 |
| Sa-Token | 1.44.0 | `backend/pom.xml` | 1.44.x | 本模块仅用 `StpUtil.getLoginIdAsLong()` |
| Jackson | 随 Spring Boot | `backend/pom.xml` | — | `ObjectMapper`/`TypeReference` |
| Lombok | 随 Spring Boot | `backend/pom.xml` | — | `@Slf4j`/`@RequiredArgsConstructor` |

> 排查范围：本模块直接 API 依赖。版本升级全局视角归 B16/X01，本报告不展开。未命中版本相关 bug。

**本模块依赖相关发现**：无独立 P0-P3 `[Deps]` 发现。MyBatis-Plus 的逻辑删除对 `@Select` 不生效是**已知框架行为**（非版本 bug），见 B08-06。

---

## `[Design]` 功能设计合理性

> 从真实使用出发，回答 §2.5 中相关问题（≥2 个）。

**审视结论**：

1. **场景适配（单人维护博客 + 每工作日 AI 日报）**：本模块为"手动单次采集 + 订阅源定时采集"双路径设计，对单人博客**略偏重**。手动 createTask 路径（single/deep/keyword）+ 转文章/日志的完整闭环，对偶尔的深度阅读笔记整理是够用的；订阅源体系（source CRUD + freshness_hours + schedule_cron + 质量评分）是日报系统的供给端，设计合理。但 `ConvertToDailyLog` 的 mood/weather/isPublic 字段对"采集来的技术内容转日志"语义不搭（采集内容转日志更像"今日所学"，不是"心情日记"），字段耦合了 dailylog 的原有语义——**勉强可用但语义错位**。

2. **闭环完整性**：采集→Python整理→回写→转文章/日志 这条链是完整的。缺的人工干预入口：①任务卡在 PENDING/CRAWLING 时（Python 宕机后）用户只能等 B17 对账（30 分钟）或手动 deleteTask 再重建，无"强制标记失败"按钮；②转文章后若 AI 整理质量差，无"重新触发 AI 整理"入口（retry 会重爬，浪费）；③订阅源无"手动立即执行一次"入口（只有 test，test 是单次探测不计入统计）。这些缺口在 MVP 单人场景可接受。

3. **可运维性 / MVP 假设检验**：CLAUDE.md 声称"Web 采集器 MVP Beta 可试用"基本成立——手动 createTask → 转文章链路可跑通。可运维短板：①createTask 的 afterCommit Python 调用失败时，任务卡 PENDING，前端无明确错误提示（只有日志里的 `markTaskFailed` 兜底，但若 markTaskFailed 自身失败则无声）；②retryTask 的"先 retry Python 旧任务，失败再建新任务"逻辑（:229-244）对用户不透明，Python 侧旧任务已删时会产生"重试变成了新建"的困惑；③`isCrawlerAvailable` 健康检查在 createTask 前调（Controller:58），但 Python 健康不代表任务一定能跑，任务仍可能失败。

### [P4] [Design] 采集任务转技术日志的字段语义错位 <!-- 编号：B08-13 -->
- **定位**：`WebCollectorAppService.convertToDailyLog:305-342`；`ConvertToDailyLogCommand.java`（mood/weather/isPublic）
- **现象**：把采集的技术内容转为"技术日志"，但日志模型带 mood（心情）/weather（天气）字段，语义是为"个人日记"设计的。采集内容转日志时这两个字段无意义，用户需手动填或留空。
- **影响**：交互上略反直觉，但不阻断功能。
- **建议方向**：维持现状（复用 dailylog 表降低复杂度）或未来为"采集笔记"单列类型（改动面 大，MVP 不建议）。标 P4 备选。
- **关联**：无

### [P4] [Design] 订阅源缺"手动立即执行"入口，test 不计入统计 <!-- 编号：B08-14 -->
- **定位**：`WebCollectSourceAppService.testSource:99-112`（调 Python `/api/v1/sources/test`，单次探测）；无 `runNow` 类方法
- **现象**：订阅源只能 test（单次探测，Python 侧不计入 run_count/success_count）或等定时调度。无"立即按订阅源配置触发一次正式采集并计入统计"的入口。
- **影响**：用户新增订阅源后想立即验证完整链路（含 AI 整理+统计回写），只能等 cron 或手动 createTask 重建配置。
- **建议方向**：未来补 `POST /source/{id}/run-now` 端点，触发正式采集并经回调更新统计（改动面 中，需 Python 配合）。MVP 阶段 test 够用，标 P4。
- **关联**：无

---

## 模块小结

### 严重度统计

| 级别 | 数量 | 条目编号 |
|---|---|---|
| P0 | 0 | — |
| P1 | 3 | B08-01, B08-02, B08-06 |
| P2 | 5 | B08-03, B08-04, B08-05→P3 实际, B08-07, B08-08, B08-10 |
| P3 | 4 | B08-05, B08-09, B08-11, B08-12 |
| P4 | 2 | B08-13, B08-14 |

> 注：B08-05 在正文标 P3，上表 P2 行多列了它，实际 P2 = 5 条（B08-03/04/07/08/10），P3 = 4 条（B08-05/09/11/12）。修正：P2=5，P3=4。

### Top 风险（本模块最该先看的 3 条）

1. **B08-01 source_id 列悬空** —— schema 建了列+索引+外键但 Java 实体完全不感知，是 schema/实体漂移的典型证据，影响按源统计/级联清理能力，归 B15 但本模块是消费方。
2. **B08-06 逻辑删除对 @Select 不生效** —— `WebCollectPageMapper` 三条原生 SQL 查到已删页面，去重场景下可能误判重复；脏改动未引入但也未修复，需显式加 `is_deleted = false`。
3. **B08-02 retryTask 绕过状态机** —— 用 setStatus 强行回退 FAILED→PENDING，破坏领域不变量，且重置字段清单与回写清单不对称，应下沉为 `resetForRetry()` 领域方法。

### 修复优先级建议

- **立即**（P1）：B08-06（加 `is_deleted = false`，改动小，去重正确性）、B08-02（retry 下沉领域方法，改动中）、B08-01（决策：补字段 or 删列，需与 B15 协同）
- **计划**（P2）：B08-03（与 B08-02 合并）、B08-04（deleteTask 已转换校验）、B08-07（投影测试加强）、B08-08（记录现状，digest 代理多用户时再改）、B08-10（上帝服务拆分）
- **择机**（P3/P4）：B08-05/09/11/12（可维护性）、B08-13/14（设计建议）

### 排查盲区 / 待复核

- **[需查证]** B08-09：`article` 表 `title` 列实际长度限制，以确认 fallback aiTitle 是否可能溢出（归 B01 核对）。
- **[需查证]** B08-06：MyBatis-Plus 3.5.9 是否有"逻辑删除对手写 SQL 生效"的可选配置（如 `sql-parser` 内部拦截器），若有则修复方向①可简化。当前 `MyBatisPlusConfig` 未注册，判断是不生效，但建议跑一次集成测试验证（命令边界禁止跑，归 X03 测试体系）。
- **未深入**：`crawler-service` 侧订阅源触发→回调链路（归 C10/C11），本报告只确认 Java 侧无 setSourceId 调用。
- **未深入**：digest 代理端点（`:241-380`）的 Python 侧字段契约（归 B09/C04 横向主题"跨服务契约"）。
