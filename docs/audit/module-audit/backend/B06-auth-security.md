# B06 认证授权 Auth/Security 排查报告

> **模块编号**：B06
> **排查范围**：Sa-Token 配置与拦截器、登录/登出流程、UserAppService、sys_user/sys_login_log 表、限流 Filter、admin/public 路由鉴权规则、角色判定、内部回调双向 key、CORS 与 Cookie 安全属性
> **基线 commit**：`6ae930098405f4d0553d96a852f3345d0f39682e`
> **工作区状态**：脏（未提交改动涉及 `ConfigRepositoryImpl.java`、`WebCollectPageMapper.java`、`crawler-service/*`、`deploy/README.md`、`docs/audit/full-project-risk-register.md`、`scripts/release/release-gate.ps1`，**均不属于本模块范围**，对本报告结论无影响）
> **排查日期**：2026-06-23
> **排查人**：B06 审计 agent
> **状态**：待复核

> **密钥脱敏说明**：本报告引用 `deploy/.env` 泄漏证据时，所有真实密钥以 `<REDACTED-类型>` 占位，不写入明文。审计人员可通过 `cat deploy/.env` 或 `git log -p --all -- deploy/.env` 自行核对。

---

## 模块概览

**职责**：基于 Sa-Token 1.44 的 Cookie 模式认证 + URL 前缀路由鉴权 + 双向 key 内部回调鉴权 + IP 限流，保护单人维护博客的 admin 接口与 Python↔Java 跨服务回调。

**关键文件**：
- `backend/src/main/java/com/nanmuli/blog/interfaces/rest/AuthController.java:16` —— 登录/登出/info 三个端点，`@RequestMapping("/api")`
- `backend/src/main/java/com/nanmuli/blog/application/user/UserAppService.java:20` —— 登录核心逻辑（BCrypt 校验、status 校验、StpUtil.login）
- `backend/src/main/java/com/nanmuli/blog/domain/user/User.java:15` —— User 实体，`role`/`status` 字段
- `backend/src/main/java/com/nanmuli/blog/infrastructure/config/security/SaTokenConfig.java:20` —— 鉴权拦截器配置（**本模块核心**）
- `backend/src/main/java/com/nanmuli/blog/interfaces/filter/RateLimitFilter.java:27` —— IP 限流
- `backend/src/main/java/com/nanmuli/blog/interfaces/rest/InternalCallbackController.java:33` —— 内部回调鉴权（X-Callback-Key）
- `backend/src/main/resources/application.yml:26` —— Sa-Token 全局配置
- `backend/src/main/resources/application-prod.yml:30` —— 生产 alone-redis db1 隔离
- `backend/src/main/java/com/nanmuli/blog/infrastructure/config/web/WebMvcConfig.java:14` —— CORS 配置（**归 B16 主模块**，本报告记交叉）

**对外接口 / 依赖**：
- 对外：`POST /api/auth/login`、`GET /api/auth/info`、`POST /api/auth/logout`；所有 `/api/admin/**` 受 Sa-Token `checkLogin()` 拦截器保护；所有 `/api/internal/**` 受 localhost + X-Callback-Key 拦截器保护
- 依赖：Sa-Token 1.44.0（`sa-token-spring-boot3-starter` + `sa-token-redis-jackson`）、hutool 5.8.36（BCrypt）、MyBatis Plus（UserMapper）、Redis（alone-redis db1 存 token）
- 表：`sys_user`、`sys_login_log`（**死表，见 B06-06**）

**已读文件清单**：
- `backend/src/main/java/com/nanmuli/blog/interfaces/rest/AuthController.java` —— 通读
- `backend/src/main/java/com/nanmuli/blog/application/user/UserAppService.java` —— 通读
- `backend/src/main/java/com/nanmuli/blog/domain/user/User.java` —— 通读
- `backend/src/main/java/com/nanmuli/blog/domain/user/UserRepository.java` —— 通读
- `backend/src/main/java/com/nanmuli/blog/infrastructure/persistence/user/UserRepositoryImpl.java` —— 通读
- `backend/src/main/java/com/nanmuli/blog/infrastructure/persistence/user/UserMapper.java` —— 通读
- `backend/src/main/java/com/nanmuli/blog/application/user/command/LoginCommand.java` —— 通读
- `backend/src/main/java/com/nanmuli/blog/infrastructure/config/security/SaTokenConfig.java` —— 通读（**核心**）
- `backend/src/main/java/com/nanmuli/blog/infrastructure/config/security/AesEncryptor.java` —— 通读（归 B07）
- `backend/src/main/java/com/nanmuli/blog/interfaces/filter/RateLimitFilter.java` —— 通读
- `backend/src/main/java/com/nanmuli/blog/interfaces/filter/AccessLogFilter.java` —— 通读
- `backend/src/main/java/com/nanmuli/blog/interfaces/filter/TraceIdFilter.java` —— 通读
- `backend/src/main/java/com/nanmuli/blog/interfaces/rest/InternalCallbackController.java` —— 通读
- `backend/src/main/java/com/nanmuli/blog/interfaces/rest/WebCollectorController.java:140-189` —— 片段（StpUtil 调用点）
- `backend/src/main/java/com/nanmuli/blog/interfaces/rest/ConfigController.java` —— 通读
- `backend/src/main/java/com/nanmuli/blog/application/config/ConfigAppService.java` —— 通读（StpUtil.isLogin 冗余校验）
- `backend/src/main/java/com/nanmuli/blog/application/article/ArticleAppService.java` —— 仅 grep（StpUtil.getLoginIdAsLong ×3）
- `backend/src/main/java/com/nanmuli/blog/infrastructure/config/web/WebMvcConfig.java` —— 通读（CORS，归 B16）
- `backend/src/main/java/com/nanmuli/blog/infrastructure/config/ConfigService.java` —— 通读
- `backend/src/main/resources/application.yml` —— 通读
- `backend/src/main/resources/application-prod.yml` —— 通读
- `backend/src/main/resources/data.sql` —— 通读（种子 admin 密码 + role 小写）
- `deploy/db/init-scripts/schema.sql`（sys_user 段）—— 片段
- `backend/src/main/resources/db/init.sql`（sys_user 段）—— 片段
- grep 覆盖：所有 Controller 的 `@RequestMapping`、所有 `StpUtil`/`@SaCheck`/`@PreAuthorize` 引用、所有 `sys_login_log`/`LoginLog` 引用、所有 `X-Callback-Key`/`crawler.callback.api-key` 引用

