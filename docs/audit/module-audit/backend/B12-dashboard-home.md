# B12 看板与首页 Dashboard / Home 排查报告

> **模块编号**：B12
> **排查范围**：Dashboard 后台聚合统计（PV/UV/文章数/项目数 + 近期文章）+ Home 公开首页并行聚合多源数据
> **基线 commit**：`6ae930098405f4d0553d96a852f3345d0f39682e`
> **工作区状态**：脏，但**未提交改动不涉及 B12 模块文件**（脏文件集中在 config/webcollector/crawler/release/risk-register，见 00-audit-plan §1.4 列表）
> **排查日期**：2026-06-23（基线约定日期）/ 报告生成 2026-06-24
> **排查人**：B12 模块排查 agent
> **状态**：待复核

---

## 模块概览

**职责**：为管理后台首页提供 PV/UV/文章/项目聚合统计 + 近期文章列表（Dashboard），为公开首页提供一次性并行拉取多源内容（文章/分类/技能/项目/日志）的聚合接口（Home），减少前端串行请求。

**关键文件**：
- `backend/src/main/java/com/nanmuli/blog/interfaces/rest/DashboardController.java:20` —— 后台看板 Controller，`/api/admin/dashboard/{stats,recent-articles}`
- `backend/src/main/java/com/nanmuli/blog/interfaces/rest/HomeController.java:30` —— 公开首页 Controller，`/api/home/aggregated`，CompletableFuture 并行 8 源
- `backend/src/main/java/com/nanmuli/blog/application/dashboard/DashboardAppService.java:19` —— 后台统计编排（60 行，4 个 count + recent articles）
- `backend/src/main/java/com/nanmuli/blog/application/dashboard/dto/DashboardStatsDTO.java:6` —— 后台统计 DTO（articleCount/projectCount/visitCount/visitorCount）
- `backend/src/main/java/com/nanmuli/blog/application/article/dto/HomeAggregatedDTO.java:14` —— 首页聚合 DTO（7 个字段 + 内嵌 SiteStatsDTO）

**对外接口 / 依赖**：
- 对外：`GET /api/admin/dashboard/stats`、`GET /api/admin/dashboard/recent-articles?limit=`、`GET /api/home/aggregated`
- 依赖（AppService）：`ArticleAppService`（listTop/listLatest/listHot/countPublished）、`CategoryAppService`（listAllActive）、`SkillAppService`（listAllVisible）、`ProjectAppService`（listAllVisible）、`DailyLogAppService`（countPublic）
- 依赖（Repository）：`ArticleRepository`（countAll/findLatestArticles）、`ArticleVisitLogRepository`（countTotalVisits）、`ArticleViewRecordRepository`（countTotalUniqueVisitors）、`ProjectRepository`（countAll）
- 依赖（表）：`article`、`article_visit_log`（PV）、`article_view_record`（UV）、`project`、`category`、`skill`、`daily_log`
- 依赖（基础设施）：`taskExecutor` Bean（`AsyncConfig`，core=3/max=8/queue=100，CallerRunsPolicy）—— 共享对象见 B17
- 依赖（鉴权）：`SaTokenConfig` 的 `/api/admin/**` 拦截器（只 `checkLogin`）—— 共享对象见 B06

