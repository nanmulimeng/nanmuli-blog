# B11 代理管理 Proxy 排查报告

> **模块编号**：B11
> **排查范围**：Mihomo/Clash 代理控制（节点切换、延迟测试、订阅刷新）+ ProxyAppService + MihomoProxyClient + ProxyController（`/api/admin/proxy/**`）+ deploy/mihomo 部署配置
> **基线 commit**：`6ae930098405f4d0553d96a852f3345d0f39682e`
> **工作区状态**：脏（未提交改动涉及 ConfigRepositoryImpl/WebCollectPageMapper/crawler 多个/deploy README/risk-register/release-gate；**本 B11 模块相关文件均未在工作区改动中**，故排查基于 HEAD 代码）
> **排查日期**：2026-06-23
> **排查人**：B11 模块排查 agent
> **状态**：草稿

---

## 模块概览

**职责**：通过 Mihomo（Clash Meta）external-controller REST API，让管理员在后台查看代理组/节点、切换节点、测速、维护订阅 URL，供 crawler-service 走代理抓取被墙页面。

**关键文件**：
- `backend/src/main/java/com/nanmuli/blog/application/proxy/ProxyAppService.java:23-170` —— 应用服务：状态聚合、组查询、节点切换、测速、订阅 CRUD
- `backend/src/main/java/com/nanmuli/blog/infrastructure/proxy/MihomoProxyClient.java:24-235` —— Mihomo HTTP API 客户端（GET 用 RestTemplate，PUT 用裸 HttpURLConnection）
- `backend/src/main/java/com/nanmuli/blog/interfaces/rest/ProxyController.java:24-88` —— `/api/admin/proxy/**` REST 入口 + 局部 `@ExceptionHandler`
- `backend/src/main/java/com/nanmuli/blog/infrastructure/proxy/MihomoUnreachableException.java` —— 业务异常（code=503）
- `deploy/mihomo/config.template.yaml:1-98` —— Mihomo 部署配置模板
- `deploy/mihomo/install.sh:1-206` —— 一键安装脚本
- `frontend/src/views/admin/proxy/Index.vue:1-297` —— 前端代理管理页

**对外接口 / 依赖**：
- 对外：`GET /api/admin/proxy/status`、`GET /groups`、`PUT /groups/{name}`、`POST /nodes/delay-test`、`GET /subscription`、`PUT /subscription`、`POST /subscription/refresh`
- 依赖：Mihomo external-controller（`http://127.0.0.1:9090`，`mihomo.api.url`/`mihomo.api.secret` 注入）；ConfigAppService（读 `crawler.proxy.enabled`/`crawler.proxy.url`/`crawler.proxy.subscription_url`）；ConfigService.reload；依赖 B06 Sa-Token 拦截 `/api/admin/**` 鉴权（引用）；依赖 B07 sys_config 表存储（引用 B15）

**已读文件清单**：
- `application/proxy/ProxyAppService.java` —— 通读
- `infrastructure/proxy/MihomoProxyClient.java` —— 通读（重点）
- `infrastructure/proxy/MihomoUnreachableException.java` —— 通读
- `interfaces/rest/ProxyController.java` —— 通读
- `application/proxy/command/*`（3 个 record）—— 通读
- `application/proxy/dto/*`（4 个 record）—— 通读
- `infrastructure/config/ConfigService.java` —— 通读（reload 行为）
- `infrastructure/config/security/SaTokenConfig.java` —— 通读（鉴权边界）
- `deploy/mihomo/config.template.yaml` —— 通读
- `deploy/mihomo/install.sh` —— 通读
- `frontend/src/views/admin/proxy/Index.vue` —— 通读
- 仅 grep：`application-dev.yml`（mihomo 段）、`db/init.sql` + `schema.sql`（proxy 配置项）、`ConfigAppService.java`（getByKey 行为）、backend 测试目录（零覆盖确认）

**主模块归属**：本模块是 Mihomo 调用链的主模块，深查。对 Sa-Token 鉴权（B06）、sys_config 存储（B07/B15）只引用不展开。

---

## `[Bug]` 代码正确性与潜在缺陷

> 排查范围：ProxyAppService、MihomoProxyClient、ProxyController 全量 + DTO/Command。逐条覆盖 §2.1（逻辑/边界/NPE/并发/异常/资源/事务）。

