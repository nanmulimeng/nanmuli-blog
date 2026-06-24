# F06 状态管理 Pinia 排查报告

> **模块编号**：F06
> **排查范围**：Pinia store（user/config）数量与组织、持久化策略、缓存策略、全局状态 vs 组件局部状态划分
> **基线 commit**：`6ae930098405f4d0553d96a852f3345d0f39682e`
> **工作区状态**：脏（未提交改动均位于 `backend/`、`crawler-service/`、`deploy/`、`scripts/`、`docs/audit/`，**无 `frontend/` 改动**，本模块基线即 HEAD）
> **排查日期**：2026-06-24
> **排查人**：F06 audit agent
> **状态**：待复核

---

## 模块概览

**职责**：用 Pinia 管理跨组件共享的全局状态（当前仅 2 个 store：`user` 鉴权态、`config` 站点元信息），其余列表/详情数据用组件内 `ref` 局部状态管理。

**关键文件**：
- `frontend/src/stores/index.ts:1-9` —— Pinia 实例创建、store 模块统一导出
- `frontend/src/stores/modules/user.ts:7-90` —— user store（setup 写法 + persist.paths）
- `frontend/src/stores/modules/config.ts:5-51` —— config store（setup 写法，**无 persist**）
- `frontend/src/main.ts:14-30` —— Pinia 实例注册 + persistedstate 插件挂载
- `frontend/src/router/guards.ts:13-43` —— 路由守卫消费 user store 的 `isLoggedIn`/`checkAuthStatus`

**对外接口 / 依赖**：
- 对外：`useUserStore`（`isAuthenticated`/`userInfo`/`isLoggedIn`/`loginAction`/`logoutAction`/`setUserInfo`/`checkAuthStatus`）；`useConfigStore`（11 个 site.* ref + `loadConfig`）
- 依赖：`pinia ^2.1.7`、`pinia-plugin-persistedstate ^3.2.1`、`vue ^3.4.15`（声明于 `frontend/package.json:22-24`）；调用 `@/api/auth`（login/logout/getCurrentUser）、`@/api/config`（getPublicConfig）
- 主模块归属（§8.6）：本模块为 Pinia state 主模块。user store 鉴权语义 → F01 路由守卫（引用）；config store 后端 key 来源 → B07 后端 Config（引用）；前端请求层 → F02（引用）。

**已读文件清单**（可追溯 + 暴露盲区）：
- `frontend/src/stores/index.ts` —— 通读
- `frontend/src/stores/modules/user.ts` —— 通读
- `frontend/src/stores/modules/config.ts` —— 通读
- `frontend/src/main.ts` —— 通读
- `frontend/src/router/guards.ts` —— 通读（user store 消费方）
- `frontend/src/layouts/AdminLayout.vue` —— 片段（前 80 行，user store 消费）
- `frontend/src/views/auth/Login.vue` —— 片段（前 60 行，user store 消费）
- `frontend/src/components/common/AppHeader.vue` —— 通读（config store 消费，loadConfig 触发点）
- `frontend/src/components/common/AppFooter.vue` —— 通读（config store 只读消费）
- `frontend/src/views/home/Index.vue` —— 片段（前 60 行，config store 消费 + loadConfig）
- `frontend/src/views/about/Index.vue` —— 片段（前 50 行，config store 消费 + loadConfig）
- `frontend/src/api/config.ts` —— 通读（getPublicConfig 定义）
- `frontend/package.json` —— 片段（仅版本声明行）
- 盲区：未运行运行时探针确认 store 实例化时序；未读 `pinia-plugin-persistedstate` 源码（§1.3.1 禁止）。

---

## `[Bug]` 代码正确性与潜在缺陷

> 排查范围：两个 store 的状态读写、persist.paths、跨 Tab 同步、config loadConfig 的并发/缓存语义、刷新页面后的状态恢复路径。逐项检查 §2.1 checklist（空集合/边界/并发共享状态/状态机/缓存失效）。

