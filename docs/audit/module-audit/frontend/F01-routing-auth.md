# F01 路由与鉴权守卫 排查报告

> **模块编号**：F01
> **排查范围**：前端路由表（公开/管理）、路由守卫、Sa-Token Cookie 模式前端侧、Pinia user store（isAuthenticated 持久化 + 跨 Tab storage 同步）、首次导航回探窗口、Login 流程与 redirect 回跳。
> **基线 commit**：`6ae930098405f4d0553d96a852f3345d0f39682e`
> **工作区状态**：脏（未提交改动集中在 `backend/.../ConfigRepositoryImpl.java`、`WebCollectPageMapper.java`、`crawler-service/*`、`deploy/README.md`、`docs/audit/full-project-risk-register.md`、`scripts/release/release-gate.ps1`、新增 `backend/src/test/.../webcollector/`），**均不涉及 F01 前端模块**，对本报告无影响）。
> **排查日期**：2026-06-24
> **排查人**：F01 agent
> **状态**：待复核

---

## 模块概览

**职责**：在 SPA 入口建立"客户端可见"的鉴权闸门——管理路由必须先登录，已登录访问 `/login` 自动跳后台，刷新后通过后端回探确认 token 真实有效；并跨 Tab 同步登出。后端 Sa-Token 拦截器（`/api/admin/**`）才是真正的安全闸门，本模块只做交互与体验层面的拦截。

**关键文件**：
- `frontend/src/router/routes.ts:1-237` —— 路由表（publicRoutes / adminRoutes / errorRoutes），`requiresAuth` meta 仅打在 admin 路由。
- `frontend/src/router/guards.ts:1-56` —— 全局前置守卫，`authChecked` 模块级标志位 + 首次导航回探 + `/login` 重定向。
- `frontend/src/router/index.ts:1-18` —— `createWebHistory()` + 挂守卫。
- `frontend/src/stores/modules/user.ts:1-90` —— `isAuthenticated`/`userInfo`/`loginAction`/`logoutAction`/`checkAuthStatus` + storage 事件监听 + `persist.paths: ['isAuthenticated']`。
- `frontend/src/views/auth/Login.vue:1-134` —— 表单提交 + redirect 回跳。
- `frontend/src/layouts/AdminLayout.vue:16-34` —— 兜底：进入后台后若无 userInfo 则再取一次，失败触发 logoutAction。
- `frontend/src/utils/request.ts:88-91` —— 401 业务码跳 `/login`（引用 F02 主模块）。
- `backend/src/main/java/com/nanmuli/blog/infrastructure/config/security/SaTokenConfig.java:30-50` —— **后端**真闸门（引用 B06），`addPathPatterns("/api/admin/**")`。
- `backend/src/main/resources/application.yml:26-39` —— Sa-Token Cookie 配置（http-only / secure=false / same-site=Lax）。

**对外接口 / 依赖**：
- 对外：暴露 `/login`、`/admin/**` 路由；向 `useUserStore` 暴露 `isLoggedIn`/`loginAction`/`logoutAction`/`checkAuthStatus`。
- 依赖：`vue-router@4`、`pinia@2` + `pinia-plugin-persistedstate@3`、`element-plus`（ElMessage）、`@/api/auth`（`login`/`logout`/`getCurrentUser` → 走 `@/utils/request`）、后端 `/api/auth/login`、`/api/auth/info`、`/api/auth/logout`。

**已读文件清单**：
- `frontend/src/router/routes.ts` —— 通读
- `frontend/src/router/guards.ts` —— 通读
- `frontend/src/router/index.ts` —— 通读
- `frontend/src/stores/modules/user.ts` —— 通读
- `frontend/src/stores/index.ts` —— 通读
- `frontend/src/views/auth/Login.vue` —— 通读
- `frontend/src/layouts/AdminLayout.vue` —— 通读
- `frontend/src/api/auth.ts` —— 通读
- `frontend/src/utils/request.ts` —— 通读（401 处理佐证，主模块 F02）
- `frontend/src/main.ts` —— 通读（pinia/router 注册时序）
- `frontend/src/constants/api.ts` —— 通读（timeout/retry 常量）
- `frontend/package.json` —— 通读（依赖清单）
- `backend/.../SaTokenConfig.java` —— 通读（引用 B06，确认后端守卫边界）
- `backend/.../application.yml`、`application-prod.yml` —— 片段（Cookie 配置佐证）
- grep：`requiresAuth`/`isLoggedIn`/`isAuthenticated`/`checkAuthStatus`/`authChecked`/`redirect`/`persist`/`SaTokenConfig`/`SameSite` 等全仓搜索

