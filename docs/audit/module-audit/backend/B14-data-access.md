# B14 数据访问层 排查报告

> **模块编号**：B14
> **排查范围**：MyBatis Plus 配置 / 各 Mapper / RepositoryImpl / 乐观锁与分页拦截器 / MetaObjectHandler 自动填充 / 逻辑删除 / JsonbTypeHandler / 分页基类
> **基线 commit**：`6ae930098405f4d0553d96a852f3345d0f39682e`
> **工作区状态**：脏。涉及本模块的未提交改动：
>   - `backend/src/main/java/com/nanmuli/blog/infrastructure/persistence/config/ConfigRepositoryImpl.java`（M）
>   - `backend/src/main/java/com/nanmuli/blog/infrastructure/persistence/webcollector/WebCollectPageMapper.java`（M）
>   - `backend/src/test/java/com/nanmuli/blog/infrastructure/persistence/webcollector/`（?? 新增，含 `WebCollectPageMapperProjectionTest.java`）
> **排查日期**：2026-06-23
> **排查人**：B14 审计 agent
> **状态**：草稿

---

## 模块概览

**职责**：实现领域层 Repository 接口，封装 MyBatis Plus 数据访问；统一分页/逻辑删除/乐观锁/自动填充/JSONB 类型映射等横切数据访问策略。

**关键文件**：

- `backend/src/main/java/com/nanmuli/blog/infrastructure/config/db/MyBatisPlusConfig.java:17` —— MP 拦截器（分页 + 乐观锁）、MetaObjectHandler 自动填充、JsonbTypeHandler Bean 注册。
- `backend/src/main/java/com/nanmuli/blog/infrastructure/config/db/JsonbTypeHandler.java:21` —— `List<String>` ↔ PostgreSQL JSONB 双向 TypeHandler，解析失败吞异常返回空列表。
- `backend/src/main/java/com/nanmuli/blog/shared/query/BasePageQuery.java:12` —— 分页基类，`current`/`size` 双重保护（`@Min/@Max` Bean Validation + getter normalize 兜底，size 上限 100）。
- `backend/src/main/java/com/nanmuli/blog/shared/domain/BaseAggregateRoot.java:14` —— 聚合根基类，承载 `id`（ASSIGN_ID 雪花）、`createdAt`/`updatedAt`（自动填充）、`isDeleted`（`@TableLogic` + INSERT 填充）。
- `backend/src/main/resources/application.yml:48-53` —— 全局逻辑删除配置（`isDeleted` / `true` / `false`）+ `id-type: assign_id`。
- `backend/src/main/java/com/nanmuli/blog/infrastructure/persistence/article/ArticleMapper.java:15` —— 自定义 FTS/trigram 搜索 SQL（原生 `@Select` + `<script>` 动态 `#{}` 参数）。
- `backend/src/main/java/com/nanmuli/blog/infrastructure/persistence/webcollector/DigestFingerprintMapper.java:12` —— 指纹批量 `@Insert` + `ON CONFLICT DO NOTHING`（原生 SQL 绕过自动填充）。
- `backend/src/main/java/com/nanmuli/blog/infrastructure/persistence/article/ArticleRepositoryImpl.java:265` —— `applyListProjection` 显式列投影（非 SELECT *）。

**对外接口 / 依赖**：

- 对外：各领域 `Repository` 接口实现 + `*Mapper`（BaseMapper 扩展）。
- 依赖：MyBatis Plus 3.5.9、mybatis-plus-jsqlparser 3.5.9、PostgreSQL JDBC、`@TableLogic`/`@Version`/`@TableField(fill=...)` MP 注解、`BasePageQuery`（被 application 层引用）。
- 表（schema 定义归 B15，本模块只引用）：article / category / daily_log / project / skill / friend_link / sys_config / users / blog_file / article_view_record / article_visit_log / web_collect_task / web_collect_page / web_collect_source / digest_fingerprint / source_authority。

**已读文件清单**：

