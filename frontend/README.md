# Nanmuli Blog Frontend

> Vue 3 + TypeScript + Vite 前端。当前作为 Nanmuli Blog MVP Beta 的公开站点和管理后台。

## 当前状态

最后复核日期：2026-06-03

- `npm run build` 已通过。
- `npm audit --omit=dev --registry=https://registry.npmjs.org` 为 `0 vulnerabilities`。
- `frontend/package-lock.json` 已纳入仓库，用于保证 Docker/CI 中 `npm ci` 可复现。
- Vite chunk warning 已通过 `chunkSizeWarningLimit=1000` 调整为符合当前 vendor 包体积的提示阈值。

剩余说明：

- 全量 dev audit 仍有 Vite/vue-tsc 相关中危项，修复需要大版本升级，当前不阻断 MVP 试用。
- `element-vendor` 和 `markdown-vendor` 体积较大，gzip 后仍可接受；后续可通过按需加载编辑器继续优化。

## 技术栈

| 技术 | 版本/说明 |
| --- | --- |
| Vue | 3.4 |
| TypeScript | 5.3 |
| Vite | 5.4 |
| Element Plus | 2.5 |
| Pinia | 2 |
| Vue Router | 4 |
| Tailwind CSS | 3.4 |
| md-editor-v3 | Markdown 编辑器 |

## 主要功能

| 区域 | 功能 |
| --- | --- |
| 公开站点 | 首页、文章列表/详情、技术日志、项目/技能、友链、技术日报 |
| 管理后台 | 登录、文章、分类、日志、项目、技能、文件、系统配置、采集器、日报、信息源、友链 |
| 日报系统 | 列表、详情、任务详情、手动触发、状态轮询、质量趋势入口 |
| 采集器 | 任务列表、详情、信息源管理、采集结果查看 |

## 目录结构

```text
frontend/
├── src/
│   ├── api/              # API 封装
│   ├── components/       # 通用和业务组件
│   ├── composables/      # 组合式逻辑
│   ├── constants/        # 常量
│   ├── layouts/          # 页面布局
│   ├── router/           # 路由
│   ├── stores/           # Pinia 状态
│   ├── styles/           # 全局样式
│   ├── types/            # TypeScript 类型
│   ├── utils/            # 工具函数
│   └── views/            # 页面
├── Dockerfile
├── package.json
├── package-lock.json
└── vite.config.ts
```

## 开发命令

```bash
npm install
npm run dev
npm run build
npm audit --omit=dev --registry=https://registry.npmjs.org
```

默认开发端口：`http://localhost:3001`。

## Docker 构建

前端由根目录上下文构建：

```bash
cd ../deploy
docker compose --env-file .env.example build frontend
```

`frontend/Dockerfile` 使用 Node 构建静态产物，再复制到 Nginx 镜像运行。

## 开发约定

- API 请求统一放在 `src/api/`。
- 类型统一放在 `src/types/`。
- 轮询类逻辑优先复用 `composables/usePolling.ts`。
- 管理端页面放在 `src/views/admin/`。
- 公开页面放在 `src/views/` 对应业务目录。
- 新增页面后同步更新 `src/router/routes.ts` 和侧边栏入口。
