# B01 文章 Article 排查报告

> **模块编号**：B01
> **排查范围**：文章 CRUD / 归档 / Top 置顶 / 浏览统计（UV/PV）/ 草稿 / 发布事件 / slug / 摘要 / 阅读时间。关键文件见下。
> **基线 commit**：`6ae930098405f4d0553d96a852f3345d0f39682e`
> **工作区状态**：脏（工作区有未提交改动，但**均与本模块无关**：`ConfigRepositoryImpl.java`、`WebCollectPageMapper.java`、`crawler-service/*`、`deploy/README.md`、`docs/audit/full-project-risk-register.md`、`scripts/release/release-gate.ps1`、新增 `backend/src/test/.../webcollector/`；本模块所有相关文件均为 HEAD 版本未改动）
> **排查日期**：2026-06-23
> **排查人**：B01 模块排查 agent
> **状态**：完成

---

## 模块概览

**职责**：管理博客文章的完整生命周期（创建/草稿/发布/编辑/软删除/归档/置顶），并对外暴露公开阅读接口（列表、详情、统计、归档）和管理接口（增删改查），同时记录文章的浏览统计（UV 去重 + PV 流水）。

**关键文件**：
- `backend/src/main/java/com/nanmuli/blog/application/article/ArticleAppService.java:1-634` —— 应用服务，文章全流程编排（事务、缓存、事件、统计、批量查询）
- `backend/src/main/java/com/nanmuli/blog/interfaces/rest/ArticleController.java:1-116` —— REST 控制器，公开 `/api/article/**` + 管理 `/api/admin/article/**`
- `backend/src/main/java/com/nanmuli/blog/domain/article/Article.java:1-71` —— 文章聚合根（含 `@Version` 乐观锁、状态流转、字数/阅读时间计算）
- `backend/src/main/java/com/nanmuli/blog/infrastructure/persistence/article/ArticleRepositoryImpl.java:1-288` —— 仓储实现（FTS/trigram 搜索、列表投影、分类计数）
- `backend/src/main/java/com/nanmuli/blog/infrastructure/persistence/article/ArticleMapper.java:1-146` —— MyBatis Mapper，含 `searchPublishedByFts` / `searchAllByFts` / `searchPublishedByTrigram` SQL
- `backend/src/main/java/com/nanmuli/blog/infrastructure/persistence/article/ArticleViewRecordRepositoryImpl.java:1-69` —— UV 记录仓储
- `backend/src/main/java/com/nanmuli/blog/infrastructure/persistence/article/ArticleVisitLogRepositoryImpl.java:1-62` —— PV 日志仓储
- `backend/src/main/java/com/nanmuli/blog/application/event/ArticleEventHandler.java:1-97` —— 文章发布事件异步处理（AI 标签/摘要/向量，详见 B13）

**对外接口 / 依赖**：
- 对外 Controller：`/api/article/list|{slug}|top|count|archive|{id}/record-view|{id}/stats`、`/api/admin/article/{id}|list`
- 依赖模块：`CategoryRepository`（叶子校验、父子路径、计数刷新）、`MarkdownUtil`（HTML 渲染、摘要、XSS 净化）、`Sa-Token`（admin 操作鉴权，归 B06）、`AiService`（发布事件，归 B13）
- 依赖表：`article`、`article_view_record`、`article_visit_log`、`article_draft`（**仅建表，无代码引用**）、`category`
- 依赖配置：`blog.cache.ttl.article*`（缓存 TTL，`CacheConfig`）

**已读文件清单**：
- `application/article/ArticleAppService.java` —— 通读（634 行）
- `interfaces/rest/ArticleController.java` —— 通读
- `domain/article/Article.java` / `ArticleId.java` / `ArticleStatus.java` / `ArticleViewRecord.java` / `ArticleVisitLog.java` / `ArticleRepository.java` —— 通读
- `domain/article/event/ArticleCreatedEvent.java` / `ArticlePublishedEvent.java` —— 通读
- `application/article/command/{Create,Update,RecordArticleView}Command.java` —— 通读
- `application/article/dto/ArticleDTO.java` / `ArticleStatsDTO.java` / `ArticleArchiveDTO.java` / `query/ArticlePageQuery.java` —— 通读
- `infrastructure/persistence/article/{ArticleRepositoryImpl,ArticleMapper,ArticleViewRecordRepositoryImpl,ArticleVisitLogRepositoryImpl,ArticleViewRecordMapper,ArticleVisitLogMapper}.java` —— 通读
- `application/event/ArticleEventHandler.java` —— 通读
- `shared/domain/BaseAggregateRoot.java` / `shared/util/MarkdownUtil.java` / `shared/query/BasePageQuery.java` —— 通读
- `infrastructure/config/security/SaTokenConfig.java` / `infrastructure/config/cache/CacheConfig.java` / `infrastructure/config/ai/AsyncConfig.java` —— 通读
- `db/init.sql` / `deploy/db/init-scripts/schema.sql` / `db/migration/V1_1*` / `V1_11*` / `sql/article_visit_stats.sql` / `sql/article_view_record.sql` —— 片段读取（article 相关表 + 索引）