**已读文件清单**（可追溯 + 暴露盲区）：
- `interfaces/rest/DashboardController.java` —— 通读
- `interfaces/rest/HomeController.java` —— 通读
- `application/dashboard/DashboardAppService.java` —— 通读
- `application/dashboard/dto/DashboardStatsDTO.java` —— 通读
- `application/article/dto/HomeAggregatedDTO.java` —— 通读
- `application/article/dto/ArticleDTO.java` —— grep 字段
- `application/article/ArticleAppService.java:283-308,430-431,443-445` —— 片段（listTop/listLatest/listHot/countPublished/normalizePublicArticleLimit）
- `infrastructure/persistence/article/ArticleRepositoryImpl.java:183-204,211-224,265-287` —— 片段（findLatestArticles/findHotArticles/countAll/countPublished/applyListProjection）
- `infrastructure/persistence/article/ArticleVisitLogMapper.java` —— 通读（PV SQL）
- `infrastructure/persistence/article/ArticleViewRecordMapper.java` —— 通读（UV SQL）
- `infrastructure/persistence/project/ProjectRepositoryImpl.java:55-73` —— 片段（countAll）
- `infrastructure/config/ai/AsyncConfig.java` —— 通读（taskExecutor 配置）
- `infrastructure/config/security/SaTokenConfig.java` —— 通读（拦截器规则）
- `deploy/db/init-scripts/schema.sql:218-247,580-606` —— 片段（article_view_record / article_visit_log 表结构与索引）
- `backend/src/main/resources/db/migration/V1_1__create_article_view_record.sql` —— 通读
- `frontend/src/api/dashboard.ts`、`frontend/src/api/home.ts` —— 通读
- `frontend/src/views/admin/Dashboard.vue` —— 通读
- `frontend/src/views/home/Index.vue:45-115` —— 片段（首页聚合调用与渲染）
- `application/dailylog/DailyLogAppService.java`、`application/category/CategoryAppService.java`、`application/project/ProjectAppService.java` —— grep 单方法（边界确认）
- `pom.xml` —— grep 版本声明

**主模块归属**：
- 本模块**深查** Dashboard/Home 自身的聚合逻辑、统计口径、并发编排。
- 对以下共享对象**只引用**（不展开，按 §8.6）：
  - 鉴权机制（Sa-Token `/api/admin/**` 只 checkLogin、无角色校验）→ 主模块 **B06**
  - `taskExecutor` 线程池配置 → 主模块 **B17**
  - `article_visit_log` / `article_view_record` 表 schema 与索引 → 主模块 **B15**（schema）+ **B01**（统计语义）
  - AES / CORS / Filter 链 / TraceId → 主模块 **B16** / **B07** / **B06**
  - 前端请求层 `request.ts` → 主模块 **F02**

---

## `[Bug]` 代码正确性与潜在缺陷

> 排查范围：DashboardAppService 4 个 count + recent articles、HomeController 8 源并行聚合、底层 Repository SQL、降级回退逻辑、limit 边界。覆盖 §2.1 的边界条件/空集合/N+1/异常传播/缓存一致性。

### [P2] [Bug] Dashboard `getRecentArticles` limit 无上限保护，可生成非法 SQL   <!-- 编号：B12-01 -->
- **定位**：`application/dashboard/DashboardAppService.java:46-50`（无 normalize）→ `infrastructure/persistence/article/ArticleRepositoryImpl.java:184-192`（`.last("LIMIT " + limit)`）
- **现象**：`DashboardController.getRecentArticles` 接收 `@RequestParam(defaultValue = "5") int limit`，**无 `@Min`/`@Max` 约束**，直接传入 `dashboardAppService.getRecentArticles(limit)`；DashboardAppService 第 47 行直接 `articleRepository.findLatestArticles(limit)` **不做任何边界归一化**；RepositoryImpl 第 190 行用 `.last("LIMIT " + limit)` 字符串拼接进 SQL。
- **影响**：
  - 传 `limit=0` → 生成 `LIMIT 0`（合法但返回空，浪费一次请求，非致命）。
  - 传 `limit=-1` 或负数 → 生成 `LIMIT -1`，PostgreSQL 报语法错误，接口 500。
  - 传 `limit=1000000` → 单次拉百万行，OOM/慢查询风险。
  - 对比：公开的 `ArticleAppService.listLatest` 第 294 行走 `normalizePublicArticleLimit`（上限 20），后台路径却完全裸奔——**同一查询两条调用路径，边界保护不一致**。
- **根因/分析**：DashboardAppService 是独立 Service，未复用 ArticleAppService 的归一化逻辑；Controller 也未用 Bean Validation。`LIMIT` 走 `int` 拼接不会被 SQL 注入（int 类型安全），但语义错误依然存在。已排除"前端写死 limit=5"作为缓解——接口可被直接调用，且 `dashboard.ts` 第 16 行 `limit=${limit}` 把调用方传入的任意值拼进 URL。
- **修复方向**：
  1. Controller 加 `@Min(1) @Max(50)` 或 `@Positive`（改动面：小）。
  2. 或 DashboardAppService.getRecentArticles 首行加 `limit = Math.max(1, Math.min(limit, 50));`（改动面：小）。
