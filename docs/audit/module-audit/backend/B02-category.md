# B02 分类 Category 排查报告

> **模块编号**：B02
> **排查范围**：树形分类 CRUD、is_leaf（替代已删 tag）、计数刷新、路径面包屑、仅叶子分类关联文章
> **基线 commit**：`6ae930098405f4d0553d96a852f3345d0f39682e`
> **工作区状态**：脏（未提交改动均与 category 无关：`ConfigRepositoryImpl.java`、`WebCollectPageMapper.java`、crawler-service 多个、`deploy/README.md`、`docs/audit/full-project-risk-register.md`、`scripts/release/release-gate.ps1`、新增 `backend/src/test/.../webcollector/`）。本模块相关文件**干净**。
> **排查日期**：2026-06-23
> **排查人**：审计 agent（B02）
> **状态**：待复核

---

## 模块概览

**职责**：维护可多级嵌套的分类树，区分"父分类（容器）"与"叶子分类（可关联文章）"，提供分类树查询、分页筛选、路径面包屑、文章计数刷新能力，供文章/日志/首页等模块消费。

**关键文件**：
- `backend/src/main/java/com/nanmuli/blog/application/category/CategoryAppService.java` —— 应用服务（519 行，含树构建、计数刷新、循环检测、深度限制、路径查询）
- `backend/src/main/java/com/nanmuli/blog/domain/category/Category.java` —— 半充血聚合（`isLeaf()`/`canAssociateArticle()`/`markAsLeaf()`/`markAsParent()`）
- `backend/src/main/java/com/nanmuli/blog/domain/category/CategoryRepository.java` —— 仓储接口
- `backend/src/main/java/com/nanmuli/blog/infrastructure/persistence/category/CategoryRepositoryImpl.java` —— 仓储实现（含 LIKE 转义）
- `backend/src/main/java/com/nanmuli/blog/infrastructure/persistence/category/CategoryMapper.java` —— 仅 `BaseMapper<Category>`，无自定义 SQL
- `backend/src/main/java/com/nanmuli/blog/interfaces/rest/CategoryController.java` —— REST 入口
- `backend/src/main/java/com/nanmuli/blog/infrastructure/config/initializer/CategoryCountInitializer.java` —— 启动时刷新计数
- `backend/src/main/java/com/nanmuli/blog/application/category/{command,dto,query}/*` —— Create/Update Command、DTO、PageQuery

**对外接口 / 依赖**：
- 对外（Controller，`/api/category/list`、`/api/category/leaf`、`/api/admin/category/{list,page,{id},{id}/path,refresh-counts}`）
- 被消费方：`ArticleAppService`（`validateLeafCategory`、`refreshCategoryArticleCount`、`getCategoryAndChildrenIds`、`findCategoryIdsByKeyword`）、`DailyLogAppService`（`findAllById`/`findById` 解析分类名）、`HomeController`（首页聚合分类树）
- 依赖：`ArticleRepository.countByCategoryId/countByCategoryIds`、`category` 表（含 `parent_id` 自引用、`is_leaf`、`article_count`、逻辑删除 `is_deleted`）

**已读文件清单**：
- `application/category/CategoryAppService.java` —— 通读
- `domain/category/Category.java` —— 通读
- `domain/category/CategoryRepository.java` —— 通读
- `infrastructure/persistence/category/CategoryRepositoryImpl.java` —— 通读
- `infrastructure/persistence/category/CategoryMapper.java` —— 通读
- `interfaces/rest/CategoryController.java` —— 通读
- `infrastructure/config/initializer/CategoryCountInitializer.java` —— 通读
- `application/category/{command,dto,query}/*` —— 通读
- `application/article/ArticleAppService.java`（与本模块交互段：74、119-207、261-279、320-338、450-500）—— 片段
- `application/dailylog/DailyLogAppService.java`（35-106、116-151）—— 片段
- `infrastructure/persistence/article/ArticleRepositoryImpl.java`（140-200）—— 片段
- `shared/domain/BaseAggregateRoot.java` —— 通读（确认 `@TableLogic` 逻辑删除）
- `interfaces/rest/HomeController.java` —— 通读
- `deploy/db/init-scripts/schema.sql`（252-289、828-877、888-926）—— 片段
- `backend/src/main/resources/db/init.sql`（95-128、735-767、931-941）—— 片段
- `db/migration/V1_7__drop_tag_tables.sql`、`V1_19__add_indexes_and_constraints.sql` —— 仅 grep / 通读
- backend `src/test/` —— glob 搜索 category 测试，**无命中**

