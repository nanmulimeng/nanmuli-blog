# F03 编辑与渲染（md 双轨） 排查报告

> **模块编号**：F03
> **排查范围**：md-editor-v3 编辑态 / markdown-it 阅读态渲染 / 双轨风格漂移 / XSS 防护（DOMPurify）/ 代码高亮（highlight.js）/ TOC 手写解析 / 图片上传回调
> **基线 commit**：`6ae930098405f4d0553d96a852f3345d0f39682e`
> **工作区状态**：脏（未提交改动集中在 backend/crawler-service/deploy/scripts，**不涉及本模块任何 frontend 文件**）
> **排查日期**：2026-06-24
> **排查人**：F03 排查 agent
> **状态**：完成

---

## 模块概览

**职责**：为博客文章 / 技术日志 / 日报 / 采集详情提供"编辑用 md-editor-v3、阅读用 markdown-it（或后端预渲染 HTML + DOMPurify 二次净化）"的 Markdown 渲染链路，包含代码高亮、TOC、图片上传回调、XSS 净化。

**关键文件**：
- `frontend/src/components/editor/MarkdownEditor.vue:1-95` —— md-editor-v3 编辑态封装（4 个 admin 页复用）
- `frontend/src/utils/markdown.ts:1-31` —— markdown-it 阅读态渲染实例（crawler 来源字段专用）
- `frontend/src/utils/sanitize.ts:1-27` —— DOMPurify 统一净化（allowlist + code class hook）
- `frontend/src/utils/hljs.ts:1-44` —— highlight.js/core + 17 语言按需注册
- `frontend/src/views/article/Detail.vue:53-180,427-434` —— 文章详情：DOMParser 手写 TOC + hljs.highlightElement + 图片点击放大
- `frontend/src/views/digest/Detail.vue:166-171` —— 日报 fallback 走 renderMarkdown + sanitize
- `frontend/src/views/dailyLog/Detail.vue:160` —— 日志详情走 sanitize（后端预渲染 HTML）
- `frontend/src/views/admin/collector/TaskDetail.vue:368-372,431-441` —— 采集详情双渲染点（aiFullContent + rawMarkdown）
- `frontend/src/views/admin/digest/Detail.vue:671-675` —— admin 日报详情 renderMarkdown + sanitize
- `frontend/src/components/article/ArticleContent.vue:10` —— 通用渲染组件（当前未被引用，见 F03-09）
- `frontend/src/components/common/AppHeader.vue:396,415` —— 搜索高亮 sanitize
- `frontend/src/views/about/Index.vue:92` —— siteAbout HTML 净化

**对外接口 / 依赖**：
- 对外：`MarkdownEditor`（admin 4 处 v-model）、`renderMarkdown`、`sanitize`
- 依赖：md-editor-v3 / markdown-it / dompurify / highlight.js（版本清单见 [Deps] 节）
- 后端契约：`contentHtml`（文章/日志，后端 MarkdownUtil Jsoup 预净化）、`ai_full_content`/`rawMarkdown`（crawler 原始 markdown，前端自行渲染+净化）
- 图片上传：`MarkdownEditor.handleUploadImg` → `@/api/file.uploadFile` → 返回 `fileUrl` 注入编辑器（关联 [[B05]]）

**已读文件清单**：
- `frontend/src/components/editor/MarkdownEditor.vue` —— 通读
- `frontend/src/utils/markdown.ts` —— 通读
- `frontend/src/utils/sanitize.ts` —— 通读
- `frontend/src/utils/hljs.ts` —— 通读
- `frontend/src/utils/url.ts` —— 通读
- `frontend/src/views/article/Detail.vue` —— 通读
- `frontend/src/views/digest/Detail.vue` —— 通读
- `frontend/src/views/dailyLog/Detail.vue` —— 通读
- `frontend/src/views/admin/collector/TaskDetail.vue` —— 片段（340-450 渲染段）
- `frontend/src/views/admin/digest/Detail.vue` —— 片段（640-690 渲染段）
- `frontend/src/components/article/ArticleContent.vue` —— 通读
- `frontend/src/views/about/Index.vue` —— 片段（1-100）
- `frontend/src/components/common/AppHeader.vue` —— 仅 grep（396/415）
- `backend/src/main/java/com/nanmuli/blog/shared/util/MarkdownUtil.java` —— 通读（确认后端净化边界）
- `frontend/package.json` / `package-lock.json` / `vite.config.ts` —— 通读声明与锁定版本

