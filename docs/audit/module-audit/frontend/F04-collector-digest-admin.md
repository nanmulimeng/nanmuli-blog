# F04 采集与日报管理页 排查报告

> **模块编号**：F04
> **排查范围**：admin 端采集任务（列表/详情/订阅源/转文章日志对话框/轮询）+ 日报管理（列表含优化看板集成/详情含诊断面板/手动触发）+ 前端 API 层 `api/collector.ts`
> **基线 commit**：`6ae930098405f4d0553d96a852f3345d0f39682e`
> **工作区状态**：脏（未提交改动均不在 `frontend/` 范围内，本模块代码与 HEAD 一致）
> **排查日期**：2026-06-24
> **排查人**：F04 排查 agent
> **状态**：草稿

---

## 模块概览

**职责**：为单人维护者提供采集与日报两大子系统的管理界面——查看采集任务进度、把 AI 整理结果转为文章/日志、管理订阅源、触发日报生成、监控日报质量与运行健康。是 admin 端最复杂、承载最多跨服务契约的页面集。

**关键文件**：

- `frontend/src/api/collector.ts:1-141` —— 采集 + 日报 + 优化 + 订阅源全部前端 API 封装（42 个函数）。
- `frontend/src/views/admin/collector/TaskList.vue:1-248` —— 采集任务列表（筛选/分页/轮询/重试/删除/创建对话框）。
- `frontend/src/views/admin/collector/TaskDetail.vue:1-466` —— 任务详情（轮询/转文章+日志对话框/诊断面板/AI 完整内容 v-html）。
- `frontend/src/views/admin/collector/SourceList.vue:1-417` —— 订阅源管理（CRUD/启停/质量建议/test 连通性测试）。
- `frontend/src/views/admin/digest/List.vue:1-607` —— 日报列表 + 优化看板集成（质量概览/弱维度/搜索反馈/运行时健康/调度诊断/手动触发）。
- `frontend/src/views/admin/digest/Detail.vue:1-691` —— 日报详情（质量评估/板块质量/来源诊断/下次优化动作/orchestrator plan/event diagnostics/optimization outcome/搜索诊断/AI 摘要/结构化板块/完整内容 fallback）。
- `frontend/src/composables/usePolling.ts:1-70` —— 递归 setTimeout 轮询 composable，4 个页面共用。
- `frontend/src/components/collector/ConvertArticleDialog.vue:1-86` / `ConvertDailyLogDialog.vue:1-116` / `TaskCreateDialog.vue:1-198` —— 三个对话框组件。
- `frontend/src/types/collector.ts:1-621` —— 采集+日报+优化+订阅源全部 TS 类型与枚举（含 snake_case/camelCase 混用）。

**对外接口 / 依赖**：

- 对外：无（消费方），仅被 `router/routes.ts` 引用为 admin 路由组件。
- 依赖后端：`WebCollectorController`（B08 采集/转文章/订阅源/重试、B10 日报透传 `/digest/*` `/optimization/*`）。
- 依赖 crawler（经后端透传）：日报/优化/调度/搜索反馈/运行时健康 6 类端点。
- 共享前端模块：`utils/request.ts`（F02）、`utils/markdown.ts`+`utils/sanitize.ts`（F03）、`utils/url.ts`、`composables/usePolling.ts`、`router/guards.ts`（F01）。

**已读文件清单**：

- `api/collector.ts` —— 通读
- `views/admin/collector/TaskList.vue` —— 通读
- `views/admin/collector/TaskDetail.vue` —— 通读
- `views/admin/collector/SourceList.vue` —— 通读
- `views/admin/digest/List.vue` —— 通读
- `views/admin/digest/Detail.vue` —— 通读
- `composables/usePolling.ts` —— 通读
- `components/collector/{ConvertArticleDialog,ConvertDailyLogDialog,TaskCreateDialog}.vue` —— 通读
- `utils/{request,sanitize,url,markdown}.ts` —— 通读
- `types/collector.ts` —— 通读
- `constants/api.ts` —— 通读
- `router/routes.ts`（F04 相关段） —— 通读
- `interfaces/rest/WebCollectorController.java`（trigger/runtime/optimization 透传段） —— 片段
- `application/webcollector/dto/{CollectTaskDTO,CollectTaskListDTO}.java` —— 仅 grep 字段
- `views/digest/Detail.vue`（公开页，对比轮询实现） —— 片段

