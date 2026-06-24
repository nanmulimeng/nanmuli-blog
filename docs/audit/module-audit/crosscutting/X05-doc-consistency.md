# X05 文档一致性 排查报告

> **模块编号**：X05
> **排查范围**：文档与代码的漂移、误导性内容、过时的验证基线数字、文档缺失。覆盖根 `README.md`、`CLAUDE.md`、`AGENTS.md`、`docs/**/*.md`、`crawler-service/README.md`、`deploy/README.md`、`deploy/db/README.md`、`frontend/README.md`、`backend/.../db/init.sql` 头部注释，以及文档声明的测试/版本基线。
> **基线 commit**：`6ae930098405f4d0553d96a852f3345d0f39682e`
> **工作区状态**：脏。涉及本模块的未提交改动：`deploy/README.md`（已被改）、`docs/audit/full-project-risk-register.md`（已被改）、`scripts/release/release-gate.ps1`。其余未提交改动（`ConfigRepositoryImpl.java`、`WebCollectPageMapper.java`、crawler `search.py`/`knowledge_base.py` + 多个 test 文件、新增 `backend/src/test/.../webcollector/`）不影响文档文字内容，但影响"测试基线数字"的实时性判断。
> **排查日期**：2026-06-23
> **排查人**：X05 文档一致性排查 agent
> **状态**：待复核

---

## 模块概览

**职责**：保证项目文档（README/CLAUDE/AGENTS/docs/deploy/crawler/frontend 等）描述的事实（测试基线、版本、功能声称、路径、配置值）与代码实际一致，文档自身不互相矛盾，不存在误导性内容（如教用未集成的工具、自称不属于自己版本的标签）。

**关键文件**：
- `README.md` —— 项目总览 + 验证基线表 + 技术栈表 + 启动/验证命令
- `CLAUDE.md` / `AGENTS.md` —— Agent 协作规范 + 项目状态口径（含验证基线 75/1266）
- `docs/trial-release-roadmap.md` —— 试用上线路线图（含验证基线 88/1366）
- `docs/digest-system.md` —— 日报/优化系统说明（引用模块路径）
- `docs/config-db-migration-plan.md` —— 配置/迁移现状
- `deploy/README.md` / `deploy/db/README.md` —— 部署与数据库说明（db/README 教用 Flyway）
- `crawler-service/README.md` / `frontend/README.md` —— 子项目说明
- `backend/src/main/resources/db/init.sql:1-6` —— 头部自称 "Flyway 版本: V1.0.0"

**对外接口 / 依赖**：
- 对外：文档是新人上手、运维故障定位、试用上线决策的依据。
- 依赖（被文档描述的代码事实）：backend `@Test` 总数、crawler `test_` 函数数、pom.xml/package.json/requirements.txt 版本号、Flyway 集成状态、migration 最新版本号、AI_MODEL 配置值、release 脚本存在性、compose 端口。

**已读文件清单**（可追溯 + 暴露盲区）：
- `README.md` —— 通读
- `AGENTS.md` —— 通读
- `CLAUDE.md`（项目级，已由 system 注入）—— 通读
- `docs/README.md` —— 通读
- `docs/trial-release-roadmap.md` —— 通读
- `docs/digest-system.md` —— 通读
- `docs/web-collector-module-design.md:1-60` —— 片段
- `docs/config-db-migration-plan.md` —— 通读
- `docs/future-development-plan.md:1-50` —— 片段
- `docs/plan-crawl-tools-refactor.md:1-40` —— 片段
- `docs/mvp-beta-2-release-checklist.md` —— 通读
- `deploy/README.md` —— 通读（工作区已修改版本）
- `deploy/db/README.md` —— 通读
- `crawler-service/README.md` —— 通读
- `crawler-service/docs/architecture-v3.md:1-50` —— 片段
- `crawler-service/docs/daily-digest-review.md:1-40` —— 片段
- `frontend/README.md` —— 通读
- `backend/src/main/resources/db/init.sql:1-30` —— 片段（头部注释）
- `backend/pom.xml`（properties + dependencies）—— grep
- `frontend/package.json`（依赖版本）—— grep
- `crawler-service/requirements.txt` —— grep
- `deploy/docker-compose.yml`（端口/容器名）—— grep
- `deploy/.env.example` / `crawler-service/.env.example`（AI_MODEL）—— grep
- `backend/src/main/resources/db/migration/V1_*.sql`（列表 + AI_MODEL 值）—— grep
- `docs/audit/full-project-risk-register.md:1-30` —— 片段（确认审计文档自身状态）

**主模块归属**：本模块深查"文档说了什么 vs 代码实际是什么"。共享对象按 §8.6 只引用不展开：
- **schema 漂移 / Flyway 未集成**：主模块 B15，本模块只查"文档是否如实描述了 Flyway 状态"。
- **AI_MODEL 三处不一致**：主模块 X06，本模块只引用并记录文档侧的口径。
- **配置项默认值/敏感项**：主模块 X06。
- **测试体系失衡（111 @Test 全单测）**：主模块 X03，本模块只查"文档写的 passed 数字是否对得上"。

---

## `[Bug]` 代码正确性与潜在缺陷

> 排查范围：文档作为"事实陈述"的准确性——测试基线数字、版本号、路径引用、功能声称是否与代码实际相符。文档类 bug 表现为"读者照文档操作会得到错误结论或走错路"。逐份文档抽查 2-3 个可验证事实。