**主模块归属**：
- 本模块**不是**任何共享对象的主模块。
- 仅引用：
  - PG `category` 表 schema / Flyway / init.sql / schema.sql → 主模块 **B15**（本报告只记 category 表视角）
  - LIKE 转义实现 → 主模块 **B14-05**（本模块是调用方，记影响面）
  - 鉴权（admin 路由是否漏配）→ 主模块 **B06**

---

## `[Bug]` 代码正确性与潜在缺陷

> 排查范围：`CategoryAppService` 全部方法、`CategoryRepositoryImpl` 全部方法、`ArticleAppService` 中调用 category 的方法、`CategoryCountInitializer`、`Category` 领域方法、并发与状态一致性。

### [P1] [Bug] 文章增删后父链 article_count 不刷新，仅启动/手动触发才校正  <!-- 编号：B02-01 -->

- **定位**：`backend/src/main/java/com/nanmuli/blog/application/article/ArticleAppService.java:489-500`（`refreshCategoryArticleCount`）；对照 `CategoryAppService.java:147-177`（`refreshAllCategoryArticleCounts` 才做父链汇总）
- **现象**：文章 `create`（行 119-121）、`update` 改 categoryId（行 200-207）、`delete`（行 335-337）调用 `refreshCategoryArticleCount(categoryId)`，该方法只 `countByCategoryId` 当前叶子分类并 `save`，**不向上递归更新 parent 链**。父分类的 `article_count` 只有在 `refreshAllCategoryArticleCounts()`（启动时 `CategoryCountInitializer` 或手动 POST `/api/admin/category/refresh-counts`）被调用时才重算。
- **影响**：日常运维中，每发一篇/删一篇/改分类，叶子分类计数实时准确，但其所有祖先分类计数长期偏差。前台 `/api/category/list` 走 `buildTree`→`calculateTotalArticleCount` 在内存重算（依赖叶子计数，正确），但管理端 `/api/admin/category/page` 直接读 DB `article_count` 字段，会显示陈旧值；任何直接读 DB 字段（看板、报表、外部脚本）都会拿到错误数字。偏差累积到下次重启或手动刷新才清零。
- **根因/分析**：`refreshCategoryArticleCount` 是早期实现，后来加入 `refreshAllCategoryArticleCounts` 做了父链汇总但未回填到单点刷新路径。注释（行 487）写"避免 AppService 跨调用耦合"，但代价是放弃了父链实时性。已排除误判：`buildTree` 确实在内存重算，但只覆盖前台树接口，不覆盖 DB 字段消费者。
- **修复方向**：①`refreshCategoryArticleCount` 向上递归 parentId 直到根，每层重算 save；或②改为只信叶子计数 + 查询时内存汇总，父分类 `article_count` 字段废弃/弃写。改动面：**中**（跨 AppService，需补并发测试）。
- **关联**：次维度 `[Arch]`（计数刷新双路径不一致）；横向主题"配置/数据一致性"。

### [P1] [Bug] 计数刷新 read-modify-write 无乐观锁，并发文章创建会丢失更新  <!-- 编号：B02-02 -->

- **定位**：`backend/src/main/java/com/nanmuli/blog/application/article/ArticleAppService.java:489-500`；`backend/src/main/java/com/nanmuli/blog/application/category/CategoryAppService.java:314-325`、`170-176`；`domain/category/Category.java`（无 `@Version`）
- **现象**：`refreshCategoryArticleCount` 流程是 `findById` → `setArticleCount(count)` → `save(updateById)`。`Category` 继承的 `BaseAggregateRoot` 无 `@Version` 字段（`backend/src/main/java/com/nanmuli/blog/shared/domain/BaseAggregateRoot.java:14-41`），`article` 表有 `version`（见 V1_3/V1_6 migration）但 `category` 表无。两个并发请求同时 `findById` 读到相同 `article_count`，各自 `count` 后写回，后写覆盖先写。
- **影响**：并发发布/删除文章（如批量导入、采集自动转文章）时，叶子分类计数可能比真实值少 1~N；叠加 B02-01 后偏差进一步向父链传播。单线程场景不触发，多用户/采集器并发场景真实存在。
- **根因/分析**：计数本质是 `count(*)`，每次全量重算而非 `+1`，理论上重算能自愈——但并发场景下两次 `count` 都发生在事务内读到的快照，仍可能读到对方尚未提交的中间态；更重要的是 `save(updateById)` 用 `WHERE id=?`（无 version 谓词），最后一次写定胜负。无 `@Version` 是根因。
- **修复方向**：①`category` 表加 `version` 列 + 实体 `@Version`，复用 article 已有乐观锁模式；或②改用原子 SQL `UPDATE category SET article_count=(SELECT count(*)...) WHERE id=?` 单语句绕开 RMW；或③`countByCategoryId` 在事务隔离级别 REPEATABLE_READ 下仍可能读旧值，建议直接走 SQL 子查询。改动面：**中**（加列需 Flyway migration）。
- **关联**：次维度 `[Security]`（无）；关联 B15（category 表 schema 加列）。

