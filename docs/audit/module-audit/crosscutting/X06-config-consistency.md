# X06 配置一致性 排查报告

> **模块编号**：X06
> **排查范围**：env 三处（deploy/crawler-service/frontend）、sys_config 种子（init.sql/schema.sql/migration/SystemConfigInitializer）、AI_MODEL 等同名项值差异、敏感项默认值与拦截、crawler↔backend 配置 key 命名一致性
> **基线 commit**：`6ae930098405f4d0553d96a852f3345d0f39682e`
> **工作区状态**：脏。涉及本模块视角的未提交改动：`backend/.../ConfigRepositoryImpl.java`（配置读取实现）、`scripts/release/release-gate.ps1`、`deploy/README.md`。其余脏文件（crawler/search.py、knowledge_base.py、tests、WebCollectPageMapper）与配置一致性无直接关系。
> **排查日期**：2026-06-23
> **排查人**：X06 排查 agent
> **状态**：草稿

---

## 模块概览

**职责**：保证"同一配置项"在 env 文件（deploy/crawler-service/frontend）、sys_config DB 种子（init.sql/schema.sql/migration）、运行时初始化器（SystemConfigInitializer）、跨服务下发（backend→crawler config 拉取）四处有**一致且自洽**的值与命名，使运维按 `.env.example` 部署、admin 在管理页改值、crawler 拉取 backend 配置三条路径都得到预期行为。

**关键文件**：
- `deploy/.env.example` —— 部署 env 模板（backend + crawler 共用）
- `crawler-service/.env.example` —— crawler 独立服务 env 模板
- `frontend/.env.example` —— 前端 env 模板（仅 3 项，与其他无重叠）
- `backend/src/main/resources/db/init.sql:966-1120` —— sys_config 种子（Java 侧 init 脚本）
- `deploy/db/init-scripts/schema.sql:923-1093` —— sys_config 种子（**docker-compose 部署实际用这份**）
- `backend/.../migration/V1_12..V1_23__*.sql` —— Flyway 迁移档案（**未集成**，仅作历史漂移参考）
- `backend/.../config/initializer/SystemConfigInitializer.java:31-56` —— 运行时从 env 补 9 项 sys_config
- `crawler-service/standalone/backend_config.py:82-289` —— crawler 拉取并应用 backend 配置（期望约 52 个 key）
- `backend/.../interfaces/rest/InternalCallbackController.java:140-160` —— `/api/internal/collector/config` 下发，`crawler.` 前缀剥离点
- `backend/.../interfaces/rest/ConfigController.java:99-113` —— admin 改配置后双端刷新编排
- `scripts/release/check-deploy-env.ps1` —— 部署前敏感项/占位符拦截
- `deploy/docker-compose.yml:57-120` —— 容器 env 注入与 `${VAR:?}` 强制非空
- `backend/src/main/resources/application-prod.yml` —— Spring 侧 env → 配置绑定
- `crawler-service/config.py:7-230` —— Pydantic 默认值（crawler fallback 层）

**对外接口 / 依赖**：
- 对外：无直接对外接口；本模块是"配置作为部署/运维依据"的横切审视。
- 依赖：B07（AES 加密机制，`crawler.ai.api_key`/`crawler.service.api-key` 等加密项）、B15（schema 三轨归属）、B06（COOKIE_SECURE/admin 弱口令）、B09（双向 key 契约）、C11（crawler 配置同步主模块）。

**已读文件清单**：
- `deploy/.env.example` —— 通读
- `crawler-service/.env.example` —— 通读
- `frontend/.env.example` —— 通读
- `backend/src/main/resources/db/init.sql:920-1133` —— 通读 sys_config 段
- `deploy/db/init-scripts/schema.sql:923-1093` —— 通读 sys_config 段 + diff 对照
- `backend/.../config/initializer/SystemConfigInitializer.java` —— 通读
- `crawler-service/standalone/backend_config.py` —— 通读
- `backend/.../interfaces/rest/InternalCallbackController.java:130-200` —— 片段（config 下发）
- `backend/.../interfaces/rest/ConfigController.java` —— 通读
- `scripts/release/check-deploy-env.ps1` —— 通读
- `scripts/release/release-gate.ps1` —— 通读
- `deploy/docker-compose.yml` —— 通读
- `backend/src/main/resources/application-prod.yml` —— 通读
- `crawler-service/config.py:1-230` —— 通读
- migration：`V1_12, V1_13, V1_14, V1_15, V1_20, V1_21, V1_22, V1_23` —— 通读（V1_16/17/18/19 与 sys_config 无关，未读）