### [P2] [Bug] 验证基线数字三套口径，且都偏离当前实际   <!-- 编号：X05-01 -->
- **定位**：
  - `README.md:14-15`（"Backend `mvn test`：88 passed"、"Crawler `python -m pytest -q --tb=short`：1366 passed"，日期 2026-06-18）
  - `AGENTS.md:67-68` + `CLAUDE.md` 项目记忆"最近验证基线"段（"75 tests passed"、"1266 passed"，日期 2026-06-03）
  - `docs/trial-release-roadmap.md:26-27`（"88 passed"、"1366 passed"，日期 2026-06-18）
  - `crawler-service/README.md:18`（"1266 passed"，日期 2026-06-03）
  - `crawler-service/docs/daily-digest-review.md:31-32`（"1266 passed"、"75 tests passed"，日期 2026-06-03）
  - 代码反证：`backend/src/test/**/*.java` 实际 `@Test` 注解数 = **111**（`grep -rE "@Test" backend/src/test --include="*.java" -c` 汇总）；`crawler-service/tests/*.py` 实际 `def test_` / `async def test_` 函数数 = **1376**（`grep -rEc "^\s*(async\s+)?def\s+test_" crawler-service/tests/*.py` 汇总）。
- **现象**：项目里同时存在三套测试基线数字——README/trial-roadmap 用 88/1366（06-18），CLAUDE/AGENTS/crawler-README/daily-digest-review 用 75/1266（06-03）。实际代码（06-23 工作区）backend @Test=111、crawler test_ 函数=1376。三套数字相互矛盾，且全部偏离当前实际：backend 偏差 +23（111 vs 88）/+36（111 vs 75），crawler 偏差 +10（1376 vs 1366）/ +110（1376 vs 1266）。
- **影响**：①新人或评审者照 README 复核基线时，跑出的数字对不上文档，会怀疑环境异常或代码回退，浪费排查时间。②两套数字并存（88 vs 75、1366 vs 1266）让读者无法判断哪份文档是"最新口径"。③CI/门禁若以文档数字为软参考，会放行实际已显著增长的测试集，掩盖测试增量未被记录的事实。注意：pytest "passed" 还会随参数化展开和 skip 动态变化，文档写的固定数字本质就无法长期准确。
- **根因/分析**：基线数字是"某次手跑的快照"，但分散在 6 份文档里，没有单一事实源（single source of truth），每次更新测试后无人同步所有副本。已排除的误判：并非代码删了测试（@Test=111 持续增长趋势合理），而是文档滞后。
- **修复方向**：①在 `docs/README.md` 或新建 `docs/verification-baseline.md` 设单一基线源，其余文档只链接、不复制数字（改动面：中）。②把"X passed"改为"以实际 `mvn test` / `pytest` 输出为准，文档仅记录最近复核日期"，去掉易过期的硬数字（改动面：小）。③若保留数字，建立 release-gate 校验步骤：跑测试后把实际数字回写到单一源文件（改动面：中）。
- **关联**：[[X03]]（测试体系主模块）/ 横向主题"配置一致性"（文档基线一致性）

### [P2] [Bug] `init.sql` 头部自称 "Flyway 版本: V1.0.0" 但 Flyway 根本未集成   <!-- 编号：X05-02 -->
- **定位**：
  - `backend/src/main/resources/db/init.sql:1-6`（注释块写 "-- Flyway 版本: V1.0.0"、"-- 创建时间: 2026-04-06"）
  - 代码反证：`backend/pom.xml` 全文无 `flyway` 依赖（`grep flyway backend/pom.xml` exit 1）；`backend/src/main/resources/application*.yml` 全部无 `flyway:` 配置（`grep -ri flyway backend/src/main/resources/` 仅命中 init.sql 自身）；migration 目录 `backend/src/main/resources/db/migration/` 虽有 V1_1..V1_23 共 23 个脚本，但无任何代码会在启动时执行它们（无 Flyway 引擎）。
- **现象**：init.sql 头部注释明确标注 "Flyway 版本: V1.0.0"，暗示该脚本由 Flyway 管理或与 Flyway 版本号挂钩。但实际上：①项目未引入 Flyway 依赖；②该文件是 Docker PostgreSQL 首次初始化时由 `/docker-entrypoint-initdb.d` 执行的裸 SQL，与 Flyway 无关；③真正的 migration 脚本（V1_1..V1_23）既不被 Flyway 执行，也不被 init.sql 引用，处于"声明了却没人跑"的悬空状态（已知全局结论，归 B15 深查）。
- **影响**：读者（尤其新接手的开发或运维）看到 "Flyway 版本: V1.0.0" 会误以为：①项目用了 Flyway；②init.sql 是 Flyway baseline；③migration 脚本会被自动执行。三者皆假。故障场景：运维按 Flyway 习惯去查 `flyway_schema_history` 表（`deploy/db/README.md:60-62` 还教了这条 SQL），但表根本不存在或为空，导致误判 schema 状态。更严重的是，新人可能以为"改 migration 脚本就能演进 schema"，实际改了根本不生效（schema 演进实际靠 init.sql/schema.sql 双轨手改，漂移风险高）。
- **根因/分析**：早期可能计划用 Flyway，注释先写了，但最终未集成，注释未清理。migration 目录可能是从其他项目模板带过来的或为未来预留。已排除的误判：已确认 pom.xml 无 flyway-core 依赖、无 spring-boot-starter-flyway、application.yml 无 `spring.flyway.*`，确属"完全未集成"而非"集成了但未启用"。
- **修复方向**：①删除 init.sql 头部 "Flyway 版本: V1.0.0" 这行误导注释，改为如实说明"本文件由 Docker entrypoint 执行，结构演进见 deploy/db/README.md"（改动面：小）。②与 B15 协同：要么真正集成 Flyway 让 migration 脚本生效，要么删除/归档悬空的 migration 目录并在文档说明现状（改动面：大，归 B15 主模块）。本模块只要求"文档/注释不再撒谎"。
- **关联**：[[B15-未编号]] schema 三轨漂移主模块 / 横向主题"schema 漂移" / 次维度 `[Arch]`

