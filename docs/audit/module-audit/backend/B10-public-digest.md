# B10 日报公开查询 PublicDigest / CrawlerTaskClient 排查报告

> **模块编号**：B10
> **排查范围**：公开日报查询接口透传 + backend→crawler HTTP 客户端主类
> **基线 commit**：`6ae930098405f4d0553d96a852f3345d0f39682e`
> **工作区状态**：脏（10 个已修改 + 2 个新增目录，**均不涉及本模块**：改动集中在 `ConfigRepositoryImpl`、`WebCollectPageMapper`、crawler `search.py`/`knowledge_base.py`、测试、`deploy/README.md`、`release-gate.ps1`、`full-project-risk-register.md`，无 `PublicDigestController`/`CrawlerTaskClient` 改动）
> **排查日期**：2026-06-24
> **排查人**：B10 audit agent
> **状态**：草稿

---

## 模块概览

**职责**：①把无登录的公开日报查询（`/api/digest/**`）透传到 Python crawler；②封装 backend→crawler 的全部 HTTP 调用（任务 CRUD、配置刷新、健康检查、digest 代理），用 HttpClient5 连接池复用 TCP。

**关键文件**：
- `backend/src/main/java/com/nanmuli/blog/interfaces/rest/PublicDigestController.java:24-71` —— 公开日报 Controller，3 个端点全部纯透传
- `backend/src/main/java/com/nanmuli/blog/infrastructure/crawler/CrawlerTaskClient.java:30-278` —— HTTP 客户端主类，连接池 + reload + 全部 crawler 调用
- `backend/src/main/java/com/nanmuli/blog/infrastructure/config/security/SaTokenConfig.java:30-49` —— 拦截器规则（确认 `/api/digest/**` 无鉴权）

**对外接口 / 依赖**：
- 对外（公开，无需登录）：`GET /api/digest`、`GET /api/digest/latest`、`GET /api/digest/{date}`
- 内部消费者（`CrawlerTaskClient` 被多模块共用）：B07 `ConfigController.reloadPool()`/`refreshConfig()`、B08 `WebCollectorAppService`/`WebCollectSourceAppService`/`WebCollectorController`、`SystemConfigInitializer`
- 依赖配置 key：`crawler.service.base-url`、`crawler.service.api-key`、`crawler.service.connect-timeout`、`crawler.service.read-timeout`、`crawler.http.pool.max-total`、`crawler.http.pool.max-per-route`、`crawler.callback.url`、`crawler.callback.api-key`
- 依赖库：Apache HttpClient5（`httpclient5`，版本由 Spring Boot BOM 管理，未显式声明）、Spring `RestTemplate`、Jackson `ObjectMapper`

**已读文件清单**：
- `backend/.../PublicDigestController.java` —— 通读
- `backend/.../CrawlerTaskClient.java` —— 通读（278 行）
- `backend/.../SaTokenConfig.java` —— 通读
- `backend/pom.xml` —— 片段（HttpClient5 依赖段 + java.version）
- `crawler-service/standalone/routes.py:730-829, 1015-1131` —— 片段（`/digests`、`/digests/{date}`、`/digests/latest`、`_build_digest_detail`）
- `backend/.../ConfigService.java` —— 仅 grep（get/getInt 签名）
- `crawler-service/api/*.py` —— 仅 grep（确认无重复 `/api/v1/digests` 路由）

**主模块归属**：**`CrawlerTaskClient` 的主模块是 B10（§8.6），本报告深查该客户端**。B07/B08/B09/B17 调用本客户端时只引用本模块编号。

---

## `[Bug]` 代码正确性与潜在缺陷

> 排查范围：`PublicDigestController` 全文、`CrawlerTaskClient` 全文（initPool/reloadPool/HTTP helpers/各业务方法）。

