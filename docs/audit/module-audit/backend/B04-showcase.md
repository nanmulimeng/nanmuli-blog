# B04 展示类 Project / Skill / FriendLink 排查报告

> **模块编号**：B04
> **排查范围**：三个展示型实体（Project / Skill / FriendLink）的 CRUD + 公开展示链路，含 JSONB screenshots、slug 唯一性、status 审核流、proficiency 边界、外链 URL 校验、公开可见性过滤
> **基线 commit**：`6ae930098405f4d0553d96a852f3345d0f39682e`
> **工作区状态**：脏（未提交改动均不在本模块范围：`ConfigRepositoryImpl.java`、`WebCollectPageMapper.java`、`crawler-service/*`、`deploy/README.md`、`docs/audit/full-project-risk-register.md`、`scripts/release/release-gate.ps1`、新增 `backend/src/test/.../webcollector/`）。本模块涉及的 `application/{project,skill,friendlink}/`、`domain/{project,skill,friendlink}/`、`interfaces/rest/{Project,Skill,FriendLink}Controller.java`、`infrastructure/persistence/{project,skill,friendlink}/` 均为干净状态。
> **排查日期**：2026-06-23
> **排查人**：B04 模块 agent
> **状态**：完成

---

## 模块概览

**职责**：为博客前台提供"项目展示 / 技能展示 / 友情链接"三块静态展示内容的管理与公开查询，是 MVP 试用的"门面"内容之一。

**关键文件**：

Project：
- `backend/src/main/java/com/nanmuli/blog/domain/project/Project.java:18-39` —— 实体，`@TableName("project_showcase")`，screenshots/techStack 走 `JsonbTypeHandler`
- `backend/src/main/java/com/nanmuli/blog/application/project/ProjectAppService.java:19-133` —— CRUD + slug 唯一性 + URL 协议校验
- `backend/src/main/java/com/nanmuli/blog/application/project/command/CreateProjectCommand.java:14-107` —— 含 jakarta-validation 校验
- `backend/src/main/java/com/nanmuli/blog/interfaces/rest/ProjectController.java:19-54` —— `/api/project/list`、`/api/admin/project*`
- `backend/src/main/java/com/nanmuli/blog/infrastructure/persistence/project/ProjectRepositoryImpl.java:15-73` —— MyBatis Plus 实现

Skill：
- `backend/src/main/java/com/nanmuli/blog/domain/skill/Skill.java:11-22` —— 实体
- `backend/src/main/java/com/nanmuli/blog/application/skill/SkillAppService.java:16-80` —— CRUD
- `backend/src/main/java/com/nanmuli/blog/application/skill/dto/SkillDTO.java:18-50` —— 含 proficiency 1-5 校验
- `backend/src/main/java/com/nanmuli/blog/interfaces/rest/SkillController.java:17-52` —— `/api/skill/list`、`/api/admin/skill*`
- `backend/src/main/java/com/nanmuli/blog/infrastructure/persistence/skill/SkillRepositoryImpl.java:15-61`

FriendLink：
- `backend/src/main/java/com/nanmuli/blog/domain/friendlink/FriendLink.java:11-21` —— 实体
- `backend/src/main/java/com/nanmuli/blog/application/friendlink/FriendLinkAppService.java:16-68` —— CRUD
- `backend/src/main/java/com/nanmuli/blog/application/friendlink/dto/FriendLinkDTO.java:19-56` —— status `@Min(0)/@Max(1)`
- `backend/src/main/java/com/nanmuli/blog/interfaces/rest/FriendLinkController.java:17-52` —— `/api/friend-link/list`、`/api/admin/friend-link*`
- `backend/src/main/java/com/nanmuli/blog/infrastructure/persistence/friendlink/FriendLinkRepositoryImpl.java:15-53`

**对外接口 / 依赖**：

- 对外 HTTP：
  - 公开 GET：`/api/project/list`、`/api/project/{id}`、`/api/skill/list`、`/api/skill/{id}`、`/api/friend-link/list`
  - 管理 GET：`/api/admin/{project,skill,friend-link}/list`、`/api/admin/friend-link/{id}`
  - 管理 POST/PUT/DELETE：`/api/admin/{project,skill,friend-link}` 系列
