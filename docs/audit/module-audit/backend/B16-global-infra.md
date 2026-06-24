# B16 全局基础设施 排查报告

> **模块编号**：B16
> **排查范围**：全局异常处理、Filter 链（TraceId/限流/访问日志）、Knife4j、CORS、Web 配置
> **基线 commit**：`6ae930098405f4d0553d96a852f3345d0f39682e`
> **工作区状态**：脏（未提交改动均不在本模块范围：`ConfigRepositoryImpl.java`、`WebCollectPageMapper.java`、`crawler-service/*`、`deploy/README.md`、`risk-register.md`、`release-gate.ps1`、新增 `webcollector/` 测试目录）。本模块涉及的 `interfaces/filter/*`、`interfaces/handler/*`、`infrastructure/config/web/*`、`infrastructure/config/security/SaTokenConfig.java` 均为干净状态。
> **排查日期**：2026-06-23
> **排查人**：B16 audit agent
> **状态**：完成

---

## 模块概览

**职责**：为所有 HTTP 请求提供横切基础设施——MDC traceId 注入、IP 限流、访问日志、统一异常映射、CORS、API 文档（Knife4j）、RestTemplate Bean。

**关键文件**：
- `backend/src/main/java/com/nanmuli/blog/interfaces/filter/TraceIdFilter.java:12` —— MDC traceId 注入与清理
- `backend/src/main/java/com/nanmuli/blog/interfaces/filter/RateLimitFilter.java:27` —— 基于 IP 的滑窗限流（/api/** 非 admin/internal）
- `backend/src/main/java/com/nanmuli/blog/interfaces/filter/AccessLogFilter.java:16` —— 访问日志（method/path/status/duration，按状态分级）
- `backend/src/main/java/com/nanmuli/blog/interfaces/handler/GlobalExceptionHandler.java:27` —— @RestControllerAdvice 统一异常映射
- `backend/src/main/java/com/nanmuli/blog/infrastructure/config/web/WebMvcConfig.java:14` —— CORS + 静态资源 handler
- `backend/src/main/java/com/nanmuli/blog/infrastructure/config/web/Knife4jConfig.java:11` —— OpenAPI 文档分组
- `backend/src/main/java/com/nanmuli/blog/infrastructure/config/web/WebConfig.java:13` —— RestTemplate Bean
- `backend/src/main/java/com/nanmuli/blog/infrastructure/config/security/SaTokenConfig.java:20` —— 鉴权拦截器（本模块仅查其与 CORS/Filter 交叉点）
- `backend/src/main/resources/logback-spring.xml:9` —— 日志 pattern 含 `%X{traceId}`

**对外接口 / 依赖**：
- 对外：无 Controller；通过 Servlet Filter 链 + @RestControllerAdvice 作用于所有 `/api/**`。
- 依赖：Sa-Token 1.44.0（异常类型）、logstash-logback-encoder（prod JSON 日志）、配置 key `rate-limit.*` / `cors.*` / `blog.file.*`。

**已读文件清单**（可追溯 + 暴露盲区）：
- `interfaces/filter/TraceIdFilter.java` —— 通读
- `interfaces/filter/RateLimitFilter.java` —— 通读
- `interfaces/filter/AccessLogFilter.java` —— 通读
- `interfaces/handler/GlobalExceptionHandler.java` —— 通读
- `infrastructure/config/web/WebMvcConfig.java` —— 通读
- `infrastructure/config/web/Knife4jConfig.java` —— 通读
- `infrastructure/config/web/WebConfig.java` —— 通读
- `infrastructure/config/security/SaTokenConfig.java` —— 通读（仅查交叉点，鉴权本身归 B06）
- `application.yml` / `application-dev.yml` / `application-prod.yml` —— 通读
- `logback-spring.xml` —— 通读
- `shared/exception/BusinessException.java` / `shared/result/Result.java` —— 通读
- `application/user/UserAppService.java` —— 通读（确认密码是否进异常 message）
- `frontend/src/utils/request.ts` —— 片段（确认 withCredentials）
- 仅 grep：`@Order` 全局、`MDC` 全局、`knife4j/springdoc` 配置、密码日志

**主模块归属**：本模块深查全局 Web 基础设施自身。对 Sa-Token 鉴权机制（B06）、AES 加密（B07）只引用，不展开。

---

## `[Bug]` 代码正确性与潜在缺陷

> 排查范围：三个 Filter、GlobalExceptionHandler、WebMvcConfig、logback pattern。

### [P2] [Bug] TraceIdFilter 缺少 @Order，导致其在限流/访问日志 Filter 之后执行，traceId 丢失 <!-- 编号：B16-01 -->
- **定位**：`backend/src/main/java/com/nanmuli/blog/interfaces/filter/TraceIdFilter.java:11-12`（无 `@Order` 注解）
- **现象**：`TraceIdFilter` 类上只有 `@Component`，没有 `@Order`。对比 `RateLimitFilter:26`（`@Order(HIGHEST_PRECEDENCE + 1)`）、`AccessLogFilter:15`（`@Order(HIGHEST_PRECEDENCE + 2)`）。Spring Boot 把 `@Component` Filter 注册到 Servlet 容器时，无 `@Order` 默认为 `Ordered.LOWEST_PRECEDENCE`（int 最大值）。实际执行顺序为：RateLimit → AccessLog → … → TraceId（最后）。
- **影响**：①`RateLimitFilter` 在 `doFilter:78` 打 `log.warn("[RateLimit] IP … exceeded …")` 时，MDC 里还没有 traceId（logback pattern `[%X{traceId}]` 输出空），该限流告警日志无法与后续业务日志关联；②`AccessLogFilter:39-46` 的访问日志同理缺 traceId；③当请求被 RateLimitFilter 提前 `return`（429），TraceIdFilter 的 `chain.doFilter` 根本不会被调用，整个请求生命周期 MDC 都没有 traceId。
- **根因/分析**：TraceId 是"请求级关联标识"，设计意图是最外层注入、最外层清理。当前顺序恰好颠倒。已排除误判：logback pattern 确实引用了 `%X{traceId}`（`logback-spring.xml:9`），所以顺序问题会产生可观测的日志缺失，而非无害。
- **修复方向**：给 `TraceIdFilter` 加 `@Order(Ordered.HIGHEST_PRECEDENCE)`（比 RateLimit 更高，确保最先执行、最后清理）。改动面 **小**（单文件加注解）。
- **关联**：次维度 `[Arch]` 可运维性；与 B17（调度/异步）的 traceId 透传无关。

### [P3] [Bug] RequestCounter 滑动窗口计数在高并发下存在计数泄漏窗口（reset 与 increment 非原子） <!-- 编号：B16-02 -->
- **定位**：`backend/src/main/java/com/nanmuli/blog/interfaces/filter/RateLimitFilter.java:137-148`
- **现象**：`incrementAndGet()` 先无锁检查 `now - windowStart > windowMillis`，命中后用 `synchronized` 双检并 `windowStart = now; count.set(0)`，然后 `count.incrementAndGet()`。`windowStart` 是 `volatile`，`count` 是 `AtomicInteger`，但"判窗 + 重置 + 自增"不是原子序列。
- **影响**：窗口边界瞬间多线程并发时，可能出现短暂的计数偏多或偏少（个位数级别），对"单人博客 60 次/分钟"阈值几乎无实际影响。非安全级问题。
- **根因/分析**：这是典型的"双检锁滑动窗口"实现，对个人博客场景够用；严格场景应改用 `synchronized` 整体或令牌桶。已排除误判：`count.set(0)` 后立即 `incrementAndGet` 保证重置后第一次请求计数为 1，逻辑正确。
- **修复方向**：维持现状即可；若需严格可改为整体 `synchronized` 或引入 Caffeine 限流。改动面 **小**（但无必要）。
- **关联**：次维度 `[Design]` 阈值合理性。

### [P3] [Bug] GlobalExceptionHandler 未捕获 Throwable，Error 类异常会穿透到容器默认错误页 <!-- 编号：B16-03 -->
- **定位**：`backend/src/main/java/com/nanmuli/blog/interfaces/handler/GlobalExceptionHandler.java:132`（`@ExceptionHandler(Exception.class)`）
- **现象**：兜底 handler 只捕获 `Exception`，不捕获 `Throwable`。`OutOfMemoryError`、`StackOverflowError`、`NoClassDefFoundError` 等会穿透 @RestControllerAdvice，由 Servlet 容器返回默认 500 错误页（可能泄漏容器版本/堆栈）。
- **影响**：生产环境 OOM 等极端场景下，返回给前端的不是统一的 `Result.error(500, "系统繁忙")`，而是容器原始错误响应，可能泄漏信息。但这类 Error 本身已意味着 JVM 不可用，影响有限。
- **根因/分析**：业界惯例是不捕获 `Error`（捕获了也无法恢复）。此处记录为已知边界，不强制修改。
- **修复方向**：维持现状（不捕获 Error 是合理的）；或新增 `@ExceptionHandler(Throwable.class)` 仅做日志记录后重抛，避免吞掉 JVM 致命错误。改动面 **小**（建议维持）。
- **关联**：次维度 `[Security]` 信息泄漏（低）。

---

## `[Security]` 安全漏洞

> 排查范围：CORS 配置、限流可绕过性、异常信息泄漏、密码脱敏、Knife4j 暴露。逐项对照计划 §2.2。

### [P2] [Security] dev 环境默认 CORS 放行任意 Origin（`*`），配合 Cookie 模式存在 CSRF/凭证泄漏面 <!-- 编号：B16-04 -->
- **定位**：`backend/src/main/java/com/nanmuli/blog/infrastructure/config/web/WebMvcConfig.java:40-43`（`resolveOriginPatterns` 当 `allowedOrigins` 空时返回 `{"*"}`）+ `application-dev.yml:66-69`（未设置 `cors.allowed-origins`）
- **现象**：dev profile 的 `application-dev.yml` 未配置 `cors.allowed-origins`，`WebMvcConfig.resolveOriginPatterns()` 回退到 `new String[]{"*"}`。`addCorsMappings:33-37` 使用 `allowedOriginPatterns("*")` + `allowedHeaders("*")`。Sa-Token 配置 `token-from-cookie: true`（`application.yml:35`），Cookie 跨域随请求发送。
- **影响**：dev 环境下任意网站都能向 dev 后端发跨域请求并携带 Cookie（若前端开了 withCredentials）。结合 Sa-Token Cookie 鉴权，恶意站点可借已登录管理员的 Cookie 发起写操作（CSRF），`same-site: Lax` 只挡跨站 POST 的部分场景（导航类 GET 仍放行）。prod profile 默认值是 `https://nanmu.xyz,http://nanmu.xyz`（`application-prod.yml:75`），风险被收敛到 dev。
- **根因/分析**：①dev 配置疏漏（写了 `cors:` 段但没填 `allowed-origins`）；②`resolveOriginPatterns` 的回退逻辑把"未配置"等同于"全放行"，这是危险默认值——安全默认应是"拒绝"而非"允许"。已排除误判：前端 `request.ts:46-47` 注释提到"如需跨域确保后端允许 credentials"，但前端 axios 实例未显式设 `withCredentials: true`（`request.ts:27-33`），所以当前**默认不会跨域带 Cookie**，CSRF 触发需要前端额外配置才成立；但 CORS `*` 本身仍允许任意站点读取 API 响应（公开内容本就公开，影响有限）。
- **修复方向**：①给 dev profile 补 `cors.allowed-origins: http://localhost:3001,http://localhost:5173`（参考 `deploy/.env:13` 已有 localhost:3001）；②把 `resolveOriginPatterns` 的空值回退从 `{"*"}` 改为 `{"http://localhost:*"}` 或抛启动失败（安全默认）。改动面 **小**。
- **关联**：横向主题"鉴权机制一致性"（B06）；次维度 `[Design]` 安全默认值。

### [P2] [Security] allowCredentials 未显式配置，Sa-Token Cookie 跨域场景下鉴权可能静默失败 <!-- 编号：B16-05 -->
- **定位**：`backend/src/main/java/com/nanmuli/blog/infrastructure/config/web/WebMvcConfig.java:32-38`
- **现象**：`addCorsMappings` 未调用 `.allowCredentials(true)`。Spring 的 CORS 规则：未显式开启时 `allowCredentials=false`，浏览器不会在跨域请求中发送 Cookie。Sa-Token 用 `token-from-cookie: true` 走 Cookie。
- **影响**：当前后端默认 `allowCredentials=false`，跨域前端（非同源部署）登录后 Cookie 不会被浏览器发送 → 所有 `/api/admin/**` 请求都拿不到 token → 全部 401。**当前规避**：前端 `request.ts` 默认不设 withCredentials，且若前后端同源部署（nginx 反代）则无跨域问题，所以 MVP 阶段可能没暴露。一旦真分域名部署且依赖 Cookie 鉴权，这是阻断性问题。
- **根因/分析**：Spring 用 `allowedOriginPatterns`（非 `allowedOrigins`）时，是允许 `allowCredentials(true)` 与通配 pattern 共存的；但当前代码两样都没配。这是"看起来 CORS 配了实则 Cookie 跨域不工作"的半成品状态。已排除误判：prod 白名单是具体域名，技术上可以安全地 `allowCredentials(true)`。
- **修复方向**：①明确决策——若同源部署则维持现状（无跨域）；若计划分域，补 `.allowCredentials(true)` 并确保 `allowedOriginPatterns` 不含 `*`。②前端配套加 `withCredentials: true`。改动面 **小**（后端）+ **小**（前端）。
- **关联**：横向主题"鉴权机制一致性"（B06 Sa-Token Cookie）、"跨服务契约一致性"（前端 request.ts 归 F02）。

### [P3] [Security] TraceIdFilter 接受客户端任意 X-Trace-Id 不做校验，可向日志注入任意字符串 <!-- 编号：B16-06 -->
- **定位**：`backend/src/main/java/com/nanmuli/blog/interfaces/filter/TraceIdFilter.java:19-22`
- **现象**：直接读取请求头 `X-Trace-Id` 原值放入 MDC，无长度限制、无字符集校验。攻击者可传入包含换行符 `\n`、CRLF、超长字符串或伪造其他用户 traceId 的值。
- **影响**：①日志注入（CRLF 伪造日志行，干扰审计）；②MDC 值进入 JSON 日志的 `traceId` 字段（logstash encoder），可能破坏 JSON 结构或撑大日志体积；③可伪造 traceId 关联，混淆排障。
- **根因/分析**：个人博客场景影响低，但修复成本极低。已排除误判：MDC 值确实流入 logback pattern 和 JSON encoder（`logback-spring.xml:9,24`）。
- **修复方向**：校验 `X-Trace-Id` 仅允许 `[a-zA-Z0-9-]{8,64}`，不合法则忽略并生成新 UUID。改动面 **小**。
- **关联**：次维度 `[Bug]` 输入校验。

### [P3] [Security] RateLimitFilter 的限流豁免使 admin/internal 接口完全无限流 <!-- 编号：B16-07 -->
- **定位**：`backend/src/main/java/com/nanmuli/blog/interfaces/filter/RateLimitFilter.java:89-94`
- **现象**：`shouldRateLimit` 对 `/api/admin/**` 和 `/api/internal/**` 直接返回 false（不限流）。
- **影响**：admin 接口（登录 `/api/auth/login` 被排除在 admin 外，但 `/api/admin/**` 全部管理操作）和 internal 回调接口完全不受 IP 限流保护。`/api/auth/login` 实际走的是 `/api/auth/` 前缀（被限流覆盖，OK）；但若 admin 凭证泄漏，攻击者可对 admin 写接口无限调用（暴力写/扫数据）。internal 接口有 localhost + X-Callback-Key 双重保护（`SaTokenConfig:36-49`），风险低。
- **根因/分析**：设计意图是"限流只保护公开 API，admin 已有鉴权"。但鉴权与限流是正交防线，admin 接口同样应有限流（防凭证爆破后的批量操作）。这是设计取舍，非 bug。
- **修复方向**：为 admin 路径设置更宽松但存在的限流（如 600 次/分钟），或对 `/api/auth/login` 单独设更严阈值（防密码爆破）。改动面 **小**。
- **关联**：横向主题"鉴权机制一致性"（B06）；次维度 `[Design]` 纵深防御。

### [P3] [Security] GlobalExceptionHandler 兜底 handler 把完整堆栈写入日志（含可能的敏感参数） <!-- 编号：B16-08 -->
- **定位**：`backend/src/main/java/com/nanmuli/blog/interfaces/handler/GlobalExceptionHandler.java:139`（`log.error(..., e)` 传入异常对象）
- **现象**：`handleException` 对 `desensitize(e.getMessage())` 做了脱敏，但 `log.error(..., e)` 的第三个参数会把整个异常对象（含 stack trace、cause chain、嵌套的各层 message）写入日志。脱敏只覆盖了最外层 message，内层异常 message 和堆栈里的局部变量不脱敏。
- **影响**：①返回给前端的 message 是固定"系统繁忙"（`Result.error(500, ...)`），无前端泄漏，OK；②但日志里可能记录数据库异常细节、SQL 片段、配置值等。日志文件访问受服务器权限保护，影响可控。
- **根因/分析**：这是"日志用于排障 vs 日志最小化"的权衡。当前偏排障友好。脱敏正则 `(password|pwd|secret|key)=...` 只匹配 `key=value` 形式，不匹配 JSON 里的 `"password":"xxx"` 或异常堆栈里的 `password=xxx` 片段（实际能匹配后者）。覆盖面有限但非缺失。
- **修复方向**：维持现状（排障需要堆栈）；若合规要求可改为只记录异常类名 + traceId，堆栈按需开关。改动面 **小**（建议维持）。
- **关联**：次维度 `[Bug]` 日志治理。

---

## `[Arch]` 架构与技术债

> 排查范围：Filter 注册机制、配置回退默认值、Web 配置散布。

### [P3] [Arch] Web 相关配置散布在 WebConfig/WebMvcConfig/Knife4jConfig 三个类，CORS 与静态资源混在同一类 <!-- 编号：B16-09 -->
- **定位**：`infrastructure/config/web/WebConfig.java`（RestTemplate）、`WebMvcConfig.java`（CORS + 静态资源）、`Knife4jConfig.java`（OpenAPI）
- **现象**：三个 `@Configuration` 类职责细碎：`WebMvcConfig` 同时管 CORS 映射和文件静态资源 handler；RestTemplate 单独一个类；Knife4j 单独一个类。
- **影响**：可维护性轻微下降——改 CORS 要去 `WebMvcConfig`，改静态资源也在同一类，职责不纯。个人项目规模下可接受。
- **根因/分析**：非技术债，是组织习惯。无需强制重构。
- **修复方向**：维持现状；若整理可将 `WebMvcConfig` 拆为 `CorsConfig` + `ResourceConfig`。改动面 **小**（可选）。
- **关联**：无。

### [P3] [Arch] RateLimitFilter 使用 ConcurrentHashMap + 定时清理，未复用 Spring 已有的缓存/限流基建 <!-- 编号：B16-10 -->
- **定位**：`backend/src/main/java/com/nanmuli/blog/interfaces/filter/RateLimitFilter.java:42-43,50-55`
- **现象**：自建 `ConcurrentHashMap<String, RequestCounter>` + 守护线程 `ScheduledExecutorService` 定时清理。项目已引入 Redis（`spring.cache.type: redis`），限流本可用 Redis 原子计数实现分布式限流。
- **影响**：①单实例限流（多实例部署时每个实例独立计数，实际阈值翻倍）；②多一个自管线程和 Map，重启丢失计数。个人博客单实例场景无影响。
- **根因/分析**：MVP 阶段单实例，本地内存限流足够。未来若水平扩容需改造。已排除误判：项目 `docker-compose` 只有一个 backend 实例（X01 范围）。
- **修复方向**：维持现状；扩容时改为 Redis INCR + EXPIRE。改动面 **中**（未来）。
- **关联**：次维度 `[Design]` 单点扩展（§2.5-7）。

### [P4] [Arch] GlobalExceptionHandler 部分分支返回 ResponseEntity、部分返回裸 Result，HTTP 状态码不一致 <!-- 编号：B16-11 -->
- **定位**：`backend/src/main/java/com/nanmuli/blog/interfaces/handler/GlobalExceptionHandler.java:30,44,53,59,68,75,84,93,106,127,133`
- **现象**：`handleBusinessException` 返回 `ResponseEntity<Result<Void>>` 并设置真实 HTTP 状态码（`resolveHttpStatus`）；其余 handler（NotLoginException→401、NotPermissionException→403、参数校验→400、ConstraintViolation→400、DataIntegrity→422、NoResource→404、Exception→500）全部返回裸 `Result<Void>`，HTTP 状态码恒为 200，业务码放在 body 的 `code` 字段。
- **影响**：①NotLoginException 实际 HTTP 200 + body code=401，前端若用 axios 的 status 拦截器（401 跳登录）会失效，必须读 body.code；②监控/网关按 HTTP 状态码告警时，4xx/5xx 业务错误全部表现为 200，不可观测；③同一 handler 类内两种风格混用，易混淆。
- **根因/分析**：这是"HTTP 语义 vs 业务码"的设计选择，项目倾向后者（前端 `request.ts` 走 body.code 处理）。但 BusinessException 分支又用了真实 HTTP 状态，自相矛盾。已排除误判：前端 `request.ts:72+` 确实靠 response 拦截器读 body（需 F02 确认具体逻辑）。
- **修复方向**：统一为一种风格——要么全部 ResponseEntity（HTTP 状态真实），要么全部裸 Result（HTTP 恒 200 + body code）。改动面 **中**（需同步前端）。
- **关联**：横向主题"跨服务契约一致性"（前端 request.ts 归 F02）。

---

## `[Deps]` 依赖升级与版本

### 本模块依赖清单（基于声明文件，未翻依赖源码）

| 依赖 | 版本 | 声明位置 | 已知风险/可升级 | 备注 |
|---|---|---|---|---|
| sa-token-spring-boot3-starter | 1.44.0 | `backend/pom.xml:60` | 可升至 1.45.x（参考训练知识，`[需查证]`） | 本模块仅用其异常类型 |
| knife4j-openapi3-jakarta-spring-boot-starter | 4.4.0 | `backend/pom.xml:74` | 可升至 4.5.x（`[需查证]`） | prod 已关闭 |
| logstash-logback-encoder | （pom 未直接声明版本，继承自 spring-boot） | `backend/pom.xml:122` | 跟随 Spring Boot 3.3.5 | prod JSON 日志 |
| spring-boot-starter-web | 3.3.5 | `backend/pom.xml`（parent） | 可升至 3.3.x 最新补丁 / 3.4 | Filter/RestTemplate/CORS 基建 |

> 排查范围：仅本模块直接涉及的依赖。未发现阻断性 CVE（基于训练知识，不翻依赖源码）。

### [P4] [Deps] Sa-Token 1.44.0 可考虑跟随小版本升级 <!-- 编号：B16-12 -->
- **定位**：`sa-token.version=1.44.0`（`backend/pom.xml:20`）
- **现象**：1.44.0 发布于 2024 年，后续有 1.45.x（`[需查证]` 具体版本号与 CVE）。
- **影响**：本模块只用其异常类（NotLoginException/NotPermissionException），升级影响面小。
- **根因/分析**：版本升级本身归 B06（鉴权主模块），本模块仅记录交叉。
- **修复方向**：跟随 B06 升级决策。改动面 **小**（本模块视角）。
- **关联**：B06（鉴权主模块）。

---

## `[Design]` 功能设计合理性

> 计划 §2.5 强制维度。即便无 P0–P3 也必写。

**审视结论**：

1. **场景适配（§2.5-1）**：单人博客 + 每工作日 AI 日报场景下，这套基础设施（traceId + IP 限流 + 访问日志 + 统一异常 + Knife4j + CORS）是**合理偏完备**的。traceId 便于排障、限流防爬虫扫站、访问日志按状态分级（5xx warn / 4xx info / 2xx debug）日志量可控、Knife4j dev 开 prod 关符合安全默认。唯一略过度的是自建限流算法（§B16-10），但单实例下可接受。**无需调整**。

2. **可运维性（§2.5-3）**：故障定位能力**中等**。traceId 设计正确（但顺序 bug B16-01 削弱了效果）；访问日志只记 method/path/status/duration 不记 body/params（安全但不利于复现复杂请求）；GlobalExceptionHandler 兜底分支生成 traceId 写入日志和响应分离（响应只给"系统繁忙"，traceId 在日志），需要用户报错时提供 traceId 才能关联——但响应 body 没有回传 traceId，用户无法提供。**建议**：兜底异常的 `Result` 里带上 traceId 字段，形成"用户报 traceId → 运维查日志"闭环。列为 `[Design/P4]`。

3. **闭环完整性（§2.5-2）**：限流命中后返回 429 + 固定 JSON，但**无 Retry-After 响应头**，前端不知道多久后重试；登录接口虽被限流覆盖，但无专门"登录失败次数锁定"机制（依赖通用 60 次/分钟阈值，对密码爆破防护偏弱）。**建议**：429 响应补 `Retry-After` 头；登录接口考虑独立计数。列为 `[Design/P4]`。

### [P4] [Design] 兜底异常响应未回传 traceId，用户报错无法关联日志 <!-- 编号：B16-13 -->
- **定位**：`backend/src/main/java/com/nanmuli/blog/interfaces/handler/GlobalExceptionHandler.java:133-141`
- **现象**：`handleException` 计算了 traceId 并写入日志，但返回的 `Result.error(500, "系统繁忙，请稍后再试")` 不含 traceId。用户看到"系统繁忙"后无法把 traceId 反馈给运维。
- **影响**：单人运维场景下，排障依赖"用户描述 + 日志全量搜索"，效率低。
- **建议方向**：在 `Result` 增加可选 `traceId` 字段，兜底异常时回传（注意不要回传堆栈/message）。或前端全局错误提示里展示 traceId。改动面 **小**（后端）+ **小**（前端）。
- **关联**：次维度 `[Arch]` 可运维性。

### [P4] [Design] 429 限流响应缺少 Retry-After 头，登录爆破防护依赖通用阈值 <!-- 编号：B16-14 -->
- **定位**：`backend/src/main/java/com/nanmuli/blog/interfaces/filter/RateLimitFilter.java:79-83`
- **现象**：429 响应只设置 status + content-type + body，无 `Retry-After` 头；阈值 `rate-limit.max-requests:60` 对 `/api/auth/login` 和普通查询接口一视同仁。
- **影响**：①被限流的客户端不知道退避多久；②登录接口 60 次/分钟仍允许较激进的密码尝试（虽 Sa-Token 单点登录 `is-concurrent:false` 会顶下线，但爆破防御应更严）。
- **建议方向**：429 补 `Retry-After: <windowSeconds>`；登录路径单独配置更严阈值（如 10 次/分钟）。改动面 **小**。
- **关联**：次维度 `[Security]` 纵深防御；B06（登录主模块）。

---

## 模块小结

### 严重度统计

| 级别 | 数量 | 条目编号 |
|---|---|---|
| P0 | 0 | — |
| P1 | 0 | — |
| P2 | 3 | B16-01、B16-04、B16-05 |
| P3 | 7 | B16-02、B16-03、B16-06、B16-07、B16-08、B16-09、B16-10 |
| P4 | 4 | B16-11、B16-12、B16-13、B16-14 |

### Top 风险（本模块最该先看的 ≤3 条）

1. **B16-01 TraceIdFilter 缺 @Order** —— 直接削弱全链路日志关联能力，修复成本极低（加一个注解），性价比最高。
2. **B16-04 dev 环境 CORS 默认 `*`** —— 危险默认值，配合 Cookie 模式有 CSRF 面，应改安全默认。
3. **B16-05 allowCredentials 未配置** —— "看起来 CORS 配了实则 Cookie 跨域不工作"的半成品，分域部署时会阻断鉴权。

### 修复优先级建议

- **立即**（P0/P1）：无。
- **计划**（P2）：
  - B16-01：TraceIdFilter 加 `@Order(Ordered.HIGHEST_PRECEDENCE)`（改动面小，建议最先做）。
  - B16-04：dev profile 补 `cors.allowed-origins`；`resolveOriginPatterns` 空值回退改为安全默认（改动面小）。
  - B16-05：明确同源/分域部署决策，分域则补 `allowCredentials(true)` + 前端 withCredentials（改动面小/中）。
- **择机**（P3/P4）：
  - B16-06：traceId 输入校验（小）。
  - B16-07：admin 路径补宽松限流 + 登录独立阈值（小，关联 B14）。
  - B16-13/14：兜底异常回传 traceId、429 补 Retry-After（小，提升可运维性）。
  - 其余 P3/P4 维持现状即可。

### 排查盲区 / 待复核

- **B16-04/B16-05 的实际触发条件**：需确认生产部署是否同源（nginx 反代 `frontend` + `backend`）。若同源，CORS 与 allowCredentials 问题均不触发，优先级可降。`[需查证]` X01（部署架构）的 nginx 配置。
- **Sa-Token 1.45.x 是否存在及含 CVE**：`[需查证]`，归 B06。
- **RateLimitFilter 的 `init()` 是否被容器正确调用**：`@Component` Filter 由 Spring Boot 包装为 `FilterRegistrationBean` 并注册到 Servlet 容器，`init` 会被调用——但未实际运行验证。`[需查证]`（低风险，若未调用则 `cleaner` 为 null 不会 NPE，只是清理不触发，限流 Map 会增长到 `maxTrackedIps` 后强制清理，功能降级但不崩溃）。
- **前端 axios 是否在某处全局开了 withCredentials**：本次只读了 `request.ts` 前 80 行，`[需查证]` 是否有其他拦截器或实例覆盖。归 F02。