### [P2] [Bug] `reloadPool()` 非原子：新 client 与新 restTemplate 之间存在"半切换"窗口 <!-- B10-01 -->
- **定位**：`CrawlerTaskClient.java:65-69`
- **现象**：`initPool()` 先把 `this.restTemplate = new RestTemplate(factory)`（L66），再 `this.httpClient = newClient`（L69）。两步之间字段不是一起更新的。`reloadPool()` 虽然是 `synchronized`（L83），但 `get/post/exchange`（L242-262）读取 `restTemplate` 和 `baseUrl/apiKey` 时**没有加 synchronized**，全靠 `volatile`。
- **影响**：并发重载 + 并发请求时，理论上请求可能读到"新 restTemplate + 旧 httpClient 已 close"组合——但实际触发需极小时间窗，且 `httpClient.close()` 在 L70-76 才执行（在 L69 赋新值之后），主线程 close 旧 client 与并发请求线程用旧 restTemplate 持有旧 client 的窗口真实存在，可能导致偶发 `IllegalStateException: Connection pool shut down`。
- **根因/分析**：`volatile` 保证可见性但不保证多字段原子性。已排除"完全用旧值"误判——`restTemplate` 字段在 L66 已是新值，但底层 `httpClient` 被 close（L72）后旧 `RestTemplate` 已不可用。`reloadPool` 在生产由 `ConfigController`（B07）触发，频率低；真实风险中等。
- **修复方向**：①`reloadPool()` 中先生成完整新 client+factory+restTemplate 三元组，最后一次性原子替换（局部变量 → 单次字段赋值）；②或对 get/post 加 `synchronized`（牺牲并发换正确性）。改动面：中
- **关联**：次维度 `[Concurrency]`；被 B07 `ConfigController` 调用（B07-XX 待编号）

### [P2] [Bug] `proxyGet`/`proxyPost` 异常分类丢失：Python 5xx 与连接异常都映射成 503，运维无法区分 <!-- B10-02 -->
- **定位**：`PublicDigestController.java:39-42, 52-55, 66-69`；`CrawlerTaskClient.java:212-215`
- **现象**：Controller 的 `catch (Exception e)` 把所有非 404 异常（含 `HttpServerErrorException`、`ResourceAccessException` 连接超时/拒绝、`RestClientException`）统一记 `log.warn` 并抛 `BusinessException(503, "服务暂时不可用")`。CrawlerTaskClient 自身的 `get()`（L242-248）在 null body 时抛裸 `RuntimeException`。
- **影响**：crawler 宕机（连不上）vs crawler 500（代码 bug）vs 超时 vs null body，前端和日志看到的全是"503 服务暂时不可用"，排查时只能去看 backend log 的 message 文本，无结构化区分；也无法对"crawler 5xx"做自动告警而对"网络抖动"不告警。
- **根因/分析**：Python 侧 4xx 已细分（`HttpClientErrorException.NotFound` 单独 catch），但 5xx 走兜底。已排除"故意合并"误判——代码无注释说明合并意图。
- **修复方向**：在 Controller 或 CrawlerTaskClient 增加 `HttpServerErrorException` / `ResourceAccessException` 分支，分别映射 502（上游错误）/504（网关超时）/503（不可用），日志 level 区分（超时 DEBUG，5xx WARN）。改动面：中
- **关联**：次维度 `[Ops]`；横向主题"跨服务契约一致性"（错误码契约）

### [P3] [Bug] `listDigests` 的 `page`/`size` 被静默重置而非拒绝，无效入参产生 200 <!-- B10-03 -->
- **定位**：`PublicDigestController.java:33-34`
- **现象**：`if (size < 1 || size > 50) size = 10;` `if (page < 1) page = 1;`——越界值被静默改成默认值，不返回 400。
- **影响**：客户端传 `size=9999` 得到的是 10 条，看似成功，掩盖客户端 bug；攻击者也无法用超大 size 拖垮 crawler（crawler `Query(le=50)` 二次兜底，见 `routes.py:742`），故无安全后果。
- **根因/分析**：防御性重置是常见模式，但公开接口对非法入参更应 400 暴露问题。已排除"安全风险"——crawler 侧有 `ge=1, le=50` 校验。
- **修复方向**：用 `@Min/@Max` + `@Validated` 返回 400，或维持现状（已有 `@Validated` 注解在类上）。改动面：小
- **关联**：次维度 `[API]`

---

## `[Security]` 安全漏洞