- **关联**：[[B01]]（findLatestArticles 同一方法，公开路径有保护）、横向主题"跨服务契约一致性"（前端默认 5，但接口未校验）

---

### [P2] [Bug] Home 聚合 `projectCount` 与 articleCount/dailyLogCount 口径不一致，降级后显示 0   <!-- 编号：B12-02 -->
- **定位**：`interfaces/rest/HomeController.java:63-65,82`
- **现象**：
  - `articleCount` 走独立 `articleAppService.countPublished()`（第 64 行，专门的 count 查询）。
  - `dailyLogCount` 走独立 `dailyLogAppService.countPublic()`（第 65 行，专门的 count 查询）。
  - `projectCount` 却取自 `dto.getProjects().size()`（第 82 行），**依赖 projects 列表加载完才能算**。
  - projects 源用 `safeAsync("projects", ..., List.of())`（第 63 行），失败时 `exceptionally` 返回空 List。
- **影响**：
  - 若 `projectAppService.listAllVisible()` 抛异常（DB 抖动/超时），`projects` 降级为 `List.of()`，则 `projectCount = 0` —— 首页统计区会显示"项目数 0"，**误导用户以为没有项目**，而真实项目数可能很多。
  - 而 articleCount/dailyLogCount 走独立 count 查询，失败也降级为 0，但至少是"专门去数"的语义；projectCount 是"顺便数加载到的"，**口径不一致**。
  - 首页 `Index.vue:73-75` 的数字动画会基于这个错误值展示。
- **根因/分析**：设计时为减少一次 DB 往返，复用 projects 列表的 size。但忽略了两点：①降级语义不对齐；②projects 列表本身可能因为 `listAllVisible` 的过滤条件（visible=true）而与"项目总数"语义不同（例如后台有隐藏项目）。已排除"projects 和 count 必然相等"——若 listAllVisible 有排序/分页/上限截断（本次未深查 listAllVisible 实现，标 `[需查证]`），size 会小于真实数。
- **修复方向**：
  1. 为 project 也走独立 `projectRepository.countAll()`（与 Dashboard 一致），与 articleCount/dailyLogCount 对齐（改动面：小，需在 ProjectAppService 加 `countAllVisible` 方法或复用 Repository）。
  2. 或明确接受"projectCount = 可见项目数"语义，但在 DTO 注释和前端展示文案上标注清楚（改动面：小）。
- **关联**：[[B12-07]]（缓存策略不一致也体现在这里）、[Design] 闭环完整性

---

## `[Security]` 安全漏洞

> 排查范围：Dashboard 后台接口鉴权、Home 公开聚合是否泄漏非公开内容、SQL 拼接安全、DTO 投影泄漏。逐项对照 §2.2：Sa-Token（引用 B06）、MyBatis `${}` vs `#{}`（本模块 `.last("LIMIT " + limit)` 已查）、CORS/AES/SSRF/文件上传（本模块不涉及）。

### [P2] [Security] Dashboard 后台接口仅校验登录、不校验角色，任意登录用户可见后台统计   <!-- 编号：B12-03 -->
- **定位**：`interfaces/rest/DashboardController.java:18`（`@RequestMapping("/api/admin")`）+ `infrastructure/config/security/SaTokenConfig.java:32-34`（拦截器只 `StpUtil.checkLogin()`）
- **现象**：`/api/admin/dashboard/stats` 和 `/api/admin/dashboard/recent-articles` 属于 `/api/admin/**`，被 SaInterceptor 拦截，但拦截器 handle 只调用 `StpUtil.checkLogin()`，**不校验角色/权限**（无 `@SaCheckRole("admin")` 或 `StpUtil.checkRole("admin")`）。
- **影响**：任何能登录的用户（若系统支持多用户）都能拉取后台统计数据和近期文章列表。当前是单人博客风险有限，但这是**鉴权机制一致性**的体现——所有 `/api/admin/**` 都靠 URL 前缀 + checkLogin，没有角色层（已知薄弱点）。
- **根因/分析**：与全局 B06-XX 一致，本模块不展开，只确认 Dashboard 接口**没有比其他 admin 接口更严格**，也没有更宽松（即没有被 `excludePathPatterns` 漏配）。已排除"Dashboard 数据不敏感所以无所谓"——PV/UV 和近期文章列表对运营有意义，不应让非管理员看到。
- **修复方向**：见主模块 B06（统一加角色校验层）。本模块视角：无需额外动作，跟随 B06 方案。
- **关联**：[[B06-XX]]（鉴权纯靠 URL 前缀 + checkLogin）、横向主题"鉴权机制一致性"