### [P1] [Bug] 订阅刷新/更新硬编码 provider 名 "default"，与部署模板的 "sub" 不一致，刷新必失败  <!-- 编号：B11-01 -->
- **定位**：`ProxyAppService.java:157`（`mihomoProxyClient.updateProviderUrl("default", targetUrl)`）、`ProxyAppService.java:165`（`refreshProviderSafe("default")`）；对照 `deploy/mihomo/config.template.yaml:58-60`（`proxy-providers: sub:`）
- **现象**：部署模板 `config.template.yaml` 定义的 proxy-provider 名是 `sub`（第 59 行 `- sub:` 的实际写法是 `sub:` 作为 key），但应用层两处调用都传 `"default"`。Mihomo API 路径 `PUT /providers/proxy/default` 会因 provider 不存在返回 404。
- **影响**：管理员在前端点「更新订阅」/保存订阅 URL 时，后端刷新的是不存在的 `default` provider。`refreshProviderSafe` 内部 catch 后返回 false（`MihomoProxyClient.java:167-170`），`refreshSubscription` 再抛 `MihomoUnreachableException`（`ProxyAppService.java:167`），前端显示「订阅刷新失败，Mihomo 服务不可达」——错误归因到「Mihomo 不可达」而真实原因是 provider 名错。订阅 URL 保存到 DB 成功但 Mihomo 端永远刷不到新节点。
- **根因/分析**：provider 名是部署约定，代码与配置模板未对齐。已排除"Mihomo 自动创建 default provider"——Mihomo 只按 config.yaml 中实际声明的 provider 名暴露 API。
- **修复方向**：①统一改用 `"sub"`（小，与模板对齐）；或②provider 名抽成配置项 `mihomo.provider.name`（默认 `sub`），代码读取（中，更灵活）；或③模板改用 `default`（小，但需同步 install.sh 静态节点分支）。建议①+补单测验证 provider 名常量。
- **关联**：[[Design]] 横向主题「跨服务契约一致性」（前端/后端/部署模板三方约定）；配置项 `mihomo.provider.name`（待引入）

### [P2] [Bug] MihomoProxyClient PUT 用裸 HttpURLConnection，GET 用 RestTemplate，两套实现不一致  <!-- 编号：B11-02 -->
- **定位**：`MihomoProxyClient.java:194-223`（`put` 方法裸 `HttpURLConnection`）vs `MihomoProxyClient.java:175-192`（`get` 方法用注入的 `restTemplate`）
- **现象**：同一类内 GET 走 `restTemplate.exchange`（复用构造时配好超时的 RestTemplate），PUT 却绕开 RestTemplate 手搓 `java.net.HttpURLConnection`，重复设置 connectTimeout/readTimeout/Authorization 头，且 `conn.disconnect()` 后连接不复用。
- **影响**：①维护负担——超时/鉴权逻辑两处各写一遍，改一处易漏另一处；②PUT 的异常分类比 GET 粗：GET 有 `isConnectRefused` 单独识别连接拒绝（`MihomoProxyClient.java:225-234`），PUT 只 `catch (ConnectException)` 单独处理其余一律 `MihomoUnreachableException`（`MihomoProxyClient.java:217-222`），嵌套异常里的 ConnectException 不会被识别；③`java.net.URI.create(baseUrl + path).toURL()` 对含特殊字符的 path（如 groupName 带空格/emoji）会抛 `URISyntaxException`，被笼统包成 MihomoUnreachableException。
- **根因/分析**：疑似早期 PUT 遇到 RestTemplate 的某个限制（如想设 `Connection: close`）后绕开。RestTemplate 完全支持 PUT + 自定义头，无技术必要手搓。
- **修复方向**：PUT 改用 `restTemplate.exchange(..., HttpMethod.PUT, ...)` 与 GET 统一（中）；超时/鉴权抽私有方法 `buildHeaders()`（小）。补单测覆盖 4xx/连接拒绝/超时分支。
- **关联**：[[Bug]] B11-03（URL 编码同源）

