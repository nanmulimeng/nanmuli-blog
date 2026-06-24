# F05 配置与代理管理页 排查报告

> **模块编号**：F05
> **排查范围**：系统配置页（key-value 编辑 / 恢复日报推荐源 / 刷新后端缓存 Java+Python 双向）+ 代理管理页（订阅/分组/测速/节点切换）+ 配置 inputType 数据库驱动渲染
> **基线 commit**：`6ae930098405f4d0553d96a852f3345d0f39682e`
> **工作区状态**：脏（未提交改动均不涉及 F05 文件：`ConfigRepositoryImpl.java`、`WebCollectPageMapper.java`、`crawler-service/*`、`deploy/README.md`、`risk-register.md`、`release-gate.ps1`、新增 `backend/src/test/.../webcollector/`、新增 `docs/audit/module-audit/`）。本模块文件 `frontend/src/views/admin/config/Index.vue` / `proxy/Index.vue` / `api/config.ts` 均为干净 HEAD 态。
> **排查日期**：2026-06-24
> **排查人**：F05 排查 agent
> **状态**：草稿

---

## 模块概览

**职责**：为管理员提供两块后台页面——系统配置（全量 key-value 编辑，按 group/sub 分组、据 inputType 渲染不同控件、敏感项脱敏、批量保存、刷新缓存与恢复日报推荐源）和代理管理（Mihomo/Clash 订阅、分组、节点延迟测试、节点切换）。

**关键文件**：
- `frontend/src/views/admin/config/Index.vue:1-417` —— 系统配置页（数据获取、分组、保存、刷新、reset、inputType 渲染）
- `frontend/src/views/admin/proxy/Index.vue:1-296` —— 代理管理页（订阅、状态、分组、测速、节点切换）
- `frontend/src/api/config.ts:1-60` —— 配置 + 代理两套 API 封装
- `frontend/src/types/config.ts:1-49` —— Config/ProxyStatus/ProxyGroup/NodeDelay 类型定义

**对外接口 / 依赖**：
- 对外：调用后端 `ConfigController`（`/api/admin/config/*`、`/api/config/public`）与 `ProxyController`（`/api/admin/proxy/*`）
- 依赖（前端）：`@/utils/request`（主模块 F02）、`@/components/common/FileUpload.vue`（图片类配置）、Element Plus、Pinia 鉴权（主模块 F01）
- 依赖（后端契约）：B07（ConfigAppService / AES / 缓存）、B11（ProxyAppService / MihomoProxyClient / 订阅 SSRF 由后端防）、C11（crawler 配置刷新）

**已读文件清单**：
- `frontend/src/views/admin/config/Index.vue` —— 通读
- `frontend/src/views/admin/proxy/Index.vue` —— 通读
- `frontend/src/api/config.ts` —— 通读
- `frontend/src/types/config.ts` —— 通读
- `frontend/src/utils/request.ts` —— 通读（仅引用，主模块 F02）
- `frontend/src/components/common/FileUpload.vue` —— 通读
- `frontend/src/router/routes.ts` —— 片段（config/proxy 路由）
- `backend/.../interfaces/rest/ConfigController.java` —— 通读（契约核对）
- `backend/.../interfaces/rest/ProxyController.java` —— 通读（契约核对）
- `backend/.../application/config/ConfigAppService.java` —— 通读（脱敏/缓存逻辑）
- `backend/.../application/config/dto/ConfigDTO.java` —— 通读
- `backend/.../application/proxy/ProxyAppService.java` —— 通读
- `backend/.../application/proxy/command/SubscriptionCommand.java` —— 通读
- `backend/.../infrastructure/proxy/MihomoProxyClient.java` —— 片段（仅 SSRF 归属确认）
- `db/init.sql`、`db/migration/V1_12__*.sql` —— 仅 grep（inputType 列）

**主模块归属**：本模块深查前端配置/代理页。后端 Config → B07；代理 → B11；刷新缓存双向 → C11。AES 加密 → B07（只引用）。鉴权机制 → B06/F01（只引用）。请求层 → F02（只引用）。schema → B15（只引用）。

---

## `[Bug]` 代码正确性与潜在缺陷

> 排查范围：`config/Index.vue`、`proxy/Index.vue`、`api/config.ts` 的数据流、保存逻辑、刷新/重置流程、错误处理、边界条件。