**主模块归属**：本模块是 `article` / `article_view_record` / `article_visit_log` / `article_draft` 表的**业务消费方**（schema 定义本身归 **B15** 深查，本报告只引用编号）。对其他共享对象**只引用**：Sa-Token 鉴权（B06）、AES（B07）、`CrawlerTaskClient`（B10）、AI 空壳链路 NoOpAiService/ArticleEventHandler/article_vector（B13）、slug 唯一约束 schema 双索引（B15）、`@Version` 乐观锁是否真生效（B14-03）。

---

## `[Bug]` 代码正确性与潜在缺陷

> 排查范围：`ArticleAppService` 全方法事务/缓存/事件边界、`Article` 状态机、`ArticleRepositoryImpl` 查询、`ArticleEventHandler` 异步副作用、DTO 映射。

### [P1] [Bug] `article:stats` 缓存 evict key 与 cacheable key 不匹配，统计缓存永不被失效  <!-- 编号：B01-01 -->
- **定位**：`backend/src/main/java/com/nanmuli/blog/application/article/ArticleAppService.java:397`（写入 key） vs `:146` / `:317`（evict key）
- **现象**：
  - 写入：`getArticleStats` 用 `@Cacheable(cacheNames="article:stats", key="'public-' + #articleId")`（行 397），生成的 Redis key 是 `article:stats::public-123`
  - 失效：`update`（行 146）用 `@CacheEvict(cacheNames="article:stats", key="#command.articleId")`，生成的 key 是 `article:stats::123`；`delete`（行 317）用 `key="#id"`，同样是 `article:stats::123`
  - 两侧 key 前缀不一致（`public-` vs 无前缀），evict 永远 miss
- **影响**：文章被编辑（标题/slug 变更）或删除后，`/api/article/{id}/stats` 仍返回旧统计（标题、slug），直至 TTL 5 分钟（`CacheConfig.TtlProperties.articleStats=Duration.ofMinutes(5)`）自然过期。删除场景更严重：文章已软删除，stats 缓存 5 分钟内仍可被公开接口读到（虽 `loadPublishedArticleForPublic` 会二次校验状态，但缓存 DTO 里 title/slug 仍是旧值，前端展示与实际不符）。
- **根因/分析**：缓存 key 拼接时人为遗漏前缀。已排除"故意用不同 key 分桶"的可能——两者 cacheName 完全相同，逻辑上就是想 evict 同一条目。
- **修复方向**：
  1. 统一 key：evict 也加 `'public-'` 前缀（改动面 **小**）
  2. 或改用 `allEntries=true`（简单但牺牲一点命中率）（改动面 **小**）
- **关联**：次维度 `[Bug]`；配置项 `blog.cache.ttl.articleStats`

### [P1] [Bug] 草稿→发布经 `update` 路径不触发 `ArticlePublishedEvent`，AI 摘要/标签/向量链路断裂  <!-- 编号：B01-02 -->
- **定位**：`backend/src/main/java/com/nanmuli/blog/application/article/ArticleAppService.java:149-208`（`update` 方法）
- **现象**：
  - `create`（行 127-135）在 `article.isPublished()` 时发布 `ArticlePublishedEvent`
  - `update`（行 180-190）虽然检测了 `wasPublished`，但**仅**在 `!wasPublished` 时设置 `publishTime`，**从不发布** `ArticlePublishedEvent`，也未发 `ArticleCreatedEvent`
  - 即"草稿保存后，后续编辑时切换为已发布（status=1）"这一常见路径，完全跳过 AI 处理
- **影响**：草稿→发布是最自然的写作流程，但此路径下 `ArticleEventHandler`（B13）不会被唤醒，AI 摘要（仅当 summary 为空时填充）、标签、向量全部缺失。结合 B13 的 NoOpAiService 现状影响被掩盖（当前 AI 本就是空壳），但一旦 B13 落地真实实现，此 bug 立即显现为"草稿发布后无 AI 增强"。
- **根因/分析**：`update` 的状态流转逻辑只关心 `publishTime` 字段，遗漏了事件发布。已排除"刻意不发"的可能——`create` 路径明确发了。
- **修复方向**：在 `update` 中检测 `!wasPublished && 新 status==1`，发布 `ArticlePublishedEvent`（需注意 `@Transactional` + `@Async` 事件的事务提交时机，建议用 `TransactionalEventListener` AFTER_COMMIT）（改动面 **小**，单文件）
- **关联**：[[B13]]（AI 空壳链路主模块）；横向主题"AI 空壳链路"

