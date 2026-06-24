# F07 构建与依赖 排查报告

> **模块编号**：F07
> **排查范围**：前端构建链（Vite 配置 / chunk 分包 / gzip / TypeScript 配置 / 构建脚本）+ 前端依赖版本与锁定（package.json + package-lock.json）
> **基线 commit**：`6ae930098405f4d0553d96a852f3345d0f39682e`
> **工作区状态**：脏（未提交改动均位于 backend / crawler-service / docs / scripts，**不涉及 frontend**；frontend 构建相关文件全部为已提交干净状态）。本地 `frontend/dist/` 目录存在（最近构建产物），但 `.gitignore` 正确排除、未被 git 跟踪。
> **排查日期**：2026-06-24
> **排查人**：frontend F07 排查 agent
> **状态**：待复核

---

## 模块概览

**职责**：管理 Vue 3 前端的开发服务器、生产构建产物分包与压缩、TypeScript 类型检查门禁，以及运行时/构建期依赖的版本声明与锁定，保证 Docker 镜像 `npm ci` 可复现。

**关键文件**：
- `frontend/vite.config.ts:1-85` —— Vite 配置入口（插件链 / dev proxy / build manualChunks）
- `frontend/package.json:1-66` —— 依赖声明、scripts、overrides、engines
- `frontend/package-lock.json` —— lockfileVersion 3，锁定实际安装版本（排查抽样，未翻 node_modules）
- `frontend/tsconfig.json:1-21` —— TS 严格度配置
- `frontend/env.d.ts:1-18` —— `import.meta.env` 类型声明
- `frontend/Dockerfile:1-19` —— 多阶段构建（builder + nginx）
- `frontend/.eslintrc.cjs` / `frontend/.prettierrc` / `frontend/postcss.config.js` —— 代码风格与 PostCSS 链
- `frontend/.env.development` / `frontend/.env.production` / `frontend/.env.example` —— 构建期环境变量
- `frontend/src/auto-imports.d.ts` / `frontend/src/components.d.ts` —— unplugin 自动生成的类型声明（**已被 git 跟踪**）

**对外接口 / 依赖**：
- 对外：产出 `frontend/dist/`（静态资源），由 `deploy/nginx.conf` 服务；Dockerfile 构建 `node:20-alpine` → `nginx:1.27-alpine`
- 依赖：backend `/api` 与 `/uploads`（dev proxy 指向 `localhost:8081`）；生产由 nginx 反代（X01 主模块）

**已读文件清单**：
- `frontend/vite.config.ts` —— 通读
- `frontend/package.json` —— 通读
- `frontend/tsconfig.json` —— 通读
- `frontend/env.d.ts` —— 通读
- `frontend/Dockerfile` —— 通读
- `frontend/.eslintrc.cjs` —— 通读
- `frontend/.prettierrc` / `frontend/postcss.config.js` —— 通读
- `frontend/.env.development` / `.env.production` / `.env.example` —— 通读
- `frontend/package-lock.json` —— 仅 node 脚本抽样关键包锁定版本（未翻 node_modules）
- `frontend/src/utils/request.ts:1-40` —— 片段（确认 `VITE_API_BASE_URL` 消费方）
- `frontend/README.md` / `README.md` / `docs/trial-release-roadmap.md` / `deploy/README.md` —— grep 审计基线声明
- `git ls-files frontend/dist` / `git check-ignore` —— 确认 dist 未提交
- `git ls-files src/auto-imports.d.ts src/components.d.ts` —— 确认生成产物已提交

**主模块归属**：本模块是**前端构建/依赖的主模块**，深查。对 nginx 部署、release-gate 等"只引用"X01 / X04。

---

## `[Bug]` 代码正确性与潜在缺陷

> 排查范围：vite.config.ts 插件链与 rollupOptions、scripts、prettier/eslint 配置一致性、env 变量声明与消费。

### [P2] [Bug] `.prettierrc` 引用未声明的 `prettier-plugin-tailwindcss`，`npm run format` 会失败 <!-- 编号：F07-01 -->
- **定位**：`frontend/.prettierrc:7`（`"plugins": ["prettier-plugin-tailwindcss"]`）对照 `frontend/package.json:27-51`（devDependencies 全量）与 `frontend/package-lock.json`
- **现象**：`.prettierrc` 声明加载 `prettier-plugin-tailwindcss`，但该插件**既不在 `package.json` 任何依赖区，也不在 `package-lock.json`**（node 脚本确认 `node_modules/prettier-plugin-tailwindcss` 在 lock 中不存在）。`package.json` 的 `scripts.format` = `prettier --write src/`。
- **影响**：任何执行 `npm run format` 的场景（开发者本地、CI、release-gate 若调用）prettier 会因找不到插件报错退出；除非开发者全局安装该插件才能侥幸跑通，不可复现。`docs/trial-release-roadmap.md:101` 已将前端工具链列为 P2 待办，但未覆盖此具体卡点。
- **根因/分析**：插件配置与依赖声明脱节。已排除误判：lock 中确实无该包，非路径别名问题。
- **修复方向**：① 把 `prettier-plugin-tailwindcss` 加入 `devDependencies` 并 `npm install` 更新 lock；或 ② 从 `.prettierrc` 移除该 plugin 项（若不需要 tailwind class 排序）。改动面：小
- **关联**：次维度 `[Deps]`；与 F07-06（工具链整体偏旧）相关