### [P2] [Bug] password 类配置失焦自动保存会推送脱敏占位值 `********`  <!-- 编号：F05-01 -->
- **定位**：`frontend/src/views/admin/config/Index.vue:326-334`（password input）+ `:308` switch + `:332` password `@blur="handleSave(...)"`；后端拒绝逻辑在 `ConfigAppService.update:74-76`
- **现象**：password 类型输入框绑 `@blur="handleSave(config.configKey)"`。`handleSave:144-145` 判定 `value === originalData.value[key]` 则跳过保存——但后端返回的脱敏值是字面量 `"********"`，`formData` 和 `originalData` 都被初始化为 `"********"`（`fetchData:32-35`）。因此用户未改动时失焦不会误保存（双等值跳过）。**但**：用户点"重新输入"清空（`:344` `formData[key] = ''`）后，若不输入直接失焦，会把空串 `""` 作为新值 PUT 到后端——后端 `update` 不会因空串触发拒绝（只有 `MASK_SENTINEL` 触发），会把敏感配置覆盖为空。同理 textarea/text 类失焦保存，用户清空后失焦也会把配置清空。
- **影响**：admin 误操作（清空输入框后失焦/切到别处）会把 API key、callback key 等敏感或关键配置静默写成空串，触发 `crawlerTaskClient.refreshConfig` 后 Python 爬虫鉴权失败、日报链路中断。失焦保存（无确认）放大了误操作后果。
- **根因/分析**：①失焦即保存的设计对敏感/关键配置缺少二次确认或空值防护；②后端 `update` 只挡 `MASK_SENTINEL`，不挡"从有值变空"的关键 key（如 `crawler.auth.api_key`、`callback.key`）；③已排除：masked 状态下 `isMasked` 让 input disabled（`:340-341`），但"重新输入"清空后 input 解除 disabled，失焦即触发空值保存。
- **修复方向**：①关键/敏感 key 失焦保存前对空值弹确认或直接拒绝；②后端 `update` 对标记为 `isSensitive` 或属关键 key（`crawler.auth.*`、`callback.key`）的空值变更做拦截或要求显式 flag。（改动面：中）
- **关联**：[[B07]] / 横向主题-跨服务契约 / 配置项 `crawler.auth.api_key`、`crawler.callback.key`

### [P2] [Bug] 批量保存按串行 await 逐条 PUT，N 条配置发 N 次顺序请求且全程无进度反馈  <!-- 编号：F05-02 -->
- **定位**：`frontend/src/views/admin/config/Index.vue:154-175`（`handleSaveSection`）
- **现象**：`for (const config of section.configs) { ... await updateConfig(...) ... }`——一个分组（如 `digest`、`pipeline`）可能有 10+ 条配置，逐条 `await` 顺序发送。每条 PUT 成功后后端还会触发 `refreshAfterConfigChange`（`ConfigController:50-58`），对 `crawler.*` key 每条都会 `crawlerTaskClient.refreshConfig()` + `configService.reload()` + `reloadPool()` ×2，即 N 条改动产生 N×（1 次 Python HTTP 调用 + 3 次 Java 重载）。
- **影响**：保存一个 15 项的分组需要 15 次串行 HTTP + 15 轮后端重载链，前端按钮 loading 数秒至十几秒，期间任一条失败仅计入 `failed` 计数但不回滚已保存项，导致部分生效。用户体验差且后端承受放大负载。
- **根因/分析**：前端无批量保存接口（后端只有单 key PUT），被迫逐条循环。已排除：循环内的 try/catch 做了失败隔离（`failed++`），不会整体崩。
- **修复方向**：①后端补一个批量更新接口（接受 key-value map，单事务 + 单次刷新）；②或前端把循环改为有限并发（如 `Promise.all` + `p-limit`）并加进度提示。（改动面：中，需后端配合）
- **关联**：[[B07]] / 横向主题-跨服务契约