**主模块归属**：**X06 是配置一致性主模块，深查**。AES 加密机制归 B07；schema 三轨存在性归 B15；admin 弱口令归 B06/X02；双向 key 强度归 B09。本模块聚焦**配置项的值/命名/来源一致性**。

---

## `[Bug]` 代码正确性与潜在缺陷

> 排查范围：env 三处值对照、sys_config 种子值自洽性、crawler↔backend key 命名映射、配置刷新编排时序、运行时初始化器 seed 逻辑。

### [P1] [Bug] AI_MODEL 三轨不一致：deepseek-v4-pro 是无效/可疑模型名，且 model 与 base_url/default_value 三方错配 <!-- 编号：X06-01 -->

- **定位**：
  - `backend/src/main/resources/db/init.sql:993` —— `('crawler.ai.model', 'deepseek-v4-pro', 'qwen-plus', ...)`
  - `deploy/db/init-scripts/schema.sql:956` —— 同上
  - `backend/.../migration/V1_12__unify_sys_config.sql:91` —— 种子源头 `deepseek-v4-pro`
  - 对照：`deploy/.env.example:17` `AI_MODEL=qwen-plus`、`crawler-service/.env.example:102` `AI_MODEL=qwen-plus`、`crawler-service/config.py:108` `ai_model: str = "qwen-plus"`
- **现象**：
  1. sys_config 种子 `crawler.ai.model` 的 **config_value（生效值）= `deepseek-v4-pro`**，但 **default_value = `qwen-plus`**。生效值与默认值是两个不同厂商的模型。
  2. `crawler.ai.base_url` 的 config_value = `https://api.deepseek.com/v1`（DeepSeek 端点），与 model=deepseek-v4-pro 自洽；但其 **default_value = `''`**（空），与 model 的 default_value=qwen-plus 不自洽（qwen-plus 应配 dashscope 端点）。
  3. env 三处的 AI_MODEL 全是 `qwen-plus`，base_url 全是 `https://dashscope.aliyuncs.com/compatible-mode/v1`（dashscope），与 sys_config 的 deepseek 组合**完全相反**。
  4. `deepseek-v4-pro` 这个模型 ID：DeepSeek 官方 API（api-docs.deepseek.com）列出的模型名是 `deepseek-chat` / `deepseek-reasoner`（2026-07-24 即将弃用）和新版 V3.2；"V4 Pro" 仅见于第三方博客文章，**官方端点是否接受 `deepseek-v4-pro` 作为 model 参数无法确认** `[需查证]`。
- **影响**：
  - **运行时实际生效 model 取决于 crawler 是否拉到 backend 配置**：若 backend 可达，crawler 用 sys_config 的 `deepseek-v4-pro` + deepseek base_url（自洽，但 model 名可能无效导致 AI 调用 400/404）；若 backend 不可达（如 `java_api_url` 为空的本地模式），crawler fallback 到 env/Pydantic 的 `qwen-plus` + dashscope（自洽且可用）。两种部署路径行为不同，且前者可能直接让日报生成失败。
  - admin 在管理页点"恢复默认值"（`ConfigController.resetToDefault`）：model 变回 `qwen-plus`，但 base_url 的 default_value 是空串 → model=qwen-plus 配空 base_url，AI 调用必然失败。这是"恢复默认"反而破坏可用性的设计缺陷。
- **根因/分析**：
  1. 历史上 V1_12 把 AI 配置统一到 `crawler.ai.*` 命名空间时，model 的生效值写成了 deepseek 系（疑似某次切换到 DeepSeek 的遗留），但 default_value 没同步更新，仍保留旧的 qwen-plus。
  2. env 模板（.env.example）与 sys_config 种子由不同的人/不同时间维护，缺乏单一事实源。
  3. README 多处（`README.md:91`、`deploy/README.md:81`、`docs/trial-release-roadmap.md:80`、`crawler-service/README.md:232`）声明"试用环境使用 `deepseek-v4-pro`"，与 env 模板的 qwen-plus 矛盾，说明文档也分裂。
- **修复方向**：
  1. 选定单一事实源：要么"deepseek 系"要么"qwen 系"，全栈统一（env + sys_config + default_value + README）。（改动面 中）
  2. 若选 deepseek，核实 `deepseek-v4-pro` 是否为官方有效 model ID；若无效改为 `deepseek-chat` 等官方名，并把 default_value 与 config_value 设成相同值。（改动面 小）
  3. 让 `crawler.ai.base_url` 的 default_value 与 model 的 default_value 配套（要么都 dashscope+qwen-plus，要么都 deepseek+deepseek-chat）。（改动面 小）