- 依赖：
  - DB 表：`project_showcase`、`skill`、`friend_link`（schema 主模块 B15）
  - 共享组件：`BaseAggregateRoot`、`JsonbTypeHandler`、`OptimisticLockerInnerInterceptor`（B14-03）、Sa-Token 拦截器（B06）
  - 前端：`frontend/src/views/{project,admin/project,admin/skill,admin/friendLink}/`、`frontend/src/api/{project,skill,friendLink}.ts`、`frontend/src/components/common/{AppFooter,AppSidebar}.vue`

**已读文件清单**：

- `backend/.../domain/{project,skill,friendlink}/*.java` —— 通读（实体 + Repository 接口）
- `backend/.../application/{project,skill,friendlink}/*.java` —— 通读（AppService + Command + DTO）
- `backend/.../interfaces/rest/{Project,Skill,FriendLink}Controller.java` —— 通读
- `backend/.../infrastructure/persistence/{project,skill,friendlink}/*RepositoryImpl.java` + `*Mapper.java` —— 通读
- `backend/.../shared/domain/BaseAggregateRoot.java` —— 通读（确认无 @Version）
- `backend/.../infrastructure/config/db/{JsonbTypeHandler,MyBatisPlusConfig}.java` —— 通读
- `backend/.../infrastructure/config/security/SaTokenConfig.java` —— 通读（确认 admin 路径鉴权）
- `backend/src/main/resources/db/init.sql`、`deploy/db/init-scripts/schema.sql`、`backend/.../db/migration/V1_11__*.sql`、`V1_19__*.sql` —— grep 三表定义与 slug 索引
- `frontend/src/views/project/Index.vue`、`frontend/src/views/admin/{project,skill,friendLink}/Index.vue`、`frontend/src/api/{project,skill,friendLink}.ts`、`frontend/src/components/common/{AppFooter,AppSidebar}.vue` —— 通读/片段

**主模块归属**：

- 本模块**非主模块**，对以下共享对象只引用：
  - **PG schema / Flyway / init.sql / schema.sql** → 主模块 **B15**（本报告仅记录三表视角的契约差异）
  - **MyBatis Plus / `JsonbTypeHandler` / 乐观锁 `@Version`** → 主模块 **B14**（B14-02 / B14-03）
  - **Sa-Token 鉴权机制** → 主模块 **B06**

---

## `[Bug]` 代码正确性与潜在缺陷

> 排查范围：三个 AppService 的 CRUD 流、status/proficiency 边界、slug 唯一性、JSONB 解析、RepositoryImpl 查询条件、BeanUtils 复制语义。

### [P3] [Bug] Project slug 无 DB 唯一索引，仅靠应用层 existsBySlug 检查存在并发竞态   <!-- 编号：B04-01 -->
- **定位**：
  - `backend/src/main/java/com/nanmuli/blog/application/project/ProjectAppService.java:50-53`（create 检查）、`:77-81`（update 检查）
  - `backend/src/main/resources/db/init.sql:274-312`、`deploy/db/init-scripts/schema.sql:295-333`（project_showcase 建表 + 索引，仅 `idx_project_{sort,status,deleted}`，**无 slug 唯一索引**）
  - 对比：`backend/src/main/resources/db/migration/V1_11__add_unique_index_article_slug.sql:4-6` 为 article.slug 建了 `idx_article_slug_active`；`init.sql:842-845` 为 article/category 建了 slug unique index，**但 project_showcase 没有对等索引**。
- **现象**：Project 的 slug 唯一性纯靠 AppService 中 `if (existsBySlug(slug)) throw` 实现，DB 层无 `UNIQUE INDEX ... WHERE is_deleted = false` 兜底。
- **影响**：两个并发 admin 请求同时创建相同 slug 的项目时，两个 `existsBySlug` 都会返回 false，两条记录都写入，产生重复 slug。展示侧 `findBySlug`（虽然 Controller 目前没暴露 slug 查询，但仓储已暴露此方法，未来用做外链时会一对多歧义）。
- **根因/分析**：article/category 表迁移时补了 slug 唯一索引，project_showcase 漏补。已排除误判：grep 全仓库 `idx_project_slug` / `project_showcase.*UNIQUE` 均无命中。单人维护博客并发概率低，故定 P3 而非 P2。
- **修复方向**：
  1. 新增 migration `CREATE UNIQUE INDEX IF NOT EXISTS idx_project_slug_active ON project_showcase(slug) WHERE is_deleted = FALSE AND slug IS NOT NULL;`
  2. 同步到 `init.sql` 与 `deploy/db/init-scripts/schema.sql`（与 B15 schema 三轨治理一并处理）