> 排查范围：PublicDigestController 透传字段、CrawlerTaskClient URL 拼接与 key 注入、SaTokenConfig 路由规则、crawler 返回字段过滤。逐项覆盖 §2.2：Sa-Token 路由/X-API-Key/SSRF（base-url 注入 + date 参数拼接）/限流。

### [P2] [Security] 公开接口无任何限流，crawler 可被外部刷爆 <!-- B10-04 -->
- **定位**：`SaTokenConfig.java:32-34`（`/api/digest/**` 不在 `/api/admin/**` 拦截范围，全公开）+ `PublicDigestController.java:29-70`（无 `@RateLimit` 或 Filter 限流，全项目 grep 无限流组件）
- **现象**：`/api/digest`、`/api/digest/latest`、`/api/digest/{date}` 三端点每次请求都经 `CrawlerTaskClient.proxyGet` → Python `/api/v1/digests`，Python 再查 SQLite。无 IP/用户/接口级限流。
- **影响**：`/api/digest/{date}` 中 `date` 为 7 位数字组合（10 年日报），脚本枚举或刷 latest 端点会把 crawler 连接池（`maxTotal=20`）占满，拖垮 crawler 进而拖垮 backend（因为 B08 采集也共用同一 client 同一连接池）。
- **根因/分析**：CLAUDE.md 声称 crawler 有"限流"能力，但 backend→crawler 这层透明代理未加限流，crawler 侧 `standalone/auth.py` 的限流 [需查证] 是否对 `/digests` 公开路由生效。已排除"crawler 自己限流所以无需"误判——C02 是主模块，本模块只记 backend 侧缺失。
- **修复方向**：①backend 侧给 `/api/digest/**` 加 IP 限流（Bucket4j 或 nginx `limit_req`，`deploy/nginx.conf` 已有 gzip 但未见 limit_req）；②crawler 连接池按调用方隔离（公开 digest 用独立小池，采集用另一池）。改动面：中
- **关联**：横向主题"鉴权机制一致性"；C02（crawler 限流主模块）；次维度 `[Availability]`

### [P2] [Security] Python 返回字段原样转发，可能透传内部诊断字段给公开访客 <!-- B10-05 -->
- **定位**：`CrawlerTaskClient.proxyGet:212-215`（直接 `toMap` 全量返回）+ crawler `routes.py:1112-1130` `_build_digest_detail` 返回字段
- **现象**：`_build_digest_detail` 对**公开**端点（`/digests/{date}`、`/digests/latest`）返回的字段包括：`ai_duration`、`ai_tokens_used`、`orchestrator_plan`、`diagnostics`、`quality_evaluation`（含 `source_diagnostics`、`next_run_actions`、`weaknesses`、`suggestions`）。
- **影响**：这些字段是**内部运营/优化诊断数据**（AI 耗时/token 消耗、优化策略规划、源诊断、弱点建议），不应向无登录访客暴露。访客可借此推断 AI 成本、采集源健康度、优化策略。虽无密钥泄露，但属信息泄露 + 攻击面放大（知道哪些源弱可针对性投毒）。
- **根因/分析**：Python `_build_digest_detail` 对公开和 admin（`/digests/task/{id}`）用同一函数，未按调用方裁剪字段。已排除"admin 专用"误判——`/digests/{date}` 是公开路由且走同一 detail 构建。
- **修复方向**：①Python 侧按 `include_all`/调用方拆分公开字段集与 admin 字段集；②或在 `PublicDigestController` 用 DTO 白名单裁剪（推荐前者，单一数据源）。改动面：中（改 crawler `routes.py`）
- **关联**：横向主题"跨服务契约一致性"；C04/C07（诊断字段来源）