### [P3] [Bug] env 变量 `VITE_USE_MOCK` / `VITE_APP_TITLE` 已声明但源码零消费（死配置） <!-- 编号：F07-02 -->
- **定位**：`frontend/.env.development:10`、`frontend/.env.production:10`、`frontend/.env.example:9`、`frontend/env.d.ts:6-7`；对照 `frontend/src/` 全量 grep
- **现象**：三个 env 文件均定义 `VITE_USE_MOCK`，`env.d.ts` 为 `VITE_USE_MOCK` / `VITE_APP_TITLE` 声明了类型，但 `grep -rn "VITE_USE_MOCK\|VITE_APP_TITLE" src/` **零命中**。仅 `VITE_API_BASE_URL` 在 `src/utils/request.ts:28` 被消费。
- **影响**：无功能后果（死配置），但误导维护者以为存在 Mock 数据开关；`VITE_APP_TITLE` 未注入 `index.html` title 也未在 App 内使用，应用标题实际靠 nginx/HTML 静态值。
- **根因/分析**：早期脚手架遗留，功能从未落地或已被移除。
- **修复方向**：① 从三份 env 与 `env.d.ts` 移除 `VITE_USE_MOCK`、`VITE_APP_TITLE`；或 ② 在 `index.html` 用 `%VITE_APP_TITLE%` 或在 App 启动时 `document.title = import.meta.env.VITE_APP_TITLE` 落地该配置。改动面：小
- **关联**：次维度 `[Design]`（配置最小性）

---

## `[Security]` 安全漏洞

> 排查范围：生产 source map 泄漏、构建产物提交、敏感环境变量泄漏、Dockerfile 供应链。逐项覆盖 §2.2 中前端相关项（Cookie/CSRF/CORS 属 F01/F02 主模块，此处只看构建期）。

### 未发现阻断级安全问题，但有 2 项需关注

**已检查并确认安全**：
- ✅ **dist 未提交仓库**：`.gitignore`（项目根）`frontend/dist/` 规则有效，`git ls-files frontend/dist` 返回 0 行，`git check-ignore frontend/dist/` 命中。本地 dist 目录仅为开发构建残留。
- ✅ **生产无 source map 泄漏**：`vite.config.ts` 全文无 `build.sourcemap` 配置，Vite 5 默认 `sourcemap: false`，生产构建不产出 map 文件。[需查证] 若后续有人显式开启需复核。
- ✅ **env 无敏感泄漏**：三份 env 文件仅含 `VITE_API_BASE_URL`（相对路径 `/api`）、`VITE_APP_TITLE`、`VITE_USE_MOCK`，无密钥/token/绝对内网地址。所有 `VITE_` 前缀变量都会被打进 bundle，当前内容安全。
- ✅ **Dockerfile 基线**：`node:20-alpine`（tag 固定到大版本）+ `nginx:1.27-alpine`（tag 固定到大版本），非 `latest`。`npm ci` 优先于 `npm install`（lockfile 存在时可复现）。
- ✅ **运行时仅静态文件**：nginx 镜像只 COPY `dist`，不带 node_modules / 源码进运行时镜像。

### [P3] [Security] 生成产物 `auto-imports.d.ts` / `components.d.ts` 已提交仓库 <!-- 编号：F07-03 -->
- **定位**：`git ls-files src/auto-imports.d.ts src/components.d.ts` 均返回已跟踪；`vite.config.ts:16-24` 配置 `unplugin-auto-import` 与 `unplugin-vue-components` 生成这两个文件
- **现象**：两个 `.d.ts` 是 unplugin 在 dev/build 时**自动生成**的产物（记录自动导入的 API 与组件类型），当前已被 git 跟踪并随提交入库。
- **影响**：非安全问题，属构建卫生问题，归 Security 维度是因为"构建产物入库"在 §2.4 被列为关注点（与 dist 同类）。后果是：多人协作或分支切换时，这两个文件易产生无意义 diff 与合并冲突；若开发者本地 element-plus 版本不同，生成的 dts 会污染 PR。
- **根因/分析**：unplugin 官方推荐将生成的 dts 加入 .gitignore（首次生成后 IDE 即可识别），项目选择了提交入库的方案。
- **修复方向**：① 将 `src/auto-imports.d.ts`、`src/components.d.ts` 加入 `frontend/.gitignore`（项目当前**无** frontend 级 .gitignore，全部依赖根 .gitignore）并 `git rm --cached`；或 ② 维持现状但在 README 标注"这两个文件由 unplugin 自动生成，请勿手改"。改动面：小
- **关联**：次维度 `[Arch]`；与 F07-05（无 frontend 级 .gitignore）相关