**主模块归属**：本模块是 **路由守卫 / Cookie 鉴权（前端侧）** 的主模块（计划 §8.6），深查。对 **后端 Sa-Token 配置 / Filter / URL 拦截规则** 只引用 B06；对 **`request.ts` 401 处理** 只引用 F02。

---

## `[Bug]` 代码正确性与潜在缺陷

> 排查范围：guards.ts 状态机、user.ts 状态变更时序、storage 事件、persist 持久化、Login 回跳。逐条对照 §2.1。

### [P2] [Bug] 跨 Tab storage 事件只同步"登出"方向，不同步"登录"方向 <!-- 编号：F01-01 -->
- **定位**：`frontend/src/stores/modules/user.ts:59-73`
- **现象**：storage 事件处理器只判断 `!parsed?.isAuthenticated` 时清状态，没有任何 `parsed?.isAuthenticated === true` 分支去同步登录态。`loginAction`（user.ts:15-26）写 `isAuthenticated.value = true` 会通过 persist 写入 localStorage，触发其他 Tab 的 storage 事件，但其他 Tab 收到后因无登录分支而忽略。
- **影响**：在 A Tab 登录后，B Tab（原先未登录）仍显示未登录；反之 A Tab 登出能同步到 B Tab。属于"半边跨 Tab 同步"。对单人博客影响小，但若多 Tab 维护（如一个 Tab 编辑文章、一个 Tab 查看采集），新登录不会反映到旧 Tab，体验不一致。
- **根因/分析**：设计意图是"防止他 Tab 登出后本 Tab 仍误以为已登录"（避免用过期状态发请求），登录方向被有意省略。已排除"persist 未生效"——persist.paths 配置正确（user.ts:86-88），写入会触发事件。
- **修复方向**：①storage 事件收到 `isAuthenticated===true` 时也调用 `checkAuthStatus()` 回探后端再同步（避免盲信 localStorage）；②或维持现状但在注释中明确"仅同步登出"。标改动面 **小**。
- **关联**：次维度 [Design]；横向主题"鉴权机制一致性"。

### [P2] [Bug] 首次导航回探窗口：访问公开页时不回探，isAuthenticated=true 但 token 可能已失效 <!-- 编号：F01-02 -->
- **定位**：`frontend/src/router/guards.ts:21-24`
- **现象**：守卫只在 `!authChecked && userStore.isLoggedIn` 时回探，而 `authChecked` 是模块级变量——首次任意导航都会进入该分支。**但**回探条件是 `userStore.isLoggedIn`（即 isAuthenticated===true），如果用户刷新后直接落在 `/`（公开页），守卫也会触发回探（因 isLoggedIn=true）。**真正的窗口**在于：回探是异步 `await userStore.checkAuthStatus()`（guards.ts:23），但守卫在同一 tick 立即用 `userStore.isLoggedIn`（guards.ts:26）做后续判定——回探未完成前 `isLoggedIn` 仍为旧值 true。
- **影响**：刷新后首次导航期间，UI 与守卫看到的是 localStorage 里的旧 isAuthenticated=true。若 token 实际已失效（后端 Redis 已清/cookie 过期），在 checkAuthStatus 的 `getCurrentUser` 返回前，访问管理路由不会被前端拦截（直接放行 next()），要等后端 `/api/admin/**` 返回 401 才被 request.ts:88-91 跳回 /login。窗口大小 ≈ 一次 `/api/auth/info` RTT（同机房几十 ms，公网几百 ms）。
- **根因/分析**：守卫没有"等待回探结果再判定 requiresAuth"，而是 fire-and-forget。这是已知线索（计划 §9）的实证。**后端 Sa-Token 拦截器（SaTokenConfig:32-34）是真正闸门**，窗口期内的越权请求会被后端 401 拒绝，所以不构成安全漏洞，降为 P2（体验/兜底链路问题）。已排除"checkAuthStatus 内部已清状态"——它 catch 后才清（user.ts:51-55），期间状态仍是 true。
- **修复方向**：①守卫里 `await checkAuthStatus()` 后再读取 `isLoggedIn` 判定 requiresAuth（首次导航多一次 RTT，但状态准确）；②或保持现状，依赖后端 401 + request.ts 跳转兜底（当前已成立）。标改动面 **小**。
- **关联**：关联 [[F02-401处理]]（待 F02 报告编号）；次维度 [Security]；横向主题"鉴权机制一致性"；后端兜底见 [[B06-*]]。