### [P2] [Bug] `update` 用 `BeanUtils.copyProperties` 覆盖 slug，但无冲突处理且不查 `existsBySlugAndIdNot`  <!-- 编号：B01-03 -->
- **定位**：`backend/src/main/java/com/nanmuli/blog/application/article/ArticleAppService.java:168`（`BeanUtils.copyProperties(command, article)`）
- **现象**：
  - `UpdateArticleCommand` 含 `slug` 字段（`UpdateArticleCommand.java:32`），`BeanUtils.copyProperties` 会把 command.slug 直接覆盖到 article
  - `update` 方法**没有**调用 `articleRepository.existsBySlugAndIdNot()`（该方法在 `ArticleRepositoryImpl.java:57-63` 已实现但**无任何调用方**，grep 确认）
  - 若用户提交已存在的 slug，靠 DB 的部分唯一索引（`idx_article_slug_active`，B15-01）抛 `DuplicateKeyException`，但 `update` 只 catch 了 `OptimisticLockingFailureException`（行 194），`DuplicateKeyException` 会以 500 错误冒泡到 `GlobalExceptionHandler`
  - 另外 `create` 路径生成随机 UUID slug（行 80），**完全忽略**用户传入的 `command.slug`（`CreateArticleCommand.slug` 字段成了死参数）
- **影响**：
  - 编辑文章改 slug 冲突时，用户得到 500 而非友好提示
  - `CreateArticleCommand.slug` 接受了正则校验却从不使用，用户填了 SEO slug 也会被 UUID 覆盖（功能名实亡）
  - slug 变更后 `/api/article/{slug}` 缓存（`getBySlug` 的 `@Cacheable`）不会被 `update` 的 evict 清除——`update` 只 evict `article`/`article:list` 等，但 `getBySlug` 的 key 是 `'published-slug-' + #slug`（行 211），**旧 slug 的缓存条目无法被新 slug 触发的 evict 命中**（allEntries=true 对 `article` cache 是生效的，但 `'published-slug-' + oldSlug` 这个 key 在 `article` cache 里，allEntries 会清掉——**此处 evict 实际是覆盖到的**，已排除误判）
- **根因/分析**：`BeanUtils.copyProperties` 的粗粒度覆盖 + 缺少应用层 slug 冲突预检。`existsBySlugAndIdNot` 实现了却没接上是明显的遗漏。
- **修复方向**：
  1. `update` 中显式处理 slug：若 command.slug 非空且与原值不同，调用 `existsBySlugAndIdNot` 预检并抛 `BusinessException`（改动面 **小**）
  2. `create` 决定 slug 策略：要么用用户传入的（预检唯一），要么删除 `CreateArticleCommand.slug` 字段（改动面 **小**）
- **关联**：[[B15-01]]（slug 唯一约束 schema）；次维度 `[Bug]`

### [P2] [Bug] `recordView` 公开接口无鉴权、无 visitorId 校验、无频次限制，PV/UV 可被刷量污染  <!-- 编号：B01-04 -->
- **定位**：`backend/src/main/java/com/nanmuli/blog/interfaces/rest/ArticleController.java:82-93` + `ArticleAppService.java:343-383`
- **现象**：
  - `POST /api/article/{articleId}/record-view` 不在 `/api/admin/**`，Sa-Token 拦截器（`SaTokenConfig.java:33`）不拦截
  - `visitorId` 由前端 localStorage 生成（`ArticleViewRecord.java:24` 注释），后端仅 `@NotBlank` 校验（`RecordArticleViewCommand.java:12`），任意客户端可提交任意 visitorId
  - 每次请求：① 往 `article_visit_log` 插一行（PV +1，无上限）；② 若是新 visitorId，`article_view_record` 插一行（UV +1）并 `increaseViewCount`
  - 无 IP 频次限制、无 UA 校验、无 visitorId 格式约束（UUID 形态未强制）
- **影响**：
  - 攻击者用随机 visitorId 循环调用，可无限抬高任意文章的 UV/PV/`view_count`，污染首页"热门文章"排序（`findHotArticles` 按 `viewCount` 排序）
  - `article_visit_log` 无清理任务（见 B01-06），刷量直接放大表膨胀
- **根因/分析**：浏览统计接口本质是公开的，但完全信任客户端生成的 visitorId 是设计薄弱点。已排除"有意放开水位"的可能——没有任何速率限制兜底。
- **修复方向**：
  1. 对 visitorId 加格式校验（UUID/固定长度）+ 对单 IP 单文章加滑动窗口限流（改动面 **中**）
  2. 或用服务端 fingerprint（IP+UA hash）作为 visitorId 兜底，降低客户端伪造空间（改动面 **中**）
