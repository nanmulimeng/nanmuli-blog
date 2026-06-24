# C09 数据层 SQLite 排查报告

> **模块编号**：C09
> **排查范围**：crawler-service 的 SQLite 独立存储层（aiosqlite 连接复用、增量迁移、孤儿任务恢复、PRAGMA 配置、Task/Page/Section/Item/OptimizationRecord 全 CRUD）
> **基线 commit**：`6ae930098405f4d0553d96a852f3345d0f39682e`
> **工作区状态**：脏。本模块核心文件（`crawler-service/standalone/db.py`、`standalone/repository.py`、`standalone/models.py`、`standalone/config.py`、`standalone/scheduler.py`、`standalone/task_executor.py`、`crawler/digest_orchestrator.py`）**均未在未提交改动列表中**；同分支未提交改动涉及 `crawler-service/crawler/search.py`、`optimization/knowledge_base.py` 及若干测试（属 C03/C07 范畴），不影响本报告结论。
> **排查日期**：2026-06-24
> **排查人**：C09 排查 agent
> **状态**：待复核

---

## 模块概览

**职责**：为 crawler-service 独立运行模式提供持久化底座——SQLite + aiosqlite 异步驱动，承担建表/PRAGMA/增量迁移/孤儿任务恢复，以及 Task/Page/Section/Item/OptimizationRecord 五表的全部 CRUD。crawler 全模块通过 `repository` 函数式 API 读写数据。

**关键文件**：
- `crawler-service/standalone/db.py:1-253` —— DDL、`_MIGRATIONS` 增量迁移链、`init_db()`、`get_db()`（ContextVar 嵌套连接复用）、`task_scoped_db()`。
- `crawler-service/standalone/repository.py:1-812` —— 全部 CRUD（Task / AI 结果 / Digest 结构 / Page / Stats / OptimizationRecord）。
- `crawler-service/standalone/models.py:1-55` —— `TaskStatus`（5 态对齐 Java `CollectTaskStatus`）、`PageStatus`、模板枚举。
- `crawler-service/config.py:47,102` —— `db_path`、`db_busy_timeout` 默认值。

**对外接口 / 依赖**：
- 对外：函数式 repository API（`create_task`/`get_task`/`save_ai_results`/`save_digest_results`/`save_optimization_round` 等），被 `task_executor`、`scheduler`、`digest_orchestrator`、`keyword_handler`、各 API 路由调用。
- 依赖：`aiosqlite>=0.19.0`（requirements.txt:32）、`config.settings`、`crawler.utils.normalize_url`。

**已读文件清单**：
- `crawler-service/standalone/db.py` —— 通读
- `crawler-service/standalone/repository.py` —— 通读
- `crawler-service/standalone/models.py` —— 通读
- `crawler-service/config.py`（db_path / db_busy_timeout 段）—— 通读
- `crawler-service/standalone/task_executor.py:240-360` —— 片段（连接复用边界）
- `crawler-service/standalone/scheduler.py:1-100` —— 片段（digest_date 来源）
- `crawler-service/crawler/digest_orchestrator.py:660-720` —— 片段（并发与 DB）
- grep 覆盖：`task_scoped_db`/`_db_connection`/`asyncio.create_task`/`datetime`/`backup`/`VACUUM`/`rollback`/`execute_fetchall`

**主模块归属**：本模块是 **SQLite 数据层主模块**（C09）。对以下共享对象**深查**：aiosqlite 连接复用、增量迁移、PRAGMA、孤儿恢复。对以下共享对象**只引用**，不展开：SQLite vs PostgreSQL 跨库一致性 → **X02**；schema 定义的 SQLite 部分（字段类型/索引/外键）跨库视角 → **X02**。

---

## `[Bug]` 代码正确性与潜在缺陷

> 排查范围：db.py 全量（连接复用/迁移/PRAGMA/孤儿恢复）、repository.py 全量（事务边界/批量写/JSON 序列化/时间戳）、models.py 枚举一致性。

