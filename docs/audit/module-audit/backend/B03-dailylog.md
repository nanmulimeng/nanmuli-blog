# B03 技术日志 DailyLog 排查报告

> **模块编号**：B03
> **排查范围**：技术日志 CRUD、公开可见性（is_public）、tags（JSONB）、log_date、心情/天气字段、时间线展示
> **基线 commit**：`6ae930098405f4d0553d96a852f3345d0f39682e`
> **工作区状态**：脏（未提交改动**不涉及** B03：仅 ConfigRepositoryImpl/WebCollectPageMapper/crawler-service/deploy README/release-gate 等）。B03 全部文件均为基线状态。
> **排查日期**：2026-06-23
> **排查人**：模块排查 agent（只读）
> **状态**：草稿

---

## 模块概览

**职责**：维护每日技术笔记（Markdown），支持公开/私密切换、按日期倒序分页、心情/天气元数据、可选关联分类，并提供给 WebCollector「转日志」链路落地。

**关键文件**：
- `backend/src/main/java/com/nanmuli/blog/interfaces/rest/DailyLogController.java:17` —— REST 入口（公开 `/api/daily-log/**` + 管理 `/api/admin/daily-log/**`）
- `backend/src/main/java/com/nanmuli/blog/application/dailylog/DailyLogAppService.java:29` —— 应用服务（CRUD + 批量分类查询 + 计数）
- `backend/src/main/java/com/nanmuli/blog/domain/dailylog/DailyLog.java:13` —— 领域实体
- `backend/src/main/java/com/nanmuli/blog/domain/dailylog/DailyLogRepository.java:8` —— 仓储接口（含 findPublic*）
- `backend/src/main/java/com/nanmuli/blog/infrastructure/persistence/dailylog/DailyLogRepositoryImpl.java:16` —— 仓储实现
- `backend/src/main/java/com/nanmuli/blog/infrastructure/persistence/dailylog/DailyLogMapper.java:8` —— MyBatis Plus Mapper（空接口，纯 BaseMapper）
- `backend/src/main/java/com/nanmuli/blog/application/dailylog/command/CreateDailyLogCommand.java:10` —— 创建/更新命令
- `backend/src/main/java/com/nanmuli/blog/application/dailylog/dto/DailyLogDTO.java:13` —— 出参 DTO
- `backend/src/main/resources/db/init.sql:241` / `deploy/db/init-scripts/schema.sql:185` / `backend/src/main/resources/db/migration/V1_5__add_category_to_daily_log.sql` —— 三轨 schema

**对外接口 / 依赖**：
- 对外 Controller：`/api/daily-log/list`、`/api/daily-log/{id}`（公开）；`/api/admin/daily-log` CRUD + `/api/admin/daily-log/list` + `/api/admin/daily-log/{id}`（管理）
- 被消费：`WebCollectorAppService.convertToDailyLog`（`WebCollectorAppService.java:306`）调用 `DailyLogAppService.create`；`HomeController.countPublic`（`HomeController.java:65`）
- 依赖：`CategoryRepository`（关联分类）、`MarkdownUtil`（Markdown→HTML + XSS 净化）、MyBatis Plus、`BaseAggregateRoot`（`@TableLogic` 软删除 + 雪花 ID）、表 `daily_log`、`category`

