# Nanmuli Blog Frontend

个人技术博客系统前端 - 基于 Vue 3 + TypeScript + Vite

## 技术栈

- **框架**: Vue 3.4+
- **语言**: TypeScript 5+
- **构建**: Vite 5+
- **UI库**: Element Plus 2.5+
- **样式**: Tailwind CSS 3.4+
- **状态管理**: Pinia 2+
- **路由**: Vue Router 4+
- **编辑器**: md-editor-v3

## 项目结构

```
frontend/
├── src/
│   ├── api/              # API 接口层
│   │   ├── auth.ts
│   │   ├── article.ts
│   │   ├── category.ts
│   │   ├── tag.ts
│   │   ├── dailyLog.ts
│   │   ├── project.ts
│   │   ├── skill.ts
│   │   ├── config.ts
│   │   └── file.ts
│   ├── components/       # 组件
│   │   └── common/       # 公共组件
│   ├── layouts/          # 布局组件
│   │   ├── DefaultLayout.vue
│   │   ├── AdminLayout.vue
│   │   └── BlankLayout.vue
│   ├── router/           # 路由配置
│   ├── stores/           # 状态管理
│   │   └── modules/
│   ├── styles/           # 样式文件
│   ├── types/            # TypeScript 类型
│   ├── utils/            # 工具函数
│   └── views/            # 页面视图
├── package.json
├── vite.config.ts
├── tsconfig.json
└── tailwind.config.js
```

## 开发环境

### 安装依赖

```bash
pnpm install
```

### 启动开发服务器

```bash
pnpm dev
```

### 构建生产版本

```bash
pnpm build
```

## 特性

- ✨ Vue 3 组合式 API
- 📝 TypeScript 类型安全
- 🎨 Element Plus UI 组件
- 🎯 Tailwind CSS 原子化样式
- 🚀 Vite 快速构建
- 📦 自动导入组件和 API
- 🔄 Pinia 状态管理 + 持久化
- 📱 响应式设计

## 开发规范

### 代码规范

- 使用 `const` 优先，`let` 次之，禁止 `var`
- 使用 `===` 严格比较，禁止 `==`
- 函数必须有返回类型注解
- 禁止使用 `any`，使用 `unknown` + 类型守卫

### 提交规范

```bash
feat: 新功能
fix: Bug修复
docs: 文档更新
style: 代码格式（不影响功能）
refactor: 重构
perf: 性能优化
test: 测试相关
chore: 构建/工具相关
```