### [P2] [Bug] testDelay / selectProxy 的 path 拼接未做 URL 编码，节点名含特殊字符会请求失败  <!-- 编号：B11-03 -->
- **定位**：`MihomoProxyClient.java:100`（`String path = String.format("/proxies/%s/delay?url=%s&timeout=%d", groupName, url, timeout);`）、`MihomoProxyClient.java:84`（`put("/proxies/" + groupName, body);`）、`ProxyAppService.java:117-118` 透传 `groupName`/`nodeName`
- **现象**：Mihomo 节点名常见为 emoji + 中文（如 `🇭🇰 香港 01`、`🇯🇵 日本 - IPLC`），直接拼进 URL path/query 不编码。`url` 测试地址含 `&`/`?` 也会破坏 query 解析（当前默认 `https://www.gstatic.com/generate_204` 无问题，但 `testDelay` 的 `testUrl` 参数外部可传）。
- **影响**：①GET 路径含中文/emoji 时，RestTemplate 内部 URI 解析在某些 JVM/版本下会出错或 Mihomo 返回 404，导致测速/查询失败，前端误判为「Mihomo 不可达」；②PUT 路径同问题，且 `URI.create`（B11-02）对未编码字符直接抛异常；③`url` 参数若含 `&` 会注入额外 query 参数。
- **根因/分析**：未使用 `UriComponentsBuilder` 或 `URLEncoder.encode`。已排除"Mihomo 自动解码"——HTTP path 规范要求百分号编码。
- **修复方向**：用 `RestTemplate` 的 `UriComponentsBuilder.fromHttpUrl(...).pathSegment(groupName).build().toUri()` 构造（小）；`testUrl` 用 `URLEncoder.encode(..., UTF_8)`（小）。改动面 小。
- **关联**：[[Bug]] B11-02；横向主题「跨服务契约」（前端节点名显示与后端编码一致）

### [P3] [Bug] getStatus 中 subscription_url 的 null 判断冗余且与 url/enabled 不一致  <!-- 编号：B11-04 -->
- **定位**：`ProxyAppService.java:33-38`（`subDTO != null ? subDTO.getConfigValue() : ""` vs 第 32/33 行 `enabledDTO`/`urlDTO` 直接 `.getConfigValue()`）
- **现象**：`configAppService.getByKey` 对缺失 key 抛 `BusinessException`（`ConfigAppService.java:55-59`），故三个 DTO 在 key 存在时永不为 null。db 三个 key 均存在（`schema.sql:1027-1029`/`init.sql:1073-1075`），故 `subDTO != null` 恒 true，是死防御。
- **影响**：非功能 bug，仅为一致性/可读性问题。若未来某 key 从 db 移除，三个判断行为不一致——enabled/url 会抛 BusinessException（500），sub 返回空串，行为割裂。
- **根因/分析**：防御式编程风格不统一。
- **修复方向**：统一三处为 `Optional.ofNullable(configAppService.getByKey(...))` 或都直接取值（小）。或保持现状但加注释说明 key 由 SystemConfigInitializer 保证存在。
- **关联**：无

### [P3] [Bug] getGroups 的单节点延迟提取逻辑与 Mihomo 数据结构疑似不匹配  <!-- 编号：B11-05 -->
- **定位**：`ProxyAppService.java:91-106`（遍历 group 的 `history` 列表，按 `hm.get("now")` 匹配节点名取 `delay`）
- **现象**：代码假设 group 的 `history` 是「每个节点一条记录，含 `now` 和 `delay` 字段」。但据 Mihomo API 语义 [需查证]，group 的 `history` 通常是该 group 整体的延迟测试记录（`time`/`delay`），不含 per-node 的 `now` 字段；per-node 延迟在各 proxy 节点对象自己的 `history` 字段里。
- **影响**：`getGroups` 返回的 `ProxyNodeDTO.delay` 极可能**永远为 null**（匹配不上），前端「测试全部延迟」依赖单独的 `testDelay` 接口（`ProxyAppService.java:123-140`）重新测，初次加载列表无任何延迟数据展示。
- **根因/分析**：数据结构假设错误。需对照 Mihomo 实际返回验证 [需查证]。
- **修复方向**：①若确证错误，改为遍历节点对象的 history（中）；或②承认该字段恒空，从 DTO 移除 `delay`，统一用 testDelay 接口（小，需同步前端 `ProxyNodeDTO`/`types/config.ts`）。
- **关联**：[需查证]；横向主题「跨服务契约」（DTO 字段语义）

---

## `[Security]` 安全漏洞

> 排查范围：MihomoProxyClient（SSRF/secret/超时）、ProxyController（鉴权）、updateSubscription（SSRF）。逐项覆盖 §2.2。