**已读文件清单**：
- `application/dailylog/DailyLogAppService.java` —— 通读
- `application/dailylog/command/CreateDailyLogCommand.java` —— 通读
- `application/dailylog/dto/DailyLogDTO.java` —— 通读
- `domain/dailylog/DailyLog.java` —— 通读
- `domain/dailylog/DailyLogRepository.java` —— 通读
- `infrastructure/persistence/dailylog/DailyLogRepositoryImpl.java` —— 通读
- `infrastructure/persistence/dailylog/DailyLogMapper.java` —— 通读
- `interfaces/rest/DailyLogController.java` —— 通读
- `shared/util/MarkdownUtil.java` —— 通读（佐证 XSS 净化）
- `shared/domain/BaseAggregateRoot.java` —— 通读（佐证软删除/ID 策略）
- `shared/query/BasePageQuery.java` —— 通读（佐证分页归一化）
- `infrastructure/config/security/SaTokenConfig.java` —— 通读（佐证鉴权边界）
- `db/init.sql`、`deploy/db/init-scripts/schema.sql`、`db/migration/V1_5__add_category_to_daily_log.sql` —— daily_log 段落
- `application.yml`（mybatis-plus / flyway 段）—— 片段
- `application/webcollector/WebCollectorAppService.java:305-342` —— 转日志链路片段
- 前端 `frontend/src/types/dailyLog.ts`、`frontend/src/api/dailyLog.ts` —— grep + 片段

**主模块归属**：
- 本模块对 **daily_log 表 schema / Flyway 双轨 / is_public 列缺失（init.sql）** 只引用 **B15**（schema 主模块），不展开。
- 对 **tags JSONB / JsonbTypeHandler** 只引用 **B14-02**（数据访问层），不展开；本报告仅记 DailyLog 视角的字段缺失。
- 对 **Sa-Token URL 前缀鉴权机制** 只引用 **B06**。
- 对 **Category 关联** 只引用 **B02**。
- 本模块深查：CRUD 正确性、is_public 过滤边界、log_date 重复、tags 缺失、长度校验、软删除、安全可见性。

---

## `[Bug]` 代码正确性与潜在缺陷

> 排查范围：DailyLogAppService / DailyLogRepositoryImpl / DailyLogController / DailyLog 实体 / CreateDailyLogCommand / DailyLogDTO / 转日志链路。

### [P2] [Bug] tags 字段三轨 schema 均定义但 Java 实体/DTO/Command/前端类型全部缺失  <!-- 编号：B03-01 -->
- **定位**：`db/init.sql:247`、`deploy/db/init-scripts/schema.sql:191`（`tags JSONB`）vs `domain/dailylog/DailyLog.java:13-31`（无 tags 字段）、`application/dailylog/command/CreateDailyLogCommand.java:10-21`（无 tags）、`application/dailylog/dto/DailyLogDTO.java:13-39`（无 tags）、`frontend/src/types/dailyLog.ts` 的 `DailyLog` 接口（无 tags）
- **现象**：daily_log 表有 `tags JSONB` 列且两份 schema 都标了 `COMMENT ON COLUMN daily_log.tags IS '标签JSON数组'`，但：
  1. `DailyLog` 实体无 `tags` 字段，未用 `@TableField(typeHandler = JsonbTypeHandler.class)`（对比 `Project.java:26-30` 的 `screenshots`/`techStack` 用了）；
  2. 写入路径（`DailyLogAppService.create`/`update`、`WebCollectorAppService.convertToDailyLog:328-335`）均不传 tags；
  3. 读取路径 DTO 不暴露 tags；
  4. 前端类型与表单也无 tags。
  即"建了表、加了列、写了注释，但全链路无人读写"。
- **影响**：tags 功能完全不可用——管理端无法给日志打标签，公开页无法按标签筛选/展示。属于「看起来能用实则跑不通」的半成品。运行时无错误（JSONB 列默认 NULL），但功能缺失。另：MyBatis Plus `map-underscore-to-camel-case=true` 下，若后续有人误以为实体有 tags，反查会导致困惑。
- **根因/分析**：疑似早期建表预留列但未实现（与 CLAUDE.md「标签系统未上线」口径一致：daily_log 的 tags 与全局标签系统一起被搁置）。已排除「字段名映射问题」——Java 层确实没有任何 tags 相关声明。
- **修复方向**：
  1. 若 MVP 不做 tags：从两份 schema 删除 `tags JSONB` 列与注释，消除三轨中的死列（改动面 中，需 B15 评估迁移）；
  2. 若要做 tags：在 `DailyLog` 加 `@TableField(typeHandler = JsonbTypeHandler.class) private List<String> tags;`，同步补 Command/DTO/前端类型与表单，参考 `Project` 实现（改动面 中）。