### [P3] [Bug] guards.ts 的 redirect 回跳与 Login.vue 的 redirect 回跳存在两处独立解析，易漂移 <!-- 编号：F01-03 -->
- **定位**：`frontend/src/router/guards.ts:36-40` 与 `frontend/src/views/auth/Login.vue:44-46`
- **现象**：守卫在"已登录访问 /login"时读取 `to.query.redirect` 直接 `next(redirect || '/admin')`（guards.ts:37-38）；Login.vue 登录成功后也独立读 `route.query.redirect` 做 `router.push(redirect || '/admin')`（Login.vue:45-46）。两处解析逻辑重复，且都未校验 redirect 是否站内路径（见 F01-05）。
- **影响**：未来若要加 redirect 白名单/校验，需改两处，易漏改其一导致行为不一致。当前无功能性 bug。
- **根因/分析**：守卫负责"已登录拦截 /login"，Login.vue 负责"登录成功跳转"，职责分离导致重复。已排除"两处读到的 redirect 不同"——同一 query 参数，值一致。
- **修复方向**：抽一个 `resolveRedirect(query): string` 工具函数（含站内校验），两处复用。标改动面 **小**。
- **关联**：次维度 [Arch]；与 F01-05 同源。

---

## `[Security]` 安全漏洞

> 排查范围：逐项覆盖 §2.2 前端可观察项——开放重定向、Cookie 属性、CSRF、persist 泄漏、守卫绕过。后端 Sa-Token / Filter 深查归 B06，本节只记前端视角与引用。

### [P2] [Security] redirect 参数未校验，存在开放重定向 <!-- 编号：F01-04 -->
- **定位**：`frontend/src/views/auth/Login.vue:45-46`、`frontend/src/router/guards.ts:37-38`
- **现象**：`const redirect = route.query.redirect as string; await router.push(redirect || '/admin')`，未校验 redirect 是否以 `/` 开头、是否同站。攻击者可构造 `https://blog.example/login?redirect=https://evil.com`，用户登录后 `router.push('https://evil.com')` 会让浏览器离开 SPA 跳到外部站点（Vue Router 对带协议的字符串按 location 跳转处理）。
- **影响**：钓鱼场景——攻击者在社交平台散布"博客登录链接"附带恶意 redirect，用户输入真实凭证登录后被打包跳转到钓鱼页（伪装成"二次验证"）。**触发前提**：用户先点恶意链接、在真实站点完成登录**之后**才跳转；因博客是单人维护，攻击面窄，但仍是可利用的开放重定向。后端鉴权不受影响（后端独立校验）。
- **根因/分析**：Vue Router 的 `push(string)` 当 string 是绝对 URL 时会走外部导航，未做白名单。已排除"Vue Router 自动拒绝跨域"——它不会拒绝，会触发 `window.location`。
- **修复方向**：①校验 redirect 必须匹配 `^/[^/].*`（以单斜杠开头、非 `//host`），否则回落 `/admin`；②或用 `router.resolve(redirect)` 检查 resolved.name 是否非空。两处（Login.vue + guards.ts）都改。标改动面 **小**。
- **关联**：与 F01-03 同源；次维度 [Bug]；横向主题"鉴权机制一致性"。

