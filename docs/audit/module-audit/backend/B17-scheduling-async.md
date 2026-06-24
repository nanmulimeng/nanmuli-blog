# B17 调度与异步 排查报告

> **模块编号**：B17
> **排查范围**：调度（`@EnableScheduling`/`@Scheduled`）与异步基础设施（`@EnableAsync`/`@Async`/线程池/`AsyncConfigurer`/异步异常与 MDC 传播），含任务对账调度器
> **基线 commit**：`6ae930098405f4d0553d96a852f3345d0f39682e`
> **工作区状态**：脏（未提交改动均不涉及本模块自身，涉及 `ConfigRepositoryImpl.java`、`WebCollectPageMapper.java`、crawler-service 多个、`deploy/README.md`、`docs/audit/full-project-risk-register.md`、`scripts/release/release-gate.ps1`、新增 `backend/src/test/.../webcollector/`）
> **排查日期**：2026-06-23
> **排查人**：B17 排查 agent
> **状态**：待复核

---

## 模块概览

**职责**：为后端提供统一的调度触发（对账调度器）和异步执行基础设施（两个线程池 + `@Async` 支持），是 ArticleEventHandler 异步消费和 HomeController 并行聚合的底座。

**关键文件**：
- `backend/src/main/java/com/nanmuli/blog/infrastructure/scheduler/TaskReconciliationScheduler.java:34` —— 唯一的 `@Scheduled` 调度入口，对账超时采集任务
- `backend/src/main/java/com/nanmuli/blog/infrastructure/config/ai/AsyncConfig.java:21` —— `@Configuration` + `@EnableAsync` + `AsyncConfigurer`，定义 `aiTaskExecutor`/`taskExecutor` 两个线程池
- `backend/src/main/java/com/nanmuli/blog/BlogApplication.java:10-11` —— `@EnableAsync` + `@EnableScheduling` 启动类注解
- `backend/src/main/java/com/nanmuli/blog/application/event/ArticleEventHandler.java:30` —— 唯一 `@Async("aiTaskExecutor")` 使用点
- `backend/src/main/java/com/nanmuli/blog/interfaces/rest/HomeController.java:90` —— `CompletableFuture.supplyAsync(supplier, taskExecutor)` 显式注入使用点

**对外接口 / 依赖**：
- 对外：两个具名 `Executor` Bean（`aiTaskExecutor`、`taskExecutor`）；`AsyncConfigurer.getAsyncExecutor()` 提供默认异步执行器（即 `taskExecutor`）
- 依赖：
  - `WebCollectTaskRepository.findStaleNonTerminal`（对账调度器查超时任务）
  - `WebCollectorAppService.syncFromPythonSilent`（对账动作委派到 B08）
  - `WebCollectTask.@Version` 乐观锁（并发保护）
  - 配置 key：`crawler.service.base-url`（条件开关）、`crawler.reconciliation.interval-ms`（调度间隔，默认 600000ms）、`async.executor.ai.*` / `async.executor.task.*`（线程池参数，均无显式 yml 声明，全走默认）

**已读文件清单**：
- `infrastructure/scheduler/TaskReconciliationScheduler.java` —— 通读
- `infrastructure/config/ai/AsyncConfig.java` —— 通读
- `BlogApplication.java` —— 通读
- `application/event/ArticleEventHandler.java` —— 通读（异步消费边界，归 B13）
- `interfaces/rest/HomeController.java` —— 通读
- `application/webcollector/WebCollectorAppService.java:355-533` —— 片段（`syncFromPythonSilent` / `syncPythonTaskToDb` / `isTerminal` / `updateTaskStatusIfKnown`）
- `infrastructure/persistence/webcollector/WebCollectTaskRepositoryImpl.java:76-100` —— 片段（`findStaleNonTerminal` SQL）
- `domain/webcollector/CollectTaskStatus.java` —— 通读（状态码 0/1/2 非终态，3/4 终态）
- `domain/webcollector/WebCollectTask.java:1-40` —— 片段（确认 `@Version` 乐观锁存在）
- `interfaces/filter/TraceIdFilter.java` —— 通读（确认 TraceId 仅 Servlet 链传播）
- `application-dev.yml:45-64`、`application.yml`（grep）—— 确认 `async.executor.*` / `crawler.reconciliation.*` 无 yml 声明
- `deploy/docker-compose.yml`（grep）—— 确认单 backend 实例