### [P2] [Bug] 增量迁移用 `PRAGMA table_info` 检测索引，索引类迁移每次启动都"假应用"   <!-- 编号：C09-01 -->
- **定位**：`crawler-service/standalone/db.py:182-191` + `_MIGRATIONS` 定义 `db.py:157,161`
- **现象**：`_MIGRATIONS` 列表混排了"列迁移"（如 `digest_date`、`time_range`）和"索引迁移"（`idx_digest_date`、`idx_opt_record_keyword`）。检测逻辑只查 `PRAGMA table_info(crawl_task)` 取列名集合 `existing_columns`（db.py:182-183），对每个迁移项用 `col_name not in existing_columns` 判定是否执行（db.py:186）。索引名永远不会出现在列集合里，故这两个索引迁移**每次启动都被判定为"需要应用"**，靠 `CREATE INDEX IF NOT EXISTS`（db.py:158,161 的 SQL）幂等性兜底，每次都会打印 `logger.info("Migration applied: %s", col_name)`（db.py:189）。
- **影响**：①日志噪声——每次重启日志都谎报"应用了 idx_digest_date/idx_opt_record_keyword 迁移"，干扰真实迁移追踪；②迁移链脆弱——检测口径与迁移项类型不一致，未来若新增非 `crawl_task` 表的迁移（如对 `crawl_page` 加列），`table_info(crawl_task)` 查不到，会误判已存在从而跳过；③`[需查证]` 多实例并发启动场景下，由于无版本表，两个进程同时探测到"缺列"并并发 `ALTER TABLE`，第二个会因 SQLite schema lock 失败被 `except` 吞掉（db.py:190-191 仅 warning），不会损坏但难诊断。
- **根因/分析**：迁移设计者用单一列名集合覆盖列+索引两种对象，类型未区分。已排除：`CREATE INDEX IF NOT EXISTS` 保证不会真正重复建索引，无数据损坏。
- **修复方向**：①为索引迁移单独走 `CREATE INDEX IF NOT EXISTS`（无需探测），或引入 `PRAGMA index_list` 探测；②中期引入真正的 schema 版本表（如 `schema_version`），记录已应用迁移名，消除列探测脆弱性（改动面：中）。`[需查证]` 并发启动场景需结合 C10 调度器启动时序确认。
- **关联**：X02-09（已知线索"增量迁移无版本表靠列探测，迁移链脆弱"）；横向主题 schema 漂移（§2.6）。

### [P2] [Bug] 孤儿任务恢复无时间窗口，正常重启也会把"刚提交的活跃任务"误杀为 FAILED   <!-- 编号：C09-02 -->
- **定位**：`crawler-service/standalone/db.py:195-205`
- **现象**：`init_db()` 在每次启动时无条件执行 `UPDATE crawl_task SET status=4 WHERE status IN (1,2)`（db.py:196-200），把所有 CRAWLING/PROCESSING 任务重置为 FAILED。无时间窗口限制，不区分"上次崩溃遗留"与"正常重启时恰好有任务在跑"。
- **影响**：crawler 正常重启（如配置热重载、手动重启、部署滚动更新）时，若此时有活跃任务（通过 API 提交后未完成），会被直接判失败，用户需手动重试。对单写者 + 低并发场景，重启窗口内命中活跃任务概率不高但非零；对部署滚动更新场景更明显。
- **根因/分析**：设计假设"重启即崩溃遗留"，未考虑干净重启。已排除：这不是数据损坏，任务可重试（`reset_task_for_retry` repository.py:350）。
- **修复方向**：①加时间窗口——仅重置 `updated_at` 早于某阈值（如 30 分钟前）的 CRAWLING/PROCESSING 任务；②或在 shutdown 时主动 fail 运行中任务（`task_executor.shutdown` 已做，见 task_executor.py:277-292），启动恢复仅处理"shutdown 未覆盖的崩溃"（改动面：小）。
- **关联**：次维度 `[Design]`（可运维性）。