- `infrastructure/config/db/MyBatisPlusConfig.java` —— 通读
- `infrastructure/config/db/JsonbTypeHandler.java` —— 通读
- `shared/query/BasePageQuery.java` —— 通读
- `shared/domain/BaseAggregateRoot.java` —— 通读
- `application.yml` —— 通读（仅 MP/Sa-Token/file 段相关）
- `pom.xml` —— 通读（依赖清单）
- 全部 16 个 `*Mapper.java` —— 通读（CategoryMapper/ConfigMapper/DailyLogMapper/BlogFileMapper/FriendLinkMapper/ProjectMapper/SkillMapper/UserMapper/WebCollectTaskMapper/WebCollectSourceMapper/SourceAuthorityMapper 为空接口；ArticleMapper/WebCollectPageMapper/ArticleViewRecordMapper/ArticleVisitLogMapper/DigestFingerprintMapper 含自定义 SQL）
- 全部 12 个 `*RepositoryImpl.java` —— 通读
- 4 个领域实体（`Article` / `WebCollectTask` / `WebCollectPage` / `DigestFingerprint` / `Config` / `ArticleVisitLog` / `Project`）—— 通读确认 `@Version` / 继承关系 / TypeHandler 用点
- `ArticleMapperProjectionTest.java` / `WebCollectPageMapperProjectionTest.java` —— 通读
- application 层 `new Page` 调用点 / `REQUIRES_NEW` 用点 —— grep

**主模块归属**：本模块是数据访问实现的**主模块**，深查。对 PG 表 schema 定义、Flyway 迁移、init.sql/schema.sql 三轨只引用 B15（不展开）。`REQUIRES_NEW` 自代理问题归 B08（本模块只记"事务边界不在 persistence 层"这一事实）。

---

## `[Bug]` 代码正确性与潜在缺陷

> 排查范围：全部 Mapper/RepositoryImpl、自动填充、乐观锁、分页、TypeHandler。覆盖空集合、越界、事务边界、并发、异常吞掉、资源释放。

### [P3] [Bug] MetaObjectHandler 自动填充对原生 `@Insert`/`@Update` SQL 不生效  <!-- 编号：B14-01 -->
- **定位**：`backend/src/main/java/com/nanmuli/blog/infrastructure/persistence/webcollector/DigestFingerprintMapper.java:14-31`（`insertIgnoreOnConflict` / `batchInsertIgnoreOnConflict`）；对照 `MyBatisPlusConfig.java:33-47`（MetaObjectHandler 只作用于 MP 自动生成的 INSERT/UPDATE）
- **现象**：`DigestFingerprintMapper` 的两个 `@Insert` 方法是原生 SQL，列清单里显式写了 `is_deleted` 为 `false`，但**没有**写 `created_at` / `updated_at`。MP 的 `strictInsertFill` 只在实体走自动生成的 INSERT 时触发，对原生 `@Insert` 注解 SQL 不生效。
- **影响**：`DigestFingerprintRepositoryImpl.saveAll`（批量指纹写入，日报去重链路核心）写入的记录 `created_at`/`updated_at` 完全依赖 DB 列 `DEFAULT NOW()`。若 `digest_fingerprint` 表的这两列缺 DEFAULT（schema 漂移场景下可能发生），插入会抛 `null value violates not-null constraint`，整批日报指纹写入失败。`is_deleted` 字段同理靠手写硬编码而非自动填充兜底。
- **根因/分析**：MyBatis Plus 的 `MetaObjectHandler` 钩在 MP 自动生成的 SQL 上，对开发者手写的 `@Insert` 原生 SQL 无能为力——这是 MP 已知行为，非 bug。但此处手写 SQL 漏掉了 `created_at`/`updated_at`，与实体继承 `BaseAggregateRoot`（期望自动填充）形成认知落差。
- **修复方向**：①原生 `@Insert` 的 VALUES 显式补 `NOW(), NOW()`（小）；②或改用 MP `saveBatch` + 唯一索引让 MP 走自动 SQL（但失去 `ON CONFLICT DO NOTHING` 语义，需评估，中）。需对照 B15 确认 `digest_fingerprint` 列 DEFAULT。
- **关联**：[[B15]] schema 列 DEFAULT 核实；横向主题：schema 漂移