### [P2] [Bug] getCategoryPath 逐层查询无环检测，DB 层已存在环时无限循环  <!-- 编号：B02-03 -->

- **定位**：`backend/src/main/java/com/nanmuli/blog/application/category/CategoryAppService.java:247-263`
- **现象**：`getCategoryPath` 用 `while (current != null)` 逐层 `findById(parentId)` 拼路径，**无 visited 集合、无深度上限**。应用层 `validateParentCategory`/`detectCircularReference`（行 333-402）确实在建/改时防环，但 DB 层 `fk_category_parent` 仅是引用约束，**无 CHECK 防环**；若数据被脚本/历史 bug/直连 DB 写入形成环，本方法会死循环直到栈溢出或请求超时。`getCategoryDepth`（行 182-194）同样无环检测。
- **影响**：极低概率（应用层已防），但一旦发生是阻塞性故障（管理端分类详情/路径接口 hang 住）。
- **根因/分析**：防御深度不足。应用层校验是唯一防线，DB 无 invariant。
- **修复方向**：`getCategoryPath`/`getCategoryDepth` 加 `Set<Long> visited` 或深度上限（如 MAX_CATEGORY_DEPTH*2）。改动面：**小**。
- **关联**：次维度 `[Arch]`（防御深度）。

### [P2] [Bug] 删除父分类的 is_leaf 一致性维护依赖手动输入，无自动联动  <!-- 编号：B02-04 -->

- **定位**：`backend/src/main/java/com/nanmuli/blog/application/category/CategoryAppService.java:289-307`（`delete`）、`83-122`（`update`）
- **现象**：`update` 时若 `command.getIsLeaf()` 从 true 改 false，会校验"有子分类不能设叶子"（行 99-101），但反向场景（一个无子分类的父分类想改为叶子）只校验"无子"即可放行——**不校验该父分类自身是否曾被设为父并被其他业务路径引用**。更关键：`delete` 仅校验 `hasChildren` 和（叶子时）`articleRepository.countByCategoryId`，**不校验 `article_draft.category_id`、`daily_log.category_id` 是否引用本分类**。
- **影响**：删除一个被 `article_draft` 或 `daily_log` 引用的分类（逻辑删除），DB 物理行仍在（逻辑删除），外键 `fk_draft_category`/`fk_daily_log_category` 不报错，但下次 `categoryRepository.findById` 返回空，DTO 转换时分类名展示为空——形成"悬挂引用"。daily_log 可挂父分类（见 B02-07），删除容器分类后日志分类信息丢失。
- **根因/分析**：`delete` 校验范围只覆盖 `article` 表（且仅叶子），遗漏同模块下游表。逻辑删除 + 外键物理约束的组合，使数据一致性校验责任全压应用层，但应用层校验不全。
- **修复方向**：`delete` 扩展校验 `article_draft`、`daily_log` 的 categoryId 引用；或显式声明"仅 article 维护引用完整性，其余允许悬挂 + DTO 兜底"。改动面：**中**（需补跨表校验与测试）。
- **关联**：次维度 `[Design]`（删除语义不清）；关联 B15（外键 ON DELETE 默认 NO ACTION 与逻辑删除的语义错配）。

### [P2] [Bug] findIdsByNameLike 转义后被 substring 破坏，搜索带 _ 或 % 的分类名异常  <!-- 编号：B02-05 -->