### [P3] [Bug] 时间戳双标准：DB 列存 UTC（`datetime('now')`），digest_date 存本地时间   <!-- 编号：C09-03 -->
- **定位**：列默认 `datetime('now')`（db.py:58,59,80,93,107,133，SQLite 返回 UTC TEXT）；`digest_date` 来源 `datetime.date.today().isoformat()`（repository.py:254、scheduler.py:84）
- **现象**：所有 `created_at`/`updated_at` 默认值由 SQLite `datetime('now')` 生成（UTC，无时区后缀的 TEXT）。但 `digest_date`（业务关键过滤字段）由 Python `datetime.date.today()` 生成，取本地日期。`list_digests_with_ai`、`get_digest_by_date`、`get_digest_today_pending_or_running` 均用 `digest_date` 过滤。
- **影响**：在 UTC+8 服务器上，UTC 0:00-8:00 之间（北京 8:00-16:00）生成的日报，`digest_date` 是本地今天，但 `created_at` 的 UTC 日期是"昨天"。按 `digest_date` 查没问题（业务一致），但任何跨 `created_at` 与 `digest_date` 的对账/排序会产生偏差。`[需查证]` 当前无代码同时依赖两者做日期级对账，故实际不触发功能性 bug。
- **根因/分析**：两套时间源（SQLite 函数 vs Python），未统一。`datetime('now')` 是 UTC 是 SQLite 文档行为，已确认。
- **修复方向**：①统一用 Python 端生成 UTC ISO 时间戳写入（去掉 `DEFAULT datetime('now')`，insert 时显式赋值）；或②文档明确"digest_date 为本地业务日期，created_at 为 UTC 技术时间"，不改代码（改动面：小）。
- **关联**：X02-02（已知线索"SQLite UTC TEXT vs PG 时区"）；横向主题 schema 漂移（§2.6）。

### [P3] [Bug] `rollback` 守卫 `await (... if hasattr else None)` 形式可读性差且防护无效   <!-- 编号：C09-04 -->
- **定位**：`crawler-service/standalone/repository.py:346,371,481,655`
- **现象**：异常分支写 `await db.rollback() if hasattr(db, 'rollback') else None`。`aiosqlite.Connection` 恒有 `rollback` 方法，`hasattr` 恒为 True，`else None` 分支永不触发；形式上是 `await (A if cond else None)`，若条件为假会 `await None` 引发 TypeError。
- **影响**：当前无害（条件恒真），但属于误导性防御代码，未来若有人误以为 `else` 分支生效或重构条件，会引入运行时错误。
- **根因/分析**：写法想兼容"非 aiosqlite 的 mock"，但仓库内所有 `get_db()` 返回的都是 aiosqlite.Connection。
- **修复方向**：简化为 `await db.rollback()`，若需测试兼容在测试端 mock（改动面：小）。
- **关联**：无。

### [P3] [Bug] digest 公开列表先全量拉取再 Python 端分页，数据量增长后内存/性能退化   <!-- 编号：C09-05 -->
- **定位**：`crawler-service/standalone/repository.py:147-161`（`list_digests_with_ai` 非 include_all 分支）、`repository.py:178-193`（`get_public_digest_by_date`）、`repository.py:220-234`（`get_latest_public_digest`）
- **现象**：`is_publishable_digest_task`（repository.py:40-55）需要解析 `ai_search_metadata` JSON 判断 `digest_publishable`，无法下推到 SQL。故上述函数先 SQL 全量拉取所有 COMPLETED + 有 ai_title 的 digest 行，再在 Python 端逐条过滤，最后才切片分页（repository.py:157-161）。
- **影响**：随历史日报累积（每日 1 条，一年 365 行），单次公开列表请求拉全表 + 全量 JSON 解析，N 大时 CPU/内存线性增长。MVP 阶段（数十条）无感，但无上限。
- **根因/分析**：publishable 判断依赖 JSON 内字段，SQLite 原生不便查询 JSON（需 JSON1 扩展且语句复杂）。当前用 Python 兜底，合理但牺牲了分页精度。
- **修复方向**：①若 `digest_publishable != false` 是常态，可改为 SQL 端 `ai_search_metadata NOT LIKE '%"digest_publishable":false%'` 粗筛后再 Python 精筛，减少传输量；②或冗余一个布尔列 `is_publishable`（改动面：中）。
- **关联**：次维度 `[Design]`（单点与扩展）。