---

### [P3] [Security] Dashboard "最近文章"设计与实现不一致：前端支持草稿/回收站标签但后端只返回已发布   <!-- 编号：B12-04 -->
- **定位**：`application/dashboard/DashboardAppService.java:47` → `ArticleRepositoryImpl.java:187-188`（`status=1 AND is_deleted=false`）vs `frontend/src/views/admin/Dashboard.vue:59-75`（getStatusType/getStatusText 支持 status=1/2/3）
- **现象**：
  - 后端 `findLatestArticles` SQL 条件硬编码 `status=1 AND is_deleted=false`（只查已发布）。
  - 前端 Dashboard.vue 第 68-75 行 `getStatusText` 却定义了 status=1（已发布）/2（草稿）/3（回收站）三种标签。
  - 实际返回的数据 status 永远是 1，标签永远是"已发布"绿色。
- **影响**：
  - **不是数据泄漏**（草稿/回收站不会被带出，这点是安全的）。
  - 但是**后台体验断层**：管理员登录后台首页，"最近文章"区只看到已发布的，**看不到自己刚写的草稿**——而这是后台用户最想看到的（继续编辑未完成的文章）。
  - 前端预留了草稿/回收站标签渲染，说明设计意图是后台看"所有近期文章"，实现却只返回已发布，**设计与实现脱节**。
- **根因/分析**：DashboardAppService 复用了公开的 `findLatestArticles`（只返回已发布），但没有为后台单独提供"含草稿/回收站"的查询。这是复用公开查询的副作用——公开接口的过滤条件被隐式带到了后台。已排除"是有意为之"——前端标签代码证明意图是显示多状态。
- **修复方向**：
  1. 为后台新增 `findLatestArticlesForAdmin(limit)`（含 status in (1,2)，排除回收站 3），或参数化 status 过滤（改动面：小，加一个 Repository 方法）。
  2. 或删除前端多余的草稿/回收站标签代码，明确"后台首页只看已发布"（改动面：小，但失去后台价值）。
- **关联**：[Design] 闭环完整性 / 场景适配

---

## `[Arch]` 架构与技术债

> 排查范围：PV/UV 统计查询性能、count 全表扫描、缓存策略一致性、Repository 方法复用、DTO 投影。注意共享对象按 §8.6，本节只记 B12 视角。

### [P2] [Arch] PV `countTotalVisits()` 全表 COUNT(*) 无时间窗/无缓存，article_visit_log 无限增长会拖慢后台   <!-- 编号：B12-05 -->
- **定位**：`infrastructure/persistence/article/ArticleVisitLogMapper.java:22-23`（`SELECT COUNT(*) FROM article_visit_log`）+ `application/dashboard/DashboardAppService.java:37`（无 `@Cacheable`）+ `deploy/db/init-scripts/schema.sql:582-606`（表无 TTL/归档字段）
- **现象**：
  - `countTotalVisits` SQL 是 `SELECT COUNT(*) FROM article_visit_log`——**无 WHERE、无时间窗、无 is_deleted 过滤**（该表 schema 确实无 is_deleted 列，schema.sql:582-590 确认）。
  - `article_visit_log` 是 PV 流水表，每次访问都插一行，**只增不减**，schema 里没有任何 TTL/归档/分区机制。
  - DashboardAppService.getStats 第 37 行每次调用都打这个 count，**无 `@Cacheable`**。
  - 表上有 `idx_article_visit_log_article_id` / `_visit_time` / `_date` 三个索引（schema.sql:599-606），但 `COUNT(*)` 全表无法利用这些索引（PG 会做全表扫描或仅扫索引覆盖，取决于 visibility map，大数据量下不可控）。