---

## `[Arch]` 架构与技术债

> 排查范围：vite.config.ts 插件链合理性、manualChunks 分包策略、TS 配置严格度、构建脚本门禁强度。共享对象 request.ts 主模块属 F02，本模块只看构建视角。

### [P2] [Arch] `splitVendorChunkPlugin()` 与 `rollupOptions.output.manualChunks` 同时配置，分包行为冲突且前者已弃用 <!-- 编号：F07-04 -->
- **定位**：`frontend/vite.config.ts:15`（`splitVendorChunkPlugin()`）+ `frontend/vite.config.ts:66-83`（`rollupOptions.output.manualChunks`）
- **现象**：vite 配置同时启用了两套 vendor 分包机制：
  1. `splitVendorChunkPlugin()`（vite 内置插件，其内部实现是返回一个带 `manualChunks` 的 rollup 插件）；
  2. 显式 `output.manualChunks(id)`，将 `md-editor-v3`/`markdown-it`/`highlight.js` → `markdown-vendor`，`element-plus`/`@element-plus` → `element-vendor`，`vue-router`/`pinia` → `app-vendor`。
- **影响**：① Rollup 对 `output.manualChunks`（对象/函数形式）与插件提供的 manualChunks 的合并行为依赖版本，vite 5 中 `output.manualChunks` 优先生效，`splitVendorChunkPlugin` **形同虚设**——配置冗余但实际无功能后果；② Vite 官方从 5.x 起在文档/类型层面将 `splitVendorChunkPlugin` 标记为不推荐使用（建议改用 `output.manualChunks`），保留它会让未来升级 vite 6（已移除该 API）时出现编译错误；③ manualChunks 函数对**未命中三个分支的 node_modules 包**（如 `vue` 本体、`axios`、`dayjs`、`dompurify`、`@element-plus/icons-vue`）`return undefined`，这些会落入默认 chunk，意味着 `vue` 核心与业务代码可能被打进同一个 entry chunk，首屏体积未充分优化。
- **根因/分析**：历史演进残留——早期只用 splitVendorChunkPlugin，后加 manualChunks 做精细分包但未移除旧的。已排除"两者协作"的误判：splitVendorChunkPlugin 提供的就是 manualChunks，二者是替代关系不是互补。
- **修复方向**：① 移除 `splitVendorChunkPlugin` 的 import 与 `plugins` 数组中的调用，仅保留显式 `output.manualChunks`；② 在 manualChunks 函数中补一个 `return 'vendor'` 默认分支兜底所有其他 node_modules 包，或显式把 `vue` 也归入 `app-vendor`；③ 升级 vite 6 前必做①。改动面：小
- **关联**：次维度 `[Deps]`（vite 6 升级阻碍）；横向主题"配置一致性"

### [P3] [Arch] 项目无 `frontend/.gitignore`，前端构建产物规则全部下沉到根 .gitignore <!-- 编号：F07-05 -->
- **定位**：`ls frontend/.gitignore` 返回文件不存在；根 `.gitignore` 含 `frontend/node_modules/` 与 `frontend/dist/`
- **现象**：frontend 子目录无独立 .gitignore，所有前端相关忽略规则（node_modules、dist）以 `frontend/xxx` 前缀写在仓库根 .gitignore。`src/auto-imports.d.ts`、`src/components.d.ts`、`frontend.log`（本地开发日志，已存在于工作区）、`tsconfig.app.tsbuildinfo` 等生成物均无忽略规则。
- **影响**：维护成本——前端开发者改构建产物忽略规则要跨目录改根文件；`frontend.log` 这类本地日志无忽略规则，存在误提交风险（目前工作区有该文件且未被跟踪，下次 `git add .` 可能带入）。
- **根因/分析**：Monorepo 常见取舍，并非缺陷，但缺少 frontend 级兜底。
- **修复方向**：新增 `frontend/.gitignore`，至少包含 `node_modules/`、`dist/`、`*.log`、`src/auto-imports.d.ts`、`src/components.d.ts`、`node_modules/.tmp/`。改动面：小
- **关联**：F07-03（生成产物入库）

---

## `[Deps]` 依赖升级与版本

### 本模块依赖清单（基于声明文件，未翻依赖源码）