---

## `[Security]` 安全漏洞

> 排查范围：SQL 注入（参数化/字符串拼接）、敏感字段（callback_headers/api_key）、文件路径（db_path）。逐项覆盖 §2.2：本模块不涉及 Sa-Token/MyBatis/Cookie/CORS/AES/SSRF/文件上传/双向 key（crawler 侧 key 属 C02）。

**排查结论**：未发现本模块直接引入的安全漏洞。

- **SQL 注入**：所有 repository 查询均用 `?` 参数化（如 repository.py:71-82、108-117、500-504）。唯一动态拼接是 `get_digest_sections` 的 IN 子句占位符（repository.py:500-502），用 `"?" * len(section_ids)` 生成占位符、值仍走参数，安全。`list_tasks` 的 where 子句拼接（repository.py:105）只拼 `AND status = ?` 字面结构、值参数化，安全。
- **敏感字段**：`callback_headers`（db.py:160）可能含鉴权头，明文存 SQLite TEXT。属跨服务双向 key 主题，主模块 B09/C02，本模块只记录"明文落库"这一事实，不展开。
- **db_path**：默认 `data/crawler.db`（config.py:47），相对路径，无路径遍历风险（由 `os.makedirs` 确保目录存在 db.py:168-169）。

### [P3] [Security] callback_headers 明文存储，含鉴权头时随 DB 文件泄露   <!-- 编号：C09-06 -->
- **定位**：`crawler-service/standalone/db.py:160`（列定义）、`repository.py:67,79`（写入）
- **现象**：`callback_headers TEXT` 明文存储回调头，可能包含 `X-Callback-Key` 等鉴权信息。
- **影响**：SQLite 是单文件（`data/crawler.db`），文件级泄露（备份外泄、容器卷挂载失误）即泄露所有回调鉴权头。
- **根因/分析**：crawler 独立存储无字段级加密（与 backend AES 配置加密 B07 不同体系）。
- **修复方向**：①敏感头不入库，仅运行时传递；②或落库前哈希/加密（改动面：中）。属低优——前提是 DB 文件已被泄露。
- **关联**：B09（双向 key）、X06（配置一致性）；横向主题 跨服务契约（§2.6）。

---

## `[Arch]` 架构与技术债

> 排查范围：连接复用策略、迁移机制、并发写模型、数据膨胀、备份。共享对象按 §8.6：SQLite schema 定义跨库视角 → X02。