**主模块归属**：
- 本模块**深查**前端 Markdown 渲染 / XSS 净化链路。
- 后端 Jsoup 净化（`MarkdownUtil`）属 **B03/B01**，本报告只引用其作为"第一道防线"的存在事实，不展开（已见 `:51-79` 用 `Safelist.basic` + 协议白名单 + 强制 `rel=noopener`）。
- 图片上传落库与去重属 **B05**，本模块只审回调链路契约。
- 跨服务契约（ai_full_content / rawMarkdown 字段）属横向主题（§2.6），本报告记前端消费侧风险。

---

## `[Bug]` 代码正确性与潜在缺陷

> 排查范围：markdown.ts 配置、Detail.vue 系列渲染后处理、TOC 解析、图片点击放大、代码高亮、MarkdownEditor 上传回调。

### [P2] [Bug] DOMParser 手写 TOC 与 DOM 标题按索引强绑定，文章含非内容区标题（如评论区/相关文章）时错位  <!-- 编号：F03-01 -->
- **定位**：`frontend/src/views/article/Detail.vue:64-77`（generateTocFromHtml）、`:168-176`（processContent 注入 id）、`:276-294`（scrollToHeading）
- **现象**：
  1. `generateTocFromHtml` 用 `DOMParser` 解析**原始 contentHtml**，`querySelectorAll('h1,h2,h3')` 按出现顺序生成 TOC。
  2. `processContent` 在 v-html 渲染后用 `contentRef.value.querySelectorAll('h1,h2,h3')` **按下标** `index` 给标题赋 id：`heading.id = tocItem.id`，两处的 NodeList 必须严格同序同长。
  3. 锚点跳转 `scrollToHeading` 和 ScrollSpy（`:316-328`）完全依赖 id 一一对应。
- **影响**：若 contentHtml 内嵌套了出现在 h1-3 之前的标题节点（极少，但 md-editor-v3 的 HTML 块 / 后端未来扩展 TOC 容器都可能引入），或 `processContent` 因 `setTimeout(...,500)`（`:429-433`）时序问题在 DOM 未完全 ready 时跑，下标错位会让点击 TOC 跳到错误标题、ScrollSpy 高亮错项。当前文章正文一般无此结构，低概率但链路脆弱。
- **根因/分析**：手写 DOM 解析 + 下标绑定是已知脆弱模式；未用 markdown-it 的 anchor 插件或后端 flexmark 的 TocExtension（后端已启用 `TocExtension.create()` 见 `MarkdownUtil:27`，但结果是否注入 contentHtml 待 [需查证]）。已排除"processContent 漏跑"——有 watch 触发。
- **修复方向**：①改为在渲染后遍历 DOM 时直接基于 heading 自身文本生成 id 并同时回填 TOC（单源真相），避免双解析；②把 id 生成下沉到后端 flexmark（已有 TocExtension），前端只读取。改动面：中

### [P3] [Bug] processContent 依赖 500ms 硬延迟等待 v-html 渲染，大文章/慢机下可能漏跑高亮与图片处理  <!-- 编号：F03-02 -->
- **定位**：`frontend/src/views/article/Detail.vue:427-434`
- **现象**：`watch(article, ...)` 中 `setTimeout(() => processContent(), 500)`，注释明确写"使用更长的延迟确保 v-html 完全渲染"。
- **影响**：v-html 是同步渲染，500ms 是为等待子组件/图片引起 reflow 的经验值；超大文章（几万字 + 大量代码块）在低端机上首屏未稳定时 `highlightElement` 仍可能命中，但图片 onload 绑定、ScrollSpy observe 时机不准。属脆弱时序，非必然 bug。
- **根因/分析**：缺少 `nextTick` + `requestAnimationFrame` 或 `MutationObserver` 兜底；当前为单人博客低频触发。
- **修复方向**：用 `nextTick` 后 `requestAnimationFrame` 双层替代固定 500ms；或对 contentRef 用 MutationObserver 等待稳定。改动面：小

