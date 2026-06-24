# C02 鉴权与服务边界 排查报告

> **模块编号**：C02
> **排查范围**：ApiKeyMiddleware 鉴权 + X-Client-Id 调用方标识 + auth_protected_prefixes 保护范围 + 失败隔离 + 限流 + 独立服务边界
> **基线 commit**：`6ae930098405f4d0553d96a852f3345d0f39682e`
> **工作区状态**：脏。本模块相关未提交改动：`crawler-service/crawler/search.py`、`crawler-service/optimization/knowledge_base.py`、3 个 crawler 测试文件（均非鉴权/中间件文件，不影响本报告结论）。鉴权核心文件 `standalone/auth.py`、`config.py`、`main.py`、`api/errors.py`、`standalone/routes.py`、`api/ssrf_guard.py`、`standalone/backend_config.py` 均为干净 HEAD 版本。
> **排查日期**：2026-06-23
> **排查人**：C02 排查 agent
> **状态**：草稿

---

## 模块概览

**职责**：crawler-service 对外暴露的 HTTP API（爬取 / 管理 / AI 整理 / 日报触发）通过 `X-API-Key` 头做共享密钥认证，区分公开端点（/health、/docs）与受保护前缀；声明支持 `X-Client-Id` 标识调用方；以独立服务原则运行（CLAUDE.md：≤2 内部服务、不重度绑定博客）。

**关键文件**：
- `crawler-service/standalone/auth.py:9-56` —— `ApiKeyMiddleware`，前缀匹配 + set 判定
- `crawler-service/config.py:45-99` —— `api_keys`、`auth_enabled`、`auth_protected_prefixes`、`auth_header_name` 默认值
- `crawler-service/main.py:112-140` —— `create_app()` 中间件注册与路由挂载
- `crawler-service/api/errors.py:63-99` —— RequestID / AccessLog 中间件（记录范围）
- `crawler-service/standalone/backend_config.py:198-209, 299-327` —— 后端配置同步 api_keys 优先级 + 反向调用 backend 带 `X-Callback-Key`
- `crawler-service/api/ssrf_guard.py:18-61` —— `_is_private_url` SSRF 防护（callback_url 校验）
- `crawler-service/standalone/routes.py:322-384` —— 任务创建 / SSRF 校验入口
- `crawler-service/api/health.py:13-72` —— 公开 /health 返回内容
- `crawler-service/standalone/task_executor.py:248-285, 38-100` —— Semaphore 并发隔离 + callback 重试

**对外接口 / 依赖**：
- 对外：`X-API-Key`（Java→Python，`auth_header_name` 默认 `X-API-Key`）、`X-Callback-Key`（Python→Java，本模块只发送不校验，校验方在 B09）
- 依赖：`config.settings`（运行时动态读取 api_keys / auth_protected_prefixes，支持 backend_config 热刷新）、`httpx`（回调与配置拉取）、backend `/api/internal/collector/config`（可选配置源）

**已读文件清单**：
- `crawler-service/standalone/auth.py` —— 通读
- `crawler-service/config.py` —— 通读
- `crawler-service/main.py` —— 通读
- `crawler-service/api/errors.py` —— 通读
- `crawler-service/api/health.py` —— 通读
- `crawler-service/api/ssrf_guard.py` —— 通读
- `crawler-service/standalone/backend_config.py` —— 通读
- `crawler-service/standalone/routes.py` —— 关键段（路由清单 grep + create_task / ready / runtime/health / sources/test 片段）
- `crawler-service/standalone/task_executor.py` —— grep 失败隔离/超时/并发
- `crawler-service/api/crawl.py` —— grep 路由定义 + 异常处理
- `crawler-service/.env.example` —— 片段（认证/回调配置）
- `crawler-service/tests/test_auth.py` —— 通读（覆盖矩阵）
- `crawler-service/tests/test_backend_config.py`、`test_task_callback.py`、`test_routes_validation.py` —— grep 片段

**主模块归属**：本模块深查 crawler 侧鉴权与边界。对横向主题"鉴权机制一致性"提供 crawler 视角（§2.6）；双向 key 的 backend 侧校验方在 **B09**，本报告只引用不展开。AES 加密 / env 三处一致性引用 **B07** / **X06**。

---

## `[Bug]` 代码正确性与潜在缺陷

> 排查范围：`standalone/auth.py` dispatch 逻辑、config 默认值、middleware 注册顺序、backend_config 对 api_keys 的覆盖。逐项覆盖 §2.1。

