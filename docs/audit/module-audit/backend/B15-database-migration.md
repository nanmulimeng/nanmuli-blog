# B15 数据库与迁移 排查报告

> **模块编号**：B15
> **排查范围**：PostgreSQL schema 定义的唯一主模块——Flyway 集成度、schema 三轨（migration / init.sql / deploy schema.sql / data.sql）漂移、缺表缺列、索引、唯一约束、外键、config seed 漂移、SQL 初始化机制
> **基线 commit**：`6ae930098405f4d0553d96a852f3345d0f39682e`
> **工作区状态**：脏。涉及本模块的未提交改动：无（脏文件为 `ConfigRepositoryImpl.java`、`WebCollectPageMapper.java`、crawler 测试与 docs，均不触碰 schema 定义）。本模块基线即 HEAD。
> **排查日期**：2026-06-23
> **排查人**：B15 排查 agent
> **状态**：草稿

---

## 模块概览

**职责**：定义全部 PG 表结构、索引、约束、触发器、外键，并管理首次建库（schema.sql）+ 后续结构演进（migration）+ 运行时数据补种（data.sql）。本质问题：**声称用 Flyway，实际未集成**；schema 散落在三个未对齐的源里，手工同步，长期漂移。

**关键文件**：
- `backend/pom.xml` —— 声明依赖（**无 Flyway**），决定集成与否的根本证据
- `backend/src/main/resources/application.yml:12-15` —— `spring.sql.init.mode: always` + `data-locations: classpath:data.sql`（dev 默认执行 data.sql）
- `backend/src/main/resources/application-prod.yml:25-27` —— 覆盖为 `mode: never`（prod 不执行 data.sql）
- `backend/src/main/resources/data.sql` —— 唯一被 `spring.sql.init` 真正执行的 SQL（dev 环境）
- `backend/src/main/resources/db/init.sql` —— "Flyway 版本 V1.0.0"基线声明（但 Flyway 未集成，此文件不被任何机制加载）
- `backend/src/main/resources/db/migration/V1_1__*.sql` ~ `V1_23__*.sql` —— 23 个 migration 脚本（**不被任何机制加载**）
- `deploy/db/init-scripts/schema.sql` —— Docker Postgres 首次建卷时执行（`docker-compose.yml:19` 挂载）
- `deploy/docker-compose.yml:17-19` —— `./db/init-scripts:/docker-entrypoint-initdb.d`
- `deploy/db/Dockerfile` —— 自定义 PG 镜像（pgvector + zhparser），与 schema 无关
- `backend/src/main/java/com/nanmuli/blog/infrastructure/config/initializer/SystemConfigInitializer.java` —— ApplicationRunner 运行时补种 config（兜底）
- `backend/src/main/java/com/nanmuli/blog/interfaces/handler/GlobalExceptionHandler.java:112` —— 靠字符串 `article_slug_key` 捕获约束冲突（依赖 PG 默认约束名）

**对外接口 / 依赖**：
- 对外：无（基础设施层）
- 依赖：被全部业务模块的 Mapper / Repository 间接依赖；crawler 配置 seed 经 `SystemConfigInitializer` + sys_config 表回读

**已读文件清单**：
- `backend/pom.xml` —— 通读（确认无 flyway-core / flyway-mysql 依赖）
- `backend/src/main/resources/application.yml` —— 通读
- `backend/src/main/resources/application-dev.yml` —— 通读
- `backend/src/main/resources/application-prod.yml` —— 通读
- `backend/src/main/resources/data.sql` —— 通读（21 行）
- `backend/src/main/resources/db/init.sql` —— 通读（1133 行）
- `deploy/db/init-scripts/schema.sql` —— 通读（1171 行）
- `backend/src/main/resources/db/migration/V1_1` ~ `V1_23` —— 全部 23 个通读
- `backend/src/main/java/com/nanmuli/blog/infrastructure/config/initializer/SystemConfigInitializer.java` —— 通读
- `deploy/docker-compose.yml` —— 通读
- `deploy/db/Dockerfile` —— 通读
- `deploy/db/README.md` —— 通读（含误导性 Flyway 承诺）

**主模块归属**：**B15 是全部 PG schema 定义的主模块**。X02 只做跨库（SQLite vs PG）视角引用本报告；B08/B13 涉及具体表时引用本报告条目编号。

---

## `[Bug]` 代码正确性与潜在缺陷

> 排查范围：data.sql 幂等性、约束名一致性、GlobalExceptionHandler 对约束名的硬编码依赖、data.sql 与 prod 环境的脱节。

