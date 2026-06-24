# C01 API 层与中间件 排查报告

> **模块编号**：C01
> **排查范围**：crawl 即时接口 + health + ssrf_guard + errors（AppError + RequestID + AccessLog 中间件 + 异常处理器）+ context + 中间件注册顺序 + CORS
> **基线 commit**：`6ae930098405f4d0553d96a852f3345d0f39682e`
> **工作区状态**：脏。涉及 crawler-service 的未提交改动为 `crawler/search.py`、`optimization/knowledge_base.py`、`tests/test_knowledge_base.py`、`tests/test_optimization.py`、`tests/test_search.py`，**均不属于 C01 范围**（C01 五个核心文件 `api/*.py` + `main.py` 均无未提交改动），不影响本报告结论。
> **排查日期**：2026-06-24
> **排查人**：C01 排查 agent
> **状态**：待复核

---

## 模块概览

**职责**：crawler-service 对外的同步爬取/AI 整理 HTTP 入口 + 全局中间件（RequestID、AccessLog）+ 分级异常处理 + SSRF 应用层防护 + 健康检查。

**关键文件**：
- `crawler-service/api/crawl.py:93-178` —— `/crawl/single`、`/crawl/deep`、`/crawl/search` 三个即时爬取端点
- `crawler-service/api/crawl.py:203-289` —— `/organize`、`/keyword` 两个 AI 整理端点
- `crawler-service/api/ssrf_guard.py:18-61` —— `_is_private_url` + `validate_url_ssrf`（应用层 SSRF 防护，文档已声明不防 DNS rebinding）
- `crawler-service/api/errors.py:18-60` —— `AppError` + 错误码工厂
- `crawler-service/api/errors.py:65-99` —— RequestID 中间件 + AccessLog 中间件 + `register_middlewares`
- `crawler-service/api/errors.py:104-145` —— `register_error_handlers`（validation/AppError/HTTPException/兜底 Exception 四档）
- `crawler-service/api/health.py:13-72` —— `/health` 含组件状态
- `crawler-service/api/context.py:1-4` —— `request_id_var` ContextVar
- `crawler-service/main.py:112-140` —— `create_app()`，路由/中间件/异常处理器注册顺序

**对外接口 / 依赖**：
- 对外：`POST /crawl/single`、`POST /crawl/deep`、`POST /crawl/search`、`POST /organize`、`POST /keyword`、`GET /health`
- 依赖：FastAPI、Pydantic、`crawler.single/deep/search`、`ai.content_organizer`、`config.settings`、`standalone.scheduler`、`standalone.task_executor`、`crawler.dependencies.crawl4ai_status`

**已读文件清单**（可追溯 + 暴露盲区）：
- `crawler-service/api/crawl.py` —— 通读
- `crawler-service/api/errors.py` —— 通读
- `crawler-service/api/ssrf_guard.py` —— 通读
- `crawler-service/api/health.py` —— 通读
- `crawler-service/api/context.py` —— 通读（4 行）
- `crawler-service/main.py` —— 通读（含 `create_app`/`lifespan`）
- `crawler-service/config.py` —— 片段（基础配置项 + limits）
- `crawler-service/crawler/single.py` —— 片段（确认无 redirect 二次校验，仅 grep 覆盖 redirect 字样）
- `crawler-service/crawler/deep.py` —— 片段（确认 BFS 子链接不重新 SSRF 校验）
- `crawler-service/crawler/search.py` —— grep + 片段（确认 `follow_redirects=True` 无二次校验）
- `crawler-service/standalone/routes.py` —— grep（callback_url SSRF 校验、callback 字段契约）
- `crawler-service/requirements.txt` —— 通读（依赖清单）
- **盲区**：Crawl4AI / Playwright 浏览器内部重定向行为（依赖源码不翻，§1.3.1）标 `[需查证]`；uvicorn 前置 nginx 是否补 CORS/限流未在代码层确认。