**主模块归属**：**B06 是鉴权机制主模块，深查**。共享对象归属：CORS → B16（本报告记交叉发现，不展开）；AES → B07（本报告仅引用）；`deploy/.env` 密钥泄漏 → X06（本报告引用并交叉记录，因 callback key 是双向鉴权凭据）；内部回调端点契约 → B09 主模块。

---

## `[Bug]` 代码正确性与潜在缺陷

> 排查范围：UserAppService 登录流程、SaTokenConfig 拦截器规则、StpUtil 调用点、UserRepositoryImpl 查询、AuthController 路由、UserDTO 映射。逐项覆盖，命中如下。

### [P2] [Bug] /api/auth/info 和 /api/auth/logout 脱离拦截器保护  <!-- 编号：B06-01 -->
- **定位**：`backend/src/main/java/com/nanmuli/blog/infrastructure/config/security/SaTokenConfig.java:33-34`；调用点 `UserAppService.java:50`（`getCurrentUser` 调 `StpUtil.getLoginIdAsLong()`）、`UserAppService.java:62`（`logout` 调 `StpUtil.logout()`）
- **现象**：Sa-Token 拦截器 `addPathPatterns("/api/admin/**")` 只覆盖 `/api/admin/` 前缀；`excludePathPatterns` 只列了 `/api/auth/login` 和 `/api/internal/**`。`/api/auth/info` 和 `/api/auth/logout` **既不在拦截范围，也不在 exclude 列表**——它们落在 `/api/` 但非 `/api/admin/`，所以**无任何鉴权拦截器**。但内部实现直接调 `StpUtil.getLoginIdAsLong()` / `StpUtil.logout()`。
- **影响**：
  - `/api/auth/info`：未登录时调用 `getLoginIdAsLong()` 会抛 `NotLoginException`，被 GlobalExceptionHandler 兜底返回 401/500（**取决于异常映射，[需查证] 是否映射为 401**）。功能上不会泄漏数据（未登录拿不到 userId 就抛异常），但**异常处理路径不规范**，且若未来异常映射改为吞异常，会变成"未登录也能进 getCurrentUser 逻辑"。
  - `/api/auth/logout`：未登录调 `StpUtil.logout()` 在 Sa-Token 中是幂等的（无 token 则无操作），**当前无害**，但语义不清。
- **根因/分析**：拦截器设计只覆盖 `/api/admin/**`，把 `/api/auth/info`/`logout` 当作"公开端点"处理，但实现却依赖登录态。已排除的误判：**不是越权**（这两个端点不涉及敏感数据写入，info 只读当前登录用户自己的信息）。
- **修复方向**：①将 `/api/auth/info`、`/api/auth/logout` 纳入 `addPathPatterns`（如改为 `/api/auth/**` 排除 `/api/auth/login`，或单独再加一个拦截器注册）；②或在两个端点内部用 `StpUtil.isLogin()` 显式判断后返回明确 401，不依赖异常兜底。（改动面：小）
- **关联**：次维度 [Security]；横向主题"鉴权机制一致性"（§2.6）

### [P3] [Bug] ConfigAppService.getAllConfigsForAdmin 应用层冗余 isLogin 校验  <!-- 编号：B06-02 -->
- **定位**：`backend/src/main/java/com/nanmuli/blog/application/config/ConfigAppService.java:45-47`
- **现象**：该方法被 `/api/admin/config/list`（`ConfigController.java:40`）调用，路由已在 `/api/admin/**` 拦截器保护下（拦截器先执行 `checkLogin()`）。但方法内部又手动 `if (!StpUtil.isLogin()) throw new BusinessException(401, ...)`。
- **影响**：双重校验逻辑上无害（拦截器先抛，应用层判断永不触发），但①违反 DDD 分层（应用服务不应直接做鉴权判断，那是基础设施/接口层职责）；②若未来该方法被非 admin 路由复用，会掩盖"该路由缺拦截器保护"的问题（因为应用层兜底了，开发者误以为安全）；③`@Cacheable(value="config:admin:list")`（line 42）在 isLogin 校验**之前**——理论上缓存命中时跳过方法体，但 Spring 缓存代理在方法进入前已决策，isLogin 判断仍在方法体内，缓存与鉴权顺序无冲突（已排除缓存绕过鉴权的误判）。
- **根因/分析**：分层不清晰，鉴权职责下沉到应用层。
- **修复方向**：删除应用层的 `isLogin` 判断，依赖拦截器统一保护；或若坚持防御性编程，提取到独立的鉴权切面。（改动面：小）
- **关联**：次维度 [Arch]；分层混乱