- **定位**：`backend/src/main/java/com/nanmuli/blog/infrastructure/persistence/category/CategoryRepositoryImpl.java:148-161`
- **现象**：`escapeLikeKeyword(keyword)` 返回 `%escaped%`（已转义 `\_"`→`\_`、`\%`），随后 `.substring(1, escapedKeyword.length() - 1)` 去掉首尾 `%`，再传给 `wrapper.like("name", ...)`。MyBatis-Plus 的 `like` 会**自动再包一层 `%...%`**，所以最终 SQL 是 `name LIKE '%\_%'`（用户原输入 `_` 被转义为 `\_`）。问题在于：PG 默认 LIKE 的 ESCAPE 字符是 `\`，`\_` 表示字面下划线——这部分**功能上是对的**；但 `findPage`（行 124-129）走 LambdaQuery `like` 时**同样自动加 `%`**，而那里传入的是已带 `%...%` 的完整串，会变成 `LIKE `%%`escaped`%%``（多了一层），转义符 `\_` 被夹在多个 `%` 之间仍生效——两条路径行为不一致。
- **影响**：①两条 LIKE 调用路径的转义/通配符叠加方式不同，维护者易误改；②用户搜索含 `_`、`%` 的分类名（如 `C++_STL`、`100%`）行为在两条路径下需分别验证。本模块是调用方，转义实现深查归 **B14-05**。
- **根因/分析**：`escapeLikeKeyword` 既加通配符又转义，调用方有的 `substring` 有的不 `substring`，约定不统一。
- **修复方向**：①`escapeLikeKeyword` 只负责转义、不加 `%`，由调用方决定通配符；②或显式声明 `ESCAPE '\'` 子句（PG 默认即可，但显式更清晰）。改动面：**小**（但属 B14-05 主模块统一处理）。
- **关联**：主模块 **B14-05**（LIKE 转义实现统一）；本模块仅记影响面。

### [P3] [Bug] refreshAllCategoryArticleCounts 按深度排序后仍递归重算，O(n²) 复杂度  <!-- 编号：B02-06 -->

- **定位**：`backend/src/main/java/com/nanmuli/blog/application/category/CategoryAppService.java:157-222`
- **现象**：`parentCategories` 已按 `getCategoryDepth` 降序排序，注释（行 169）说"最深的先处理，上层可复用"。但实际循环里对每个 parent 仍调用 `calculateTotalArticleCountForCategory`（行 199-222）**递归遍历全部子树**，没有利用"已按深度排序"的结果做累加。排序是无效优化，复杂度 O(n²)（n = 分类数）。同时 `getCategoryDepth`（行 182-194）本身也是 O(depth) 遍历，外层排序再 O(n log n × depth)。
- **影响**：分类数大时（数百~数千）启动慢、`refresh-counts` 接口慢。MVP 阶段分类数 <50，影响轻微。
- **根因/分析**：注释承诺的优化未真正实现（排序后应直接读子节点已算好的 `articleCount` 累加，而非递归）。
- **修复方向**：要么删掉无效排序注释（保持递归，O(n²) 接受），要么真正改为"子节点已算好→父节点直接 sum children"。改动面：**小**。
- **关联**：次维度 `[Arch]`（性能/可维护性）。

---

## `[Security]` 安全漏洞

> 排查范围：`CategoryController` 全部路由、`CategoryAppService` 写操作、`CategoryRepositoryImpl` 全部查询、Command 校验注解。逐项覆盖 §2.2 重点：Sa-Token 路由、MyBatis `${}` vs `#{}`、CSRF、CORS、AES、SSRF、文件上传、双向 key。

### [P2] [Security] admin 路由鉴权纯靠 URL 前缀，无 @SaCheck* 方法级注解  <!-- 编号：B02-07 -->

- **定位**：`backend/src/main/java/com/nanmuli/blog/interfaces/rest/CategoryController.java:42-92`（`/api/admin/category/**` 全部写操作）
- **现象**：`create`/`update`/`delete`/`refreshArticleCounts` 等 5 个写接口无任何 `@SaCheck*`/`@PreAuthorize` 注解，鉴权完全依赖 Sa-Token 路由拦截器的 URL 前缀规则（`/api/admin/**`）。公开读接口 `/api/category/list`、`/api/category/leaf` 在 `/api/**` 下。
- **影响**：若拦截器规则漏配（如新增前缀、规则顺序错误），所有写接口直接暴露。属项目级已知薄弱点（见 §9 线索），本模块是该模式的一个实例。
- **根因/分析**：项目统一约定，非本模块独有。
- **修复方向**：参考主模块 **B06** 的统一修复方案（方法级注解或过滤器加固）。改动面：**小**（本模块加注解）/ **大**（全项目）。
- **关联**：主模块 **B06**；横向主题"鉴权机制一致性"。