### [P3] [Security] persist 仅持久化 isAuthenticated，但 isAuthenticated 本身是"信任标志"非凭证——泄漏风险低但语义需澄清 <!-- 编号：F01-05 -->
- **定位**：`frontend/src/stores/modules/user.ts:86-88`
- **现象**：`persist.paths: ['isAuthenticated']`，只持久化布尔标志，不持久化 userInfo（每次刷新靠回探或 AdminLayout 重新拉取）。Sa-Token 凭证在 HttpOnly Cookie 里（application.yml:36-39 http-only=true），JS 读不到，localStorage 里也没有 token。
- **影响**：即使 localStorage 被同类域 XSS 读取，也只能拿到一个布尔值，不泄漏 token 本身。**但** isAuthenticated=true 会让前端 UI 显示"已登录"并放行管理路由前端守卫——若攻击者能写 localStorage（如通过子域 cookie/localStorage 污染），可让前端误判已登录，但后端仍会 401（无有效 Cookie）。综合：低风险。
- **根因/分析**：设计正确，isAuthenticated 非敏感，凭证在 Cookie。无需调整。已排除"persist 把 userInfo 也持久化"——paths 只列了 isAuthenticated。
- **修复方向**：维持现状；可在注释中写明"isAuthenticated 仅为 UI 状态，真正鉴权依赖后端 Cookie + 拦截器"。标改动面 **小**（仅注释）。
- **关联**：次维度 [Arch]；CSRF/Cookie 属性深查归 [[B06-*]]。

### [P3] [Security] 前端守卫纯客户端，管理路由唯一真闸门在后端 SaInterceptor——需确认所有 admin API 都在 `/api/admin/**` 下 <!-- 编号：F01-06 -->
- **定位**：前端守卫 `frontend/src/router/guards.ts:29-33`（仅拦 requiresAuth）；后端 `backend/.../SaTokenConfig.java:32-34`（`addPathPatterns("/api/admin/**")` + exclude `/api/auth/login`、`/api/internal/**`）
- **现象**：前端守卫可被任意绕过（改 localStorage isAuthenticated=true / 直接访问 URL），真正鉴权 100% 依赖后端 SaInterceptor 对 `/api/admin/**` 的 checkLogin。**风险点**：若有管理类 Controller 不挂在 `/api/admin/` 前缀下（如误放到 `/api/xxx`），后端拦截器不会覆盖，前端守卫被绕过后即裸奔。
- **影响**：取决于后端路由命名规范是否被严格遵守——这是 B06 的核心排查项（计划 §9 已知线索"鉴权纯靠 URL 前缀"）。F01 视角只能确认"前端守卫不提供任何安全保证"。
- **根因/分析**：SPA 前端守卫天然不可信，设计如此。**[需查证]** 需 B06 核查所有写操作 Controller 是否都在 `/api/admin/**`，以及 `/api/auth/logout`、`/api/auth/info` 是否需要登录态（当前 SaInterceptor 未覆盖 `/api/auth/**`，仅 exclude 了 login）。
- **修复方向**：①后端补 `@SaCheckLogin` 注解到敏感 Controller（防 URL 前缀漏配）——归 B06；②前端维持现状。标改动面 **中**（后端）。
- **关联**：主模块 [[B06-*]]；横向主题"鉴权机制一致性"（§2.6）；计划 §9 已知线索。

---

## `[Arch]` 架构与技术债

> 排查范围：分层、重复逻辑、隐式约定、可测试性。共享对象按 §8.6 归属。

### [P3] [Arch] authChecked 为模块级可变变量，非 store 化，刷新后只生效一次的语义隐式 <!-- 编号：F01-07 -->
- **定位**：`frontend/src/router/guards.ts:5`（`let authChecked = false`）、`guards.ts:21-24`
- **现象**：`authChecked` 是 guards.ts 顶层的 `let`，不在 Pinia store 里。语义是"本次页面生命周期内只回探一次"。刷新页面会重置（新 JS 模块实例），SPA 内导航不会重置。
- **影响**：单次会话内 token 失效（如后端 active-timeout 触发，虽然当前 active-timeout=-1 即不触发，见 application.yml:29）不会被前端主动发现，只能靠下次 API 401 被动兜底。可运维性偏弱（没有"定期回探"机制）。对个人博客（timeout=30 天）影响极小。
- **根因/分析**：避免每次导航都打 `/api/auth/info` 的合理优化。隐式约定"回探一次即信任到下次刷新"。已排除"authChecked 跨刷新残留"——模块级变量随页面重载重置。
- **修复方向**：①维持现状，注释写明语义；②或加定时回探（如每 10 min 一次）——对单人博客过度。标改动面 **小**。
- **关联**：次维度 [Design]；与 F01-02 同源。