### [P3] [Bug] `JsonbTypeHandler` 解析失败静默吞异常返回空列表  <!-- 编号：B14-02 -->
- **定位**：`backend/src/main/java/com/nanmuli/blog/infrastructure/config/db/JsonbTypeHandler.java:53-63`（`parseJson`）
- **现象**：JSONB 反序列化抛 `JsonProcessingException` 时，仅 `log.error` 后 `return Collections.emptyList()`，不向上抛。
- **影响**：`Project.screenshots` / `Project.techStack` 字段若 DB 中存了损坏/不合法 JSON（手工改库、迁移脏数据、版本升级 schema 变更），前端展示静默变空，无任何监控/告警/可观测信号，运维侧无法发现"数据还在但读不出来"。当前影响面小（仅 Project 两个字段，展示用），但属于"静默数据丢失"类隐患。
- **根因/分析**：TypeHandler 返回空列表而非 null 是为了避免 NPE，设计意图合理；但"解析失败"与"DB 存空数组"两种语义被合并，丢失了可观测性。
- **修复方向**：①解析失败改为抛 `SQLException`（或 RuntimeException），由上层决定降级（小，但需评估 Project 展示链路容错）；②至少加监控埋点/Metrics 计数（中）。`[需查证]`：当前是否有日志告警规则捕获这条 `log.error`。
- **关联**：次维度 `[Arch]` 可观测性

### [P4] [Bug] 乐观锁 `@Version` 字段为包装类型 `Integer`，新建时 null 导致首次更新不携带版本号条件  <!-- 编号：B14-03 -->
- **定位**：`backend/src/main/java/com/nanmuli/blog/domain/article/Article.java:36-38`（`@Version private Integer version`）、`backend/src/main/java/com/nanmuli/blog/domain/webcollector/WebCollectTask.java:20-21`、`backend/src/main/java/com/nanmuli/blog/domain/webcollector/WebCollectSource.java:44`
- **现象**：三处 `@Version` 都是 `Integer`（包装类），新建实体时 version 为 null。MyBatis Plus `OptimisticLockerInnerInterceptor`（`MyBatisPlusConfig.java:28` 已注册）行为：实体 version 为 null 时，`updateById` **不会**追加 `WHERE version = ?` 条件、也不会自增——首次更新等同于无乐观锁保护。
- **影响**：仅在"实体 insert 后内存对象 version 仍为 null、未重新查询、直接 updateById"的路径上才失去保护。实际路径多在 insert 后重新 `selectById` 取回 DB 回填的 version（若 DB 有 DEFAULT），此时 version 非 null，乐观锁正常生效。是否真失效取决于应用层是否 reload 实体。
- **根因/分析**：MP 官方文档明确：version 字段推荐用基础类型 int 或在 insert 时初始化为 1（或依赖 DB DEFAULT 1）。包装类型 + null 是已知"首次更新无锁"场景。非 bug，是设计选择，但属于"乐观锁看起来配了实则首次失效"的隐性陷阱。
- **修复方向**：①确认 schema 中 `article.version` / `web_collect_task.version` / `web_collect_source.version` 列有 `DEFAULT 1`（归 B15 核实）；②或在领域层 `publish()`/状态流转前 reload 实体。`[需查证]`：实际 update 路径是否都 reload。
- **关联**：[[B15]] schema 列 DEFAULT 核实；次维度 `[Security]` 并发更新覆盖

### [P4] [Bug] `BasePageQuery.getCurrent/getSize` 重写 getter，Lombok `@Data` 生成 `equals/hashCode/toString` 可能用裸字段值  <!-- 编号：B14-04 -->
- **定位**：`backend/src/main/java/com/nanmuli/blog/shared/query/BasePageQuery.java:11-31`
- **现象**：类标注 `@Data`，但手写了 `getCurrent()`/`getSize()` 做 normalize。`@Data` 生成的 `toString()/equals()/hashCode()` 直接读字段 `current`/`size`（未 normalize），而 getter 读 normalize 后的值。
- **影响**：若有代码依赖 `toString()` 或 `equals()` 比较（如日志打印、缓存 key、测试断言），会看到未归一化的原始值（如 `current=0` 或 `size=9999`），与实际查询用的归一化值不一致，造成认知混乱。当前未发现关键路径依赖此行为，属低风险。
- **根因/分析**：Lombok `@Data` 对"手写 getter"与"自动生成方法"的字段访问不一致是已知陷阱。非 bug，但属于潜在踩坑点。
- **修复方向**：①改用 `@Getter @Setter` + 手写需要的方法，避免 `@Data` 生成的方法读裸字段（小）；②或保持现状，加注释说明。维持现状亦可。
- **关联**：无