### [P2] [Arch] ContextVar 嵌套连接复用 + 并发子任务共享同一 aiosqlite 连接，并发退化为串行   <!-- 编号：C09-07 -->
- **定位**：`crawler-service/standalone/db.py:210-241`（`get_db` 嵌套复用）、`task_executor.py:269`（`async with task_scoped_db()`）、`digest_orchestrator.py:680-688`（`asyncio.create_task` × N）
- **现象**：`task_scoped_db()` 在 `_execute_with_semaphore` 入口建立连接并写入 ContextVar（db.py:235）。digest orchestrator 在此作用域内用 `asyncio.create_task` 创建多个 section 并发任务（orchestrator.py:680-683）。Python `create_task` 会**复制**当前 ContextVar 快照给子任务，故所有并发 section 子任务的 `get_db()` 都看到 `depth>0`，全部复用**同一个** aiosqlite.Connection（db.py:221-227）。
- **影响**：aiosqlite 底层是单线程串行执行器（一个线程跑一个连接的所有 SQL），多个并发 section 的 DB 操作经同一连接被**串行化**，并发收益被部分抵消（爬取本身是网络 IO 仍并发，但每次落库排队）。更隐蔽：若任一子任务在连接上未 commit 就让出，其他子任务可能读到中间态。**当前 repository 每个函数都自 commit（如 repository.py:81,270），降低了跨任务脏读风险，但破坏了 `task_scoped_db` "整个任务一个事务"的初衷**——嵌套复用只省了连接开销，并未实现真正的事务边界统一。
- **根因/分析**：ContextVar 复制语义 + aiosqlite 单连接单线程，决定了"复用同一连接 = 串行化 + 无独立事务"。已排除：不会数据损坏（单线程串行保证），但并发模型与设计文档（db.py:1-8 注释"减少频繁开关连接的开销，同时避免事务冲突"）存在偏差。
- **修复方向**：①明确文档：`task_scoped_db` 仅省连接，不保证事务；需要独立事务的并发分支应各自 `async with get_db()`（在外层无 scope 时）；②或每个 section 子任务显式开独立连接（改动面：中，需评估连接数）。
- **关联**：次维度 `[Bug]`（事务边界）；C04（digest 编排并发）。

### [P2] [Arch] 无 SQLite 备份/WAL checkpoint/数据清理策略，DB 文件单点 + 膨胀   <!-- 编号：C09-08 -->
- **定位**：全文缺失（grep `backup|VACUUM|wal_checkpoint|sqlite3` 仅命中 logging backupCount 与测试）
- **现象**：①启用 WAL 模式（db.py:174）但无显式 `PRAGMA wal_checkpoint` 调度，WAL 文件（`crawler.db-wal`）持续增长依赖 SQLite 自动 checkpoint（默认 1000 页触发）；②无备份机制——`data/crawler.db` 单文件，容器重启/卷丢失即全丢；③`crawl_page.raw_markdown`（全文 HTML 转 markdown，db.py:70）与 `digest_item` 无清理/归档策略，随采集量无限增长。`get_history_digest_pages` 仅截取 2000 字（repository.py:760）缓解读取压力，但写入端不清理。
- **影响**：①DB 文件单点故障——crawler 任务历史、日报结构、优化记录全部丢失（可从 PG 侧重建部分，但 crawler 独立数据无兜底）；②长期运行 DB 膨胀，影响 `list_digests_with_ai` 等全表扫描（见 C09-05）；③WAL 文件膨胀影响启动/恢复时间。
- **根因/分析**：MVP 阶段未规划运维侧。SQLite 文件级备份（`.backup` 或文件拷贝）简单但未实现。
- **修复方向**：①加定时 `wal_checkpoint(TRUNCATE)` + 文件级备份（cron + `.backup` 命令或 Python `sqlite3.Connection.backup`）；②`crawl_page`/`digest_item` 加 TTL 清理或归档到冷存储；③文档记录恢复流程（改动面：中）。
- **关联**：次维度 `[Design]`（可运维性、单点与扩展）；X01（部署架构）。

### [P3] [Arch] 增量迁移靠列探测无版本表，迁移链不可审计、不可回滚   <!-- 编号：C09-09 -->
- **定位**：`crawler-service/standalone/db.py:142-193`
- **现象**：`_MIGRATIONS` 是硬编码列表，无版本表记录"已应用哪些迁移"。每次启动重跑全量探测（db.py:185-191）。迁移失败仅 `logger.warning`（db.py:190），无失败计数/告警。
- **影响**：①无法审计某实例跑到了哪个迁移版本（排障靠猜）；②无法回滚（down migration）；③迁移 SQL 写错（如语法）被 except 吞掉，启动照常成功，运行时才因缺列报错。属已知线索 X02-09 的本模块视角细节。
- **根因/分析**：项目 PG 侧 Flyway 未集成（§9 已知），SQLite 侧同样无版本管理，双轨各自脆弱。
- **修复方向**：引入轻量 `applied_migrations` 表 + 迁移名记录（改动面：中）。与 C09-01 合并实施。
- **关联**：X02-09、B15（PG Flyway 双轨）；横向主题 schema 漂移（§2.6）。