### [P3] [Arch] AdminLayout 与 guards.ts 存在重复的"拉 userInfo"逻辑 <!-- 编号：F01-08 -->
- **定位**：`frontend/src/layouts/AdminLayout.vue:22-33` 与 `frontend/src/stores/modules/user.ts:21`（loginAction 内）、`user.ts:44-49`（checkAuthStatus 内）
- **现象**：三处都会调 `getCurrentUser()` 取 userInfo：loginAction 登录后（user.ts:21）、AdminLayout onMounted 兜底（AdminLayout.vue:25）、checkAuthStatus（user.ts:44）。AdminLayout.onMounted 还直接 import 了 `getCurrentUser` 而非走 store action，绕过了 setUserInfo 之外的状态管理（AdminLayout.vue:26 调 setUserInfo，但若失败调 logoutAction）。
- **影响**：职责分散，未来改 userInfo 获取逻辑（如加字段、加缓存）需改三处。AdminLayout 直接调 api 而非 store，破坏了"store 是状态唯一入口"的约定。
- **根因/分析**：AdminLayout 的兜底是为应对"守卫放行但 userInfo 为空"（如刷新后 persist 只恢复了 isAuthenticated）。可改为调 `userStore.checkAuthStatus()` 复用。已排除"三处会并发重复请求"——guards 已回探的话，AdminLayout 进入时 userInfo 已有，不会二次请求（AdminLayout.vue:22 的 `!userStore.userInfo` 守卫）。
- **修复方向**：AdminLayout 改调 `userStore.checkAuthStatus()`（若 userInfo 为空），统一入口。标改动面 **小**。
- **关联**：次维度 [Bug]；横向主题"前端请求层"归 [[F02-*]]。

---

## `[Deps]` 依赖升级与版本

### 本模块依赖清单（基于声明文件，未翻依赖源码）

| 依赖 | 版本 | 声明位置 | 已知风险/可升级 | 备注 |
|---|---|---|---|---|
| vue | ^3.4.15 | `frontend/package.json:24` | 可升至 3.5.x（稳定） | 路由守卫 API 无 breaking |
| vue-router | ^4.2.5 | `frontend/package.json:25` | 可升至 4.4.x | `beforeEach`/`meta` API 稳定 |
| pinia | ^2.1.7 | `frontend/package.json:22` | 可升至 2.2.x；Pinia 3 已发布 | persist 插件兼容性需验 |
| pinia-plugin-persistedstate | ^3.2.1 | `frontend/package.json:23` | **v3 已 EOL，v4 重写了 API**（`paths` → `pick`），升级需改 store 配置 | **[需查证]** v3 是否有安全补丁；升级 v4 是 breaking |
| element-plus | ^2.5.1 | `frontend/package.json:18` | 可升至 2.8.x+ | ElMessage API 稳定 |
| axios | ^1.6.5 | `frontend/package.json:15` | 1.x 内可升；曾有 SSRF/ReDoS CVE（1.8.0+ 修复） | F02 主查 |

> 排查范围：仅本模块直接触达的依赖（路由/store/持久化/请求）。

### [P2] [Deps] pinia-plugin-persistedstate v3 已 EOL，v4 为 breaking 升级 <!-- 编号：F01-09 -->
- **定位**：`frontend/package.json:23`（`"pinia-plugin-persistedstate": "^3.2.1"`）+ `frontend/src/stores/modules/user.ts:86-88`（`persist: { paths: [...] }`）
- **现象**：v3 系列已停止维护，v4 把配置 key 从 `paths` 改为 `pick`/`omit`，并调整了 SSR 行为。当前用法 `persist.paths` 在 v4 下不生效。
- **影响**：停留在 EOL 版本收不到安全补丁；若未来顺带升级 pinia 到 v3，persistedstate 也必须升 v4，届时需同步改 user.ts 配置 key。非即时风险。
- **根因/分析**：`^3.2.1` 锁在主版本 3。**[需查证]** v3 末版是否有未修复 CVE（不翻 node_modules，基于公开信息）。
- **修复方向**：①短期维持 v3，记录技术债；②升级时一并迁 v4（`paths` → `pick`）+ pinia v3 兼容测试。标改动面 **中**（需回归持久化行为）。
- **关联**：次维度 [Arch]；F07（构建与依赖）汇总。

---

## `[Design]` 功能设计合理性

> 从真实使用出发（单人维护的技术博客 + 每工作日 AI 日报），回答 §2.5 中相关问题。