### [P2] [Bug] 多 key 场景使用 set `in` 判定，非恒定时间比较 <!-- 编号：C02-01 -->
- **定位**：`crawler-service/standalone/auth.py:50`
- **现象**：校验语句为 `if not valid_keys or api_key not in valid_keys`，其中 `valid_keys` 是 `set`。Python `set.__contains__` 基于 hash 桶查找，比较耗时与桶分布相关，理论上可被时序攻击利用区分"前缀匹配/不匹配"。
- **影响**：内部服务场景下 key 泄露途径主要是日志/配置/网络抓包，时序侧信道在 MVP 内网部署下现实风险低；但本项目 CLAUDE.md 把"恒定时间比较"列为安全原则（见 §2.2 双向 key 重点），且 `test_auth.py:143-149` 已显式测试"部分 key 匹配返回 401"，说明部分匹配场景被关注，却未用 `secrets.compare_digest`。
- **根因/分析**：直接用 set 成员判定而非 `secrets.compare_digest`；多 key 时应遍历逐个恒定时间比较。已排除误判：当前 key 均为长随机串，单次请求时序差异极小，故定 P2 而非 P1。
- **修复方向**：①对单 key 场景直接 `secrets.compare_digest(api_key, single_key)`；②多 key 场景遍历 + `compare_digest`（改动面：小，仅 auth.py）
- **关联**：§2.2 双向 key、横向主题"鉴权机制一致性"、关联 B09（backend 侧 X-API-Key 校验）

### [P3] [Bug] `auth_enabled=False` 全局开关可一键关闭所有鉴权 <!-- 编号：C02-02 -->
- **定位**：`crawler-service/standalone/auth.py:29-30`、`config.py:46`
- **现象**：`auth.py` 第 29 行 `if not settings.auth_enabled: return await call_next(request)` —— 开关一关，所有受保护前缀全部放行，包括 `/api/v1/tasks`（可创建任意爬取任务触发 SSRF 候选链路）、`/api/v1/config/refresh`（可触发配置重载）。
- **影响**：`auth_enabled` 可经 `backend_config._apply_auth_settings`（`backend_config.py:200-201`）由后端配置热刷新。若后端 sys_config 被误配为 `auth.enabled=false`，crawler 瞬间裸奔。`.env.example:21` 默认 `AUTH_ENABLED=true` 是对的，但缺少"生产环境禁止关闭"的硬护栏。
- **根因/分析**：设计上为开发环境便利保留开关，属已知折中。无 bug，但有运维风险——`/api/v1/config/refresh` 自身也在受保护前缀内，关闭鉴权后该端点同样开放，无法在线恢复。
- **修复方向**：①记录运维约束到 deploy 文档；②考虑仅允许环境变量关闭、不允许 backend_config 在线关闭（改动面：小-中）
- **关联**：关联 X06（配置一致性）、deploy 文档

---

## `[Security]` 安全漏洞

> 排查范围：§2.2 通用项 + 技术栈重点之"跨服务双向 key / 限流可绕过 / 敏感信息泄露 / SSRF"。Crawler 侧无 Sa-Token / MyBatis / Cookie，对应重点不适用。

### [P2] [Security] `X-Client-Id` 在代码中完全未实现，仅存在于文档 <!-- 编号：C02-03 -->
- **定位**：声明于 `crawler-service/docs/architecture-v3.md:46,75,78` 与 `README.md:117`；`grep X-Client-Id|client_id` 在 `crawler-service`（排除 .venv）**仅命中文档**，零代码引用。
- **现象**：文档承诺"支持 X-Client-Id 区分调用方"、"MVP 主要用于日志、排查和简单隔离"。但：(a) `ApiKeyMiddleware`（auth.py:48-50）只读 `auth_header_name` 一个头，不读 `X-Client-Id`；(b) `access_log_middleware`（errors.py:83-93）只记 method/path/status/duration，**不记 client_id 也不记任何调用方标识**；(c) 无任何按 client_id 的限流/审计/隔离逻辑。
- **影响**：CLAUDE.md "≤2 内部服务" 假设下，调用方隔离是边界设计的关键一环。当前所有内部服务共用同一组 api_keys（逗号分隔多 key，但 key 与 client 无绑定），任一 key 泄露等同全局泄露，无法从日志追溯是哪个调用方发起的请求。文档与实现严重不符，是"看起来能用实则跑不通"的半成品（§2.5 问题 4）。
- **根因/分析**：设计阶段规划了 header，实现阶段未落地。非安全隐患本身，但文档承诺造成虚假安全感。
- **修复方向**：①若 MVP 不做隔离，删除文档中 X-Client-Id 承诺（改动面：小，文档）；②若要落地最小版：access_log 增加记录 X-Client-Id（改动面：小，单文件 errors.py）；③进阶：按 client_id 维度限流/计费（改动面：中）
- **关联**：§2.5 问题 4/7、§2.6 横向主题、关联 C02-04（限流缺失）