- **关联**：B15（schema 三轨主模块）、B14-02（JsonbTypeHandler 主模块）、横向主题「schema 漂移」、CLAUDE.md「标签系统未上线」

### [P2] [Bug] log_date 无唯一约束，findByLogDate 形同虚设  <!-- 编号：B03-02 -->
- **定位**：`infrastructure/persistence/dailylog/DailyLogRepositoryImpl.java:36-40`（`findByLogDate`）；schema 无 UNIQUE：`db/init.sql:241-254`、`deploy/db/init-scripts/schema.sql:185-199`（`log_date DATE NOT NULL` 但无 UNIQUE/索引唯一）；`grep -i "unique.*daily\|daily.*unique"` 在三轨 schema 均无命中
- **现象**：`DailyLogRepository.findByLogDate` 用 `selectOne` 查询，但表上 `log_date` 没有唯一约束。若同一天插入多条日志，`selectOne` 在 MyBatis Plus 下会抛 `TooManyResultsException`。
- **影响**：①当前 `findByLogDate` **无任何调用方**（全仓 grep 仅接口声明 + 实现，零消费），所以暂不触发；②但该方法是公开仓储接口，一旦未来被「按日期跳转/防重复录入」逻辑调用，多人维护或 WebCollector 批量转日志时会因重复日期炸开；③「技术日志」语义上通常一天一条，缺少唯一约束意味着可以无限建同日记录，时间线展示会出现重复日期条目。
- **根因/分析**：DDL 漏建唯一索引，仓储方法与约束脱节。已排除「逻辑删除影响唯一性」——即便加唯一约束，PostgreSQL 唯一索引默认不排除软删行（`is_deleted=false` 的重复也会冲突），需配合 partial index。
- **修复方向**：
  1. 明确 log_date 语义：若「一天一条」→ 加 partial unique index `WHERE is_deleted=false`，并让 create/update 先 `findByLogDate` 校验；
  2. 若允许多条 → 把 `findByLogDate` 改为 `findAllByLogDate` 返回 List，或删除该死方法（改动面 小）。
- **关联**：B15（索引/约束主模块）、次维度 [Arch]（死代码）

### [P3] [Bug] mood/weather 无长度校验，超长触发 DB 异常而非业务异常  <!-- 编号：B03-03 -->
- **定位**：`application/dailylog/command/CreateDailyLogCommand.java:13-14`（`private String mood; private String weather;` 无 `@Size`）、`domain/dailylog/DailyLog.java:18-19`；schema `db/init.sql:245-246`（`mood VARCHAR(20), weather VARCHAR(20)`）
- **现象**：Command 的 mood/weather 既无 `@Size(max=20)` 也无 enum 校验；schema 注释明确 mood 取值 `happy/excited/normal/tired`，但后端不校验枚举值。前端 `dailyLog.ts` 用了联合类型 `'happy'|'excited'|'normal'|'tired'`，但后端裸接 String。
- **影响**：①API 直调（绕过前端）传 mood=`"a-very-long-mood-string- exceeding-twenty-chars"` 会到 DB 才报 `value too long for type character varying(20)`，被全局异常处理器吞成 500 而非 400 业务异常；②传 mood=`"invalid"` 也能落库，污染数据。
- **根因/分析**：校验只在 DB 层与前端层，应用层缺位。
- **修复方向**：Command 加 `@Size(max=20)`；mood 考虑用枚举或 `@Pattern` 限定取值（改动面 小）。
- **关联**：次维度 [Security]（输入校验）