**审视结论**：

1. **场景适配**（§2.5-1）：单人博客场景下，前端守卫 + 后端 SaInterceptor 双层结构是**合理适配**——前端守卫改善体验（避免未登录用户看到空管理页），后端做真鉴权。`authChecked` 单次回探优化对 30 天 timeout 的个人博客够用，无需复杂会话刷新机制。**无需调整**。
2. **闭环完整性**（§2.5-2）：登录→访问管理→登出 的主闭环完整；但**跨 Tab 同步是半闭环**（只同步登出，F01-01），且**主动会话续期缺失**（F01-07）。对单人场景影响可控，但若未来有多端登录（如手机+桌面）会暴露体验断层。
3. **可运维性 / 单点扩展**（§2.5-3/7）：当前 `is-share=false` + `is-concurrent=false`（application.yml:30-31）= 单点登录，同一账号新登录会踢掉旧会话——对单人管理员是安全增益。但前端无"被踢下线"的主动通知（依赖 401 兜底），运维侧无法快速感知"谁在何时登录"——这部分归 B06。

### [P4] [Design] 缺少"被踢下线"的前端主动提示，仅靠 401 被动跳转 <!-- 编号：F01-10 -->
- **定位**：`frontend/src/utils/request.ts:88-91`（401 跳 /login，无提示）+ 后端 `application.yml:30`（`is-concurrent: false`）
- **现象**：因 `is-concurrent=false`，同一账号在 B 设备登录会把 A 设备的 token 顶失效。A 设备下次 API 调用返回 401，request.ts 静默跳 /login，用户无"你的账号在其他设备登录"的提示。
- **影响**：单人博客场景下，作者多设备切换时会被"莫名登出"，不知原因。体验断层而非 bug。
- **建议方向**：401 跳转前 ElMessage 提示"登录已失效，请重新登录"；或后端在踢下线时返回特定 code 区分"被踢"vs"过期"。标改动面 **小**（前端）/ **中**（后端区分 code）。
- **关联**：主模块 [[F02-*]]（401 处理）、[[B06-*]]（is-concurrent 语义）。

---

## 模块小结

### 严重度统计

| 级别 | 数量 | 条目编号 |
|---|---|---|
| P0 | 0 | — |
| P1 | 0 | — |
| P2 | 4 | F01-01、F01-02、F01-04、F01-09 |
| P3 | 5 | F01-03、F01-05、F01-06、F01-07、F01-08 |
| P4 | 1 | F01-10 |

### Top 风险（本模块最该先看的 ≤3 条）

1. **F01-04 redirect 开放重定向** —— 唯一带"可被外部利用"性质的前端缺陷，虽触发链路需先登录，但钓鱼场景成立，改动面小，应优先修。
2. **F01-02 首次导航回探窗口** —— 已知线索实证，窗口 ≈ 一次 RTT，后端 401 兜底已成立，非安全问题但影响体验准确性。
3. **F01-09 pinia-plugin-persistedstate v3 EOL** —— 长期技术债，会随 pinia 升级被迫迁 v4（breaking）。

### 修复优先级建议

- **立即**（P0/P1）：无。本模块无阻断或高优问题——真正的高优在 B06（后端鉴权机制）。
- **计划**（P2）：F01-04（redirect 校验，改动小、收益明确）、F01-01（跨 Tab 同步补登录方向）、F01-02（守卫 await 回探）、F01-09（登记技术债，配合 F07）。
- **择机**（P3/P4）：F01-03/07/08 重构收敛、F01-05 注释澄清、F01-10 被踢提示。

### 排查盲区 / 待复核

- **[需查证]** F01-06：后端所有管理类 Controller 是否都在 `/api/admin/**` 下，`/api/auth/logout`、`/api/auth/info` 是否需要登录态校验——**主模块 B06 核查**。
- **[需查证]** F01-09：pinia-plugin-persistedstate v3 末版是否有未修复 CVE（不翻 node_modules，基于公开信息）。
- **[需查证]** F01-10：后端在 `is-concurrent=false` 踢下线时，401 响应是否携带可区分的 code/message——**B06 核查**。
- 未覆盖：vue-router 4 / pinia 2 / persistedstate v3 在 SSR 场景的行为差异（本项目纯 SPA，不适用，但登记为盲区）。