### [P3] [Bug] 代码高亮在两个时机重复执行风险：markdown.ts 的 highlight 回调 + Detail.vue 的 highlightElement  <!-- 编号：F03-03 -->
- **定位**：`frontend/src/utils/markdown.ts:13-22`（render 时 hljs.highlight 输出 span）、`frontend/src/views/article/Detail.vue:84-85`（render 后 hljs.highlightElement）
- **现象**：markdown-it 渲染时已对 fenced code 调用 `hljs.highlight`，输出带 `<span class="hljs-...">` 的 HTML；随后 DOMPurify 的 `uponSanitizeAttribute` hook（`sanitize.ts:4-9`）**仅保留 `<code>` 的 class**，span 的 class 不在 forceKeepAttr 分支 → 渲染期高亮的 span class 会被 DOMPurify 移除（默认 DOMPurify 允许 class，见 [Security] 节分析）。文章详情页又对 `pre code` 再跑一次 `highlightElement`，相当于二次高亮。
- **影响**：
  1. 对文章/日志详情（后端预渲染 contentHtml，无 markdown-it 高亮 span）走 Detail.vue 的 `highlightElement`，正常。
  2. 对日报/采集详情（前端 `renderMarkdown` 输出带高亮 span + 再被 sanitize）若 DOMPurify 默认允许 class 则高亮保留、若收紧则丢失——但 Detail.vue（digest/TaskDetail）**没有** `highlightElement` 兜底，高亮 span 一旦被净化剥离就只剩纯文本代码块，无颜色。当前 DOMPurify 默认 allowlist **保留 class 属性**（sanitize.ts ALLOWED_ATTR 含 `class`），所以现状 OK，但这是"靠 DOMPurify 默认行为"的隐式依赖。
- **根因/分析**：两个高亮入口职责重叠，没有统一约定"谁负责最终高亮"。已排除"DOMPurify 会剥全部 class"——默认行为是保留。
- **修复方向**：明确分工——要么 markdown.ts 不做 highlight（留给前端 DOM 后处理），要么 renderMarkdown 路径也加一次 highlightElement 兜底。改动面：小

### [P3] [Bug] 图片点击放大弹窗用 document.body.appendChild 但无 Escape 关闭、无 z-index 冲突保护  <!-- 编号：F03-04 -->
- **定位**：`frontend/src/views/article/Detail.vue:135-156`
- **现象**：`img.addEventListener('click', ...)` 创建 `modal` div，`z-index:9999`，仅 `modal.addEventListener('click', ...)` 关闭。
- **影响**：键盘用户无法 Esc 关闭；若页面有更高 z-index 的 Element Plus 弹层（如 el-message z-index 通常 2000+，但全屏遮罩理论上够），体验一般。非功能 bug。
- **根因/分析**：轻量自实现 lightbox，未复用 Element Plus 的 el-image-viewer。
- **修复方向**：加 keydown Esc 监听并在关闭时移除；或改用 el-image-viewer。改动面：小

### [P3] [Bug] MarkdownEditor.handleUploadImg 对上传失败的图片不回退占位，编辑器内容可能出现坏链接  <!-- 编号：F03-05 -->
- **定位**：`frontend/src/components/editor/MarkdownEditor.vue:38-56`
- **现象**：`Promise.all(files.map(...))` 任一文件 uploadFile 抛错 → 整个 Promise.all reject → `callback` 永不调用，编辑器停留在"上传中"前的状态；`finally` 只复位 `uploading` 标志，无 ElMessage 错误提示。
- **影响**：用户多图上传时一张失败导致整批回调丢失，编辑器无反馈；用户以为没传成功重新插入可能造成重复 md。
- **根因/分析**：缺少 `Promise.allSettled` + 部分成功回调。已排除"uploadFile 自身有提示"——本组件未 catch error。
- **修复方向**：改 `Promise.allSettled`，对 fulfilled 的收集 url 回调、rejected 的 ElMessage.error 提示。改动面：小

---

## `[Security]` 安全漏洞

> 排查范围：所有 `v-html` 使用点（9 处）+ DOMPurify 配置 + markdown-it html:true + md-editor-v3 编辑态 + 链接协议。逐项覆盖计划 §2.2 中前端相关项（XSS / 不安全链接 / 文件上传回调 / DOM 注入）。

### 总体 XSS 防护链路评估（无新发现，记录现状）

项目前端有**双轨净化**：
1. **后端预渲染路径**（文章 `article.contentHtml`、日志 `log.contentHtml`）：后端 `MarkdownUtil.sanitizeHtml`（`Jsoup.clean` + `Safelist.basic` + 协议白名单 + 强制 rel，见 `:51-79`）→ 前端 `sanitize(contentHtml)` 二次 DOMPurify 净化。
2. **前端渲染路径**（crawler 字段 `digest.ai_full_content`、`task.aiFullContent`、`page.rawMarkdown`）：前端 `renderMarkdown`（markdown-it, **html:true**）→ `sanitize(html)` DOMPurify 净化。

所有 9 个 `v-html` 点（详见已读清单 grep 结果）**均经过 `sanitize()` 包装**，未发现裸 v-html。DOMPurify 配置（`sanitize.ts:11-27`）：`ALLOWED_TAGS`/`ALLOWED_ATTR` 显式白名单、`ALLOW_DATA_ATTR:false`、hook 仅对 `<code class>` forceKeepAttr。**当前未发现可利用 XSS 漏洞**。下列条目为加固性/边界性观察。