**主模块归属**：本模块深查 admin 采集与日报管理页。后端接口契约 → 引用 B08（采集编排）/B10（日报透传）；请求层 → 引用 F02；Markdown 渲染与 XSS → 引用 F03；路由守卫 → 引用 F01；优化看板数据来源 → 引用 C06/C07。跨服务契约一致性（§2.6 横向主题）为本模块重点贡献视角。

---

## `[Bug]` 代码正确性与潜在缺陷

> 排查范围：4 个 admin 页面 + 3 个对话框 + usePolling + api/collector.ts 的控制流、轮询生命周期、表单校验、状态管理、错误处理。逐条对照 §2.1。

### [P2] [Bug] 日报列表页冷加载后轮询不重启，进行中日报进度不自动刷新 <!-- 编号：F04-01 -->

- **定位**：`frontend/src/views/admin/digest/List.vue:40-52`（`fetchData`）+ `:235-247`（`usePolling` + `onMounted`）+ 对比 `views/admin/collector/TaskList.vue:39-41`
- **现象**：`List.vue` 的 `fetchData()` 拿到 `digests.value` 后**不检查是否需要重启轮询**；`onMounted` 顺序是 `fetchData()`（async，未 await）后立即 `startPolling()`。由于 `usePolling` 用 `immediate: false`，`start()` 设一个 5s 后触发的 `setTimeout(poll)`；5s 后 `poll()` 先跑 `condition()`，此时若 `digests` 为空或无进行中日报，`hasActiveTasks()` 返回 false，`poll()` 调用 `stop()` 终止轮询并清 timer。
- **影响**：页面冷加载时后台**已有进行中的日报任务**（如刚触发或工作日定时触发的 `status=0/1/2` 日报），用户进入日报列表页后，列表的状态/进度**永远不会自动刷新**，必须手动 F5。这与采集任务列表 `TaskList.vue` 的行为不一致（后者 `fetchData` 末尾 `if (hasActiveTasks()) nextTick(() => startPolling())` 每次拉取后重新评估）。
- **根因/分析**：`List.vue` 的 `fetchData` 缺少 `TaskList.vue` 中对应的重启逻辑。`handleTrigger` 成功路径有 `setTimeout(() => { fetchData(); ...; startPolling() }, DELAY.DIGEST_REFRESH)`（`:131`），那条路径能启动轮询；但**冷加载路径**和**翻页路径**（`handlePageChange` → `fetchData`）都漏了。已排除误判：`usePolling` 的 `start()` 在 `timer !== null` 时 no-op，所以即使多次调用也安全，缺失的不是调用次数而是"数据回来后评估重启"这一步。
- **修复方向**：① 在 `List.vue` 的 `fetchData` 末尾仿照 `TaskList.vue` 增加 `if (hasActiveTasks()) nextTick(() => startPolling())`；或 ② 更稳妥地在 `usePolling` 内部提供 `restart()` 语义并让消费方在数据变化后调用。（改动面：小）
- **关联**：与 F04-02 同属轮询资源管理主题。

### [P2] [Bug] `triggerDigest` 响应字段 `status === 'created'` 为前端硬编码契约，crawler 侧返回值漂移将致静默走 warning 分支 <!-- 编号：F04-02 -->

- **定位**：`frontend/src/views/admin/digest/List.vue:125`（`if (res.status === 'created')`）+ `frontend/src/api/collector.ts:68`（TS 声明 `{ status: string; message: string; task_id?: number }`）+ `backend/.../WebCollectorController.java:304-311`（`Result<Object>` 透传）
- **现象**：前端 `handleTrigger` 依据 `res.status === 'created'` 区分"已触发，跳转/刷新"与"已跳过，提示 warning"。后端 `triggerDigest` 返回 `Result<Object>`，`Object` 是 crawler `/api/v1/digests/trigger` 的原始透传结果，后端不做 DTO 校验。前端 TS 类型 `{ status, message, task_id? }` 是**单方面假设**。
- **影响**：若 crawler 实际返回 `status` 取值为 `'ok'`/`'success'`/`'pending'`/`'queued'` 等非 `'created'` 字符串，前端**始终走 else 分支**，显示 `ElMessage.warning(res.message)`，既不导航到任务详情页、也不启动进度轮询——用户以为"触发失败/被跳过"，但后端实际可能正在生成。`task_id` 字段同理：若 crawler 用 `taskId`（camelCase）返回，前端 `res.task_id` 为 undefined，跳转失效。
- **根因/分析**：B10 透传链路对 crawler 响应零约束，前端硬编码字符串枚举。这是 §2.6 跨服务契约一致性横向主题在 F04 的典型表现。`[需查证]`：crawler `digests/trigger` 实际返回的 `status` 取值集合（应在 C04 报告或 crawler 源码确认）。
- **修复方向**：① 在 crawler 侧固化响应 schema（`status ∈ {created, skipped, ...}`、`task_id` snake_case）并在两端共享类型；② 前端放宽判定为 `res.task_id != null`（有任务 id 即视为已创建），用 `task_id` 存在性替代字符串匹配；③ 后端透传层加最小校验。（改动面：中，跨服务）
- **关联**：跨服务契约横向主题（§2.6）；crawler 侧归属 C04。

