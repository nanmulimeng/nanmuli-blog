# C10 调度器 排查报告

> **模块编号**：C10
> **排查范围**：APScheduler 装配（日报 cron、信息源同步、优化记录清理）+ 防重入锁 + 超时 + 生命周期管理。关键文件 `crawler-service/standalone/scheduler.py`。
> **基线 commit**：`6ae930098405f4d0553d96a852f3345d0f39682e`
> **工作区状态**：本模块文件干净（`crawler-service/standalone/scheduler.py` 无未提交改动）。仓库整体处于脏状态（backend `WebCollectPageMapper.java`、`ConfigRepositoryImpl.java`、crawler `search.py`/`knowledge_base.py`/多 test、`deploy/README.md`、`scripts/release/release-gate.ps1` 等），均不触及本模块调度逻辑。
> **排查日期**：2026-06-24
> **排查人**：C10 audit agent
> **状态**：待复核

---

## 模块概览

**职责**：基于 APScheduler `AsyncIOScheduler` 编排三类周期任务——①工作日 8:00 自动生成 AI 技术日报；②每 5 分钟从 Java 后端同步信息源 cron 并注册/移除源任务；③每天清理 90 天前的优化记录。同时提供日报防重入锁（`_digest_lock`）、任务完成事件通知、调度器诊断状态。

**关键文件**：
- `crawler-service/standalone/scheduler.py:1-554` —— 全部调度逻辑（本模块主体，通读）。
- `crawler-service/main.py:51-109` —— `lifespan` 启停 `start_scheduler()`/`stop_scheduler()`，`workers=1`。
- `crawler-service/standalone/task_executor.py:250-292,505-506` —— `executor.submit`、`shutdown`、`notify_task_completion` 调用点。
- `crawler-service/standalone/routes.py:700-1010,1151` —— 调度状态查询、`/digests/trigger` 手动触发、健康检查引用。
- `crawler-service/optimization/knowledge_base.py:856-874` —— `cleanup_old_records(days=90)` 被 C10 直接调用。
- `crawler-service/standalone/repository.py:196-204` —— `get_digest_existing_non_failed`（防重复查询）。

**对外接口 / 依赖**：
- 对外（被调用）：`start_scheduler`、`stop_scheduler`、`get_scheduler_status`、`generate_scheduled_digest(force)`、`refresh_source_schedules`、`register_task_event`、`notify_task_completion`。
- 依赖（外发）：Java 后端 `GET/POST /api/internal/collector/sources*`（带 `X-Callback-Key`）；`executor.submit`；`repo.create_task/get_digest_existing_non_failed`；`KnowledgeBase.cleanup_old_records`。
- 配置 key：`DIGEST_CRON`、`digest.enabled`（backend_config）、`java_api_url`、`callback_api_key`、`callback_timeout`、`sources_api_timeout`、`max_concurrent_crawls`、`digest_search_engine`、`proxy_url`。
- 第三方库：`apscheduler>=3.10.0`、`httpx`、`aiosqlite`。

**已读文件清单**：
- `crawler-service/standalone/scheduler.py` —— 通读（1-554）。
- `crawler-service/main.py` —— 通读（lifespan + create_app）。
- `crawler-service/standalone/task_executor.py:240-292,500-510` —— 片段（submit/shutdown/notify 调用）。
- `crawler-service/standalone/repository.py:190-220` —— 片段（防重复查询）。
- `crawler-service/optimization/knowledge_base.py:854-874` —— 片段（cleanup 实现）。
- `crawler-service/standalone/routes.py:125-200,690-860,990-1010,1145-1155` —— 片段（调度诊断与手动触发）。
- `crawler-service/config.py:1-170` —— 片段（相关配置项）。
- `crawler-service/requirements.txt` —— 通读（依赖版本）。
- `crawler-service/tests/test_source_scheduling.py` —— grep（覆盖范围确认）。

**主模块归属**：本模块是 C10 自身主模块，深查。对 digest 编排内部只引用 C04；对 Java 内部回调端点契约只引用 B09；对配置一致性（`DIGEST_CRON`/`java_api_url`）只引用 X06。

---

## `[Bug]` 代码正确性与潜在缺陷

> 排查范围：`scheduler.py` 全文 + `main.py` lifespan + `task_executor.shutdown` 调用顺序 + `cleanup_old_records` 实现 + 防重复查询 SQL。