- **关联**：[[B13 AI 空壳链路]] / [[C05 AI 整理]] / 横向主题"配置一致性" / 配置项 `crawler.ai.model`、`crawler.ai.base_url`、`AI_MODEL` / 计划 §9 已知线索

### [P2] [Bug] sys_config 种子 init.sql 与 schema.sql 存在 8 项配置项差异，docker 部署会少一批 crawler 期望的 key <!-- 编号：X06-02 -->

- **定位**：
  - `backend/src/main/resources/db/init.sql` 有、`deploy/db/init-scripts/schema.sql` 没有的配置项（diff 实测）：
    1. `crawler.ai.digest_per_max_chars` = 8000
    2. `crawler.ai.digest_total_budget` = 100000
    3. `crawler.ai.digest_max_tokens` = 10000
    4. `crawler.digest.parallel_sections` = 2
    5. `crawler.digest.global_timeout` = 600
    6. `crawler.dependency_mode` = degraded（**有运行时兜底**，见 X06-04）
    7. `crawler.optimization.breadth_max_rounds` = 3
    8. `crawler.digest.optimization_min_results_per_section` = 3
  - docker-compose 实际挂载的是 `deploy/db/init-scripts/`（`deploy/docker-compose.yml:19` `./db/init-scripts:/docker-entrypoint-initdb.d`），所以 **compose 部署用的是 schema.sql**，这 8 项不存在。
- **现象**：同一份"sys_config 种子"在 init.sql 与 schema.sql 间漂移 8 项。crawler `backend_config.py` 会 `get()` 这些 key（如 `ai.digest_max_tokens` line 102、`digest.global_timeout` line 122、`optimization.breadth_max_rounds` line 174），拿不到就 fallback Pydantic 默认值。
- **影响**：
  - **两套部署路径的 crawler 行为不同**：
    - compose/schema.sql 部署：`ai.digest_max_tokens` 走 Pydantic 默认 **16000**（`config.py:129`）。
    - 假设有人跑 init.sql 部署：`ai.digest_max_tokens` 走 sys_config 的 **10000**。
    - 日报 AI 输出 token 预算差 60%，可能影响日报是否被截断。
  - 其余几项（global_timeout=600、parallel_sections=2）Pydantic 默认值与 init.sql 恰好一致，巧合不爆雷，但属于"侥幸一致"。
  - admin 在管理页看不到这些项（schema.sql 部署下根本没入库），无法调整。
- **根因/分析**：schema 双轨（init.sql 与 schema.sql）长期手工维护，V1_15 新增的 6 项 + V1_13/V1_22 后续追加项只更新了 init.sql，没回写 schema.sql。这是 B15 主模块的 schema 漂移在配置维度的具体体现。
- **修复方向**：让 schema.sql 与 init.sql 的 sys_config 种子段完全对齐（或统一单一来源，生成另一份）。（改动面 中，归属 B15）
- **关联**：[[B15-_schema-三轨漂移]] / [[C11 配置同步]] / 横向主题"schema 漂移"与"配置一致性"交集

### [P3] [Bug] crawler backend_config.py 期望约 10 个 key 在 sys_config 种子完全不存在，只能靠 Pydantic fallback <!-- 编号：X06-03 -->

- **定位**：
  - `crawler-service/standalone/backend_config.py:90-97` 期望 `ai.section_cleanup_timeout / per_max_chars / total_budget / max_output_chars`（4 项）
  - `backend_config.py:138-142` 期望 `digest.publish_core_sections / publish_min_core_sections`（2 项）
  - `backend_config.py:176-188` 期望 `optimization.total_budget_seconds / depth_target_score / breadth_target_score`（3 项）
  - 全 SQL grep `section_cleanup|publish_core_sections|total_budget_seconds|depth_target_score|breadth_target_score` → **0 命中**（init.sql/schema.sql/migration 都没有）。
- **现象**：crawler 拉取 backend 配置时，这些 key 永远不在响应里（因为 sys_config 没有），`if config.get(key, "")` 跳过，crawler 用 Pydantic 默认值。
- **影响**：
  - 功能上能跑（有 fallback），但 admin 无法通过管理页调整这些参数，它们对 admin 完全不可见。
  - 这是 V1_21 注释所说的有意设计（"Python config.py 默认值作为 fallback 仍然生效"），但 crawler 代码里仍写了 `get()` 调用，形成"代码期望 ↔ 数据源"的隐性契约缺口，后续维护者难以判断这些 key 是"待补"还是"故意不暴露"。