**主模块归属**：C01 是 **API 层主模块**。对共享对象 `ApiKeyMiddleware` / 限流 / 失败隔离（C02 主模块）**只引用**；callback 字段契约与 **B09 共查**（横向主题"跨服务契约"，§2.6）；`CrawlerTaskClient`（backend→crawler）归 **B10**，只引用。

---

## `[Bug]` 代码正确性与潜在缺陷

> 排查范围：crawl.py 五个端点的入参校验/异常分支、errors.py 中间件与异常处理器、health.py 组件探测、context.py ContextVar 用法。

### [P2] [Bug] /organize、/keyword 透传底层异常字符串给客户端（信息泄漏口径不一致）  <!-- 编号：C01-01 -->
- **定位**：`crawler-service/api/crawl.py:262-264`、`crawler-service/api/crawl.py:287-289`
- **现象**：`/organize` 与 `/keyword` 的兜底 `except Exception as e` 直接 `raise HTTPException(status_code=500, detail=f"AI organize failed: {str(e)}")` / `f"AI keyword processing failed: {str(e)}"`，把底层异常字符串拼进响应体。而 `/crawl/*` 三个端点（crawl.py:108/145/178）同样如此。
- **影响**：`str(e)` 可能含上游 AI provider 返回的 URL/认证头片段、httpx 连接错误中的内部主机名、数据库路径等，构成信息泄漏。与 errors.py:138-145 全局兜底处理器"生产环境只暴露 `type(exc).__name__`"的口径**自相矛盾**——但因为这三个端点先 `raise HTTPException`，会被 `http_handler`(errors.py:126-132) 捕获而**绕过**全局兜底，导致 leak 路径成立。
- **根因/分析**：端点内手动 `raise HTTPException` 捷径了 `AppError` 体系，未被 `global_exception_handler` 的脱敏逻辑覆盖。已排除误判：`http_handler` 对所有 `HTTPException` 只取 `str(exc.detail)`，不会二次脱敏。
- **修复方向**：①端点内捕获后改为 `raise AppError("AI_ORGANIZE_FAILED", "AI 整理失败", 500)` 走 `app_error_handler`；或②兜底 `raise` 让全局处理器接管，detail 用固定文案 + 服务端日志记 `str(e)`。改动面：小（单文件，约 6 处 raise）。
- **关联**：次维度 [Security]（信息泄漏）；§2.2 敏感信息泄露；与 C01-03 异常处理口径问题同源。

### [P2] [Bug] /organize 重试循环 result 可能仍为 None 导致 AttributeError  <!-- 编号：C01-02 -->
- **定位**：`crawler-service/api/crawl.py:226-260`
- **现象**：`result = None`；循环 `for attempt in range(max_retries + 1)` 内 `RateLimitError` 在最后一次也 `raise`（246 行），`OrganizerError` 直接 `raise`（247-248 行），正常路径 `break`。但若 `max_retries + 1 == 0`（即 `ai_settings.ai_max_retries` 为 0 时循环体不执行），或循环内既未 `break` 也未 `raise` 的分支不存在时，`result` 仍为 `None`，随后 `result.title`(253) 抛 `AttributeError`。
- **影响**：当 `ai_max_retries=0` 时（配置边界），`/organize` 必然 500 而非正常返回。属边界条件缺陷。
- **根因/分析**：`ai_max_retries` 默认值未在本次 grep 中确认（`ai/config.py`），标 `[需查证]`；但只要配置允许设为 0，bug 成立。已排除：循环体只要执行且非限流即 `break`，故 `ai_max_retries>=1` 时不触发。
- **修复方向**：循环后增加 `if result is None: raise AppError("AI_ORGANIZE_FAILED", ..., 500)` 兜底。改动面：小。
- **关联**：次维度 [Bug]（边界条件）；配置项 `ai_max_retries`。