### [P1] [Bug] 日报生成全流程无 APScheduler 超时约束，`digest_global_timeout` 仅作用于板块爬取阶段  <!-- 编号：C10-01 -->
- **定位**：`scheduler.py:99-107`（`generate_scheduled_digest` 提交后直接 return）；`task_executor.py:294+`（`_execute` 内 digest 路径，`digest_global_timeout` 见 C04）；`scheduler.py:460-466`（`add_job` 未设 `misfire_grace_time`/`max_instances`）。
- **现象**：C10 的 `generate_scheduled_digest` 调用 `executor.submit(task_id)` 后立即返回，APScheduler 任务函数本身在毫秒级结束，因此 APScheduler 侧没有任何"日报生成超时"概念。真正的超时（`settings.digest_global_timeout=600`，见 `config.py:143`）只作用于 C04 的板块并行爬取阶段。AI 栏目清洗、organizer、save 等后续阶段若长时间阻塞或挂起，APScheduler 既不会取消也不会告警。
- **影响**：若 AI 整理或落库阶段卡住（如远端模型 hang、httpx 连接池耗尽），日报任务会无限期占用 `_digest_lock` 之外的 executor 槽位且无超时兜底，次日 cron 触发时因 `get_digest_existing_non_failed` 命中卡住的 `status != 4` 记录而 skip，连续多日缺日报且无告警。
- **根因/分析**：调度层把超时责任完全下放到 C04 的板块阶段；APScheduler `add_job` 未配置 `misfire_grace_time`，且 `AsyncIOScheduler` 默认 `max_instances=1` + 默认 `coalesce` 行为未显式声明。已排除误判：`_digest_lock` 仅保护"创建任务"临界区（`scheduler.py:83`），不覆盖整个执行过程。
- **修复方向**：①在 `add_job` 显式声明 `misfire_grace_time`/`max_instances`/`coalesce`；②对 digest 任务在 executor 内增加端到端 `asyncio.wait_for` 包裹（属 C04，C10 仅触发）；③调度层在 skip 时记录"因前一日任务未结束而跳过"的可观测信号。（改动面：中，跨 C04）
- **关联**：C04（日报编排超时）、横向主题"可运维性/告警"。

### [P2] [Bug] `generate_scheduled_digest` 用 `datetime.date.today()` 取本地日期，与 cron 时区及数据时间戳口径不一致  <!-- 编号：C10-02 -->
- **定位**：`scheduler.py:84`（`today = datetime.date.today().isoformat()`）；`config.py:133`（`digest_cron` 默认 `0 8 * * 1-5`，未声明时区）；`repository.py:200`（防重复查询用同一 `today`）。
- **现象**：`date.today()` 取**进程宿主机本地时区**。APScheduler `AsyncIOScheduler` 默认时区同样取宿主机本地时区（未在 `start_scheduler` 设置 `timezone=`），所以 cron 触发与 `today` 通常一致；但一旦容器宿主机时区非东八区（Docker 默认 UTC，见 X01/X02 部署），cron 会在 UTC 8:00（北京 16:00）触发，且 `today` 返回 UTC 日期，导致日报 `digest_date` 与业务期望的"北京工作日"错位。
- **影响**：容器以 UTC 运行时，日报生成时间错位 8 小时，且 `digest_date` 标记为 UTC 日期，前端按日期查询会"少一天/错一天"。属时区口径漂移，归 X02-02 横向主题。
- **根因/分析**：`AsyncIOScheduler()` 未传 `timezone`（`scheduler.py:454`），`CronTrigger(**cron_params)` 也未传 `timezone`（`scheduler.py:462,153`），全程依赖宿主机 TZ 环境变量。
- **修复方向**：①显式给 scheduler 与 trigger 传入 `pytz.timezone(settings.timezone or "Asia/Shanghai")`；②`today` 改用相同时区下的 `datetime.now(tz).date()`；③配置新增 `TIMEZONE` 项（归 X06）。（改动面：小）
- **关联**：X02-02（时区）、X06（配置一致性）。

