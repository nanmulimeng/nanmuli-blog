# X02 数据库 schema 完整性（跨子系统）排查报告

> **模块编号**：X02
> **排查范围**：PG 完整 schema 工程质量（索引/外键/种子/PG 特性）、crawler SQLite 表结构、双库字段一致性（指纹/来源/配置三处跨库同步对齐）、跨子系统 schema 风险
> **基线 commit**：`6ae930098405f4d0553d96a852f3345d0f39682e`
> **工作区状态**：脏。涉及本模块的未提交改动：无直接 schema 文件改动；当前脏文件（`ConfigRepositoryImpl.java`、`WebCollectPageMapper.java`、`crawler-service/*.py`、`deploy/README.md`、`release-gate.ps1` 等）不影响本模块结论。
> **排查日期**：2026-06-23
> **排查人**：X02 audit agent
> **状态**：草稿

---

## 模块概览

**职责**：从跨子系统视角审视数据库 schema 的完整性——PG schema 的工程质量（PG 特性使用、索引、外键、种子数据安全）、crawler SQLite 的表结构、以及**双库（PG + SQLite）在指纹/来源/配置三处跨库同步点的字段对齐**。本模块是"双库一致性"主模块。

**关键文件**：
- `deploy/db/init-scripts/schema.sql:1-1171` —— 完整 PG schema（部署用，逐表读）
- `backend/src/main/resources/db/init.sql:1-1132` —— 完整 PG schema（后端资源目录，三轨之一）
- `backend/src/main/resources/data.sql:1-20` —— Spring Boot `sql.init` 种子（三轨之一）
- `backend/src/main/resources/db/migration/V1_*.sql` —— Flyway 迁移档案（未集成）
- `crawler-service/standalone/db.py:24-162` —— SQLite DDL + 增量迁移
- `crawler-service/standalone/repository.py:1-812` —— SQLite 读写
- `crawler-service/crawler/digest.py:15-119` —— 指纹跨库同步（crawler→PG）
- `crawler-service/crawler/quality.py:27-179` —— 来源可信度跨库同步（PG→crawler 缓存）
- `backend/src/main/java/com/nanmuli/blog/interfaces/rest/InternalCallbackController.java:1-287` —— 跨库同步端点
- `backend/src/main/java/com/nanmuli/blog/domain/webcollector/DigestFingerprint.java` / `SourceAuthority.java` —— 跨库实体
- `backend/src/main/java/com/nanmuli/blog/infrastructure/persistence/webcollector/DigestFingerprintRepositoryImpl.java` —— 指纹批量保存

**对外接口 / 依赖**：
- 对外：跨库同步端点 `/api/internal/collector/digest/fingerprints`（GET/POST）、`/source-authority`、`/source-authority/all`、`/config`
- 依赖：PostgreSQL 15+（pgvector + zhparser + pg_trgm）、SQLite（WAL）、httpx（跨库 HTTP）

**已读文件清单**：
- `deploy/db/init-scripts/schema.sql` —— 通读（1171 行）
- `backend/src/main/resources/db/init.sql` —— 片段（article_vector / digest_fingerprint / source_authority / web_collect_* 段 + 索引清单 grep）
- `backend/src/main/resources/data.sql` —— 通读（20 行）
- `backend/src/main/resources/db/migration/V1_8/V1_17/V1_18/V1_19*.sql` —— 通读
- `crawler-service/standalone/db.py` —— 通读（254 行）
- `crawler-service/standalone/repository.py` —— 通读（812 行）
- `crawler-service/crawler/digest.py` —— 通读（183 行）
- `crawler-service/crawler/quality.py` —— 片段（SourceAuthority 类 1-179 + ContentQuality.score 242-360）
- `crawler-service/crawler/digest_orchestrator.py:410-449` —— 片段（Phase 3 指纹持久化）
- `backend/.../InternalCallbackController.java` —— 通读（287 行）
- `backend/.../DigestFingerprint.java` / `SourceAuthority.java` / `BaseAggregateRoot.java` / `ArticleEventHandler.java` / `DigestFingerprintRepositoryImpl.java` —— 通读
- `backend/src/main/resources/application.yml` / `application-dev.yml` —— 通读/grep
- `scripts/release/check-deploy-env.ps1` —— 通读（57 行）
- 仅 grep：`article_vector`/`ArticleVector` 引用、`ivfflat`/`lists`、`chinese_zh`/`to_tsvector`、admin/role 比较点

**主模块归属**：
- **本模块深查**（§8.6）：SQLite vs PostgreSQL 跨库一致性。
- **只引用不展开**：PG 三轨 schema 漂移细节 → B15（本模块仅在跨库视角补充）；AI 空壳链路 NoOpAiService → B13（本模块只记 article_vector 表的落地缺口视角）；鉴权 → B06；配置一致性 → X06。