### [P3] [Bug] AccessLog 不记录请求体/查询参数，排障时缺关键线索  <!-- 编号：C01-03 -->
- **定位**：`crawler-service/api/errors.py:83-93`
- **现象**：AccessLog 只记 `method / path / status / duration`，对 `/crawl/search` 的 keyword、`/organize` 的 pages 数量等**不记录**。同时 path 用 `request.url.path`（不含 query string）。
- **影响**：故障复盘时无法定位是哪个关键词/哪批 pages 触发的 500，需要去翻业务 logger.info（crawl.py 内有部分记录但不全）。属于可运维性短板，非 bug。
- **根因/分析**：设计取舍——不记 query 避免泄漏敏感参数（正向），但也丢了排障线索。
- **修复方向**：可选记录 query string（非 body）+ 关键标识（keyword 哈希、pages 数量），保持不记完整 body。改动面：小。
- **关联**：次维度 [Design]（可运维性）。

---

## `[Security]` 安全漏洞

> 排查范围：ssrf_guard 完整性（私有/回环/保留/IPv6/DNS rebinding/hostname 长度/redirect 二次校验）、errors 异常处理器信息泄漏、health 信息暴露、CORS、中间件顺序、双向 key（callback key 由 B09 主查，本节只记 API 层视角）。

### [P1] [Security] SSRF 防护不覆盖 HTTP 客户端重定向与 BFS 子链接（redirect-to-internal + DNS rebinding 放大）  <!-- 编号：C01-04 -->
- **定位**：`crawler-service/api/ssrf_guard.py:18-50`（仅校验 hostname 字面量）+ `crawler-service/crawler/search.py:362,586`（`follow_redirects=True`）+ `crawler-service/crawler/deep.py:120-174`（BFS 子链接不重新校验）
- **现象**：
  1. `validate_url_ssrf` 只在请求入口校验**用户提交 URL 的 hostname**，Crawl4AI/Playwright 浏览器和 httpx 实际抓取时 `follow_redirects=True`，对 302 跳转目标**不二次校验**。
  2. BFS 深爬（`/crawl/deep`）由 Crawl4AI `BFSDeepCrawlStrategy` 发现的内部子链接（`deep.py:158` 读 `result.links.internal`）不经过 `validate_url_ssrf`。
  3. 搜索引擎结果页（`search.py:757`）对每个结果 URL 校验了一次，但 baidu 跳转解码（`_decode_baidu_redirect` search.py:378-410 `follow_redirects=True`）的最终目标不二次校验。
- **影响**：攻击者构造公网 URL（通过入口校验）→ 302/JS 跳转到 `http://169.254.169.254/`（云元数据）/ `http://127.0.0.1:8501`（内网 admin）→ 浏览器跟随抓取 → 内容进入 markdown 返回调用方。`ssrf_guard.py:1-7` 文档已声明"不防 DNS rebinding、需网络层补防护"，但**重定向-to-internal** 这一更易利用的路径未在文档/代码中提示。
- **根因/分析**：应用层 SSRF 防护的固有局限——仅在入口校验字面 hostname，实际抓取链路（浏览器/httpx）独立解析与跟随。已排除：`config.py:9` host=0.0.0.0 与此无关。
- **修复方向**：①网络层（部署侧）用 iptables/egress proxy 拦截 RFC1918/169.254/127.0.0.0/8 出站（主补，归 X01）；②应用层在 Crawl4AI 抓取后对 `result.url`（最终落地 URL）做二次 SSRF 校验，命中则丢弃结果；③BFS 子链接在交给 Crawl4AI 前逐条 `validate_url_ssrf`。改动面：中（应用层 ②③）+ 大（网络层 ①，跨模块 X01）。
- **关联**：次维度 [Security]；横向主题"跨服务契约"无关；主模块归属：SSRF 应用层归 C01，网络层归 X01；§2.2 SSRF 重点。