### [P2] [Bug] `deploy/db/README.md` 通篇教用 Flyway，但项目根本没集成 Flyway   <!-- 编号：X05-03 -->
- **定位**：
  - `deploy/db/README.md:6`（"生产或长期试用环境建议优先使用后端 Flyway migration 管理结构演进"）
  - `deploy/db/README.md:25`（"后续结构变更应通过后端 `src/main/resources/db/migration` 下的 Flyway 脚本完成"）
  - `deploy/db/README.md:57-63`（"查看 Flyway 版本" SQL：`select installed_rank, version, description, success from flyway_schema_history ...`）
  - `deploy/db/README.md:69`（"新增配置项优先走 Flyway + `SystemConfigInitializer` 双保险"）
  - `AGENTS.md:143`（"Schema 变化使用 Flyway migration"——开发规范也这么写）
  - 代码反证：同 X05-02，`backend/pom.xml` 无 flyway 依赖，application.yml 无 flyway 配置。
- **现象**：deploy/db/README.md 把 Flyway 描述为"生产环境优先使用的迁移机制"，并给出查询 `flyway_schema_history` 的 SQL 作为运维命令。AGENTS.md 的开发规范也写"Schema 变化使用 Flyway migration"。但项目从未集成 Flyway，migration 目录里的 23 个脚本无人执行。
- **影响**：①运维照文档去 `select * from flyway_schema_history` 会报"relation does not exist"，浪费时间。②开发照 AGENTS.md 规范"新增 Flyway migration"来改 schema，改完不生效（实际要改 init.sql + schema.sql 双轨），导致 schema 漂移加剧。③与根 README/crawler README 形成系统性误导：整个项目的数据库演进叙事建立在"有 Flyway"这个不存在的地基上。
- **根因/分析**：与 X05-02 同源——Flyway 是"计划中但未落地"的能力，文档却按"已落地"来写。deploy/db/README.md 更新日期 2026-06-03，彼时这一差距已存在却未被修正。已排除的误判：已确认不是"Flyway 集成了但配置在别处"——application-prod.yml 也无 flyway 配置。
- **修复方向**：①deploy/db/README.md 改写为如实描述当前双轨机制（init.sql 首次初始化 + schema.sql + migration 脚本目前需手动应用），删除或标注 `flyway_schema_history` 查询为"若未来集成 Flyway 后可用"（改动面：中）。②AGENTS.md 开发规范同步修正（改动面：小）。③与 B15 协同决定 Flyway 路线，文档跟随代码事实。
- **关联**：[[B15-未编号]] / [[X05-02]] / 横向主题"schema 漂移"

### [P3] [Bug] `docs/digest-system.md` 等多份文档把 AI_MODEL 口径统一写成 `deepseek-v4-pro`，但 `.env.example` 实际是 `qwen-plus`   <!-- 编号：X05-04 -->
- **定位**：
  - 文档侧（统一写 `deepseek-v4-pro`）：`README.md:91`、`AGENTS.md` 未提具体值、`deploy/README.md:81`、`crawler-service/README.md:233`、`docs/trial-release-roadmap.md:50,80`、`docs/digest-system.md` 未写具体值、`docs/config-db-migration-plan.md` 未写具体值。
  - 配置侧不一致：`deploy/.env.example:17`（`AI_MODEL=qwen-plus`）、`crawler-service/.env.example:102`（`AI_MODEL=qwen-plus`）。
  - sys_config 种子（与文档一致）：`backend/src/main/resources/db/migration/V1_12__unify_sys_config.sql:91,217`（`crawler.ai.model` 默认 `deepseek-v4-pro`）、`backend/src/main/resources/db/init.sql:993`、`deploy/db/init-scripts/schema.sql:956`（同为 `deepseek-v4-pro`）。
- **现象**：所有文档声称试用模型是 `deepseek-v4-pro`，sys_config 种子也写 `deepseek-v4-pro`，但两份 `.env.example` 写的是 `qwen-plus`。文档叙事与 env 模板矛盾。
- **影响**：新人复制 `.env.example` 起 Docker，实际跑的是 `qwen-plus`，但读文档以为是 `deepseek-v4-pro`，AI 行为/成本/可用性与预期不符时定位困难。注意：sys_config 优先级高于 env（见 config-db-migration-plan.md §配置优先级），运行时 crawler 会从 backend 拉 `deepseek-v4-pro`，所以 env 的 `qwen-plus` 在 Blog-integrated 模式下实际被覆盖——这让"文档 vs env"的矛盾更隐蔽。
- **根因/分析**：env 模板与 sys_config 种子由不同时刻/不同人维护，文档跟随了 sys_config 那一版。这是配置一致性问题，归 X06 主模块深查；本模块只记录"文档侧口径是 deepseek-v4-pro，env 侧是 qwen-plus，二者打架"。
- **修复方向**：归 X06 统一裁决——要么 env.example 改为 deepseek-v4-pro 与文档/sys_config 对齐，要么文档改为说明"env 模板用 qwen-plus 作示例，实际模型以 sys_config 为准"。本模块要求"文档与最显眼的配置模板（.env.example）不打架"（改动面：小，但归属 X06）。
- **关联**：[[X06-未编号]] 配置一致性主模块 / 横向主题"配置一致性"