---

## 双库字段映射表（核心交付物）

| 概念 | PG 表/字段 | SQLite 表/字段 | 一致性结论 |
|---|---|---|---|
| 采集任务 ID | `web_collect_task.id BIGINT`（snowflake） | `crawl_task.id INTEGER AUTOINCREMENT` | **不一致**：PG 用 snowflake Long，SQLite 用自增 int；两库 id 独立生成，靠 `python_task_id` 反向关联。见 X02-04 |
| 任务状态 | `web_collect_task.status SMALLINT`（0-4） | `crawl_task.status INTEGER`（0-4） | 一致（枚举值对齐：0 待处理/1 爬取中/2 整理中/3 已完成/4 失败） |
| URL 哈希 | `web_collect_page.url_hash VARCHAR(64)` | `crawl_page.url_hash TEXT` | 一致（均 SHA-256 hex，64 字符） |
| 内容哈希 | `web_collect_page.content_hash VARCHAR(64)` | **SQLite 无此列** | **不一致**：PG 有内容去重 hash，SQLite crawl_page 无对应列，内容去重只在 PG 侧落地 |
| AI 搜索元数据 | `web_collect_task.ai_search_metadata TEXT` | `crawl_task.ai_search_metadata TEXT` | 一致（JSON 字符串，增量迁移补齐） |
| 日报日期 | `web_collect_task` 无独立列 | `crawl_task.digest_date TEXT` | **不一致**：SQLite 有 `digest_date`（含增量迁移 idx_digest_date），PG `web_collect_task` 无对应列，日报日期只在 SQLite 侧管理 |
| 日报高亮 | `web_collect_task` 无对应列 | `crawl_task.digest_highlight TEXT` | **不一致**：仅 SQLite 侧存储 |
| 日报指纹 task_id | `digest_fingerprint.task_id BIGINT`（关联 PG web_collect_task.id） | 不存于 SQLite | **语义错位**：crawler POST 时填的是 SQLite `crawl_task.id`（int），但 PG `digest_fingerprint.task_id` 语义上应关联 PG `web_collect_task.id`（snowflake）。见 X02-04 |
| 指纹 simhash | `digest_fingerprint.simhash BIGINT` | （crawler 内存计算，不入 SQLite） | 一致（crawler 传 int，PG 存 BIGINT） |
| 来源可信度 | `source_authority` 表（28 条种子） | 不存于 SQLite（crawler 内存缓存 `_api_cache`） | 双源：DB 种子 + crawler 硬编码兜底。**两源域名集合不一致**，见 X02-06 |
| 来源可信度 level | `source_authority.level VARCHAR(20)`（official/high/medium） | crawler 硬编码返回 `official/high/medium/spam` | **枚举不一致**：crawler 多一个 `spam` 级别（5 分），PG 种子无 spam 记录 |
| 时间戳类型 | `TIMESTAMP DEFAULT CURRENT_TIMESTAMP`（PG，带时区） | `TEXT DEFAULT (datetime('now'))`（SQLite，UTC 无时区字面量） | **不一致**：跨库时间戳语义/时区不同。见 X02-08 |
| 软删除 | `is_deleted BOOLEAN`（多数表） | **SQLite 全部表无 is_deleted** | **不一致**：SQLite 物理删除，PG 逻辑删除；跨库同步时 PG 的"未删除"过滤不会作用到 SQLite |
| 回调 URL/headers | `web_collect_task` 无对应列 | `crawl_task.callback_url / callback_headers TEXT` | 仅 SQLite 侧（任务发起时存） |

---

## `[Bug]` 代码正确性与潜在缺陷

> 排查范围：跨库同步链路（指纹保存/查询、来源可信度同步、配置同步）、ID 类型对齐、时间戳/时区、一致性窗口。

### [P2] [Bug] 指纹跨库同步失败时静默丢失，跨日去重回退到不完整本地历史  <!-- 编号：X02-01 -->
- **定位**：`crawler-service/crawler/digest.py:102-118`（save_digest_fingerprints）；`crawler-service/crawler/digest_orchestrator.py:417-422`
- **现象**：日报生成完成后，Phase 3 调 `save_digest_fingerprints` 将指纹 POST 到 PG。该调用被 `try/except` 包裹，失败时仅 `logger.warning("[DigestFingerprints] Save failed: %s", e)`（digest.py:118）或 `logger.warning("[Orchestrator] Fingerprint save failed (non-critical)")`（orchestrator.py:422）。主流程不中断、无重试、无持久化失败记录。
- **影响**：当 backend 短暂不可用或网络抖动时，当日所有日报指纹丢失持久化。次日 `build_digest_history_engine`（digest.py:15-65）从 PG 拉不到指纹，回退到本地 SQLite 历史（`get_history_digest_pages`，仅取最近 3 期 raw_markdown 截断 2000 字做 SimHash）。回退路径覆盖率低且依赖本地库存活，导致跨日重复 URL 无法去重，日报质量下降但无任何告警。
- **根因/分析**：设计上把指纹持久化定为 "non-critical"（日报本身已成功），但跨日去重是日报质量的核心闭环之一，失败静默化使运维无法感知数据缺口。已排除误判：`build_digest_history_engine` 确实有 try/except 回退（digest.py:49-50），但回退数据源与 PG 指纹集合不同构（本地是 page 级 markdown，PG 是 url_hash+simhash 级）。
- **修复方向**：①失败时在 SQLite 侧落一条 `pending_fingerprint_sync` 待重试记录，由调度器补传；②至少 metrics 计数 + 告警阈值（连续 N 次失败通知）。改动面：中（跨服务、需补表/补传机制）。
- **关联**：横向主题"跨服务契约一致性"；次维度 [Arch]；C04/C07（日报闭环）。