### [P1] [Security] /health 端点向任意调用方暴露内部状态（DB 路径、调度器状态、AI 模型名、活跃任务数）  <!-- 编号：C01-05 -->
- **定位**：`crawler-service/api/health.py:13-72`；鉴权由 `ApiKeyMiddleware`（C02 主模块）控制，但 `/health` 是否在保护前缀内 `[需查证]`
- **现象**：`/health` 返回：`database.path`（绝对路径，泄露部署目录结构）、`database.size_mb`、`scheduler` 完整状态对象、`ai.model`（AI 模型名）、`active_tasks`、`crawler.version`。
- **影响**：①若 `/health` 在 ApiKeyMiddleware 白名单（典型设计让 k8s/docker 健康探测免鉴权），则任意网络可达者可获取部署路径/AI 模型/任务负载，用于后续攻击画像；②DB 绝对路径泄漏助力路径遍历类漏洞利用。即使 `/health` 要 key，也应遵循最小暴露。
- **根因/分析**：health 端点把"就绪探测"（status/version）和"运维诊断"（components 细节）合并到一个端点，未分层。`main.py:128` 注册 health_router 时无额外保护注解。
- **修复方向**：①拆 `/health`（轻量，仅 status=ok，免鉴权供探活）+ `/api/v1/health/detail`（带鉴权，返回 components）；②DB 路径脱敏为布尔 `db_exists`，不返回绝对路径；③AI model 在非 debug 下不返回。改动面：小-中。
- **关联**：次维度 [Security]（信息泄漏）；与 C02（鉴权白名单）共查 `/health` 是否被保护。

### [P2] [Security] 全局兜底异常处理器在 debug=False 下仍暴露异常类名  <!-- 编号：C01-06 -->
- **定位**：`crawler-service/api/errors.py:134-145`
- **现象**：`global_exception_handler` 非 debug 时 `hint = f"Internal server error: {type(exc).__name__}"`，异常类名直接进响应。
- **影响**：异常类名（如 `psycopg.OperationalError`、`redis.AuthenticationError`、自定义内部异常）泄露技术栈/依赖指纹，辅助攻击者画像。影响程度中等（类名非完整堆栈）。
- **根因/分析**：注释（138 行）写"生产环境暴露异常类名作为线索"，是有意为之，但权衡偏宽松。
- **修复方向**：非 debug 下仅返回 `{"code":"INTERNAL_ERROR","message":"Internal server error"}`，类名仅进服务端日志。改动面：小。
- **关联**：次维度 [Security]（信息泄漏）；与 C01-01 同源（口径不一致）。

### [P2] [Security] RequestID 中间件直接信任客户端 X-Request-ID 头（无格式校验/无长度限制）  <!-- 编号：C01-07 -->
- **定位**：`crawler-service/api/errors.py:69-78`
- **现象**：`request_id = request.headers.get("X-Request-ID", uuid.uuid4().hex[:12])`——客户端传入的任意值被原样写入 `request.state`、响应头 `X-Request-ID`、并通过 `request_id_var` 进入日志。
- **影响**：①日志注入：攻击者传含换行/ANSI 转义/XSS payload 的 X-Request-ID，污染日志（日志查看器若未转义可被攻击）；②响应头注入：若 uvicorn 不校验头值换行（FastAPI/Starlette 通常拦截，但 `[需查证]`）；③日志关联伪造：掩盖真实请求链路。
- **根因/分析**：信任客户端头是 RequestID 常见模式，但缺格式白名单（如 `^[A-Za-z0-9-]{1,64}$`）。生成分支用 `uuid.uuid4().hex[:12]`（12 位 hex）安全，信任分支不安全。
- **修复方向**：对客户端传入的 X-Request-ID 做正则校验（长度+字符集），不合法则忽略并用新生成 uuid。改动面：小。
- **关联**：次维度 [Security]（日志注入/头注入）。