> 声明版本来自 `frontend/package.json`，lock 实际版本来自 `frontend/package-lock.json`（lockfileVersion 3）抽样。风险判定基于公开已知信息 + 项目使用方式，标 `[需查证]` 处需 `npm audit` / `npm outdated` 实跑复核（本轮命令边界禁止）。

#### dependencies（运行时）

| 依赖 | 声明版本 | lock 实际 | 已知风险 / 可升级 | 备注 |
|---|---|---|---|---|
| `vue` | `^3.4.15` | **3.5.32** | 声明 `^3.4` 但 lock 被拉到 3.5.x 跨大版本；vue 3.5 已稳定可升 3.5 最新；vue 3.4 EOL 在即 | **类型工具链 vue-tsc 仍是 1.8.27（vue 3.3 时代），与运行时 3.5 不匹配**（见 F07-06） |
| `vue-router` | `^4.2.5` | **4.6.4** | 4.x 内升级，无 breaking；可锁定到 `^4.4` 收窄 | |
| `pinia` | `^2.1.7` | **2.3.1** | pinia 2.x 内升级；**pinia 3.0 已发布**（对 vue 3.5 + TS 5 有更好支持），可评估大版本升级 | |
| `pinia-plugin-persistedstate` | `^3.2.1` | **3.2.3** | **v3 已 EOL，官方推荐 v4**（API 有变化，需迁移）；任务简介明确点名此项 | **F07-07** |
| `element-plus` | `^2.5.1` | **2.13.6** | 2.x 内跨多个小版本（2.5→2.13），changelog 较多；无强制升级 | |
| `@element-plus/icons-vue` | `^2.3.1` | 2.3.2 | 当前最新，无风险 | |
| `axios` | `^1.6.5` | **1.16.1** | 1.x 内跨 10 个小版本（声明 1.6 实跑 1.16）；**axios 1.x 有历史 CVE（SSRF/CSRF 相关），1.16 已含修复**，但声明 `^1.6.5` 允许范围过宽 | [需查证] 具体 CVE 编号需 `npm audit` 实跑 |
| `md-editor-v3` | `^4.11.0` | **4.21.3** | 4.x 内升级；任务简介点名 4.11，实际已漂移到 4.21 | |
| `markdown-it` | `^14.2.0` | 14.2.0 | 锁定准确；markdown-it 14 要求 Node 18+，与 engines 一致 | |
| `highlight.js` | `^11.9.0` | **11.11.1** | 11.x 内升级；**highlight.js 历史曾有 ReDoS（CVE-2024-...）**，建议保持最新 11.x | [需查证] |
| `dompurify` | `^3.4.11` | 3.4.11 | 锁定准确；**dompurify 3.x 历史 DOMPurify 有多次 mutation XSS 绕过 CVE**，3.4.11 为较新版本，建议持续跟进 | XSS 防护主防线，F03 主模块 |
| `dayjs` | `^1.11.10` | 1.11.20 | 1.x 内升级，无风险 | |

#### devDependencies（构建期，不进运行时镜像）