### [P2] [Bug] 跨库时间戳类型与时区语义不一致，跨库按时间过滤存在窗口误差  <!-- 编号：X02-02 -->
- **定位**：`crawler-service/standalone/db.py:58-59`（SQLite `created_at TEXT DEFAULT (datetime('now'))`，UTC 无时区）；`deploy/db/init-scripts/schema.sql:114/688`（PG `TIMESTAMP NOT NULL DEFAULT NOW()`）；`backend/src/main/resources/application.yml:17`（Jackson `time-zone: Asia/Shanghai`）
- **现象**：SQLite 的 `datetime('now')` 返回 UTC 无时区字面量（如 `2026-06-23 02:00:00`）；PG 的 `TIMESTAMP`（无 tz）存的是服务器本地时间（容器默认 UTC 或 Asia/Shanghai，取决于部署）；后端 Jackson 序列化统一按 Asia/Shanghai。
- **影响**：跨库同步端点 `/digest/fingerprints?days=3`（InternalCallbackController.java:201）用 `LocalDate.now().minusDays(days)` 计算 `since`，`LocalDate.now()` 取 JVM 默认时区。crawler 侧 SQLite 的日报任务按 UTC `created_at` 排序。当后端 JVM 时区与 crawler 进程时区不一致（如容器一个 UTC 一个 Asia/Shanghai）时，"最近 3 天"的边界会出现几小时偏差，跨日去重窗口在边界日期漏拉或重拉。
- **根因/分析**：双库对"时间"的表示未统一。SQLite TEXT 时间默认 UTC、PG TIMESTAMP 无时区、应用层强制 Asia/Shanghai 三者叠加，边界场景（午夜前后）易错。已排除：PG 用 `TIMESTAMP`（without tz）而非 `TIMESTAMPTZ`，本身就不存时区。
- **修复方向**：①统一两端都用 UTC 存储+offset 计算；②或跨库同步端点显式传时区参数。改动面：中（涉及双端时间处理 + 历史 SQL 查询）。
- **关联**：横向主题"跨服务契约一致性"；次维度 [Bug]。

### [P2] [Bug] web_collect_page CASCADE 删除策略与软删除冲突，误删时无法恢复  <!-- 编号：X02-03 -->
- **定位**：`deploy/db/init-scripts/schema.sql:880-881`（`fk_page_task ... ON DELETE CASCADE`）；`web_collect_page` 有 `is_deleted BOOLEAN`（schema.sql:723）
- **现象**：`web_collect_page` 表同时有逻辑删除列 `is_deleted` 和物理级联删除外键 `ON DELETE CASCADE`。当父表 `web_collect_task` 行被物理删除时，所有 page 物理级联删除，绕过软删除语义。
- **影响**：若任何运维操作或 bug 触发 `web_collect_task` 物理删除（而非逻辑删除），关联 page 永久丢失，无法追溯采集历史。MyBatis Plus 全局逻辑删除（application.yml:49-52）通常保证 UPDATE 而非 DELETE，但手写 SQL、DBA 操作、Flyway 迁移都可能绕过。
- **根因/分析**：软删除 + 物理级联混用是反模式。SQLite 侧（db.py:67）也是 `ON DELETE CASCADE`，但 SQLite 无软删除列，行为一致；PG 侧混用产生语义矛盾。对比 `article_draft`/`ai_generation`/`article_vector` 也用 CASCADE，但这些的父表 `article` 同样逻辑删除，问题相同但不那么尖锐（article 误删概率低）。
- **修复方向**：①page 表去掉 `ON DELETE CASCADE`，改为 `ON DELETE RESTRICT` 或依赖应用层级联软删除；②或保留 CASCADE 但移除 page 的 `is_deleted`（明确物理删除语义）。改动面：中（schema 变更 + 迁移）。
- **关联**：B15（schema 定义）；次维度 [Arch]。