### [P2] [Bug] 优雅关闭先停调度器后停 executor，正在执行的信息源任务被 cancel 后才被 executor.shutdown 标记 FAILED，状态更新顺序倒置  <!-- 编号：C10-03 -->
- **定位**：`main.py:86-107`（`yield` 后先 `stop_scheduler()` 再 `executor.shutdown()`）；`scheduler.py:513-520`（`stop_scheduler` 调 `_scheduler.shutdown(wait=False)`）；`task_executor.py:277-292`（`shutdown` cancel 任务并 `fail_task`）。
- **现象**：`stop_scheduler` 用 `wait=False` 立即返回，不等待运行中的 source job / digest job。随后 `executor.shutdown` cancel 运行任务并 `repo.fail_task(tid, "Service shutting down")`。问题在于：信息源任务在 `_wait_and_update_source_status`（`scheduler.py:229-272`）中等待 event 时被 cancel，`except` 路径会调用 `_update_source_run_status(source_id, "failed", ...)` 通知 Java；但此时调度器已停，且若 Java 后端此时不可达，`httpx` 调用失败仅 warning（`scheduler.py:330-332`），Java 侧源状态会停留在 `running` 永不更新。
- **影响**：重启时 Java 后端可能看到信息源"永久 running"，影响 `refresh_source_schedules` 的活跃判定与前端展示。日报任务同理，但日报有 `get_digest_existing_non_failed` 兜底（FAILED 会被排除）。
- **根因/分析**：关闭顺序导致 source 状态通知与任务 cancel 存在竞态；`_update_source_run_status` 是 fire-and-forget，无重试无落库。
- **修复方向**：①`stop_scheduler` 改为 `wait=True` 或给关键 job 设超时；②`executor.shutdown` cancel 前先尝试一次性 flush 状态通知；③Java 侧对超时 running 状态加兜底回收（属 B09）。（改动面：中，跨 B09）
- **关联**：B09（内部回调/源状态）、横向主题"跨服务契约"。

### [P3] [Bug] `_wait_and_update_source_status` 的事件等待 + 指数退避轮询存在 event 未注册时的无谓 busy-wait  <!-- 编号：C10-04 -->
- **定位**：`scheduler.py:229-272`。
- **现象**：当 `event is None`（即 `register_task_event` 未被调用，例如非调度器触发的任务路径）时，循环每次仅 `await asyncio.wait_for` 一个不存在的等待——实际代码在 `event is None` 时跳过 wait（`if event is not None`），仅靠 `intervals` 轮询 DB，最坏每 10s 查一次最长 300s。
- **影响**：调度器提交的信息源任务，`register_task_event` 在 `task_executor` 内是否调用取决于 `_execute` 路径——`notify_task_completion` 在 `task_executor.py:505` 调用，但 `register_task_event` 调用点未见（仅 `notify` 被调用，`register` 调用方需在创建任务后注册）。若 event 字典缺失，退化为纯轮询，300s 超时前 Java 源状态延迟更新。
- **根因/分析**：`_task_completion_events` 的写入端（`register_task_event`）在本模块外，调用链不闭环；`[需查证]` 是否所有调度器路径都在 `executor.submit` 前调用了 `register_task_event`。
- **修复方向**：①确认 `register_task_event` 在 `create_task` 后统一调用（可能在 `task_executor.submit` 内补）；②event 缺失时降低轮询开销。（改动面：小）
- **关联**：`[需查证]`。

### [P3] [Bug] `parse_cron` 对 APScheduler cron 语义无校验，`0 8 * * 1-5` 之外的非法表达式只抛 ValueError 被吞  <!-- 编号：C10-05 -->
- **定位**：`scheduler.py:54-69`（`parse_cron` 仅按空格切分）；`scheduler.py:158`（`except (ValueError, Exception)` 实质捕获所有异常并 warning）。
- **现象**：`parse_cron` 只校验字段数=5，不校验字段合法性（如 `25 8 * * *` 合法，`abc 8 * * *` 会在 `CronTrigger` 构造时才报错）。信息源同步时 `refresh_source_schedules` 捕获异常后仅 `logger.warning`，源被静默跳过，Java 端无感知。
- **影响**：用户在 Java 管理端配置了非法 cron 的信息源，crawler 静默不调度，排查困难。
- **修复方向**：①在 `_update_source_run_status` 增加 `invalid_cron` 状态回传 Java；②`parse_cron` 增加字段级校验。（改动面：小，跨 B09）
- **关联**：B09（源状态回调）。

---

## `[Security]` 安全漏洞

> 排查范围：`X-Callback-Key` 使用、Java API 鉴权、httpx 超时、SSRF（信息源 URL 来自 Java）、密钥日志泄露。逐项覆盖 §2.2 重点：本模块不涉及 Sa-Token/MyBatis/AES/CORS/文件上传；涉及双向 key（X-Callback-Key）与 SSRF（信息源 URL）。