### [P3] [Bug] 根 `README.md` 技术栈表写 "Vite 5.4"，实际 package.json 声明 `^5.0.11`   <!-- 编号：X05-05 -->
- **定位**：
  - 文档侧：`README.md:98`（"Vite | 5.4"）、`frontend/README.md:27`（"Vite | 5.4"）。
  - 代码反证：`frontend/package.json`（`"vite": "^5.0.11"`）；`frontend/node_modules/vite/package.json` 实装 `5.4.21`（因 `^5.0.11` 允许 5.x 最新）。
- **现象**：文档写 Vite 5.4，package.json 声明的是 `^5.0.11`（最低 5.0.11）。实装（lock 后）是 5.4.21，所以"5.4"描述的是实装版本而非声明版本。
- **影响**：轻微。读者照 package.json 看到的是 `^5.0.11`，会困惑"文档说 5.4 但代码写 5.0"。实际因 caret 语义，实装确实是 5.4.x，文档不算错，只是"描述口径"与"声明口径"不一致。不阻断使用。
- **根因/分析**：文档作者按 `npm ls` 实装版本写，package.json 写的是下限。属口径选择问题。
- **修复方向**：统一口径——要么文档写"Vite ^5.0（实装 5.4.x）"，要么 package.json 收紧到 `^5.4.0`。建议前者（改动面：小）。
- **关联**：[[F07-未编号]] 前端构建与依赖主模块

### [P3] [Bug] `docs/README.md` 文档索引日期停留在 2026-06-03，但项目文档（README/trial-roadmap/deploy-README）已更新到 06-18   <!-- 编号：X05-06 -->
- **定位**：
  - `docs/README.md:3`（"更新时间：2026-06-03"）、`docs/README.md:44`（"截至 2026-06-03，项目可以进入初步试用上线阶段"）。
  - 反证：`README.md:8`（"最后复核日期：2026-06-18"）、`docs/trial-release-roadmap.md:5`（"日期：2026-06-18"）、`deploy/README.md:4`（"最后复核：2026-06-18"）。
- **现象**：docs/README.md 作为文档索引页，自报更新日期 06-03，但被它索引的多份核心文档（README/trial-roadmap/deploy-README）已更新到 06-18。索引页日期落后于被索引文档 15 天。
- **影响**：轻微。读者看索引页"06-03"会以为整个 docs/ 目录都是 06-03 的旧内容，可能跳过读最新文档。不影响功能，但削弱索引页的"导航可信度"。
- **根因/分析**：索引页未随被索引文档同步更新头部日期。
- **修复方向**：docs/README.md 头部日期改为最近一次被索引文档的更新日期（06-18 或更新），或在索引页注明"各文档日期以文档自身头部为准"（改动面：小）。
- **关联**：无

### [P4] [Bug] `docs/digest-system.md` 描述的"轻闭环"与 `trial-release-roadmap.md` 的"Beta-2 强反馈"路线在措辞上有时间差，读者易混淆当前状态   <!-- 编号：X05-06b -->
- **定位**：
  - `docs/digest-system.md:11`（"当前属于 **轻闭环**：系统已经能识别和记录问题，后续重点是把建议变成更强的采集约束"）、`docs/digest-system.md:110-114`（"后续增强：把最终弱点转成下一轮强约束"）。
  - `docs/trial-release-roadmap.md:126-140`（"Beta-2：自动优化强反馈"，验收"连续两次日报中，同类弱点不应重复出现而无策略变化"）。
  - 反证：`docs/mvp-beta-2-release-checklist.md:82`（"确认 skip/deprioritize/boost actions 会进入下一轮采集策略"——暗示强反馈已部分落地）。
- **现象**：digest-system.md（06-03）说优化是"轻闭环、后续才做强约束"，trial-roadmap（06-18）把"强反馈"列为 Beta-2 目标（未明确是否已完成），mvp-beta-2-checklist（06-11）又写得像已可用。三份文档对"自动优化强闭环当前到底做到哪一步"的口径不一致。
- **影响**：轻微。读者无法判断"structured action / 强约束"是已实现、Beta-2 在做、还是未来计划。故障场景：管理员期待"弱点自动转约束"，实际可能仍是轻反馈，体验落差。归 C06/C07 主模块判定实际进度，本模块只记录"文档口径不统一"。
- **根因/分析**：自动优化是渐进增强的功能，文档随版本迭代但旧描述未同步刷新。
- **修复方向**：在 digest-system.md 增加状态标注（如"截至 06-18，强反馈部分已落地，详见 trial-roadmap Beta-2"），统一三份文档的时态（改动面：小）。
- **关联**：[[C06-未编号]] / [[C07-未编号]]

---

## `[Security]` 安全漏洞

> 排查范围：文档是否泄露敏感信息（密钥、内网地址、真实 token）、是否教做了不安全的操作、是否遗漏安全约束说明。逐份文档检查"密钥/密码/token/内网 URL/权限提示"。