### [P2] [Bug] digest_fingerprint.task_id 跨库语义错位（SQLite int vs PG snowflake）  <!-- 编号：X02-04 -->
- **定位**：`crawler-service/crawler/digest.py:91`（`"taskId": task_id`，task_id 是 SQLite crawl_task.id INTEGER）；`backend/.../InternalCallbackController.java:220`（`fp.setTaskId(... n.longValue())` 存入 PG `digest_fingerprint.task_id BIGINT`）；`backend/.../domain/webcollector/DigestFingerprint.java:18`
- **现象**：crawler 完成日报后，把 SQLite 的 `crawl_task.id`（自增 int）作为 `taskId` POST 到 PG，存入 `digest_fingerprint.task_id`。但 PG 侧 `web_collect_task.id` 是 snowflake Long（BaseAggregateRoot.java:17 `IdType.ASSIGN_ID`），且 `web_collect_task` 通过 `python_task_id INTEGER`（schema.sql:673）反向关联 SQLite。PG 侧从未把 `digest_fingerprint.task_id` 关联回 `web_collect_task.id`。
- **影响**：`digest_fingerprint.task_id` 实际存的是 SQLite 任务 id，无法 JOIN 到 PG `web_collect_task`（id 体系不同）。该字段沦为孤儿引用，任何"某篇日报包含哪些指纹"的跨库追溯查询都失效。目前 `findByDigestDateAfter`（DigestFingerprintRepositoryImpl.java:40）只按日期查，未 JOIN task 表，所以暂时无功能性 bug，但字段语义错误是隐患。
- **根因/分析**：跨库 id 体系未对齐。PG 任务和 SQLite 任务是两个独立 id 空间，靠 `python_task_id` 桥接，但指纹表设计时没考虑这点。
- **修复方向**：①PG `digest_fingerprint` 增 `python_task_id INTEGER` 列与 `web_collect_task.python_task_id` 对齐；②或 task_id 字段改名为 `source_task_id` + 加 `source_db` 标识。改动面：中（schema + 实体 + 同步代码）。
- **关联**：横向主题"跨服务契约一致性"；次维度 [Arch]；B09。

---

## `[Security]` 安全漏洞

> 排查范围：种子弱口令、source_authority 种子合理性、跨库同步鉴权（引用 B09）、ID 精度。逐项覆盖计划 §2.2 技术栈重点中与本模块相关项（跨服务双向 key 归 B09，本模块只记 schema 视角）。

### [P1] [Security] 种子 admin 弱口令 admin123 明文注释 + check-deploy-env 未覆盖  <!-- 编号：X02-05 -->
- **定位**：`backend/src/main/resources/data.sql:2-6`（注释明文"密码: admin123" + BCrypt 哈希）；`deploy/db/init-scripts/schema.sql:888-890`（同哈希）；`backend/src/main/resources/db/init.sql`（同哈希，三轨一致）；`scripts/release/check-deploy-env.ps1:7-14`（RequiredKeys 不含任何口令检查项）
- **现象**：三轨 schema 种子均插入 id=1 的 admin 用户，BCrypt 哈希对应明文 `admin123`，且 data.sql 第 2 行注释直接写"密码: admin123"。`check-deploy-env.ps1` 只校验 6 个 env key（AI_ENABLED/DIGEST_ENABLED/AI_API_KEY/CRAWLER_API_KEY/CRAWLER_CALLBACK_API_KEY/BLOG_SECURITY_ENCRYPTION_KEY），完全不检查 admin 口令是否已改。
- **影响**：若部署者忘记改 admin 口令（且 release-gate 不会拦），生产环境存在可登录的弱口令账户，配合 Sa-Token Cookie 模式即可完全接管管理端。BCrypt 哈希公开在代码库 + 明文注释，攻击者无需爆破。
- **根因/分析**：种子数据安全 + 发布门禁两个环节都缺校验。已排除：check-deploy-env 对 env 的 placeholder 检查（`your_|sk-your-`）逻辑是对的，只是没覆盖 DB 种子口令。
- **修复方向**：①check-deploy-env 增加一步：登录 admin/admin123 探测，命中则 fail；②或种子改为随机口令 + 首次登录强制改密；③至少移除 data.sql 明文注释。改动面：小（脚本 + 注释）/ 中（种子策略）。
- **关联**：B06（鉴权）；§9 已知线索"默认弱口令"；X04（发布脚本）。