- **关联**：次维度 `[Security]`；[[B06]]（限流机制主模块）；横向主题"鉴权一致性"

### [P2] [Bug] `update` 的乐观锁 catch 只对 `Article` 实体，分类计数刷新无并发保护  <!-- 编号：B01-05 -->
- **定位**：`backend/src/main/java/com/nanmuli/blog/application/article/ArticleAppService.java:192-207` + `:489-500`
- **现象**：
  - `update` catch `OptimisticLockingFailureException`（行 194）处理 article 本体的并发，但随后 `refreshCategoryArticleCount`（行 489-500）对 category 做 read-modify-write（查 count → setArticleCount → save），category 也有 `@Version`（归 B14），并发刷新同分类会触发 `OptimisticLockingFailureException`，**此处未 catch**，会以 500 冒泡
  - `create`（行 119-121）和 `delete`（行 333-337）同样调用 `refreshCategoryArticleCount`，同样无保护
- **影响**：单人博客场景并发概率低，但批量导入/自动采集转文章（B08）并发写同一分类时，分类计数刷新失败会导致请求 500，尽管文章本身已成功写入（事务会回滚，但 article 已 insert，产生不一致表象）。
- **根因/分析**：`refreshCategoryArticleCount` 是内联的 read-modify-write，未考虑 category 自身的乐观锁。`countByCategoryId` 本可直接用 SQL 原子更新（`UPDATE category SET article_count = (SELECT COUNT(*)...)`），绕过乐观锁。
- **修复方向**：改用 SQL 原子更新分类计数，或在 `refreshCategoryArticleCount` 内 catch 乐观锁失败并重试（改动面 **小**）
- **关联**：[[B14-03]]（乐观锁主模块）；[[B02]]（Category 模块）

### [P3] [Bug] `getArticleStats` 与公开详情用 `loadPublishedArticleForPublic`，但 `getById`（admin）不校验状态可读草稿/回收站 —— 此为预期，确认覆盖  <!-- 编号：B01-06 -->
- **定位**：`backend/src/main/java/com/nanmuli/blog/application/article/ArticleAppService.java:434-441` vs `:219-224`
- **现象**：
  - 公开路径 `getBySlug`（行 212-217）：`filter(Article::isPublished)` 过滤草稿/回收站 ✅
  - 公开路径 `getArticleStats` / `recordView`（行 347 / 399）：`loadPublishedArticleForPublic` 抛异常屏蔽未发布 ✅
  - 管理路径 `getById`（行 220-224）：不校验状态，admin 可读任意状态（**预期**）
  - 公开列表 `listPublished`（行 247）：repository 层 `status=1` 过滤 ✅
  - 管理列表 `listAll`（行 227-243）：`findAllPage` 不过滤状态（**预期**）
- **影响**：经逐路径核对，**公开接口不会泄漏草稿/回收站内容**。此条作为覆盖度确认记录，非问题。
- **根因/分析**：状态过滤分散在 application + repository 两层，未来新增公开接口需注意保持一致。
- **修复方向**：无需修复。建议抽取 `loadPublishedArticleForPublic` 为公开路径统一前置（改动面 **小**，可选）
- **关联**：次维度 `[Security]`（信息泄漏覆盖度确认）

### [P3] [Bug] `ArticleAppService.java:602` 存在疑似乱码/占位注释  <!-- 编号：B01-07 -->
- **定位**：`backend/src/main/java/com/nanmuli/blog/application/article/ArticleAppService.java:602`
- **现象**：`toCategoryDTO` 方法内有一行注释 `// XSS963262a4Ff1a5bf952067c7b540d79f08fdb884cHTML8f6c4e49`，明显是异常字符序列，疑似某次替换/合并事故残留。
- **影响**：仅为注释，不影响运行。但读代码者会困惑，且字符模式可疑（含类 hash 串），建议确认为何产生。
- **根因/分析**：[需查证] 来源不明，可能是 `XSS防护` 注释被错误替换。`git blame` 可追溯。
- **修复方向**：恢复为 `// XSS防护：转义分类名中的HTML`（改动面 **小**）
- **关联**：次维度 `[Arch]`（代码可读性）