### [P2] [Security] main.py 未配置 CORS（跨域调用方行为未定义）  <!-- 编号：C01-08 -->
- **定位**：`crawler-service/main.py:112-140`（`create_app` 全文 grep 无 `CORSMiddleware`/`add_middleware(CORS...)`）
- **现象**：crawler-service 无任何 CORS 配置。`grep -r "CORS\|allow_origins\|Access-Control"` 全仓库零命中。
- **影响**：①浏览器端（如 Vue 前端 admin 页）直接调 crawler 会被同源策略挡（无 `Access-Control-Allow-Origin` 响应头），跨域 POST 预检失败——但当前架构前端走 backend 代理，不直连 crawler，故 MVP 阶段无实际影响；②若未来前端/其他浏览器端直连 crawler，需补 CORS 且不能 `allow_origins=*` + `allow_credentials=true` 组合（§2.2 CORS 重点）。当前是"未配置"而非"配置过宽"，风险等级 P2（潜在）。
- **根因/分析**：架构上前端→backend→crawler，crawler 仅服务端调用，CORS 非必需。设计合理但未在文档显式说明。
- **修复方向**：维持不配置（服务端调用无需 CORS）即可，但应在 crawler README 显式声明"仅供服务端调用，未启用 CORS；若需浏览器直连须显式配置白名单"。改动面：小（文档）/中（若补 CORS）。
- **关联**：次维度 [Arch]（架构边界）；§2.2 CORS；CLAUDE.md "Crawler 不应重度绑定博客系统"。

### [P3] [Security] ssrf_guard 解析异常时默认放行（fail-open）  <!-- 编号：C01-09 -->
- **定位**：`crawler-service/api/ssrf_guard.py:49-50`
- **现象**：`_is_private_url` 的最外层 `except Exception: return False`——任何解析异常都判为"非私有"放行。
- **影响**：畸形 URL（如 `file:///`、`gopher://`、异常 Unicode 编码 hostname）若触发 urlparse 异常分支，会被放行进入 Crawl4AI。实际 Crawl4AI/Playwright 会拒绝非 http(s) scheme，故危害有限，但 fail-open 方向错误。
- **根因/分析**：安全校验函数应 fail-closed（异常时拒绝）。
- **修复方向**：最外层 `except Exception: return True`（异常时按私有处理），或显式处理 scheme 白名单（仅允许 http/https）。改动面：小。
- **关联**：次维度 [Security]；与 C01-04 SSRF 同主题。

### [P3] [Security] ssrf_guard 对 file/gopher/ftp 等非 http scheme 无白名单  <!-- 编号：C01-10 -->
- **定位**：`crawler-service/api/ssrf_guard.py:18-50`
- **现象**：只检查 hostname 是否私有/保留，不校验 URL scheme。`file:///etc/passwd` 的 hostname 为空（23 行 `if not hostname: return False` 直接放行）。
- **影响**：依赖下游 Crawl4AI 拒绝非 http scheme。若下游某条降级路径（httpx fallback）未严格校验 scheme，`file://`/`gopher://` 可能被解析。`[需查证]` Crawl4AI 0.8.6 是否拒绝 file://（依赖源码不翻，§1.3.1）。
- **根因/分析**：scheme 白名单应在应用层显式声明。
- **修复方向**：`validate_url_ssrf` 入口加 `if parsed.scheme not in ("http","https"): raise HTTPException(400,...)`。改动面：小。
- **关联**：次维度 [Security]；§2.2 SSRF。

---

## `[Arch]` 架构与技术债

> 排查范围：中间件注册顺序、AppError 采用率、errors.py 与各端点异常口径一致性、health 端点分层。