### [P3] [Bug] TaskDetail.vue 的 `taskId` 在 setup 顶层固定，同组件内 params 变化不更新 <!-- 编号：F04-03 -->

- **定位**：`frontend/src/views/admin/collector/TaskDetail.vue:21`（`const taskId = route.params.id as string`）+ `:2`（仅 import `computed, onMounted, ref`，无 `watch`）
- **现象**：`taskId` 是非响应式常量，取自 `route.params.id`。组件无 `watch(() => route.params)`。对比 `views/admin/digest/Detail.vue:28-31` 用 `computed` 取 route.params，且 `:214-220` 有 watch 处理同组件参数变化。
- **影响**：正常用户路径（列表 → 详情 → 返回列表 → 另一任务详情）因中间经过列表页（不同 component）会重新 mount，不受影响。但**编程式导航**（如某处 `router.push('/admin/collector/2')` 从 `/admin/collector/1` 直接跳）或**浏览器地址栏改 id 回车**会复用组件，`taskId` 不变，`fetchTask` 仍请求旧 id，显示错误数据且无报错。当前代码无此调用路径，但留下了隐患。
- **根因/分析**：setup 顶层取一次性 params 是 Vue Router 复用组件时的常见陷阱。已排除误判：检查确认无任何 `router.push('/admin/collector/:其他id')` 的同组件跳转，故降为 P3。
- **修复方向**：① 把 `taskId` 改为 `computed(() => route.params.id as string)` 并加 `watch(taskId, fetchTask)`；或 ② 在 `router/routes.ts` 给该路由加 `:key` 强制 remount。（改动面：小）
- **关联**：与 Detail.vue（日报）的严谨写法形成对比，同模块内一致性技术债。

### [P3] [Bug] `handleTrigger` 的"今日已有日报"判断用浏览器本地日期匹配服务端日期，跨日/时区边界可能误判 <!-- 编号：F04-04 -->

- **定位**：`frontend/src/views/admin/digest/List.vue:106-108`（`const today = ...; const todayDigest = digests.value.find(d => d.digest_date?.startsWith(today) && d.status === 3)`）
- **现象**：用 `new Date()` 取浏览器本地日期拼 `YYYY-MM-DD`，与列表中日报的 `digest_date` 做 `startsWith`。`digest_date` 由 crawler 按其服务器时区生成。
- **影响**：浏览器时区与 crawler 服务器时区不一致时（如用户在 UTC+0、crawler 在 UTC+8），跨日窗口（本地 23:30 vs crawler 次日 07:30）会误判"今日已有/无日报"，导致 force 重新生成确认框的错误弹出或缺失。属低频边界。
- **根因/分析**：前端无法获知 crawler 时区，纯客户端判断固有局限。已排除误判：即便误判，force 选项走 confirm 二次确认，不会直接损坏数据。
- **修复方向**：① 将"今日是否已有日报"判断下沉到后端/crawler trigger 端点（其本身已支持 force 参数，由后端权威判定）；前端仅依据响应 message 提示。② 维持现状但注释标注时区假设。（改动面：小到中）
- **关联**：时区处理是项目级隐式约定（§2.3）。

### [P3] [Bug] SourceList test 连通性可能长时间 loading，无超时/进度提示 <!-- 编号：F04-05 -->