| 依赖 | 声明版本 | lock 实际 | 已知风险 / 可升级 | 备注 |
|---|---|---|---|---|
| `vite` | `^5.0.11` | **5.4.21** | **vite 5.x 仍为中危 audit 来源（README 自认）**；**vite 6 已发布**（移除 `splitVendorChunkPlugin`、rollup 4 默认），**vite 7 亦已发布**；升级路径需联动 `@vitejs/plugin-vue`、`vue-tsc`、`unplugin-*` | **F07-06 / F07-08** |
| `@vitejs/plugin-vue` | `^5.0.3` | 5.2.4 | 5.x 内升级；vite 6 需配套 `@vitejs/plugin-vue` 6.x | |
| `vue-tsc` | `^1.8.27` | **1.8.27** | **严重过时**：vue-tsc 1.x 基于 Volar 1.x，仅支持 vue 3.3 类型；当前 vue 运行时为 3.5.32。**vue-tsc 2.x（基于 Volar 2.x）已长期稳定，支持 vue 3.4/3.5 新类型系统**。任务简介明确点名此项 | **F07-06** |
| `typescript` | `~5.3.3` | 5.3.3 | TS 5.3（2023 末发布），**当前 TS 已到 5.7+**；用 `~` 锁定小版本范围偏窄；vue-tsc 2.x 要求 TS 5.4+ | |
| `unplugin-auto-import` | `^0.17.3` | 0.17.8 | 0.17.x；**unplugin-auto-import 0.18+/1.x 已发布**，对 vite 6 / vue 3.5 适配更好 | |
| `unplugin-vue-components` | `^0.26.0` | 0.26.0 | 0.26.x；**0.28+/1.x 已发布**；overrides 中强行固定其 `minimatch` 为 9.0.9（见 F07-09） | |
| `unplugin-icons` | `^23.0.1` | 23.0.1 | `autoInstall: true`（vite.config.ts:26）会在缺图标时**自动 npm install**，CI/无网环境会失败 | F07-10 |
| `vite-plugin-compression` | `^0.5.1` | 0.5.1 | **该包长期未更新**（最后发布久远），社区已转向 `vite-plugin-compression2`；lock 确认未标 deprecated 但维护停滞 | [需查证] |
| `sass` | `^1.70.0` | **1.99.0** | 1.x 内升级；sass 1.99 已是较新版本，声明范围允许 | |
| `tailwindcss` | `^3.4.1` | 3.4.19 | 3.x 内升级；**tailwindcss 4.0 已发布**（CSS-first 配置， breaking 较多） | |
| `eslint` | `^8.56.0` | **8.57.1** | **eslint 8 已 EOL（2024 末停维护）**，官方推荐 eslint 9（flat config，breaking）；当前 `.eslintrc.cjs` 为旧 config 格式，升级需重写 | |
| `@vue/eslint-config-typescript` | `^12.0.0` | 12.0.0 | 12.x 配 eslint 8；eslint 9 需 13.x+ | |
| `@vue/tsconfig` | `^0.5.1` | 0.5.1 | 0.5.x；**0.6+/0.7 已发布**，对 vue 3.5 适配更好 | |
| `@types/markdown-it` | `^13.0.7` | **13.0.9** | **版本不匹配**：实际 `markdown-it` 是 14.x，但 `@types/markdown-it` 还是 13.x。markdown-it 14 自带类型，**`@types/markdown-it` 已不必要**（markdown-it 13+ 起 DefinitelyTyped 已 deprecated 该包） | F07-11 |
| `@types/dompurify` | `^3.0.5` | 3.0.5 | **dompurify 3.x 自带类型**，`@types/dompurify` 已 deprecated（与 markdown-it 同类问题） | F07-11 |
| `@types/node` | `^20.11.5` | 20.19.39 | 与 engines `node>=18` + Dockerfile `node:20-alpine` 一致，无风险 | |
| `@tsconfig/node20` | `^20.1.2` | 20.1.9 | tsconfig 预设，未被 tsconfig.json extends 引用（tsconfig 只 extends `@vue/tsconfig`），**疑似未使用** | [需查证] |
| `@rushstack/eslint-patch` | `^1.7.0` | — | 被 `.eslintrc.cjs:2` 用于 modern-module-resolution | |
| `prettier` | `^3.2.4` | — | 正常；但 `.prettierrc` 引用了未声明的 `prettier-plugin-tailwindcss`（F07-01） | |
| `autoprefixer` / `postcss` | — | — | postcss 链正常 | |

### [P1] [Deps] `vue-tsc@1.8.27` 严重落后于运行时 `vue@3.5.32`，类型检查门禁形同虚设 <!-- 编号：F07-06 -->
- **定位**：`vue@3.5.32`（lock）+ `vue-tsc@1.8.27`（`package.json:50` + lock）；`vue-tsc` 的依赖 `@volar/typescript@~1.11.1` + `@vue/language-core@1.8.27`（lock 抽样）
- **现象**：运行时 vue 已到 3.5.32（声明 `^3.4.15` 被 ^ 拉升），但类型检查工具 vue-tsc 仍是 1.8.27——这是 vue 3.3 时代的 Volar 1.x 工具链。vue 3.4 引入了 `defineModel`、3.5 引入了响应式 props 解构等新类型特性，vue-tsc 1.8 **无法正确检查这些语法**。
- **影响**：`npm run build` = `vue-tsc && vite build`（`package.json:8`），vue-tsc 1.8 对 vue 3.5 代码的类型检查**能力不足**——可能漏报类型错误（类型门禁没起到应有作用），或对新语法误报；类型检查成了"走过场"。这是 README 自认"dev audit 有 vue-tsc 相关中危"的根因之一。
- **根因/分析**：vue-tsc 2.0（基于 Volar 2.0）于 2024 年发布，要求 TS 5.4+；当前 typescript 锁定 `~5.3.3` 形成连带阻塞（vue-tsc 2.x 装不上）。三件套（vue-tsc + typescript + vue）版本不协调。
- **修复方向**：① 同步升级 `vue-tsc` → 2.x（最新稳定）、`typescript` → 5.6+ 或 5.7+、`@vue/tsconfig` → 0.7+；② 升级后 `npm run build` 验证类型检查能正常阻断错误；③ 评估 `vue` 声明版本显式收窄到 `^3.5` 避免再次静默跨大版本。改动面：中（需跑通类型检查并修复可能的既有类型报错）
- **关联**：F07-08（vite 6 升级联动）；横向主题"配置一致性"