### [P2] [Security] source_authority 种子含高争议域名（csdn/zhihu/reddit），且双源域名集不一致  <!-- 编号：X02-06 -->
- **定位**：`deploy/db/init-scripts/schema.sql:1133-1165`（28 条种子）；`crawler-service/crawler/quality.py:38-79`（OFFICIAL_DOMAINS + HIGH_QUALITY_COMMUNITIES + TECH_BLOGS 硬编码）
- **现象**：PG 种子给 `csdn.net`/`blog.csdn.net`/`zhihu.com`/`reddit.com`/`v2ex.com` 打 80 分（high 级），与这些域名的实际内容质量分布不符（CSDN 有大量低质 SEO 文章、reddit 子版块质量分化大）。crawler 硬编码兜底列表更全（多出 `segmentfault.com`/`draveness.me`/`cnblogs.com`/`istio.io`/`azure.microsoft.com`/`postgresql.org`/`redis.io` 等），两源域名集合不一致。
- **影响**：①质量评分被种子"虚高"——CSDN 文章因域名得 80 分，掩盖内容质量不足；②双源不一致导致同一域名在"API 缓存命中"和"硬编码兜底"两种路径下得分可能不同（如 `postgresql.org` 在 crawler 硬编码是 95 official，但 PG 种子没有，API 未命中时走硬编码 95，API 命中时……其实没命中因为种子没有，所以永远走硬编码——种子反而失效）。
- **根因/分析**：种子设计偏"广撒网"，且与 crawler 硬编码未同步维护。来源可信度本应是可运营数据，现变成两份漂移的静态列表。
- **修复方向**：①下调争议域名分数（csdn/reddit/v2ex → 60-65 medium）；②统一双源（crawler 硬编码只做兜底，权威数据进 DB + 管理端可编辑）；③补齐 crawler 硬编码多出的官方域名到 PG 种子。改动面：中（种子数据 + 同步机制）。
- **关联**：C08（质量评估）；次维度 [Design]。

---

## `[Arch]` 架构与技术债

> 排查范围：article_vector 落地缺口、ivfflat 索引工程质量、SQLite 增量迁移健壮性、双库软删除语义、三轨种子一致性。schema 三轨漂移细节引用 B15，本节只记跨库/工程质量视角。

### [P1] [Arch] article_vector 表 + pgvector 索引全建但零 Repository，向量从不写入（落地缺口）  <!-- 编号：X02-07 -->
- **定位**：`deploy/db/init-scripts/schema.sql:557-576`（article_vector 表 + ivfflat 索引）；`backend/.../application/event/ArticleEventHandler.java:62-74`（注释明确"向量存储模块尚未实现，待article_vector表和Repository开发后保存"）；全仓 grep `ArticleVector`/`INSERT INTO article_vector` 仅命中 schema 文件和该 TODO 注释，**无任何 Mapper/Repository/实体类**
- **现象**：PG 建了 `article_vector` 表（含 `content_vector vector(1536)` + `summary_vector vector(1536)`）和 ivfflat 索引，但 Java 侧无对应实体、Mapper、Repository。`ArticleEventHandler.handleArticlePublished` 调 `aiService.generateEmbedding()` 拿到向量后，注释写"暂未持久化"直接丢弃。
- **影响**：①表和索引空转，占用 schema 复杂度却零功能收益；②结合 NoOpAiService（B13），整条"发布文章→生成向量→语义推荐"链路是空壳；③ivfflat 索引在空表上创建，即使后续填充数据，索引也是基于空数据聚类，召回质量极差（pgvector 要求"数据导入后再建索引"）。
- **根因/分析**：AI 推荐功能按"骨架先行"开发，表/事件/接口都建了，唯独缺数据落地层。属已知线索 [Arch/P1] Java AI NoOp（§9）的 schema 侧佐证。
- **修复方向**：①若 MVP 不上 AI 推荐，删除 article_vector 表 + 索引 + EventHandler 向量分支，降低 schema 噪音；②若要上，补 `ArticleVectorRepository` + 实体 + 在数据导入后 REINDEX。改动面：小（删）/ 大（补全链路）。
- **关联**：B13（AI 空壳主模块）；§9 已知线索；次维度 [Design]。

### [P2] [Arch] ivfflat 向量索引无 lists 参数且在空表创建，召回质量隐患  <!-- 编号：X02-08 -->
- **定位**：`deploy/db/init-scripts/schema.sql:576`；`backend/src/main/resources/db/init.sql:532`（两轨一致）
- **现象**：`CREATE INDEX ... USING ivfflat (content_vector vector_cosine_ops)` 未指定 `WITH (lists = N)`，用 pgvector 默认 lists=100。索引在 schema 初始化时（表空）创建。
- **影响**：①pgvector 官方建议 lists = 行数/1000（<100万）或 sqrt(行数)（>=100万），且必须在数据导入后建索引才能正确聚类（项目自带文档 `docs/postgresql_pgvector_tutorial_supplemented.md:907-926` 明确此点）；②空表建索引 = 聚类中心基于零样本，后续 INSERT 的向量无法被正确分配到簇；③即使 article_vector 落地（X02-07），召回率和召回准确度都会受损。
- **根因/分析**：schema 编写时未遵循 pgvector 索引最佳实践，照搬默认参数。
- **修复方向**：数据真正导入后用 `REINDEX` + 显式 `lists`；或改用 hnsw（无需 lists，召回更稳，项目文档也推荐 hnsw）。改动面：小（单索引 DDL）。
- **关联**：X02-07；次维度 [Bug]。