### [P3] [Bug] UserAppService.login 事务范围包含外部不可逆操作（写 loginIp/loginTime）  <!-- 编号：B06-03 -->
- **定位**：`backend/src/main/java/com/nanmuli/blog/application/user/UserAppService.java:24-46`
- **现象**：`@Transactional` 方法内：①查用户 → ②BCrypt 校验 → ③status 校验 → ④写 loginIp/loginTime → ⑤`StpUtil.login()`（操作 Redis alone-redis db1）。Redis 写入在事务内，但 Redis 不参与 Spring 事务管理。
- **影响**：若 ④ 之后 ⑤ 之前 DB 提交成功但 Redis 写失败（网络抖动），会出现"DB 已记录登录时间，但用户实际未登录成功"的状态不一致。反之若 ⑤ 成功后事务回滚（如 `userRepository.save` 后某个 AOP 失败），用户拿到 token 但 DB 未记录登录——**影响仅限审计字段不准**，不影响安全。单人博客场景影响极低。
- **根因/分析**：跨存储（PG + Redis）事务无补偿机制。已排除：BCrypt 不在事务内引发锁问题（无长事务持有连接做重计算）。
- **修复方向**：将 `StpUtil.login()` 移到事务外（事务方法只负责 DB 更新，返回 user，调用方再 login）；或接受当前不一致（审计字段非关键）。（改动面：小）
- **关联**：次维度 [Arch]

---

## `[Security]` 安全漏洞

> 排查范围：逐项覆盖计划 §2.2 技术栈重点。Sa-Token（拦截器规则/token 失效/alone-redis 隔离/登出清理/StpUtil 绕过）、MyBatis `${}` vs `#{}`、Cookie+CSRF、CORS、AES（引用 B07）、SSRF（非本模块）、文件上传（非本模块）、双向 key。命中如下。

### [P0] [Security] deploy/.env 真实密钥曾在 git 历史中提交（5 类敏感凭据全部泄漏）  <!-- 编号：B06-04 -->
- **定位**：`deploy/.env`（工作区存在但当前未被 git 跟踪，`.gitignore:33` 有 `**/.env`）；git 历史 `git log --all -- deploy/.env` 显示 4 个 commit 改过该文件：`247afe4`、`7b34820`、`4523b7f`、`6606143`。历史 commit `4523b7f` 中 `deploy/.env` 含明文 `DB_PASSWORD=nanmuli_blog_2024`（弱密码，已实测 `git show 4523b7f:deploy/.env` 确认）。当前工作区 `deploy/.env` 含 5 类真实密钥（明文值已脱敏，类型如下）：
  - `CRAWLER_API_KEY=<REDACTED-32char>` （Java→Python 调用 key）
  - `CRAWLER_CALLBACK_API_KEY=<REDACTED-32char>` （Python→Java 回调 key，本模块双向鉴权凭据）
  - `DB_PASSWORD=<REDACTED-32char>` （PostgreSQL 密码）
  - `BLOG_SECURITY_ENCRYPTION_KEY=<REDACTED-43char>` （AES 加密 key，用于解密 sys_config 敏感配置）
  - `AI_API_KEY=<REDACTED-sk-prefix>` （LLM API key）