---

## `[Security]` 安全漏洞

> 排查范围：逐项对照计划 §2.2 技术栈重点中的 MyBatis 部分（`${}` vs `#{}`、`apply()/last()` 拼接、分页 + 逻辑删除越权、乐观锁生效、SELECT * 投影泄漏）。Sa-Token/CORS/AES/SSRF/文件上传/双向 key 归各自主模块，本节只记 MyBatis 相关。

### [P3] [Security] `CategoryRepositoryImpl.findIdsByNameLike` LIKE 转义未声明 ESCAPE 子句，PG 默认 LIKE 下反斜杠转义不生效  <!-- 编号：B14-05 -->
- **定位**：`backend/src/main/java/com/nanmuli/blog/infrastructure/persistence/category/CategoryRepositoryImpl.java:149-161`（`findIdsByNameLike` + `escapeLikeKeyword`）
- **现象**：`escapeLikeKeyword` 把 `%`/`_`/`\` 转义为 `\%`/`\_`/`\\`，然后 `wrapper.like("name", escapedKeyword.substring(1, escapedKeyword.length() - 1))` 去掉首尾 `%` 后传入。MyBatis Plus `.like()` 生成 `name LIKE CONCAT('%', ?, '%')`（参数化，**无 SQLi**），但**不附加 `ESCAPE '\'` 子句**。PostgreSQL 默认 `LIKE` 不把 `\` 当转义符（除非 `standard_conforming_strings=off` 或显式 `ESCAPE`），所以 `\%` 在 DB 侧被当字面量 `\` + `%`，`%` 仍是通配符。
- **影响**：①非 SQLi（参数化已防注入）；②但 `escapeLikeKeyword` 的转义**实际无效**，用户输入的 `%`/`_` 仍被当通配符，导致搜索结果不符合预期（如搜 `50%` 匹配所有含 `50` 的分类）。属功能正确性问题，非数据泄露。当前 `findIdsByNameLike` 调用方有限，影响面窄。
- **根因/分析**：MP 的 `Like` 条件不自带 ESCAPE 声明，需开发者用 `apply("name LIKE ? ESCAPE '\\'", ...)` 自行补。`escapeLikeKeyword` 写对了转义逻辑但没配 ESCAPE 子句让转义生效，属于"防护写了一半"。
- **修复方向**：①改用 `wrapper.apply("name LIKE CONCAT('%', ?, '%') ESCAPE '\\'", escapedKeyword)` 显式声明 ESCAPE（小）；②或接受现状（PG 下 LIKE 通配符泄漏影响小），移除无效的 `escapeLikeKeyword` 减少误导。`[需查证]`：当前 PG `standard_conforming_strings` 默认值（on）。
- **关联**：次维度 `[Bug]` 功能正确性

### [P4] [Security] 全部分页查询显式列投影，无 SELECT * 投影泄漏，反射守卫测试已覆盖核心 Mapper  <!-- 编号：B14-06 -->
- **定位**：`ArticleRepositoryImpl.applyListProjection`（`:265-287`）、`FileRepositoryImpl.findPage`（`:82-85`）、`ArticleMapper.ARTICLE_LIST_COLUMNS`（`:17-21`）、`WebCollectPageMapper.WEB_COLLECT_PAGE_COLUMNS`（`:18-37`）；守卫测试 `ArticleMapperProjectionTest` / `WebCollectPageMapperProjectionTest`
- **现象**：所有列表/分页查询（Article/File/Category selectPage、WebCollectPage 原生 @Select、Article FTS/trigram 搜索）均使用显式列投影，无 `SELECT *`。两个反射守卫测试验证 `ArticleMapper` 三个搜索方法、`WebCollectPageMapper` 三个查询方法的 `@Select` SQL 不含 `SELECT *`。`Article` 列表投影明确排除 `content`/`content_html`（大字段），避免列表接口泄漏正文。
- **影响**：无安全问题。投影策略合理，守卫测试防止回归。但守卫**只覆盖含 `@Select` 原生 SQL 的 Mapper**，LambdaQueryWrapper 路径的投影（如 `applyListProjection`）反射测试够不到——不过这些是 Java 代码显式 `select()`，回归风险低。
- **根因/分析**：上一轮发现的 SELECT * 问题已在工作区改动（WebCollectPageMapper M 状态）修复并加守卫测试，闭环完整。
- **修复方向**：无需调整。可选：为 LambdaQueryWrapper 投影路径补基于 SQL 日志的集成测试断言（中，非必要）。
- **关联**：无