### [P2] [Bug] config store 的 loadConfig 无去重，单次页面加载触发多次重复请求  <!-- 编号：F06-01 -->
- **定位**：`frontend/src/stores/modules/config.ts:18-35`（loadConfig 无 in-flight 标记/缓存守卫）；调用点 `frontend/src/components/common/AppHeader.vue:176`、`frontend/src/views/home/Index.vue:35`、`frontend/src/views/about/Index.vue:34`
- **现象**：config store 没有"已加载"标志位，也没有对并发 `loadConfig()` 做 Promise 去重。`AppHeader`（每个非 admin 页面都挂载）的 `onMounted` 调一次，`home/Index.vue` 的 `onMounted` 又调一次。访问首页时两个组件同帧 onMounted → 发出 **2 个** `/config/public` 请求；任何 SPA 内导航回到首页都会重复触发（store 字段虽已填充但不阻止再次拉取）。
- **影响**：单人博客场景下请求数翻倍但单次成本低，真实影响有限；但 `getPublicConfig` 是后端无鉴权公开接口（B07 视角），高频无意义请求会增加后端 config 缓存读取压力，且在管理端改完配置后无法保证多 Tab 看到的是最新值（store 内无脏标记/TTL）。
- **根因/分析**：store 把"加载动作"和"状态"解耦但没有"加载状态机"（loading/loaded/error）。已排除：并非 persistedstate 导致（config store 未配置 persist）。
- **修复方向**：① loadConfig 内加 `loaded` 标志位，已加载直接 return（小）；② 进一步对并发请求做 Promise 复用（`pendingPromise` 字段），避免同帧多次调用都打到后端（小-中）；③ 给 loaded 标志加 TTL 或暴露 `reloadConfig()` 供管理端配置变更后主动刷新（中）。改动面：**小-中**
- **关联**：次维度 `[Design]`（缓存策略缺失）；横向主题跨服务契约一致性（`/config/public` 契约归属 B07）；F02 请求层。

### [P3] [Bug] user store 的 storage 事件监听无解绑，且每次 store 实例化都注册一遍  <!-- 编号：F06-02 -->
- **定位**：`frontend/src/stores/modules/user.ts:58-73`
- **现象**：跨 Tab 同步逻辑写在 setup store 顶层（非 `onMounted`），靠 `typeof window !== 'undefined'` 判定后直接 `window.addEventListener('storage', ...)`。没有对应的 `removeEventListener`。监听器闭包内引用的是当前 store 实例的 `isAuthenticated`/`userInfo`。
- **影响**：Pinia 的 setup store 工厂函数在每个使用 `useUserStore()` 的组件首次调用时执行一次（后续走缓存），实际监听器通常只注册一次，故内存泄漏风险低。但存在两个隐患：① 监听器无解绑，若未来 store 被销毁/重建（如测试或 SSR hydration）会残留；② 监听器解析 `e.newValue` 的 JSON 时若其他代码往 `localStorage['user']` 写了非预期格式，`catch` 分支会**无条件把当前 Tab 也登出**（`isAuthenticated.value = false`）——即别的 Tab 或别的代码污染 user key 会让正常工作的 Tab 被动登出。
- **根因/分析**：跨 Tab 同步意图正确（单点登录 `is-concurrent=false` 语义需要），但实现放在 store 工厂顶层而非可托管生命周期的位置，且兜底分支过激。已排除：不是 SSR 问题（项目无 SSR）。
- **修复方向**：① 把监听器注册移到应用入口（main.ts 或 App.vue onMounted），返回取消函数便于测试清理（小）；② catch 分支改为仅在 `newValue === null` 或显式 `isAuthenticated:false` 时清状态，格式错误时忽略（小）。改动面：**小**
- **关联**：F01（跨 Tab 同步主语在路由守卫/鉴权）；次维度 `[Security]`（被动登出可用性）。

---

## `[Security]` 安全漏洞

> 排查范围：persist 持久化字段是否含敏感数据、localStorage 暴露面、user store 是否持久化 token/userInfo、跨 Tab storage 事件被滥用。逐项覆盖 §2.2 技术栈重点中前端相关项（Cookie/CSRF/token 暴露）。Sa-Token/MyBatis/AES/SSRF/文件上传/双向 key 均非本模块范围。

### [P3] [Security] user store 仅持久化 isAuthenticated 布尔，未持久化 token/userInfo —— 设计正确，记录确认  <!-- 编号：F06-03 -->
- **定位**：`frontend/src/stores/modules/user.ts:85-89`（`persist: { paths: ['isAuthenticated'] }`）；`config.ts` 整文件无 persist 配置
- **现象**：① user store 的 `persist.paths` 显式只含 `isAuthenticated`（boolean），**不持久化** `userInfo`（含 nickname/avatar/email）。Sa-Token 走 Cookie 模式（HttpOnly 由后端控制），前端不接触 token 字符串，故 token 不进 localStorage。② config store 完全不持久化，每次刷新页面都从后端重拉，避免站点配置在前端 localStorage 脏缓存。
- **影响**：安全侧良好——localStorage 中只有 `{"isAuthenticated":true}`，无敏感信息可被 XSS 直接窃取（XSS 仍可借此伪造登录态，但守卫会回探后端校验，见 F01）。`userInfo` 刷新后丢失，由 `AdminLayout.vue:22-33` 的 `onMounted` 重拉 `getCurrentUser()` 补回，闭环成立。
- **根因/分析**：设计符合 §2.2 的"敏感信息不落 localStorage"原则。无需调整，记录为安全确认项。已排除：检查了 `frontend/src/utils/visitor.ts`（`blog_visitor_id` 是访客计数器，非鉴权，无关）。
- **修复方向**：无需调整。若后续要把 userInfo 一起持久化以减少首屏抖动，**不要**持久化含 email/手机号的字段。改动面：—
- **关联**：F01（鉴权守卫回探窗口）；B06（Sa-Token Cookie 模式主语）。