### [P3] [Security] `crawler.service.base-url` 可被注入 SSRF，但攻击面仅限管理员 <!-- B10-05b -->
- **定位**：`CrawlerTaskClient.java:46`（`baseUrl = configService.get("crawler.service.base-url", ...)`）+ `get():243`（`baseUrl + path`）
- **现象**：`base-url` 通过 sys_config 表可被管理员（B07 `ConfigController`）运行时修改为任意值（如 `http://169.254.169.254`），`reloadPool` 后所有 crawler 调用（含公开 digest 代理）都打到该地址。
- **影响**：理论上可构成 SSRF（让 backend 对内网/元数据服务发请求）。但触发需 admin 权限改 sys_config，而 admin 本身就受 SaToken 保护——属"已授权用户的权限内行为"，不构成可被外部利用的 SSRF。
- **根因/分析**：真正的 SSRF 风险在 `PublicDigestController.getDigestByDate` 的 `date` 参数——但 `@Pattern(regexp="^\\d{4}-\\d{2}-\\d{2}$")`（L61）已严格限制，无法注入路径/查询参数，**该路径安全**。已排除"date 参数 SSRF"误判。`base-url` 注入需 admin 权限，定 P3。
- **修复方向**：①对 `base-url` 配置项加 schema 校验（拒绝内网/回环/元数据地址，复用 crawler `ssrf_guard` 思路）；②或加注释说明"此值需运维审核"。改动面：小
- **关联**：次维度 `[SSRF]`；B07（配置主模块）；crawler `ssrf_guard`（C01，已声明不防 DNS rebinding）

### [P3] [Security] `X-API-Key` 用 `String.equals` 比较，非常量时间 <!-- B10-06 -->
- **定位**：`CrawlerTaskClient.authHeaders():267-269`（这是**发送**方，无比较）—— 实际比较在 crawler 侧 `standalone/auth.py`，backend 本模块**不参与 key 比较**。
- **现象**：backend 作为 crawler 的客户端，只负责在 `authHeaders()` 注入 `X-API-Key`。key 比较（恒定时间与否）是 crawler 侧 C02 的职责。
- **影响**：无（backend 不比较）。
- **根因/分析**：列出以明确边界——backend 侧无可改进点，timing attack 归 C02。`SaTokenConfig.hasValidCallbackKey():55` 用 `expectedKey.equals(requestKey)` 比较 `X-Callback-Key`（crawler→backend 方向），那个非常量时间，但归 B09/B16 边界，本模块不展开。
- **修复方向**：无需调整（backend 发送方）。改动面：无
- **关联**：B09（回调 key 主模块）、C02（crawler key 比较主模块）

---

## `[Arch]` 架构与技术债

> 排查范围：分层、抽象、硬编码、可测试性。

### [P3] [Arch] `PublicDigestController` 直接 `new BusinessException` 写业务错误码，绕过 AppService 层 <!-- B10-07 -->
- **定位**：`PublicDigestController.java:38, 41, 51, 54, 65, 68`
- **现象**：Controller 内含 try/catch + 错误映射 + size/page 校验逻辑（CLAUDE.md 规定"Controller 不写业务逻辑"）。无 `PublicDigestAppService` 中间层。
- **影响**：与项目 DDD 分层约定不符；但逻辑极简（纯透传 + 错误码翻译），引入 AppService 反而增加样板。属可接受的偏离。
- **根因/分析**：B16 `WebCollectorController` 同样有透传逻辑，是项目既有模式。已排除"必须分层"误判——透传接口分层收益低。
- **修复方向**：维持现状（`无需调整`），或为一致性抽 `DigestProxyAppService`。改动面：小
- **关联**：B16（Controller 透传模式）；次维度 `[DDD]`

### [P4] [Arch] `RestTemplate` 已被 Spring 标记为 maintenance，新代码推荐 `RestClient`/`WebClient` <!-- B10-08 -->
- **定位**：`CrawlerTaskClient.java:10, 34, 66`
- **现象**：用 `RestTemplate`（Spring Framework 6 起 maintenance mode，不再增强）。
- **影响**：当前可用，无功能缺陷；长期看技术债，但 Spring Boot 3.3.5 生命周期内无强制迁移压力。
- **根因/分析**：非 bug，记录为未来升级方向。
- **修复方向**：下次大版本升级（Spring Boot 3.4+）时评估迁移到 `RestClient`（同步、API 更简洁）。改动面：中
- **关联**：B-Deps（Spring Boot 版本）