### [P2] [Security] crawler 侧无任何限流，受保护端点可被暴力/滥用 <!-- 编号：C02-04 -->
- **定位**：全模块 grep `rate|limit|throttle|slowapi|429` 在 crawler-service（排除 .venv 与 AI provider 返回的 429）**无任何应用层限流实现**。`api/errors.py:39-40` 的 `ai_rate_limited` 仅处理 AI 上游 429，不保护本服务入口。
- **现象**：`/crawl/search`、`/api/v1/tasks`（POST，触发真实爬取+AI 整理）、`/api/v1/digests/trigger`（触发日报，一次几分钟+多轮 AI 调用）均无入口限流。认证前缀判定（auth.py:43）`startswith` 一旦通过即放行，无 per-key/per-IP 频率限制。
- **影响**：持有合法 key 的内部服务若发生 bug（如循环触发 digest），或 key 泄露，可瞬间打满 Crawl4AI 浏览器实例（`max_concurrent_crawls=3`，config.py:17）与 AI token 预算。CLAUDE.md "单个外部源失败不能拖垮整个服务" 原则在"恶意/失控调用方"维度无防护。注意：`max_concurrent_tasks` Semaphore（task_executor.py:248）能挡住并发数，但挡不住短时间高频排队堆积。
- **根因/分析**：MVP 单人 ≤2 内部服务假设下，限流优先级低，属可理解的取舍。但 `digest/trigger` 这类重操作零限流风险偏高。
- **修复方向**：①对 `/digests/trigger`、`/tasks` POST 加最小频控（如每分钟 1-5 次/key）；②接入 slowapi 或简单内存计数（改动面：中）
- **关联**：§2.5 问题 7（单点扩展）、关联 C02-03（client_id 缺失使 per-key 限流也难做）

### [P3] [Security] /health 公开端点泄露内部组件详情 <!-- 编号：C02-05 -->
- **定位**：`crawler-service/api/health.py:13-72`
- **现象**：公开 `/health`（auth.py:33 白名单）返回：Crawl4AI 版本与可用性、AI 模型名（`ai_settings.ai_model`）、调度器运行状态、**SQLite 数据库绝对路径**（`db_path`，config 默认 `data/crawler.db`，可被 backend_config 改写为任意路径）、数据库大小、活跃任务数、爬虫引擎 mode（degraded/strict）。
- **影响**：未认证方可探测：服务是否启用 AI、用什么模型（便于针对性攻击 AI 端点）、DB 文件位置（配合其他路径遍历/SSRF 可定位数据文件）、当前负载。MVP 内网部署风险低，但对外暴露时（如直接挂公网调试）信息泄漏面偏大。
- **根因/分析**：health 端点为运维便利塞了过多诊断字段。常见做法是拆分 `/health`（仅 status:healthy）与 `/ready`（详细，但 /ready 在受保护前缀 `/api/v1` 下，auth.py 实际要求认证 ✓）。问题在于 `/health` 的详细度与 `/api/v1/ready`（routes.py:1135）几乎重叠，却一个公开一个保护。
- **修复方向**：①`/health` 仅返回 `{"status":"healthy"}`，详情移到 `/api/v1/health-detail`（受保护）；②或对非本机请求返回精简版（改动面：小-中）
- **关联**：§2.2 敏感信息泄露

### [P4] [Security] /docs、/openapi.json 公开暴露完整 API schema <!-- 编号：C02-06 -->
- **定位**：`crawler-service/standalone/auth.py:33-37`、`main.py:118-123`（FastAPI 默认 docs_url/openapi_url 未禁用）
- **现象**：`/docs`、`/redoc`、`/openapi.json` 全部在白名单，未认证可获取全部受保护端点的参数 schema（如 `CreateTaskRequest` 字段、`callback_url` 可控等）。
- **影响**：攻击面侦察便利。配合 C02-04（无限流）与若发生的 key 泄露，可快速构造合法请求。内网 MVP 风险低。
- **根因/分析**：开发便利优先。生产环境通常应关闭 docs。
- **修复方向**：生产部署通过 env 开关关闭 docs_url/openapi_url，或纳入受保护前缀（改动面：小）
- **关联**：§2.5 问题 3（可运维性）

---