### [P3] [Bug] update 方法复用 CreateDailyLogCommand，UpdateDailyLogCommand 缺失  <!-- 编号：B03-04 -->
- **定位**：`application/dailylog/DailyLogAppService.java:54`（`public void update(Long id, CreateDailyLogCommand command)`）、`interfaces/rest/DailyLogController.java:41`；`backend/src/main/java/com/nanmuli/blog/application/dailylog/command/` 目录仅有 `CreateDailyLogCommand.java`
- **现象**：update 接口和 create 共用同一个 Command 类。任务描述里提到的 `UpdateDailyLogCommand` 在代码中**不存在**。
- **影响**：功能层面无 bug（create 的字段 update 都需要），但语义混淆：未来若 update 需要部分字段可选（如只改 isPublic 不动 content），Create 的 `@NotBlank content` / `@NotNull logDate` 会强制要求全量字段，无法做 PATCH 语义。
- **根因/分析**：应为早期简化设计，未拆分 Command。已排除「文件丢失」——目录确无此文件。
- **修复方向**：若需要 PATCH 语义，拆出 `UpdateDailyLogCommand`（字段均可选）；若维持 PUT 全量语义，保持现状但更新文档/注释说明（改动面 小）。
- **关联**：次维度 [Arch]（命名一致性）

### [P3] [Bug] toDTO 单条查询路径绕过批量 Map，回退查询未去重  <!-- 编号：B03-05 -->
- **定位**：`application/dailylog/DailyLogAppService.java:138-158`（`toDTO(dailyLog, categoryMap)`）
- **现象**：`getById`（管理端单查）走 `toDTO(dailyLog)` → `toDTO(dailyLog, Map.of())`。进入 148-156 行后，因 `categoryMap` 是空 Map 且 `containsKey(categoryId)` 为 false，会**每次都回退到 `categoryRepository.findById` 单查**。批量路径 `batchConvertToDTO` 已预填 Map，不受影响；但单条详情接口（高频调用）每次都多一次分类查询。
- **影响**：管理端详情页有轻微 N+1（1+1 查询而非 1 次 join）。性能影响小（单条），但逻辑上「批量反而比单条更优化」是反直觉的。
- **根因/分析**：`toDTO` 的 Map 回退分支设计意图是兜底，但单条入口直接传空 Map，等于总是走兜底。
- **修复方向**：单条入口直接 `categoryRepository.findById` 并放入 Map，或让 `getById` 也走批量逻辑的等价路径；不影响正确性，属优化（改动面 小）。
- **关联**：次维度 [Bug]（性能）

---

## `[Security]` 安全漏洞

> 排查范围：公开/管理接口可见性边界、is_public 过滤、Sa-Token 拦截、XSS（Markdown 渲染）、SQL 注入（MyBatis Plus 写法）、ID 越权。
> 逐项对照 §2.2 技术栈重点：Sa-Token（URL 前缀鉴权 → 引用 B06）、MyBatis `${}`vs`#{}`（本模块纯 LambdaQueryWrapper，无字符串拼接，无 SQLi）、Cookie/CSRF（引用 B06）、CORS（引用 B16）、AES（不涉及）、SSRF（不涉及）、文件上传（不涉及）、双向 key（不涉及）。

### [P1] [Security] 公开详情接口 is_public 过滤正确，但 update/delete 不校验日志归属（单人博客可接受，需确认）  <!-- 编号：B03-06 -->
- **定位**：`interfaces/rest/DailyLogController.java:40-49`（update/delete 仅 `/api/admin/**` 前缀保护）、`application/dailylog/DailyLogAppService.java:53-106`（update/delete 按 id 操作，不校验作者/归属）
- **现象**：
  - 公开可见性过滤**正确**：`/api/daily-log/list` → `listPublicPage`（`findPublicPage` `eq(getIsPublic, true)`，`DailyLogRepositoryImpl.java:50-55`）；`/api/daily-log/{id}` → `getPublicById`（`findPublicById` 同时校验 id + `eq(getIsPublic, true)`，`DailyLogRepositoryImpl.java:58-63`）。公开接口**严格排除** is_public=false，无越权泄露。
  - 但 update/delete 无归属校验：任何已登录 admin（Sa-Token 仅 `checkLogin()`，见 `SaTokenConfig.java:32`）可改/删任意日志。本项目是单人博客，admin 即 owner，**风险可接受**，但若未来多作者则越权。