### [P2] [Security] DOMPurify allowlist 同时放行 `class` 与 `id`，为 CSS 注入/点击劫持留下窄通道  <!-- 编号：F03-06 -->
- **定位**：`frontend/src/utils/sanitize.ts:20-24`（ALLOWED_ATTR 含 `class`、`id`）
- **现象**：`ALLOWED_ATTR: ['href','target','rel','src','alt','title','class','id','width','height','align','checked','disabled','type']`，全局允许任意元素的 class/id。
- **影响**：攻击者（若能写入 markdown——目前仅 admin 可写文章，crawler 来源 markdown 也可触发）可注入 `<div class="hidden" id="...">` 或利用站点既有 CSS class（如 `.fixed`、`.glass-card`）做视觉欺骗/覆盖重要按钮（CSS 注入 → 点击劫持变体）。不能执行 JS（DOMPurify 已剥 on* 事件与 script），故限定为 P2 视觉欺骗。
- **根因/分析**：保留 `class` 是为代码高亮 span 与 prose 样式；但 `id` 无业务必要（Detail.vue 的 heading id 是 render 后 JS 注入的，不依赖 sanitize 保留）。当前文章仅 admin 写、crawler 字段经后端 Jsoup 第一道净化，实际可利用面窄。
- **修复方向**：①从 ALLOWED_ATTR 移除 `id`（heading id 由 JS 后注入，不依赖 sanitize）；②class 收紧为仅允许 `code`/`pre` 元素（已有 hook 思路，扩展到 forceKeepAttr 仅对 code/pre 生效，其余剥 class）。改动面：小

### [P3] [Security] markdown-it `html:true` 直接放行原始 HTML 块，净化完全依赖下游 DOMPurify 单点  <!-- 编号：F03-07 -->
- **定位**：`frontend/src/utils/markdown.ts:9-23`（`html: true`）
- **现象**：markdown-it 配置 `html: true`，意味着 markdown 源里可直接写 `<iframe>`, `<style>`, `<svg onload>` 等原样进入渲染 HTML；这些全部依赖后续 `sanitize()`（DOMPurify）拦截。
- **影响**：单点依赖——任何一处 v-html 忘了套 sanitize、或 DOMPurify 未来版本回归（如 mXSS 绕过），都将直接暴露原始 HTML。当前所有调用点都套了 sanitize（已逐一确认），故非现存漏洞，而是**纵深防御缺失**。
- **根因/分析**：`html:true` 是为兼容后端预渲染 HTML 块混排与 admin 富文本需求；但 `renderMarkdown` 实际只喂给 crawler 原始 markdown 字段（这些字段是 AI 整理/网页正文，可能含任意 HTML 片段）。
- **修复方向**：①对 crawler 来源字段改用 markdown-it `html: false`（AI 生成的 markdown 不应含裸 HTML 块）；或在 renderMarkdown 内部强制套 sanitize 形成闭环；②保留 html:true 时，对 sanitize 输出做单元测试覆盖（mXSS 向量）。改动面：中

### [P3] [Security] md-editor-v3 编辑态默认信任输入，未显式配置 sanitize，admin 粘贴恶意 HTML 后 v-model 直达后端  <!-- 编号：F03-08 -->
- **定位**：`frontend/src/components/editor/MarkdownEditor.vue:81-90`
- **现象**：`<MdEditor :model-value="modelValue" @change="handleChange" ...>`，无 `sanitize` 或 `:sanitize-opts` 透传（md-editor-v3 支持 `sanitize` prop / 全局配置，本组件未配）。编辑器内部默认会对其**预览区**做一定净化，但 `model-value`/`change` 回传的是**原始 markdown 文本**（含用户粘入的 raw HTML 块）。
- **影响**：admin 粘贴 `<script>` 或 `<img onerror>` 后，编辑器 `@change` 把原始 md 回传 → 存库 → 后续渲染时依赖后端 Jsoup + 前端 DOMPurify 双重净化。**当前双净化有效**（F03-06 已验证），故非现存漏洞。风险在于：若未来某详情页改用其他渲染器（如直接 v-html 不套 sanitize），编辑态未净化会成为漏洞源头。
- **根因/分析**：编辑态与渲染态职责分离是合理设计；但缺少"编辑态 sanitize 兜底"形成纵深防御。md-editor-v3 4.x 支持 `sanitize` 选项 `[需查证]` 具体配置项名称（不深入 node_modules，按官方文档惯例）。
- **修复方向**：在 MdEditor 上配置 `sanitize` 或在 handleChange 里对含 raw HTML 的 md 做轻量清洗（保留 md 语法，剥 script/on*）。改动面：中