未发现文档直接泄露生产密钥或 token 的情形。`.env.example` 中的 key 均为占位符（`your-*`、`sk-your-client-key`、`sk-xxx`），文档示例同此口径，未发现硬编码真实凭据。

但有一处**安全相关文档缺口**值得记录（非漏洞，属文档缺失）：

### [P3] [Security] 文档缺少"默认弱口令 admin123"的显式上线警告   <!-- 编号：X05-07 -->
- **定位**：
  - 文档侧：`README.md:151-167`（上线前必填配置，列了 DB_PASSWORD/CRAWLER_API_KEY 等，但未提"默认 admin 密码必须改"）、`deploy/README.md:155-173`（上线检查清单，无"修改默认管理员密码"项）、`docs/mvp-beta-2-release-checklist.md`（同样无此项）。
  - 代码反证：`deploy/db/init-scripts/schema.sql` 种子 admin 密码为弱口令（已知全局结论 `admin123`，归 X02/B06 深查）；`docs/audit/full-project-risk-register.md` 已将"默认弱口令"列为 P1 风险（"schema.sql 种子 admin 密码 admin123，check-deploy-env 未覆盖"）。
- **现象**：上线检查清单文档列了 13+ 项必填配置（密钥、CORS、cookie 等），但唯独没列"修改默认 admin 登录密码"。risk-register 已知这是 P1 风险且 check-deploy-env.ps1 未覆盖，但面向运维的 deploy/README 和 mvp-beta-2-checklist 都没把这条写进上线必做项。
- **影响**：中低。运维照文档跑完所有检查项以为安全，实际 admin 弱口令仍在。需配合"忘改密码"才触发，不到 P1，但文档缺口放大了风险（运维无提醒）。注意：这本身是 X02/B06 的安全问题，本模块只记"文档未提示"这一面。
- **根因/分析**：上线清单聚焦 env 变量，忽略了"数据库种子里的默认账号"这类非 env 凭据。
- **修复方向**：在 deploy/README.md 上线检查清单和 mvp-beta-2-release-checklist.md 增加"已修改默认 admin 密码（非 admin123）"条目（改动面：小）。
- **关联**：[[X02-未编号]] / [[B06-未编号]] 默认弱口令主模块 / 次维度 `[Design]`（可运维性）

---

## `[Arch]` 架构与技术债

> 排查范围：文档作为"架构叙事"是否与代码实际架构一致——分层描述、模块边界、数据流图、表归属是否如实。注意 schema 漂移按 §8.6 归 B15，本模块只看"文档叙事 vs 代码架构"。

### [P3] [Arch] 多份文档的架构图把 "Backend --> AI" 画成已建立的数据流，但后端 AI 链路是 NoOp 空壳   <!-- 编号：X05-08 -->
- **定位**：
  - 文档侧架构图：
    - `README.md:48-59`（mermaid 图含 `Backend --> ...` 未直连 AI，但 `Crawler --> AI`；描述尚算克制）
    - `AGENTS.md:78-90`（mermaid 图明确画 `Backend --> AI["OpenAI-compatible AI"]` 与 `Crawler --> AI`，两条线并列）
    - `CLAUDE.md` 项目记忆架构图（`Backend --> AI`、`Crawler --> AI`）
  - 代码反证（已知全局结论，归 B13）：backend `infrastructure/ai/NoOpAiService` 是空实现，`AiService` 端口存在但无真实 provider，`ArticleEventHandler` 的标签/向量处理无落地，`article_vector` 表存在但无人写入。
- **现象**：AGENTS.md 和 CLAUDE.md 的架构图把 Backend→AI 画成与 Crawler→AI 并列的有效数据流，暗示后端直接调用 AI。实际后端 AI 是空壳，所有真实 AI 调用都在 crawler 侧。
- **影响**：中低。读者照架构图理解"后端会调 AI"，做集成或排障时会找错方向（去后端查 AI 调用日志，实际根本没有）。README 的图相对克制（只画 Crawler→AI），但 AGENTS/CLAUDE 的图更误导。
- **根因/分析**：架构图按"设计意图"而非"当前实现"画。后端 AI 端口/表/事件是预留骨架，文档却画成了活跃链路。归 B13 主模块判定空壳范围，本模块记"图与实不符"。
- **修复方向**：在 AGENTS/CLAUDE 架构图给 `Backend --> AI` 线加标注（如"(预留/NoOp)"），或在图下补一句"当前 AI 调用仅在 crawler 侧生效，backend AI 为预留骨架"（改动面：小）。
- **关联**：[[B13-未编号]] AI 空壳链路主模块 / 横向主题"AI 空壳链路"

### [P3] [Arch] 文档未记载 `data.sql` 的存在与职责，与 init.sql/schema.sql 形成"文档可见的 schema 三轨"之外的隐式第四轨   <!-- 编号：X05-09 -->
- **定位**：
  - 文档侧：`docs/config-db-migration-plan.md`、`deploy/db/README.md`、`docs/README.md` 提到 schema 演进时只讨论 init.sql（Docker 首次初始化）+ Flyway migration（未集成），未提及 `data.sql`。
  - 代码反证：`backend/src/main/resources/data.sql` 存在（`find . -name data.sql` 命中 `./backend/src/main/resources/data.sql` 及 `./backend/target/classes/data.sql` 编译产物）。