- **根因/分析**：crawler 引入了 sys_config 从未声明的新调参（section_cleanup 系列是后来加的栏目清洗逻辑），但没同步补 sys_config 种子，也没在 backend_config.py 里删除对这些 key 的 get。属于跨服务契约的"单向漂移"。
- **修复方向**：二选一——要么把这些 key 补进 sys_config 种子（若 admin 需要管），要么在 backend_config.py 删除对这些 key 的 get 调用并明确注释"仅用 Pydantic 默认"。（改动面 小）
- **关联**：[[B09 跨服务契约]] / [[C11 配置同步]] / 横向主题"跨服务契约一致性"

### [P3] [Bug] SystemConfigInitializer 仅 seed 9 项，大量 sys_config 项依赖 SQL 种子；首次启动若 SQL 种子缺项则永久缺 <!-- 编号：X06-04 -->

- **定位**：`backend/.../config/initializer/SystemConfigInitializer.java:34-51` 只 seed：`crawler.service.base-url / api-key`、`crawler.callback.api-key / url`、`crawler.ai.enabled / api_key / base_url / model`、`crawler.digest.enabled`，外加 `ensureCrawlerDependencyMode()` 补 `crawler.dependency_mode`。
- **现象**：SystemConfigInitializer 是"运行时补配置"的唯一机制，但只覆盖 10 个 key。其余约 40+ 项 crawler 组配置完全靠 SQL 种子（init.sql/schema.sql）。一旦 SQL 种子缺项（见 X06-02 的 8 项差异），运行时不会补，永久缺失。
- **影响**：`crawler.dependency_mode` 有运行时兜底（`ensureCrawlerDependencyMode`），所以即使 schema.sql 没这条（X06-02 第 6 项），backend 启动会补上 ✓。但 X06-02 的其余 7 项（digest_max_tokens 等）没有兜底，compose 部署后永久缺失。
- **根因/分析**：SystemConfigInitializer 的 seed 列表是手工维护的"运维必填项"子集，与 crawler 实际消费的 key 集合脱节。设计上假设"SQL 种子是完整基线"，但 SQL 种子本身三轨漂移（B15）。
- **修复方向**：扩展 SystemConfigInitializer 的 seed 列表覆盖 crawler 必需的全部 key，或建立"SQL 种子 ↔ Initializer seed 列表"的单一来源。（改动面 中）
- **关联**：[[X06-02]] / [[B15]] / [[B07 系统配置]]

---

## `[Security]` 安全漏洞

> 排查范围：敏感默认值（admin 密码、加密 key、API key 占位符）、check-deploy-env 拦截覆盖、`.env.example` 是否泄漏真密钥、`${VAR:?}` 强制非空覆盖。AES 加密机制本身归 B07。

### [P2] [Security] check-deploy-env.ps1 必填项覆盖不完整，DB_PASSWORD / COOKIE_SECURE / CORS 等关键项不检查 <!-- 编号：X06-05 -->

- **定位**：`scripts/release/check-deploy-env.ps1:7-14`
  ```
  $RequiredKeys = @(
      "AI_ENABLED", "DIGEST_ENABLED", "AI_API_KEY",
      "CRAWLER_API_KEY", "CRAWLER_CALLBACK_API_KEY",
      "BLOG_SECURITY_ENCRYPTION_KEY"
  )
  ```
- **现象**：必填项清单只有 6 个。**缺失**：
  - `DB_PASSWORD` —— deploy/.env.example:4 是占位符 `your_secure_database_password`，但 check-deploy-env 不查它（虽然 docker-compose 的 `${DB_PASSWORD:?}` 会拦截，但 check-deploy-env 是发布门禁的"env 体检"层，应该独立覆盖）。
  - `COOKIE_SECURE` —— deploy/.env.example:6 默认 `false`，生产环境应为 true，check-deploy-env 不检查（Cookie 安全属性归 B06，但 env 检查是 X06 的部署门禁视角）。
  - `CORS_ALLOWED_ORIGINS` —— 默认 `https://nanmu.xyz,http://nanmu.xyz`，check-deploy-env 不验证是否被改成危险的 `*`。
  - `CRAWLER_CALLBACK_URL` / `JAVA_API_URL` —— 不检查。
  - `CRAWLER_SERVICE_URL` —— 不在 .env.example 里（见 X06-08），也不在检查清单。
- **影响**：发布门禁对 env 的安全体检有盲区。运维若误填或漏填这些项，check-deploy-env 不会报错，docker-compose 的 `:?` 只能拦截"空"，不能拦截"占位符"或"危险值"（如 CORS=*、COOKIE_SECURE=false）。
- **根因/分析**：RequiredKeys 只列了"AI/日报链路必填"，没覆盖"部署安全基线"。check-deploy-env 的定位（line 46-51）偏窄，只验证 AI_ENABLED/DIGEST_ENABLED=true 和加密 key 长度。
- **修复方向**：
  1. 扩充 RequiredKeys 覆盖 DB_PASSWORD、CORS_ALLOWED_ORIGINS。（改动面 小）
  2. 增加"危险值"断言：COOKIE_SECURE 在生产必须 true、CORS_ALLOWED_ORIGINS 不能含 `*`。（改动面 小）