### [P3] [Bug] 代理测速无前端超时与并发控制，结果按"最后一次"覆盖且失败节点不可区分  <!-- 编号：F05-03 -->
- **定位**：`frontend/src/views/admin/proxy/Index.vue:42-57`（`handleTestDelay`）、`:48-49`（结果覆盖）、`:100-111`（`getDelayText`）
- **现象**：`testNodesDelay(groupName)` 单次 POST，后端 `ProxyAppService.testDelay:124` 固定 3s 超时对整组测速。前端 `delays.value[groupName]` 整组覆盖。`getDelayText:108-110` 中 `delay === 0` 显示"不可达"，但 `delays` 初始化/未测时 `getNodeDelay` 返回 `undefined` 显示"未测试"——而 `handleTestDelay:48` 把不可达节点 delay 也设为 `0`，与"未测试"区分正确。但若同组二次测速返回结果集为空（Mihomo 异常），会把整组覆盖为空对象，已测过的延迟丢失。
- **影响**：重复测速若后端返回空/部分结果，前端无 merge 逻辑，已展示的历史延迟被清空；无单节点重测能力，必须整组重测。
- **根因/分析**：测速结果按 groupName 整体替换而非按 nodeName merge。已排除：不可达 vs 未测试的显示逻辑本身正确。
- **修复方向**：①测速结果按 nodeName 合并而非整组覆盖（保留未重测节点的旧值）；②支持单节点重测。（改动面：小）
- **关联**：[[B11]]

### [P3] [Bug] `handleSave` 对未改动 key 的 switch/password 提前 return，但 switch 的 `@change` 用 `String(val)` 转换可能误判相等  <!-- 编号：F05-04 -->
- **定位**：`frontend/src/views/admin/config/Index.vue:143-152`（`handleSave`）、`:308`（switch `@change`）
- **现象**：switch 的 `active-value="true" inactive-value="false"` 是字符串，`@change` 回调把 `val` 转 `String(val)` 写入 `formData`。若 Element Plus 在某些版本对 `active-value/inactive-value` 传字符串时回调实际给布尔值，`String(true) === 'true'` 与 `originalData`（也是 `'true'`）相等会跳过保存——属正常。但 `originalData` 初始化来自后端 `configValue`（`fetchData:32-35`），switch 类配置后端存的是 `'true'`/`'false'` 字面量，前后端口径一致。已排除：无实质 bug。
- **影响**：暂无功能性后果，仅在 Element Plus 版本变更 `change` 回调签名时可能出现"切换不保存"。
- **根因/分析**：依赖 `active-value/inactive-value` 字符串字面量与后端存储字面量一致这一隐式约定。
- **修复方向**：保持现状即可；若加固可显式归一化布尔配置。（改动面：小）
- **关联**：无

### [P3] [Bug] 订阅地址保存无前端校验，空串与非法 URL 直送后端  <!-- 编号：F05-05 -->
- **定位**：`frontend/src/views/admin/proxy/Index.vue:76-86`（`handleSaveSubscription`）、`:145-157`（输入框）
- **现象**：`subUrl` 直接 `await updateSubscriptionUrl(subUrl.value)`，无 URL 格式校验、无空值确认。空串会触发后端 `ProxyAppService.updateSubscription:150-161` 把 `crawler.proxy.subscription_url` 写空。
- **影响**：误清空订阅地址后，Mihomo 重新拉取节点会失败；SSRF 由后端 B11 兜底，但前端缺提示会让 admin 提交明显错误的值（如 `javascript:`、内网地址）后才被后端拒。
- **根因/分析**：前端职责分工上 SSRF 交后端，但基本格式校验应在入口做。
- **修复方向**：保存前用 `new URL()` try/catch 做轻量校验，空值需二次确认。（改动面：小）
- **关联**：[[B11]] / SSRF 主模块归属

---

## `[Security]` 安全漏洞

> 排查范围：敏感配置回显/脱敏、订阅 URL 输入、测速/节点切换入参、XSS（config value 渲染）、鉴权路由、文件上传图片类配置。逐项覆盖 §2.2 中的 SSRF/敏感信息泄露/XSS/双向 key 相关项。