- **现象**：项目里存在 `backend/src/main/resources/data.sql`（种子数据脚本），但所有文档讨论 schema/数据初始化时都未提及它。已知 schema 是三轨（init.sql / migration / schema.sql），data.sql 是这三轨之外的"种子数据"文件，文档完全沉默。
- **影响**：低。读者不知道 data.sql 何时被执行（是 Spring Boot 自动执行？还是手动？）、与 sys_config 种子什么关系、与 schema.sql 的种子数据是否重复。增加数据初始化排查的盲区。注意：data.sql 是否真被 Spring Boot 加载执行需进一步确认（Spring Boot 默认会对 `spring.sql.init.mode=always` 或 embedded DB 执行 classpath:data.sql，但 PostgreSQL + 生产模式通常不执行）——这归 B15 深查。本模块只记"文档没说有这个文件"。
- **根因/分析**：data.sql 可能是早期遗留或 Spring Boot 默认约定文件，文档从未纳入叙事。
- **修复方向**：与 B15 协同确认 data.sql 的实际加载行为后，在 deploy/db/README.md 或 config-db-migration-plan.md 补一段说明其职责与是否生效（改动面：小，但依赖 B15 结论）。
- **关联**：[[B15-未编号]] / 横向主题"schema 漂移" / `[需查证]` 见模块小结

### [P4] [Arch] 文档普遍缺少"故障恢复 / 运维 Runbook"专题，可运维性叙事偏弱   <!-- 编号：X05-10 -->
- **定位**：
  - 现有运维相关内容散落：`deploy/README.md:111-117`（健康检查 curl）、`deploy/README.md:126-152`（日报 smoke）、`docs/mvp-beta-2-release-checklist.md:86-97`（回滚方式，仅 4 行）。
  - 缺失：无独立的"故障恢复 Runbook"——日报生成失败如何排查（AI/搜索/源站/配置/回调五类原因的定位步骤）、callback 失败如何补、crawler SQLite 损坏如何恢复、配置改错如何回滚 sys_config，这些场景在文档里只有零散提示。
- **现象**：trial-release-roadmap.md 的 Beta-4 阶段（运维与观测）明确把"管理员能在 3 分钟内判断失败原因"列为验收标准，但当前文档没有支撑这一目标的 Runbook。回滚章节只有"保留上一版镜像 + stop 容器"4 行，无数据库回滚、配置回滚、日报数据修复步骤。
- **影响**：低（设计建议层面）。试用期真实出故障时，运维只能翻代码或问 AI，文档帮不上忙。不阻断 MVP，但与项目"降低试用期排查成本"的优先级（CLAUDE.md §当前优先级第 5 条）不符。
- **根因/分析**：MVP 阶段优先功能，运维文档滞后。
- **修复方向**：新增 `docs/ops-runbook.md`，覆盖日报失败排查、callback 补偿、数据回滚、配置回滚四类场景（改动面：中）。
- **关联**：次维度 `[Design]`（可运维性）

---

## `[Deps]` 依赖升级与版本

### 本模块依赖清单（基于声明文件，未翻依赖源码）

本模块排查对象是"文档"，依赖清单指**文档中声明的技术栈版本**与代码声明文件（pom.xml / package.json / requirements.txt）的对照：

| 依赖 | 文档声明版本 | 代码声明版本 | 一致性 | 备注 |
|---|---|---|---|---|
| Spring Boot | 3.3.5 | `backend/pom.xml` parent 3.3.5 | ✅ | |
| Java | 21 | `backend/pom.xml` java.version 21 | ✅ | |
| MyBatis Plus | 3.5.9 | `backend/pom.xml` mybatis-plus.version 3.5.9 | ✅ | |
| Sa-Token | 1.44.0 | `backend/pom.xml` sa-token.version 1.44.0 | ✅ | |
| Knife4j | 4.4.0 | `backend/pom.xml` knife4j.version 4.4.0 | ✅ | |
| PostgreSQL | 15+ | Dockerfile 镜像（pgvector-zhparser 自建） | ✅ | 文档无具体小版本，合理 |
| Redis | 7+ | `deploy/docker-compose.yml` `redis:7-alpine` | ✅ | |
| Python | 3.10+ | `crawler-service/Dockerfile` 用 `playwright/python:v1.59.0-jammy`（内含 Python，版本未显式声明） | ⚠️ | [需查证] 镜像实际 Python 版本 |
| FastAPI | 0.100+（README）/ 0.109+（无文档明确） | `requirements.txt` `>=0.109.0` | ⚠️ | README 下限偏低但不误导 |
| Crawl4AI | 0.8.x | `requirements.txt` `~=0.8.6` | ✅ | |
| Vue | 3.4 | `package.json` `^3.4.15` | ✅ | |
| Vite | 5.4 | `package.json` `^5.0.11`（实装 5.4.21） | ⚠️ | 见 X05-05 |
| TypeScript | 5.3 | `package.json` `~5.3.3` | ✅ | |
| Element Plus | 2.5 | `package.json` `^2.5.1` | ✅ | |
| Pinia | 2 | `package.json` `^2.1.7` | ✅ | |
| Tailwind CSS | 3.4 | `package.json` `^3.4.1` | ✅ | |
| md-editor-v3 | 4.11 | `package.json` `^4.11.0` | ✅ | |
| Flyway | 文档暗示在用 | pom.xml **无** flyway 依赖 | ❌ | 见 X05-02 / X05-03 |