### [P3] [Bug] `calculateWordCount` 把 Markdown 源码当纯文本计字数，与 `extractText` 摘要口径不一致  <!-- 编号：B01-08 -->
- **定位**：`backend/src/main/java/com/nanmuli/blog/domain/article/Article.java:65-70` vs `MarkdownUtil.extractText:84-104`
- **现象**：
  - `calculateWordCount`：`content.replaceAll("\\s+", "").length()`，**直接对原始 Markdown 计数**，包含 `#`、`*`、`` ` ``、`[]()`、`|` 等标记符号
  - `extractText`（摘要用）：先剥离 Markdown 标记再取纯文本
  - 两者口径不一致，字数偏大（含标记），`readingTime = wordCount / 300` 也跟着偏大
- **影响**：阅读时间显示偏高（技术博客 Markdown 标记密度高，偏差可达 10-20%）。功能性体验问题，非正确性 bug。
- **根因/分析**：`calculateWordCount` 在 domain 层无法依赖 `MarkdownUtil`（避免领域层依赖工具类），所以用了简陋实现。
- **修复方向**：在 application 层调用 `markdownUtil.extractText` 后再计字数，或在 domain 注入纯文本（改动面 **小**）
- **关联**：无

---

## `[Security]` 安全漏洞

> 排查范围：逐项覆盖计划 §2.2 技术栈重点（Sa-Token 路由 / MyBatis `${}`vs`#{}` / Cookie+CSRF / CORS / AES / SSRF / 文件上传 / 双向 key）。

### [P2] [Security] MyBatis Plus `LambdaQueryWrapper.last("LIMIT " + limit)` 存在潜在 SQL 拼接，但参数为 int 不可注入（确认安全）  <!-- 编号：B01-09 -->
- **定位**：`backend/src/main/java/com/nanmuli/blog/infrastructure/persistence/article/ArticleRepositoryImpl.java:136` / `:190` / `:202`
- **现象**：`findTopArticles` / `findLatestArticles` / `findHotArticles` 用 `.last("LIMIT " + limit)`，limit 是 `int` 类型，由 `normalizePublicArticleLimit`（`ArticleAppService.java:443-445`）夹逼到 `[0,20]`。
- **影响**：参数为基本类型 int，无法承载 SQL 注入 payload（编译期类型保证）。**确认安全**，此条作为覆盖度记录。
- **根因/分析**：`last()` 本身是字符串拼接 API，但输入是 int，无注入面。归档到 §2.2 覆盖确认。
- **修复方向**：无需修复。若未来 limit 来源变为 String，需改用 `#{}` 参数化（改动面 **小**）
- **关联**：次维度 `[Security]`；[[B14]]（数据访问层主模块）

### 逐项覆盖结论（无单独条目）

- **MyBatis `${}` vs `#{}`**：`ArticleMapper` 所有 `@Select`/`@Update` 均用 `#{param}` 预编译，`<foreach>` 用 `#{id}`，无 `${}` 拼接。`searchPublishedByFts` 的 `sort` 参数走 `<choose><when>` 白名单（`ArticleMapper.java:73-77`），不接受任意字符串。✅ 安全
- **公开接口泄漏草稿/回收站**：见 B01-06 覆盖度确认，公开路径均过滤。✅ 安全
- **Sa-Token 路由**：admin 路径 `/api/admin/article/**` 在拦截器 `/api/admin/**` 覆盖内（`SaTokenConfig.java:33`），但 `record-view` / `stats` 等公开接口不在 admin 前缀，**符合预期**。鉴权一致性归 B06 深查。
- **XSS**：`toDTO` 对 title 做 `HtmlUtils.htmlEscape`（行 554），content_html 经 `MarkdownUtil.sanitizeHtml`（Jsoup Safelist）净化。✅ 覆盖
- **CSRF / CORS / AES / SSRF / 文件上传 / 双向 key**：本模块不涉及（分别归 B06/B16/B07/B08/B05/B09）。

---

## `[Arch]` 架构与技术债

> 排查范围：DDD 分层、上帝类、双轨漂移、隐式约定、可测试性。共享对象按 §8.6 归属，非主模块只引用。

### [P2] [Arch] `article_draft` 表有完整 schema 但零代码引用，是死表/半成品  <!-- 编号：B01-10 -->
- **定位**：`deploy/db/init-scripts/schema.sql:161-182` + `backend/src/main/resources/db/init.sql:211-235`（建表+索引+注释+外键）vs 全代码 grep `ArticleDraft|article_draft` 零命中
- **现象**：
  - schema 三轨（init.sql / schema.sql / 无对应 migration）均定义了 `article_draft` 表，含 `article_id`/`title`/`content`/`category_id`/`tags`/`auto_save` 字段
  - **整个 backend 代码库无 `ArticleDraft` Entity、无 Mapper、无 Repository、无 AppService 引用**（grep 确认）
  - 当前"草稿"能力靠 `article.status=2`（`ArticleStatus.DRAFT`）实现，`article_draft` 表完全闲置
  - CLAUDE.md 明确"标签系统未上线"，`article_draft.tags` 字段也印证这是为标签系统预留的半成品