### [P1] [Security] 订阅 URL 更新无 SSRF/协议校验，可把 Mihomo 引导向内网/任意地址发请求  <!-- 编号：B11-06 -->
- **定位**：`ProxyController.java:70-72`（`PUT /subscription`）、`ProxyAppService.java:149-162`（`updateSubscription`）、`MihomoProxyClient.java:144-150`（`updateProviderUrl` → `PUT /configs`）
- **现象**：`updateSubscription(url)` 接收任意 URL，仅存 DB 后透传给 Mihomo 的 `proxy-providers.default.url`。无协议白名单（http/https）、无内网/回环/保留地址过滤、无域名黑名单。Mihomo 会周期性（`interval: 3600`）向该 URL 拉取订阅。
- **影响**：admin（或任何能调用该接口的人，见 B11-08 鉴权弱点）可设置 `http://169.254.169.254/latest/meta-data/`（云元数据）、`http://127.0.0.1:xxxx/internal-endpoint`、`file:///etc/passwd` [需查证 Mihomo 是否支持 file 协议] 等地址，让 Mihomo 充当 SSRF 跳板探测内网。订阅响应会被 Mihomo 解析为节点配置，攻击者可据此做内网端口扫描/服务指纹。
- **根因/分析**：与 crawler 的 `ssrf_guard`（C01）形成对比——crawler 显式声明了 SSRF 防护（虽不防 DNS rebinding），但代理订阅这条链路完全裸奔。已排除"admin 都是可信的"——admin 账号若被钓鱼/弱口令（见 §9 默认 `admin123`）即失守。
- **修复方向**：①`updateSubscription` 增加协议白名单（仅 https，订阅源通常支持 https）+ 域名解析后过滤回环/私网/保留段（中，参考 crawler ssrf_guard）；②限制 URL 长度 + 域名级速率（小）；③订阅 URL 标记为敏感配置（见 B11-07）。
- **关联**：[[Security]] §9 默认弱口令（B06/X02）；C01 ssrf_guard（引用）；横向主题「SSRF」

### [P2] [Security] 订阅 URL 含流量盗用 token 却按非敏感明文存储  <!-- 编号：B11-07 -->
- **定位**：`deploy/db/init-scripts/schema.sql:1028` 与 `backend/src/main/resources/db/init.sql:1074`（`('crawler.proxy.subscription_url', '', '', '代理订阅地址', 'crawler', FALSE, 'text', FALSE, FALSE)`——`is_encrypted=FALSE, is_sensitive=FALSE`）；`ProxyStatusDTO.java:12`（`subscriptionUrl` 明文返回前端）、`ProxyAppService.java:144-147`（`getSubscriptionUrl` 明文返回）
- **现象**：机场订阅 URL 通常含个人 token（`https://sub.xxx.com/link/ABCDEFG123==`），泄漏后他人可盗用你的流量配额。但 db 中标记为非敏感、非加密，`getSubscriptionUrl`/`getStatus` 直接明文返回给前端（`GET /subscription`、`GET /status` 都含明文订阅 URL）。
- **影响**：①DB 被拖库或备份泄漏 → 订阅 token 泄漏 → 流量被盗用；②浏览器 DevTools/网络日志/前端缓存可见明文订阅 URL；③与项目其他敏感配置（AI key 等已加密）处理标准不一致。
- **根因/分析**：订阅 URL 的敏感性被低估。对比 `AesEncryptor`（B07）已用于 AI key，机制现成。
- **修复方向**：①将该配置项 `is_encrypted=TRUE, is_sensitive=TRUE`（中，需 schema migration + 数据迁移现有值）；②`getSubscriptionUrl` 返回脱敏值（如 `https://sub.xxx.com/link/***`），更新时走 `getByKeyForAdmin` 全量返回（小，复用 B07 的 MASK_SENTINEL 机制，见 `ConfigAppService.java:62-66/74-76`）；③审计日志不记录订阅 URL 明文。
- **关联**：B07 AES 加密/AesEncryptor（引用）；X06 配置一致性（引用）