## `[Arch]` 架构与技术债

> 排查范围：独立服务边界、配置源优先级、middleware 注册、失败隔离。

### [P3] [Arch] api_keys 配置源三路（env / sys_config / service.api-key）优先级隐式 <!-- 编号：C02-07 -->
- **定位**：`crawler-service/standalone/backend_config.py:198-209`、`config.py:45`、`backend_config.py:74-75`
- **现象**：`_apply_auth_settings` 优先级：①sys_config `auth.api_keys`（非空时覆盖）→ ②sys_config `service.api-key`（非空时覆盖）→ ③env `API_KEYS`（兜底）。而 `_config_fetch_key`（用于反向调 backend 的 X-Callback-Key）取 `api_keys` 第一项或 `callback_api_key`。即"认证 key"与"回调 key"在配置缺失时会互相兜底混用。
- **影响**：运维改 sys_config 的 `auth.api_keys` 时，若误清空，会静默回退到 env 值（test_backend_config.py:76-93 已测此行为），不易察觉漂移。`api_keys[0]` 兼作 callback key 的兜底，使两类密钥语义耦合，违背"独立服务 key 边界清晰"。
- **根因/分析**：MVP 减少配置项的折中。已有测试守护回退行为，故 P3。
- **修复方向**：①文档显式记录三路优先级；②callback key 与 auth key 解耦，不互为兜底（改动面：中，涉及配置语义变更需补测试）
- **关联**：关联 X06（配置一致性）、B07（AES 配置加密）、C11（配置同步主模块）

### [P4] [Arch] middleware 注册混用两种风格，顺序依赖隐式约定 <!-- 编号：C02-08 -->
- **定位**：`crawler-service/main.py:126-137`、`api/errors.py:96-99`
- **现象**：`register_middlewares` 用 `app.middleware("http")(fn)` 注册 RequestID + AccessLog（main.py:126 先调用），随后 `app.add_middleware(ApiKeyMiddleware)`（main.py:135）。Starlette 中 `add_middleware` 把中间件包在**最外层**，而 `app.middleware("http")` 注册的在**内层**。因此请求实际顺序：ApiKey（外）→ RequestID → AccessLog → 路由。
- **影响**：ApiKey 校验失败返回 401 时，RequestID 中间件先于它？实际不会——外层 ApiKey 先执行，401 短路时内层 RequestID/AccessLog 不执行，导致**被拒请求没有 X-Request-ID 响应头、也不进 access_log**（errors.py:88 仅记非 /health 路径）。排查暴力探测时缺少日志。
- **根因/分析**：非 bug，是顺序副作用。若想让 401 也带 request_id 并被审计，应把 ApiKey 放到最内层。
- **修复方向**：统一用 `add_middleware` 并显式控制顺序，或接受现状（改动面：小）
- **关联**：关联 C02-04（限流/审计缺失）

---

## `[Deps]` 依赖升级与版本

### 本模块依赖清单（基于声明文件，未翻依赖源码）

| 依赖 | 版本 | 声明位置 | 已知风险/可升级 | 备注 |
|---|---|---|---|---|
| fastapi | （未在本模块直接 import 版本号，见 requirements.txt） | `crawler-service/requirements.txt` | [需查证] 具体版本 | 提供 `add_middleware` / `app.middleware` |
| starlette | 随 fastapi | 同上 | [需查证] | `BaseHTTPMiddleware` 基类（auth.py:3） |
| httpx | （callback / config fetch） | 同上 | [需查证] | X-Callback-Key 发送方 |
| pydantic-settings | （config.py:4） | 同上 | [需查证] | `BaseSettings` |

> 排查范围：本模块仅声明性依赖（认证逻辑无第三方安全库，未用 `secrets`/`hmac` 标准库以外组件）。具体版本号未在本模块文件中出现，依赖版本统一在 C12 / X01 的 requirements 审计覆盖。未发现本模块专属依赖风险。

---

## `[Design]` 功能设计合理性

> 必填。从真实使用出发回答 §2.5 相关问题（≥2）。

**审视结论**：

1. **场景适配（§2.5-1）**：单人维护 + ≤2 内部服务场景下，`X-API-Key` 单层共享密钥 + 前缀白名单的鉴权模型**基本适配**，不属过度设计。但"多 key 支持"（config 逗号分隔）与"X-Client-Id 调用方标识"的组合**只做了一半**——多 key 已实现（test_auth.py:119-126 验证），client_id 未落地（C02-03），导致多 key 无法与调用方对应，场景上是"半成品"而非"过简"。