- **影响**：单人 MVP 场景下无实际越权（只有 owner 一个 admin）。多作者场景下会越权改删他人日志。鉴权纯靠 URL 前缀（`/api/admin/**`）是已知薄弱点，归属 B06。
- **根因/分析**：单人博客的合理简化。已确认公开接口的 is_public 过滤无漏洞——这是任务重点关注的越权风险点，结论是**安全**。
- **修复方向**：维持现状即可（MVP 单人）；若未来多作者，update/delete 加 ownerId 校验。鉴权机制强化见 B06（改动面 小）。
- **关联**：B06-鉴权机制、横向主题「鉴权一致性」

### [P2] [Security] content_html 由后端 flexmark + Jsoup 净化，但前端二次渲染需确认（XSS）  <!-- 编号：B03-07 -->
- **定位**：`shared/util/MarkdownUtil.java:39-79`（`toHtml` → `sanitizeHtml`，Safelist.basic + 白名单协议 + `rel=noopener`）、`application/dailylog/DailyLogAppService.java:46,61`（create/update 调 toHtml 存 content_html）、`DailyLogDTO.java:19`（`contentHtml` 出参）
- **现象**：后端渲染 HTML 时用 Jsoup `Safelist` 过滤：a 标签仅 http/https/mailto、img 仅 http/https（禁 data:）、强制 `rel="noopener noreferrer"`、白名单标签集。净化策略**合理**，已覆盖常见 XSS 向量（script/onevent/javascript:/data:）。
- **影响**：若前端直接 `v-html` 渲染 `contentHtml`，后端净化已兜底，XSS 风险低。**但**：前端若同时用 markdown-it 对 `content`（原始 Markdown）二次渲染，则需前端自行净化——这是 F03 的重点，本模块只确认后端侧。
- **根因/分析**：后端净化链路完整。前端渲染路径归属 F03（md 双轨）。
- **修复方向**：无需后端改动；前端确认不绕过 `contentHtml` 直渲原始 `content`（改动面 无/引用 F03）。
- **关联**：F03（前端 md 渲染主模块）、次维度 [Bug]

### 未发现（其余安全项）
- **MyBatis SQL 注入**：本模块全部用 `LambdaQueryWrapper` + `eq`，无 `${}`、无 `apply()`/`last()` 字符串拼接，无 SQLi。`DailyLogMapper` 是空接口继承 `BaseMapper`，无自定义 SQL。
- **ID 越权（公开接口）**：`findPublicById` 双条件（id + is_public），即便枚举 id 也拿不到私有日志。
- **逻辑删除泄露**：`@TableLogic` + 全局 `logic-delete-field=isDeleted`（`application.yml:50`），公开查询自动过滤软删行。

---

## `[Arch]` 架构与技术债

> 排查范围：DDD 分层、命名一致性、死代码、与 Project 模块的 JsonbTypeHandler 模式不一致。

### [P3] [Arch] DailyLog 实体缺 @TableName，依赖下划线驼峰映射隐式约定  <!-- 编号：B03-08 -->
- **定位**：`domain/dailylog/DailyLog.java:13`（`public class DailyLog extends BaseAggregateRoot<Long>` 无 `@TableName`）vs `domain/project/Project.java:17`（`@TableName("project_showcase")` 显式）
- **现象**：DailyLog 类名 `DailyLog`，表名 `daily_log`，靠 `map-underscore-to-camel-case=true` 隐式映射。Project 因类名 `Project` 与表名 `project_showcase` 不一致，显式标了 `@TableName`。
- **影响**：功能正常，但隐式约定脆弱——若有人重命名类或改全局映射配置，DailyLog 会静默查错表。
- **根因/分析**：约定优于配置的合理使用，非 bug。
- **修复方向**：可选显式加 `@TableName("daily_log")` 提高可读性（改动面 小）。
- **关联**：B14（数据访问层主模块）