- **影响**：
  - 博客跑半年/一年后，article_visit_log 可能几十万到百万行，每次后台首页加载都触发一次全表 COUNT，**Dashboard 加载时间随 PV 累积线性劣化**。
  - 后台用户每次刷新 Dashboard（Dashboard.vue onMounted 触发）都打全表 count，无缓存兜底。
- **根因/分析**：设计时假设 PV 表不会太大（单人博客），但没考虑长期累积。`COUNT(*)` 在 PG 上虽然比 MySQL 快（MVCC + visibility map），但仍需扫描整表的事务可见性。已排除"有索引就快"——COUNT(*) 不走 WHERE 过滤，索引加速有限。
- **修复方向**：
  1. 给 getStats 加 `@Cacheable(cacheNames="dashboard:stats", ...)`，TTL 设几分钟（改动面：小，注意 ArticleAppService 的 list 方法已有 article 缓存，需协调 cache name）。
  2. 或改用近似计数（PG 的 `pg_class.reltuples` 估算，或维护一个独立的 `visit_daily_summary` 汇总表）（改动面：中，需 B01/B15 配合）。
  3. article_visit_log 加分区或定期归档（改动面：大，涉及 B15 schema + 运维）。
- **关联**：[[B01]]（PV/UV 统计语义主模块）、[[B15]]（表结构）、[[B12-07]]（缓存策略不一致）

---

### [P2] [Arch] UV `COUNT(DISTINCT visitor_id)` 全表 distinct，大数据量下性能不可控   <!-- 编号：B12-06 -->
- **定位**：`infrastructure/persistence/article/ArticleViewRecordMapper.java:19-20`（`SELECT COUNT(DISTINCT visitor_id) FROM article_view_record WHERE is_deleted = false`）+ `db/migration/V1_1__create_article_view_record.sql:26-28`（visitor_id 部分索引）
- **现象**：
  - UV 统计 SQL 用 `COUNT(DISTINCT visitor_id)`，需扫描 `is_deleted=false` 的全部行并去重计数。
  - 有 `idx_article_view_record_visitor_id`（部分索引，`WHERE is_deleted=FALSE`），但 **`COUNT(DISTINCT)` 不保证走索引**——PG 计划器可能选择全表扫描后排序去重，取决于行数和统计信息。
  - `article_view_record` 虽然有唯一约束 `uk_article_visitor(article_id, visitor_id)`（V1_1:17-19）限制了行数上限（每文章每访客一行），但仍会随文章数 × 访客数增长。
  - DashboardAppService 第 40 行每次调用都打，无缓存。
- **影响**：与 B12-05 同理，UV 统计随数据增长劣化，且 `DISTINCT` 比 `COUNT(*)` 更重（需排序/哈希去重）。后台 Dashboard 加载会变慢。
- **根因/分析**：UV 本质是"独立访客数"，DISTINCT 是正确语义，问题在于没有汇总层缓存这个结果。已排除"用 HyperLogLog"——那需要 PG 扩展或应用层估算，当前实现是精确计数。
- **修复方向**：与 B12-05 共用方案（getStats 加 @Cacheable + TTL）；或维护独立的 visitor_count 汇总表（改动面：中）。
- **关联**：[[B12-05]]、[[B01]]、[[B15]]

---

### [P3] [Arch] DashboardAppService 完全无 @Cacheable，与 ArticleAppService 同类查询的缓存策略不一致   <!-- 编号：B12-07 -->
- **定位**：`application/dashboard/DashboardAppService.java:19`（类上无 `@CacheConfig`，方法无 `@Cacheable`）vs `application/article/ArticleAppService.java:282,292,302`（listTop/listLatest/listHot 都有 `@Cacheable(cacheNames="article", key=...)`）
- **现象**：
  - Home 聚合调 ArticleAppService.listLatest/listTop/listHot，**能命中 article 缓存**（key=`latest-5`/`top-3`/`hot-5`）。
  - Dashboard 的 `getStats()`（4 个 count）和 `getRecentArticles()`（findLatestArticles）**完全无缓存**，每次后台刷新都打 DB。
  - 更微妙：Dashboard 的 recent-articles 和 Home 的 latest 都走 `findLatestArticles(5)`，但 Home 路径走 ArticleAppService（有缓存），Dashboard 路径走 DashboardAppService（无缓存）——**同一个底层查询，缓存命中情况取决于调用路径**。