2. **独立服务边界 / 单点扩展（§2.5-7）**：CLAUDE.md 明确 crawler"不应重度绑定博客"。实测 `main.py:76-80` lifespan 中 `backend_config.fetch_from_backend()` 包在 try/except 里，**backend 不可用时仅 warning 不阻断启动**，降级路径成立 ✓；`java_api_url` 为空时所有 backend 交互跳过（digest.py:24、backend_config.py:303）✓。**独立服务原则在启动/降级维度守住了**。但"≤2 内部服务"假设在**无限流 + 无 client_id 隔离**下是裸假设——真实增长到 3+ 服务时，第一个硬阻塞是"无法按调用方限流/审计"（C02-03/04），而非鉴权本身。

3. **可运维性（§2.5-3）**：`auth_enabled` 全局开关可在线关闭（C02-02）且 `/api/v1/config/refresh` 自身需认证——关闭后无法通过该端点恢复，属可运维性缺陷。`/health` 信息丰富利于排查（C02-05 是双刃剑）。整体可运维性中等。

### [P4] [Design] 多 key 与 client_id 未配对，调用方隔离停留在口号 <!-- 编号：C02-09 -->
- **定位**：`config.py:45`（api_keys 多值）、文档 `README.md:116-117`（"建议每个内部服务使用独立 key"、"X-Client-Id 传稳定标识"）
- **现象**：当前设计建议"每服务一 key"+ "X-Client-Id 标识"，但 key 与 client 无任何绑定关系，任意 key 任意 client 都放行，access_log 也不记 client。
- **影响**：真实使用下，2 个内部服务用 2 个 key 时，运维无法从日志判断某次异常请求来自哪个服务，key 泄露也无法定位泄露源。
- **建议方向**：维持现状（接受 MVP 简化）或落地最小版（access_log 记 X-Client-Id）（标改动面：小）
- **关联**：§2.5 问题 7、关联 C02-03

---

## 模块小结

### 严重度统计

| 级别 | 数量 | 条目编号 |
|---|---|---|
| P0 | 0 | — |
| P1 | 0 | — |
| P2 | 3 | C02-01、C02-03、C02-04 |
| P3 | 3 | C02-02、C02-05、C02-07 |
| P4 | 3 | C02-06、C02-08、C02-09 |

### Top 风险（本模块最该先看的 ≤3 条）

1. **C02-03 X-Client-Id 代码零实现，仅文档承诺** —— 文档与实现严重不符，调用方隔离/审计完全缺失，是"看起来能用实则跑不通"的典型。
2. **C02-04 入口无限流** —— 持有 key 的失控/泄露调用方可瞬间打满浏览器实例与 AI 预算，`/digests/trigger` 这类重操作风险最高。
3. **C02-01 key 比较非恒定时间** —— 与 CLAUDE.md/§2.2 "双向 key 恒定时间比较"原则不符，虽 MVP 内网风险低但属明确安全欠账。

### 修复优先级建议

- **立即**（P0/P1）：无。
- **计划**（P2）：
  - C02-03：二选一——删除文档 X-Client-Id 承诺，或在 access_log 落地记录（建议后者，改动小收益大）。
  - C02-04：至少给 `/api/v1/digests/trigger`、POST `/api/v1/tasks` 加 per-key 最小频控。
  - C02-01：`auth.py:50` 改用 `secrets.compare_digest`（多 key 遍历）。
- **择机**（P3/P4）：
  - C02-02：文档约束 `auth_enabled` 在线关闭风险，或限制只能 env 关闭。
  - C02-05：`/health` 精简化，详情移入受保护端点。
  - C02-06/C02-07/C02-08/C02-09：生产部署前评估。

### 排查盲区 / 待复核

- **[需查证] C02-Deps**：fastapi/starlette/httpx/pydantic-settings 的确切版本号未在本模块文件出现，依赖版本审计统一在 C12/X01；本模块未用 `secrets`/`hmac` 以外的安全敏感第三方库，故无模块专属依赖风险。需 C12/X01 复核 fastapi 版本是否有已知的 middleware 顺序/BaseHTTPMiddleware 相关 CVE。
- **[需查证] C02-02 实际部署**：生产 `AUTH_ENABLED` 是否真为 true、sys_config 是否会在线改 `auth.enabled`，需结合 B07/X06 配置审计与 deploy 实际环境确认。
- **[需查证] C02-04 下游**：`max_concurrent_tasks` Semaphore 在 task_executor 层是否真能挡住"高频创建但慢执行"导致的队列膨胀，需 C10（调度器）/C03（采集核心）复核任务排队上限。