### [P2] [Bug] GlobalExceptionHandler 靠字符串匹配 `article_slug_key` 捕获唯一冲突，约束名在三轨中不一致  <!-- 编号：B15-01 -->
- **定位**：`backend/src/main/java/com/nanmuli/blog/interfaces/handler/GlobalExceptionHandler.java:112`；约束名来源 `backend/src/main/resources/db/migration/V1_11__add_unique_index_article_slug.sql:4`（`idx_article_slug_unique`）vs `backend/src/main/resources/db/init.sql:842` 与 `deploy/db/init-scripts/schema.sql:1093`（`idx_article_slug_active`）；表内联 `slug VARCHAR(200) UNIQUE`（`init.sql:138`、`schema.sql:97`）
- **现象**：article.slug 的唯一性在数据库里由**三个不同机制**保证：①表定义内联 `UNIQUE`（产生默认约束 `article_slug_key`，GlobalExceptionHandler 依赖此名）②migration V1_11 创建索引 `idx_article_slug_unique` ③init.sql/schema.sql 创建部分唯一索引 `idx_article_slug_active`。GlobalExceptionHandler 只匹配 `article_slug_key`。
- **影响**：若未来某环境实际只生效了 V1_11 的索引名或部分索引名，则冲突异常将**穿透到 500 错误**而非返回 409 业务错误；当前靠"表内联 UNIQUE 始终先生效"侥幸成立。三轨约束名不一致本身就是 schema 漂移的直接证据。
- **根因/分析**：V1_11 是后加的迁移，但 init.sql/schema.sql 没采用 V1_11 的命名，而是自创 `idx_article_slug_active`（与 category/config 的 `_active` 命名风格一致）；表内联 `UNIQUE` 又是另一层。三层未对齐。
- **修复方向**：①统一采用部分唯一索引 `idx_article_slug_active`，移除表内联 `UNIQUE` 与 V1_11 的冗余索引（**大**，涉及数据迁移与约束 DROP）；或 ②GlobalExceptionHandler 改为按 PG 状态码 `23505`（unique_violation）捕获而非字符串匹配（**中**，需改异常处理逻辑）。建议先做 ②。
- **关联**：B06（异常处理）、横向主题 schema 漂移

---

## `[Security]` 安全漏洞

> 排查范围：默认弱口令 seed、密钥 seed、敏感字段标记、SQL 注入面（本模块纯 DDL/DML 静态脚本，无动态拼接）。

### [P1] [Security] admin 默认弱口令 `admin123` 在 schema.sql / init.sql / data.sql 三处 seed，data.sql 在 dev 环境每次启动都尝试插入  <!-- 编号：B15-02 -->
- **定位**：`deploy/db/init-scripts/schema.sql:888-890`、`backend/src/main/resources/db/init.sql:926-928`、`backend/src/main/resources/data.sql:5-7`；BCrypt 哈希 `$2a$10$L6YrzL7XRPy7S0FL3zUdNuer8d2WGZ5VICnomMZpz71LI0DsRf.xq`（对应明文 `admin123`，见 `data.sql:2` 注释）
- **现象**：三轨均用同一 BCrypt 哈希 seed admin 用户，明文 `admin123`。schema.sql 在首次建卷时执行（生产首启即种弱口令）；data.sql 在 dev 环境 `mode: always` 下每次启动执行（虽有 `WHERE NOT EXISTS` 幂等保护，但全新库首启仍会种入）。
- **影响**：生产环境若管理员忘记改密码，admin/admin123 直接进管理后台。已有 risk-register 与 audit-plan §9 线索，本报告补充三轨证据链。
- **根因/分析**：基线脚本为方便首启硬编码弱口令；check-deploy-env 未覆盖密码修改校验（见 X04）。
- **修复方向**：①首启后强制改密（**中**）；②schema.sql 种子密码留空或随机，通过环境变量 `ADMIN_INIT_PASSWORD` 注入（**中**）；③release-gate 增加"admin 密码非 admin123"检查（**小**，归 X04）。
- **关联**：B06-（鉴权/默认口令）、X02、X04（check-deploy-env）、横向主题配置一致性