- **影响**：后台 Dashboard 加载比 Home 首页更耗 DB（Home 命中缓存，Dashboard 不命中）。统计 count 更重，每次都全表。
- **根因/分析**：DashboardAppService 是独立 Service，没复用 ArticleAppService 的缓存注解。属于缓存策略碎片化。
- **修复方向**：
  1. DashboardAppService.getStats 加 `@Cacheable(cacheNames="dashboard", key="'stats'")`，TTL 5-10 分钟（改动面：小）。
  2. getRecentArticles 直接改为调用 ArticleAppService.listLatest（复用缓存），删除 DashboardAppService 里重复的 toArticleDTO 逻辑（改动面：小，但需注意 Dashboard 想看含草稿的文章，见 B12-04）。
- **关联**：[[B12-05]]、[[B12-06]]、[[B12-08]]、[Arch] 缓存策略一致性

---

### [P3] [Arch] Dashboard 与 Home 重复调用 findLatestArticles，缓存不复用 + toArticleDTO 逻辑分叉   <!-- 编号：B12-08 -->
- **定位**：`application/dashboard/DashboardAppService.java:46-59`（自有 toArticleDTO）vs `application/article/ArticleAppService.java:293-299,298`（batchConvertToDTO）
- **现象**：
  - Dashboard.getRecentArticles 第 47 行调 `articleRepository.findLatestArticles(limit)` 后用**自有的 `toArticleDTO`**（第 52-59 行，`BeanUtils.copyProperties` + 手动 set id/createTime/updateTime）。
  - Home 路径的 ArticleAppService.listLatest 第 298 行调同一个 `findLatestArticles` 但用 **`batchConvertToDTO`**（ArticleAppService 内部的批量转换）。
  - 两套 DTO 转换逻辑并存。
- **影响**：
  - 两条路径的 DTO 字段填充可能不一致（Dashboard 的 toArticleDTO 没填 category/categoryPath，而 batchConvertToDTO 可能填——需查证 ArticleAppService.batchConvertToDTO 实现，标 `[需查证]`）。
  - 维护成本：改 ArticleDTO 转换逻辑要同步改两处。
  - 缓存不复用（见 B12-07）。
- **根因/分析**：DashboardAppService 没复用 ArticleAppService 的转换方法，自己写了一套精简版。属于代码重复。
- **修复方向**：Dashboard.getRecentArticles 改为委托 ArticleAppService.listLatest（或新增 listLatestForAdmin），删除自有 toArticleDTO（改动面：小，但与 B12-04 的"后台看草稿"需求耦合）。
- **关联**：[[B12-04]]、[[B12-07]]

---

## `[Deps]` 依赖升级与版本

### 本模块依赖清单（基于声明文件，未翻依赖源码）

| 依赖 | 版本 | 声明位置 | 已知风险/可升级 | 备注 |
|---|---|---|---|---|
| Spring Boot | 3.3.5 | `backend/pom.xml`（parent） | 可升至 3.3.x 最新补丁 / 3.4.x | B12 用到 @Transactional/@Cacheable/CompletableFuture，均为稳定 API，升级风险低 |
| Java | 21 | `pom.xml` `<java.version>` | LTS，当前合适 | CompletableFuture.supplyAsync 用法兼容 |
| MyBatis Plus | 3.5.9 | `pom.xml` `<mybatis-plus.version>` | 可升至 3.5.12+ | B12 用 selectCount/LambdaQueryWrapper/.last()，API 稳定 |
| Sa-Token | 1.44.0 | `pom.xml` `<sa-token.version>` | 见 B06 | B12 只是被拦截，不直接调用 StpUtil |
| Lombok | （随 Spring Boot） | `pom.xml` | — | @Data/@Slf4j 用在 DTO/Controller |
| Spring Cache (Redis) | 随 Spring Boot | `BlogApplication.java:12 @EnableCaching` + `CacheConfig.java` | — | DashboardAppService 未用，ArticleAppService 用 |