### 未发现（其余 §2.2 项）

- **MyBatis `${}` vs `#{}`**：`CategoryRepositoryImpl` 全部用 LambdaQueryWrapper / QueryWrapper.select("id")（列名硬编码，非用户输入），未发现 `${}` 拼接用户输入。LIKE 用 `.like()` 预编译参数，转义在应用层处理（见 B02-05）。无 SQLi。
- **CSRF / CORS / AES / SSRF / 文件上传 / 双向 key**：本模块无文件上传、无外部 URL、无密钥、无 AES；CSRF/CORS 是全局配置（B16），本模块无特殊性。

---

## `[Arch]` 架构与技术债

> 排查范围：分层合规性、God Service、重复实现、隐式约定、可测试性。共享对象按 §8.6 归属，非主模块只引用。

### [P2] [Arch] CategoryAppService 半充血设计与贫血实体并存，领域方法未被调用  <!-- 编号：B02-08 -->

- **定位**：`backend/src/main/java/com/nanmuli/blog/domain/category/Category.java:42-51`（`markAsLeaf`/`markAsParent`）；`application/category/CategoryAppService.java:58-66`（create 时直接 `BeanUtils.copyProperties` + `setColor`，未调 `markAsLeaf`）
- **现象**：`Category` 提供 `markAsLeaf()`/`markAsParent()`/`canAssociateArticle()` 三个领域方法，但 `CategoryAppService` 全程通过 `BeanUtils.copyProperties(command, category)` 直接拷贝 `isLeaf` 字段，**从未调用** `markAsLeaf`/`markAsParent`；`canAssociateArticle()` 也无人调用（`ArticleAppService.validateLeafCategory` 直接用 `category.isLeaf()`）。半充血设计形同摆设。
- **影响**：领域不变量封装失败（未来若 `isLeaf=true` 需联动其他字段，分散在 AppService 难维护）。可读性误导。
- **根因/分析**：DDD 改造不彻底，Command→Entity 走 BeanUtils 偷懒。
- **修复方向**：要么删除未用的领域方法（承认贫血），要么把 isLeaf 设置改为通过 `markAsLeaf/markAsParent`。改动面：**小**。
- **关联**：次维度 `[Bug]`（一致性）。

### [P2] [Arch] toDTO 有两个重载，单参版本绕过批量优化走实时 N+1  <!-- 编号：B02-09 -->

- **定位**：`backend/src/main/java/com/nanmuli/blog/application/category/CategoryAppService.java:475-486`（单参 `toDTO`，实时 `countByCategoryId`）、`491-501`（双参，用预计算 map）、`278-282`（`getById` 调单参）、`247-263`（`getCategoryPath` 内 `toDTO(current)` 调单参）
- **现象**：`buildTree`/`listLeafCategories` 走批量（正确），但 `getById`、`getCategoryPath` 走单参 `toDTO`，每个节点实时 `countByCategoryId`。`getCategoryPath` 在 while 循环里每层调一次单参 toDTO，每层一次 `count` 查询——路径深度 N 则 N 次 count。
- **影响**：管理端"分类详情"和"分类路径"接口在深层分类上有 N+1 查询，但调用频率低，影响轻微。
- **根因/分析**：批量优化只覆盖了 list 类接口，单点查询沿用旧实现。
- **修复方向**：单参 `toDTO` 接受可选的预计算 map，或路径接口一次 `findAllById(路径上所有id)` 批量。改动面：**小**。
- **关联**：次维度 `[Bug]`（性能）。

### [P3] [Arch] 计数刷新逻辑在 ArticleAppService 与 CategoryAppService 各有一份，重复实现  <!-- 编号：B02-10 -->