**主模块归属**：本模块是调度/异步基础设施的主模块，**深查自身**。ArticleEventHandler 的业务异常消费行为归 B13（AI 空壳链路），本模块只看其异步基础设施面；WebCollector 任务状态机归 B08，本模块只看对账调度器与状态机的交互点。

---

## `[Bug]` 代码正确性与潜在缺陷

> 排查范围：`TaskReconciliationScheduler` 全量、`AsyncConfig` 全量、两个线程池的所有使用点（`@Async` 1 处、`taskExecutor` 注入 1 处）、`@Scheduled` 与 `@Async` 组合、并发与乐观锁、异步异常传播。

### [P3] [Bug] `AsyncConfig` 未配置 `AsyncUncaughtExceptionHandler`，`void` 异步方法异常仅走默认日志  <!-- 编号：B17-01 -->
- **定位**：`backend/src/main/java/com/nanmuli/blog/infrastructure/config/ai/AsyncConfig.java:21-68`（实现 `AsyncConfigurer` 但只 override `getAsyncExecutor`，未 override `getAsyncUncaughtExceptionHandler`）
- **现象**：`AsyncConfig implements AsyncConfigurer`，仅重写 `getAsyncExecutor()` 返回 `taskExecutor()`，未重写 `getAsyncUncaughtExceptionHandler()`。Spring 对未配置 handler 的 `void` 异步方法，异常会被 `SimpleAsyncUncaughtExceptionHandler` 捕获并打一行 WARN 日志（`Unexpected exception occurred`），无统一上报/告警通道。
- **影响**：当前唯一 `@Async` 使用点 `ArticleEventHandler.handleArticlePublished` 在方法入口包了 `try-catch(Exception)`（`ArticleEventHandler.java:34-78`），且三条 AI 调用链都挂了 `.exceptionally(...)`，所以**当前实际不会触发默认 handler**。但这是"靠业务层逐个 try-catch 兜底"而非"基础设施兜底"，未来新增 `@Async void` 方法时易遗漏，异常静默。
- **根因/分析**：`AsyncConfigurer` 的两个回调方法不对称实现。已排除：`getAsyncExecutor()` 返回 `taskExecutor()`（self-invocation）——因 `@Configuration` 默认 CGLIB 代理，`this.taskExecutor()` 会走代理返回容器内单例 Bean，不会重复 `new`，故此处 self-invocation 是安全的，非 bug。
- **修复方向**：在 `AsyncConfig` override `getAsyncUncaughtExceptionHandler()`，返回一个打 ERROR 日志（含 MDC/方法名/异常）的 handler；可选再加 `TaskDecorator` 在提交前 `MDC.put` 子线程上下文。改动面：小。
- **关联**：次维度 `[Arch]`；横向主题"AI 空壳链路"（关联 B13）；与 B17-03（MDC 传播）同源。