- **定位**：`frontend/src/views/admin/collector/SourceList.vue:129-145`（`handleTest`）+ `frontend/src/api/collector.ts:138-140`（`testSource` 无自定义 timeout）
- **现象**：`testSource` 走 `/admin/collector/source/{id}/test` → 后端透传 crawler 实际爬取测试。前端请求 timeout 统一 30s（`REQUEST_TIMEOUT`），且 F02-01 指出 5xx 会自动重试 3 次（1+2+4s 退避）。爬取测试若耗时较长或 crawler 5xx，`testingId === row.id` 的 loading 态可能持续 30s+，用户只看到按钮转圈，无进度/超时提示。
- **影响**：用户以为卡死，可能重复点击（每次点击触发新请求，旧的被 F02-02/F02-03 的 abort 机制取消，但 loading 状态由 `testingId` 单值控制，重复点同一行不会叠加）。体验差但无数据风险。
- **根因/分析**：长耗时操作复用通用请求层，未单独配置更长 timeout 或禁用重试。与 F02-05（timeout 30s vs nginx 300s）同源。
- **修复方向**：① 给 `testSource` 传 `skipRetry`（需 F02 扩展）或自定义 `timeout: 120000`；② 测试中显示已耗时秒数；③ 后端 test 端点改为异步任务 + 轮询结果（与采集任务一致的模式）。（改动面：小到中）
- **关联**：F02-01（POST 重试）、F02-05（timeout 不匹配）。

### [P3] [Bug] 转换对话框加载分类列表失败被静默吞掉，用户看不到分类下拉 <!-- 编号：F04-06 -->

- **定位**：`frontend/src/components/collector/ConvertArticleDialog.vue:26-29`（`try { categories = await getLeafCategoryList() } catch { /* non-critical */ }`）+ `ConvertDailyLogDialog.vue:38-42`（同模式）
- **现象**：两个转换对话框在 `@open` 时拉取叶子分类，失败时 catch 空体，仅 `ElMessage.error` 由 request 拦截器全局弹出（若未 skipErrorMessage）。分类下拉为空，用户无法选分类（分类本就是可选字段，转换不阻断）。
- **影响**：分类接口异常时用户可继续提交（categoryId 留空），但下拉空白无任何"加载失败"提示，体验断层。request 全局 ElMessage 会弹一次，但对话框内无上下文。
- **根因/分析**：`/* non-critical */` 注释表明有意降级，但未给用户对话框内的可见提示。
- **修复方向**：① catch 中在对话框内显示"分类加载失败，可手动重试"小字 + 重试按钮；或 ② 保持现状但确认全局 ElMessage 足够。（改动面：小）
- **关联**：无。

### [P3] [Bug] ConvertArticleDialog 标题字段无前端校验，依赖后端兜底 <!-- 编号：F04-07 -->

- **定位**：`frontend/src/components/collector/ConvertArticleDialog.vue:52-64`（`el-form` 无 `ref`/`rules`/`prop`，无 `validate` 调用）+ `:32-42`（`handleSubmit` 直接 `convertToArticle`）
- **现象**：表单未声明校验规则，提交时不调 `formRef.validate()`。标题留空依赖后端用 AI 标题兜底（`:62-63` 注释"留空则使用 AI 生成标题"）。`ConvertDailyLogDialog` 同样无校验，但 logDate 默认填今天，风险低。
- **影响**：若后端校验失败（如标题超长、含非法字符），前端无前置拦截，错误经 request 全局提示。功能可用但交互不友好。
- **根因/分析**：表单字段大多可选，设计上靠后端兜底。属交互优化项。
- **修复方向**：加 `maxlength` 提示与基本格式校验（标题非空时长度上限）。（改动面：小）
- **关联**：无。

### 未发现

- **轮询资源泄漏**：`usePolling` 在 `onUnmounted(() => stop())`（`:67`）清理 timer，4 个页面卸载时均会停止轮询；`poll()` 内 `if (running) return` 防堆叠；递归 setTimeout 在 `await fn()` 完成后才调度下一轮（`:42-45`）。未发现请求堆叠或 timer 泄漏。
- **终态停止轮询**：`TaskDetail.fetchTask`（`:90-91`）与 `Detail.vue` 轮询 condition（`:33-36`）在任务进入终态（status=3/4）时正确停止。
- **重复提交**：三个对话框用 `loading` ref + 按钮 `:loading` 绑定防重复；`handleTrigger` 用 `triggerLoading`；`handleTest` 用 `testingId` 单值。防重复机制覆盖到位（`loading` 在 `finally` 重置，即使异常也可恢复）。

---

## `[Security]` 安全漏洞

> 排查范围：XSS（v-html 渲染 ai_full_content/rawMarkdown）、外部链接（a href）、订阅源 value 注入、转文章/日志的表单输入。逐项对照 §2.2。XSS 主维度归 F03，本节仅记 F04 视角。

### 未发现（F04 视角新增）