- **定位**：`backend/src/main/java/com/nanmuli/blog/application/article/ArticleAppService.java:485-500`（注释明确写"原 CategoryAppService.refreshArticleCount() 的内联实现，避免 AppService 跨调用耦合"）；`backend/src/main/java/com/nanmuli/blog/application/category/CategoryAppService.java:310-325`
- **现象**：两份 `refreshCategoryArticleCount`/`refreshArticleCount` 逻辑几乎一致（findById → count → save），注释承认是"内联以避免耦合"。但两者都不向上刷新父链（B02-01），重复的缺陷也重复。
- **影响**：未来修复 B02-01/B02-02 时需同步改两处，易漏。
- **根因/分析**：为解耦引入重复，但重复的恰恰是需要一致演化的不变量。
- **修复方向**：抽到 domain service 或 CategoryAppService 单一实现，ArticleAppService 调用它；或彻底改为 SQL 子查询消除 RMW。改动面：**中**。
- **关联**：次维度 `[Bug]`（B02-01/B02-02）；横向主题"keyword 优化循环 vs digest 优化循环"同类问题（跨模块重复实现）。

### [P3] [Arch] CategoryCountInitializer 启动阻塞主流程，异常仅 log 不告警  <!-- 编号：B02-11 -->

- **定位**：`backend/src/main/java/com/nanmuli/blog/infrastructure/config/initializer/CategoryCountInitializer.java:24-32`
- **现象**：`ApplicationRunner` 同步执行 `refreshAllCategoryArticleCounts`，启动时全表扫描 + 逐个 save。异常被 `catch + log.error` 吞掉，无重试、无健康检查标记、无告警。
- **影响**：①分类数大时拖慢启动；②刷新失败后计数长期偏差且无信号（运维不知情）。MVP 阶段影响小。
- **根因/分析**：`try-catch` 兜底保证启动不阻断是合理的，但缺少失败可观测性。
- **修复方向**：失败时记录到看板/告警，或改 `@Async` 后台执行。改动面：**小**。
- **关联**：次维度 `[Design]`（可运维性）。

---

## `[Deps]` 依赖升级与版本

### 本模块依赖清单（基于声明文件，未翻依赖源码）

| 依赖 | 版本 | 声明位置 | 已知风险/可升级 | 备注 |
|---|---|---|---|---|
| MyBatis Plus | 3.5.9 | `backend/pom.xml` | 可升至 3.5.12+；`BaseMapper`/`QueryWrapper` API 稳定 | 本模块用 LambdaQuery/QueryWrapper/selectPage |
| Spring Boot | 3.3.5 | `backend/pom.xml` | 3.3.x 已进维护期，可评估 3.4/3.5 | `@Cacheable/@CacheEvict`、`ApplicationRunner` 均稳定 |
| Lombok | (随 SB) | `backend/pom.xml` | — | `@Data/@Getter/@RequiredArgsConstructor` |
| Jakarta Validation | (随 SB) | `backend/pom.xml` | — | `@NotBlank/@Size/@Pattern` 用于 Command |
| 无独立第三方库 | — | — | — | 本模块无文件/AI/HTTP 客户端，仅依赖 SB + MP |

> 排查范围：仅本模块直接使用的依赖。未发现版本特定风险。MyBatis Plus/Spring Boot 的整体升级路径归 B14/X01。

**未发现**本模块特有的依赖升级阻断点。

---

## `[Design]` 功能设计合理性

**审视结论**（回答 §2.5 问题 1、2、5）：

1. **场景适配**（单人技术博客场景）：树形分类 + is_leaf 二态 + 5 层深度限制，对单人博客是**略偏重**但可接受的设计——单人维护的分类通常 ≤20 个、2~3 层就够了，5 层 + 循环检测 + 深度校验属防御性过度，但成本低，不构成问题。is_leaf 替代 tag 是合理简化（一人博客不需要多对多标签）。
2. **闭环完整性**（计数刷新闭环）：**不完整**。日常增删文章后父分类计数偏差（B02-01），只能靠"重启或手动点 refresh-counts"校正，没有定时校正机制，也没有偏差检测。对单人博客这种低频场景，偏差可容忍，但缺少"该有而没有"的定时/事件驱动校正，是体验断层。
3. **可运维性 / 缺失功能**：`refresh-counts` 是手动兜底入口（好），但①无单分类手动刷新接口（只有全量）；②Initializer 失败无告警（B02-11）；③删除语义不清（B02-04，draft/daily_log 引用不校验）。这些在真实使用中会以"分类计数不准""删了分类日志分类名没了"的形式暴露。

### [P3] [Design] 缺少单分类计数刷新接口与偏差检测  <!-- 编号：B02-12 -->