### [P2] [Bug] 对账调度器 `@Scheduled` 线程与 `@Async` 线程均无 MDC/TraceId 传播  <!-- 编号：B17-02 -->
- **定位**：`backend/src/main/java/com/nanmuli/blog/infrastructure/scheduler/TaskReconciliationScheduler.java:34-58`（`@Scheduled` 线程）+ `infrastructure/config/ai/AsyncConfig.java:37-68`（两个线程池均无 `TaskDecorator`）+ `interfaces/filter/TraceIdFilter.java:16-29`（TraceId 仅在 Servlet `FilterChain` 内 put/clear）
- **现象**：`TraceIdFilter` 只在 HTTP Servlet 链路 put traceId 到 MDC，`finally` 中 `MDC.clear()`。调度线程（Spring `TaskScheduler` 默认 `ConcurrentTaskScheduler`，线程名 `scheduling-`）和两个异步线程池（`ai-task-`/`async-task-`）都不经过该 Filter，其日志行的 traceId 占位（`logback-spring.xml` 若用 `%X{traceId}`）将为空。
- **影响**：①对账调度器日志（`[Reconciliation] Found ... stale tasks` 等）无法与触发链路关联，故障定位时缺少 traceId 串联。②`ArticleEventHandler` 异步处理的日志同样无 traceId，文章发布请求与其异步 AI 处理的日志无法用同一 traceId 串起来。③`HomeController` 并行查询线程也无 traceId。
- **根因/分析**：`ThreadPoolTaskExecutor` 默认不做 MDC 传播，需配 `TaskDecorator`。InheritableThreadLocal 也救不了线程池（线程复用，不继承调用方 MDC）。这是 Spring 异步 + SLF4J MDC 的经典缺口。
- **修复方向**：在两个 `ThreadPoolTaskExecutor` 上 `executor.setTaskDecorator(new MdcTaskDecorator())`，`MdcTaskDecorator` 在 `run()` 前后 `MDC.put`/`MDC.clear` 拷贝父线程上下文；对账调度线程可单独在 `reconcileStaleTasks` 入口生成 traceId。改动面：小（单文件新增装饰器 + 2 处 setTaskDecorator）。
- **关联**：次维度 `[Arch]`/`[Design]` 可运维性；与 B17-01 同源；关联 B16（TraceIdFilter 属 B16 全局基础设施）。

---

## `[Security]` 安全漏洞

> 排查范围：线程池/调度器是否暴露敏感信息、异步异常是否泄漏堆栈到外部、对账调度器是否会向未经授权的外部服务发请求。逐项覆盖计划 §2.2 技术栈重点后**未命中**与调度/异步直接相关的安全漏洞。

未发现。理由：
- 线程池配置不含密钥；对账调度器调用的 `crawlerTaskClient` 归 B10/B09，本模块仅触发；
- 异步异常走日志（`logback-spring.xml`），未发现回传前端；
- `@ConditionalOnExpression("!'${crawler.service.base-url:}'.isEmpty()")` 仅决定 Bean 是否注册，非鉴权，不构成安全风险。

---

## `[Arch]` 架构与技术债

> 排查范围：`@EnableAsync` 重复声明、两个线程池职责划分、配置 key 未显式声明、单实例假设。

### [P3] [Arch] `@EnableAsync` 在 BlogApplication 与 AsyncConfig 重复声明  <!-- 编号：B17-03 -->
- **定位**：`backend/src/main/java/com/nanmuli/blog/BlogApplication.java:10` + `backend/src/main/java/com/nanmuli/blog/infrastructure/config/ai/AsyncConfig.java:20`
- **现象**：`@EnableAsync` 同时出现在启动类（`BlogApplication.java:10`）和配置类（`AsyncConfig.java:20`）。Spring 的 `@EnableAsync` 是 `@Import` 元注解，重复声明只生效一次（Spring 内部去重），不报错也不产生两个切面。
- **影响**：纯冗余，无功能影响。已知线索（计划 §9 未直接列出，但任务提示"已知线索"）。轻微可维护性问题：阅读者会困惑"哪一个是生效的"。
- **根因/分析**：历史演进遗留——`BlogApplication` 上 `@EnableAsync`+`@EnableScheduling` 是早期启动配置；后引入 `AsyncConfig` 实现精细化线程池时又加了一次 `@EnableAsync`。`@EnableScheduling` 仅启动类一处（已 grep 确认）。
- **修复方向**：保留 `AsyncConfig` 上的 `@EnableAsync`（与 `AsyncConfigurer` 实现就近），移除 `BlogApplication.java:10` 的 `@EnableAsync`，保留 `@EnableScheduling`。改动面：小（删一行注解 + import）。
- **关联**：次维度 `[Bug]` 但后果为零故定 P3。