### [P2] [Security] 敏感配置 admin 端解密回显为 `********`，"重新输入"后明文编辑框无二次验证即可改写密钥  <!-- 编号：F05-06 -->
- **定位**：`frontend/src/views/admin/config/Index.vue:336-348`（masked + 重新输入）、`ConfigAppService.toAdminDTO:147-157`（后端解密后仍 mask）
- **现象**：后端对 `isSensitive` 配置**先 AES 解密再 mask 成 `********`**（`ConfigAppService:151-157`），即前端拿不到明文（合理）。前端"重新输入"按钮把 `formData[key]` 清空，input 解禁，admin 输入新值后失焦保存。**新值以明文经 HTTP（若非 HTTPS）传后端**，且无需二次确认当前密钥即可重置——任何能进入 `/admin/config` 的会话（含被盗 Cookie / CSRF 成功的情形）可一键改写 `crawler.auth.api_key`、`crawler.callback.key`。
- **影响**：敏感配置（API key、callback key）的修改无"输入旧值确认"或二次密码验证，鉴权仅靠 Sa-Token Cookie（主模块 B06 已知 URL 前缀 + Cookie 模式薄弱）。若 Cookie 被窃或 CSRF（需确认 §2.2 CSRF 防护，主模块 B06/F01），攻击者可静默改写密钥接管跨服务调用。
- **根因/分析**：设计上把"能进 admin"等价于"可信改密钥"，但 Sa-Token Cookie + URL 前缀鉴权强度有限。已排除：后端 `update` 拒绝 `MASK_SENTINEL` 覆盖（防误改），但无法防"清空后填攻击者值"。
- **修复方向**：①敏感配置修改要求二次输入当前密码或旧值；②敏感配置写操作加 CSRF token（依赖 B06）；③前端对敏感 key 保存弹二次确认。（改动面：中）
- **关联**：[[B07-敏感配置]] / [[B06-CSRF/鉴权]] / AES 加密主模块 B07 / 双向 key（§2.2）

### [P3] [Security] 订阅 URL 输入框接受任意字符串，SSRF 防护完全依赖后端 B11（前端零校验）  <!-- 编号：F05-07 -->
- **定位**：`frontend/src/views/admin/proxy/Index.vue:144-157`、`api/config.ts:53-55`
- **现象**：前端对 `subUrl` 不做任何协议/域名/格式校验，`updateSubscriptionUrl(subUrl.value)` 直送。后端 `ProxyAppService.updateSubscription:150-161` 调用 `mihomoProxyClient.updateProviderUrl`——Mihomo 自身去拉取该 URL，SSRF 防护在 B11/Mihomo 侧。
- **影响**：若后端 B11 未对订阅 URL 做回环/保留地址过滤，admin（或 CSRF/被劫持会话）可让 Mihomo 拉取内网地址（如 `http://169.254.169.254/`）触发 SSRF。前端无任何拦截。
- **根因/分析**：前端分工可不防 SSRF，但**零校验**意味着连明显错误（`javascript:`、空格、超长）也不挡。SSRF 深查归 B11。
- **修复方向**：①前端加 `http(s)://` 协议白名单 + `new URL()` 校验（减少误输与低级滥用）；②SSRF 实质防护见 B11。（改动面：小，前端）
- **关联**：[[B11-SSRF]] / §2.2 SSRF

### 未发现（已检查）
- **XSS（config value 含 HTML）**：`config/Index.vue` 全程用 `{{ }}` 文本插值与 `el-input v-model`，无 `v-html`/`innerHTML`（已 grep 确认 `frontend/src/views/admin/config/`、`/proxy/` 无命中）。config value 即使含 `<script>` 也只会作为文本显示，无 XSS。FileUpload 的图片 URL 经 `:src`（`FileUpload.vue:87`），浏览器对 img src 的脚本不执行。安全。
- **越权/路由**：`/admin/config`、`/admin/proxy` 均带 `requiresAuth: true`（`routes.ts:202,208`），守卫属 F01。后端 `ConfigController` 的 `/admin/config/*` 路径依赖 Sa-Token 路由拦截器（鉴权一致性主模块 B06）。
- **密钥日志泄露**：前端不打印 config value（`request.ts` 仅 `console.warn/error` URL+message，不含 body）。
- **CSRF**：写操作（PUT/POST）是否带 CSRF token 见 B06/F01，本模块不重复。

---

## `[Arch]` 架构与技术债

> 排查范围：前后端契约一致性、API 封装合理性、组件复用、类型定义、分组逻辑可维护性。共享对象按 §8.6 归属，非主模块只引用。