### [P3] [Security] `X-Callback-Key` 与 `X-API-Key` 双向 key 的强度、恒定时间比较、日志泄露归 B09/X06，本模块仅调用方视角补充  <!-- 编号：C10-06 -->
- **定位**：`scheduler.py:312-314,432-433`（设置 `X-Callback-Key` header）；`scheduler.py:328-329`（日志记录 status_code 不记 key，安全）。
- **现象**：本模块仅作为 key 的**消费方**把 `settings.callback_api_key` 放入 header，不做比较；日志只记 `resp.status_code`，不记 key/header，未发现泄露。key 强度、Java 侧比较方式见 B09。
- **影响**：本模块视角无新增安全问题。
- **根因/分析**：消费方无恒定时间比较需求；唯一隐患是若 `callback_api_key` 为空（默认 `""`，`config.py:147`），`scheduler.py:313` 的 `if settings.callback_api_key` 会跳过 header，请求以无鉴权发往 Java——但 Java 内部端点是否豁免 key 归 B09。
- **修复方向**：见 B09（双向 key 强度）。本模块无需改动。
- **关联**：B09、X06。

### [P3] [Security] 信息源 URL（`src.value`）由 Java 透传，本模块直接喂给 crawl/feed，SSRF 防护依赖 C03 的 `ssrf_guard`，调度层无额外校验  <!-- 编号：C10-07 -->
- **定位**：`scheduler.py:189-219,341-352`（`src_value` 直接进入 `crawl_single_page`/`parse_feed`）。
- **现象**：调度器从 Java 拉取的 `sources` 中的 `value` 字段（URL/keyword）未经调度层校验即进入爬取。SSRF 防护在 C01 `ssrf_guard` 与 C03 各引擎内部。
- **影响**：若 Java 管理端被注入内网 URL 且 `ssrf_guard` 配置为 allow private（`callback_allow_private_urls`，`config.py:148`），调度路径会触发 SSRF。属既有 `ssrf_guard` 不防 DNS rebinding 的延伸。
- **修复方向**：见 C01（ssrf_guard 主模块）。本模块无需改动。
- **关联**：C01、横向主题 SSRF。

---

## `[Arch]` 架构与技术债

> 排查范围：调度器单例、`_registered_source_jobs` 全局可变状态、闭包 job 创建、模块耦合。共享对象按 §8.6 归属，本节只记 C10 视角。

### [P2] [Arch] 单实例假设未显式声明：`AsyncIOScheduler` 默认 `max_instances=1`，但多 worker/多容器部署会重复执行日报 cron  <!-- 编号：C10-08 -->
- **定位**：`scheduler.py:454`（`AsyncIOScheduler()` 无 `job_defaults`）；`main.py:154`（`workers=1` 硬编码）。
- **现象**：`main.py` 强制 `workers=1`，单进程内 `max_instances=1` 默认值能防同一 job 重叠。但：①若运维误改 `workers>1` 或用多容器（compose 横扩），每个进程独立持有 scheduler，日报 cron 会在多个实例同时触发；②`_digest_lock` 是**进程内** `asyncio.Lock`（`scheduler.py:13`），跨进程无效；③防重复靠 SQLite `get_digest_existing_non_failed`，多实例并发时存在 TOCTOU 窗口（两实例同时查到不存在 → 同时 `create_task`）。
- **影响**：多实例下可能创建两条当日日报任务（最终 `_build_digest_detail` 取最新一条，但浪费 AI 算力 + 重复爬取）。
- **根因/分析**：单实例假设靠 `workers=1` 隐式维持，无文档/断言；`max_instances` 默认值只在单进程内生效。
- **修复方向**：①部署文档明确"crawler 单实例"约束（归 X01）；②`create_task` 增加唯一约束（`task_type+digest_date` 唯一索引，归 C09）；③改用分布式锁或 DB 行锁。（改动面：中，跨 C09/X01）
- **关联**：C09（数据层）、X01（部署）。

### [P3] [Arch] 模块级全局可变状态 `_registered_source_jobs`、`_scheduler`、`_task_completion_events` 在并发刷新与测试间共享，可读性差  <!-- 编号：C10-09 -->
- **定位**：`scheduler.py:21-22,37`（三个模块级全局）。
- **现象**：`_registered_source_jobs` 是 `set[str]`，`refresh_source_schedules` 用 `global` 重新赋值（`scheduler.py:121`）；测试 `test_source_scheduling.py:208` 直接 `patch` 该全局。
- **影响**：全局可变 + `global` 赋值增加并发推理负担，测试需手动 patch 污染。非 bug，可维护性问题。
- **修复方向**：封装为 `SchedulerRegistry` 类单例，状态内聚。（改动面：中）
- **关联**：无。