### [P1] [Deps] `pinia-plugin-persistedstate@^3.2.1` 对应 v3 已 EOL，官方建议升 v4 <!-- 编号：F07-07 -->
- **定位**：`frontend/package.json:23`（`"pinia-plugin-persistedstate": "^3.2.1"`）+ lock 实际 3.2.3
- **现象**：persistedstate v3 已结束维护（官方文档明确 v4 为当前主线）。任务简介明确点名此项。
- **影响**：v3 不再接收 bug 修复与安全更新；v4 API 有 breaking（`persist` option 写法、Serializer/Storage 接口变化），但迁移成本可控。F06（Pinia 状态管理）实际使用该插件做持久化，EOL 状态会传导到所有持久化 store。
- **根因/分析**：MVP 阶段为求稳留在 v3，未跟进官方主线。
- **修复方向**：① 评估升级到 v4，主要改 `defineStore` 第三参数的 `persist` 配置写法；② 升级前先 grep 所有用到 `persist: true` / `persist: {...}` 的 store（F06 主模块）评估改动面。改动面：中（涉及多个 store 文件 + 测试）
- **关联**：F06（状态管理主模块）；次维度 `[Arch]`

### [P2] [Deps] vite 5.x 为 dev audit 中危来源，vite 6/7 已发布；升级受 vue-tsc/unplugin 连带阻塞 <!-- 编号：F07-08 -->
- **定位**：`vite@^5.0.11`（lock 5.4.21）+ `package.json:48`；README.md:23 / frontend/README.md:16 / deploy/README.md:179 / docs/trial-release-roadmap.md:38,101 自认"dev audit 仍有 vite/vue-tsc 中危"
- **现象**：vite 5.4.21 仍在 5.x 维护线，但 vite 6（2024 末）与 vite 7（2025）已相继发布，5.x 的安全补丁窗口在收窄。README 已自认 dev audit（非生产依赖）有 vite/vue-tsc 相关中危项。
- **影响**：dev 依赖漏洞**不进 nginx 运行时镜像**（Dockerfile 多阶段只 COPY dist），运行时风险低；但开发者本地 `npm install` 仍会拉取带漏洞的 vite 依赖链，且阻碍其他工具链升级（eslint 9 / vue-tsc 2 等都可能要求 vite 6+）。
- **根因/分析**：MVP 稳定化优先，README 已将此项列为 P2 待办（docs/trial-release-roadmap.md:101），**结论与既有文档一致，不重复铺陈，仅补本模块视角**：升级 vite 6 必须先移除 `splitVendorChunkPlugin`（vite 6 已删除该 API，见 F07-04），这是文档未提及的具体阻塞点。
- **修复方向**：① 按文档既定计划排期升级 vite 6 → 7；② 升级前先完成 F07-04（移除 splitVendorChunkPlugin）、F07-06（vue-tsc 2.x）；③ 升级后重跑 dev audit 验证中危清零。改动面：中
- **关联**：F07-04、F07-06；既有风险登记册已收录（docs/trial-release-roadmap.md:101）

### [P2] [Deps] 多处 `@types/*` 包与运行时版本不匹配或已 deprecated <!-- 编号：F07-11 -->
- **定位**：`@types/markdown-it@^13.0.7`（lock 13.0.9，实际 markdown-it 14.2.0）、`@types/dompurify@^3.0.5`（lock 3.0.5，实际 dompurify 3.4.11）
- **现象**：`markdown-it@14` 与 `dompurify@3.x` **自身已内置 TypeScript 类型**，对应的 `@types/markdown-it` 与 `@types/dompurify` 在 DefinitelyTyped 上已被标记 deprecated（包 README 会提示"this is a stub, the real package ships types"）。
- **影响**：项目同时存在两套类型来源，可能产生类型冲突或编译告警；增加无谓的 dev 依赖体积。
- **根因/分析**：早期 markdown-it/dompurify 还没自带类型时引入的 @types，主包升级后未清理。
- **修复方向**：① 删除 `@types/markdown-it` 与 `@types/dompurify`，让 TS 直接用主包自带类型；② 删除后跑 `vue-tsc` 验证无类型回归。改动面：小
- **关联**：F07-06（vue-tsc 升级时一并清理）

### [P3] [Deps] `unplugin-icons` 配置 `autoInstall: true`，CI/无网环境会自动 npm install <!-- 编号：F07-10 -->
- **定位**：`frontend/vite.config.ts:25-27`（`Icons({ autoInstall: true })`）
- **现象**：unplugin-icons 开启 `autoInstall`，当代码中引用某个图标集（如 `@iconify-json/xxx`）但项目未安装时，插件会**自动执行 npm install**。
- **影响**：① CI/无外网环境的 Docker 构建（Dockerfile 在 `npm ci` 后才 `npm run build`）若触发自动安装会失败或污染 lockfile 一致性；② 自动安装的包不进 package.json/lock，破坏可复现性。当前 `package.json` 未声明任何 `@iconify-json/*`，需 [需查证] 源码是否真的用了 unplugin-icons 图标组件。
- **根因/分析**：开发期便利配置，未考虑 CI 严格性。
- **修复方向**：① 改为 `autoInstall: false`，所需图标集显式写入 devDependencies；② 先 grep 确认是否真有图标使用，若无则考虑直接移除 unplugin-icons 插件。改动面：小
- **关联**：[需查证] 源码实际图标使用情况