### [P4] [Arch] 连接池配置项（max-total/max-per-route/timeout）散在 sys_config，无 yml 兜底 <!-- B10-09 -->
- **定位**：`CrawlerTaskClient.java:48-51`（全走 `configService.getInt`）+ `application-dev.yml:53-55`（仅注释说明，无实际 yml key）
- **现象**：连接池大小、超时**完全依赖 sys_config 表**，yml/env 无同名 key 兜底。若 sys_config 未初始化（如新部署漏跑 `SystemConfigInitializer`），走代码内联默认值（maxTotal=20, connect=10s, read=30s）。
- **影响**：默认值合理，不会崩；但配置可见性差——运维在 yml 里搜不到这些 key，需知道它们在 sys_config 表。
- **根因/分析**：与 X06"配置三轨"主题一致，本模块只记视角。已排除"无默认值会崩"误判——`getInt` 有 defaultValue 参数。
- **修复方向**：在 `application.yml` 加注释块列出这些 sys_config key 的默认值与含义（文档化），不改运行时行为。改动面：小
- **关联**：X06（配置一致性主模块）

---

## `[Deps]` 依赖升级与版本

### 本模块依赖清单（基于声明文件，未翻依赖源码）

| 依赖 | 版本 | 声明位置 | 已知风险/可升级 | 备注 |
|---|---|---|---|---|
| Apache HttpClient5 | 未显式声明（由 Spring Boot 3.3.5 BOM 管理） | `backend/pom.xml:115-119` | 无已知 CVE（5.x 当前稳定）；可显式锁版本增强可复现性 | 版本号 [需查证]：未进 `~/.m2` 查 BOM 实际解析值 |
| Spring `RestTemplate` | Spring Boot 3.3.5（spring-web 6.1.x） | 传递依赖 | maintenance mode（见 B10-08） | — |
| Jackson `ObjectMapper` | Spring Boot 3.3.5 BOM | 传递依赖 | 无已知 CVE | 用于 `toMap`（L274-277） |
| Spring Web (`HttpEntity`/`ResponseEntity`) | Spring Boot 3.3.5 | 传递依赖 | — | — |

> 排查范围：仅 `pom.xml` 声明 + 传递依赖的 Spring Boot 版本，未翻 BOM/`~/.m2`。未发现版本相关 P0-P3 问题。

### [P4] [Deps] HttpClient5 版本未显式锁定，依赖 BOM 传递 <!-- B10-10 -->
- **定位**：`pom.xml:115-119`（无 `<version>` 标签）
- **现象**：`httpclient5` 仅声明 groupId/artifactId，版本由 Spring Boot 3.3.5 的 `dependencyManagement` 决定。
- **影响**：Spring Boot 升级时 HttpClient5 跟随升级，无显式控制；`PoolingHttpClientConnectionManager` API 在 5.x 内稳定，风险低。
- **根因/分析**：符合 Spring Boot 最佳实践（让 BOM 管），非问题。HttpClient5 实际版本 [需查证]（未查 BOM 解析结果）。
- **修复方向**：维持现状（`无需调整`）。改动面：无
- **关联**：—

---

## `[Design]` 功能设计合理性

> 必填。回答 §2.5 中相关问题（至少 2 个）。

**审视结论**：

1. **场景适配（§2.5-1）**：单人维护技术博客 + 每工作日 AI 日报场景下，公开日报查询用"backend 透传 crawler"而非"crawler 结果落 PG 后由 backend 直接查"，是**过度间接**——每次公开访问都打 crawler（SQLite），而非利用 backend 的 PostgreSQL。但考虑 crawler 是独立服务、日报数据在 crawler 侧 SQLite，落 PG 需额外同步链路，MVP 阶段透传可接受。**结论：场景适配合理，无需调整，但长期看日报公开查询应落 PG。**

2. **闭环完整性（§2.5-2）**：公开查询端点只读，无人工干预入口需求（公开访客不需要编辑/剔除日报）；闭环缺口在"日报质量数据不进闭环"（C04/C07 已知问题），不在本模块。**结论：本模块闭环完整。**