### [P4] [Security] 全局逻辑删除 + 实体 `@TableLogic` 双重配置，部分 RepositoryImpl 手写 `.eq(isDeleted, false)` 形成冗余双保险，风格不一致  <!-- 编号：B14-07 -->
- **定位**：全局配置 `application.yml:48-53`；`BaseAggregateRoot.java:26-28`（`@TableLogic`）；显式过滤的如 `ArticleRepositoryImpl.java:44/53/61/75` 等；**未**显式过滤的如 `SkillRepositoryImpl.findAllVisible`（`:44-48`）、`ProjectRepositoryImpl.findAllVisible`（`:49-53`）、`DailyLogRepositoryImpl` 全部方法、`UserRepositoryImpl.findByUsername`（`:34-38`）、`WebCollectPageRepositoryImpl.findPageByTaskId`（`:47-52`）
- **现象**：MP 已通过全局配置 + 实体 `@TableLogic` 对所有继承 `BaseAggregateRoot` 的实体自动追加 `is_deleted = false`。`Article`/`Category`/`WebCollectTask`/`WebCollectSource`/`ArticleViewRecord` 等的 RepositoryImpl **额外手动**写了 `.eq(getIsDeleted, false)`；而 `Skill`/`Project`/`FriendLink`/`DailyLog`/`User`/`DigestFingerprint`(部分) **完全依赖**全局拦截器。两套风格并存。
- **影响**：当前**无数据安全问题**（双保险方向一致）。但风格不一致增加维护认知成本：①新人改某查询时不知道该不该手写 isDeleted 条件；②若未来有人误删全局配置，依赖拦截器的一批查询会突然暴露已删除数据（如 `UserRepositoryImpl.findByUsername` 会让已软删用户可登录）。原生 `@Select`/`@Update`/`@Insert` SQL（如 `ArticleMapper.searchPublishedByFts`、`DigestFingerprintMapper`）**必须**手写，这部分无歧义。
- **根因/分析**：典型"演进式"代码——早期手写、后期发现全局拦截器后新代码省略，老代码未统一。非 bug。
- **修复方向**：①统一约定：LambdaQueryWrapper 路径**不**手写（依赖全局），原生 SQL **必须**手写，并补注释说明（小，跨多文件）；②或反过来全部手写显式（更防御但啰嗦）。维持现状亦可，记为技术债。
- **关联**：次维度 `[Arch]` 一致性

---

## `[Arch]` 架构与技术债

> 排查范围：DDD 分层（领域层是否泄漏 MP 注解）、事务边界、命名约定、重复模式、隐式依赖。

### [P3] [Arch] 领域层聚合根直接依赖 MyBatis Plus 注解（`@TableName`/`@Version`/`@TableField`/`@TableLogic`/`@TableId`），DDD 分层泄漏  <!-- 编号：B14-08 -->
- **定位**：`backend/src/main/java/com/nanmuli/blog/shared/domain/BaseAggregateRoot.java:3-7,17,20,23,26-27`（`@TableId`/`@TableField`/`@TableLogic`）；`backend/src/main/java/com/nanmuli/blog/domain/article/Article.java:3-4,36-38`；`backend/src/main/java/com/nanmuli/blog/domain/webcollector/WebCollectTask.java:3-4,16,20`；`backend/src/main/java/com/nanmuli/blog/domain/webcollector/WebCollectPage.java:3,18`；`backend/src/main/java/com/nanmuli/blog/domain/config/Config.java:3,12`；`backend/src/main/java/com/nanmuli/blog/domain/project/Project.java:5,26,29`（连 `JsonbTypeHandler` 这个 infrastructure 类都 import 到 domain）
- **现象**：领域层实体直接标注 MP 注解、直接引用 infrastructure 包的 `JsonbTypeHandler`。`BaseAggregateRoot`（shared/domain）把"持久化关注点"耦合进"领域基类"。
- **影响**：①领域层无法脱离 MP 独立测试/复用；②更换 ORM 需改领域层；③`Project.java` 直接 `import com.nanmuli.blog.infrastructure.config.db.JsonbTypeHandler` 违反分层方向（domain → infrastructure 反向依赖）。这是项目级架构选择，单人 MVP 可接受，但与 CLAUDE.md 声称的"DDD 分层"有张力。
- **根因/分析**：MP 的"实体即映射"模式与纯 DDD"领域层无持久化注解"天然冲突，多数 Spring + MP 项目都做了此妥协。`shared/domain/BaseAggregateRoot` 命名上属于 domain 但实质是持久化基类。
- **修复方向**：①维持现状，在文档明确"采用 MP 活动记录风格，领域层容忍 MP 注解"（小，仅文档）；②长期可抽 `BaseEntity`（infrastructure）+ 纯领域模型分离（大，非 MVP 优先级）。
- **关联**：次维度 `[Design]` 场景适配；项目级架构决策