- **关联**：[[B06-cookie-csrf]] / [[B16-cors]] / [[X04 发布脚本]] / 计划 §9 已知线索"check-deploy-env 未覆盖 admin123"

### [P3] [Security] BLOG_SECURITY_ENCRYPTION_KEY 占位符恰好 ≥16 字符，长度检查单层防御不足；所幸占位符正则兜底 <!-- 编号：X06-06 -->

- **定位**：`deploy/.env.example:5` `BLOG_SECURITY_ENCRYPTION_KEY=your_16_plus_char_encryption_key`；`check-deploy-env.ps1:52-54` 仅检查 `Length -lt 16`；`check-deploy-env.ps1:36` 占位符正则 `^(your_|sk-your-|nanmuli-blog-key$)`。
- **现象**：占位符值 `your_16_plus_char_encryption_key` 长度 31（≥16），单看 line 52-54 的长度检查会通过。但 line 36 的占位符正则里有 `your_` 分支，该值以 `your_` 开头，会被拦截 ✓。
- **影响**：当前是双层防御，未泄漏。但若未来有人把占位符改成不以 `your_` 开头但仍是弱值（如 `1234567890abcdef`），line 52-54 的长度检查会放行。属于"防御纵深不足"的潜在风险。
- **根因/分析**：占位符黑名单是枚举式，无法覆盖所有弱值形态。AES 密钥强度的真正校验应在 AesEncryptor 拒绝弱密钥（归 B07）。
- **修复方向**：在 AesEncryptor 初始化时拒绝已知弱密钥/熵不足的密钥（归 B07）；check-deploy-env 增加密钥熵/字符多样性检查。（改动面 中，主改动在 B07）
- **关联**：[[B07-aes-加密]] / [[B07-加密密钥强度]]

### [P3] [Security] .env.example 未泄漏真实密钥，占位符设计合理 <!-- 编号：X06-07 -->

- **定位**：`deploy/.env.example` 全文 + `crawler-service/.env.example` 全文。
- **现象**：逐项核对，所有敏感项均为占位符（`your_*` / `sk-your-*` / 空），无真实密钥、无真实 token、无真实域名凭据。
- **影响**：无安全风险。
- **根因/分析**：.env.example 的占位符设计是合规的。
- **修复方向**：无需调整。
- **关联**：无

---

## `[Arch]` 架构与技术债

> 排查范围：配置三轨（env/SQL 种子/migration）漂移、crawler↔backend 配置 key 命名映射机制、配置刷新编排时序、单一事实源缺失。

### [P2] [Arch] 配置值在 migration V1_13..V1_23 间反向漂移，V1_21 删除的 key 仍被 crawler 消费 <!-- 编号：X06-08 -->

- **定位**：
  - `V1_20__fix_config_defaults_and_add_missing.sql:7-9` 把 `crawler.digest.search_engine` 改为 `sogou`，把 `crawler.ai.digest_max_tokens` 改为 16000。
  - `V1_21__remove_unnecessary_configs.sql:27` 又把 `crawler.ai.digest_max_tokens` 删了；`V1_21:82-92` 把 `crawler.digest.optimization_*`、`crawler.digest.global_timeout` 等也删了。
  - 但 crawler `backend_config.py:102-103, 122-123, 126-136` 仍消费这些被删的 key。
  - 最终生效值（Flyway 若集成）：V1_21 后这些 key 不存在 → crawler fallback Pydantic 默认。init.sql/schema.sql 种子仍保留这些 key（因为种子不随 migration 变），导致"种子有、migration 删了、crawler 仍要"的三方不一致。
- **现象**：migration 链内部自相矛盾（V1_20 加/改 → V1_21 删），且与 SQL 种子（init.sql/schema.sql 保留）和 crawler 代码（仍 get）都对不齐。
- **影响**：Flyway 一旦集成（B15 修复后），V1_21 会删掉这批 key，crawler 立刻拿不到（目前 Flyway 未集成，种子在，crawler 能拿到，是"Flyway 没集成"在掩盖契约破裂）。这是未来 B15 修复后会爆的雷。
- **根因/分析**：V1_21 的设计意图是"admin 只管 33 项核心，其余走 Pydantic 默认"，但 crawler backend_config.py 的 get 调用没同步精简。migration 与 crawler 代码的演进不同步。
- **修复方向**：明确每个 crawler get 的 key 是否应有 sys_config 后端，把"应删"的从 backend_config.py 移除，把"应留"的补回 V1_21 或在 SystemConfigInitializer 兜底。（改动面 中）
- **关联**：[[B15-flyway-未集成]] / [[X06-02]] / [[C11]] / 横向主题"配置一致性"