- **定位**：`backend/src/main/java/com/nanmuli/blog/interfaces/rest/CategoryController.java:87-92`（只有全量 refresh）；缺失单分类 refresh 端点
- **现象**：当前只有 `POST /api/admin/category/refresh-counts`（全量），无 `POST /api/admin/category/{id}/refresh-count`。运维若发现某分类计数偏差，必须触发全量刷新。
- **影响**：低频，但全量刷新在分类多时较重。
- **建议方向**：补单分类刷新端点（顺带修复 B02-01 父链刷新）。改动面：**小**。
- **关联**：B02-01。

### [P4] [Design] is_leaf 二态设计合理，无需调整  <!-- 编号：B02-13 -->

- **定位**：`backend/src/main/java/com/nanmuli/blog/domain/category/Category.java:23-51`
- **现象**：is_leaf 区分容器/叶子，配合"仅叶子关联文章"约束，替代了已删除的 tag 系统。
- **影响**：对单人博客场景适配良好，查询时一棵树即可拿到所有"标签"，避免 tag + category 双系统的维护负担。
- **建议方向**：**无需调整**。仅 `markAsLeaf`/`markAsParent` 未被调用（见 B02-08）需清理。
- **关联**：B02-08。

---

## 模块小结

### 严重度统计

| 级别 | 数量 | 条目编号 |
|---|---|---|
| P0 | 0 | — |
| P1 | 2 | B02-01, B02-02 |
| P2 | 6 | B02-03, B02-04, B02-05, B02-07, B02-08, B02-09 |
| P3 | 4 | B02-06, B02-10, B02-11, B02-12 |
| P4 | 1 | B02-13 |

### Top 风险（本模块最该先看的 ≤3 条）

1. **B02-01 文章增删后父链 article_count 不刷新** —— 直接影响管理端展示与所有读 DB 字段的下游，偏差累积，最贴近真实使用。
2. **B02-02 计数刷新无乐观锁并发丢失更新** —— 与 B02-01 叠加，并发采集/批量发布场景下数据偏差放大。
3. **B02-04 删除分类不校验 draft/daily_log 引用** —— 删除后下游 DTO 分类名悬挂，需明确删除语义。

### 修复优先级建议

- **立即（P1）**：B02-01（父链刷新，建议方案②废弃父 article_count 字段或方案①递归刷新二选一）、B02-02（加 `@Version` 或改原子 SQL，建议原子 SQL 更省 migration）。
- **计划（P2）**：B02-04（删除校验扩展 draft/daily_log）、B02-03（路径查询加 visited 防御）、B02-05（LIKE 转义随 B14-05 统一）、B02-07（鉴权随 B06 统一）、B02-08（清理贫血方法或真正充血）、B02-09（单点 toDTO 批量化）。
- **择机（P3/P4）**：B02-06、B02-10、B02-11、B02-12、B02-13。

### 排查盲区 / 待复核

- **[需查证] B02-02 并发实测**：未运行压测，`countByCategoryId` 在 PG 默认 READ COMMITTED 下并发事务的读快照行为需实测确认偏差幅度；建议补集成测试。
- **[需查证] B02-04 外键 ON DELETE 实际行为**：schema.sql 中 `fk_draft_category`/`fk_daily_log_category`/`fk_category_parent` 均无 `ON DELETE` 子句（默认 NO ACTION），但 category 用 `@TableLogic` 逻辑删除（`UPDATE is_deleted=true`，不触发外键）。需确认生产环境是否真用逻辑删除（`categoryMapper.deleteById` → MyBatis-Plus 逻辑删除）——若是，则外键 ON DELETE 永不触发，B02-04 的悬挂引用问题成立；若有人手动物理删除，则 NO ACTION 会阻塞。归 B15 复核外键语义。
- **[需查证] 测试覆盖**：`backend/src/test/` 无任何 `*Category*` 测试文件，**本模块零单测覆盖**。建议补 `validateParentCategory`（循环/深度边界）、`refreshAllCategoryArticleCounts`（父链汇总）、`buildTree`（排序/计数）三类测试。归 X03。
- 未深入：LIKE 转义在 MyBatis-Plus 不同版本下 `like()` 是否自动包 `%` 的行为细节（归 B14-05 主模块）；Sa-Token 拦截器实际规则配置（归 B06）。