### [P2] [Security] Mihomo external-controller 无 secret，仅靠 127.0.0.1 绑定保护  <!-- 编号：B11-08 -->
- **定位**：`deploy/mihomo/config.template.yaml:22`（`external-controller: 127.0.0.1:9090`，无 `secret:` 字段）；`backend/src/main/resources/application-dev.yml:62-64`（只有 `mihomo.api.url`，无 `mihomo.api.secret`）；`MihomoProxyClient.java:36/178/206`（secret 为空时不发 Authorization 头）
- **现象**：Mihomo 控制端口未设 secret。`install.sh` 生成的 config.yaml 同样无 secret（模板没有）。本地绑定 127.0.0.1 是唯一防线。
- **影响**：①若服务器存在 SSRF（如 B11-06 的订阅链路、crawler 的抓取链路），攻击者可通过 SSRF 访问 `http://127.0.0.1:9090/proxies/...` 任意切换节点/改配置，无需任何凭证；②同机其他服务（crawler、nginx）若被攻破可直接控制 Mihomo；③`Mixed/SSRF` 链路：crawler 本身就可能被诱导访问 127.0.0.1:9090。
- **根因/分析**：127.0.0.1 绑定不是安全边界（SSRF/同机进程都能绕）。Mihomo 官方推荐 external-controller 配 secret。
- **修复方向**：①config.template.yaml 加 `secret: {{MIHOMO_SECRET}}` 占位，install.sh 生成随机 secret（中）；②application-dev.yml 加 `mihomo.api.secret`，生产从环境变量注入（小）；③secret 本身作为敏感配置存 sys_config 或仅环境变量（避免循环依赖）。
- **关联**：[[Security]] B11-06（SSRF 放大本问题）；X01 部署架构（引用）

### [P3] [Security] ProxyController 局部 @ExceptionHandler 覆盖全局处理，错误码语义可能被覆盖  <!-- 编号：B11-09 -->
- **定位**：`ProxyController.java:84-87`（`@ExceptionHandler(MihomoUnreachableException.class)` 返回 `Result.error(e.getCode(), e.getMessage())`）
- **现象**：Controller 内声明局部异常处理器。`MihomoUnreachableException` code=503（`MihomoUnreachableException.java:11`），但 `Result.error` 的 code 字段语义是业务码，把 HTTP 503 当业务码返回（HTTP 层仍是 200）。
- **影响**：前端拿到 `{code:503,...}` 但 HTTP 200，监控/网关按 2xx 计数，告警漏报。语义上「服务不可达」是服务端错误（5xx）却按业务错误返回。
- **根因/分析**：业务码与 HTTP 状态码混用。需对照 GlobalExceptionHandler（B16）确认是否有同类处理被局部覆盖 [需查证]。
- **修复方向**：①统一由 GlobalExceptionHandler 处理 MihomoUnreachableException，删局部 handler（小）；或②局部 handler 明确返回 `ResponseEntity.status(503)`（小）。改动面 小。
- **关联**：B16 全局异常处理（引用）；[需查证]

---

## `[Arch]` 架构与技术债

> 排查范围：分层、耦合、DDD 边界、可测试性、配置管理。非主模块只引用。

### [P2] [Arch] ProxyAppService 零测试覆盖，Mihomo 调用链无任何单测/集成测试  <!-- 编号：B11-10 -->
- **定位**：`backend/src/test/` 全目录 grep `ProxyAppService|MihomoProxyClient|ProxyController` 零命中
- **现象**：整个代理模块（AppService + Client + Controller）无任何测试文件、无任何被引用。对比项目其他模块（ConfigAppServiceTest 等存在），本模块是测试盲区。
- **影响**：B11-01（provider 名错误）、B11-03（URL 编码）、B11-05（延迟结构假设）这类 bug 无法被测试捕获；Mihomo API 契约（路径、返回结构）变更无人发现；重构无安全网。
- **根因/分析**：可能因依赖外部 Mihomo 服务难 mock 而跳过。但 MihomoProxyClient 是普通 HTTP 客户端，可用 MockRestServiceServer/MockWebServer 测试。
- **修复方向**：①为 MihomoProxyClient 写 MockRestServiceServer 单测，覆盖 GET/PUT/连接拒绝/超时/4xx（中）；②为 ProxyAppService 写 Mockito 单测，覆盖 getStatus 各分支 + updateSubscription（中）；③provider 名抽常量后加断言（小）。
- **关联**：X03 测试体系（引用，后端测试失衡的极端案例）