### [P3] [Arch] 线程池参数全走 `@Value` 默认值，yml 无显式声明  <!-- 编号：B17-04 -->
- **定位**：`infrastructure/config/ai/AsyncConfig.java:23-35`（6 个 `@Value`，均带默认值）；`application.yml` / `application-dev.yml` / `application-prod.yml` grep `async.executor` / `async` 均 **No matches**
- **现象**：`@Value("${async.executor.ai.core-pool-size:2}")` 等 6 个参数全有默认值，但所有 yml 文件均未声明这些 key。注释（`AsyncConfig.java:15-16`）写"从 application.yml 读取线程池参数，支持 dev/prod 差异化配置"，实际无差异化。
- **影响**：声明与实现不符——注释声称可差异化但从未差异化；运维想调线程池只能改代码或加 env，无文档化的配置入口。对单实例 MVP 影响有限（默认值 ai 2/5/50、task 3/8/100 偏保守但够用）。
- **根因/分析**：设计意图（可配置）未落到配置文件。非阻断，属文档/配置漂移。
- **修复方向**：在 `application.yml` 显式声明 `async.executor.ai.*` 和 `async.executor.task.*` 的默认值并加注释，或更新 `AsyncConfig` 注释为"当前使用默认值，如需调整可通过 env 覆盖"。改动面：小。
- **关联**：次维度 `[Deps]`/`[Design]`；横向主题"配置一致性"（关联 X06）。

### [P2] [Arch] 对账调度器无分布式锁，依赖单实例假设  <!-- 编号：B17-05 -->
- **定位**：`infrastructure/scheduler/TaskReconciliationScheduler.java:34-58`（`@Scheduled(fixedDelayString)`，无 ShedLock/Redis 锁）
- **现象**：`reconcileStaleTasks` 用单节点 `@Scheduled`，无任何分布式锁。`deploy/docker-compose.yml`（grep 确认 `container_name: nanmuli-backend`，无 `replicas`/`deploy.replicas`）当前单 backend 实例。
- **影响**：单实例 MVP 下无问题。但 README/CLAUDE.md 声称"≤2 内部服务调用"，未来若 backend 水平扩容到 2+ 实例，对账调度器会在每个实例并发触发，多实例同时 `syncFromPythonSilent` 同一批 stale 任务（`LIMIT 20`）。乐观锁（`WebCollectTask.@Version`，`WebCollectTask.java:20-21`）能挡住重复更新（一方 `OptimisticLockingFailureException` 被 `syncFromPythonSilent:381` 捕获），所以**不会数据损坏**，但会产生无谓的 Python API 重复 GET（每个实例都拉一次）和大量 info 日志。
- **根因/分析**：MVP 单实例设计取舍合理。需在 Design 节标注为已知扩展边界，避免未来直接扩容踩坑。
- **修复方向**：扩容前引入 ShedLock（已有 Redis，`redisson` 或 `shedlock-spring`）对 `reconcileStaleTasks` 加 `@SchedulerLock`；或在 Design 文档显式标注"backend 必须单实例部署"前置约束。改动面：中（引入依赖 + 配置）。
- **关联**：主维度其实是 `[Design]` 单点扩展，因有乐观锁兜底不构成 bug，故归 `[Arch]` 技术债/P2。

---

## `[Deps]` 依赖升级与版本

### 本模块依赖清单（基于声明文件，未翻依赖源码）

| 依赖 | 版本 | 声明位置 | 已知风险/可升级 | 备注 |
|---|---|---|---|---|
| Spring Framework (`spring-context`) | 随 Spring Boot 3.3.5 | `backend/pom.xml`（继承自 `spring-boot-starter`） | 3.3.x 维护期，可升至 3.3.6+/3.4.x | 提供 `@EnableAsync`/`@EnableScheduling`/`ThreadPoolTaskExecutor`/`AsyncConfigurer` |
| MyBatis Plus（`@Version` 乐观锁） | 3.5.9 | `backend/pom.xml` | 当前稳定 | 对账并发保护依赖此特性 |