### [P3] [Arch] findByLogDate 死代码（零调用）  <!-- 编号：B03-09 -->
- **定位**：`domain/dailylog/DailyLogRepository.java:13`（接口声明）、`infrastructure/persistence/dailylog/DailyLogRepositoryImpl.java:36-40`（实现）
- **现象**：全仓 grep `findByLogDate` 仅命中接口声明 + 实现，**无任何业务调用方**。
- **影响**：维护负担 + 与 B03-02 叠加（无唯一约束下 selectOne 是隐患）。
- **根因/分析**：预留接口未接入。
- **修复方向**：要么接入防重复录入逻辑（配合 B03-02 加约束），要么删除（改动面 小）。
- **关联**：B03-02

### 未发现（其余架构项）
- **DDD 分层**：分层清晰，Controller 不写业务（仅 Math.max 归一化），AppService 编排事务，Repository 接口在领域层、实现在基础设施层，符合规约。
- **上帝类**：`DailyLogAppService` 176 行，规模健康。
- **事务**：写操作 `@Transactional`，读操作 `@Transactional(readOnly=true)`，正确。

---

## `[Deps]` 依赖升级与版本

### 本模块依赖清单（基于声明文件，未翻依赖源码）

| 依赖 | 版本 | 声明位置 | 已知风险/可升级 | 备注 |
|---|---|---|---|---|
| MyBatis Plus | 3.5.9 | `backend/pom.xml`（CLAUDE.md 声明） | 可升至 3.5.12+；3.5.9 已非最新 [需查证] | 本模块仅用 BaseMapper + LambdaQueryWrapper，API 稳定 |
| flexmark-java | (未在 pom 片段确认) | `backend/pom.xml` | [需查证] 具体版本 | MarkdownUtil 依赖，用于 toHtml |
| jsoup | (未在 pom 片段确认) | `backend/pom.xml` | [需查证] 具体版本 | XSS 净化用，safelist API 稳定 |
| Sa-Token | 1.44.0 | `backend/pom.xml`（CLAUDE.md） | 可升至 1.46.0 [需查证] | 本模块仅间接依赖（拦截器） |

> 排查范围：本模块依赖基于 CLAUDE.md 声明 + import 语句，未逐行核对 pom.xml 版本号（pom 版本核对归属 B14/X01）。flexmark/jsoup 具体版本标 [需查证]。

### 未发现

本模块无独立依赖升级风险项——使用的都是项目基础库（MyBatis Plus / flexmark / jsoup），版本统一性归属 B14。

---

## `[Design]` 功能设计合理性

> 从单人维护的技术博客 + 每工作日 AI 日报场景出发，回答 §2.5 相关问题。

**审视结论**：

1. **场景适配（§2.5-1）**：DailyLog 的字段设计（content/mood/weather/log_date/isPublic/categoryId）对「每日技术笔记」场景**适配合理**，mood/weather 是轻量元数据不冗余。但 **tags 缺失（B03-01）** 让「按技术标签回顾」这个技术日志最该有的能力不可用——技术日志的核心价值之一就是按技术主题（Java/算法/调试）归类，没有 tags 等于只能按日期线性浏览，场景适配上**过于简陋**。

2. **闭环完整性（§2.5-2）**：WebCollector「转日志」链路（`convertToDailyLog`）能闭环落库，但转过来的日志默认 `isPublic=false`（`WebCollectorAppService.java:333`），需要人工再去管理端改公开——这一步**有人工干预入口（管理端列表）**，闭环成立。不过缺少「按日期去重提醒」（B03-02 无唯一约束），同一天转多次会产生重复日志且无提示。