> 排查范围：覆盖 README/AGENTS/CLAUDE/deploy-README/crawler-README/frontend-README/docs 全部技术栈表与 pom.xml/package.json/requirements.txt/docker-compose 声明。除上表 ⚠️/❌ 项外，其余一致。未发现文档声明但代码不存在的依赖，或代码有但文档完全没提的核心依赖（data.sql 非依赖，见 X05-09）。

---

## `[Design]` 功能设计合理性

> 从"文档作为上手依据与运维依据是否可靠"角度审视。回答计划 §2.5 中相关的问题。

**审视结论**：

1. **场景适配（单人维护博客 + 工作日 AI 日报）**：文档体量与单人 MVP 匹配——README 简洁给出启动/验证/上线清单，docs/ 按主题拆分（roadmap/digest-system/web-collector/config-migration），没有过度文档化。但文档"分散性"偏高：同一事实（测试基线、AI_MODEL、优化闭环状态）在 6+ 份文档重复陈述且不同步，对单人维护者反而是负担（改一处要改六处）。文档体系本身需要"单一事实源"重构。

2. **可运维性**：文档对"正常路径"覆盖好（启动、健康检查、smoke），对"异常路径"覆盖弱（故障排查、数据回滚、配置回滚、callback 补偿）。trial-roadmap 自己都把 Beta-4 运维观测列为未来目标，说明项目自知运维文档不足。对 MVP 试用，当前文档能让系统跑起来，但出问题时帮不上忙。

3. **MVP 假设检验**：文档声称的"可试用"能力（文章/日报/采集/优化）与代码实际基本相符，但有两处"看起来能用实则虚"：①Flyway migration（文档/规范说在用，实际未集成）；②Backend→AI（架构图画成活跃链路，实际 NoOp）。这两处不是"功能 bug"而是"文档夸大"，会误导依赖文档做决策的人。

### [P4] [Design] 文档体系缺少"单一事实源"，导致基线数字/口径多处漂移   <!-- 编号：X05-11 -->
- **定位**：全文档体系（6+ 份文档重复陈述测试基线、AI_MODEL、优化状态）。
- **现象**：见 X05-01（测试数字三套）、X05-04（AI_MODEL 文档 vs env）、X05-06b（优化闭环状态三处口径）。根因是文档无单一事实源，每份文档各自维护副本。
- **影响**：单人维护者改一次事实要同步 6+ 处，极易漏改（当前已漏）。读者看到不同文档写不同数字，信任度下降。
- **建议方向**：建立 `docs/_baseline.md`（或类似）作为唯一事实源（测试数字、版本、AI_MODEL、功能状态），其余文档只链接、不复制（改动面：中）。
- **关联**：归并 X05-01/X05-04 的根因

---

## 模块小结

### 严重度统计

| 级别 | 数量 | 条目编号 |
|---|---|---|
| P0 | 0 | — |
| P1 | 0 | — |
| P2 | 3 | X05-01、X05-02、X05-03 |
| P3 | 6 | X05-04、X05-05、X05-06、X05-07、X05-08、X05-09 |
| P4 | 3 | X05-06b、X05-10、X05-11 |

合计 12 条发现。

### Top 风险（本模块最该先看的 ≤3 条）

1. **X05-02 / X05-03 init.sql 头部 + deploy/db/README 通篇误导性 Flyway 叙事** —— 这是"文档撒谎"级别：不仅过时，而是"从未成立却写得像既定事实"。直接影响 schema 演进操作正确性，是本模块最该优先修正的文档问题。修复面小（改注释/改文档），但背后 Flyway 路线决策归 B15。
2. **X05-01 测试基线数字三套口径且偏离实际** —— 影响面最广（6 份文档），让任何照文档复核的人都会困惑。根因是缺单一事实源（X05-11），治本需重构文档体系。
3. **X05-07 上线检查清单缺"改默认 admin 密码"** —— 唯一带安全后果的文档缺口，虽属 P3（需忘改才触发），但与 risk-register 已记录的 P1 弱口令风险直接相关，文档侧补一句成本极低。

### 修复优先级建议

- **立即**（P0/P1）：无。本模块无阻断或高危发现。
- **计划**（P2）：
  - X05-02：删 init.sql 头部 "Flyway 版本: V1.0.0" 误导注释（改动面小，可立即做，不等 B15）。
  - X05-03：deploy/db/README.md + AGENTS.md 如实修正 Flyway 叙事（改动面中，与 B15 协同）。
  - X05-01：测试基线数字去硬编码，改为"以实际输出为准 + 链接单一源"（改动面中，配合 X05-11）。
- **择机**（P3/P4）：
  - X05-04（AI_MODEL 文档 vs env，归属 X06 统一裁决）。
  - X05-05（Vite 版本口径）、X05-06（docs/README 日期）、X05-06b（优化闭环措辞）—— 批量刷新即可。
  - X05-07（上线清单补改密码项）—— 顺手做。
  - X05-08（架构图标注 NoOp）、X05-09（data.sql 文档补述，依赖 B15）—— 与 B13/B15 协同。
  - X05-10（运维 Runbook）、X05-11（单一事实源）—— 中长期改进。

### 排查盲区 / 待复核