- **改动面**：小（单 migration + schema 文件对齐）
- **关联**：[[B15]] schema 三轨漂移；横向主题 §2.6 schema 漂移

### [P3] [Bug] SkillRepository.findAllVisibleByCategory 为死代码，声明但无任何调用方   <!-- 编号：B04-02 -->
- **定位**：
  - `backend/src/main/java/com/nanmuli/blog/domain/skill/SkillRepository.java:11`（接口声明）
  - `backend/src/main/java/com/nanmuli/blog/infrastructure/persistence/skill/SkillRepositoryImpl.java:35-41`（实现）
- **现象**：`findAllVisibleByCategory(String category)` 在 SkillAppService、SkillController、前端 `frontend/src/api/skill.ts`、`frontend/src/views/skill/*` 中均无调用（grep 全仓库 `findAllVisibleByCategory` / `skill/category` / `by-category` 零业务命中）。
- **影响**：增加维护面，未来若误以为"按分类查技能"接口对外可用，会暴露未经验证的查询路径；同时诱导开发者重复实现。
- **根因/分析**：MVP 阶段仅做平铺列表展示，分类视图未上线。属于早期设计遗留。
- **修复方向**：删除接口与实现中的 `findAllVisibleByCategory`；或在 SkillController 补一个 `/api/skill/list?category=xxx` 真正用起来（按 MVP 范围取舍，倾向删除）。
- **改动面**：小
- **关联**：无

### [P3] [Bug] FriendLinkController 直接用 DTO 作 Command，缺少 dedicated CreateFriendLinkCommand 应用入口   <!-- 编号：B04-03 -->
- **定位**：
  - `backend/src/main/java/com/nanmuli/blog/interfaces/rest/FriendLinkController.java:36-39`（create 形参为 `FriendLinkDTO`）
  - `backend/src/main/java/com/nanmuli/blog/application/friendlink/FriendLinkAppService.java:21-26`（create 形参同样为 `FriendLinkDTO`）
  - 对比：`backend/.../application/friendlink/command/{CreateFriendLinkCommand,UpdateFriendLinkCommand}.java` **已声明却完全未被 Controller/AppService 引用**（grep `CreateFriendLinkCommand`/`UpdateFriendLinkCommand` 仅命中声明文件本身）
- **现象**：FriendLink 模块写了一套 `CreateFriendLinkCommand`/`UpdateFriendLinkCommand`（与 Project/Skill 风格一致），但 Controller 和 AppService 实际都直接接收 `FriendLinkDTO`。Command 类成了死代码。
- **影响**：① 与 Project/Skill 的"Command 输入 / DTO 输出"分层约定不一致；② `FriendLinkDTO` 上同时挂了入参校验注解（`@NotBlank url`、`@Min/@Max status`）和出参字段（`createTime`、`updateTime`），职责混杂；③ `UpdateFriendLinkCommand.id` 的 `@NotNull` 校验失效（因为根本没被使用），实际更新时 id 来自 path，body 校验薄弱。
- **根因/分析**：早期按 Project/Skill 模板写了 Command，后续重构时直接复用 DTO，未清理。已排除误判：grep 全仓库这两个 Command 类的 import 均为空。
- **修复方向**：统一为"Controller 接 CreateFriendLinkCommand/UpdateFriendLinkCommand，AppService 转 FriendLinkDTO 返回"——与 Project 模式对齐；或承认现状删除未用 Command。前者更符合 DDD 分层。
- **改动面**：中（跨 Controller + AppService + 测试）
- **关联**：次维度 [Arch]；DDD 分层违反（轻微）

### [P3] [Bug] Project screenshots（List<String> JSONB）无后端 URL 校验，与 githubUrl/demoUrl/docUrl 校验口径不一致   <!-- 编号：B04-04 -->
- **定位**：
  - `backend/src/main/java/com/nanmuli/blog/application/project/command/CreateProjectCommand.java:45-46`（screenshots 字段无任何 jakarta-validation 注解）
  - `backend/src/main/java/com/nanmuli/blog/application/project/ProjectAppService.java:38-42`（`validateUrls` 只校验 github/demo/doc 三个标量 URL，不校验 screenshots 列表）