- **影响**：
  - schema 与代码能力不对齐，读 schema 会误以为有独立草稿表
  - 与 B15 schema 三轨漂移叠加，增加维护困惑
  - "自动保存（auto_save）"功能缺失，前端编辑器意外关闭会丢失内容
- **根因/分析**：早期设计预留了独立草稿表（含 tags），后改为用 article.status 实现草稿，article_draft 未清理。是典型的"功能转向后留下死表"。
- **修复方向**：
  1. 短期：在 schema 注释标注"预留未启用"，或直接删除表（改动面 **中**，需 schema migration）
  2. 中期：若要 auto-save 体验，落地 article_draft 的 auto-save 路径（改动面 **大**）
- **关联**：[[B15]]（schema 主模块）；次维度 `[Arch]`（死代码）

### [P2] [Arch] `ArticleCreatedEvent` 无任何 listener，是死事件  <!-- 编号：B01-11 -->
- **定位**：`backend/src/main/java/com/nanmuli/blog/domain/article/event/ArticleCreatedEvent.java` + `ArticleAppService.java:124`（发布）vs 全代码 grep 无 `@EventListener` 消费方
- **现象**：`create` 方法发布 `ArticleCreatedEvent`（行 124），但 grep 全代码库无任何 `@EventListener`/`@TransactionalEventListener` 消费它（`ArticleEventHandler` 只听 `ArticlePublishedEvent`）。
- **影响**：每次创建文章都构造并发布一个无人接收的事件，浪费对象创建/ApplicationEventPublisher 调度开销（虽小）。更重要的是误导——读代码者会以为创建有异步副作用。
- **根因/分析**：可能是为未来"创建即生成摘要/向量"预留，但当前与 `ArticlePublishedEvent` 功能重叠（已发布文章既发 Created 又发 Published）。
- **修复方向**：删除 `ArticleCreatedEvent` 及其发布点，或为其补充 listener（改动面 **小**）
- **关联**：次维度 `[Arch]`（死代码）；[[B13]]（AI 链路）

### [P3] [Arch] `ArticleAppService` 634 行，是偏大的应用服务，但职责内聚（边界可接受）  <!-- 编号：B01-12 -->
- **定位**：`backend/src/main/java/com/nanmuli/blog/application/article/ArticleAppService.java:1-634`
- **现象**：单类 634 行，承担 CRUD + 统计 + 归档 + Top + 分类计数刷新 + DTO 批量转换 + 分类路径构建。
- **影响**：低于计划 §3 "787 行 → P2" 的阈值，且方法粒度合理（私有辅助方法抽取充分）。可维护性中等，不阻断。
- **根因/分析**：DTO 转换（`batchConvertToDTO`/`toDTO`/`buildCategoryPath`，约 130 行）可下沉到独立的 `ArticleAssembler`，但非必要。
- **修复方向**：可选——抽取 `ArticleDtoAssembler` 承载转换逻辑（改动面 **中**，可选）
- **关联**：次维度 `[Arch]`（可维护性）

### [P3] [Arch] 状态码用魔法数字 `1/2/3` 而非 `ArticleStatus` 枚举，散落在 repository/command 层  <!-- 编号：B01-13 -->
- **定位**：`ArticleRepositoryImpl.java:74`（`wrapper.eq(Article::getStatus, 1)`）等 7 处；`ArticleAppService.java:101-103`（`command.getStatus() == 1`）；`CreateArticleCommand.java:75-77`（`@Min(1) @Max(2)`）
- **现象**：`ArticleStatus` 枚举（`ArticleStatus.java`）已定义 PUBLISHED(1)/DRAFT(2)/RECYCLED(3)，但 repository 和 command 层大量硬编码 `1`/`2`。
- **影响**：状态语义散落，改枚举值需多处同步。`RECYCLED(3)` 在 command 校验 `@Max(2)` 中被排除（用户不能直接创建回收站文章），但 `Article.recycle()` 方法存在，调用方不明（grep 显示 domain 内无调用）。
- **根因/分析**：MyBatis Plus 的 `LambdaQueryWrapper.eq` 接受 Object，可以传 `ArticleStatus.PUBLISHED.getCode()`，但习惯用了字面量。
- **修复方向**：repository/command 层统一用 `ArticleStatus.PUBLISHED.getCode()`（改动面 **小**）
- **关联**：次维度 `[Arch]`（可维护性）

---

## `[Deps]` 依赖升级与版本

### 本模块依赖清单（基于声明文件，未翻依赖源码）