### [P2] [Security] AES 加密密钥 seed 为空且 V1_21 删除了 DB 中的 `blog.security.encryption-key`，但 init.sql/schema.sql 仍 seed 此 key（空值），文档与运行时脱节  <!-- 编号：B15-03 -->
- **定位**：`backend/src/main/resources/db/migration/V1_21__remove_unnecessary_configs.sql:188-192`（删除 DB 中此 key 并注释"DB 中的值完全无效"）；`backend/src/main/resources/db/init.sql:1119` 与 `deploy/db/init-scripts/schema.sql:1073` 仍 seed `('blog.security.encryption-key', '', ...)`；`backend/src/main/resources/application-prod.yml:71` 从 `BLOG_SECURITY_ENCRYPTION_KEY` 环境变量读取
- **现象**：migration 层面已声明"DB 中此 key 无效、删除"，但 init.sql/schema.sql 两个基线脚本仍 seed 此 key（空值），且 `SystemConfigInitializer` 也不再处理它（grep 确认）。三轨对此 key 的处理完全不一致。
- **影响**：admin 在配置页能看到一个"加密密钥"配置项（空值），误以为改了生效——实际运行时走 `@Value` 注入的环境变量。误导性配置项，属于安全配置幻觉。
- **根因/分析**：V1_21 的清理未同步回 init.sql/schema.sql 基线（典型双轨漂移）。
- **修复方向**：①init.sql/schema.sql 删除 `blog.security.encryption-key` seed（**小**，单文件）；②同时核对 B07 `AesEncryptor` 真实取值路径（归 B07）。
- **关联**：B07（AES 加密主模块）、X06（配置一致性）、横向主题 schema 漂移

---

## `[Arch]` 架构与技术债

> 排查范围：Flyway 集成度、三轨漂移清单、缺表缺列缺索引、config seed 漂移、触发器覆盖、SQL 初始化机制设计、双轨漂移修复承诺与现状。

### [P1] [Arch] Flyway 完全未集成：pom 无依赖、yml 无配置、无 flyway_schema_history 表，但项目声称用 Flyway 且 migration 目录维护了 23 个脚本  <!-- 编号：B15-04 -->
- **定位**：
  - `backend/pom.xml:26-126`（依赖清单完整通读，**无 flyway-core**）
  - `backend/src/main/resources/application.yml`、`application-dev.yml`、`application-prod.yml`（**无 `spring.flyway.*` 配置**）
  - 全 `backend/` 目录 grep `flyway` 仅命中 `init.sql:4` 的注释（"-- Flyway 版本: V1.0.0"）
  - `deploy/db/README.md:25` 承诺"后续结构变更应通过 Flyway migration 完成"；`:57-63` 甚至给出 `select ... from flyway_schema_history` 示例——但此表根本不会被创建
  - migration 目录 `V1_1` ~ `V1_23` 共 23 个脚本存在，无人加载
- **现象**：项目在文档、代码注释、README 多处声称使用 Flyway 管理迁移，实际：
  1. pom 无 `flyway-core` 依赖（Spring Boot 3 下需手动加，starter 不传递）
  2. 三个 application yml 都无 `spring.flyway.*` 配置
  3. 运行时不会创建 `flyway_schema_history` 表
  4. V1_1 ~ V1_23 的全部变更**从未在任何环境被执行过**
- **影响**：①生产环境 schema 演进完全靠手工同步 init.sql ↔ schema.sql，遗漏即漂移（事实上已经漂移，见 B15-05/B15-06/B15-07）；②migration 脚本沦为"装饰性文档"，给维护者虚假的安全感；③fresh deploy 与 incremental upgrade 路径完全分离且无机制对齐。这是本项目 schema 一切漂移问题的**根因**。
- **根因/分析**：早期可能计划用 Flyway，但从未真正接入；后续为赶 MVP 直接用 schema.sql 一次性建库，migration 脚本继续追加但已脱节。CLAUDE.md 项目记忆 `database_schema_state.md` 也记录了"Flyway 未集成，双轨"。
- **修复方向**：①**接入 Flyway**（**大**）：pom 加 `flyway-core` + PG 驱动兼容版本，yml 配 `spring.flyway.enabled=true` + `baseline-on-migrate=true` + `baseline-version=1.0`，把现有 init.sql 设为 V1_0 基线，V1_1~V1_23 作为增量；②**或放弃 Flyway 承诺**，承认 schema.sql 是唯一真实源，删 migration 目录、改文档（**中**，但放弃演进能力）。推荐 ①。归 B15 主修复项。
- **关联**：横向主题 schema 漂移（最高优先级根因）、CLAUDE.md `database_schema_state.md`

### [P1] [Arch] schema 三轨漂移：init.sql / schema.sql / migration 严重不一致，全新环境建库后缺列缺索引致运行时错误  <!-- 编号：B15-05 -->
- **定位**：见下方"三轨差异清单"表
- **现象**：三个 schema 源（migration 增量、init.sql 基线声明、deploy schema.sql 实际生产基线）逐项 diff 后存在大量漂移。**生产实际用的是 schema.sql**（docker-compose 挂载），但 init.sql 与 migration 的演进从未同步回 schema.sql。
- **影响**：fresh deploy（用 schema.sql）后，下列对象缺失或值错误，直接导致运行时错误或行为偏差：
  - `web_collect_task.python_task_id` 列缺失（V1_10）→ Python 任务回调写入失败
  - `web_collect_task.ai_search_metadata` 列在 schema.sql 有、init.sql 有、但 V1_2 原始建表无（属事后补丁，三轨对齐但来源不一）
  - `idx_task_python_id` 索引缺失（V1_19）→ Python 任务回调查询全表扫
  - `ai_generation` 表在 schema.sql 有、init.sql **完全缺失**
  - 多项 config seed 缺失或默认值陈旧（见 B15-07）