---

## `[Deps]` 依赖升级与版本

### 本模块依赖清单（基于声明文件，未翻依赖源码）

| 依赖 | 版本 | 声明位置 | 已知风险/可升级 | 备注 |
|---|---|---|---|---|
| aiosqlite | `>=0.19.0`（未锁上界） | `requirements.txt:32` | 当前稳定线 0.20.x；0.19→0.20 无 breaking for 本项目用法 | 唯一直接依赖，本模块核心驱动 |
| Python | `3.10+` | `requirements.txt:2` | 注释要求 3.10+，`ContextVar[...]` 等语法需 3.10 | 运行时基线 |
| （间接）sqlite3 | 随 Python | — | 随 Python 版本 | WAL/busy_timeout/JSON1 依赖 |

> 排查范围：本模块仅直接依赖 `aiosqlite`（requirements.txt:32）。其余 `config`/`hashlib`/`json` 为标准库。未命中版本相关缺陷。

### [P3] [Deps] aiosqlite 版本未锁上界，依赖宽松可能引入未验证行为   <!-- 编号：C09-10 -->
- **定位**：`aiosqlite>=0.19.0`（`crawler-service/requirements.txt:32`）
- **现象**：用 `>=0.19.0` 无上界，`pip install` 会拉到最新（当前 0.20.x）。
- **影响**：`[需查证]` 0.20 相对 0.19 的 changelog 未在本次排查范围内核对（命令边界禁止深入依赖源码）。本项目用法（connect/execute/executemany/executescript/rollback/Row/text_factory）均为稳定 API，破坏性变更概率低，但无 lock 文件锁定具体版本。
- **根因/分析**：项目无 `requirements.lock`/`pip-compile` 产物。
- **修复方向**：①生成锁文件（`pip-compile`）固定 aiosqlite 具体版本；②或上界约束 `>=0.19,<0.21`（改动面：小）。
- **关联**：无。

---

## `[Design]` 功能设计合理性

> 从真实使用（单人技术博客 + 每工作日 AI 日报）出发，回答 §2.5 相关问题。

**审视结论**：

1. **场景适配（§2.5.1）**：SQLite 作为 crawler 独立存储，对"单实例 + 每日数条日报 + 低并发 API 调用"场景**适配良好**——零运维、文件即备份、WAL 支撑读写并发。单写者瓶颈在当前 max_concurrent_tasks=3（config.py:48）下不会暴露。**判断：无需调整**。
2. **可运维性（§2.5.3）**：**明显缺口**——无备份、无 checkpoint 调度、无数据清理、孤儿恢复误杀活跃任务（C09-02）、迁移失败静默（C09-09）。故障时"快速定位/恢复/回滚"三要素均薄弱：定位靠猜迁移版本、恢复靠手工文件拷贝（无工具）、回滚不支持。**判断：需补运维工具链**。
3. **单点与扩展（§2.5.7）**：SQLite 单文件是 crawler 的单点。MVP 假设（≤2 内部服务）成立，但若未来 crawler 横向扩展到多实例，SQLite 文件级锁会成为硬阻塞，届时需迁出（如 PG/对象存储）。**判断：当前合理，记为未来迁移触发点**。