> 排查范围：本节覆盖 B12 直接或间接用到的依赖（基于 pom.xml 声明 + 代码使用方式）。本模块**无独有依赖**，全部继承 Spring Boot starter + MyBatis Plus + Sa-Token，未引入新库。未发现 B12 特有的依赖风险。

### 未发现 B12 特有的 [Deps] 问题
依赖升级风险与本模块无强相关（升级决策归 X06/B16 全局视角）。本模块用的都是稳定 API，升级路径平滑。标 `[需查证]`：Spring Boot 3.3→3.4 对 `CompletableFuture.allOf().join()` 行为无影响（标准 JDK API），但 `@Cacheable` 在 Spring Cache 抽象层，需 X06 确认 Redis 版本兼容。

---

## `[Design]` 功能设计合理性

> **必填**。从真实使用出发，回答 §2.5 中相关的问题（至少 2 个）。本模块回答"场景适配""闭环完整性""可运维性"。

**审视结论**：

1. **场景适配**（§2.5-1/6）：单人维护的技术博客场景下，Home 首页一次 `/api/home/aggregated` 聚合 8 源是**合理的设计**（避免前端 8 次串行请求，提升首屏速度），并行编排用 `safeAsync` + fallback 降级是正确思路。但 Dashboard 后台只聚合 4 个 count + 1 个文章列表，且 Dashboard.vue 第 79 行用 `Promise.all([fetchStats, fetchRecentArticles])` 发两次请求——**本可以合并成一个 `/api/admin/dashboard/aggregated` 接口**，减少一次 HTTP 往返。当前实现 Home 聚合很彻底，Dashboard 却退化为两个独立接口，前后端风格不统一。

2. **闭环完整性**（§2.5-2）：Dashboard 的"最近文章"只显示已发布（B12-04），管理员登录后**看不到草稿**，闭环断了——后台首页本应是"继续未完成工作"的入口，现在却只展示对外公开的内容，失去后台价值。建议后台 recent-articles 含草稿。另外，Dashboard 没有"今日 PV/UV"卡片（ArticleVisitLogMapper 第 25 行已有 `countTodayVisits` 方法但 Dashboard 没调用），数据已采集未展示，闭环不完整。

3. **可运维性**（§2.5-3）：Home 聚合的 `safeAsync` 失败时只 `log.warn`（HomeController:92）并返回 fallback，**没有埋点/告警**——8 个源中某个持续失败（如 Skill 表锁等待超时），运维无感知，首页会静默降级（某区块为空）。单人博客阶段可接受，但缺少"降级发生"的可见性。Dashboard 的 PV/UV 是全表 count（B12-05/06），**无缓存无近似**，长期运行后 Dashboard 加载会变慢，且没有监控指标暴露这个延迟。

### [P4] [Design] Dashboard 可合并为单一聚合接口，与 Home 风格统一   <!-- 编号：B12-09 -->
- **定位**：`interfaces/rest/DashboardController.java:24-33`（两个独立端点）+ `frontend/src/views/admin/Dashboard.vue:79`（Promise.all 两次请求）
- **现象**：Dashboard 拆成 `/stats` 和 `/recent-articles` 两个接口，前端发两次请求；Home 却是单一 `/aggregated` 一次拿全。
- **影响**：后台加载多一次 HTTP 往返；前后端聚合风格不统一；Dashboard.vue 的 `Promise.all` 任一失败只各自 ElMessage，不能整体降级。
- **建议方向**：合并为 `/api/admin/dashboard/aggregated`（返回 stats + recentArticles），与 Home 风格对齐（改动面：小）。**无需调整**也可接受，列为优化建议。
- **关联**：[Design] 场景适配 / 交互合理性

### [P4] [Design] Dashboard 未展示"今日 PV/UV"，已采集数据未上墙   <!-- 编号：B12-10 -->
- **定位**：`infrastructure/persistence/article/ArticleVisitLogMapper.java:25`（`countTodayVisits` 已定义但未被 DashboardAppService 调用）
- **现象**：Mapper 里有现成的今日统计方法，Dashboard 只展示了累计 PV/UV，没有"今日"维度。
- **影响**：管理员看不到当天流量趋势，后台首页信息密度不足。
- **建议方向**：DashboardStatsDTO 增加今日 PV/UV 字段，调用 countTodayVisits（改动面：小）。**无需调整**也可接受，列为功能增强建议。
- **关联**：[Design] 闭环完整性