### [P3] [Arch] `BaseAggregateRoot` 既在 `shared/domain` 又承载持久化字段，职责混杂  <!-- 编号：B14-09 -->
- **定位**：`backend/src/main/java/com/nanmuli/blog/shared/domain/BaseAggregateRoot.java:14-29`
- **现象**：该类名为"聚合根"（DDD 领域概念），却集中了：①`@TableId` 主键映射（持久化）；②`@TableField(fill=...)` 自动填充（持久化）；③`@TableLogic` 逻辑删除（持久化）；④`isNew()` 领域方法。
- **影响**：所有继承它的实体（Article/Category/.../DigestFingerprint 等 10+ 个）被迫携带持久化关注点。`ArticleVisitLog` 因为不需要这些（只增日志），只能**不继承**该类、单独用 `@Data` + `@TableId(AUTO)`，导致实体风格分裂。
- **根因/分析**：与 B14-08 同源。"聚合根"基类承载了基础设施职责，名实不符。
- **修复方向**：与 B14-08 合并处理。维持现状 + 文档说明亦可。
- **关联**：[[B14-08]]

### [P4] [Arch] 分页参数归一化与 Bean Validation 校验分散在两处，依赖 Controller `@Valid` 触发  <!-- 编号：B14-10 -->
- **定位**：`backend/src/main/java/com/nanmuli/blog/shared/query/BasePageQuery.java:19-24`（`@Min/@Max`）+ `:25-31`（getter normalize）+ application 层 `new Page<>(query.getCurrent(), query.getSize())` 调用点（见已读清单）
- **现象**：分页保护分两层：①`@Min(1)/@Max(100)` Bean Validation（需 Controller 形参加 `@Valid` 才触发，返回 400）；②getter 内 normalize 兜底（即使绕过校验也安全）。DailyLog 接口未继承 BasePageQuery，改用 `BasePageQuery.normalizeCurrent/normalizeSize` 静态方法。两层防御完整。
- **影响**：当前所有分页入口（Article/Category/File/CollectTask 4 个 PageQuery + DailyLog 静态方法）均已覆盖。无越权/越界风险。唯一隐患：若未来新增分页接口忘了继承 `BasePageQuery` 或忘调静态方法，会失去保护——但这是约定层面，非代码可强制。
- **根因/分析**：设计合理，两层防御。
- **修复方向**：无需调整。
- **关联**：无

---

## `[Deps]` 依赖升级与版本

### 本模块依赖清单（基于声明文件，未翻依赖源码）

| 依赖 | 版本 | 声明位置 | 已知风险/可升级 | 备注 |
|---|---|---|---|---|
| `mybatis-plus-spring-boot3-starter` | 3.5.9 | `pom.xml:40-43` | 可升至 3.5.12（2025 年发布）；3.5.9 无已知关键 CVE | 本模块核心 |
| `mybatis-plus-jsqlparser` | 3.5.9 | `pom.xml:44-48` | 同上；分页 count 优化依赖 jsqlparser | 分页 `optimizeCountSql` 用 |
| `postgresql`（JDBC driver） | 随 Spring Boot 3.3.5 BOM | `pom.xml:49-52` | 42.7.x 系列；建议确认是否 ≥42.7.4（修复若干 CVE）`[需查证]` | |
| `org.postgresql.util.PGobject` | 随 driver | `JsonbTypeHandler.java:10` | —— | JSONB 写入用 |
| `com.fasterxml.jackson` | 随 Spring Boot | `JsonbTypeHandler.java:3-5` | —— | JSON 序列化 |
| `lombok` | 随 Spring Boot BOM | `pom.xml:91-95` | —— | `@Data/@Getter` |