### [P2] [Arch] SQLite 增量迁移无版本表，靠"列是否存在"判定，迁移链脆弱  <!-- 编号：X02-09 -->
- **定位**：`crawler-service/standalone/db.py:143-193`（`_MIGRATIONS` 列表 + `PRAGMA table_info` 逐列探测）
- **现象**：SQLite 增量迁移用一个硬编码 `_MIGRATIONS = [(name, sql), ...]` 列表，执行时 `PRAGMA table_info(crawl_task)` 拿现有列名集合，对每个迁移项检查 `col_name not in existing_columns` 决定是否执行。没有 `schema_migrations` 版本表，没有迁移顺序保证（部分项是 index 不是 column，靠 index 名不在列集合里判定，逻辑混用）。
- **影响**：①无法可靠追踪已执行迁移（如某迁移失败被 except 吞掉 db.py:190-191，下次启动不会重试也不会记录）；②"index 迁移"和"column 迁移"混在一个列表里用同一判定（index 名当然不在列集合里，所以每次启动都会尝试 CREATE INDEX IF NOT EXISTS，靠 IF NOT EXISTS 幂等——能跑但语义混乱）；③新增迁移要手动维护列表顺序，易遗漏。
- **根因/分析**：早期 SQLite 单文件、无 Flyway 等工具，手搓迁移。对比 PG 侧虽有 Flyway 档案但未集成（B15），双库迁移管理都偏弱。
- **修复方向**：①引入轻量 SQLite 迁移工具（如 `yoyo-migrations` 或自建 `schema_version` 表）；②至少把 column 迁移和 index 迁移分离，index 用纯 `IF NOT EXISTS` 幂等即可，column 用版本号。改动面：中。
- **关联**：C09（SQLite 数据层主模块）；B15（PG 迁移）；次维度 [Arch]。

### [P3] [Arch] SQLite 全部表无 is_deleted 软删除，跨库同步时 PG 软删除过滤不传导  <!-- 编号：X02-10 -->
- **定位**：`crawler-service/standalone/db.py:25-139`（所有表 DDL 无 is_deleted 列）；`deploy/db/init-scripts/schema.sql`（多数表有 is_deleted）
- **现象**：SQLite 的 `crawl_task`/`crawl_page`/`digest_section`/`digest_item`/`optimization_record` 均无 `is_deleted`，删除走物理 DELETE（repository.py:339-347 `delete_task`）。PG 侧同概念表多数有 `is_deleted` + MyBatis Plus 全局逻辑删除。
- **影响**：跨库同步语义不对称。例：PG 侧逻辑删除一条 `web_collect_task`，crawler 侧 SQLite 的 `crawl_task` 仍存活并被查询；反向，crawler 物理删 SQLite 任务，PG 侧无感知。当前因跨库同步是单向（指纹 crawler→PG、来源 PG→crawler）且不依赖 task 表 JOIN，暂无功能性 bug，但语义不一致是技术债。
- **根因/分析**：SQLite 作为 crawler 独立运行时存储，设计上就是物理删除（WAL + 简单），与 PG 的 DDD 软删除范式不同。两套范式并存于同一系统。
- **修复方向**：明确"SQLite 是 crawler 私有运行态，PG 是博客权威态"，文档化两库删除语义边界；或同步引入软删除（成本高、收益低）。改动面：小（文档）/ 大（schema）。
- **关联**：C09；次维度 [Design]。

### [P3] [Arch] 三轨种子 admin role 大小写不一致（data.sql 'admin' vs schema.sql 'ADMIN'）  <!-- 编号：X02-11 -->
- **定位**：`backend/src/main/resources/data.sql:6`（`role` 值 `'admin'` 小写）；`deploy/db/init-scripts/schema.sql:889` + `init.sql`（`'ADMIN'` 大写）
- **现象**：data.sql 插入 admin 用户时 role = `'admin'`（小写），schema.sql/init.sql 种子 role = `'ADMIN'`（大写）。`sys_user.role` 是 `VARCHAR(20)`，PG 默认大小写敏感。
- **影响**：取决于哪个文件先执行 / 哪条 INSERT 生效（data.sql 有 `WHERE NOT EXISTS` 保护，schema.sql 用 `ON CONFLICT DO NOTHING`），生产 admin 的 role 可能是 `'admin'` 或 `'ADMIN'`。若 Java 侧鉴权按特定大小写比较（如 `equals("ADMIN")`），小写 `admin` 可能被误判为非管理员，导致 admin 登录后无管理权限；反之若按小写比较则大写失效。grep 未在 Java 代码找到直接的 `"ADMIN"` 字面量比较（可能在 SQL 或 SaToken 注解里），**需查证实际鉴权比较点**。
- **根因/分析**：三轨 schema 漂移的典型表现（B15 主模块），本条记 X02 视角：种子数据三轨不一致 + role 字段无 CHECK 约束 + 无应用层枚举校验。
- **修复方向**：①统一三轨 role 值（建议大写 'ADMIN' 配合 Java 枚举）；②加 `CHECK (role IN ('ADMIN','USER'))` 约束；③应用层用枚举而非字符串。改动面：小（三文件 + 约束）。
- **关联**：B15（三轨漂移主模块）；横向主题"schema 漂移"；B06（鉴权）；`[需查证]` 鉴权比较点。