- **现象**：①git 历史中 `deploy/.env` 被提交过多次，任何能 clone 仓库的人可通过 `git show <commit>:deploy/.env` 取出历史密钥；②当前 `.gitignore` 虽已排除 `.env`，工作区文件未被 `git add`（`git ls-files --error-unmatch deploy/.env` 报未跟踪），但**文件实体存在于工作区**，部署脚本（`deploy/docker-compose.yml:69` `${CRAWLER_CALLBACK_API_KEY:?...}`）从该文件读取——意味着该文件是真实部署凭据来源，任何接触过该工作区/备份/IDE 同步的人都能看到明文密钥；③历史 commit 中的 `DB_PASSWORD=nanmuli_blog_2024` 是弱密码，若该密码曾被真实使用且未轮换，DB 直接暴露；④`deploy/docker-compose.yml:69,109` 强制要求 `CRAWLER_CALLBACK_API_KEY` 必须从 env 读取，说明该文件是部署必经路径。
- **影响**：**P0 级凭据泄漏**。只要仓库历史未清理（`git filter-repo`/BFG）且密钥未轮换，攻击者可：①用 `CRAWLER_CALLBACK_API_KEY` 伪造 Python 回调，向 `/api/internal/collector/callback` 注入任意任务状态、污染采集数据；②用 `CRAWLER_API_KEY` 直接调用 crawler-service 任意接口；③用 `DB_PASSWORD` 直连 PostgreSQL；④用 `BLOG_SECURITY_ENCRYPTION_KEY` 解密 sys_config 表中所有 `{AES}` 加密的敏感配置（如 AI_API_KEY）；⑤用 `AI_API_KEY` 盗用 LLM 配额。
- **根因/分析**：`.gitignore` 规则在 `deploy/.env` 首次提交**之后**才添加，git 对已跟踪文件不应用 ignore 规则。后续虽通过某种方式停止跟踪（`git rm --cached` 或重新初始化），但历史 commit 不可变。**已排除**：这不是"配置项默认值弱"（§9 X02-11 是另一条），这是"真实凭据入库史"。
- **修复方向**：①**立即轮换全部 5 个密钥**（DB_PASSWORD、CRAWLER_API_KEY、CRAWLER_CALLBACK_API_KEY、BLOG_SECURITY_ENCRYPTION_KEY、AI_API_KEY）；②用 `git filter-repo` 或 BFG 清理 git 历史中的 `deploy/.env`（全量 `git log -p --all -- deploy/.env` 确认每个历史 commit）；③确认 `deploy/.env` 在所有环境（包括 CI/备份/开发者本地）中未被二次泄漏；④`check-deploy-env.ps1` 增加校验"工作区 .env 不在 git 跟踪且未出现在历史"。（改动面：大，跨工具链）
- **关联**：**主模块 X06**（配置一致性，本条由 X06 深查 env 三处）；**B09**（内部回调双向 key 主模块）；B07（AES key 轮换影响敏感配置解密）；横向主题"配置一致性"

### [P1] [Security] 鉴权纯靠 URL 前缀，无 @SaCheck*/@PreAuthorize 兜底，role 字段是死字段（"假 RBAC"）  <!-- 编号：B06-05 -->
- **定位**：`backend/src/main/java/com/nanmuli/blog/infrastructure/config/security/SaTokenConfig.java:32`（拦截器只调 `StpUtil.checkLogin()`）；全代码库 grep `@SaCheck|@PreAuthorize|hasRole|hasAuthority|checkRole|getRole` **零命中业务代码**；`UserAppService.java:24-46` 登录流程从不读取 `user.getRole()`
- **现象**：①拦截器对所有 `/api/admin/**` 只校验"是否登录"，不校验"是否 admin 角色"；②`User.java:24` 有 `role` 字段，`sys_user` 表有 `role` 列，但**全代码库无任何一处读取该字段做权限判定**；③登录成功后 `StpUtil.login(user.getId())` 只绑定 userId，不绑定 role/permissions；④任何能登录的用户（无论 role 字段是 'admin'/'ADMIN'/'user'/'xxx'）都能访问所有 `/api/admin/**` 接口。
- **影响**：①**当前单人博客场景下无实际越权风险**（只有 1 个 admin 账号，role 字段恒为 'admin'/'ADMIN'），但这是"靠人数=1 兜底"而非"靠机制兜底"；②一旦未来新增第二个用户（即使 role='user'），该用户登录后能访问所有 admin 接口——**静默越权**，无任何报错；③role 字段的存在给人"有 RBAC"的错觉，实际是死字段，维护者可能误以为已做角色隔离。
- **根因/分析**：MVP 阶段简化为单角色单用户，role 字段为预留但未接入鉴权链路。已排除：不是"忘了加注解"，而是"整体设计就是单用户，role 是占位"。
- **修复方向**：①**短期**：在 SaTokenConfig 拦截器内或自定义 `SaInterceptor` 中，对 `/api/admin/**` 增加 `StpUtil.checkRoleOr("admin", "ADMIN")`（配合 Sa-Token `StpInterfaceImpl` 实现，从 User 表读 role）；②**中期**：引入 `@SaCheckRole("admin")` 注解到 admin Controller 类级别作为防御性兜底；③统一 role 大小写（见 B06-11）。（改动面：中）
- **关联**：§9 已知线索"[Security/P2] 鉴权纯靠 URL 前缀"——本条**升级为 P1**并补充"role 死字段"新细节；横向主题"鉴权机制一致性"（§2.6）；关联 B06-11（角色大小写）