- **v-html XSS**：F04 共 4 处 `v-html="sanitize(renderMarkdown(...))"`（`TaskDetail.vue:370,434`、`Detail.vue:673`、公开页 `digest/Detail.vue`），全部先 `renderMarkdown` 再 `sanitize`（DOMPurify）。净化主问题归 F03-06/07/09（allowlist 放行 class+id、markdown-it html:true、链接协议过滤不一致），F04 仅是消费方，**无新增安全问题**。
- **外部链接**：所有 `<a :href>` 均经 `safeExternalUrl()`（`utils/url.ts`）过滤为 http/https 且加 `rel="noopener noreferrer"`（`TaskDetail.vue:212-215,392-396`、`Detail.vue:647-650,370-372,488-494`）。未发现 `javascript:` 残留。
- **订阅源 value**：`SourceList.vue` 创建/编辑表单的 `value`（URL/keyword/RSS）提交给后端，前端不做 URL 协议校验（与 `safeExternalUrl` 不同），但 SSRF 防护在 crawler `ssrf_guard`（C01），前端非责任层。
- **表单输入**：转换对话框、订阅源表单均走 axios JSON body，无 SQLi/模板注入面。
- **鉴权**：所有 F04 API 均在 `/admin/**` 前缀下（`api/collector.ts` 全部 `/admin/collector/*`），由 SaToken 路由拦截器统一保护（B06 主题，F01-06 引用）。前端 `requiresAuth: true` meta 已配（`routes.ts:160,166,172,178,184,190,196`）。

---

## `[Arch]` 架构与技术债

> 排查范围：文件规模、职责拆分、composable 复用、命名一致性、跨服务契约透传模式。共享对象按 §8.6 归属，非主模块只引用。

### [P2] [Arch] 日报 List.vue 单文件 607 行承载 5 个独立数据源 + 优化看板，职责过重 <!-- 编号：F04-08 -->

- **定位**：`frontend/src/views/admin/digest/List.vue:1-607`
- **现象**：单文件同时承担：①日报列表（fetchData/分页）；②调度状态（fetchSchedulerStatus + diagnostics 渲染）；③质量概览（fetchQualityOverview + 弱维度/建议）；④搜索反馈（fetchSearchFeedback + 板块/引擎/零结果）；⑤运行时健康（fetchRuntimeHealth + checks/recommendations）；⑥手动触发（handleTrigger + force 流程）。7 个 label/format 函数（sectionLabel/dimensionLabel/schedulerStateLabel 等）+ 6 个 tagType 函数内联。模板里有 5 个独立的 `v-if` 看板区块。
- **影响**：可维护性差——任一看板的数据字段或展示调整都要改这个 607 行文件；新人定位特定看板逻辑需全文扫描；5 个 fetch 并发触发（`:240-246`）任一失败都覆盖同一个 `loadError`（见 F04-11）。
- **根因/分析**：优化看板（质量/搜索反馈/运行时健康）是后期逐步叠加到日报列表页的，未抽 composable。已知线索 §9 "优化看板无独立入口"是相邻设计问题，本条聚焦实现层职责膨胀。
- **修复方向**：① 抽 `useDigestOptimizationPanel()` composable 封装 4 个优化数据源 fetch + computed；② 抽 `DigestOptimizationPanel.vue` 子组件承载 5 个看板区块模板；③ List.vue 回归"列表 + 触发 + 调度状态"本职。（改动面：中）
- **关联**：F04-13（优化看板无独立入口，Design）；§9 已知线索。

### [P2] [Arch] 日报 Detail.vue 单文件 691 行，诊断面板字段与 crawler 透传 JSON 深度耦合 <!-- 编号：F04-09 -->

- **定位**：`frontend/src/views/admin/digest/Detail.vue:1-691`
- **现象**：文件内联 9 个区块：失败诊断 / 今日亮点 / 质量评估（总分+维度+板块质量+来源诊断+下次优化动作+成品质量+建议）/ orchestrator plan log / event merge diagnostics / optimization action outcome / search diagnostics / AI 摘要 / 结构化板块 / 完整内容 fallback。大量 computed（`:39-74` 共 12 个）深度解构 `orchestrator_plan` 的嵌套结构（`plan.search_diagnostics`、`plan.event_diagnostics.sample_events`、`plan.optimization_action_outcome.action_snapshot` 等）。
- **影响**：crawler 侧 orchestrator_plan 结构任何调整（字段增删/嵌套层级变化）都会波及此文件多处 computed 与模板。可维护性与跨服务耦合双重压力。
- **根因/分析**：诊断面板本质是 crawler 内部观测数据的"直显示"，未做前端视图模型抽象。`orchestrator_plan` 类型定义为 `string[] | DigestOrchestratorPlan | null`（`types/collector.ts:125`），联合类型加剧 computed 内的类型守卫负担（`:49-63` 多处 `Array.isArray(plan)` 判断）。
- **修复方向**：① 按区块拆子组件（QualityEvaluation / EventDiagnostics / OptimizationOutcome / SearchDiagnostics）；② 定义专门的 ViewModel 并在后端透传层或前端做一次归一化映射，隔离 crawler 结构变化。（改动面：中到大）
- **关联**：跨服务契约横向主题（§2.6）。