### [P3] [Arch] crawler↔backend 配置 key 命名剥离用 `replace("crawler.", "")` 而非前缀去除，潜在误伤 <!-- 编号：X06-09 -->

- **定位**：`backend/.../interfaces/rest/InternalCallbackController.java:150` `c.getConfigKey().replace("crawler.", "")`
- **现象**：用 `String.replace`（全局替换）而非 `removePrefix`。sys_config 的 key 都是 `crawler.xxx` 单层前缀，目前替换结果正确。但若将来出现 `crawler.foo.crawler.bar` 这类 key，会变成 `foo.bar`（错误剥离两层）。
- **影响**：当前所有 key 都是 `crawler.` 开头且内部不含 `crawler.` 子串，无现行 bug。但这是脆性实现，依赖"key 命名永远不含重复前缀子串"的隐性约定。
- **根因/分析**：Java 标准库无 `removePrefix`，用 `replace` 是常见妥协。crawler 侧 `backend_config.py` 用 `key.replace(".", "_")` 做 env fallback（line 334）也有类似约定依赖。
- **修复方向**：改为 `key.startsWith("crawler.") ? key.substring("crawler.".length()) : key` 显式剥离前缀。（改动面 小）
- **关联**：[[B09 跨服务契约]] / 横向主题"跨服务契约一致性"

### [P3] [Arch] CRAWLER_SERVICE_URL 不在 deploy/.env.example，运维无法从模板发现该入口 <!-- 编号：X06-10 -->

- **定位**：
  - `deploy/.env.example` 全文无 `CRAWLER_SERVICE_URL`
  - `deploy/docker-compose.yml:67` `CRAWLER_SERVICE_URL: http://crawler:8500`（硬编码，无 `${}` 引用）
  - `backend/src/main/resources/application-prod.yml:80` `${CRAWLER_SERVICE_URL:http://localhost:8500}`
  - `backend/.../config/initializer/SystemConfigInitializer.java:34` seed `crawler.service.base-url` 从 env `CRAWLER_SERVICE_URL` 读
- **现象**：compose 模式下 backend 用硬编码的 `http://crawler:8500`（容器网络），运维无法通过 .env 覆盖。非 compose 模式（本地 java -jar）则用 application-prod.yml 的 fallback `http://localhost:8500`，或通过环境变量注入。
- **影响**：运维若看 `.env.example` 想调整 crawler 地址（如改为服务器内网 IP），找不到 `CRAWLER_SERVICE_URL` 这个 key，只能去翻 docker-compose.yml/application-prod.yml。可运维性差，且 `config-db-migration-plan.md:33`、`deploy/README.md:74`、`mvp-beta-2-release-checklist.md:21` 都提到这个 key，说明它"应该"是可配置的，但模板漏了。
- **根因/分析**：docker-compose.yml 把它写死而非 `${CRAWLER_SERVICE_URL:-http://crawler:8500}`，.env.example 也漏列。两处疏漏叠加。
- **修复方向**：在 deploy/.env.example 补 `CRAWLER_SERVICE_URL=http://crawler:8500`（带注释说明 compose 内网络名），docker-compose.yml 改为 `${CRAWLER_SERVICE_URL:-http://crawler:8500}` 允许覆盖。（改动面 小）
- **关联**：[[X04 发布脚本]] / [[X01 部署架构]]

---

## `[Deps]` 依赖升级与版本

### 本模块依赖清单（基于声明文件，未翻依赖源码）

本模块是配置一致性审视，不引入第三方依赖。涉及的工具/库仅作为配置载体：

| 依赖 | 版本 | 声明位置 | 已知风险/可升级 | 备注 |
|---|---|---|---|---|
| Pydantic Settings | （crawler requirements） | `crawler-service/config.py` 使用 | 无 | crawler 配置 fallback 层 |
| Spring Environment | Spring Boot 3.3.5 | `SystemConfigInitializer` 使用 `${VAR:default}` | 无 | backend env → sys_config seed |

> 排查范围：本模块无第三方依赖升级问题。未命中。

---

## `[Design]` 功能设计合理性

> 必填。从"配置作为部署/运维依据是否自洽"角度回答计划 §2.5 相关问题。

**审视结论**：