> 排查范围：仅 `ThreadPoolTaskExecutor`/`AsyncConfigurer`/`@Scheduled`/`@Version` 相关依赖。未翻依赖源码。未命中需升级的版本问题。

未发现。Spring Boot 3.3.5 的调度/异步 API 稳定，无已知 CVE 影响本模块使用的 `spring-context` 调度/异步部分 `[需查证]`（具体 CVE 清单未在本次排查范围内逐条核对，建议 X04/X03 模块统一查 Spring Boot CVE）。

---

## `[Design]` 功能设计合理性

> **必填**。从真实使用出发回答计划 §2.5 中相关的问题。

**审视结论**：

1. **场景适配（问题 1）**：单人维护技术博客 + 每工作日 AI 日报场景下，调度/异步基础设施**配置合理偏保守**。两个线程池（ai 2/5/50、task 3/8/100）+ `CallerRunsPolicy` 拒绝策略，意味着 AI 高峰时回退到调用线程同步执行（背压），对单人博客流量是恰当的——不会丢任务、不会 OOM、不会把数据库连接池打爆。对账调度器 30 分钟阈值 + `LIMIT 20` + 10 分钟间隔，对偶发的 Python 回调失败足够覆盖，且不构成 DB 压力。**判断：场景适配良好，无需调整**。

2. **闭环完整性（问题 2）**：对账调度器形成了"Python 回调失败 → 本地任务卡 CRAWLING/PROCESSING → 调度器重新拉 Python 状态"的**自动修复闭环**。关键安全点：对账不是无脑 markFailed，而是 `syncFromPythonSilent` 拉取 Python 真实状态（`WebCollectorAppService.java:376-388`），若 Python 那边其实还在跑，本地会同步回 CRAWLING/PROCESSING，不会误杀。乐观锁（`@Version`）+ `OptimisticLockingFailureException` 捕获（`:381`）保证对账与回调并发安全。**判断：闭环完整且安全**。但缺一个"对账连续 N 次失败后的告警/人工介入入口"——当前只是 warn 日志。

3. **可运维性（问题 3）**：①对账调度器 Bean 受 `@ConditionalOnExpression("!'${crawler.service.base-url:}'.isEmpty()")` 控制（`TaskReconciliationScheduler.java:25`），即未配 crawler 地址时整个调度器不注册——合理但隐式，运维若发现"对账没跑"需先排查这个条件；②线程池在 shutdown 时 `aiTaskExecutor` 设了 `waitForTasksToCompleteOnShutdown(true)` + `awaitTerminationSeconds(60)`（`AsyncConfig.java:45-46`），但 `taskExecutor` **没设**（`:52-63`），停机时正在跑的首页聚合查询会被中断——影响轻；③日志统计对账 synced/failed（`:57`），可观测性基本够。**判断：可运维性中等**。

4. **单点与扩展（问题 7）**：见 B17-05，单实例假设需在扩容前处理（ShedLock）。MVP 阶段**无需调整**，但需文档化"backend 单实例"为部署前置约束。

### [P4] [Design] 对账调度器缺"连续失败告警"与人工触发入口  <!-- 编号：B17-06 -->
- **定位**：`infrastructure/scheduler/TaskReconciliationScheduler.java:43-57`（仅 info/warn 日志，无告警阈值，无手动触发端点）
- **现象**：对账调度器对每个任务 try-catch 记 warn，循环结束记 info 统计，但无"连续 N 轮失败率超阈值"的告警，也无管理端手动触发对账的 API。
- **影响**：Python 服务长时间不可用时，对账会持续 warn 刷屏但无人感知异常严重度；运维想立即对账（不等下个 10 分钟周期）只能重启或改 cron。
- **建议方向**：①加一个轮次级失败率指标（日志或未来接监控）；②在 admin Controller 暴露 `POST /api/admin/collector/reconcile` 手动触发（鉴权归 B06）。改动面：小～中。**当前 MVP 可接受，列为未来增强**。
- **关联**：次维度 `[Design]` 可运维性。