---

## `[Deps]` 依赖升级与版本

### 本模块依赖清单（基于声明文件，未翻依赖源码）

| 依赖 | 版本 | 声明位置 | 已知风险/可升级 | 备注 |
|---|---|---|---|---|
| PostgreSQL | 15+ | `CLAUDE.md` / `deploy/docker-compose.yml` | 可升至 16/17（性能 + 逻辑复制改进） | 本模块关注 PG 特性使用，非版本升级 |
| pgvector | 0.1.4（Java 绑定） | `backend/pom.xml:23,54-56` | 可升至 0.3.x（hnsw 原生支持、性能） | Java 绑定版本，非 PG 扩展本体 |
| zhparser | 未声明版本 | `deploy/db/init-scripts/schema.sql:10` | SCWS 维护停滞，中文 FTS 长期方案待评估 | 依赖 PG 镜像预装 |
| pg_trgm | 未声明版本 | `schema.sql:13` | 稳定 | init.sql 声明了 trgm 索引，schema.sql 没有（见 X02-12） |
| aiosqlite | 未在 requirements 声明版本 | `crawler-service/standalone/db.py:12` | [需查证] requirements.txt 实际版本 | SQLite 异步驱动 |

> 排查范围：仅本模块涉及的 PG 扩展 + SQLite 驱动声明。依赖版本升级主排查归各模块 [Deps] 节 + X（全局）。未命中额外风险。

### [P3] [Deps] pgvector Java 绑定 0.1.4 偏旧，且 article_vector 落地前无实际使用  <!-- 编号：X02-12 -->
- **定位**：`backend/pom.xml:23`（`<pgvector.version>0.1.4</pgvector.version>`）
- **现象**：pgvector Java 绑定锁 0.1.4，较旧（社区已有 0.3.x）。
- **影响**：当前 article_vector 零使用（X02-07），版本旧无功能影响；一旦落地 AI 推荐，旧绑定可能缺 hnsw 支持、性能优化。
- **根因/分析**：随骨架引入后未随 pgvector 扩展本体同步升级。
- **修复方向**：article_vector 落地时一并升至 0.3.x；在此之前可不动。改动面：小。
- **关联**：X02-07；B13。

---

## `[Design]` 功能设计合理性

> 从真实使用出发审视双库设计。回答计划 §2.5 中相关问题。

**审视结论**：

1. **场景适配（单人技术博客 + 每工作日 AI 日报）**：双库架构（PG 博客权威 + SQLite crawler 运行态）对"≤2 内部服务"的 MVP 假设是合理的——PG 保证博客数据一致性和关系完整性，SQLite 给 crawler 轻量异步存储。但跨库同步靠 HTTP 端点 + 内存缓存（SourceAuthority `_api_cache`）+ 静默重试，在单人运维场景下"故障可感知性"不足（X02-01 指纹静默丢失、SourceAuthority preload 失败只 debug 日志 quality.py:178）。**判断：架构合理，但可观测性需补强。**

2. **闭环完整性（日报质量闭环）**：指纹跨日去重闭环存在"持久化失败静默化"缺口（X02-01），日报质量评估闭环存在"超时跳过 KB 写入"（C04/C07 已知线索）。从 schema 视角看，`digest_fingerprint.task_id` 语义错位（X02-04）使得"某篇日报含哪些指纹"无法跨库追溯，闭环的可审计性受损。**判断：闭环跑得通但可审计性弱，运维难定位"为何今天日报重复了昨天 URL"。**

3. **可运维性 / 缺失功能**：source_authority 是质量评估的关键数据，但双源（PG 种子 + crawler 硬编码）漂移（X02-06），且无管理端编辑入口（grep 未发现 admin Controller 管理 source_authority）。单人博主想调整某域名评分只能改 SQL 或硬编码，违反"配置 DB 化、可运营"原则。**判断：source_authority 应是可运营数据，现被设计成静态种子，缺运营入口。**