| 依赖 | 版本 | 声明位置 | 已知风险/可升级 | 备注 |
|---|---|---|---|---|
| MyBatis Plus | 3.5.9 | `backend/pom.xml:19,41-47` | 可升至 3.5.12+；3.5.9 已非最新 | 含 `mybatis-plus-jsqlparser` |
| Sa-Token | 1.44.0 | `backend/pom.xml:20,60-66` | 1.44.0 较新，无已知阻断 CVE | 鉴权主归 B06 |
| flexmark-all | 0.64.8 | `backend/pom.xml:24,98-100` | 0.64.8 是 2024 版，flexmark 已较少更新；[需查证] 是否有后续版本 | Markdown 渲染 |
| jsoup | （pom 未显示版本，可能由 spring-boot 管理） | `backend/pom.xml:110-111` | [需查证] 实际解析版本 | XSS 净化 |
| Spring Boot | 3.3.5（CLAUDE.md 基线） | 父 pom | 3.3.x 已有 3.3.10+，可升；3.4/4.x 大版本升级归 X06 | — |
| Java | 21 | `backend/pom.xml:18` | 当前 LTS，无升级压力 | — |

> 排查范围：仅本模块直接使用的依赖（MyBatis Plus / Sa-Token 间接 / flexmark / jsoup）。未翻依赖源码（§1.3.1）。Spring Boot 大版本、Sa-Token 配置深查归 B06/X06。

### [P4] [Deps] flexmark-all 0.64.8 维护活跃度偏低，建议关注替代或锁定  <!-- 编号：B01-14 -->
- **定位**：`backend/pom.xml:24`（`<flexmark.version>0.64.8</flexmark.version>`）+ `:98-100`
- **现象**：flexmark-java（VSCode.fm 衍生）0.64.8 发布于 2024 年，项目更新节奏明显放缓。本模块 `MarkdownUtil` 依赖其 Tables/Strikethrough/Tasklist/Toc 扩展。
- **影响**：当前功能正常。风险在于若发现 Markdown 解析 CVE 或与未来 Java 版本不兼容，上游修复可能滞后。
- **根因/分析**：[需查证] flexmark 是否有 0.64.8 之后的稳定 release。CommonMark-java / markdown-jvm 是潜在替代，但迁移成本不小。
- **修复方向**：记录监控，暂不升级；若需迁移评估 commonmark-java（改动面 **大**，跨模块）
- **关联**：次维度 `[Deps]`

---

## `[Design]` 功能设计合理性

> **必填**。从真实使用出发，回答计划 §2.5 中相关的问题（至少 2 个）。

**审视结论**：

1. **场景适配（§2.5-1）**：单人维护的技术博客 + AI 日报场景下，文章模块的核心 CRUD/草稿/发布/归档/置顶能力**齐全且不过度**。浏览统计做了 UV（部分唯一索引去重）+ PV（流水）双轨，对单人博客略偏重，但成本可控（详见 B01-06 PV 无清理）。`findHotArticles` 按 viewCount 排序做"热门"在内容少时区分度低，但无害。**判断：场景适配合理，无需调整。**

2. **闭环完整性（§2.5-2）**：存在两处闭环缺口。① **草稿自动保存缺失**——`article_draft.auto_save` 字段建了表却无代码，前端编辑器意外关闭会丢失内容（B01-10）；② **草稿→发布不触发 AI**（B01-02），AI 摘要/标签链路在此路径断裂。两处都是"看起来该有实际没有"的半成品。**判断：需补齐，但优先级低于 B13 AI 空壳本身。**

3. **可运维性（§2.5-3）**：① `article_visit_log` 无清理/归档任务（B01-06 详述），长期运行表无限膨胀，无运营工具介入；② 文章发布是 `@Transactional` + 事件，但事件用 `@Async("aiTaskExecutor")`（`ArticleEventHandler.java:30`），AI 失败仅 log 不重试，无告警；③ 缺少"重新触发某篇文章 AI 处理"的管理入口（只能删了重建）。**判断：可运维性偏弱，建议补 visit_log 清理 + AI 重试入口。**

4. **MVP 假设检验（§2.5-4）**：README/CLAUDE.md 声称"博客基础系统可试用"，文章 CRUD 真实可用（75 tests passed 基线）。但 `article_draft` 表、`ArticleCreatedEvent`、`recycle()` 方法、`existsBySlugAndIdNot` 都是**建好但未接线**的半成品，读 schema/代码会高估实际能力。**判断：MVP 可用，但半成品需在文档中如实标注，避免误导。**

### [P2] [Design] `article_visit_log`（PV 流水）无任何清理/归档机制，长期运行无限膨胀  <!-- 编号：B01-15 -->
- **定位**：`backend/src/main/java/com/nanmuli/blog/infrastructure/persistence/article/ArticleVisitLogMapper.java`（无 delete 方法）+ grep 全代码无 `@Scheduled` 清理 visit_log
- **现象**：
  - `article_visit_log` 每次 `recordView` 插一行（`ArticleAppService.java:356`），无聚合、无 TTL、无清理 job
  - 与之对比，`article_view_record`（UV）靠部分唯一索引天然有上界（每文章每 visitor 一行），但 `article_visit_log` 是纯追加流水
  - `countTodayByArticleId` / `countTodayVisits` 依赖 `DATE(visit_time) = CURRENT_DATE`，需扫描当日全量