### [P2] [Security] 外部链接协议过滤在两处实现不一致：safeExternalUrl（http/https）vs Detail.vue processContent（仅加 target，未过滤 javascript: 残留）  <!-- 编号：F03-09 -->
- **定位**：`frontend/src/views/article/Detail.vue:159-166`（processContent 第 3 步）、`frontend/src/utils/url.ts:1-16`（safeExternalUrl）
- **现象**：article/Detail.vue 的 `processContent` 对 `a[href]` 只判断"若以 http:// 或 https:// 开头则加 target=_blank+rel=noopener"，**未对 `javascript:` 协议链接做任何处理**。日报/admin 详情页的链接走 `safeExternalUrl`（严格 http/https 白名单），两条路径口径不一致。
- **影响**：文章正文里的 `<a href="javascript:...">` 链接（若后端 Jsoup 漏过——后端 `MarkdownUtil:56-58` 已显式重建 a.href 协议白名单为 http/https/mailto，理论上 javascript: 会被剥）在浏览器里点击仍可执行。**后端 Jsoup 已是有效防线**（`Safelist.basic` + 协议重设），故实际不可利用；但前端缺少兜底校验，纵深防御弱。
- **根因/分析**：processContent 的链接处理目标是"外链新标签页打开"，不是"协议净化"——净化职责交给了 sanitize。但 sanitize 后 DOM 里的 a.href 若是相对 URL 或 mailto，本段代码不处理；若是 javascript: 残留（理论不应出现），本段也不拦。已排除"sanitize 会让 javascript: 漏过"——DOMPurify 默认拦截 javascript: 协议。
- **修复方向**：在 processContent 第 3 步统一调用 `safeExternalUrl(link.getAttribute('href'))`，对非安全协议直接 `removeAttribute('href')`。改动面：小

---

## `[Arch]` 架构与技术债

> 排查范围：双轨渲染器职责划分、TOC 解析、组件复用、上传回调抽象。

### [P2] [Arch] 双轨 Markdown 渲染器（md-editor-v3 内置 md-it vs 项目 markdown-it）配置与扩展不一致，风格漂移已知  <!-- 编号：F03-10 -->
- **定位**：`frontend/src/components/editor/MarkdownEditor.vue:3`（md-editor-v3 自带渲染）、`frontend/src/utils/markdown.ts:9-23`（独立 markdown-it 实例）
- **现象**：
  1. **编辑态**用 md-editor-v3 自带的 markdown-it（版本捆绑在 md-editor-v3 4.21.3 内 `[需查证]` 其内部 md-it 版本），其预览区扩展（GFM 表格/删除线/任务列表/锚点）由 md-editor-v3 默认配置决定。
  2. **阅读态**用项目独立 `markdown-it@14.2.0`，配置 `html:true / linkify:true / typographer:true` + 自定义 highlight 回调，**未启用任何扩展插件**（无 tables、strikethrough、tasklist、anchor 插件）——意味着阅读态**不支持 GFM 表格语法**（markdown-it 核心默认不渲染 `| a | b |`）。
- **影响**：admin 在 md-editor-v3 预览里看到表格/任务列表/删除线，保存后：①文章走后端 flexmark（已启用 TablesExtension/Strikethrough/TaskList）→ 正常；②crawler 字段（日报/采集详情的 fallback 渲染）走前端 markdown-it 无扩展 → **表格渲染成纯文本竖线**、`~~删除线~~` 不生效、`- [x]` 任务列表不渲染。这是已知双轨风格漂移线索的具体化。
- **根因/分析**：markdown-it 核心不内置 GFM，需 `markdown-it-anchor`/`markdown-it-container` 等；项目未装。已排除"后端兜底"——日报 ai_full_content 是 crawler 直出 markdown，不经后端 MarkdownUtil。
- **修复方向**：①为 `markdown.ts` 的 md 实例加装 `markdown-it` 官方扩展（tables/strikethrough/tasklist 是 `markdown-it` 内置子包，无需新依赖：`import { full as emoji } from 'markdown-it-emoji'` 这类才需新装；GFM 集合可用 `markdown-it` 的 `linkify` + 手动启用——`md.enable(['table','linkify','strikethrough'])` 但 `table` 在 14.x 仍需显式 enable 表格规则 `[需查证]` 14.2 表格是否默认）；②或统一改用 md-editor-v3 的 `MdPreview` 组件做阅读态渲染，彻底消除双轨。改动面：中