3. **可运维性（§2.5-3）**：日志删除是软删除（`@TableLogic`），但**无审计**（谁删的、何时删的无记录），误删后只能查 DB `is_deleted=true` 行手动恢复，无运营工具。对单人博客可接受。

4. **MVP 假设检验（§2.5-4）**：CRUD + 公开可见性 + 时间线展示**真实可用**，非半成品。唯一的「假能力」是 tags（B03-01）：schema 声明有能力，实际全链路不可用。

### [P4] [Design] tags 缺失导致技术日志无法按主题归类（设计层）  <!-- 编号：B03-10 -->
- **定位**：功能点：日志标签分类（schema 已建列，代码未实现）
- **现象**：见 B03-01。技术日志场景下，按技术主题（Spring/MyBatis/算法/调试经验）归类是高频需求，当前只能靠 `categoryId`（单一分类）+ 全文搜索。
- **影响**：日志量积累后，按主题回顾困难，时间线是唯一导航维度。
- **建议方向**：实现 tags（参考 Project 的 JsonbTypeHandler 模式），或明确从 schema 删列并文档化「不做标签」（改动面 中）。
- **关联**：B03-01、B14-02

---

## 模块小结

### 严重度统计

| 级别 | 数量 | 条目编号 |
|---|---|---|
| P0 | 0 | — |
| P1 | 1 | B03-06（实为「确认安全」，风险可接受） |
| P2 | 3 | B03-01, B03-02, B03-07 |
| P3 | 4 | B03-03, B03-04, B03-05, B03-08, B03-09 |
| P4 | 1 | B03-10 |

> 注：B03-06 标 P1 是因「越权」标签本身高敏，但结论是**当前单人场景安全**，待多作者时才成问题。其余 P2/P3 均为功能缺失或边界优化，无数据损坏/安全漏洞。

### Top 风险（本模块最该先看的 ≤3 条）

1. **B03-01 tags 全链路缺失** —— schema 建了列、注释写了「标签JSON数组」，但 Java/前端零实现，是典型的「假能力」，影响技术日志核心使用价值。
2. **B03-02 log_date 无唯一约束 + findByLogDate 死代码** —— 预留方法无约束兜底，未来接入即炸，且允许同日重复。
3. **B03-06 公开可见性** —— 结论是**安全**（is_public 过滤严格），但需确认未来多作者场景的归属校验规划。

### 修复优先级建议

- **立即**（P0/P1）：无。B03-06 当前安全，无需立即改。
- **计划**（P2）：
  - B03-01：决策 tags 是做还是删（与 B15/B14 协同）
  - B03-02：明确 log_date 语义，加约束或删死方法
  - B03-07：前端渲染路径确认（依赖 F03）
- **择机**（P3/P4）：
  - B03-03 长度/枚举校验
  - B03-04 Command 拆分（若需 PATCH）
  - B03-05 单条查询优化
  - B03-08 显式 @TableName
  - B03-09 删死代码
  - B03-10 tags 设计决策

### 排查盲区 / 待复核

- **[需查证] flexmark-java / jsoup 的具体 pom 版本**：本次未逐行核 pom.xml（归属 B14），仅确认 import 可用。jsoup 旧版本曾有 safelist 绕过 CVE，需 B14 核版本。
- **[需查证] 前端是否对 `content`（原始 Markdown）二次渲染**：若前端 markdown-it 渲染原始 content 且不净化，则 B03-07 升级为前端 XSS，归属 F03。
- **[需查证] is_public 列在 init.sql 缺失的实际影响**：init.sql 的 daily_log 表定义**没有 is_public 列**（`db/init.sql:241-254`），仅 schema.sql 和 V1_5 migration 有。若新建库走 init.sql 而非 migration（Flyway 未集成），则 is_public 列不存在 → `findPublicPage`/`findPublicById` 的 `eq(getIsPublic, true)` 会 SQL 报错。这是 B15 schema 三轨漂移的具体体现，本模块只引用，由 B15 定级。