1. **场景适配**（单人维护 + MVP 试用）：当前配置体系"看起来完善（70+ sys_config 项 + env 三处 + 运行时初始化器），实则自洽性差"。X06-01 的 AI_MODEL 三方错配、X06-02 的 8 项种子漂移，意味着运维按 `.env.example` 部署后，实际生效的 crawler 行为与 env 模板的"承诺"不一致（env 写 qwen-plus，crawler 拉到的是 deepseek-v4-pro）。对单人维护者，这种"改了 env 却不生效"的体验会严重拖慢排障——这是过度设计（70+ 配置项）与欠打磨（值不自洽）并存的典型 MVP 病。

2. **闭环完整性**（配置变更→双端刷新）：`ConfigController.refreshAfterConfigChange`（line 99-113）的编排时序是"先用旧 ConfigService 通知 Python → 再刷新 Java → 再重建连接池"，注释说明是为避免 callback key 变更后认证死锁。这个设计是有意识的，闭环基本完整。但缺一环：**配置变更无历史/审计**（sys_config 无 version/update_time 审计字段在管理页暴露），admin 改错了无法回滚到上一个已知good值，只能"恢复默认"——而 X06-01 证明"默认值"本身可能就是错的。建议补配置变更历史表。

3. **可运维性**（故障定位/单一事实源）：当前"同一配置项"的值分布在 env（3 处）+ sys_config 种子（2 份 SQL）+ migration（N 份）+ Pydantic 默认 + SystemConfigInitializer seed 列表，**共 6+ 个潜在来源**，无单一事实源。运维遇到"crawler 行为异常"时，要排查"到底是哪个源的值生效"非常困难。X06-01 的 deepseek-v4-pro 正是例证——env 明明写 qwen-plus，crawler 却用 deepseek-v4-pro，因为 sys_config 种子覆盖了 env。建议确立优先级文档：明确"sys_config > env > Pydantic 默认"且 sys_config 种子与 env 模板必须人工保持一致。

### [P4] [Design] 配置体系缺单一事实源与变更审计，运维排障成本高 <!-- 编号：X06-11 -->

- **定位**：全模块（env 3 处 + sys_config 种子 2 份 SQL + migration + Pydantic 默认 + Initializer seed 列表）
- **现象**：同一配置项有 6+ 个潜在来源，无自动化校验它们一致。配置变更无历史记录。
- **影响**：单人维护下，配置相关故障的定位成本高；改 env 不生效（因 sys_config 覆盖）会反复踩坑。
- **建议方向**：① 写一个校验脚本（可加进 release-gate）比对 env 模板与 sys_config 种子的同名项值是否一致；② sys_config 增加变更历史表（key/old_value/new_value/changed_at/changed_by）；③ 明确文档化优先级。（标改动面 中）
- **关联**：[[X06-01]] / [[X06-02]] / [[X06-08]]

---

## 模块小结

### 严重度统计

| 级别 | 数量 | 条目编号 |
|---|---|---|
| P0 | 0 | — |
| P1 | 1 | X06-01 |
| P2 | 3 | X06-02, X06-05, X06-08 |
| P3 | 5 | X06-03, X06-04, X06-06, X06-09, X06-10 |
| P4 | 1 | X06-11 |

（X06-07 为"未发现风险"的正向确认条目，不计入严重度统计）

### Top 风险（本模块最该先看的 ≤3 条）

1. **X06-01 AI_MODEL 三轨不一致 + deepseek-v4-pro 疑似无效模型名 + model/base_url/default_value 三方错配** —— 直接影响日报生成是否可跑，且"恢复默认"会破坏可用性，是配置体系最危险的自洽性缺陷。
2. **X06-02 init.sql 与 schema.sql 的 sys_config 种子漂移 8 项** —— compose 部署（用 schema.sql）会少一批 crawler 期望的 key，两套部署路径行为不同。
3. **X06-05 check-deploy-env 必填项覆盖不全** —— DB_PASSWORD/COOKIE_SECURE/CORS 等关键安全项不在发布门禁体检范围。

### 修复优先级建议

- **立即**（P0/P1）：
  - X06-01：选定 AI 单一事实源（deepseek 或 qwen），全栈统一 env + sys_config 的 config_value/default_value + README；核实 `deepseek-v4-pro` 是否官方有效 model ID。
- **计划**（P2）：
  - X06-02：对齐 init.sql 与 schema.sql 的 sys_config 种子段（主改动归 B15）。
  - X06-05：扩充 check-deploy-env 必填项与危险值断言。
  - X06-08：理清 V1_21 删除的 key 与 crawler 消费的关系，明确每个 key 的归属。