- **根因/分析**：Flyway 未集成（B15-04）+ 手工双轨维护的必然结果。每次加 migration 后开发者忘记同步 init.sql/schema.sql。
- **修复方向**：①以 schema.sql 为权威基线，反向补齐 init.sql 与 migration 的差异；②接入 Flyway（B15-04）从根上消除双轨；③加 CI 校验脚本 diff schema.sql 与 init.sql（**中**）。归 B15 主修复项。
- **关联**：B15-04（根因）、B15-06/B15-07（具体漂移项）、横向主题 schema 漂移

#### [Arch] 三轨差异清单（schema 对象维度）

> "migration" 列指该对象是否在 V1_1~V1_23 中定义/变更；"init.sql"/"schema.sql" 列指该对象在对应基线文件中是否存在。✓=有，✗=无，△=存在但值/定义不同。

| 对象 | migration | init.sql | schema.sql | 差异说明 |
|---|---|---|---|---|
| `sys_user` 表 | ✗（无建表脚本） | ✓ | ✓ | migration 从不建核心表，基线缺失 |
| `article` 表 | ✗ | ✓ | ✓ | 同上 |
| `category` / `daily_log` / `sys_config` / `skill` / `project_showcase` / `friend_link` / `sys_file` / `sys_operation_log` / `sys_login_log` 表 | ✗ | ✓ | ✓ | 核心表全部无 migration 建表脚本 |
| `article_view_record` 表 | ✓ V1_1 | ✓ | ✓ | 三轨一致 |
| `web_collect_source/task/page` 表 | ✓ V1_2 | ✓ | ✓ | 建表三轨一致，但 V1_2 原始无 `version`/`success_count` 等列，靠 V1_16/V1_19 事后补 |
| `web_collect_task.python_task_id` 列 | ✓ V1_10 | ✗ | ✓ | **init.sql 缺此列**，全新库（init.sql 路径）写入失败 |
| `web_collect_task.ai_search_metadata` 列 | ✓ V1_9 | ✓ | ✓ | 三轨一致（事后补丁） |
| `idx_task_python_id` 索引 | ✓ V1_19 | ✗ | ✗ | **init.sql 与 schema.sql 都缺**，Python 任务回调查询无索引 |
| `article.slug` 唯一约束 | ✓ V1_11（名 `idx_article_slug_unique`） | △（表内联 `UNIQUE` + `idx_article_slug_active`） | △（同 init.sql） | 三处约束名不一致，见 B15-01 |
| `daily_log.category_id` / `is_public` 列 | ✓ V1_5 | ✓ | ✓ | 三轨一致 |
| `article.version` NOT NULL | ✓ V1_6 | ✓（建表即 NOT NULL） | ✓（同 init.sql） | 一致 |
| `ai_generation` 表 | ✗ | ✗ | ✓ | **init.sql 完全缺此表**；且全代码无 `AiGeneration` 类引用（死表）；schema.sql 有表无 Java 落地 |
| `article_vector` 表 | ✗ | ✓ | ✓ | init.sql/schema.sql 一致；Java 侧无 Repository（落地缺口归 B13） |
| `digest_fingerprint` 表 | ✓ V1_17 | ✓ | ✓ | 三轨一致 |
| `source_authority` 表 | ✓ V1_18 | ✓ | ✓ | 三轨一致（含 28 条域名 seed） |
| `uk_source_name_active` 唯一索引 | ✗（无 migration，靠 `data.sql:20` 补） | ✓ | ✓ | 由 data.sql 兜底，见 B15-08 |
| `idx_digest_fp_unique` 唯一索引 | ✓ V1_19 | ✓ | ✓ | 三轨一致（V1_17 原始未加，V1_19 补） |
| `web_collect_source.version` 列 | ✓ V1_19 | ✓（line 635, DEFAULT 0） | ✓（line 640, DEFAULT 0） | 三轨一致 |
| 触发器 `update_*_updated_at` 覆盖范围 | △（V1_1/V1_2 局部） | ✓（14 个表） | ✓（14 个表） | init.sql/schema.sql 全覆盖，migration 分散补 |
| `tag` / `article_tag` 表 | ✓ V1_7（DROP） | ✗（已移除，仅注释） | ✗（已移除，仅注释） | 三轨一致（已清理） |
| zhparser FTS 索引 `idx_article_fts` | ✓ V1_8 | ✓ | ✓ | 三轨一致 |
| `idx_article_search_trgm`（pg_trgm 模糊索引） | ✗ | ✓（line 197） | ✗ | **仅 init.sql 有**，schema.sql 与 migration 都无；crawler 有模糊搜索需求时性能差异 |