### [P1] [Security] sys_login_log 表存在但代码从不写入，登录失败次数/锁定/审计完全缺失  <!-- 编号：B06-06 -->
- **定位**：`backend/src/main/resources/db/init.sql:69`（`sys_login_log` 表定义）；grep `LoginLog|loginLog|insertLoginLog|sys_login_log` 在 `backend/src/main/java` **零命中**（只在 SQL 文件出现）；`UserAppService.java:24-46` 登录成功只更新 `login_ip`/`login_time` 到 `sys_user`，**登录失败无任何记录**
- **现象**：①`sys_login_log` 表有完整 DDL（user_id/ip/location/user_agent/status/message/created_at + 2 个索引），但**全代码库无任何 Mapper/Service/Repository 读写它**——死表；②`UserAppService.login` 密码错误时只 `throw new BusinessException("用户名或密码错误")`，不记录失败日志、不累计失败次数、不触发账号锁定；③用户名不存在时同样抛相同异常（避免账号枚举，这点是对的），但同样无日志。
- **影响**：①**无登录审计**：发生攻击后无法追溯"何时/何 IP 尝试登录、失败多少次"；②**无爆破防护闭环**：虽有 `RateLimitFilter`（60 次/min/IP，见 B06-08），但这是"全局 IP 限流"而非"登录失败累计锁定"——攻击者用多 IP 代理池可绕过；③单人博客 + 弱密码 `admin123`（§9 X02-11）+ 无锁定 = 在限流阈值内可暴力破解；④死表本身是 schema/代码漂移（声明能力但未实现）。
- **根因/分析**：表是按"完整后台系统"模板建的，但实现只做了 MVP 最小集（仅更新 login_time）。已排除：不是"日志走 logback 文件就够了"——`sys_login_log` 是结构化审计表，与 logback 文本日志用途不同。
- **修复方向**：①实现 `LoginLogService`，在 `UserAppService.login` 的成功/失败分支都写入 `sys_login_log`（含 ip/ua/status）；②增加"连续失败 N 次锁定账号 X 分钟"逻辑（可用 Redis 计数）；③或若决定不做，删除 `sys_login_log` 表避免漂移。（改动面：中）
- **关联**：§9 已知线索"[Test/P2] Auth 零覆盖"——本条补充"登录审计能力声明但未实现"；次维度 [Arch]（死表漂移）

### [P2] [Security] X-Callback-Key 校验用 String.equals（非恒定时间比较），存在时序攻击理论风险  <!-- 编号：B06-07 -->
- **定位**：`backend/src/main/java/com/nanmuli/blog/infrastructure/config/security/SaTokenConfig.java:55`（`expectedKey.equals(requestKey)`）；`backend/src/main/java/com/nanmuli/blog/interfaces/rest/InternalCallbackController.java:67`（`!expectedKey.equals(callbackKey)`）、line 77、line 82
- **现象**：四处 callback key 比较全部用 `String.equals`，该 API 在首个字符不匹配时立即返回，响应时延与"前缀匹配长度"正相关。
- **影响**：理论上攻击者可通过精确测量响应时延，逐字节猜出 callback key（时序攻击）。**但**：①需攻击者能稳定测量毫秒级时延（要求网络位置近、无抖动）；②key 长度 32 字符，逐字节爆破需大量样本，实际可行性低；③key 同时受"localhost 拦截器"保护（外部网络默认进不来 `/api/internal/**`，见 `SaTokenConfig.java:36-49`），时序攻击需先突破网络层。综合：单人博客场景威胁等级 P2（理论风险 > 实际可利用性）。
- **根因/分析**：Java `String.equals` 非恒定时间。已排除：`MessageDigest.isEqual` 才是恒定时间替代品。
- **修复方向**：将四处比较改为 `MessageDigest.isEqual(expected.getBytes(), actual.getBytes())`。（改动面：小）
- **关联**：B09（内部回调主模块）引用本条；次维度 [Security]

### [P2] [Security] 登录接口限流阈值偏宽松（60 次/min/IP），无登录失败累计锁定  <!-- 编号：B06-08 -->
- **定位**：`backend/src/main/java/com/nanmuli/blog/interfaces/filter/RateLimitFilter.java:29`（`max-requests:60`）、line 89-94（`shouldRateLimit` 对 `/api/` 限流，排除 `/api/admin/`、`/api/internal/`——**`/api/auth/login` 在 `/api/` 下，会被限流**）
- **现象**：①登录接口受 IP 限流保护，阈值 60 次/min（默认），可通过 `rate-limit.max-requests` 调整；②`resolveClientIp`（line 96-112）**仅在受信任代理后才读 X-Forwarded-For**（line 100），默认 `trusted-proxies` 为空，直接用 `request.getRemoteAddr()`——**X-Forwarded-For 伪造风险已规避**（这是对的，记为正向发现）；③但 60 次/min 对登录爆破而言仍偏宽松（8 位密码字典攻击，60/min ≈ 8.6 万次/天），且无"单账号失败锁定"。
- **影响**：与 B06-06 叠加，构成"弱密码 + 无锁定 + 宽松限流"的爆破窗口。但限流对单 IP 有效，攻击者需代理池。
- **根因/分析**：限流设计是全局 API 限流，非专门登录保护。
- **修复方向**：①为 `/api/auth/login` 单独配置更严限流（如 10 次/min/IP）；②配合 B06-06 的账号锁定；③保持现有 trusted-proxies 机制（已正确）。（改动面：小）
- **关联**：关联 B06-06；次维度 [Security]