### [P3] [Arch] C10 同时承担"调度装配"与"信息源执行编排"（`execute_scheduled_source`/`_execute_rss_source`）两职责，文件 554 行偏长  <!-- 编号：C10-10 -->
- **定位**：`scheduler.py:182-420`（信息源执行 + RSS 独立爬取逻辑）。
- **现象**：调度器文件内嵌完整的 RSS 爬取编排（`parse_feed` → 并发 `crawl_single_page` → `save_pages`），与 C03 采集核心、C04 编排存在职责重叠。
- **影响**：RSS 路径的并发控制、错误处理与 C03 单页爬取重复实现，维护时易漂移。
- **修复方向**：将 `_execute_rss_source` 抽到 `crawler/source_agent.py` 或独立模块，scheduler 只负责触发。（改动面：中，归 C07/C03 边界）
- **关联**：C03、C07。

---

## `[Deps]` 依赖升级与版本

### 本模块依赖清单（基于声明文件，未翻依赖源码）

| 依赖 | 版本 | 声明位置 | 已知风险/可升级 | 备注 |
|---|---|---|---|---|
| apscheduler | `>=3.10.0` | `requirements.txt:35` | 3.x 稳定；4.x 已发布（重写 async API），升级为破坏性变更 | 本模块用 3.x `AsyncIOScheduler` API |
| httpx | `>=0.26.0` | `requirements.txt:13` | 当前 0.28+，无已知 CVE | 用于 Java API 调用 |
| aiosqlite | `>=0.19.0` | `requirements.txt:32` | 无已知风险 | 经 repo 间接使用 |
| pydantic-settings | `>=2.1.0` | `requirements.txt:17` | 无已知风险 | `config.Settings` |

> 排查范围：仅 C10 直接/间接使用的运行时依赖。未发现阻断级版本问题。

### [P4] [Deps] APScheduler 3.x → 4.x 为破坏性升级，当前 3.x API（`AsyncIOScheduler`/`CronTrigger`）在 4.x 需重写  <!-- 编号：C10-11 -->
- **定位**：`requirements.txt:35`（`apscheduler>=3.10.0`）；`scheduler.py:7-8,454`。
- **现象**：项目锁定 3.x API。4.x 已正式发布且改为 dataclass + scheduler 分离架构，`AsyncIOScheduler` 用法不同。
- **影响**：未来升级需重写 `start_scheduler` 与 job 注册。当前无安全风险，记录备选。
- **修复方向**：暂不升级；升级时同步评估 misfire/coalesce 默认值变化。（改动面：大，未来）
- **关联**：无。

---

## `[Design]` 功能设计合理性

> 必填。从真实使用出发，回答计划 §2.5 中相关的问题。

**审视结论**：

1. **场景适配（单人技术博客 + 每工作日 AI 日报）**：调度设计匹配场景——工作日 8:00 cron、防重复、手动 force 重触发、信息源 cron 同步。但**节假日处理缺失**：`0 8 * * 1-5` 不识别中国法定节假日/调休，节假日照常生成（轻度浪费算力），调休周末不生成（可能漏报）。对单人博客可接受，但与"工作日"语义不完全对齐。
2. **闭环完整性（错过执行弥补）**：**存在缺口**——APScheduler 默认 `misfire_grace_time=1` 秒，若服务在 8:00:01 后才启动，当天的日报 cron 会被丢弃（misfire），次日才有。无任何补偿机制（无启动时检查"今天日报缺失则补生成"）。CLAUDE.md 称"工作日定时"，但服务重启时间窗错过的日报需手动 `/digests/trigger?force=true`。这是真实运维痛点。
3. **可运维性（故障定位/恢复/告警）**：调度状态查询完善（`get_scheduler_status` + routes 诊断），但**缺主动告警**：日报连续 N 天 skip/error 无通知；信息源同步连续失败无告警。需人工看日志或看管理端。