---

## `[Arch]` 架构与技术债

> 排查范围：store 数量与组织、setup vs options 写法一致性、全局 vs 局部状态划分合理性、类型定义、命名。共享对象按 §8.6 归属，本模块只看 store 自身。

### [P4] [Arch] 仅 2 个 store + 大量组件局部 ref 状态，划分基本合理但 config 缺集中管理  <!-- 编号：F06-04 -->
- **定位**：`frontend/src/stores/`（全目录仅 `index.ts` + `modules/user.ts` + `modules/config.ts`）
- **现象**：① 项目仅 2 个 store。文章/分类/日报/项目/采集/日报管理/代理 等列表页全部用组件内 `ref` + `onMounted` 拉取（见 `AppFooter.vue:11` friendLinks、`home/Index.vue:32-33` articles/aggregated、`about/Index.vue:12` skills），无对应 list store。② 两个 store 都用 setup 写法（`defineStore('id', () => {...})`），风格一致。③ 类型定义清晰（`UserInfo` 来自 `@/types/user`，config 字段为 `ref<string>`）。
- **影响**：列表用局部状态对单人博客**合理**（无跨页共享需求、避免 store 膨胀），不是技术债。真正的小隐患是 config store：字段散落 11 个 ref，管理端改配置后无主动失效信号（见 F06-01），且无统一类型（如 `SiteConfig` interface）。
- **根因/分析**：MVP 阶段最小化 store 数量是正确取舍。已排除：不是"缺少 store 导致重复请求"（重复请求根因是 loadConfig 无去重，见 F06-01，而非缺 store）。
- **修复方向**：可选——把 11 个 site.* ref 收敛成一个 `siteConfig = ref<SiteConfig>({...})` 对象 + 定义 `SiteConfig` 类型，减少 store 顶层 ref 数量（小，纯重构）。改动面：**小**
- **关联**：次维度 `[Design]`。

---

## `[Deps]` 依赖升级与版本

### 本模块依赖清单（基于声明文件，未翻依赖源码）

| 依赖 | 版本 | 声明位置 | 已知风险/可升级 | 备注 |
|---|---|---|---|---|
| pinia | `^2.1.7` | `frontend/package.json:22` | 可升级至 2.2.x / 3.x（Vue 3.4 兼容） | `^2.1.7` 实际安装最新 2.x；3.x 为大版本，需评估 [需查证] |
| pinia-plugin-persistedstate | `^3.2.1` | `frontend/package.json:23` | 4.x 已发布，API 有变更（`persist` 选项写法） | 当前 3.x 用法 `persist: { paths: [...] }` 在 4.x 改为 `pick`/`omit`，升级需改 store 配置 [需查证] |
| vue | `^3.4.15` | `frontend/package.json:24` | 可升级至 3.4.x 最新 / 3.5.x | 与本模块无直接冲突 |

> 排查范围：仅 `frontend/package.json` 中 pinia/persistedstate/vue 三项声明。未跑 `npm audit`（§1.3 命令边界），CVE 判断基于公开信息 [需查证]。未发现阻断性版本问题。

### （无独立 [Deps] 发现条目）

依赖版本均在合理范围内，pinia 2.x → 3.x 和 persistedstate 3.x → 4.x 是未来升级方向但非当前问题，归入 §下文 Design P4 备选。

---

## `[Design]` 功能设计合理性

> 从真实使用出发，回答 §2.5 中相关的问题（≥2 个）。本模块为 🟢 简单模块，重点回答"场景适配""可运维性""缺失功能"。

**审视结论**：