- **影响**：单人博客日均 PV 有限，但叠加 B01-04 的刷量漏洞，表会快速膨胀；`idx_article_visit_log_date` 是非部分索引，膨胀后今日计数查询变慢；备份体积增长。
- **根因/分析**：设计时只考虑了统计当前值（COUNT），未考虑历史数据生命周期。
- **修复方向**：
  1. 增加 `@Scheduled` 任务定期归档/删除 N 天前的 visit_log（改动面 **中**）
  2. 或改为按天聚合表（`article_visit_daily`），牺牲明细换体积（改动面 **大**）
- **关联**：次维度 `[Design]`/`[Bug]`；[[B17]]（调度模块）

### [P4] [Design] 浏览统计 UV 去重依赖前端 localStorage visitorId，隐私换设备即重计  <!-- 编号：B01-16 -->
- **定位**：`backend/src/main/java/com/nanmuli/blog/domain/article/ArticleViewRecord.java:23-26`（注释"前端生成的唯一ID，存储在localStorage中"）
- **现象**：visitorId 由前端 localStorage 生成，清缓存/换浏览器/换设备即视为新访客，UV 会偏高。
- **影响**：单人技术博客场景下 UV 精度要求不高，偏高可接受。但与"独立访客"的语义有偏差，展示数字会让作者误判真实读者数。
- **根因/分析**：典型 trade-off。服务端 fingerprint（IP+UA）精度更差（NAT 下多人算一个）。当前选择合理。
- **修复方向**：无需调整。若要更准，可结合 IP+UA hash 作辅助去重 key（改动面 **中**，可选）
- **关联**：次维度 `[Design]`

---

## 模块小结

### 严重度统计

| 级别 | 数量 | 条目编号 |
|---|---|---|
| P0 | 0 | — |
| P1 | 2 | B01-01, B01-02 |
| P2 | 6 | B01-03, B01-04, B01-05, B01-09, B01-10, B01-11, B01-15 |
| P3 | 4 | B01-06, B01-07, B01-08, B01-12, B01-13 |
| P4 | 2 | B01-14, B01-16 |

> 注：B01-09 为安全覆盖度确认（确认安全），B01-06 为泄漏覆盖度确认（确认安全），严格说不算"问题"，但按模板登记。实际需修复的 P2 为 B01-03/04/05/10/11/15。

### Top 风险（本模块最该先看的 ≤3 条）

1. **B01-01 `article:stats` 缓存 evict key 不匹配** —— 标题/slug 变更或删除后，公开统计接口 5 分钟内返回旧值，缓存机制形同虚设。改动面小，应立即修。
2. **B01-02 草稿→发布不触发 AI 事件** —— 最自然的写作流程下 AI 增强链路断裂，B13 落地后会立即显现。改动面小。
3. **B01-04 record-view 公开接口可刷量** —— UV/PV/热门排序可被任意污染，且放大 B01-15 的表膨胀。需配合 B06 限流。

### 修复优先级建议

- **立即（P1）**：B01-01（缓存 key 统一）、B01-02（update 发发布事件）
- **计划（P2）**：B01-03（slug 冲突预检）、B01-04（record-view 限流+校验）、B01-05（分类计数原子化）、B01-10（article_draft 死表处理）、B01-11（死事件清理）、B01-15（visit_log 清理任务）
- **择机（P3/P4）**：B01-07（乱码注释）、B01-08（字数口径）、B01-12/13（重构）、B01-14（flexmark 监控）、B01-16（UV 精度）

### 排查盲区 / 待复核

- **[需查证]** `ArticleAppService.java:602` 乱码注释的来源（建议 `git blame` 追溯历史，确认是否合并事故）
- **[需查证]** jsoup 实际解析版本（pom.xml 未显式声明，可能由 spring-boot 父 pom 管理，需查 effective-pom，但本次按命令边界未跑 mvn）
- **[需查证]** flexmark-all 0.64.8 之后是否有更新版本（未查外网，按命令边界禁止）
- **未深入**：B14（乐观锁 `@Version` 是否真生效）、B15（slug 双索引 schema 漂移：`slug VARCHAR(200) UNIQUE` 全表约束 vs `idx_article_slug_active` partial + `V1_11 idx_article_slug_unique` partial 三者并存）—— 均按 §8.6 归属主模块，本报告只引用编号。