### [P3] [Security] Sa-Token active-timeout=-1（无活动超时），cookie secure 默认 false  <!-- 编号：B06-09 -->
- **定位**：`backend/src/main/resources/application.yml:29`（`active-timeout: -1`）、line 38（`cookie.secure: false`）；`application-prod.yml:31-32`（`cookie.secure: ${COOKIE_SECURE:false}`，生产默认仍 false）
- **现象**：①`active-timeout: -1` 表示 token 一旦签发，30 天内（`timeout: 2592000`）无论是否活动都不因"长时间不操作"失效——token 泄漏后 30 天有效窗口；②`cookie.secure` 在 dev 和 prod 默认都是 false，需显式设 `COOKIE_SECURE=true` 才走 HTTPS-only——生产若忘记设，Cookie 会通过 HTTP 明文传输。
- **影响**：①active-timeout=-1 在单人博客场景可接受（个人习惯长期登录），但 token 泄漏后无"自动失活"兜底；②cookie.secure 默认 false 是**生产陷阱**——部署时若反向代理终止 TLS 但后端以为 HTTP，或忘记设 env，Cookie 明文暴露。`same-site: Lax`（line 39）提供基础 CSRF 防护（已正确）。
- **根因/分析**：dev/prod 共用默认 false 是为本地 HTTP 调试方便，但 prod 应强制 true。
- **修复方向**：①`application-prod.yml` 将 `cookie.secure` 默认值改为 true（或用 `${COOKIE_SECURE:true}`）；②考虑 active-timeout 设为 7 天，平衡安全与体验；③部署文档强调 `COOKIE_SECURE=true`。（改动面：小）
- **关联**：X06（配置一致性）；Cookie+CSRF 技术栈重点

### [P3] [Security] CORS allowedOriginPatterns 配置：生产有白名单兜底，但 env 未设时回退通配  <!-- 编号：B06-10 -->
- **定位**：`backend/src/main/java/com/nanmuli/blog/infrastructure/config/web/WebMvcConfig.java:40-49`（`resolveOriginPatterns`，`allowedOrigins` 为空时返回 `{"*"}`）；`application-prod.yml:75`（`CORS_ALLOWED_ORIGINS:https://nanmu.xyz,http://nanmu.xyz` 生产有默认白名单）
- **现象**：①用 `allowedOriginPatterns`（非 `allowedOrigins`），配合 Sa-Token Cookie 模式（隐式 allowCredentials）——Spring 对 `allowedOriginPatterns("*")` + credentials 不抛错（这是它和 `allowedOrigins` 的区别），技术上可行；②**但**当 `cors.allowed-origins` 配置项为空时，`resolveOriginPatterns` 返回 `{"*"}`，等于"任意 Origin 可携带 Cookie 跨域请求"——CSRF 防护仅靠 `SameSite=Lax`；③生产 yml 有默认白名单，所以生产默认安全；**但若 `CORS_ALLOWED_ORIGINS` env 显式设为空字符串**，会覆盖 yml 默认值吗？[需查证] Spring `@Value` 对空字符串的处理：`${CORS_ALLOWED_ORIGINS:https://...}` 中 env 存在但为空时，`@Value` 注入空字符串，触发 `{"*"}` 回退。
- **影响**：配置错误（env 设空）会导致 CORS 全开放。SameSite=Lax 能挡大部分 CSRF，但挡不了同站子域攻击。
- **根因/分析**：回退逻辑用"空=全开放"是危险默认。**归 B16 主模块**（CORS/全局基础设施），本报告记交叉。
- **修复方向**：见 B16 报告。本模块视角：确保生产 `CORS_ALLOWED_ORIGINS` 永远显式设白名单。（改动面：小，但归 B16）
- **关联**：**主模块 B16**；Cookie+CSRF / CORS 技术栈重点；[需查证] env 空值覆盖行为

---

## `[Arch]` 架构与技术债

> 排查范围：鉴权分层、拦截器与 Filter 职责边界、role 模型设计、内部回调双重鉴权。命中如下。

### [P1] [Arch] sys_user.role 大小写三轨不一致（X02-11），当前不致功能故障但是"假 RBAC"地雷  <!-- 编号：B06-11 -->
- **定位**：`backend/src/main/resources/data.sql:6`（种 `'admin'` 小写）；`backend/src/main/resources/db/init.sql:927`（种 `'ADMIN'` 大写）；`deploy/db/init-scripts/schema.sql:889`（种 `'ADMIN'` 大写）；`schema.sql:40` + `init.sql:39`（列默认值 `'ADMIN'`）；`User.java:24`（`private String role`，无枚举约束）
- **现象**：①data.sql 种子用小写 `'admin'`，init.sql/schema.sql 种子用大写 `'ADMIN'`，列默认值 `'ADMIN'`——三轨不一致；②**但全代码库无任何一处读取 role 做大小写敏感比较**（见 B06-05，role 是死字段），所以**当前 admin 账号能正常登录和访问所有 admin 接口**，**X02-11 角色大小写不一致当前不造成功能性影响**。
- **影响**：①**当前无功能影响**（明确结论，回答 X02-11）；②**但一旦未来按 B06-05 建议接入 role 校验**（如 `checkRoleOr("admin","ADMIN")` 或 `@SaCheckRole("admin")`），大小写敏感的比较会立即踩雷：若校验只写 `"admin"` 而 DB 种的是 `'ADMIN'`（init.sql/schema.sql 路径），admin 账号被锁；反之同理。这是"潜伏地雷"。
- **根因/分析**：三轨 schema 漂移（§9 已知线索 [Arch/P1] schema 三轨漂移）在 role 字段上的具体表现。data.sql 是 Spring `sql.init` 执行的（`application.yml:14-15`），init.sql/schema.sql 是 Docker init-scripts 执行的——不同初始化路径用不同大小写。
- **修复方向**：①统一 role 为大写 `'ADMIN'`（与列默认值和 schema.sql 一致），修改 data.sql 第 6 行；②或在 role 比较处统一 `toUpperCase()` 归一化；③接入 RBAC 时（B06-05）一并解决。（改动面：小，但归 B15 schema 主模块执行）
- **关联**：**回答 X02-11**；§9 已知线索；主模块 B15（schema 三轨漂移）；横向主题"schema 漂移"（§2.6）；关联 B06-05