- **择机**（P3/P4）：
  - X06-03/04：补齐 crawler 期望的 key 或清理 backend_config.py 的无效 get。
  - X06-09：前缀剥离改显式 substring。
  - X06-10：补 CRAWLER_SERVICE_URL 到 .env.example。
  - X06-11：建立配置一致性校验脚本与变更审计。

### 排查盲区 / 待复核

- **X06-01 `[需查证]`**：`deepseek-v4-pro` 是否为 DeepSeek 官方 API（`https://api.deepseek.com/v1`）接受的有效 model ID。WebSearch 结果显示官方文档只列 `deepseek-chat`/`deepseek-reasoner`，"V4 Pro" 仅第三方文章提及。需用真实 API key 调一次 `POST /chat/completions` 验证（属外网请求，本排查受 §1.3 命令边界限制未执行）。
- **X06-02 `[需查证]`**：是否真有部署路径会跑 `init.sql`（而非 schema.sql）。docker-compose 明确挂载 schema.sql，init.sql 的实际使用场景待确认（可能是历史遗留或本地开发用）。
- **运行时优先级实测 `[需查证]`**：crawler 拉取 backend 配置成功时，sys_config 是否真的覆盖 env（`backend_config.py` 的 `if config.get(key,""):` 非空才覆盖）。本排查读代码确认逻辑如此，但未实跑验证 crawler 在 backend 可达时的最终 ai_model 值。

### 同名配置项三处对照表（核心不一致项）

| 配置 key | deploy/.env.example | crawler-service/.env.example | sys_config 种子 (init.sql/schema.sql) | 差异/风险 |
|---|---|---|---|---|
| AI_MODEL | `qwen-plus` | `qwen-plus` | `deepseek-v4-pro`（config_value）/ `qwen-plus`（default_value） | **X06-01 P1**：生效值与 env 矛盾，default_value 与 config_value 不同厂商 |
| AI_BASE_URL | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `https://api.deepseek.com/v1`（config_value）/ `''`（default_value） | **X06-01 P1**：与 AI_MODEL 的 deepseek 组自洽，但与 env 的 qwen 组矛盾；default_value 空会致"恢复默认"后调用失败 |
| DIGEST_SEARCH_ENGINE | （无此项） | `bing`（crawler env） | `bing`（种子）/ `sogou`（V1_20 改） | crawler Pydantic 默认 `sogou`；env 写 bing；种子写 bing；V1_20 migration 改 sogou。四方不一致（X06-08） |
| AI_DIGEST_MAX_TOKENS | （无此项） | （无此项） | `10000`（init.sql/schema.sql 种子）/ `16000`（V1_20 改）/ V1_21 删除 | crawler Pydantic 默认 16000；种子 10000；migration 内部反向漂移（X06-02/08） |
| MAX_CONCURRENT_CRAWLS | `2` | `3` | `crawler.limit.max_concurrent=3`（init.sql，schema.sql 无） | deploy env 与 crawler env 默认值不同（2 vs 3）；sys_config=3；compose 用 deploy env 的 2。**注**：deploy env 是有意的"试用资源护栏"，但 sys_config 种子未同步降为 2，admin 改 sys_config 后行为与 deploy env 预期背离 |
| DIGEST_GLOBAL_TIMEOUT | `420` | （无） | `crawler.digest.global_timeout=600`（init.sql，schema.sql 无） | deploy env 420 vs sys_config/Pydantic 600；compose 注入 deploy env 的 420 覆盖。三层不一致 |
| DIGEST_PARALLEL_SECTIONS | `1` | （无） | `crawler.digest.parallel_sections=2`（init.sql，schema.sql 无） | deploy env 1 vs sys_config/Pydantic 2；同上 |
| AI_DIGEST_TOTAL_BUDGET | `60000` | （无） | `crawler.ai.digest_total_budget=100000`（init.sql，schema.sql 无） | deploy env 60000 vs sys_config/Pydantic 100000；同上 |
| CRAWLER_SERVICE_URL | **缺失** | （不适用） | `crawler.service.base-url` 从该 env seed | **X06-10 P3**：.env.example 漏列，compose 硬编码 |
| AI_ENABLED | `false` | `false` | `crawler.ai.enabled=false`（种子）/ SystemConfigInitializer 从 env seed | 一致 ✓ |
| DIGEST_ENABLED | `false` | `false` | `crawler.digest.enabled=false`（种子）/ Initializer 从 env seed | 一致 ✓ |
| CRAWLER_API_KEY | `your_shared_crawler_api_key`（占位符） | `sk-your-secret-key-here`（占位符，字段名 API_KEYS） | `crawler.service.api-key` 从 env seed（加密） | 占位符 check-deploy-env 会拦；crawler env 字段名是 API_KEYS 非 CRAWLER_API_KEY（compose 做映射） |