### [P3] [Deps] 声明版本范围普遍用 `^` 允许跨小版本漂移，lock 与 package.json 长期不一致 <!-- 编号：F07-12 -->
- **定位**：`package.json` 全量（几乎全部依赖用 `^`）
- **现象**：多个依赖的声明版本与 lock 实际版本差距较大：vue `^3.4.15`→3.5.32、axios `^1.6.5`→1.16.1、element-plus `^2.5.1`→2.13.6、md-editor-v3 `^4.11.0`→4.21.3、vite `^5.0.11`→5.4.21、pinia `^2.1.7`→2.3.1。lock 锁定了实际版本（Docker `npm ci` 可复现），但 package.json 声明落后，给人"项目还在用旧版"的错觉。
- **影响**：非 bug（lock 保证可复现），但增加维护者认知负担，`npm outdated` 输出与实际不符；声明与实际漂移过大时，未来 `npm install`（非 ci）可能拉到声明范围内更新的版本引入意外行为。
- **根因/分析**：依赖更新只更新 lock 未同步改 package.json 声明。
- **修复方向**：① 定期把 package.json 声明版本 bump 到与 lock 一致或收窄范围（如 vue 改 `^3.5.0`、axios 改 `^1.16.0`）；② 或对关键依赖用 `~` 锁定小版本。改动面：小
- **关联**：次维度 `[Arch]`

### [P3] [Deps] `@tsconfig/node20` 疑似未使用（tsconfig.json 未 extends 它） <!-- 编号：F07-13 -->
- **定位**：`frontend/package.json:29`（`"@tsconfig/node20": "^20.1.2"`）对照 `frontend/tsconfig.json:2`（`"extends": "@vue/tsconfig/tsconfig.dom.json"`）
- **现象**：tsconfig.json 只 extends `@vue/tsconfig/tsconfig.dom.json`，**未引用 `@tsconfig/node20`**。该 devDependency 疑似未使用。
- **影响**：无功能后果，仅冗余依赖。
- **根因/分析**：脚手架默认带入但项目用了 `@vue/tsconfig` 替代。[需查证] 是否有其他 tsconfig（如 tsconfig.node.json）引用——当前 frontend 目录下只有一个 tsconfig.json。
- **修复方向**：确认无其他 tsconfig 引用后从 devDependencies 移除。改动面：小
- **关联**：[需查证]

---

## `[Design]` 功能设计合理性

> 从真实使用出发，回答 §2.5 中相关问题。本模块为构建/依赖模块，重点回答"场景适配"、"可运维性"、"单点与扩展"。

**审视结论**：

1. **场景适配（§2.5-1）**：单人维护的技术博客 + 每工作日 AI 日报场景下，当前构建链（vite 5 + vue-tsc + manualChunks + gzip）**功能上足够**，首屏分包策略（markdown-vendor / element-vendor / app-vendor 三大块）思路正确，能把编辑器与 UI 库隔离出首屏 chunk。但 `splitVendorChunkPlugin` 冗余配置（F07-04）和未兜底的 manualChunks 默认分支（vue 本体未归入任何 vendor chunk）说明分包策略**停在"能用"未到"调优过"**——对单人博客够用，但偏离了"已优化"的自我认知。

2. **可运维性（§2.5-3）**：Dockerfile 多阶段构建（builder → nginx）+ `npm ci` 优先 + lockfile 入库，**可复现性与供应链设计是本模块最扎实的地方**，dev 依赖漏洞不进运行时镜像这一隔离设计值得肯定。但构建失败的排查路径偏弱：`vue-tsc` 类型检查因版本不匹配（F07-06）能力打折，类型错误可能漏过到运行时；prettier 插件缺失（F07-01）会让 `npm run format` 直接失败——这些是"看起来配置齐全实则跑不通"的半成品状态。

3. **单点与扩展（§2.5-7）**：前端构建链为单服务设计，无扩展压力。真正的扩展瓶颈在**升级路径的连带阻塞**：vite 6 升级需要同步移除 splitVendorChunkPlugin（F07-04）+ 升级 vue-tsc（F07-06）+ 升级 unplugin-* + typescript，形成"一动全动"的耦合簇，任意一环卡住整个升级都停滞。这解释了为什么 README 自认的"vite/vue-tsc 中危"长期未修——不是不想修，是升级入口被版本耦合锁死。