- **现象**：screenshots 作为图片 URL 列表直接 `BeanUtils.copyProperties` 落库，后端无 `^https?://` 协议校验、无长度限制、无单元素个数上限；而 githubUrl/demoUrl/docUrl 都有 `@Pattern` + `@Size(max=500)` + AppService 二次 `validateUrlProtocol`。
- **影响**：① 一致性差：理论上可写入 `javascript:`、`data:`、内网 IP 等任意字符串到 screenshots；② 展示侧 `frontend/src/views/project/Index.vue:263` 走 `<SrcImage :src="screenshot">`，图片 src 的 XSS 风险相对低（浏览器对 img src 执行 JS 的能力有限），且 `openScreenshot` 用 `openSafeExternalUrl` 兜底（见 `frontend/src/utils/url.ts`，属 F0x）；③ 但若 screenshots 被其他消费者复用（如未来 OGP 渲染），缺乏后端校验是真实薄弱点。
- **根因/分析**：List<String> 用 jakarta-validation 做元素级校验需 `@Valid` + 自定义注解或 `List<@Pattern(...) String>`，实现成本高于标量字段，被遗漏。`JsonbTypeHandler.parseJson`（`JsonbTypeHandler.java:53-63`）解析失败时静默返回空列表（log.error 后吞掉异常），也属于"解析失败"边界处理（关联 B14-02）。
- **修复方向**：
  1. 在 CreateProjectCommand.screenshots 上加 `List<@Pattern(regexp="^https?://.+") @Size(max=500) String>`，并限制 `@Size(max=20)` 列表长度
  2. ProjectAppService.validateUrls 中遍历 screenshots 调 validateUrlProtocol（与外链校验口径统一）
- **改动面**：小
- **关联**：[[B14-02]] JsonbTypeHandler 解析失败静默吞异常；次维度 [Security]；外链（rel=nofollow 归前端 F0x）

---

## `[Security]` 安全漏洞

> 排查范围：逐项对照 §2.2 技术栈重点。覆盖：Sa-Token 路由覆盖（admin 路径）、MyBatis `${}` vs `#{}`、Cookie+CSRF、CORS、AES（本模块无关）、SSRF（screenshots/FriendLink.url）、文件上传（本模块无关）、双向 key（本模块无关）、越权（公开可见性过滤）。

### 本模块逐项核对结论（无新发现项，仅记录已验证口径）

- **Sa-Token 路由覆盖** ✅ 已核对：`SaTokenConfig.java:32-34` 对 `/api/admin/**` 全量 `StpUtil.checkLogin()`，本模块三个 admin Controller（`/api/admin/project*`、`/api/admin/skill*`、`/api/admin/friend-link*`）均命中前缀，**无漏网路径**。问题与所有 admin Controller 共享，主模块 **B06**。
- **MyBatis `${}` vs `#{}`** ✅ 已核对：三个 RepositoryImpl 全部使用 `LambdaQueryWrapper.eq(...)`，参数化绑定，无 `${}` / `apply()` / `last()` 字符串拼接，无 SQLi 风险。
- **公开可见性过滤（越权）** ✅ 已核对：
  - Project 公开 list 走 `findAllVisible`（`status=1` 过滤）、公开 detail 走 `getVisibleById`（额外 `filter(this::isVisible)`）—— 不可见的 project 前台访问返回 "项目不存在"。OK
  - Skill 同样模式。OK
  - FriendLink 公开 list 走 `findAllActive`（`status=1`），**没有**公开 `{id}` 详情接口（管理端才有）。OK
  - 但 `status` 字段为 Integer，逻辑删除 `isDeleted` 走 MyBatis Plus `@TableLogic` 自动追加，**未发现**绕过。
- **CSRF / CORS / Cookie** —— 共性问题，主模块 B06 / B16。本模块无独立写法。
- **SSRF**：见 B04-04（screenshots 无 URL 校验）；FriendLink.url 有 `@Pattern(regexp="^https?://.*$")` 协议白名单（`FriendLinkDTO.java:30`），但**无回环/保留地址过滤**（schema 注释声明 crawler 的 `ssrf_guard` 也不防 DNS rebinding，见 §9）。FriendLink.url 仅前端 `<a href>` 跳转、logo 走 `<img src>`，后端不会主动请求这些 URL，故**无服务端 SSRF**，仅前端外链安全（rel=nofollow 归 F0x）。
- **AES / 文件上传 / 双向 key** —— 本模块无关。