### [P1 / Design] 日报 cron 无 misfire 补偿，服务重启错过执行窗口则当天日报静默丢失  <!-- 编号：C10-12 -->
- **定位**：`scheduler.py:454-466`（`add_job` 未设 `misfire_grace_time`）；APScheduler 3.x 默认 `misfire_grace_time=1`。
- **现象**：`AsyncIOScheduler` 默认 `job_defaults.misfire_grace_time=1` 秒。若 crawler 服务在 8:00:01+ 启动（如容器重启、部署、崩溃恢复），当日 `digest_daily` 被判定 misfire 并跳过，无补偿。
- **影响**：单人运维场景下，一次部署或崩溃恢复若发生在早 8 点附近，当天日报直接缺失，需手动触发。属真实可用性缺口，非理论问题。
- **根因/分析**：未显式配置 misfire 策略，依赖 1 秒默认值过于严苛。
- **建议方向**：①`add_job` 设 `misfire_grace_time` 为较大值（如 3600s）+ `coalesce=True`；②`start_scheduler` 启动时检查"今日工作日且无当日日报"则补触发一次（需结合节假日）。标 `无需调整` 之外的首选。（改动面：小）
- **关联**：横向主题"可运维性"。

### [P3 / Design] 节假日/调休未处理，`0 8 * * 1-5` 在中国日历下语义不精确  <!-- 编号：C10-13 -->
- **定位**：`config.py:133`（`digest_cron` 默认值）。
- **现象**：cron 仅按周一至周五触发，不识别节假日。
- **影响**：节假日多生成（算力浪费，AI 成本）、调休日漏生成。单人博客可接受。
- **建议方向**：维持现状（`无需调整`）或未来接入 `chinese_calendar` 库判定工作日。（改动面：小，可选）
- **关联**：无。

### [P4 / Design] 优化记录清理策略固定 90 天且无条件删除，无归档无审计  <!-- 编号：C10-14 -->
- **定位**：`scheduler.py:484-501`；`knowledge_base.py:856-874`。
- **现象**：每天清理 90 天前 `optimization_record`，硬删除无归档。
- **影响**：长期趋势分析被截断在 90 天；单人博客数据量小，90 天够用。
- **建议方向**：维持现状（`无需调整`）；若需长期趋势，可改为软删除或延长保留期。（改动面：小，可选）
- **关联**：C07（知识库/趋势）。

---

## 模块小结

### 严重度统计

| 级别 | 数量 | 条目编号 |
|---|---|---|
| P0 | 0 | — |
| P1 | 2 | C10-01（日报全流程无超时）、C10-12（misfire 无补偿） |
| P2 | 3 | C10-02（时区）、C10-03（关闭顺序竞态）、C10-08（单实例假设） |
| P3 | 5 | C10-04、C10-05、C10-06、C10-07、C10-09、C10-10、C10-13 |
| P4 | 2 | C10-11、C10-14 |

### Top 风险（本模块最该先看的 ≤3 条）

1. **C10-12 日报 cron 无 misfire 补偿** —— 服务重启错过 8:00 窗口则当天日报静默丢失，真实运维痛点，改动面小。
2. **C10-01 日报生成全流程无 APScheduler 超时约束** —— AI/落库阶段挂起无兜底，可能连续多日缺日报且无告警。
3. **C10-02 时区口径漂移** —— 容器 UTC 运行时日报日期错位 8 小时，与 X02-02 横向主题呼应。

### 修复优先级建议

- **立即（P1）**：C10-12（misfire_grace_time + 启动补偿）、C10-01（端到端超时，跨 C04）。
- **计划（P2）**：C10-02（显式时区）、C10-03（关闭顺序）、C10-08（单实例约束文档/DB 唯一索引）。
- **择机（P3/P4）**：C10-04/05/09/10 可维护性、C10-13/14 设计取舍、C10-11 未来升级。

### 排查盲区 / 待复核

- **[需查证] C10-04**：`register_task_event` 的所有调用方未在本模块确认，需在 C03/C04/task_executor 全链路核验 event 字典是否被正确注册，否则退化为轮询。
- **[需查证] C10-08**：多容器/多 worker 部署是否在任何环境（compose 横扩、k8s）存在，需 X01 确认；当前 `main.py` `workers=1` 单实例假设是否在部署文档固化。
- **[需查证] APScheduler 3.x `misfire_grace_time` 默认值**：本报告基于训练知识判定为 1 秒，未查依赖源码（§1.3.1），实际默认以 APScheduler 文档为准。
- 未深入 C04 digest 编排内部超时实现（归 C04 主模块）。
- 未验证 Java 侧 `/api/internal/collector/sources` 端点契约字段（归 B09）。