### [P1] [Arch] config seed 三轨漂移：V1_21 删除的 64 项 key 仍在 init.sql/schema.sql 中 seed，V1_20/V1_22/V1_23 的新 key 与默认值未同步回基线  <!-- 编号：B15-06 -->
- **定位**：
  - `backend/src/main/resources/db/migration/V1_21__remove_unnecessary_configs.sql`（删除 64 项调参 key）
  - `backend/src/main/resources/db/init.sql:966-1120`（仍 seed 绝大多数 V1_21 已删的 key，如 `crawler.ai.temperature` line 999、`crawler.search.*` line 1096-1112、`crawler.quality.*` line 1081-1094）
  - `deploy/db/init-scripts/schema.sql:929-1073`（同样仍 seed V1_21 已删的 key）
  - V1_20 新增的 `crawler.service.java-api-url`、`crawler.pipeline.filter_content_preview_length` 在 init.sql/schema.sql 中 grep **无匹配**
  - V1_22 新增的 `crawler.dependency_mode` 在 init.sql/schema.sql 中 grep **无匹配**（仅 data.sql 兜底 + SystemConfigInitializer 运行时补）
- **现象**：config seed 三层不同步：
  1. migration 层：V1_12 全量 seed → V1_13/V1_15/V1_16/V1_20/V1_22 增量加 → V1_21 批量删
  2. init.sql 层：仍保留 V1_12 时期的全量 seed（约 100+ key），未应用 V1_21 的删除，也未加 V1_20/V1_22 的新 key
  3. schema.sql 层：与 init.sql 基本同步（都保留旧 key、缺新 key），额外还 seed 了 V1_21 已删的 `crawler.digest.optimization_min_results_per_section`、`crawler.digest.global_timeout`、`crawler.optimization.breadth_max_rounds`、`crawler.ai.digest_*` 等
- **影响**：fresh deploy 后 sys_config 表里有 64 项"V1_21 已声明应删"的死配置（admin 看到一堆调参项，但改了 Python 侧也不读 DB 走 fallback）；同时缺 `crawler.dependency_mode`（虽有 SystemConfigInitializer 运行时兜底，但首启时机与一致性无保障）。配置页呈现与 V1_21 的"精简 33 项"设计意图完全不符。
- **根因/分析**：V1_21 的清理是 migration 层独有操作，init.sql/schema.sql 基线从未回写；V1_20/V1_22 的新增也只在 migration 层。典型的"增量变更不同步基线"。
- **修复方向**：①以 V1_21 之后的"33 项核心配置"为准，重写 init.sql/schema.sql 的 sys_config seed 段（**中**）；②接入 Flyway（B15-04）后此问题自动消解；③补 CI 校验 config key 集合一致性（**中**）。
- **关联**：B15-04（根因）、B15-07（默认值漂移）、横向主题配置一致性（X06 主模块）

### [P2] [Arch] config 默认值漂移：`crawler.digest.sections` 三/五段、`crawler.digest.search_engine` bing/sogou、`crawler.ai.digest_max_tokens` 10000/16000 在各轨不一致  <!-- 编号：B15-07 -->
- **定位**：
  - `crawler.digest.sections`：V1_12 seed 1 段（`[{"name":"news",...}]`，line 130）→ V1_14 改 3 段 → V1_23 default 改 5 段（`hot_trend/open_source/dev_tool/tech_article/paper`，line 5）；init.sql/schema.sql 仍 seed 3 段（`news/articles/opensource`，init.sql:1036、schema.sql:995）
  - `crawler.digest.search_engine`：V1_20 改 `sogou`（line 8）；init.sql:1034 / schema.sql:993 仍 seed `bing`
  - `crawler.ai.digest_max_tokens`：V1_20 改 `16000`（line 5）；init.sql:1003 / schema.sql 无此 key（被 V1_21 删）但仍 seed `10000`
  - `crawler.optimization.mode`：V1_12 seed `keyword` → V1_13 改 `both`；init.sql/schema.sql 已 seed `both`（一致）
- **现象**：多个 config key 的默认值在 migration 演进中被修改，但 init.sql/schema.sql 基线仍是旧值。
- **影响**：fresh deploy 后日报板块配置、搜索引擎、AI token 上限等关键运行参数与最新设计不符，需 admin 手动改或 crawler 走 Python config.py fallback。行为偏差，非崩溃。
- **根因/分析**：同 B15-06，增量变更不同步基线。
- **修复方向**：随 B15-06 一并修；或接入 Flyway 自动消解（**中**）。
- **关联**：B15-04、B15-06、X06