### [P3] [Arch] `updateConfig` 与 `resetConfigToDefault` 对 key 的编码不一致（一个裸传一个 encodeURIComponent）  <!-- 编号：F05-08 -->
- **定位**：`frontend/src/api/config.ts:9`（`put('/admin/config/${key}')` 裸传）、`:13`（`post('/admin/config/${encodeURIComponent(key)}/reset-default')` 编码）
- **现象**：同一份 config API，PUT 更新用裸 `${key}`（如 `crawler.digest.sections`，点号在 path 中合法），reset-default 却用了 `encodeURIComponent`（点号不被编码，但若 key 含 `/` 或空格则 PUT 会错乱而 reset 不会）。后端 `ConfigController:51,61` 用 `@PathVariable String key` 接收，Spring 默认 `/admin/config/{key}` 不匹配带 `/` 的 key（两种调用一致），但行为不对称是隐患。
- **影响**：当前所有 key 形如 `a.b.c`（点号），两种方式都能工作；但语义不一致，未来若 key 含特殊字符（空格、`/`）会出现 PUT 失败而 reset 成功（或反之）的诡异 bug。
- **根因/分析**：历史演进中 reset 路径补了编码、PUT 未补。已排除：现网 key 字符集受限，无即时故障。
- **修复方向**：统一两者编码策略（都裸传或都 encodeURIComponent），并补注释说明后端 `@PathVariable` 的字符约束。（改动面：小）
- **关联**：横向主题-跨服务契约

### [P3] [Arch] 配置分组逻辑（`groupedConfigs` computed）在模板里多层嵌套查找，120+ key 渲染时每帧重算  <!-- 编号：F05-09 -->
- **定位**：`frontend/src/views/admin/config/Index.vue:105-139`（`sortedGroups` + `groupedConfigs` 两个 computed）、`:121`（`configs.filter` 全量遍历）、`:247`（模板再 `groupedConfigs[group]`）
- **现象**：`groupedConfigs` 是 computed，内部对 `sortedGroups` 每个 group 再 `configs.filter`（O(G×N)）+ 子分组 map + sort。模板里 `v-for group` 又 `v-for section` 又 `v-for config`。当配置项 120+（CLAUDE.md 提及"120+ config key"），每次 `formData` 变更触发响应式重算。
- **影响**：单人维护场景下配置项数量有限，实测卡顿风险低；但 `formData[config.configKey] = ...` 频繁触发（每输入一个字符）可能让 computed 重算。属可维护性/边界性能问题。
- **根因/分析**：computed 依赖 `configs.value`（不在输入时变），实际输入改的是 `formData`（不触发 `groupedConfigs` 重算）——所以性能影响比直觉小。但分组结构本身复杂、SUB_LABELS 硬编码（`:90-96`）新加分组需改前端。
- **修复方向**：①分组标签由后端返回（`groupName` 已在 DTO，可扩展 `groupLabel`）；②若性能确实可观测，用 `shallowRef` + 手动重建。（改动面：小-中）
- **关联**：无

### [P4] [Arch] `Config.sensitive` 字段已 `@deprecated` 但前后端仍双写双读  <!-- 编号：F05-10 -->
- **定位**：`frontend/src/types/config.ts:12-13`（`sensitive?` 标 `@deprecated`）、`config/Index.vue:165,196,292`（`config.isSensitive || config.sensitive` 双判断）、后端 `ConfigDTO.java:23-24`（`sensitive` 标 `@deprecated`）、`ConfigAppService:155`（`setSensitive(true); setIsSensitive(true)` 双写）
- **现象**：迁移期兼容写法散落前端 3 处 + 后端 DTO/AppService。`@deprecated` 字段长期保留增加心智负担。
- **影响**：无功能问题，仅技术债。
- **根因/分析**：渐进迁移未收尾。
- **修复方向**：确认线上数据全部为 `isSensitive` 后移除 `sensitive` 双写双读。（改动面：小）
- **关联**：[[B07]]

---

## `[Deps]` 依赖升级与版本

### 本模块依赖清单（基于声明文件，未翻依赖源码）