> 排查范围：仅本模块直接相关的 MP / PG JDBC / Jackson。Spring Boot / Sa-Token / Knife4j 等全局依赖归 B16/X01。

### [P4] [Deps] MyBatis Plus 3.5.9 可升级至 3.5.12，但非关键路径  <!-- 编号：B14-11 -->
- **定位**：`pom.xml:19`（`<mybatis-plus.version>3.5.9</mybatis-plus.version>`）
- **现象**：MP 3.5.9（2024 年发布）为当前稳定线，3.5.10/3.5.11/3.5.12 已发布，含分页 count 优化、逻辑删除边界修复等增强。无已知针对 3.5.9 的关键 CVE（基于公开信息，`[需查证]`）。
- **影响**：当前版本运行正常（基线 75 tests passed）。升级非紧迫。
- **根因/分析**：常规版本滞后，非风险。
- **修复方向**：随 Spring Boot 升级周期一并升级 MP（中，需回归测试乐观锁/分页/逻辑删除行为）。
- **关联**：[[B16]] 全局依赖升级

---

## `[Design]` 功能设计合理性

> 必填。从真实使用（单人维护技术博客 + 每工作日 AI 日报）出发，回答计划 §2.5 相关问题（至少 2 个）。

**审视结论**：

1. **场景适配（§2.5-1）**：MyBatis Plus 的"实体即映射 + LambdaQueryWrapper"模式对单人维护的中小型项目是**恰当**的——省去 XML Mapper 和手写 SQL 的维护成本，编译期字段引用检查。当前 16 个 Mapper 中 11 个为空接口（纯 BaseMapper）、仅 5 个有自定义 SQL（FTS/JSONB/批量 INSERT 等复杂场景），分层干净。乐观锁/分页/逻辑删除/自动填充四大横切能力通过一次 `MyBatisPlusConfig` 配置全覆盖，无需重复样板。**判断：场景适配良好，无过度设计。**

2. **可运维性（§2.5-3）**：数据访问层**缺少可观测性**：①`JsonbTypeHandler` 解析失败静默吞异常（B14-02）；②乐观锁冲突（`updateById` 返回 0 行）在上层如何处理未见统一日志/告警；③逻辑删除"看不见的数据"无管理端查看入口。故障时运维难以定位"为什么某条记录查不到/某字段读空"。**判断：可运维性偏弱，建议补关键路径日志/计数。**

3. **闭环完整性（§2.5-2）**：逻辑删除形成"软删 + 全局过滤"闭环，但**缺人工干预入口**——已软删数据无 admin 界面查看/恢复（`selectById` 也被拦截），只能直连 DB 操作。对单人博客影响小（误删概率低），但日报/采集任务若误删恢复成本高。**判断：闭环基本完整，软删恢复入口缺失属可接受的技术债。**

### [P4] [Design] 数据访问层缺乏可观测性埋点（日志/指标）  <!-- 编号：B14-12 -->
- **定位**：本模块全局（`MyBatisPlusConfig` / 各 RepositoryImpl / `JsonbTypeHandler`）
- **现象**：除 `JsonbTypeHandler.parseJson` 有一行 `log.error` 外，整个数据访问层无 INFO/WARN 级别日志、无 Metrics 计数。乐观锁失败、批量插入部分成功、慢查询（依赖 MP `log-impl: Slf4jImpl` 打印 SQL，但无慢查询阈值）均无结构化观测。
- **影响**：单人运维场景下，"日报指纹为什么没写入""某 Project 的 techStack 为什么变空"这类问题难定位，需开 MP 全量 SQL 日志（噪声大）或直连 DB 排查。
- **建议方向**：①关键失败路径（TypeHandler 解析失败、乐观锁返回 0 行、批量 INSERT 返回数 < 入参数）补结构化 WARN 日志 + 计数（中）；②维持现状，依赖 MP SQL 日志兜底（小，可接受）。
- **关联**：次维度 `[Bug]` B14-02