### [P2] [Arch] 前端模块内 snake_case（日报/优化）与 camelCase（采集任务/订阅源）命名风格混用 <!-- 编号：F04-10 -->

- **定位**：`frontend/src/types/collector.ts` —— 采集任务侧 camelCase（`CollectTask.aiTitle`/`progressPercent`/`completedPages` `:46-48`、`CollectTaskListDTO` 同），日报/优化侧 snake_case（`DigestListItem.digest_date`/`ai_title`/`status_label` `:99-109`、`DigestDetail.ai_full_content`/`ai_duration`/`ai_tokens_used` `:120-122`、`DigestQualityEvaluation` 全 snake_case）。
- **现象**：同一 `types/collector.ts` 文件、同一 `api/collector.ts` 模块、同一 F04 页面集，两种命名风格并存。根因是数据来源不同：采集任务由 backend Java DTO 序列化（Jackson 默认 camelCase），日报/优化由 crawler Python 经 backend 透传（snake_case 原样穿透）。
- **影响**：开发认知负担——写日报相关代码要切换到 snake_case，写采集任务代码切回 camelCase；字段名拼写错误（如 `digest_date` 误写 `digestDate`）不会被 TS 在跨边界处捕获（因为透传层是 `Object`）。`handleView`（`List.vue:96-101`）混用 `row.status`（数字）、`row.ai_title`、`row.digest_date` 三种风格于一处。
- **根因/分析**：B10 透传层零转换是根本原因（B10 主模块职责）。前端无法单方面统一，除非后端透传层做 key 转换或 crawler 侧改 camelCase。
- **修复方向**：① 后端透传层（B10）统一转为 camelCase；或 ② 前端定义归一化映射层；或 ③ 接受现状但在 types 文件加分隔注释与 ESLint 规则。（改动面：中，跨服务）
- **关联**：跨服务契约横向主题（§2.6）；根因在 B10。

### [P3] [Arch] usePolling 仅暴露 start/stop，无 restart 语义，消费方需自行 nextTick 重启 <!-- 编号：F04-11 -->

- **定位**：`frontend/src/composables/usePolling.ts:48-65`
- **现象**：`start()` 在 `timer !== null` 时直接 return（`:49`），无法显式"无论当前状态都重新启动"。`TaskList.vue:39-41` 为此用 `nextTick(() => startPolling())` 配合 `stop()` 的副作用（condition 失败时 poll 内部调 stop 清 timer）实现重启。`List.vue` 漏掉这一步即成 F04-01 Bug。
- **影响**：API 语义不够清晰，消费方易遗漏重启路径（F04-01 即实例）。`immediate: false` + condition 自停止的设计需要消费方理解内部状态机。
- **根因/分析**：设计上 start 幂等（防重复启动）是合理的，但缺少显式 restart 导致使用陷阱。
- **修复方向**：增加 `restart(): void { stop(); start() }` 并鼓励消费方在数据变化后调用；或在 start 内部判断"若 running 但 timer 为 null"也重新调度。（改动面：小）
- **关联**：F04-01。

### 未发现

- **循环依赖 / 上帝类**：F04 无 service/store 类，均为页面组件 + 纯函数 API 封装，未发现分层违反。
- **重复实现**：`List.vue` 与 `Detail.vue` 各自定义 `dimensionLabel`/`sectionLabel`/`formatScore`/`formatPercent`/`scoreTagType`（`:113-228`），存在重复但量小，未达独立条目阈值（可归入 F04-08/F04-09 拆分时一并处理）。

---

## `[Deps]` 依赖升级与版本

### 本模块依赖清单（基于 `frontend/package.json`，未翻依赖源码）