| 依赖 | 版本 | 声明位置 | 已知风险/可升级 | 备注 |
|---|---|---|---|---|
| vue | ^3.4.15 | `frontend/package.json:24` | 可升至 3.5.x | config/proxy 页用 `<script setup>` + computed，升级影响小 |
| element-plus | ^2.5.1 | `frontend/package.json:18` | 可升至 2.8+ | 用到 `el-tabs/el-switch/el-input/el-table/el-tag/el-empty/el-alert/el-upload`，需回归 switch change 回调签名（见 F05-04） |
| axios | ^1.6.5 | `frontend/package.json:16` | 可升至 1.7+ | 请求层主模块 F02 |
| @element-plus/icons-vue | ^2.3.1 | `frontend/package.json:14` | 当前可用 | RefreshRight/Lock/Hide/Connection 图标 |

> 排查范围：仅 F05 直接使用的 4 个前端依赖（基于 `package.json` 声明）。无版本相关 bug 命中。请求层/构建依赖见 F02/F07。

### 未发现
- 本模块所用依赖版本均与项目其他前端模块一致，无 F05 独有的过时/废弃依赖。

---

## `[Design]` 功能设计合理性

> 从单人维护的技术博客 + 每工作日 AI 日报场景出发，按 §2.5 相关问题审视。

**审视结论**：

1. **场景适配（§2.5-1）**：配置页对单人 admin 场景**整体合适**——按 group/sub 双层分组、据 inputType 渲染、敏感项脱敏、刷新缓存双向、恢复日报推荐源，覆盖了 crawler/日报链路的真实配置需求。但**失焦自动保存 + 批量保存双轨**对单人维护略显复杂：失焦保存适合"改一处即生效"，批量保存适合"调一整组再提交"，两者并存且都改 `originalData`，用户难以预判"此刻哪些已生效"。对单人场景，统一为一种保存模型更清晰。

2. **闭环完整性（§2.5-2）**：**配置变更无审计历史**是真实断层——admin 改了 `crawler.auth.api_key` 后链路异常，无法回溯"谁在何时改成了什么"，只能查数据库当前值（引用 B07-12）。`getAllConfigsForAdmin` 只返回当前快照，前端也无变更日志入口。对 crawler 链路排障这是真实痛点。

3. **可运维性（§2.5-3）**：刷新缓存按钮（`handleRefreshAll`）有确认对话框 + 文案说明"刷新 Java + Python + 连接池"，错误时 `ElMessage.error` 提示后端状态——可运维性尚可。但**刷新失败后无重试入口、无部分成功提示**（`refreshConfigs` 返回 `RefreshResult{message, components}`，前端只显示 message，不显示哪些 component 刷新成功/失败）。恢复日报推荐源同理，失败仅一句"恢复失败"。

4. **交互合理性（§2.5-6）**：代理页测速 UX 合理（颜色 tag、当前节点标记、不可达占位），但**订阅保存后无自动刷新分组**（`handleSaveSubscription` 成功只 toast，不触发 `fetchAll`，用户需手动点"刷新"看新节点），轻微反直觉。

### [Design/P4] [Design] 失焦自动保存 + 批量保存双轨并存，生效边界不清晰  <!-- 编号：F05-11 -->
- **定位**：`config/Index.vue:143-152`（失焦保存）+ `:154-175`（批量保存）+ `:261-268`（保存本组按钮）
- **现象**：文本/textarea/password 失焦即 `handleSave`（单条 PUT），switch `@change` 即保存；同时每个 section 有"保存本组"按钮（`handleSaveSection` 串行批量）。两条路径都更新 `originalData`。
- **影响**：admin 改 3 项后点"保存本组"，批量保存内部按"值变化"逐条 PUT——但前 2 项可能已因失焦保存过（`originalData` 已更新），导致批量保存只真正提交第 3 项。行为正确但用户无法从 UI 感知"哪些已生效"，误以为整组都未保存。
- **建议方向**：统一为"显式批量保存"（去掉失焦保存）或"失焦即存 + 去掉批量按钮"，二选一。（标改动面：小-中）
- **关联**：无