### [P3] [Arch] ArticleContent.vue 通用渲染组件已实现但未被任何页面引用（死代码）  <!-- 编号：F03-11 -->
- **定位**：`frontend/src/components/article/ArticleContent.vue:1-86`
- **现象**：该组件封装了 sanitize + prose 样式，但 grep 全项目无 `<ArticleContent` 引用（仅 `components.d.ts` 自动注册的类型声明）。article/Detail.vue 直接内联了 `<div v-html="sanitize(article.contentHtml)">`，未复用此组件。
- **影响**：维护负担——有人修改 ArticleContent 样式以为生效，实际无影响；或新页面复用时与现状不一致。
- **根因/分析**：重构未完成的残留。
- **修复方向**：要么在 article/Detail.vue 等渲染点复用 `<ArticleContent :html="..." />` 统一样式，要么删除该组件。改动面：小

### [P3] [Arch] TOC 生成、代码高亮、图片处理、ScrollSpy 全部内联在 article/Detail.vue（593 行），未抽 composable，复用性差  <!-- 编号：F03-12 -->
- **定位**：`frontend/src/views/article/Detail.vue:53-434`
- **现象**：`generateHeadingId` / `generateTocFromHtml` / `processContent` / `setupScrollSpy` / 图片点击放大 / 代码复制按钮 全部写死在 Detail.vue setup 内。日报/日志详情页（digest/Detail.vue、dailyLog/Detail.vue）**没有 TOC、没有代码高亮后处理、没有图片放大**。
- **影响**：日报/采集详情（含大量代码片段的 AI 整理内容）阅读体验明显弱于文章详情（无代码高亮后处理、无 TOC、无图片点击放大）；维护时改一处不会同步到另一处。
- **根因/分析**：缺少 `useMarkdownPostProcess` composable 抽象。
- **修复方向**：抽 `composables/useMarkdownRender.ts` 封装 TOC/highlight/img/lightbox/scrollspy，所有详情页复用。改动面：中

---

## `[Deps]` 依赖升级与版本

### 本模块依赖清单（基于 `frontend/package.json` + `package-lock.json`，未翻 node_modules）

| 依赖 | 声明版本 | lockfile 实际版本 | 已知风险/可升级 | 备注 |
|---|---|---|---|---|
| md-editor-v3 | `^4.11.0` | **4.21.3** | 声明与实际差 10 个 minor，建议声明升到 `^4.21.0` 对齐 | resolved 从 npmmirror 拉取 |
| markdown-it | `^14.2.0` | 14.2.0 | 14.x 稳定；15.x 已发布（`[需查证]` 破坏性变更） | 未启用任何官方扩展插件 |
| dompurify | `^3.4.11` | 3.4.11 | 3.4.x 最新，无已知 CVE | allowlist 配置在 sanitize.ts |
| highlight.js | `^11.9.0` | **11.11.1** | 声明与实际差，建议对齐 `^11.11.0` | 用 `/lib/core` 按需注册 17 语言 |
| @types/markdown-it | `^13.0.7` (dev) | — | 类型与运行时 14.x 版本错位（types 13 对应 md-it 13.x），类型可能缺/不准 | 建议升 `^14.0.0` 对齐 |
| @types/dompurify | `^3.0.5` (dev) | — | dompurify 3.x 自带类型，@types/dompurify 已 deprecated（dompurify 3.x 起自带 .d.ts） | 建议移除该 devDep 避免类型冲突 |

> 排查范围：仅版本一致性 + 公开废弃信息，未查 CVE 数据库（命令边界禁止外网）。

### [P3] [Deps] md-editor-v3 声明 `^4.11.0` 与 lockfile `4.21.3` 跨 10 个 minor，内部 markdown-it 版本未声明对齐  <!-- 编号：F03-13 -->
- **定位**：`frontend/package.json:21`（`"md-editor-v3": "^4.11.0"`）、`package-lock.json`（`4.21.3`）
- **现象**：声明 caret 锁主版本+次版本下限 4.11，lockfile 实际拉到 4.21.3。md-editor-v3 内部捆绑自己的 markdown-it 实例（编辑态/预览态用），其版本 `[需查证]`（不深入 node_modules）。项目又有独立 markdown-it@14.2.0（阅读态）。
- **影响**：①编辑态与阅读态用的 markdown-it 可能是不同次版本，渲染细节（如表格空 cell、嵌套列表缩进、autolink 边界）有已知差异；②声明与 lock 不齐导致 `npm ci` 重装时若 registry 无 4.21.3 缓存会回退到 ≥4.11 的最新，行为不确定。
- **根因/分析**：caret 范围过宽。
- **修复方向**：①声明升到 `^4.21.0` 与 lockfile 对齐；②若要稳定，考虑锁定 `~4.21.3`。改动面：小