1. **场景适配**（§2.5-1）：单人维护博客 + 每工作日 AI 日报场景下，仅 user/config 两个 store 的取舍**合理**。文章/日报等列表数据无跨路由共享需求，放组件局部 ref 避免了 store 膨胀和过期缓存问题，符合 MVP 最小化原则。不是过度设计也不至于太简陋。

2. **可运维性 / 缺失功能**（§2.5-3/5）：config store 的两个可运维短板——① 无"已加载/加载中/出错"状态机（F06-01），管理端改配置后无法保证已打开页面看到最新值，也无显式 reload 入口；② 站点配置在前端无缓存兜底，后端 `/config/public` 不可用时整站 header/footer 的 siteName 会回退到硬编码默认值（`AppHeader.vue:228` `|| 'Nanmuli'`），功能不阻断但元信息会错。对单人博客不是硬伤，记录为 P4。

3. **闭环完整性 / SSR 首屏**（§2.5-2/缺失）：项目无 SSR，config store 的 `loadConfig` 在 `onMounted` 异步触发，首帧渲染靠 store 内硬编码默认值（`siteName='Nanmuli Blog'` 等），异步到达后响应式更新。会有轻微首屏闪烁（站点名/logo 跳变）但可接受。若未来要消除闪烁，可在 `main.ts` 挂载前 `await configStore.loadConfig()`（代价是首屏阻塞一个请求，取舍见仁）。

### [P4] [Design] config store 缺"已加载"状态机与显式 reload 入口  <!-- 编号：F06-05 -->
- **定位**：`frontend/src/stores/modules/config.ts:18-35`（loadConfig 无 loaded/loading 标志、无 reload）；管理端配置页 `views/admin/config/*`（F05 范围）改完配置后无信号触发 store 失效
- **现象**：当前 loadConfig 是"无条件全量拉取"，既不防重复（见 F06-01），也不提供"标记失效后强制刷新"的能力。管理端保存配置后，已打开的其他 Tab 的 header/footer 不会自动更新（除非整页刷新）。
- **影响**：单人场景下用户多半自己改自己看，刷新即可；但这是"配置闭环"的一个小缺口——配置变更不能即时广播。
- **建议方向**：① loadConfig 加 `loaded` 标志 + 暴露 `invalidate()`/`reload()`（小）；② 管理端保存成功后调用 `configStore.reload()`（小，跨 F05/F06）；③ 可选——用 storage 事件做跨 Tab 配置失效广播（中）。改动面：**小-中**
- **关联**：F06-01；B07（后端 config 缓存刷新主语）；F05（配置管理页）。

---

## 模块小结

### 严重度统计

| 级别 | 数量 | 条目编号 |
|---|---|---|
| P0 | 0 | — |
| P1 | 0 | — |
| P2 | 1 | F06-01 |
| P3 | 2 | F06-02, F06-03 |
| P4 | 2 | F06-04, F06-05 |

> 注：F06-03 为安全确认项（设计正确），计入 P3 仅作登记，**非待修问题**。

### Top 风险（本模块最该先看的 ≤3 条）

1. **F06-01 config store loadConfig 无去重致重复请求** —— 唯一 P2，影响后端公开接口被无意义重复命中，且是配置缓存失效问题（F06-05）的根因载体。
2. **F06-02 user store storage 监听器无解绑 + catch 分支过激被动登出** —— 低概率但用户体验直接受害（被登出）。
3. **F06-05 config store 缺状态机/reload 入口** —— 配置闭环缺口，单人不痛但记录。

### 修复优先级建议

- **立即**（P0/P1）：无。
- **计划**（P2）：F06-01（loadConfig 加 loaded 标志 + Promise 去重，改动面小-中）。
- **择机**（P3/P4）：F06-02（监听器治理 + catch 收敛）；F06-04（config ref 收敛为对象，纯重构）；F06-05（reload 入口，跨 F05 协同）。

### 排查盲区 / 待复核

- pinia 2.x → 3.x、persistedstate 3.x → 4.x 的 breaking change 细节未深入（§1.3.1 禁翻 node_modules），升级影响标 `[需查证]`，登记到索引页待复核。
- 未在运行时验证 AppHeader + home/Index 同帧 onMounted 是否真触发 2 次 `/config/public`（基于代码静态分析推断，逻辑确定性高但未实测），若需 100% 确证可在浏览器 Network 面板观察 [需查证]。
- config store 升级为对象式（F06-04 建议方向）对模板 `configStore.siteName` 解构消费的影响未逐一核对所有消费点（AppHeader/AppFooter/home/about 共 4 处均用 `configStore.xxx` 点访问，重构为 `configStore.siteConfig.xxx` 需同步改）。