### [P2] [Arch] data.sql 承担了"补丁式 migration"职责：补 web_collect_source 列、补 uk_source_name_active 索引，与 migration 职责重叠且仅 dev 执行  <!-- 编号：B15-08 -->
- **定位**：`backend/src/main/resources/data.sql:9-20`（用 `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` 补 V1_16 的 5 列、V1_19 的 version 列、V1_20 的 `uk_source_name_active` 唯一索引）
- **现象**：data.sql 本应是纯数据 seed，实际混入了 schema 变更（`ALTER TABLE`、`CREATE UNIQUE INDEX`）。这些补丁仅在 dev 环境 `mode: always` 执行；prod 环境 `mode: never`（application-prod.yml:27）**完全不执行**，prod 的这些列/索引只能靠 schema.sql 手工同步（schema.sql 确实有，line 631-636、647）。
- **影响**：①职责混乱（data.sql 既 seed 数据又改 schema）；②dev 与 prod 的 schema 补齐机制不同（dev 靠 data.sql 每次跑、prod 靠 schema.sql 首次建卷），极易漂移；③若开发者只改 data.sql 不改 schema.sql，prod 永远缺。
- **根因/分析**：Flyway 未集成，开发者被迫用 data.sql 当"运行时 migration"兜底。
- **修复方向**：接入 Flyway（B15-04）后，data.sql 回归纯 seed 职责，schema 变更全部走 migration（**中**）。
- **关联**：B15-04（根因）、横向主题 schema 漂移

### [P2] [Arch] `spring.sql.init.mode` dev(always)/prod(never) 的语义错位：dev 每次启动重跑 data.sql（含 ALTER），prod 完全不跑  <!-- 编号：B15-09 -->
- **定位**：`backend/src/main/resources/application.yml:14`（`mode: always`，dev 默认）；`backend/src/main/resources/application-prod.yml:27`（`mode: never`）
- **现象**：dev 每次启动执行 data.sql（含 ALTER TABLE 补丁），prod 完全不执行。两侧 schema 演进路径不同。
- **影响**：①dev 环境 data.sql 的 ALTER 虽 `IF NOT EXISTS` 幂等，但每次启动都做 schema 内省查询，轻微性能与日志噪音；②prod 环境的 schema 演进完全脱离 Spring 控制，纯靠 docker 卷首次建库；③"在 dev 验证通过的 schema 变更"与"prod 实际 schema"无机制保证一致。
- **根因/分析**：Spring Boot 的 `spring.sql.init` 本就是为 demo/原型设计，生产禁用是正确做法，但项目未提供 prod 的 schema 演进替代方案（Flyway 缺失）。
- **修复方向**：接入 Flyway（B15-04）后，`spring.sql.init` 可整体关闭，dev/prod 统一走 Flyway（**大**）。
- **关联**：B15-04、B15-08

### [P3] [Arch] init.sql 头部声明 "Flyway 版本: V1.0.0" 但该文件不被 Flyway 加载，属误导性注释  <!-- 编号：B15-10 -->
- **定位**：`backend/src/main/resources/db/init.sql:4`（`-- Flyway 版本: V1.0.0`）
- **现象**：init.sql 自称是 Flyway V1.0.0 基线，但 Flyway 未集成，此文件不被任何机制加载（dev 走 data.sql，prod 走 schema.sql，init.sql 仅作为"参考基线"存在于代码库）。
- **影响**：误导维护者以为 init.sql 是权威基线；实际它既不被执行也不与生产 schema.sql 完全一致（如缺 ai_generation 表、缺 python_task_id 列）。
- **根因/分析**：Flyway 未集成的衍生误导。
- **修复方向**：接入 Flyway 后将 init.sql 真正作为 V1_0 基线（B15-04），或删除此注释明确其"参考文档"定位（**小**）。
- **关联**：B15-04

### [P3] [Arch] `ai_generation` 表为死表：schema.sql 有定义但全代码无 AiGeneration 类、无 Mapper、无 Repository  <!-- 编号：B15-11 -->
- **定位**：`deploy/db/init-scripts/schema.sql:529-554`（表定义）；`backend/src/main/java` grep `ai_generation|AiGeneration` **无匹配**
- **现象**：schema.sql 定义了 ai_generation 表（AI 生成记录），但 Java 侧零引用。同时 init.sql **完全缺此表**（grep 无匹配）。
- **影响**：三轨中只有 schema.sql 有此表，且无代码消费。建表语句占用 schema 空间但无业务价值。AI 链路落地缺口归 B13。
- **根因/分析**：AI 模块（B13）是 NoOp 空壳，表先建了但实现没跟上；init.sql 漂移更严重（连表都没同步）。
- **修复方向**：随 B13 AI 链路落地决策一并处理——若 AI 链路废弃则 DROP 此表，若要落地则补 Java 侧（**大**，归 B13）。
- **关联**：B13（AI 空壳链路主模块）、B15-05

