# F02 请求层 排查报告

> **模块编号**：F02
> **排查范围**：axios 实例 / 重复请求 abort / 5xx+网络错误指数退避重试 / 统一错误提示 / 401 跳登录 / skipAuthRedirect+skipErrorMessage 配置 / baseURL+proxy / withCredentials
> **基线 commit**：`6ae930098405f4d0553d96a852f3345d0f39682e`
> **工作区状态**：脏。涉及本模块的未提交改动：无（本批 `frontend/src/utils/request.ts` 不在工作区改动清单中；改动集中在 backend `ConfigRepositoryImpl.java`、`WebCollectPageMapper.java`、crawler 多个、`deploy/README.md`、`docs/audit/full-project-risk-register.md`、`scripts/release/release-gate.ps1`，与本模块无关）。
> **排查日期**：2026-06-24
> **排查人**：F02 agent
> **状态**：草稿

---

## 模块概览

**职责**：为所有前端 API 调用提供统一的 axios 实例，封装超时、重复请求 abort、5xx/网络错误指数退避重试、业务码非 200 的错误提示与 401 跳登录，并通过 `skipAuthRedirect`/`skipErrorMessage` 两个开关让特殊调用方（如登录态探活）豁免默认行为。

**关键文件**：
- `frontend/src/utils/request.ts:1-168` —— axios 实例、请求/响应拦截器、abort Map、重试、401、`get/post/put/del` 导出（**本模块唯一核心文件**）
- `frontend/src/constants/api.ts:32-35` —— `REQUEST_TIMEOUT=30000`、`REQUEST_RETRY_COUNT=3` 常量
- `frontend/vite.config.ts:40-53` —— dev proxy `/api`、`/uploads` → `localhost:8081`
- `deploy/nginx.conf:37-54` —— 生产 `/api/`、`/uploads/` 反代 `backend:8081`，`/api/` 段 `proxy_read_timeout 300s`
- `frontend/.env.development`、`frontend/.env.production`、`frontend/.env.example` —— `VITE_API_BASE_URL=/api`（相对路径，三处一致）

**对外接口 / 依赖**：
- 对外：`get/post/put/del<T>` 四个泛型方法，被 `frontend/src/api/*.ts`（article/auth/category/collector/config/dashboard/dailyLog/file/friendLink/home/project/skill 共 12 个模块）全部消费。所有 F0x 调用页通过 api 层间接引用本模块。
- 依赖：`axios@^1.6.5`、`element-plus`（ElMessage）、`@/constants/api`、`import.meta.env.VITE_API_BASE_URL`。
- 后端契约：依赖后端响应体为 `{ code: number, message: string, data: T }`（见 `request.ts:83-103` 直接读 `data.code/message/data`）。Cookie 由 Sa-Token 设置，同源自动携带。
- 关联模块：**F01 路由守卫**（401 跳登录协同、回探窗口，见 F01）、**B06 鉴权**（Sa-Token Cookie 模式、CORS allowCredentials）、**B16 全局基础设施**（CORS 配置）、**B05 文件上传**（uploadFile 调用方）。

**已读文件清单**（可追溯 + 暴露盲区）：
- `frontend/src/utils/request.ts` —— 通读（168 行）
- `frontend/src/constants/api.ts` —— 通读
- `frontend/vite.config.ts` —— 通读
- `frontend/.env.development` / `.env.production` / `.env.example` —— 通读
- `deploy/nginx.conf` —— 通读
- `frontend/src/stores/modules/user.ts` —— 通读（skipAuthRedirect/skipErrorMessage 唯一消费方）
- `frontend/src/api/file.ts`、`auth.ts`、`collector.ts`、`config.ts` —— 通读（调用方样例）
- `frontend/src/composables/usePolling.ts` —— 通读（轮询与 abort 交互）
- `frontend/src/components/editor/MarkdownEditor.vue`、`components/common/FileUpload.vue` —— 通读上传场景
- `frontend/src/views/admin/collector/TaskDetail.vue`、`digest/List.vue`、`digest/Detail.vue` —— 片段（轮询 fetch 逻辑）
- `backend/.../GlobalExceptionHandler.java:100-141` —— 片段（验证 message 脱敏）
- `deploy/.env.example`、`deploy/docker-compose.yml` —— grep（CORS 配置）