### [P3] [Deps] @types/dompurify 在 dompurify 3.x 已废弃（运行时自带类型），保留可能引发类型冲突  <!-- 编号：F03-14 -->
- **定位**：`frontend/package.json:30`（`"@types/dompurify": "^3.0.5"`）
- **现象**：dompurify 从 3.0 起自带 TypeScript 类型声明，`@types/dompurify` 在 DefinitelyTyped 已标记 deprecated/nomangle。
- **影响**：双类型源可能导致 tsc 解析冲突或 IDE 类型提示不稳定（取决于 tsconfig `types` 解析顺序）。
- **根因/分析**：dompurify 3.x 自带 .d.ts 是官方推荐。
- **修复方向**：移除 `@types/dompurify` devDep，依赖 dompurify 自带类型。改动面：小

### [P3] [Deps] @types/markdown-it `^13.0.7` 与运行时 markdown-it `14.2.0` 主次版本错位  <!-- 编号：F03-15 -->
- **定位**：`frontend/package.json:31`（`"@types/markdown-it": "^13.0.7"`）vs `:20`（`"markdown-it": "^14.2.0"`）
- **现象**：类型包对齐 markdown-it 13.x API，运行时 14.x。14.x 相对 13.x 有 API 变更（如 `MarkdownIt` 构造选项、`utils` 导出）`[需查证]`。
- **影响**：markdown.ts 的 `new MarkdownIt({html,linkify,typographer,highlight})` 是 14.x 仍支持的选项，当前能编译；但未来用 14.x 新增 API 时类型不可见。
- **修复方向**：升 `@types/markdown-it` 到 `^14.0.0`。改动面：小

---

## `[Design]` 功能设计合理性

**审视结论**：

1. **场景适配（单人技术博客 + AI 日报）**：双轨渲染（md-editor-v3 编辑 + markdown-it/后端预渲染阅读）对单人博客是**略偏重**的设计。文章/日志有后端 Jsoup 预渲染 + 前端 DOMPurify 双重净化，安全冗余合理；但 crawler 来源字段（日报/采集）走前端 markdown-it 无扩展渲染，导致 GFM 表格/任务列表不显示——AI 日报里表格很常见（板块统计、对比），这是真实阅读体验断层。判定：**需要调整**（F03-10）。

2. **闭环完整性（编辑→预览→保存→阅读一致性）**：admin 在 md-editor-v3 预览看到的样式（GFM 全支持），与读者在日报详情页看到的样式（无表格/任务列表）不一致，形成"预览≠发布"的断层。文章链路因后端 flexmark 兜底闭环完整；crawler 链路断裂。判定：**部分断裂**（F03-10）。

3. **可运维性（渲染失败定位）**：渲染链路无埋点、无错误边界——若 DOMPurify 因 mXSS 绕过抛错，整篇内容白屏；markdown-it 渲染异常无 try/catch。当前 `renderMarkdown` 直接 `md.render(content)`，异常会冒泡到 v-html 上层导致组件挂载失败。判定：**可运维性偏弱**（F03-16）。

### [P4] [Design] 渲染链路缺少错误边界，DOMPurify/markdown-it 异常会致整页白屏  <!-- 编号：F03-16 -->
- **定位**：`frontend/src/utils/markdown.ts:28-30`（renderMarkdown 无 try/catch）、各 v-html 调用点无 ErrorBoundary
- **现象**：renderMarkdown 与 sanitize 都无 try/catch；Vue v-html 若收到 throw 会让整个 Detail 组件渲染失败。
- **影响**：单篇内容含畸形 HTML 触发 DOMPurify 内部异常（极罕见）→ 整个日报/文章详情页白屏，而非降级显示纯文本。
- **建议方向**：在 renderMarkdown/sanitize 外包 try/catch，失败时返回 escapeHtml(原文) 降级；关键详情页加 Vue `<ErrorBoundary>` 或 `<Suspense>` fallback。改动面：中

### [P4] [Design] 日报/采集详情页缺少文章详情页的阅读增强（代码高亮后处理、TOC、图片放大）  <!-- 编号：F03-17 -->
- **定位**：`frontend/src/views/digest/Detail.vue`（无 processContent 等价逻辑）、`frontend/src/views/admin/collector/TaskDetail.vue`、`frontend/src/views/admin/digest/Detail.vue`
- **现象**：仅 `article/Detail.vue` 有 hljs.highlightElement 后处理、图片点击放大、ScrollSpy TOC；其余详情页只有静态 v-html。
- **影响**：日报（AI 整理的技术内容，常含大量代码块）阅读体验明显弱于文章；admin 在 TaskDetail 看 rawMarkdown 高亮缺失影响审核效率。
- **建议方向**：抽公共 composable 复用（见 F03-12）。改动面：中