---

## `[Deps]` 依赖升级与版本

### 本模块依赖清单（基于声明文件，未翻依赖源码）

| 依赖 | 版本 | 声明位置 | 已知风险/可升级 | 备注 |
|---|---|---|---|---|
| PostgreSQL JDBC | 随 Spring Boot 3.3.5 BOM | `backend/pom.xml:49-52` | 无 | `org.postgresql:postgresql` |
| pgvector Java client | 0.1.4 | `backend/pom.xml:54-57` | 较旧，0.1.x 系 | `com.pgvector:pgvector` |
| Flyway | **未声明** | `backend/pom.xml`（缺失） | — | 本模块核心缺口，见 B15-04 |
| zhparser | 2.2（DB 镜像层） | `deploy/db/Dockerfile:15` ARG | — | 非 Java 依赖，DB 扩展 |
| pgvector 扩展 | 随 `ankane/pgvector:latest` | `deploy/db/Dockerfile:10` | `:latest` 未固定 tag | X01 主模块 |

> 排查范围：pom.xml 依赖清单、Dockerfile ARG。本模块无独立第三方库依赖（纯 SQL + DDL）。**核心发现：Flyway 依赖缺失**（B15-04）。

### [P1] [Deps] Flyway 依赖未声明，导致 schema 演进机制从根上缺失  <!-- 编号：B15-12 -->
- **定位**：`backend/pom.xml:26-126`（完整依赖清单，无 `flyway-core`）
- **现象**：项目声称用 Flyway，pom 里没有 `org.flywaydb:flyway-core`。Spring Boot 3.3.5 下 Flyway 需手动声明（不像 Spring Boot 2.x 时代 starter 会传递）。
- **影响**：见 B15-04。此条作为 `[Deps]` 维度的独立编号，便于索引页依赖升级批次引用。
- **根因/分析**：架构决策与依赖声明脱节。
- **修复方向**：pom 加 `flyway-core`（版本随 Spring Boot BOM 即可，3.3.5 对应 Flyway 10.x）+ PG 兼容性确认（**小**，单依赖声明）；接入配置见 B15-04。
- **关联**：B15-04

### [P3] [Deps] pgvector Java client 0.1.4 版本陈旧  <!-- 编号：B15-13 -->
- **定位**：`backend/pom.xml:23`（`<pgvector.version>0.1.4</pgvector.version>`）
- **现象**：pgvector Java client 锁在 0.1.4。
- **影响**：当前 article_vector 表无 Repository（B13），此依赖实际未被业务代码使用。但版本较旧，未来 AI 链路落地时可能需升级。
- **根因/分析**：预留依赖，未跟进上游。
- **修复方向**：随 B13 AI 链路落地一并评估升级（**小**）。
- **关联**：B13

---

## `[Design]` 功能设计合理性

> **必填**。从真实使用出发审视 schema 管理机制设计。

**审视结论**：

1. **场景适配（单人维护的技术博客 + MVP Beta）**：当前 schema 管理机制（schema.sql 一次性建库 + data.sql dev 兜底 + migration 装饰性存在 + 无 Flyway）对单人 MVP 来说**勉强能用但脆弱**——fresh deploy 能跑起来，但任何 schema 变更都要手工同步三个文件，遗漏即漂移（事实上已漂移 10+ 处）。这不是过度设计，而是**设计未完成**——声称的 Flyway 演进能力根本没接入。

2. **闭环完整性（schema 演进闭环）**：schema 变更闭环**断裂**。migration 脚本写了但不执行，init.sql/schema.sql 靠手工同步，无 CI 校验，无对齐机制。结果是 schema.sql（生产基线）与 migration（设计意图）已经漂移到"缺列缺索引缺表"的程度（B15-05）。这是闭环缺失的直接后果。

3. **可运维性（故障定位/回滚）**：无 `flyway_schema_history` 表意味着无法回答"当前库是哪个版本"。出问题时只能 `pg_dump` 对比，回滚纯靠手工 SQL。对单人博客尚可忍受，但 CLAUDE.md 声称"MVP Beta 试用稳定化"，schema 不可追溯是与"稳定化"目标冲突的。