> 三模块均为简单 CRUD，鉴权与可见性过滤实现正确，**未发现独立的安全漏洞条目**。SSRF 边界（screenshots 无校验）已在 B04-04 记录。

---

## `[Arch]` 架构与技术债

> 排查范围：DDD 分层、God Class、重复实现、双轨漂移（schema 与代码契约）、隐式约定。共享对象（PG schema / Sa-Token / JsonbTypeHandler / 乐观锁）按 §8.6 仅引用。

### [P2] [Arch] FriendLink "2-待审核"状态值在代码层完全不可达，schema 注释与 Java 契约脱节   <!-- 编号：B04-05 -->
- **定位**：
  - `backend/src/main/resources/db/init.sql:458`、`deploy/db/init-scripts/schema.sql:474`：`COMMENT ON COLUMN friend_link.status IS '状态：1-正常 2-待审核 0-禁用';`
  - `backend/src/main/java/com/nanmuli/blog/application/friendlink/dto/FriendLinkDTO.java:46-49`：`@NotNull` + `@Min(value = 0)` + `@Max(value = 1)` —— **只允许 0/1**
  - `backend/src/main/java/com/nanmuli/blog/application/friendlink/command/CreateFriendLinkCommand.java:57-60`：同样 `@Min(0)/@Max(1)`（虽然这个 Command 是死代码，见 B04-03）
  - `frontend/src/views/admin/friendLink/Index.vue:172-173`、`:225-227`：前端管理页 status 也只有 "显示(1)/隐藏(0)"，**无"待审核"选项**
  - `frontend/src/api/friendLink.ts`、`frontend/src/components/common/{AppFooter,AppSidebar}.vue`：全前端 grep `申请|review|audit|待审核` 零命中（除 schema 注释），**无公开"申请友链"入口**
- **现象**：DB 注释声明 status 有 3 档（0/1/2），但前后端代码都把它当作 2 档（0/1）用，且没有任何"用户提交→待审核→管理员审核通过"的入口与流转。
- **影响**：① schema 文档与实际行为严重不符，新人/Agent 会被误导以为存在审核流；② `FriendLinkRepositoryImpl.findAllActive` 只过滤 `status=1`，即使有外部手段（直连 DB / SQL 注入）写入 status=2，前台也看不到，但 `findAll()`（管理端 list）会列出，造成管理混乱；③ 属于"看起来能用实则跑不通"的半成品（§2.5 第 4 问）。
- **根因/分析**：早期 schema 设计时按"友链申请"完整流设计，落地 MVP 时砍掉了申请入口和审核 UI，但 schema 注释未同步。已排除误判：grep 全仓库确认无 applyFriendLink/submit/申请友链 等任何路径。
- **修复方向**（二选一）：
  1. **承认现状**：把 schema 注释改为 `'状态：1-正常 0-禁用'`（删除"2-待审核"承诺），与 Project/Skill 口径统一。改动面小。
  2. **补齐闭环**：新增 `POST /api/friend-link/apply`（无需鉴权）、管理端新增"审核"操作（status 2→1）。改动面大，MVP 阶段不建议。
- **改动面**：小（方案 1）/ 大（方案 2）
- **关联**：[[B15]] schema 与代码契约漂移；横向主题 §2.6 跨服务契约一致性 / schema 漂移；次维度 [Design]

### [P3] [Arch] Skill category 字段无后端枚举校验，schema 注释约束未在代码层强制   <!-- 编号：B04-06 -->
- **定位**：
  - `backend/src/main/resources/db/init.sql:353`、`deploy/db/init-scripts/schema.sql:353`：`COMMENT ON COLUMN skill.category IS '技能分类：language-语言 framework-框架 tool-工具 other-其他';`
  - `backend/src/main/java/com/nanmuli/blog/application/skill/dto/SkillDTO.java:28-29`：`@NotBlank(message = "技能分类不能为空") private String category;` —— **无枚举校验**
  - `backend/src/main/java/com/nanmuli/blog/application/skill/command/CreateSkillCommand.java:25-26`：同样仅 `@NotBlank`
  - `frontend/src/views/admin/skill/Index.vue:30-35`：前端用 select 限制 4 个枚举值