### [P3] [Arch] 内部回调双重鉴权（SaTokenConfig 拦截器 + InternalCallbackController.authRequired）逻辑重复  <!-- 编号：B06-12 -->
- **定位**：`backend/src/main/java/com/nanmuli/blog/infrastructure/config/security/SaTokenConfig.java:36-49`（拦截器校验 localhost 或 X-Callback-Key）；`backend/src/main/java/com/nanmuli/blog/interfaces/rest/InternalCallbackController.java:50-68`（`authRequired` 方法再次校验 X-Callback-Key）
- **现象**：`/api/internal/**` 被两层校验：①SaTokenConfig 的 HandlerInterceptor（localhost 直通，否则校验 X-Callback-Key）；②Controller 内每个方法的 `authRequired` / `configAuthRequired`（再次校验 X-Callback-Key）。两层逻辑口径一致，但代码重复。
- **影响**：①维护成本翻倍（改 key 校验逻辑要改两处）；②`/config` 端点的 `configAuthRequired`（line 75-95）还多接受 `crawler.service.api-key`——这种"特例"只在 Controller 层有，拦截器层不知道，**语义割裂**；③但功能上无害（双重校验更严，不会漏判）。
- **根因/分析**：防御性编程 + 历史演进（拦截器先有，Controller 内校验后加）。**归 B09 主模块**（内部回调），本报告记交叉。
- **修复方向**：见 B09 报告。本模块视角：鉴权逻辑应集中。（改动面：中，归 B09）
- **关联**：**主模块 B09**；横向主题"鉴权机制一致性"

---

## `[Deps]` 依赖升级与版本

### 本模块依赖清单（基于声明文件，未翻依赖源码）

| 依赖 | 版本 | 声明位置 | 已知风险/可升级 | 备注 |
|---|---|---|---|---|
| sa-token-spring-boot3-starter | 1.44.0 | `backend/pom.xml:60-62` | Sa-Token 1.44 为 2025 年版本，最新主线 1.4x 系列；无已知关键 CVE [需查证] | Cookie 模式 + alone-redis |
| sa-token-redis-jackson | 1.44.0 | `backend/pom.xml:65-67` | 同上 | token 持久化到 alone-redis db1 |
| hutool-all | 5.8.36 | `backend/pom.xml:79-81` | hutool 5.x 已进入维护，主线转向 6.x [需查证] 6.x API 变动 | 本模块用 `BCrypt.checkpw` |
| spring-boot-starter-parent | 3.3.5 | `backend/pom.xml:9` | Spring Boot 3.3.x，3.4 已发布 [需查证] 升级影响 | 传递 spring-security-crypto 等 |

> 排查范围：仅本模块鉴权相关依赖（Sa-Token、hutool BCrypt、Spring Boot 基线）。MyBatis/Redis/PG 归 B14。未命中独立 CVE 级发现（基于训练知识，标 [需查证] 需 `mvn dependency-tree` 或官方 advisory 确认）。

### [P4] [Deps] Sa-Token 1.44 与 hutool 5.8 均非最新主线，建议跟踪升级窗口  <!-- 编号：B06-13 -->
- **定位**：`backend/pom.xml:20`（`<sa-token.version>1.44.0</sa-token.version>`）、line 22（`<hutool.version>5.8.36</hutool.version>`）
- **现象**：Sa-Token 1.44.0（2025 年中版本）、hutool 5.8.36（5.x 维护线）。两者均非绝对最新。
- **影响**：无已知阻断性 CVE（[需查证] 官方 advisory）。升级主要价值是获得安全补丁与新特性（如 Sa-Token 更细粒度的注解、hutool 6.x 性能）。
- **根因/分析**：版本不算陈旧，属常规跟踪。
- **修复方向**：①定期关注 Sa-Token/hutool 官方 advisory；②升级前跑 Auth 相关测试（当前 Auth 测试覆盖=0，见 §9，需先补测试）。（改动面：中）
- **关联**：§9 [Test/P2] Auth 零覆盖

---

## `[Design]` 功能设计合理性

> 从真实使用（单人维护的技术博客 + 每工作日 AI 日报）出发，回答 §2.5 相关问题。

**审视结论**：

1. **场景适配（§2.5-1）**：单人博客场景下，**Sa-Token + Cookie 模式 + alone-redis db1 隔离** 是过度设计的——alone-redis 单独开 db1 存 token、单独配连接池，对单用户系统是"用大炮打蚊子"。但这是合理的"预留扩展"（未来若多用户/多端登录，基础设施已就绪）。**`is-concurrent: false`（单点登录）符合单人单端习惯**（防止 token 泄漏后被并发滥用），设计合理。真正不匹配的是 **role 字段 + sys_login_log 表**——为"多用户后台系统"预留但未实现，形成死字段/死表（B06-05/06），属于"过度预留"。