**结论**：schema 管理机制的设计意图（Flyway 演进）与实际实现（手工三轨）严重脱节，是本项目最该优先修复的架构债之一。建议作为 P1 批次处理。

### [P1] [Design] schema 管理机制设计与实现脱节，建议接入 Flyway 或明确放弃演进承诺  <!-- 编号：B15-14 -->
- **定位**：本模块整体设计（见上述审视结论）
- **现象**：设计意图是 Flyway 演进式 schema 管理，实际是 schema.sql 一次性 + 手工三轨同步。
- **影响**：schema 漂移已实际发生（B15-05/B15-06/B15-07），fresh deploy 缺列缺索引，配置页呈现与设计意图不符。
- **建议方向**：**接入 Flyway**（推荐，B15-04）或**明确放弃 Flyway 承诺**、删 migration 目录、改文档为"schema.sql 单一源"。二选一，禁止现状继续（**大**）。
- **关联**：B15-04、B15-05、横向主题 schema 漂移

---

## 模块小结

### 严重度统计

| 级别 | 数量 | 条目编号 |
|---|---|---|
| P0 | 0 | — |
| P1 | 5 | B15-02、B15-04、B15-05、B15-06、B15-12、B15-14 |
| P2 | 5 | B15-01、B15-03、B15-07、B15-08、B15-09 |
| P3 | 3 | B15-10、B15-11、B15-13 |
| P4 | 0 | — |

> 注：B15-14 为 Design 维度审视条目，与 B15-04 同源（Flyway 未集成），分别从"架构缺陷"与"设计审视"角度记录。统计时计入 P1。

### Top 风险（本模块最该先看的 ≤3 条）

1. **B15-04 Flyway 完全未集成** —— 一切 schema 漂移的根因。pom 无依赖、yml 无配置、无 history 表，migration 目录 23 个脚本沦为装饰。修复此条可连带消解 B15-05/06/07/08/09/10。
2. **B15-05 schema 三轨漂移致 fresh deploy 缺列缺索引** —— 生产实际用的 schema.sql 缺 `python_task_id` 列（init.sql）、缺 `idx_task_python_id` 索引（双轨）、缺 `ai_generation` 表（init.sql），全新库建后运行时错误。
3. **B15-02 admin 默认弱口令 admin123 三处 seed** —— 生产首启即种弱口令，check-deploy-env 未覆盖，需忘改才触发但后果严重。

### 修复优先级建议

- **立即（P0/P1）**：
  - B15-04 / B15-12：接入 Flyway（pom 加依赖 + yml 配置 + baseline 策略）—— 根因修复
  - B15-05：随 Flyway 接入，反向补齐 init.sql/schema.sql 与 migration 差异
  - B15-02：admin 弱口令改环境变量注入 + release-gate 校验
  - B15-06 / B15-07：config seed 三轨对齐（随 Flyway 或手工同步）
- **计划（P2）**：
  - B15-01：GlobalExceptionHandler 改按 SQLSTATE 23505 捕获，约束名统一
  - B15-03：init.sql/schema.sql 删除已失效的 `blog.security.encryption-key` seed
  - B15-08 / B15-09：data.sql 回归纯 seed 职责，schema 变更移交 Flyway
- **择机（P3/P4）**：
  - B15-10：init.sql 误导性注释修正
  - B15-11：`ai_generation` 死表随 B13 AI 链路决策处理
  - B15-13：pgvector client 升级随 B13 评估

### 排查盲区 / 待复核

- **[需查证] B15-01**：PG 表内联 `slug VARCHAR(200) UNIQUE` 产生的默认约束名是否恒为 `article_slug_key`。当前 GlobalExceptionHandler 依赖此名。若 PG 版本或建表顺序导致约束名变化，异常捕获会失效。建议在真实 PG 实例 `\d+ article` 核实（受 §1.3 命令边界限制，本轮未跑 docker）。
- **[需查证] B15-05**：`idx_article_search_trgm`（pg_trgm 模糊索引）仅 init.sql 有、schema.sql 与 migration 都无——是否为有意删除（crawler 模糊搜索改走他路）还是漂移遗漏。需核对 ArticleRepositoryImpl 是否还用 LIKE 模糊查询（归 B01/B14 视角）。
- **[需查证] B15-06**：V1_21 删除的 64 项 key 中，是否有部分在 Python `config.py` 仍有默认值 fallback 且 admin 确实不需要管理——若是，则 init.sql/schema.sql 保留 seed 反而是"无害冗余"而非 bug。需对照 crawler config.py 默认值表（归 C11）。
- **[需查证] B15-11**：`ai_generation` 表是否在某次计划中被声明"未来 AI 链路落地用"而刻意保留。需查 git log 该表引入 commit 的 commit message（本轮未深挖 git 历史）。