- **现象**：schema 注释承诺 category ∈ {language, framework, tool, other}，前端用下拉强制，但后端 DTO 只校验非空。
- **影响**：① 绕过前端直接调 `/api/admin/skill`（已登录 admin）可写入任意字符串（如 `<script>`、空格、超长串）到 category；② 展示侧 `frontend/src/views/skill/*` 用 `categoryMap` 映射，未命中 key 会显示原始字符串（Vue 模板 `{{ }}` 默认转义，XSS 风险低）；③ 数据一致性：若 admin 误操作或后续接入其他客户端，会产生脏数据。考虑到本接口需 admin 登录、且仅 admin 自己维护，风险偏低。
- **根因/分析**：category 在 schema 层是 VARCHAR 而非 PG ENUM，注释只是文档约束；Java 侧未补 `@Pattern` 或自定义枚举校验注解。已排除误判：grep 确认无 EnumCheck 之类自定义校验。
- **修复方向**：
  1. 在 SkillDTO.category 加 `@Pattern(regexp = "^(language|framework|tool|other)$")`，与 schema 注释对齐
  2. 或引入 Java enum + `@JsonCreator` 反序列化校验
- **改动面**：小
- **关联**：次维度 [Security]（弱）；DDD 校验分层

### [P2] [Arch] 三个实体均无 @Version 字段，OptimisticLockerInnerInterceptor 对本模块不生效（引用 B14-03）   <!-- 编号：B04-07 -->
- **定位**：
  - `backend/src/main/java/com/nanmuli/blog/shared/domain/BaseAggregateRoot.java:14-41`：基类仅含 `id` / `createdAt` / `updatedAt` / `isDeleted`，**无 @Version 字段**
  - `backend/src/main/java/com/nanmuli/blog/domain/{project,skill,friendlink}/*.java`：三个实体均未单独声明 `@Version`
  - `backend/src/main/java/com/nanmuli/blog/infrastructure/config/db/MyBatisPlusConfig.java:28`：全局注册了 `OptimisticLockerInnerInterceptor`（说明项目预期用乐观锁）
- **现象**：MyBatis Plus 乐观锁拦截器全局开启，但 Project/Skill/FriendLink 三表均无 version 列、实体无 @Version，乐观锁对这三个聚合完全不生效。`update` 走 `updateById`，并发更新后写覆盖前写，无冲突检测。
- **影响**：单人维护场景下并发概率低，影响有限。但管理端若开两个 tab 同时编辑同一项目，后保存的会静默覆盖前一个，无报错提示。
- **根因/分析**：乐观锁基础设施已具备（拦截器注册），但实体未配合声明 @Version。这是项目级系统性问题（article/web_collect_task 等核心聚合有 version，见 V1_3/V1_4/V1_6 migration；而展示类三表 + 友链未补）。
- **修复方向**：
  1. 若展示类需要：为 project_showcase/skill/friend_link 加 version 列（migration），实体加 `@Version`
  2. 若不需要：维持现状，但应在 B14-03 统一记录"乐观锁仅覆盖核心聚合"的口径
- **改动面**：中（migration + 实体 + 测试）
- **关联**：[[B14-03]] 乐观锁覆盖范围（主模块深查）；本模块仅引用

---

## `[Deps]` 依赖升级与版本

### 本模块依赖清单（基于声明文件，未翻依赖源码）

| 依赖 | 版本 | 声明位置 | 已知风险/可升级 | 备注 |
|---|---|---|---|---|
| Spring Boot | 3.3.5 | `backend/pom.xml` | 3.3.x 维护中，可升至 3.3.6+ / 3.4.x | 本模块仅用 `@RestController`/`@Transactional`/`BeanUtils`，无高危 API |
| MyBatis Plus | 3.5.9 | `backend/pom.xml` | 3.5.x 稳定 | 本模块用 `BaseMapper`/`LambdaQueryWrapper`，无 `apply()`/`last()` |
| Lombok | （随 Spring Boot BOM） | `backend/pom.xml` | 无 | `@Data`/`@RequiredArgsConstructor` 常规用法 |
| jakarta-validation | （随 Spring Boot） | —— | 无 | `@Pattern`/`@Size`/`@Min`/`@Max`/`@NotBlank`/`@NotNull`/`@AssertTrue`/`@Email` |
| PostgreSQL JDBC Driver | （随 Spring Boot） | —— | 无 | 通过 `JsonbTypeHandler` 使用 `PGobject`（jsonb） |
| Element Plus | （随 frontend/package.json） | `frontend/package.json` | 无 | `el-table`/`el-dialog`/`el-form` 常规用法 |
| Vue 3 | （随 frontend/package.json） | `frontend/package.json` | 无 | `<script setup>` + Composition API |