### [P3] [Arch] 代理管理嵌入博客后端，与 crawler 主线耦合点分散  <!-- 编号：B11-11 -->
- **定位**：`ProxyAppService.java` 依赖 `ConfigAppService`（博客配置体系）、读 `crawler.proxy.*` 配置；crawler-service 通过 `PROXY_URL` env（见 `install.sh:186` 注释）使用代理，但与后端代理管理无直接调用关系
- **现象**：代理管理是 crawler 的辅助能力，却实现在博客后端（Spring Boot），通过共享 sys_config 的 `crawler.proxy.*` 间接联动。后端改订阅 → 写 DB → ConfigService.reload → crawler 下次读配置生效。链路：admin UI → backend → DB → crawler（读 PROXY_URL/订阅）；同时 admin UI → backend → Mihomo API（刷新订阅/切节点）。
- **影响**：①两条更新路径（DB 配置同步 vs Mihomo API 直控）职责混在一个模块；②crawler 作为代理的实际消费者，却无法感知订阅刷新结果（无回调）；③博客后端承担了与博客业务无关的代理运维职责，违背 CLAUDE.md「crawler 独立服务原则」边界。
- **根因/分析**：设计取舍——借博客 admin UI 做可视化运维，避免再开 crawler admin 端口。但代价是职责越界。
- **修复方向**：①维持现状但明确文档边界（小）；或②长期看，把代理管理迁到 crawler-service 自身（它才是代理消费者），博客后端只透传配置（大，需 crawler 开 admin API）；③至少把 Mihomo client 调用与 DB 配置管理拆成两个 Service（中）。
- **关联**：[[Design]] B11-14；CLAUDE.md「crawler 独立服务原则」

### [P3] [Arch] updateSubscription 在 readOnly=false 的方法里先 update 再 reload 再调 Mihomo，事务/副作用混合  <!-- 编号：B11-12 -->
- **定位**：`ProxyAppService.java:22`（类级 `@Transactional(readOnly = true)`）、`ProxyAppService.java:149`（方法级 `@Transactional` 覆盖为读写）、`ProxyAppService.java:150-161`
- **现象**：`updateSubscription` 在同一事务里：①`configAppService.update`（写 DB，本身 @Transactional + @CacheEvict）、②`configService.reload`（全量重载缓存，非事务操作）、③`mihomoProxyClient.updateProviderUrl`（外部 HTTP 调用）。外部调用在事务内执行，占用 DB 连接期间等待 HTTP。
- **影响**：①Mihomo 调用慢（10s 超时）会长时间持有 DB 连接，连接池耗尽风险；②若 HTTP 调用抛异常，事务回滚——但 DB 其实已写成功（update 是独立事务且已 @CacheEvict），reload 也已执行，回滚语义混乱；③`@Transactional` 标注在已 readOnly=true 的类上，AOP 代理行为需确认 [需查证]。
- **根因/分析**：事务边界未隔离外部调用。正确做法是 DB 写完提交事务，再做外部调用。
- **修复方向**：①把 Mihomo 调用移出事务（拆两个方法，外层编排）（中）；②`configAppService.update` 已是独立事务，外层 `@Transactional` 可去（小）；③reload 放事务后。
- **关联**：[[Bug]] 事务边界

---

## `[Deps]` 依赖升级与版本

### 本模块依赖清单（基于声明文件，未翻依赖源码）

| 依赖 | 版本 | 声明位置 | 已知风险/可升级 | 备注 |
|---|---|---|---|---|
| Spring Web (RestTemplate) | 随 Spring Boot 3.3.5 | `backend/pom.xml`（Spring Boot BOM） | RestTemplate 在 Spring 6 已标记为 maintenance，官方推荐 WebClient/RestClient | 本模块 GET 用 RestTemplate，PUT 用裸 HttpURLConnection（B11-02） |
| Jackson ObjectMapper | 随 Spring Boot 3.3.5 | 同上 | 无 | 用于 Mihomo JSON 解析 |
| Mihomo (Clash Meta) | install.sh 动态拉最新 release（`api.github.com/.../latest`） | `deploy/mihomo/install.sh:68-78` | 无固定版本，每次安装拉最新；可能引入 breaking change（如 API 路径/返回结构变更，关联 B11-05） | 无校验和（无 SHA256 验证，`install.sh:84` 仅下载不校验） |

> 排查范围：基于 pom.xml（Spring Boot BOM）+ install.sh 的 Mihomo 拉取方式。未翻 Spring/Jackson 源码。