### [Design/P4] [Design] 刷新缓存结果未展示 components 明细，部分失败不可见  <!-- 编号：F05-12 -->
- **定位**：`config/Index.vue:56-64`（`handleRefreshAll`）、`api/config.ts:21-23`（`RefreshResult{message, components}`）
- **现象**：后端返回 `components: ["Spring Cache","Python Crawler","ConfigService","CrawlerTaskClient Pool"]`，前端只 `result.message`。
- **影响**：若 Python crawler 刷新失败但 Java 成功，后端可能仍返回 200 + message（需查证 B07），前端无法提示部分失败，admin 误以为全链路已刷新。
- **建议方向**：前端把 `components` 以列表/toast 形式展示，或后端返回逐组件成败状态。（标改动面：小）
- **关联**：[[C11]] / [需查证] 后端 `refreshAll` 是否在 Python 失败时仍返回 200

### [Design/P4] [Design] 代理订阅保存后不自动刷新分组列表  <!-- 编号：F05-13 -->
- **定位**：`proxy/Index.vue:76-86`（`handleSaveSubscription`）
- **现象**：保存订阅 URL 仅 toast，需手动点页面右上角"刷新"才重新拉取 groups。
- **影响**：admin 保存订阅后期望立即看到新节点，实际需两步操作，略反直觉。
- **建议方向**：保存成功后提示"是否立即更新订阅"，或自动触发 `handleRefreshSubscription` + 延迟刷新 groups。（标改动面：小）
- **关联**：无

---

## 模块小结

### 严重度统计

| 级别 | 数量 | 条目编号 |
|---|---|---|
| P0 | 0 | — |
| P1 | 0 | — |
| P2 | 2 | F05-01, F05-06 |
| P3 | 5 | F05-02, F05-03, F05-04, F05-05, F05-07, F05-08, F05-09 |
| P4 | 4 | F05-10, F05-11, F05-12, F05-13 |

> 注：P3 统计含 F05-02（批量保存串行，按影响也可归 P2，此处保守定 P3）；F05-04 经分析无实质 bug，仍登记以便复核。

### Top 风险（本模块最该先看的 ≤3 条）

1. **F05-06 敏感配置改写无二次验证** —— API key / callback key 仅靠 Sa-Token Cookie 鉴权即可一键改写，配合 B06 已知的 URL 前缀 + Cookie 薄弱点，是本模块最高安全风险（定 P2，未到 P1 因仍需先突破 admin 鉴权）。
2. **F05-01 password/文本失焦保存可清空关键配置** —— 误操作（清空失焦）会把敏感/关键 key 写成空串触发 crawler 链路中断，失焦保存无空值防护。
3. **F05-02 批量保存串行触发 N×后端重载链** —— 一个分组保存产生 N 次 Python HTTP + 3N 次 Java 重载，放大负载且部分失败无回滚。

### 修复优先级建议

- **立即**（P0/P1）：无。
- **计划**（P2）：
  - F05-01：失焦保存对敏感/关键 key 加空值防护（前端拦截 + 后端对关键 key 空值变更拒绝）
  - F05-06：敏感配置修改加二次验证（前端弹窗 + 后端要求旧值/二次密码）
- **择机**（P3/P4）：
  - F05-02：推动后端批量更新接口
  - F05-03/F05-05/F05-07：测速 merge、订阅 URL 前端校验
  - F05-08：统一 key 编码
  - F05-11/F05-12/F05-13：Design 层交互优化

### 排查盲区 / 待复核

- **[需查证]** F05-02：后端 `refreshAfterConfigChange` 对每条 `crawler.*` PUT 是否真的都触发 Python HTTP（`crawlerTaskClient.refreshConfig`）—— 代码上看是（`ConfigController:55,99-113`），但未运行验证；若 `ConfigService.reload()` 有节流则放大效应减弱。
- **[需查证]** F05-12：后端 `refreshAll`（`ConfigController:85-97`）在 `crawlerTaskClient.refreshConfig()` 抛异常时是否仍返回 200（异常是否被全局 handler 吞）—— 需 B07 / B16 确认 `CrawlerTaskClient` 的异常语义。
- **[需查证]** F05-06：当前线上是否启用了 HTTPS —— 若 admin 走 HTTP，敏感配置新值明文传输风险升级。需 X01（部署）/ X06（配置一致性）确认。
- **共享对象未深查**（按 §8.6 只引用）：AES 加密（B07）、Sa-Token 鉴权/CSRF（B06/F01）、SSRF 防护（B11）、schema inputType 列（B15）、请求层重试/401（F02）、crawler 配置刷新（C11）。