- **[需查证-1]** `crawler-service/Dockerfile` 使用 `mcr.microsoft.com/playwright/python:v1.59.0-jammy` 镜像，文档声称 "Python 3.10+"。该镜像实际内置的 Python 版本未在本审计中确认（不深入镜像层）。若镜像 Python < 3.10，则文档与实际不符；若 ≥ 3.10 则一致。需 `docker run ... python --version` 验证（超出本模块只读命令边界）。
- **[需查证-2]** `backend/src/main/resources/data.sql` 是否被 Spring Boot 自动加载执行（`spring.sql.init.mode` 配置）未在本审计确认。若执行，则它是 schema 三轨之外的"第四轨"种子数据，文档完全未记载；若不执行，则是死文件。归 B15 主模块确认。本模块的 X05-09 依赖此结论。
- **[需查证-3]** 文档（digest-system.md:64-66）描述的任务状态机 `PENDING(0)->CRAWLING(1)->PROCESSING(2)->COMPLETED(3)/FAILED(4)` 与 crawler README:166-174 的 5 态表文字一致，但未与 `standalone/db.py` 的状态常量定义逐一核对（归 C09）。本模块只确认"两份文档互相一致"，不确认"文档与代码常量一致"。
- **文档总数统计口径**：本审计统计项目文档 32 份（排除 node_modules/.git/.pytest_cache/artifacts/module-audit 自身）。其中 `.claude/commands/*.md`（3 份 slash command 说明）未深查，因属工具配置非项目文档；`docs/superpowers/plans/*.md`（2 份计划文档）仅 grep 未深查；`docs/Crawl4AI/*.md`（4 份外部参考资料）按 docs/README.md 声明"外部参考，不代表项目状态"未深查。漂移判定仅基于已深查的 ~20 份核心文档。

### 文档清单 + 时效性判定（汇总表）

| 文档 | 主题 | 最后日期 | 与代码一致性 | 主要问题 |
|---|---|---|---|---|
| `README.md` | 项目总览 | 2026-06-18 | ⚠️ 部分 | 测试数字 88/1366 偏离实际 111/1376（X05-01）；Vite 5.4 口径（X05-05） |
| `CLAUDE.md`（项目级） | Agent 规范+状态 | 2026-06-03 | ⚠️ 部分 | 测试数字 75/1266 严重过时（X05-01）；架构图 Backend→AI 误导（X05-08） |
| `AGENTS.md` | Agent 协作规范 | 2026-06-03 | ⚠️ 部分 | 测试数字 75/1266（X05-01）；开发规范"用 Flyway"误导（X05-03）；架构图（X05-08） |
| `docs/README.md` | 文档索引 | 2026-06-03 | ⚠️ 部分 | 索引日期落后于被索引文档（X05-06） |
| `docs/trial-release-roadmap.md` | 试用路线图 | 2026-06-18 | ⚠️ 部分 | 测试数字 88/1366（X05-01）；AI_MODEL deepseek-v4-pro（X05-04） |
| `docs/digest-system.md` | 日报/优化系统 | 2026-06-03 | ✅ 大致 | 优化闭环措辞与其他文档有时差（X05-06b）；路径引用正确 |
| `docs/config-db-migration-plan.md` | 配置/迁移 | 2026-06-03 | ⚠️ 部分 | migration 列表只到 V1_22，未含 V1_23（实际已有，轻微）；未提 data.sql（X05-09） |
| `docs/web-collector-module-design.md` | WebCollector 设计 | 2026-06-03 | ✅ | 未发现明显漂移 |
| `docs/future-development-plan.md` | 未来计划 | 2026-06-03 | ✅ | 计划文档，无硬事实可漂移 |
| `docs/plan-crawl-tools-refactor.md` | 重构参考 | 2026-05-24/06-03 | ✅ | 参考性文档 |
| `docs/mvp-beta-2-release-checklist.md` | 发布清单 | 2026-06-11 | ⚠️ 部分 | 缺"改默认 admin 密码"项（X05-07）；优化闭环措辞（X05-06b） |
| `deploy/README.md`（已改） | 部署说明 | 2026-06-18 | ⚠️ 部分 | AI_MODEL（X05-04）；缺改密码项（X05-07） |
| `deploy/db/README.md` | 数据库说明 | 2026-06-03 | ❌ 误导 | 通篇教用 Flyway 但未集成（X05-03）；教查不存在的 flyway_schema_history |
| `crawler-service/README.md` | Crawler 说明 | 2026-06-03 | ⚠️ 部分 | 测试数字 1266（X05-01）；AI_MODEL（X05-04） |
| `crawler-service/docs/architecture-v3.md` | Crawler 架构 | 2026-06-03 | ✅ | 未深查全文，头部无漂移 |
| `crawler-service/docs/daily-digest-review.md` | 日报质量评审 | 2026-06-03 | ⚠️ 部分 | 测试数字 1266/75（X05-01） |
| `frontend/README.md` | 前端说明 | 2026-06-03 | ⚠️ 轻微 | Vite 5.4 口径（X05-05） |
| `backend/.../db/init.sql`（头部） | 初始化脚本 | 2026-04-06 | ❌ 误导 | 头部自称 "Flyway 版本: V1.0.0" 但与 Flyway 无关（X05-02） |
| `docs/audit/full-project-risk-register.md`（已改） | 风险登记册 | 2026-06-22 | ✅ | 审计文档，记录的 P0/P1 状态与代码修复一致 |

**文档总数**：~20 份核心文档深查（项目文档合计 32 份，含未深查的外部参考/superpowers plans/.claude commands）。
**漂移/误导文档数**：**13 份**存在不同程度漂移或误导（⚠️ 或 ❌），其中 **2 份属"误导"级别**（deploy/db/README.md、init.sql 头部——把未集成的 Flyway 写成在用），其余为数字过时或口径不统一。
**完全一致**：7 份。