3. **可运维性（§2.5-3）**：crawler 不可用时公开端点返回 503，但**无降级**——访客看到"服务暂时不可用"而非最近一次缓存的日报。backend 有 Redis 却未缓存最近一期日报供降级展示。运维定位困难（见 B10-02 错误码合并）。**结论：可运维性有缺口，建议加 Redis 降级缓存。**

### [P4] [Design] 公开日报查询无降级缓存，crawler 宕机即全站日报不可用 <!-- B10-11 -->
- **定位**：`PublicDigestController.getLatestDigest:47-56`（直接 proxyGet，无 Redis 回源）
- **现象**：crawler 宕机时 `/api/digest/latest` 返回 503，访客看不到任何日报。
- **影响**：日报是博客公开内容的核心吸引点之一，crawler 单点故障导致公开内容消失，体验断层。
- **建议方向**：用 Redis 缓存最近 N 期日报（TTL 1-2 小时），crawler 不可用时返回缓存 + 标记"数据可能非最新"。改动面：中
- **关联**：§2.5-3 可运维性；X01（部署单点）

### [P4] [Design] 透传响应体无大小上限校验 <!-- B10-12 -->
- **定位**：`CrawlerTaskClient.proxyGet:212-215`（`toMap` 全量）+ `PublicDigestController` 原样 `Result.success`
- **现象**：`_build_digest_detail` 返回含 `ai_full_content`（完整日报正文）+ sections/items + quality_evaluation，单期日报 JSON 可能达数百 KB。公开端点无分页（详情接口）无大小限制。
- **影响**：当前日报体量可控；若未来日报变长或 AI 输出暴增，单次响应过大拖慢传输（nginx `gzip` 已开，`deploy/nginx.conf:8-11` 缓解）。
- **建议方向**：维持现状（已有 gzip）；或对 `ai_full_content` 单独按需懒加载。改动面：小
- **关联**：§2.5-3 可运维性

---

## 模块小结

### 严重度统计

| 级别 | 数量 | 条目编号 |
|---|---|---|
| P0 | 0 | — |
| P1 | 0 | — |
| P2 | 3 | B10-01, B10-02, B10-04, B10-05 |
| P3 | 4 | B10-03, B10-05b, B10-06, B10-07, B10-09 |
| P4 | 4 | B10-08, B10-10, B10-11, B10-12 |

> 注：B10-05 含 Python 字段透传（P2），B10-05b 是 base-url SSRF 子条目（P3）；B10-06 无需调整（边界说明）。

### Top 风险（本模块最该先看的 ≤3 条）

1. **B10-05 字段透传泄露内部诊断** —— 公开访客可拿到 `ai_tokens_used`/`orchestrator_plan`/`source_diagnostics`/`weaknesses`，属信息泄露，需 Python 侧按调用方裁剪字段。
2. **B10-04 公开接口无限流** —— 无登录 + 无限流 + 共用 crawler 连接池，外部刷量可拖垮 crawler 进而影响采集（B08）。
3. **B10-01 reloadPool 非原子** —— 配置重载（B07 触发）与并发请求竞争，偶发连接池已关闭异常，难复现。

### 修复优先级建议

- **立即**（P0/P1）：无
- **计划**（P2）：B10-05（字段裁剪，改 crawler `routes.py`）、B10-04（公开端点限流）、B10-01（reloadPool 原子化）、B10-02（错误码细分）
- **择机**（P3/P4）：B10-03（入参 400）、B10-05b（base-url 校验）、B10-07/B10-08/B10-09/B10-10/B10-11/B10-12（技术债/设计建议）

### 排查盲区 / 待复核

- **B10-10** HttpClient5 实际解析版本未查（未进 `~/.m2`，标 `[需查证]`）——低优。
- **crawler 侧 `/digests` 路由的限流**（`standalone/auth.py`）是否对公开 GET 生效未逐行核对，归 C02 主模块——影响 B10-04 严重度判定（若 crawler 已限流，B10-04 可降为 P3）。
- **`PoolingHttpClientConnectionManager` 默认连接保活/空闲超时**未查 HttpClient5 默认值——影响连接泄漏风险评估，标 `[需查证]`。