2. **闭环完整性（§2.5-2）**：**登录闭环不完整**。有登录（BCrypt 校验 ✓）、有登出（`StpUtil.logout()` ✓）、有 token 失效（30 天 timeout ✓），但**缺登录失败闭环**：失败无日志（sys_login_log 死表）、无累计锁定、无账号禁用后的告警。对单人博客，"密码忘了被爆破"是真实风险（尤其弱密码 admin123），当前闭环在"失败处理"这一环断裂。

3. **可运维性（§2.5-3）**：**登录审计可运维性差**。发生疑似爆破时，运维只能看 nginx/AccessLogFilter 的文本日志（`AccessLogFilter.java` 记 status≥400），无法按 user_id/ip/时间结构化查询登录记录（sys_login_log 死表）。**token 强制失效手段缺失**——无"踢人下线"管理端点（`kickout`），若怀疑 token 泄漏，只能改密码触发 `is-concurrent` 逻辑或手动删 Redis db1 的 key。

### [P4] [Design] 登录审计与 token 管控缺失（运维体验断层）  <!-- 编号：B06-14 -->
- **定位**：`sys_login_log` 死表（B06-06）；无 `kickout`/强制下线端点；无登录历史查询接口
- **现象**：见上述审视结论 2、3。
- **影响**：故障/安全事件时定位困难，需手动翻文本日志或操作 Redis。
- **建议方向**：①激活 sys_login_log（B06-06）；②增加 admin 端"查看在线 token / 强制下线"端点（Sa-Token 原生支持 `StpUtil.kickout(loginId)`）。（改动面：中）
- **关联**：关联 B06-06；§2.5-2/3

---

## 模块小结

### 严重度统计

| 级别 | 数量 | 条目编号 |
|---|---|---|
| P0 | 1 | B06-04 |
| P1 | 3 | B06-05, B06-06, B06-11 |
| P2 | 4 | B06-01, B06-07, B06-08, B06-09 |
| P3 | 4 | B06-02, B06-03, B06-10, B06-12 |
| P4 | 2 | B06-13, B06-14 |

### Top 风险（本模块最该先看的 ≤3 条）

1. **B06-04 [P0] deploy/.env 真实密钥在 git 历史中泄漏** —— 凭据可被任何 clone 仓库者取出，必须立即轮换全部 5 个密钥并清理 git 历史。归 X06 主模块执行。
2. **B06-05 [P1] 鉴权纯靠 URL 前缀 + role 死字段（假 RBAC）** —— 当前单用户兜底，未来加用户即静默越权。建议拦截器层补 `checkRoleOr`。
3. **B06-06 [P1] sys_login_log 死表 + 无登录失败锁定** —— 弱密码 admin123 + 无锁定 + 宽松限流（60/min）= 爆破窗口。

### 修复优先级建议

- **立即**（P0/P1）：
  - B06-04：轮换全部密钥 + 清理 git 历史 + check-deploy-env 增加跟踪校验（归 X06）
  - B06-05：拦截器补角色校验（或显式声明"单用户不校验角色"并删除 role 字段避免误导）
  - B06-06：激活 sys_login_log + 登录失败锁定
  - B06-11：统一 role 大小写（归 B15 schema 主模块）
- **计划**（P2）：
  - B06-01：`/api/auth/info`/`logout` 纳入鉴权或显式 401
  - B06-07：X-Callback-Key 改恒定时间比较（`MessageDigest.isEqual`）
  - B06-08：登录接口单独限流（10/min/IP）
  - B06-09：prod `cookie.secure` 默认改 true
- **择机**（P3/P4）：
  - B06-02：删除 ConfigAppService 应用层冗余 isLogin
  - B06-03：login 事务与 Redis 写入分离
  - B06-10：CORS 回退逻辑（归 B16）
  - B06-12：内部回调双重鉴权收敛（归 B09）
  - B06-13：依赖升级跟踪
  - B06-14：登录审计/token 管控端点

### 排查盲区 / 待复核

- **[需查证-1] B06-10**：Spring `@Value("${CORS_ALLOWED_ORIGINS:https://...}")` 当 env `CORS_ALLOWED_ORIGINS` 显式设为空字符串时，注入的是空字符串还是走默认值？若注入空字符串，则触发 `{"*"}` 回退——需实测或查 Spring 文档确认。
- **[需查证-2] B06-01**：`NotLoginException` 在 GlobalExceptionHandler 中是否映射为 401？若映射为 500，`/api/auth/info` 未登录访问会返回 500（信息泄漏+语义错误）——需读 GlobalExceptionHandler 确认（归 B16 异常处理主模块）。
- **[需查证-3] B06-13**：Sa-Token 1.44.0 / hutool 5.8.36 是否有已知 CVE——需查官方 advisory（命令边界禁止外网，本轮无法验证）。
- **[需查证-4] B06-04**：git 历史中 `deploy/.env` 的全部历史 commit 是否都已确认含真实密钥（本轮只验证了 `4523b7f` 的 DB_PASSWORD 和工作区现状）——清理历史前需 `git log -p --all -- deploy/.env` 全量确认。
- **[需查证-5]**：Sa-Token alone-redis db1 是否真与业务 db0 物理隔离（`application-prod.yml:33-42` 配置正确，但未运行时验证 Redis 实际 key 分布）——需 `redis-cli -n 1 keys 'satoken:*'` 确认。