> 排查范围：本模块仅使用 Spring Boot / MyBatis Plus / jakarta-validation 的常规 API，未引入模块特有依赖，未发现独立依赖风险条目。版本一致性 / CVE 问题随 X06 / F07 主模块统一处理。

---

## `[Design]` 功能设计合理性

> 必填。从真实使用出发，回答 §2.5 中相关的问题。

**审视结论**：

1. **场景适配**（§2.5-1）：对于"单人维护的技术博客"，三个展示型实体是合理的轻量门面。Project 用 JSONB 存 screenshots + techStack 充分利用了 PG 特性，无需额外表；Skill 按 category + proficiency 展示也是博客圈的常规设计。**整体适配良好，无过度设计**。但 screenshots 缺管理端 UI 输入（见下条）是"简陋到断链"。

2. **闭环完整性 / MVP 假设检验**（§2.5-2、§2.5-4）：
   - **Project screenshots 是半成品**：`frontend/src/views/admin/project/Index.vue` 的表单**没有 screenshots 输入控件**（仅 cover/techStack/URL 等），但实体 + DTO + DB + 公开详情页（`views/project/Index.vue:254-266` 的"项目截图"展示区）都齐备。结果：管理员无法通过 UI 添加截图，公开页永远显示空。这是典型的"看起来能用实则跑不通"。
   - **FriendLink 审核流是半成品**：见 B04-05。schema 承诺"待审核"，代码不可达，无申请入口。属于"砍掉了一半但没清理"。
   - 这两处共同拉低了 MVP 试用的真实体验。

3. **可运维性 / 缺失功能**（§2.5-3、§2.5-5）：三个模块均无"排序批量调整"、"可见性快速切换"、"友链失效检测"等运营小工具。单人维护场景下影响有限，但友链 logo/url 失效是常见痛点（外链 404），目前无任何检测机制——可作为未来 P4 建议项。

### [P2 / Design] [Design] Project screenshots 管理端无 UI 输入，公开展示页永远为空（功能断链）   <!-- 编号：B04-08 -->
- **定位**：
  - `frontend/src/views/admin/project/Index.vue:62-92`（handleCreate/handleEdit 表单字段，无 screenshots 控件）
  - `frontend/src/views/admin/project/Index.vue:172-348`（模板部分，dialog 表单中无截图输入区）
  - `frontend/src/views/project/Index.vue:254-266`（公开详情页"项目截图"展示区，依赖 screenshots 字段）
  - `backend/src/main/java/com/nanmuli/blog/domain/project/Project.java:26-27`（实体字段存在）
- **现象**：后端实体 / DTO / DB schema / 前端展示页都为 screenshots 留了位置，但**唯一的管理编辑入口（admin/project/Index.vue 的对话框表单）没有 screenshots 的输入控件**。`handleCreate` 初始化了 `screenshots: []`，`handleEdit` 做了 `[...row.screenshots]` 深拷贝，但模板里没有任何上传/输入 UI 把数据填进去。
- **影响**：管理员即使想添加项目截图也无法操作；公开项目详情页的"项目截图"区块永远空着（`v-if="selectedProject.screenshots?.length"` 永远 false）。是 README/CLAUDE.md 宣称"项目展示"能力下的实际断链。
- **根因/分析**：早期建好了数据通路，前端管理 UI 没补完。已排除误判：通读整个 admin/project/Index.vue 模板确认无任何 `screenshots` 相关 `el-upload`/`el-input`，仅 cover 单图上传。
- **修复方向**：
  1. 在 admin/project/Index.vue 表单加多图上传控件（可复用 `el-upload` + 已有 file 模块 B05），绑定 `form.screenshots`
  2. 或暂时从前端展示页移除"项目截图"区块，待 UI 补齐后再放出