| 依赖 | 版本 | 声明位置 | 已知风险/可升级 | 备注 |
|---|---|---|---|---|
| vue | ^3.4.15 | `package.json:24` | 3.4→3.5 已发布 | F04 用 `<script setup>`、`defineModel`、`computed`、`watch`，3.5 兼容 |
| element-plus | ^2.5.1 | `package.json:18` | 2.5→2.8+ | F04 大量用 `el-table`/`el-dialog`/`el-tag`/`el-collapse`/`el-tabs`/`el-pagination`/`el-input-number`/`el-date-picker`/`el-radio-group`/`el-progress`/`el-alert`/`el-switch`/`el-empty`，2.5 API 稳定 |
| @element-plus/icons-vue | ^2.3.1 | `package.json:14` | 稳定 | F04 用 Plus/Delete/Refresh/Search/View/Document/Notebook/ArrowLeft/Edit/VideoPlay/Calendar/Promotion/Timer/DataAnalysis |
| axios | ^1.6.5 | `package.json:16` | 见 F02-11 | F04 不直接用，经 `utils/request.ts` |
| markdown-it | ^14.2.0 | `package.json:20` | 见 F03-13 | F04 经 `renderMarkdown` |
| dompurify | ^3.4.11 | `package.json:17` | 见 F03 | F04 经 `sanitize` |

> 排查范围：仅 `frontend/package.json` 中 F04 实际用到的依赖。依赖声明与 lockfile 偏差、废弃类型包等横向问题归 F03（@types/dompurify/@types/markdown-it）与 F07（构建与依赖主模块），本模块不重复。

### 未发现

F04 视角无新增依赖问题。axios/markdown-it/dompurify 的版本问题已在 F02-11、F03-13/14/15 记录，F04 仅引用。

---

## `[Design]` 功能设计合理性

> **必填**。从单人维护的技术博客 + 每工作日 AI 日报场景出发，回答 §2.5 相关问题。

**审视结论**：

1. **场景适配（§2.5-1）**：采集 + 日报 + 优化看板三套能力塞进 admin 端是合理的（单人维护者一站式），但优化看板（质量概览/搜索反馈/运行时健康/调度诊断）的**展示密度对单人场景偏重**——单人维护者更关心"今天日报生成成功了吗、失败原因是什么"，而非每次进列表页都被 5 个看板的指标轰炸。看板更适合作为"按需展开"或独立诊断入口。
2. **闭环完整性（§2.5-2）**：采集→转文章/日志闭环完整（TaskDetail 有转换入口 + 成功后 articleId 回填 + 跳转编辑）。日报闭环**缺人工干预入口**：日报生成失败后，List.vue/Detail.vue 都只能"查看诊断"，**无"重试本次日报生成"按钮**（handleTrigger 只能 force 重新生成今日，不能按特定失败任务重试）；质量评估的"下次优化动作"（skip/deprioritize 源）只展示不可人工覆盖。
3. **可运维性（§2.5-3）**：诊断信息丰富（失败 category/stage/signals/action_hint、orchestrator plan log、event diagnostics、search diagnostics），定位能力强。但**无前端侧的重试/回滚操作**——采集任务有重试（TaskList/TaskDetail），日报失败只能去后端/crawler 侧处理，断层明显。

### [P4] [Design] 优化看板无独立入口，强制叠加在日报列表页 <!-- 编号：F04-12 -->

- **定位**：`frontend/src/views/admin/digest/List.vue:283-516`（5 个看板区块）+ `router/routes.ts`（无 `/admin/optimization` 或类似独立路由）
- **现象**：质量概览、调度诊断、搜索反馈、运行时健康 4 类看板 + 调度状态条全部渲染在日报列表页顶部，列表表格被推到下方。用户每次进列表页都要滚动越过看板才能看到日报列表本身。
- **影响**：日常使用中"看日报列表"与"诊断优化系统"两种不同心智的任务被混在一页，视觉噪音大；看板数据 5 个并发请求（`:240-246`）拖慢列表页首屏。
- **建议方向**：将优化看板拆为独立路由（如 `/admin/optimization`）或在列表页用 `el-collapse` 默认折叠、提供"展开诊断"开关。列表页只保留调度状态条 + 列表 + 触发按钮。（改动面：中）
- **关联**：§9 已知线索（优化看板无独立入口）；F04-08（实现层职责膨胀）。

### [P4] [Design] 日报失败缺"按任务重试"入口，只能 force 重新生成今日 <!-- 编号：F04-13 -->