### [P3] [Deps] Mihomo 二进制拉取无固定版本 + 无 SHA256 校验  <!-- 编号：B11-13 -->
- **定位**：`deploy/mihomo/install.sh:68`（`LATEST_VERSION=$(curl ... releases/latest)`）、`install.sh:84`（`curl ... -o mihomo.gz` 无 checksum）
- **现象**：install.sh 每次从 GitHub API 取最新 release 版本号并下载，不固定 tag，不校验 SHA256。
- **影响**：①供应链风险——若 GitHub release 被替换或中间人篡改（虽走 https），装到恶意二进制；②可复现性差——不同时间安装的 Mihomo 版本不同，行为可能不一致（API 变更影响 B11-05 等）；③GitHub API 限流时安装失败（`install.sh:71-74`）。
- **根因/分析**：便利性优先。生产部署应固定版本 + 校验。
- **修复方向**：①install.sh 改为固定版本号（如 `MIHOMO_VERSION="v1.18.x"`）+ SHA256 校验（中）；②提供 checksums 文件（小）。
- **关联**：X01 部署架构（引用）；[Deps]

---

## `[Design]` 功能设计合理性

> 必填。从单人维护的技术博客 + 工作日 AI 日报场景出发，回答 §2.5 相关问题。

**审视结论**：

1. **场景适配（§2.5-1）**：代理管理的存在是为 crawler 抓取被墙技术博客/文档服务，与「单人维护技术博客 + AI 日报」场景**部分相关**——日报需要外网信息源，代理是刚需。但完整的 Mihomo 节点切换/测速/订阅 UI 是**重度运维功能**，单人维护者更可能直接 SSH 改 config.yaml 或用 Clash 面板，而非在博客 admin 里点。本模块有**过度设计**倾向：把代理控制台嵌进博客后端，而非让 crawler 直连 Mihomo 自管。

2. **闭环完整性（§2.5-2）**：订阅更新链路**闭环不完整**——保存订阅 URL 写 DB，但刷新 Mihomo（B11-01 因 provider 名错误必失败）后无反馈机制确认节点是否真的更新；crawler 也无回调感知订阅已变。延迟测试结果（`delays`）仅前端临时持有，刷新即丢，无持久化趋势。缺少「订阅更新成功/失败的明确反馈」和「节点延迟历史」。

3. **可运维性（§2.5-3）**：故障定位差——provider 名错误（B11-01）报「Mihomo 不可达」误导排查；URL 编码错误（B11-03）同样误报。无审计日志记录谁在何时切了节点/改了订阅（安全合规弱，节点切换可能影响 crawler 抓取行为却无留痕）。无回滚——订阅 URL 改错后只能手动改回，无历史版本。

4. **MVP 假设检验（§2.5-4）**：CLAUDE.md/README 声称「Web 采集器 MVP Beta 可试用」，但代理管理这个支撑采集的子模块**实际跑不通**——B11-01 订阅刷新必失败，意味着「通过 admin UI 管理代理订阅」这一宣称能力是**半成品**。属于「看起来能用实则跑不通」。

### [P2] [Design] 代理管理作为博客后端子功能过度，且与 crawler 边界混乱  <!-- 编号：B11-14 -->
- **定位**：整个 B11 模块（`application/proxy/` + `infrastructure/proxy/` + `interfaces/rest/ProxyController`）；与 CLAUDE.md「crawler 独立服务原则」对照
- **现象**：代理是 crawler 的辅助设施，却实现为博客后端（Spring Boot）的一等公民模块，含完整 CRUD + UI。crawler（实际消费者）通过 env `PROXY_URL` 静态使用，感知不到 admin 的动态切换；admin 通过博客 UI 操作 Mihomo，操作结果不回传 crawler。
- **影响**：①职责越界——博客后端承担代理运维，违背 crawler 独立原则；②耦合分散——配置在博客 DB、操作在博客 API、消费在 crawler、执行在 Mihomo，四散难追踪；③单人维护者实际更可能用 Mihomo 自带 dashboard（`http://127.0.0.1:9090/ui`）或 Clash Verge，博客这套 UI 价值低。
- **建议方向**：**简化**——长期把代理管理迁到 crawler-service（它才是消费者），博客后端仅保留「订阅 URL 配置项」透传（大）；短期维持现状但补全 B11-01 让功能真正可用 + 补操作审计日志（中）。标改动面 中（短期）/ 大（长期）。
- **关联**：[[Arch]] B11-11；CLAUDE.md「crawler 独立服务原则」