- **改动面**：中（前端组件 + 联调 B05 文件上传）
- **关联**：[[B05]] 文件上传模块；MVP 试用稳定化方向（CLAUDE.md 第 1 项）

### [P4 / Design] [Design] 友链无失效检测 / 排序批量调整等运营小工具（记录备选）   <!-- 编号：B04-09 -->
- **定位**：`backend/src/main/java/com/nanmuli/blog/application/friendlink/FriendLinkAppService.java`（仅基础 CRUD）、`frontend/src/views/admin/friendLink/Index.vue`（仅列表 + 单条编辑）
- **现象**：友链管理只有"单条 CRUD"，无批量排序、无 URL 可达性检测、无友链回链校验。
- **影响**：长期运营下友链 URL 失效（404 / 域名过期）是常见痛点，目前只能靠管理员手动逐个点开验证。
- **建议方向**：可选地（非 MVP 范围）补一个定时任务（关联 B17 调度）周期性 HEAD 探测友链 URL，失败的在管理端打标。**当前无需调整**，列为未来 P4 建议。
- **改动面**：大（跨 B17 + 前端 + 仓储）
- **关联**：[[B17]] 调度模块；CLAUDE.md 第 5 项"运维观测"

---

## 模块小结

### 严重度统计

| 级别 | 数量 | 条目编号 |
|---|---|---|
| P0 | 0 | — |
| P1 | 0 | — |
| P2 | 3 | B04-05、B04-07（引用 B14-03）、B04-08 |
| P3 | 4 | B04-01、B04-02、B04-03、B04-04、B04-06 |
| P4 | 1 | B04-09 |

> 注：B04-07 实际归档到主模块 B14-03，本报告仅引用，编号保留以便索引页统计去重时识别。本模块**自有** P2 = B04-05、B04-08；P3 = B04-01/02/03/04/06。

### Top 风险（本模块最该先看的 ≤3 条）

1. **B04-05 FriendLink "2-待审核" schema 与代码契约脱节** —— schema 注释承诺的审核流在代码层完全不可达，是"看起来能用实则跑不通"的典型，且会误导后续开发/Agent。修复成本极小（改注释即可），收益明显。
2. **B04-08 Project screenshots 管理端无 UI 输入** —— 直接影响 MVP 试用体验，公开页"项目截图"区块永远空着。需补前端上传控件，改动面中等。
3. **B04-04 Project screenshots 后端无 URL 校验** —— 与同模块 githubUrl/demoUrl/docUrl 校验口径不一致，存在一致性差和潜在外链风险，改动面小。

### 修复优先级建议

- **立即**（P0/P1）：无
- **计划**（P2）：
  - B04-05：与 B15 schema 治理一并处理，统一 friend_link.status 语义
  - B04-08：前端补 screenshots 上传 UI（依赖 B05 文件模块）
  - B04-07：随 B14-03 统一乐观锁口径决策
- **择机**（P3/P4）：
  - B04-01：project slug 加 DB 唯一索引（与 B15 一并）
  - B04-02：删除 SkillRepository.findAllVisibleByCategory 死代码
  - B04-03：FriendLink 改用 dedicated Command（与 Project/Skill 风格对齐）
  - B04-04：screenshots 加后端 URL 校验
  - B04-06：Skill category 加枚举校验
  - B04-09：友链失效检测（未来增强）

### 排查盲区 / 待复核

- **[需查证] B04-04**：screenshots 在前端是否还有其他消费者（如 OGP 渲染、SEO meta）会影响"XSS 风险低"的定级。本次仅 grep 了 `frontend/src/views/project/Index.vue` 与 SrcImage 组件，未穷尽所有引用 `project.screenshots` 的位置（如未来可能的 SSR/OGP 链路）。建议索引页登记后由 F0x 侧复核。
- **[需查证] B04-07**：三个表是否有"曾经存在 version 列"的历史 migration 被回滚（本次仅看了 V1_3/V1_4/V1_6 为 article/web_collect_task 加 version，未深查是否有针对 project_showcase/skill/friend_link 的 version migration 草稿）。建议由 B15 主模块统一核对 migration 完整性。
- **未覆盖**：三个模块的单测情况（`backend/src/test/.../{project,skill,friendlink}/`）本次未读取，测试缺失影响归 X03 统一评估。