### [P4] [Design] SQLite 文件单点 + 无运维工具链，建议补备份/checkpoint/清理   <!-- 编号：C09-11 -->
- **定位**：`crawler-service/standalone/db.py`（无 backup/checkpoint 代码）+ 运维文档缺失
- **现象**：如 C09-08 所述，无备份、无 checkpoint 调度、无 TTL 清理。
- **影响**：长期运行的数据安全与体量控制缺位，属"该有而没有"的运维断层。
- **建议方向**：补定时 checkpoint + 文件备份 + `crawl_page`/`digest_item` TTL 清理，并在 `deploy/README.md` 记录恢复流程（改动面：中）。
- **关联**：C09-08；X01。

---

## 模块小结

### 严重度统计

| 级别 | 数量 | 条目编号 |
|---|---|---|
| P0 | 0 | — |
| P1 | 0 | — |
| P2 | 3 | C09-01、C09-02、C09-07、C09-08 |
| P3 | 5 | C09-03、C09-04、C09-05、C09-06、C09-09、C09-10 |
| P4 | 1 | C09-11 |

> 修正：P2 实际 4 条（C09-01/02/07/08），P3 实际 5 条（C09-03/04/05/06/09/10 共 6 条），P4 1 条（C09-11）。统计见下表更正。

| 级别 | 数量 | 条目编号 |
|---|---|---|
| P0 | 0 | — |
| P1 | 0 | — |
| P2 | 4 | C09-01、C09-02、C09-07、C09-08 |
| P3 | 6 | C09-03、C09-04、C09-05、C09-06、C09-09、C09-10 |
| P4 | 1 | C09-11 |

### Top 风险（本模块最该先看的 ≤3 条）

1. **C09-08 无备份/checkpoint/清理** —— SQLite 单文件是 crawler 数据单点，长期运行数据膨胀 + 无恢复手段，运维断层最严重。
2. **C09-07 并发子任务共享单连接 + 每函数自 commit 破坏事务边界** —— `task_scoped_db` 的"一个任务一个事务"设计意图未实现，并发退化为串行且事务语义混乱。
3. **C09-02 孤儿恢复误杀活跃任务** —— 正常重启会把运行中任务判失败，影响用户体感与重试成本。

### 修复优先级建议

- **立即**（P0/P1）：无。
- **计划**（P2）：
  - C09-02 孤儿恢复加时间窗口（改动面小，收益直接）。
  - C09-08 补备份 + checkpoint + 文档（改动面中，运维刚需）。
  - C09-07 明确 `task_scoped_db` 事务语义或重设并发连接策略（改动面中）。
  - C09-01 + C09-09 迁移机制引入版本表（改动面中，可与 X02/B15 统一规划）。
- **择机**（P3/P4）：
  - C09-03 时间戳双标准（文档化或统一，小）。
  - C09-04 rollback 守卫简化（小）。
  - C09-05 分页下推或冗余列（中，待数据量增长）。
  - C09-06 callback_headers 敏感头处理（中，与 B09/C02 协同）。
  - C09-10 aiosqlite 锁版本（小）。

### 排查盲区 / 待复核

- **C09-01 并发启动迁移竞争**：多实例/多进程同时 init_db 时 ALTER TABLE 的实际行为 `[需查证]`——需结合 C10 调度器启动时序与部署拓扑（X01）确认 crawler 是否存在多实例。
- **C09-03 时间戳偏差实际影响**：当前无代码同时依赖 `created_at`（UTC）与 `digest_date`（本地）做日期级对账，故未触发功能性 bug，但 `[需查证]` 是否有外部对账脚本/报表依赖。
- **C09-10 aiosqlite 0.19→0.20 changelog**：命令边界禁止深入依赖源码，0.20 相对 0.19 的破坏性变更 `[需查证]`。
- **aiosqlite 子任务 ContextVar 复制的确切语义**（C09-07）：基于 Python 文档语义推断，未运行时验证；`[需查证]` 是否存在子任务意外重置 `_db_connection`（set 到 None）污染父作用域的场景——当前代码子任务只读 `_db_connection.get()` 且走嵌套分支不 set，理论安全，但极端情况下若子任务异常退出未走 finally 可能有风险。