### [P4] [Design] 调度器条件开关 `@ConditionalOnExpression` 依赖 sys_config 注入时机，需文档化  <!-- 编号：B17-07 -->
- **定位**：`infrastructure/scheduler/TaskReconciliationScheduler.java:25`（`@ConditionalOnExpression("!'${crawler.service.base-url:}'.isEmpty()")`）+ `application-dev.yml:52-53`（注释 `crawler.service.* → sys_config`）
- **现象**：调度器 Bean 注册条件依赖 `crawler.service.base-url` 非空。dev 环境该 key 由 sys_config 表注入（非 yml/env），prod 由 `CRAWLER_SERVICE_URL` env 注入（`application-prod.yml:80`）。`@ConditionalOnExpression` 在 Bean 定义注册阶段求值，若 sys_config 注入晚于条件求值，调度器可能不注册。
- **影响**：dev 环境若 sys_config 未初始化 `crawler.service.base-url`，对账调度器静默不注册（无错误日志），运维难发现。属 B07 配置注入机制与 B17 调度的交互点。
- **建议方向**：①确认 B07 的 sys_config → `@Value`/`@ConditionalOnExpression` 注入时机（`[需查证]`）；②在启动日志显式打印"对账调度器已注册/已跳过"及原因。改动面：小。
- **关联**：关联 B07（配置模块）；`[需查证]`。

---

## 模块小结

### 严重度统计

| 级别 | 数量 | 条目编号 |
|---|---|---|
| P0 | 0 | — |
| P1 | 0 | — |
| P2 | 2 | B17-02、B17-05 |
| P3 | 3 | B17-01、B17-03、B17-04 |
| P4 | 2 | B17-06、B17-07 |

### Top 风险（本模块最该先看的 ≤3 条）

1. **B17-02 MDC/TraceId 在调度/异步线程不传播** —— 直接影响故障定位效率，调度日志和异步日志无法与触发请求串联，单人运维场景下放大排障成本。
2. **B17-05 对账调度器无分布式锁** —— 当前单实例无害，但属扩容硬阻塞，需在水平扩容前处理或文档化单实例约束。
3. **B17-01 `AsyncUncaughtExceptionHandler` 缺失** —— 当前靠业务层逐个 try-catch 兜底，基础设施层面无统一异步异常兜底，未来新增 `@Async void` 方法易遗漏。

### 修复优先级建议

- **立即**（P0/P1）：无。
- **计划**（P2）：
  - B17-02 加 `TaskDecorator` 做 MDC 传播（小改动，收益高）。
  - B17-05 在部署文档/CLAUDE.md 显式标注"backend 单实例"前置约束（或扩容前引入 ShedLock）。
- **择机**（P3/P4）：
  - B17-01 补 `AsyncUncaughtExceptionHandler`。
  - B17-03 去掉 `BlogApplication` 重复的 `@EnableAsync`。
  - B17-04 yml 显式声明线程池参数或修正注释。
  - B17-06/B17-07 按未来增强择机处理。

### 排查盲区 / 待复核

- **B17-07 `[需查证]`**：`@ConditionalOnExpression` 求值时机与 sys_config 注入（B07）的先后关系——若 sys_config 在 Bean 注册阶段尚未注入 `crawler.service.base-url`，dev 环境对账调度器可能不注册。需 B07 模块确认配置注入机制是否覆盖 `@Conditional*` 阶段。
- **B17-Debs `[需查证]`**：Spring Boot 3.3.5 的 `spring-context` 调度/异步部分是否有已知 CVE，本次未逐条核对，建议 X03/X04 统一查 Spring Boot CVE 清单。
- 未覆盖：`crawlerTaskClient.getTask`（对账实际调用的 Python HTTP 客户端）的超时/重试配置归 B10/B07，本模块仅确认对账会调用它；`logback-spring.xml` 的 `%X{traceId}` 占位是否真存在未逐行核对（已确认 TraceIdFilter put 的 key 是 `traceId`，但 logback pattern 是否消费该 key 属 B16 范围）。