### [P4] [Design] 软删数据无管理端查看/恢复入口，依赖直连 DB  <!-- 编号：B14-13 -->
- **定位**：全局逻辑删除配置 + 所有继承 `BaseAggregateRoot` 的实体
- **现象**：逻辑删除后，所有 Repository 查询（含 `selectById`、admin 列表）都被拦截器过滤，已删数据在前端/管理端"消失"。无任何"回收站"或"查看已删除"接口。
- **影响**：误删 article/daily_log/web_collect_task 后，恢复需直连 DB `UPDATE ... SET is_deleted=false`，单人项目可接受但操作风险高（易改错）。
- **建议方向**：①维持现状，在 `docs/` 补"软删恢复 SOP"文档（小）；②长期可加 admin 回收站接口（中，非 MVP 优先级）。
- **关联**：无

---

## 模块小结

### 严重度统计

| 级别 | 数量 | 条目编号 |
|---|---|---|
| P0 | 0 | — |
| P1 | 0 | — |
| P2 | 0 | — |
| P3 | 4 | B14-01, B14-02, B14-05, B14-08/09（合并计为架构项） |
| P4 | 6 | B14-03, B14-04, B14-06, B14-07, B14-10, B14-11, B14-12, B14-13 |

> 实际条目编号 13 条。按主维度归并后：P3 共 4 条问题（B14-01 自动填充、B14-02 TypeHandler 吞异常、B14-05 LIKE ESCAPE、B14-08/09 分层泄漏），P4 共 7 条。

### Top 风险（本模块最该先看的 ≤3 条）

1. **B14-01 原生 `@Insert` 绕过 MetaObjectHandler** —— `DigestFingerprintMapper` 批量写入漏 `created_at`/`updated_at`，依赖 DB DEFAULT，schema 漂移下可能致日报指纹写入失败。需对照 B15 确认列 DEFAULT。
2. **B14-02 `JsonbTypeHandler` 静默吞异常** —— JSONB 解析失败变空列表，损坏数据无告警，可观测性盲区。
3. **B14-05 LIKE 转义未配 ESCAPE 子句** —— 转义逻辑写了但 PG 下不生效，搜索结果不符合预期（非 SQLi）。

### 修复优先级建议

- **立即**（P0/P1）：无。本模块无阻断级问题。
- **计划**（P2）：无明确 P2 条目。B14-01/B14-02/B14-05 按 P3 处置（功能/可运维性影响，非数据安全）。
- **择机**（P3/P4）：
  - 确认 B15 的 `digest_fingerprint` 列 DEFAULT（解除 B14-01 `[需查证]`）。
  - B14-05 LIKE ESCAPE 子句补全（小改动，提升搜索正确性）。
  - B14-08/09 分层泄漏维持现状 + 文档说明。
  - B14-02 TypeHandler 加监控（随可观测性专项）。

### 排查盲区 / 待复核

- **B14-01 `[需查证]`**：`digest_fingerprint` 表 `created_at`/`updated_at` 列是否有 `DEFAULT NOW()`（归 B15 schema 核实）。若有 DEFAULT 则本条降为 P4/Info；若无则升 P2（写入直接失败）。
- **B14-03 `[需查证]`**：`article` / `web_collect_task` / `web_collect_source` 三表的 `version` 列是否有 `DEFAULT 1`，以及应用层 update 前是否 reload 实体（归 B15 + B01/B08 应用层核实）。
- **B14-05 `[需查证]`**：生产 PG 的 `standard_conforming_strings` 设置（默认 on，导致 `\` 转义不生效）。`findIdsByNameLike` 的实际上游调用方与影响面未深查（归 B02）。
- **B14-02 `[需查证]`**：当前是否有日志告警规则捕获 `JsonbTypeHandler` 的 `log.error`（归 X01 运维观测）。
- **B14-11 `[需查证]`**：MyBatis Plus 3.5.9 是否有未公开的 CVE（基于训练知识无，需查官方 security advisory）。
- **未深查**：乐观锁冲突时上层（application 层）的处理逻辑（归 B01/B08）；`REQUIRES_NEW` 自代理问题（归 B08）；各 RepositoryImpl 与 Controller 的字段契约（归各业务模块 + 跨服务契约横向主题）。