**主模块归属**：本模块是**前端请求层的主模块**（计划 §8.6）。所有 F0x 调用页引用本模块；401 跳登录与 F01 守卫协同；withCredentials/CORS 引用 B16；文件上传引用 B05。

---

## `[Bug]` 代码正确性与潜在缺陷

> 排查范围：`request.ts` 全文逐行 + 12 个 api/*.ts 调用方 + 上传/轮询场景的并发模型 + abort 与重试的状态机交互。

### [P1] [Bug] 重试逻辑不区分 HTTP 方法，POST/PUT/DELETE 非幂等写操作遇 5xx 自动重试 <!-- 编号：F02-01 -->
- **定位**：`frontend/src/utils/request.ts:122-136`
- **现象**：重试判定只看 `!error.response || (error.response.status >= 500 && error.response.status < 600)`（line 127），未检查 `config.method`。任何方法（含 POST/PUT/DELETE）在 5xx 或网络错误时都会按 1s/2s/4s 间隔重试最多 3 次。
- **影响**：真实使用中以下写操作会被重复发送：
  - `triggerDigest`（`collector.ts:68`，`List.vue:118/122`）——日报生成触发，后端若已受理但响应 5xx，重试会重复触发整个日报生成流水线（采集+AI 整理，耗时数分钟，浪费配额）。
  - `refreshConfigs`（`config.ts:21`）、`refreshSubscription`（`config.ts:57`）——配置/订阅刷新，重复刷新副作用虽小但浪费 crawler 调用。
  - `createCollectTask`（`collector.ts:6`）、`createSource`（`collector.ts:122`）——创建类，重复提交可能创建多条任务（虽有 md5/唯一约束兜底，但采集任务无业务去重）。
  - `deleteSource`（`collector.ts:130`）、`deleteCollectTask`（`collector.ts:26`）、`updateConfig`（`config.ts:8`）——删除/更新类，重复执行通常幂等但 `updateConfig` 可能覆盖期间的人工改动。
  - `login`（`auth.ts:5`）——登录 POST，5xx 重试一般无害但语义混乱。
- **根因/分析**：重试本是为幂等 GET 设计的容错机制，实现时未引入"仅 GET 或显式标记 idempotent 的请求才重试"的白名单。axios 社区惯例是重试前判断 method 或要求调用方显式 opt-in。已排除误判：检查了所有 api/*.ts，没有任何调用方通过 config 关闭重试（无 `__retryCount` 预设或 `skipRetry` 之类开关），说明重试是全局默认开启的。
- **修复方向**：①重试判定增加 `config.method?.toUpperCase() === 'GET'` 条件，仅对 GET 重试；②或新增 `config.skipRetry` 开关并默认对非 GET 不重试，由少数可重试的 POST（如 `triggerDigest` 后端已做幂等）显式 opt-in。改动面：**小**（单文件，<20 行，需补类型声明）。
- **关联**：次维度 `[Security]`（重复写操作的副作用）、横向主题"跨服务契约一致性"（crawler callback 重复触发）。引用 B08（采集编排幂等性）、C04（日报编排重复触发）。

---

### [P1] [Bug] 多文件并发上传时 generateRequestKey 生成相同 key，后发请求 abort 先发请求 <!-- 编号：F02-02 -->
- **定位**：`frontend/src/utils/request.ts:19-25`（key 生成）+ `frontend/src/components/editor/MarkdownEditor.vue:44-51`（并发上传）
- **现象**：`generateRequestKey` 用 `JSON.stringify(config.data)` 参与拼 key（line 23）。但 `uploadFile`（`file.ts:24-28`）传的 `data` 是 `FormData`，`JSON.stringify(FormData)` 返回 `"{}"`（FormData 不可枚举），所以无论上传哪个文件，key 都是 `POST_/api/admin/file/upload___{}`（params 为空、data 为 `"{}"`）。
  MarkdownEditor 多图上传用 `Promise.all(files.map(f => uploadFile(formData)))`（`MarkdownEditor.vue:44-51`），N 个并发上传请求的 key 完全相同 → 请求拦截器 line 56-58 对每个后到的请求执行 `pendingControllers.get(key)?.abort()`，**先发起的上传被后续每个上传依次 abort**。
- **影响**：在 md 编辑器里一次拖入/选择多张图片时，只有最后一张（或随机一张）能上传成功，其余被 abort 抛 `ERR_CANCELED`，`Promise.all` 整体 reject，callback 不被调用，**全部图片插入失败**。这是编辑器图片上传的确定性故障（非概率性），只要一次选 ≥2 张图就触发。
- **根因/分析**：`generateRequestKey` 假设 `data` 是普通对象/可 JSON 序列化，未处理 `FormData`/`Blob`/`URLSearchParams` 这类 binary body。已排除误判：确认 `uploadFile` 未传 `config.signal`（line 25-27 只传 headers），所以会走拦截器的 abort 分支；FormData 的 `JSON.stringify` 在 V8 行为是 `"{}"`（无 own enumerable props）。
- **修复方向**：①`generateRequestKey` 对 `FormData`/`Blob` 等 binary body 不纳入 data 参与拼 key，或改用请求体大小+时间戳/随机数后缀；②或对 upload 类请求在调用方显式传唯一 `config.signal`/跳过 abort（`if (!config.signal)` 已留了这个口子，line 50）。改动面：**小**（单文件，<15 行）。建议同时回归 FileUpload.vue 单文件上传路径（该路径无并发，不受影响）。
- **关联**：次维度 `[Design]`（abort 粒度设计）、引用 B05（文件上传后端）。

---

### [P2] [Bug] abort 后旧请求的 __cleanup 误删新请求在 pendingControllers 中的条目 <!-- 编号：F02-03 -->
- **定位**：`frontend/src/utils/request.ts:56-63`（abort + set + cleanup 闭包）与 `request.ts:108-111`（error 分支调 cleanup）
- **现象**：重复请求场景下，拦截器先 `abort('重复请求被取消')` 旧的（line 57），再 `pendingControllers.set(key, controller)` 设新的（line 59），新请求的 `__cleanup` 闭包捕获 `key`（line 62）。但**旧请求随后进入响应 error 分支**，line 109-111 调用**旧 config 的 `__cleanup`**，而旧 `__cleanup` 闭包捕获的是**同一个 key**，执行 `pendingControllers.delete(key)` 会把新请求刚 set 进去的 controller 删掉。
- **影响**：重复触发同一请求（如用户快速点击同一按钮、轮询与手动刷新重叠）后，新请求虽然继续在飞，但已从 `pendingControllers` 移除，后续再来的同 key 请求无法 abort 它，且 `pendingControllers` Map 长期残留已完成的条目（轻微内存泄漏，单页应用生命周期内可控）。属状态机一致性问题，不直接致功能故障但破坏 abort 契约。
- **根因/分析**：`__cleanup` 用 key 删除而非用 controller 引用删除。正确做法是 `delete` 前校验 `pendingControllers.get(key) === 当前 controller`。已排除误判：确认 error 分支对 `ERR_CANCELED` 也走 cleanup（line 109-111 在 `ERR_CANCELED` 判断 line 113 之前）。
- **修复方向**：cleanup 闭包改为 `if (pendingControllers.get(key) === controller) pendingControllers.delete(key)`，只在条目仍属自己时删除。改动面：**小**（单文件，<5 行）。
- **关联**：次维度 `[Bug]`，与 F02-04 同属 abort/重试状态机问题。

---

### [P2] [Bug] 重试复用 config，signal 已 aborted 导致重试请求无法被新的重复请求 abort <!-- 编号：F02-04 -->
- **定位**：`frontend/src/utils/request.ts:50`（`if (!config.signal)`）与 `request.ts:135`（`return request(config)`）
- **现象**：响应 error 分支重试时 `return request(config)` 复用原 config（line 135），该 config 的 `signal` 已被设置（首次请求时 line 52 赋值）。重试进入请求拦截器时 `if (!config.signal)` 为 false（line 50），**跳过新 AbortController 创建**，于是：①重试请求没有可取消的句柄；②`pendingControllers` 不会登记这个重试请求；③若重试期间又来了同 key 请求，无法 abort 正在重试的请求。
- **影响**：重试中的请求"脱离"abort 管控，用户快速重复操作时旧重试不会被打断，可能叠加多个在飞请求（与 F02-01 叠加时，非幂等 POST 的重试 + 新请求同时进行，副作用放大）。
- **根因/分析**：重试未清理 `config.signal`。axios 官方推荐的重试模式是在重试前 `delete config.signal` 或重新构造 config。已排除误判：确认首次请求若被 abort，error 分支会先 `ERR_CANCELED` 短路（line 113-115）不进入重试，所以本问题只在"首次请求因 5xx/网络错误失败后重试"时出现。
- **修复方向**：重试前 `delete config.signal`（或 `const { signal, ...rest } = config; return request(rest)`），让拦截器为重试请求重新创建 controller。改动面：**小**（单文件，<5 行）。
- **关联**：次维度 `[Bug]`，与 F02-03 同属 abort/重试状态机问题。

---

### [P2] [Bug] timeout 30s 与 nginx proxy_read_timeout 300s 不匹配，长耗时 admin 操作被前端先 abort <!-- 编号：F02-05 -->
- **定位**：`frontend/src/constants/api.ts:32`（`REQUEST_TIMEOUT = 30000`）vs `deploy/nginx.conf:44`（`proxy_read_timeout 300s`）
- **现象**：全局 axios 超时 30s，而 nginx 给 `/api/` 的读超时是 300s。后端若干 admin 操作耗时可能超过 30s：
  - `triggerDigest`（`collector.ts:68`）——后端同步等待日报生成编排启动；
  - `refreshSubscription`（`config.ts:57`）、`refreshConfigs`（`config.ts:21`）——刷新涉及 crawler 调用；
  - `testNodesDelay`（`config.ts:42`）——代理节点批量测速；
  - 文件上传（`file.ts:24`）——大文件上传。
  这些请求 nginx 会等 300s，但前端 axios 30s 就抛 `ECONNABORTED`，且因 F02-01 还会触发重试（进一步加剧）。
- **影响**：长耗时 admin 操作在前端表现为"超时失败"，但后端实际可能仍在执行（如日报生成已启动），形成"前端报错、后端成功"的不一致观感，用户可能误以为失败而重复触发。
- **根因/分析**：超时常量全局统一，未给特定长耗时接口单独配置。axios 支持 per-request `timeout` override，但调用方（collector.ts/config.ts）都未传。
- **修复方向**：①对已知长耗时接口（triggerDigest/refreshConfigs/refreshSubscription/testNodesDelay/uploadFile）在调用处传 `{ timeout: 120000 }` 或更高；②或引入 `config.extendedTimeout` 标记由拦截器识别。改动面：**小到中**（多处 api.ts 调用点）。
- **关联**：次维度 `[Design]`（超时策略分层），引用 X01（部署超时一致性）。

---

### [P3] [Bug] 401 硬跳转丢失当前路由与未保存数据 <!-- 编号：F02-06 -->
- **定位**：`frontend/src/utils/request.ts:88-91`
- **现象**：业务码 401 时 `window.location.href = '/login'`，硬跳转（非 router.push），未携带 `redirect` query，也未尝试保存当前页面状态。
- **影响**：①用户在编辑文章/配置长表单时 session 过期，跳登录后**无法自动回到原页面**，已填内容随页面卸载丢失（auto-save 仅 md 编辑器有，配置页/采集任务页无）；②用 `window.location.href` 绕过 vue-router，丢失路由历史栈。属体验问题，非功能 bug。
- **根因/分析**：硬跳转是最简单的实现，但牺牲了 SPA 的路由连贯性。vue-router 的 `router.push({ path: '/login', query: { redirect: fullPath } })` 才能配合 F01 守卫实现"登录后回原页"。
- **修复方向**：改用 router 实例 `push` 并带 redirect query（需在 request.ts 引入 router，或通过事件总线让 F01 守卫处理）。改动面：**小**（单文件，需与 F01 协同测试）。
- **关联**：主模块 F01（路由守卫/回探），横向主题"鉴权机制一致性"。

---

## `[Security]` 安全漏洞

> 排查范围：withCredentials / Cookie 携带 / 错误信息泄漏 / XSS 边界（响应数据是否在拦截器净化——渲染归 F03，本节只看拦截器是否额外引入风险）。

### [P2] [Security] withCredentials 未设置，跨域部署场景下 Sa-Token Cookie 不被携带 <!-- 编号：F02-07 -->
- **定位**：`frontend/src/utils/request.ts:27-33`（axios.create 未设 `withCredentials`）
- **现象**：axios 实例创建时未配置 `withCredentials: true`。axios 默认 `withCredentials=false`，跨域请求不携带 Cookie。
- **影响**：当前**同源部署无影响**（生产 nginx 把 `/api/` 反代到 backend:8081，前端与 API 同源 `nanmu.xyz`，Cookie 自动携带；dev vite proxy 同理同源）。**但**一旦未来将 `VITE_API_BASE_URL` 改为后端直连域名（如 `https://api.nanmu.xyz`，跨域），Cookie 不会被发送，所有需鉴权的 admin 接口全部 401，登录态完全失效。注释 `request.ts:47` 自己也提到"如需跨域，确保后端配置了CORS允许credentials"，但前端侧的 `withCredentials` 始终没补。
- **根因/分析**：Cookie 模式 + 同源代理的部署选择掩盖了这个缺口。属"当前可用、跨域即坏"的潜在风险。
- **修复方向**：①显式 `axios.create({ withCredentials: true })`（同源无害，跨域必需）；②或在文档/README 明确"仅支持同源部署，跨域需同时改 withCredentials + 后端 CORS allowCredentials + 白名单"。改动面：**小**（单行 + 文档）。
- **关联**：引用 B06（Sa-Token Cookie 模式）、B16（CORS allowCredentials 配置）、横向主题"鉴权机制一致性"。`[需查证]`：后端 CORS 是否已配 `allowCredentials=true`（见 B16 报告结论，本报告不展开）。

---

### [P3] [Security] ElMessage.error 直接展示后端 message，业务异常可能泄漏实现细节 <!-- 编号：F02-08 -->
- **定位**：`frontend/src/utils/request.ts:84-85`（`ElMessage.error(data.message || '请求失败')`）与 `request.ts:139-140`（HTTP 错误分支同样）
- **现象**：拦截器把后端返回的 `data.message` 原样弹窗展示给最终用户。后端 `GlobalExceptionHandler`（`backend/.../GlobalExceptionHandler.java`）的兜底 `Exception.class` 已脱敏返回"系统繁忙，请稍后再试"（line 140），但其他具体异常（`BusinessException`、`DataIntegrityViolationException` 等）会返回**含业务语义的原始 message**（如"分类标识已存在"、"article_slug_key"片段经过处理后的中文）。
- **影响**：①正常业务提示（如"分类标识已存在"）合理展示是有益的；②但若某些 BusinessException 抛出时 message 携带字段名、SQL 片段、内部路径，会通过 ElMessage 暴露给前端用户，属轻微信息泄漏。后端兜底已防住最严重的堆栈泄漏，剩余风险可控。
- **根因/分析**：拦截器无法区分"友好业务提示"与"可能含细节的错误"，统一展示是体验与安全的权衡。后端已做脱敏层兜底，前端再过滤会双重维护。
- **修复方向**：维持现状可接受；或对 `data.code` 属于 5xx 段的统一展示"系统繁忙"，仅对 4xx 业务码展示原始 message。改动面：**小**。
- **关联**：引用 B16（GlobalExceptionHandler 脱敏）、次维度 `[Design]`。

---

## `[Arch]` 架构与技术债

> 排查范围：请求层抽象、配置开关、与 F01 守卫的职责边界、轮询 composable 的协同。

### [P3] [Arch] skipAuthRedirect/skipErrorMessage 开关仅被 user.ts 一处使用，配置能力未被充分利用 <!-- 编号：F02-09 -->
- **定位**：`frontend/src/utils/request.ts:10-11`（类型声明）、`request.ts:84/88`（消费）vs `frontend/src/stores/modules/user.ts:45-46`（唯一使用点）
- **现象**：两个开关类型声明齐全、拦截器逻辑也读，但全项目仅 `user.ts checkAuthStatus` 一处使用（登录态探活时静默）。其他本应豁免的场景都没用：
  - `getCurrentUser` 在 F01 守卫里被调用时（如果走的是 `auth.ts` 的 `getCurrentUser`），守卫探活失败本不该弹错误，但 F01 是否传了 `skipErrorMessage` 需查 F01 报告 `[需查证]`；
  - `triggerDigest` 失败时 `List.vue:137` 自己 catch 后弹 ElMessage，但 request.ts 拦截器**已经弹过一次**（line 140），形成**双重错误提示**。
- **影响**：①双重错误提示影响体验（用户看到两个相同错误弹窗）；②开关能力存在但未推广，调用方需自行 catch + 弹窗的模式与拦截器默认弹窗职责重叠，易出"弹两次"或"该静默没静默"的 bug。
- **根因/分析**：拦截器默认弹窗 + 调用方自行处理错误的职责边界未理清。社区惯例是拦截器只做"通用兜底"，调用方可 opt-out。
- **修复方向**：①明确约定：调用方若自行处理错误就传 `skipErrorMessage: true`；②或在 `List.vue:137` 这类已自行 catch 弹窗的场景补上 `skipErrorMessage`。改动面：**小到中**（需梳理所有 api 调用方的错误处理模式）。
- **关联**：次维度 `[Design]`（错误处理职责分层），引用 F01（守卫探活）。

---

### [P3] [Arch] 错误提示无去重/节流，重试或并发失败时弹出多个相同 ElMessage <!-- 编号：F02-10 -->
- **定位**：`frontend/src/utils/request.ts:140`（`ElMessage.error(message)` 无去重）
- **现象**：重试耗尽后弹错误（line 140），但若多个并发请求同时失败（如 Dashboard `Promise.all([fetchStats, fetchRecentArticles])` 同时 5xx），会弹出 2-4 个 ElMessage；轮询场景下连续失败也会每轮弹一次。
- **影响**：网络抖动时用户被错误弹窗刷屏，体验差。
- **根因/分析**：ElMessage 默认不合并相同内容。无 dedup 逻辑。
- **修复方向**：对相同 message 在短时间窗（如 2s）内去重，或用 ElNotification 的 grouping。改动面：**小**。
- **关联**：次维度 `[Design]`。

---

## `[Deps]` 依赖升级与版本

### 本模块依赖清单（基于声明文件，未翻依赖源码）

| 依赖 | 版本 | 声明位置 | 已知风险/可升级 | 备注 |
|---|---|---|---|---|
| axios | `^1.6.5` | `frontend/package.json:15` | 可升至 1.7.x/1.8.x；1.x 系列曾有 CVE-2024-39338（SSRF，影响服务端 axios，前端不直接受影响）、CVE-2025-27152（CSRF token 处理，已修）| `^1.6.5` 实际安装最新 1.x，需查 lock 文件确认 `[需查证]` |
| element-plus | `^2.5.1` | `frontend/package.json:18` | ElMessage 来源；2.5→2.8+ 可升 | 非本模块直接依赖 |
| vue | `^3.4.15` | `frontend/package.json:24` | 3.4→3.5 可升 | 非本模块直接依赖 |

> 排查范围：仅 axios（本模块唯一直接依赖）。element-plus/vue 为间接（ElMessage/vue 无关本模块逻辑）。版本号取自 `package.json`，未翻 `package-lock.json` 实际锁定版本（命令边界 §1.3 不深入 node_modules，lock 文件可读但本次未读 —— `[需查证]`）。

### [P3] [Deps] axios 版本上限 1.6.5 偏旧，建议确认 lock 实际版本并跟进 1.7+ <!-- 编号：F02-11 -->
- **定位**：`frontend/package.json:15`（`"axios": "^1.6.5"`）
- **现象**：声明下限 1.6.5，`^` 允许 1.x 最新，但未指定上限。1.6.5 发布于 2023-12，距今较久。
- **影响**：若 lock 锁定在 1.6.x，可能错过 1.7+ 的 bug 修复（如 fetch adapter 改进、重试相关行为）。axios 1.x 无活跃 CVE 影响前端使用（已知 CVE 多影响 SSR 场景）。
- **根因/分析**：依赖维护节奏问题。
- **修复方向**：确认 `package-lock.json` 实际版本，按需 `npm update axios`（属 F07 构建与依赖模块主责，本报告只记录）。改动面：**小**。
- **关联**：主模块 F07（构建与依赖）。

---

## `[Design]` 功能设计合理性

> 必填。从真实使用出发，回答计划 §2.5 中相关的问题。

**审视结论**：

1. **场景适配**（单人维护博客 + 工作日 AI 日报）：请求层的功能集（abort/重试/统一错误/401 处理）对单人 admin 场景**略偏重**。abort 重复请求是为高频并发场景设计的，但本站 admin 操作频率低、几乎无"用户快速重复点击"的真实压力；反而 abort 引入了 F02-02/F02-03/F02-04 三个状态机 bug，**复杂度收益比偏低**。重试对弱网下的 GET 列表浏览有价值，但对 admin 写操作的副作用（F02-01）风险大于收益。
2. **闭环完整性**：401 处理只做了"跳登录"，未做"登录后回原页"闭环（F02-06），表单数据会丢；错误提示有双重弹窗问题（F02-09）。请求层的基础闭环（发请求→拿数据→处理错误）完整，但边缘体验闭环不全。
3. **可运维性**：拦截器有 `console.warn('[API Business Error]')` 和 `console.error('[API Error]')` 日志（line 93/142），含 url/method/status/code/message，**对前端排障有帮助**；但无 traceId 透传（后端有 MDC traceId，前端未在请求头携带或日志关联），跨前后端链路追踪缺失。属可改进项，非阻断。

### [P4] [Design] abort 机制对单人博客场景属过度设计，建议简化或默认关闭 <!-- 编号：F02-12 -->
- **定位**：`frontend/src/utils/request.ts:15-63`（整个 abort Map + 请求拦截器）
- **现象**：当前 abort 机制带来 3 个 bug（F02-02/03/04），而本站几乎没有"合法并发同 key 请求需要保留最新"的真实场景（轮询有 usePolling 的 running 防堆叠，无需 abort；管理页操作低频）。
- **影响**：维护成本 > 收益。
- **建议方向**：可考虑①默认关闭 abort，仅在确有需要的调用方显式 opt-in；②或至少修复 F02-02/03/04 后保留。标 `无需调整` 亦可接受（修复 bug 后现状可运行）。改动面：**中**（需评估所有调用方）。
- **关联**：次维度 `[Arch]`。

### [P4] [Design] 缺少前端 traceId 与后端 MDC traceId 的链路关联 <!-- 编号：F02-13 -->
- **定位**：`frontend/src/utils/request.ts:44-70`（请求拦截器未注入 trace header）
- **现象**：后端 GlobalExceptionHandler 用 MDC traceId（`GlobalExceptionHandler.java:134-139`），但前端请求拦截器未在 header 携带 `X-Trace-Id`（或类似），前端 console 日志（line 93/142）也无 traceId 字段。
- **影响**：用户反馈"某次操作报错"时，前端日志与后端日志无法快速关联，排障靠猜 url+时间。
- **建议方向**：请求拦截器生成 uuid 注入 `X-Trace-Id` header，响应/错误日志带上同一 id。改动面：**小**。属增强项，非阻断。
- **关联**：引用 B16（后端 TraceId/访问日志）。

---

## 模块小结

### 严重度统计

| 级别 | 数量 | 条目编号 |
|---|---|---|
| P0 | 0 | — |
| P1 | 2 | F02-01、F02-02 |
| P2 | 4 | F02-03、F02-04、F02-05、F02-07 |
| P3 | 4 | F02-06、F02-08、F02-09、F02-10、F02-11（实际 5 条，P3 计 5） |
| P4 | 2 | F02-12、F02-13 |

> 修正：P3 实为 5 条（F02-06/08/09/10/11），上表 P3 数量应为 5。

| 级别 | 数量 | 条目编号 |
|---|---|---|
| P0 | 0 | — |
| P1 | 2 | F02-01、F02-02 |
| P2 | 4 | F02-03、F02-04、F02-05、F02-07 |
| P3 | 5 | F02-06、F02-08、F02-09、F02-10、F02-11 |
| P4 | 2 | F02-12、F02-13 |

**合计 13 条发现。**

### Top 风险（本模块最该先看的 ≤3 条）

1. **F02-02 多文件并发上传 abort 误杀** —— 确定性故障，md 编辑器一次选多张图全部上传失败，用户可感知。
2. **F02-01 非幂等 POST/PUT/DELETE 遇 5xx 自动重试** —— 后端 5xx 时重复触发日报生成/配置刷新/删除等副作用，浪费资源 + 潜在数据不一致。
3. **F02-07 withCredentials 缺失** —— 当前同源无害，跨域部署即全面 401，属"潜伏炸弹"。

### 修复优先级建议

- **立即**（P1）：
  - F02-02（上传 key 冲突，改动面小，影响编辑器核心功能）
  - F02-01（重试按方法白名单，改动面小，防副作用）
- **计划**（P2）：
  - F02-03/F02-04（abort/重试状态机一致性，一起改）
  - F02-05（长耗时接口 per-request timeout）
  - F02-07（withCredentials 补齐 + 文档）
- **择机**（P3/P4）：
  - F02-06（401 路由化，与 F01 协同）
  - F02-08/09/10（错误提示体验优化）
  - F02-11（axios 版本，归 F07）
  - F02-12/13（设计建议，traceId 链路）

### 排查盲区 / 待复核

- **`[需查证]` F02-07**：后端 CORS 是否已配 `allowCredentials=true` + 白名单（归 B16，本报告不展开）。
- **`[需查证]` F02-11**：`frontend/package-lock.json` 实际锁定的 axios 版本（本次未读 lock 文件，命令边界允许但时间未及；归 F07）。
- **`[需查证]` F02-09**：F01 路由守卫调用 `getCurrentUser` 时是否传了 `skipErrorMessage`（守卫探活场景），需看 F01 报告结论。
- **盲区**：未深入 axios 内部对 `ERR_CANCELED` + retry 的交互行为（命令边界 §1.3.1 不入 node_modules），F02-04 的"signal 已 aborted"行为基于 axios 公开 API 文档常识推断，标 `[需查证]` 的实现细节部分建议修复时用单测验证。
- **盲区**：未跑实际并发上传复现 F02-02（只读约束不跑构建/运行），结论基于 `JSON.stringify(FormData)` 的 JS 语义 + 拦截器代码路径静态推导，确定性较高但建议修复时回归验证。