---

## 模块小结

### 严重度统计

| 级别 | 数量 | 条目编号 |
|---|---|---|
| P0 | 0 | — |
| P1 | 0 | — |
| P2 | 4 | B12-01, B12-02, B12-03, B12-05, B12-06 |
| P3 | 3 | B12-04, B12-07, B12-08 |
| P4 | 2 | B12-09, B12-10 |

> 注：P2 计 5 条（B12-01/02/03/05/06），表格中"4"为笔误更正——实际 P2 = 5 条。

### 修正统计

| 级别 | 数量 | 条目编号 |
|---|---|---|
| P0 | 0 | — |
| P1 | 0 | — |
| P2 | 5 | B12-01, B12-02, B12-03, B12-05, B12-06 |
| P3 | 3 | B12-04, B12-07, B12-08 |
| P4 | 2 | B12-09, B12-10 |

### Top 风险（本模块最该先看的 ≤3 条）

1. **B12-05 / B12-06 PV/UV 全表 count 无缓存** —— 博客长期运行后 Dashboard 加载随数据线性劣化，且每次刷新都打全表，是本模块最值得修的性能隐患。
2. **B12-01 Dashboard getRecentArticles limit 无保护** —— 可生成非法 SQL 导致 500，虽需构造请求触发，但修复成本极低（一行 normalize），性价比高。
3. **B12-03 Dashboard 接口仅 checkLogin 不校验角色** —— 鉴权薄弱点（归属 B06），本模块确认 Dashboard 未漏配也未加强，跟随 B06 统一方案。

### 修复优先级建议

- **立即**（P0/P1）：无。本模块无阻断或高危问题。
- **计划**（P2）：
  - B12-01：DashboardAppService.getRecentArticles 加 limit 归一化（1 行，改动面小）。
  - B12-05/06/07：DashboardAppService.getStats 加 `@Cacheable` + TTL 5-10 分钟（改动面小，与 B01 协调 cache name）。
  - B12-02：projectCount 改走独立 count，与 articleCount/dailyLogCount 口径对齐（改动面小）。
  - B12-03：跟随 B06 鉴权方案，本模块不单独处理。
- **择机**（P3/P4）：
  - B12-04：后台 recent-articles 改为含草稿（改动面小，需新增 Repository 方法）。
  - B12-08：Dashboard 委托 ArticleAppService，消除重复 toArticleDTO（改动面小，与 B12-04 耦合）。
  - B12-09/10：Dashboard 合并接口、展示今日 PV/UV（功能增强，非必须）。

### 排查盲区 / 待复核

- **[需查证] B12-02**：`ProjectAppService.listAllVisible()`（ProjectAppService.java:89）的实现是否有排序/分页/上限截断？若有，`dto.getProjects().size()` 会小于真实项目数，projectCount 口径问题更严重。本次只 grep 了方法签名，未读方法体。
- **[需查证] B12-08**：`ArticleAppService.batchConvertToDTO` 是否填充 category/categoryPath？若填充，则 Dashboard 的 toArticleDTO（不填）与 Home 路径的 DTO 字段不一致，前端渲染可能出差异。本次未读 batchConvertToDTO 实现。
- **[需查证] B12-05**：PG 在 article_visit_log 上的 `COUNT(*)` 实际执行计划（是否走 index-only scan）取决于 visibility map 和 ANALYZE 统计，需运行时 `EXPLAIN` 确认，本次只读静态 SQL 无法断定。
- **盲区**：Home 聚合的 8 个源里，CategoryAppService.listAllActive / SkillAppService.listAllVisible / DailyLogAppService.countPublic 是否有 `@Cacheable`，本次只 grep 了部分，未逐一确认缓存覆盖（影响 Home 首屏实际 DB 压力评估）。
- **盲区**：B12 零测试覆盖（`backend/src/test` 无 Dashboard/Home 测试类），统计口径正确性完全无自动化验证——但这是全局 X03 问题，本模块不单独展开。