### [P2] [Arch] AppError 体系采用率低——即时端点几乎全用 HTTPException，错误码体系形同虚设  <!-- 编号：C01-11 -->
- **定位**：`crawler-service/api/errors.py:34-60`（8 个错误码工厂）vs `crawler-service/api/crawl.py:108/121/123/145/154/178/211/264`（全部 `raise HTTPException`）+ `crawler-service/crawler/search.py:757` 内部异常
- **现象**：errors.py 定义了 `CRAWL_TIMEOUT`/`AI_RATE_LIMITED`/`SEARCH_BLOCKED`/`INVALID_URL`/`TASK_NOT_TERMINAL` 等 8 个结构化错误码及 `AppError` 基类，但 crawl.py 的 5 个即时端点**无一使用**——超时返回 500（crawl.py:108），限流返回 500（crawl.py:264），全部塌缩成 `{"code":"HTTP_ERROR"}`（errors.py:129）。
- **影响**：①调用方（backend `CrawlerTaskClient`）无法据 `code` 区分"超时重试"/"限流退避"/"永久失败"，只能凭 HTTP 状态码（且都是 500）猜测；②结构化错误码体系的投资回报落空；③与 B09 回调契约（§2.6 跨服务契约）的 error 字段对齐失去抓手。
- **根因/分析**：AppError 体系后建但未回填到即时端点。`search.py` 等业务层也只抛裸 Exception。已排除：`standalone/routes.py`（C02）可能有采用，但不在 C01 范围。
- **修复方向**：①crawl.py 各 except 分支按语义映射到 `crawl_timeout()`/`ai_rate_limited()`/`search_blocked()` 等 AppError 工厂；②内部业务层（crawler.search 等）抛 AppError，端点不再 try/except 吞掉。改动面：中（跨 crawl.py + 部分 crawler/*）。
- **关联**：次维度 [Arch]（一致性）；横向主题"跨服务契约"（§2.6，错误码契约影响 B09 回调字段）；与 C01-01 同根。

### [P2] [Arch] 中间件注册顺序：鉴权中间件晚于 RequestID/AccessLog 注册，实际执行顺序需复核  <!-- 编号：C01-12 -->
- **定位**：`crawler-service/main.py:126`（`register_middlewares` 注册 RequestID+AccessLog）→ `main.py:135`（`app.add_middleware(ApiKeyMiddleware)`）
- **现象**：Starlette 中间件执行顺序是**后添加的先执行**（LIFO 包裹）。代码顺序：RequestID → AccessLog → ApiKey，实际请求栈：ApiKey 最外层先跑 → AccessLog → RequestID → 路由。
- **影响**：①实际效果"ApiKey 先于 AccessLog"——鉴权失败的请求也会被 AccessLog 记录（正向，便于追踪鉴权失败）；②但"ApiKey 先于 RequestID"意味着鉴权失败时 `request.state.request_id` 尚未设置，此时若 ApiKeyMiddleware 内抛 HTTPException 走 `http_handler`(errors.py:126)，`rid` 为空，响应无 request_id，日志无法关联。属可运维性细节。
- **根因/分析**：当前顺序对"鉴权失败也记日志"是合理的，但 RequestID 未最早设置导致鉴权失败请求无关联 ID。`[需查证]` ApiKeyMiddleware 是否在 reject 前已读取 request_id（C02 主模块）。
- **修复方向**：若希望鉴权失败也可关联，把 RequestID 调整为最先执行（最后 add）。改动面：小（但需测试覆盖）。
- **关联**：次维度 [Arch]；C02 主模块（ApiKeyMiddleware 细节）。

### [P3] [Arch] health.py 的 VERSION 常量与 main.py 的 FastAPI(version="2.0.0") 双源  <!-- 编号：C01-13 -->
- **定位**：`crawler-service/api/health.py:10`（`VERSION = "2.0.0"`）+ `crawler-service/main.py:121`（`FastAPI(..., version="2.0.0")`）
- **现象**：版本号两处硬编码，升级时易漏改其一。
- **影响**：版本漂移，`/health` 与 OpenAPI `/openapi.json` 版本不一致时排查误导。低危。
- **根因/分析**：缺乏统一版本源。
- **修复方向**：抽到 `__version__.py` 或 `config.settings.version`，两处引用。改动面：小。
- **关联**：次维度 [Arch]（DRY）；X05 文档一致性。

---

## `[Deps]` 依赖升级与版本

### 本模块依赖清单（基于 `crawler-service/requirements.txt`，未翻依赖源码）

| 依赖 | 版本 | 声明位置 | 已知风险/可升级 | 备注 |
|---|---|---|---|---|
| fastapi | `>=0.109.0` | requirements.txt:8 | 0.109 较旧（当前 0.115+），可升至最新 0.11x；Pydantic v2 已适配 | API 层核心 |
| uvicorn[standard] | `>=0.27.0` | requirements.txt:9 | 可升至 0.30+ | ASGI server |
| pydantic | `>=2.5.0` | requirements.txt:14 | 已 v2， crawl.py 用 `ConfigDict`/`Field(..., pattern=)` 为 v2 写法 | 入参校验 |
| pydantic-settings | `>=2.1.0` | requirements.txt:15 | OK | config 加载 |
| httpx | `>=0.26.0` | requirements.txt:11 | 可升至 0.27+ | AI/回调 client（本模块间接） |
| crawl4ai | `~=0.8.6` | requirements.txt:6 | 0.8.x 系列内约束，兼容性限制 | 本模块通过 crawler.* 间接依赖 |

> 排查范围：仅 C01 直接/间接用到的依赖。crawl4ai/httpx 内部行为（重定向默认 follow、scheme 校验）标 `[需查证]`（§1.3.1 不翻源码）。

### [P3] [Deps] fastapi `>=0.109.0` 下限偏低，未锁上限  <!-- 编号：C01-14 -->
- **定位**：`crawler-service/requirements.txt:8` `fastapi>=0.109.0`
- **现象**：下限 0.109（2024-01 发布），未锁上限。当前 FastAPI 已至 0.11x，Starlette 中间件执行语义、`RequestValidationError` 行为在版本间有微调。
- **影响**：`pip install` 拉到新版本时，中间件顺序（C01-12）、异常处理器签名理论上有兼容风险（实际 FastAPI 在 0.10x-0.11x 保持稳定，风险低）。
- **根因/分析**：未 pin 上限是常见取舍，便于安全补丁；但缺乏上限测试矩阵。
- **修复方向**：可选锁到 `fastapi>=0.115,<0.120` 或引入 lock 文件。改动面：小。
- **关联**：次维度 [Deps]；X06 配置一致性（lock 策略）。

---

## `[Design]` 功能设计合理性

> 回答 §2.5 中相关问题（至少 2 个）。

**审视结论**：

1. **场景适配（§2.5-1）**：crawler-service 定位为"被 ≤2 内部服务调用的采集服务"（CLAUDE.md），C01 的 5 个即时端点 + `/health` 对该场景**适配合理**——即时爬取供 backend 手动触发、`/organize`/`/keyword` 供 backend AI 链路调用、`/health` 供探活。无过度设计（无公开文档页、无多租户），也无关键缺失。但 `/crawl/*` 即时接口与 `/api/v1/tasks` 异步任务（C02/C03）两套入口的边界未在 API 层文档化，调用方可能混淆"何时用即时、何时用任务"。

2. **闭环完整性（§2.5-2）**：`/organize` 和 `/keyword` 是同步阻塞 AI 调用，单次 `/organize` 可能耗时数十秒（AI 整理 + 重试），**无客户端超时协商/无服务端硬超时**。对"backend 调用方 httpx 设 5s 超时（`callback_timeout=5.0`，config.py:38）"的场景，长 AI 任务必然超时但 crawler 侧仍在跑，形成"客户端已放弃、服务端继续烧 token"的半孤儿。这是即时 AI 端点的设计断层——应改为异步任务或显式声明长超时契约。

3. **可运维性（§2.5-3）**：`/health` 把探活和诊断混在一个端点（C01-05），故障定位时无法快速判断"是 Crawl4AI 挂了还是 AI 挂了还是 DB 满了"而不暴露内部信息——分层缺失。AccessLog 不记关键业务标识（C01-03）也削弱排障。

### [P4] [Design] 即时 AI 端点（/organize、/keyword）无超时契约，与调用方超时不匹配  <!-- 编号：C01-15 -->
- **定位**：`crawler-service/api/crawl.py:203-264`（/organize 重试循环）+ `config.py:38`（`callback_timeout=5.0`）
- **现象**：`/organize` 同步等待 AI 整理 + 重试（`ai_max_retries` 次），单次可能 30s+；而 backend 调用方默认 5s 超时。
- **影响**：backend 调 `/organize` 5s 后断开，crawler 仍跑完 AI 烧 token，结果丢弃；形成资源浪费与"明明调了但拿不到结果"的迷惑体验。
- **建议方向**：①改为异步任务（POST 返回 task_id，GET 轮询结果，复用 C02 任务体系）；或②文档显式声明 `/organize` 最长耗时 + backend 调用方放大超时。改动面：中（异步化）。
- **关联**：次维度 [Design]（闭环）；横向主题"跨服务契约"（超时契约）；B10 `CrawlerTaskClient` 调用方视角。

### [P4] [Design] /crawl/* 即时接口与 /api/v1/tasks 异步任务的边界未文档化  <!-- 编号：C01-16 -->
- **定位**：`crawler-service/api/crawl.py:93-178`（即时）vs `crawler-service/standalone/routes.py`（C02 异步任务）
- **现象**：两套爬取入口共存，调用方需自行判断何时用即时（轻量、阻塞）、何时用任务（重量、异步、可轮询）。无 API 层指引。
- **影响**：调用方误用（如 backend 误用即时接口做大批量爬取阻塞 crawler 主循环）。
- **建议方向**：crawler README 补"调用决策树"——单页/快速用 /crawl/single，多页/需结果聚合用 /api/v1/tasks。改动面：小（文档）。
- **关联**：次维度 [Design]（交互合理性）；X05 文档一致性。

---

## 模块小结

### 严重度统计

| 级别 | 数量 | 条目编号 |
|---|---|---|
| P0 | 0 | — |
| P1 | 2 | C01-04、C01-05 |
| P2 | 5 | C01-01、C01-02、C01-06、C01-07、C01-08、C01-11、C01-12 |
| P3 | 4 | C01-03、C01-09、C01-10、C01-13、C01-14 |
| P4 | 2 | C01-15、C01-16 |

> 校对：P2 实际为 7 条（C01-01、C01-02、C01-06、C01-07、C01-08、C01-11、C01-12）。合计 15 条。

### Top 风险（本模块最该先看的 3 条）

1. **C01-04 SSRF 不覆盖重定向/BFS 子链接** —— 应用层校验被浏览器/httpx `follow_redirects=True` 绕过，redirect-to-internal 是更易利用路径，且文档未提示。需网络层（X01）+ 应用层双补。
2. **C01-05 /health 泄漏内部状态** —— DB 绝对路径、AI 模型、调度器状态、活跃任务数对任意调用方暴露（若 health 免鉴权则为 P1）。
3. **C01-11 AppError 错误码体系形同虚设** —— 5 个即时端点全用 HTTPException，8 个结构化错误码未被采用，跨服务错误契约（B09）失去抓手。

### 修复优先级建议

- **立即（P1）**：C01-04（SSRF 重定向，应用层二次校验部分）、C01-05（health 分层 + 脱敏）。
- **计划（P2）**：C01-01/06（异常信息脱敏口径统一）、C01-02（result None 兜底）、C01-07（RequestID 格式校验）、C01-08（CORS 文档声明）、C01-11（AppError 采用回填）、C01-12（中间件顺序复核）。
- **择机（P3/P4）**：C01-03/09/10/13/14（日志增强、scheme 白名单、fail-closed、版本统一、依赖 pin）、C01-15/16（AI 端点超时契约、入口决策树文档）。

### 排查盲区 / 待复核

- **C01-04**：Crawl4AI 0.8.6 / Playwright 浏览器是否对最终落地 URL 提供 hook 供应用层二次校验 `[需查证]`（依赖源码不翻，§1.3.1）；uvicorn 前置 nginx 是否已做 egress 过滤 `[需查证]`（归 X01）。
- **C01-05**：`/health` 是否在 `ApiKeyMiddleware` 保护前缀内 `[需查证]`（C02 主模块，影响定级——若免鉴权则 C01-05 风险升高）。
- **C01-07**：uvicorn/Starlette 是否对响应头值做换行过滤（防 header 注入）`[需查证]`。
- **C01-10**：Crawl4AI 0.8.6 是否拒绝 `file://`/`gopher://` scheme `[需查证]`。
- **C01-12**：`ApiKeyMiddleware` reject 路径是否读取 `request.state.request_id`（C02 主模块）。
- **C01-02**：`ai_settings.ai_max_retries` 默认值与是否允许 0 `[需查证]`（`ai/config.py`，未通读）。