### [P4] [Design] 构建链版本耦合形成"升级簇"，建议规划一次性工具链升级窗口 <!-- 编号：F07-14 -->
- **定位**：F07-04 / F07-06 / F07-08 / F07-11 的联合观察
- **现象**：vite 6 升级、vue-tsc 2 升级、eslint 9 升级、typescript 5.4+ 升级、unplugin-* 升级、pinia-plugin-persistedstate v4 升级相互耦合，单项升级难以独立完成。
- **影响**：README 自认的"前端工具链中危 audit"（docs/trial-release-roadmap.md:101 P2 项）长期搁置，技术债随时间累积。
- **建议方向**：规划一个"前端工具链升级"专项窗口，一次性完成 vue-tsc 2 + typescript 5.6+ + vite 6 + 移除 splitVendorChunkPlugin + unplugin 升级 + eslint 9（可选）+ pinia-plugin-persistedstate v4，避免长期被版本耦合锁死。改动面：大（但单次集中投入优于多次零散修补）
- **关联**：F07-04 / F07-06 / F07-07 / F07-08 / F07-11；docs/trial-release-roadmap.md:101

---

## 模块小结

### 严重度统计

| 级别 | 数量 | 条目编号 |
|---|---|---|
| P0 | 0 | — |
| P1 | 2 | F07-06（vue-tsc 落后）、F07-07（persistedstate v3 EOL） |
| P2 | 4 | F07-01（prettier 插件缺失）、F07-04（splitVendor 冲突+弃用）、F07-08（vite 5 audit）、F07-11（@types 不匹配） |
| P3 | 5 | F07-02（死 env 配置）、F07-03（生成 dts 入库）、F07-05（无 frontend 级 gitignore）、F07-10（unplugin-icons autoInstall）、F07-12（声明版本漂移）、F07-13（@tsconfig/node20 未用） |
| P4 | 1 | F07-14（升级簇规划建议） |

> 注：P3 实际 6 条，上表修正为 6。

### Top 风险（本模块最该先看的 ≤3 条）

1. **F07-06 vue-tsc 1.8.27 与运行时 vue 3.5 严重不匹配** —— 类型检查门禁 `vue-tsc && vite build` 实际能力打折，类型错误可能漏过到生产，是构建链最该先修的项。
2. **F07-04 splitVendorChunkPlugin 与 manualChunks 冲突且前者已弃用** —— 当前冗余无害，但会阻塞 vite 6 升级，是升级簇的入口卡点。
3. **F07-01 .prettierrc 引用未声明的 prettier-plugin-tailwindcss** —— `npm run format` 直接失败，是"看起来配置齐全实则跑不通"的典型，影响日常开发体验。

### 修复优先级建议

- **立即**（P1）：F07-06（vue-tsc 2 + typescript 5.6+ 升级，需配套修复类型报错）、F07-07（persistedstate v4 迁移，联动 F06）
- **计划**（P2）：F07-01（补 prettier-plugin-tailwindcss 依赖或移除配置）、F07-04（移除 splitVendorChunkPlugin，为 vite 6 铺路）、F07-08（按文档既定计划升 vite 6）、F07-11（清理 @types/markdown-it、@types/dompurify）
- **择机**（P3/P4）：F07-02 / F07-03 / F07-05 / F07-10 / F07-12 / F07-13（构建卫生与配置清理）、F07-14（规划一次性工具链升级窗口）

### 排查盲区 / 待复核

- **[需查证]** `axios` 1.6→1.16 跨版本的具体 CVE 编号与影响（需 `npm audit` 实跑，本轮命令边界禁止）。
- **[需查证]** `highlight.js` 11.x 历史 ReDoS CVE 在 11.11.1 是否已修复。
- **[需查证]** `dompurify` 3.4.11 相对最新 3.x 是否仍有未修复的 mutation XSS 绕过。
- **[需查证]** `vite-plugin-compression@0.5.1` 的维护状态与是否有已知 bug（lock 未标 deprecated）。
- **[需查证]** `unplugin-icons` 在源码中的实际图标使用情况（F07-10 自动安装是否真会触发）。
- **[需查证]** `@tsconfig/node20` 是否被某个未发现的 tsconfig 引用（F07-13）。
- **[需查证]** 生产构建实际首屏 chunk 体积分布（需跑 `npm run build` 看 chunk 报告，本轮禁止；可结合 vite 的 chunkSizeWarningLimit=1000 阈值与 manualChunks 兜底缺失推断 vue 本体大概率进了 entry chunk）。
- **本次未做**：未跑 `npm audit` / `npm outdated` / `npm run build`（命令边界禁止）；未翻 `node_modules`（仅对 package-lock.json 用 node 脚本抽样版本字段，未读依赖源码逻辑）；未跑 `vue-tsc` 验证当前类型报错数（禁止 npm 脚本）。