### [P4] [Design] source_authority 无管理端入口，质量评分不可运营  <!-- 编号：X02-13 -->
- **定位**：`deploy/db/init-scripts/schema.sql:1122-1170`（表 + 种子）；无对应 admin Controller（grep `source_authority` 仅命中 InternalCallback 只读端点 + Mapper）
- **现象**：source_authority 表设计为"动态质量评估"（COMMENT 注释），但仅有 crawler 读取端点（`/source-authority/all` 只读），无 admin CRUD 接口。调整评分需直连 DB 或改 crawler 硬编码。
- **影响**：单人博主发现某域名（如新出的优质技术博客）评分偏低，无法通过管理端调整，要 SQL 操作或改代码重启，违反 DB 化配置初衷。
- **建议方向**：补 admin CRUD（与 web_collect_source 管理端同级），crawler 通过 preload 缓存自动生效。改动面：中。
- **关联**：X02-06；F04/F05（管理页）；次维度 [Arch]。

### [P4] [Design] 双库概念映射应文档化，当前仅靠代码隐式约定  <!-- 编号：X02-14 -->
- **定位**：本报告"双库字段映射表"是首次系统梳理；项目文档（`docs/web-collector-module-design.md` 等）未含此映射
- **现象**：双库字段对应关系（task_id 双 id 体系、digest_date 仅 SQLite、content_hash 仅 PG、软删除不对称）散落在代码里，无文档。
- **影响**：新 agent 或维护者接手时，跨库 bug 排查要逆向代码理解两库关系，效率低、易误判。
- **建议方向**：把本报告的"双库字段映射表"沉淀到 `docs/web-collector-module-design.md` 或 `docs/digest-system.md`。改动面：小（文档）。
- **关联**：横向主题"跨服务契约一致性"；X05（文档一致性）。

---

## 模块小结

### 严重度统计

| 级别 | 数量 | 条目编号 |
|---|---|---|
| P0 | 0 | — |
| P1 | 2 | X02-05, X02-07 |
| P2 | 6 | X02-01, X02-02, X02-03, X02-04, X02-06, X02-08 |
| P3 | 4 | X02-09, X02-10, X02-11, X02-12 |
| P4 | 2 | X02-13, X02-14 |

### Top 风险（本模块最该先看的 3 条）

1. **X02-05 种子 admin 弱口令 + check-deploy-env 未覆盖** —— 上线前可利用，release-gate 拦不住，是生产事故入口。
2. **X02-07 article_vector 全建零用 + ivfflat 空表索引** —— schema 复杂度噪音 + AI 链路空壳的 schema 佐证，要么删要么补全，不能悬空。
3. **X02-01 指纹跨库同步静默丢失** —— 日报质量闭环的可感知性缺口，单人运维场景下最难发现。

### 修复优先级建议

- **立即（P0/P1）**：
  - X02-05：check-deploy-env 增 admin 口令探测；移除 data.sql 明文注释。
  - X02-07：决策 article_vector 去留（删或补全 Repository），消除空壳。
- **计划（P2）**：
  - X02-01：指纹同步失败补重试/告警机制。
  - X02-04：digest_fingerprint.task_id 语义对齐（加 python_task_id）。
  - X02-03：web_collect_page CASCADE 与软删除二选一。
  - X02-02：双库时间戳/时区统一。
  - X02-06：source_authority 种子下调争议域名 + 双源同步。
  - X02-08：ivfflat 索引补 lists 或改 hnsw（依赖 X02-07 决策）。
- **择机（P3/P4）**：
  - X02-09：SQLite 迁移引入版本表。
  - X02-11：三轨 role 大小写统一 + CHECK 约束。
  - X02-13/X02-14：source_authority 管理 + 双库映射文档化。
  - X02-10/X02-12：软删除语义文档化 / pgvector 绑定升级（低优先）。

### 排查盲区 / 待复核

- **[需查证] X02-11**：Java 侧 admin role 鉴权比较点（`"ADMIN"` 大小写敏感比较的具体位置），需在 B06 鉴权模块或 SQL 层确认。若按大写比较，data.sql 小写 `'admin'` 种子会导致 admin 无管理权限（功能性 bug，严重度可能升至 P1）。
- **[需查证] X02-12**：aiosqlite 在 `crawler-service/requirements.txt` 的实际版本未读（本排查未打开 requirements.txt），升级风险未评估。
- **[需查证]**：`web_collect_task` 是否真的无 `digest_date` 列（init.sql/schema.sql grep 未发现，但可能有 migration 补列未读全，需 B15 确认）。
- **未覆盖**：crawler `/config` 端点拉取的配置 key 与 PG `sys_config` 的字段对齐（crawler.ai.model 默认值 `deepseek-v4-pro` vs `qwen-plus` 不一致，归 X06 配置一致性主模块，本模块不展开）。