### [P4] [Design] 缺少节点切换/订阅变更的审计与延迟趋势记录  <!-- 编号：B11-15 -->
- **定位**：`ProxyAppService.java:117-119`（selectNode 无日志）、`ProxyAppService.java:149-162`（updateSubscription 无审计）、`ProxyAppService.java:123-140`（testDelay 结果不持久化）
- **现象**：切节点/改订阅/测速均无审计记录；延迟测试结果仅前端临时态，刷新丢失。
- **影响**：代理状态变更影响 crawler 抓取行为，却无法追溯「谁在何时把节点切到日本 → 导致某源抓取失败」。延迟无趋势，无法判断节点质量退化。
- **建议方向**：**补充**——selectNode/updateSubscription 加 INFO 级审计日志（含操作人，小）；延迟结果可选持久化到轻量表（中）。标改动面 小/中。
- **关联**：[[Design]] 闭环完整性

---

## 模块小结

### 严重度统计

| 级别 | 数量 | 条目编号 |
|---|---|---|
| P0 | 0 | — |
| P1 | 2 | B11-01, B11-06 |
| P2 | 5 | B11-02, B11-03, B11-07, B11-08, B11-10, B11-14 |
| P3 | 4 | B11-04, B11-05, B11-09, B11-11, B11-12, B11-13 |
| P4 | 1 | B11-15 |

> 注：B11-14 为 Design 类记 P2，B11-15 为 Design 记 P4。P3 含 B11-04/05/09/11/12/13。统计：P1=2，P2=5（02/03/07/08/10/14 中 14 算 Design-P2，故 Bug/Sec/Arch 的 P2 = 02/03/07/08/10 = 5 条，加 Design-14 = 6 条 P2）。修正下表。

| 级别 | 数量 | 条目编号 |
|---|---|---|
| P0 | 0 | — |
| P1 | 2 | B11-01, B11-06 |
| P2 | 6 | B11-02, B11-03, B11-07, B11-08, B11-10, B11-14 |
| P3 | 6 | B11-04, B11-05, B11-09, B11-11, B11-12, B11-13 |
| P4 | 1 | B11-15 |

### Top 风险（本模块最该先看的 ≤3 条）

1. **B11-01 订阅刷新硬编码 provider 名 "default" 与模板 "sub" 不一致** —— 直接导致「订阅刷新/更新」功能完全不可用，且错误归因误导排查，使 MVP 宣称的代理管理能力沦为半成品。
2. **B11-06 订阅 URL 更新无 SSRF 校验** —— 配合 B11-08（Mihomo 无 secret）+ §9 默认弱口令，构成可被利用的 SSRF 攻击链。
3. **B11-10 零测试覆盖** —— 整个 Mihomo 调用链无任何测试，B11-01/03/05 这类 bug 无安全网，重构高风险。

### 修复优先级建议

- **立即**（P0/P1）：
  - B11-01：provider 名对齐为 `sub`（或抽配置项），让订阅刷新功能可用（小/中）
  - B11-06：updateSubscription 增 SSRF/协议校验，参考 crawler ssrf_guard（中）
- **计划**（P2）：
  - B11-08：Mihomo external-controller 加 secret（中）
  - B11-07：订阅 URL 标敏感 + 加密 + 前端脱敏返回（中）
  - B11-02/B11-03：PUT 统一用 RestTemplate + URL 编码（中）
  - B11-10：补 MihomoProxyClient/ProxyAppService 单测（中）
  - B11-14：明确代理管理边界（文档/长期迁移）
- **择机**（P3/P4）：
  - B11-04/05/09/11/12/13：一致性、数据结构验证、异常处理统一、事务边界、Mihomo 版本固定
  - B11-15：审计日志与延迟趋势

### 排查盲区 / 待复核

- **B11-05**：Mihomo group 的 `history` 字段实际数据结构 [需查证]——需对照 Mihomo 官方 API 文档或实际返回验证 per-node delay 提取逻辑是否有效。
- **B11-09**：GlobalExceptionHandler（B16）是否已处理 MihomoUnreachableException，局部 handler 是否造成覆盖 [需查证]——需读 B16 报告/GlobalExceptionHandler 源码。
- **B11-06**：Mihomo proxy-provider 的 `url` 字段是否支持 `file://` 协议（影响 SSRF 严重度）[需查证]——需查 Mihomo 文档。
- **B11-12**：类级 `@Transactional(readOnly=true)` + 方法级 `@Transactional` 的 AOP 代理实际行为（Spring 是否正确覆盖）[需查证]——需运行时验证或查 Spring 事务文档。
- **B11-13**：Mihomo 最新稳定版本号 + 是否有已知 CVE [需查证]——install.sh 不固定版本，需查 MetaCubeX/mihomo releases。