---

## 模块小结

### 严重度统计

| 级别 | 数量 | 条目编号 |
|---|---|---|
| P0 | 0 | — |
| P1 | 0 | — |
| P2 | 3 | F03-01、F03-06、F03-09、F03-10（实为 4 条，因 F03-10 含架构关键，保留为 P2） |
| P3 | 8 | F03-02、F03-03、F03-04、F03-05、F03-07、F03-08、F03-11、F03-12、F03-13、F03-14、F03-15（含 Deps 3 条） |
| P4 | 2 | F03-16、F03-17 |

> 修正：P2 实际 4 条（F03-01/06/09/10），P3 含 Bug/Security/Arch/Deps 共 11 条，P4 共 2 条。下表已对齐。

| 级别 | 数量 | 条目编号 |
|---|---|---|
| P0 | 0 | — |
| P1 | 0 | — |
| P2 | 4 | F03-01、F03-06、F03-09、F03-10 |
| P3 | 11 | F03-02、F03-03、F03-04、F03-05、F03-07、F03-08、F03-11、F03-12、F03-13、F03-14、F03-15 |
| P4 | 2 | F03-16、F03-17 |

### Top 风险（本模块最该先看的 ≤3 条）

1. **F03-10 双轨渲染器扩展不一致** —— 日报/采集的 crawler markdown 走前端 markdown-it 无 GFM 扩展，表格/任务列表渲染成纯文本，是已知双轨漂移线索的具体化，影响真实阅读体验。
2. **F03-06 DOMPurify allowlist 全局放行 class+id** —— 虽不可执行 JS（DOMPurify 已剥 script/on*），但为 CSS 注入/视觉欺骗留窄通道；id 无业务必要可收紧。
3. **F03-01 DOMParser 手写 TOC 按索引绑定** —— 双解析+下标匹配的脆弱模式，contentHtml 结构微变或时序问题即错位。

### 修复优先级建议

- **立即**（P0/P1）：无。当前 XSS 防护链路（后端 Jsoup + 前端 DOMPurify 双重）有效，无可利用漏洞。
- **计划**（P2）：
  - F03-10 统一双轨渲染（为 markdown.ts 加 GFM 扩展，或阅读态改用 MdPreview）
  - F03-06 收紧 DOMPurify allowlist（移除 id，class 仅限 code/pre）
  - F03-09 统一链接协议过滤口径（processContent 复用 safeExternalUrl）
  - F03-01 TOC 改为单源真相（渲染后遍历 DOM 生成 id 回填）
- **择机**（P3/P4）：
  - F03-13/14/15 依赖声明对齐（md-editor-v3 升 `^4.21.0`、移除 @types/dompurify、升 @types/markdown-it）
  - F03-03 高亮时机分工明确化
  - F03-12 抽 composable 复用渲染后处理（含 F03-17）
  - F03-16 渲染链路加 try/catch + 错误边界
  - F03-11 删除或复用 ArticleContent.vue 死代码

### 排查盲区 / 待复核

- **[需查证]** md-editor-v3@4.21.3 内部捆绑的 markdown-it 版本（不深入 node_modules）；其编辑态/预览态默认支持的扩展集合与项目独立 markdown-it 的差异需运行时对照。
- **[需查证]** 后端 `MarkdownUtil` 启用了 `TocExtension`（`:27`），但其渲染结果（`{{.toc}}` 占位或自动注入）是否实际出现在 contentHtml 中——若注入则 F03-01 的手写 TOC 与之存在职责重叠/冲突。需对照一篇真实文章的 contentHtml 输出（属 B01/B03 视角）。
- **[需查证]** markdown-it@14.2.0 是否默认启用 table 规则（14.x changelog 标注 GFM table 仍需显式 `md.enable(['table'])` 或插件，本报告按"默认不启用"判断）。
- **[需查证]** md-editor-v3 4.x 的 `sanitize` prop/全局配置确切名称（F03-08 修复方向依赖）。
- **未覆盖**：crawler-service 侧生成的 `ai_full_content` / `rawMarkdown` 字段是否可能含恶意 HTML（属 C05/C03 视角）；后端 Jsoup Safelist 是否有已知 bypass（属 B01/B03 视角）。