- **定位**：`frontend/src/views/admin/digest/List.vue:103-141`（`handleTrigger` 仅 force=true/false 二选一，无按 task_id 重试）+ `Detail.vue`（无重试按钮）
- **现象**：采集任务在 TaskList/TaskDetail 都有"重试"按钮（`retryCollectTask`）。但日报任务失败后，前端无对应重试入口。`handleTrigger` 调的是 `/digest/trigger`（生成新日报），不是重试特定失败任务。Detail.vue 的诊断面板只展示 `action_hint` 文本，无操作按钮。
- **影响**：工作日定时日报失败时，单人维护者要么 force 重新生成（可能丢掉已采集的中间结果）、要么登录 crawler 后端处理。运维断层。
- **建议方向**：① 在 Detail.vue 诊断面板加"按 task_id 重试"按钮（需 crawler/B10 提供重试端点）；或 ② 明确设计为"日报失败一律 force 重新生成"并在 UI 文案中讲清。（改动面：中，需后端配合）
- **关联**：闭环完整性（§2.5-2）；crawler 侧归属 C04。

### [P4] [Design] 轮询间隔固定 5s，无自适应或可见性感知 <!-- 编号：F04-14 -->

- **定位**：`frontend/src/constants/api.ts:52-56`（`POLLING_INTERVAL.TASK_STATUS=5000`、`DIGEST_STATUS=5000`）+ `composables/usePolling.ts`
- **现象**：所有采集/日报轮询固定 5s。无 Page Visibility API 感知（标签页切后台仍轮询）、无指数退避（任务长时间 running 时仍每 5s 查）、无根据剩余进度调整。
- **影响**：单人场景影响有限，但浏览器后台 tab 持续轮询白白消耗后端配额（crawler 的 rate limit、后端 DB 查询）。长耗时任务（深度爬取/AI 整理数分钟）5s 轮询频率偏高。
- **建议方向**：① 加 `document.hidden` 感知，后台 tab 暂停或降频；② 任务进入 PROCESSING（AI 整理）阶段后自动拉长间隔到 15-30s。（改动面：小到中）
- **关联**：F04-01/F04-11（轮询资源管理主题）。

---

## 模块小结

### 严重度统计

| 级别 | 数量 | 条目编号 |
|---|---|---|
| P0 | 0 | — |
| P1 | 0 | — |
| P2 | 5 | F04-01、F04-02、F04-08、F04-09、F04-10 |
| P3 | 6 | F04-03、F04-04、F04-05、F04-06、F04-07、F04-11 |
| P4 | 3 | F04-12、F04-13、F04-14 |

合计 14 条。

### Top 风险（本模块最该先看的 ≤3 条）

1. **F04-01 日报列表页冷加载后轮询不重启** —— 直接影响核心体验（进行中日报进度不刷新），改动面小、收益明确，应最先修。
2. **F04-02 triggerDigest 响应字段硬编码契约** —— 跨服务契约风险，crawler 侧 status 取值漂移会导致用户以为触发失败，需对照 C04 确认 `[需查证]`。
3. **F04-08/F04-09 大文件职责过重（607/691 行）** —— 可维护性，后续任何看板/诊断调整都卡在这两个文件，应规划拆分。

### 修复优先级建议

- **立即**（P0/P1）：无。
- **计划**（P2）：
  - F04-01（轮询重启，改动面小，先修）
  - F04-02（跨服务契约，需联合 C04/B10 确认 schema 后统一）
  - F04-10（命名风格统一，需 B10 透传层配合）
  - F04-08/F04-09（大文件拆分，作为重构批次）
- **择机**（P3/P4）：
  - F04-03/F04-04/F04-05/F04-06/F04-07/F04-11（边缘 Bug 与体验优化）
  - F04-12/F04-13/F04-14（设计建议，结合优化看板独立入口、日报重试入口、轮询自适应一起规划）

### 排查盲区 / 待复核

- **[需查证] F04-02**：crawler `/api/v1/digests/trigger` 实际返回的 `status` 取值集合与 `task_id` 字段命名（snake_case vs camelCase），需对照 C04 报告或 crawler `digest_orchestrator.py` 源码确认。直接影响前端 `res.status === 'created'` 判定是否成立。
- **[需查证]**：F04-10 命名风格混用的根因（B10 透传层是否做过任何 key 转换）需在 B10 报告确认；若 B10 已有转换逻辑则本条结论需修正。
- **未覆盖**：`components/collector/TaskStatusTag.vue`/`TaskTypeTag.vue`/`CrawlProgress.vue`/`TaskCreateDialog.vue` 的模板细节未逐行审（已确认存在与基本职责，无异常迹象但非地毯式）。
- **未覆盖**：admin 端 F04 页面与公开端 `views/digest/*`、`views/collector/*`（若存在公开采集页）的代码复用关系未深查（公开页轮询用手动 setTimeout 与 admin 的 usePolling 不一致，归 F03/公开页模块）。
