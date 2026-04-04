# 前端架构说明

## 目录结构规范

```
src/
├── api/                          # API 接口层
│   ├── index.ts                  # API 统一导出
│   ├── article.ts                # 文章相关 API
│   ├── auth.ts                   # 认证相关 API
│   ├── category.ts               # 分类相关 API
│   ├── config.ts                 # 配置相关 API
│   ├── dailyLog.ts               # 日志相关 API
│   ├── file.ts                   # 文件相关 API
│   ├── project.ts                # 项目相关 API
│   ├── skill.ts                  # 技能相关 API
│   └── tag.ts                    # 标签相关 API
│
├── components/                   # 组件层
│   ├── article/                  # 文章相关组件
│   │   ├── ArticleCard.vue
│   │   ├── ArticleList.vue
│   │   ├── ArticleContent.vue
│   │   ├── ArticleMeta.vue
│   │   ├── ArticleTags.vue
│   │   └── ArticleToc.vue
│   ├── common/                   # 通用组件
│   │   ├── AppHeader.vue
│   │   ├── AppFooter.vue
│   │   └── AppSidebar.vue
│   ├── dailyLog/                 # 日志相关组件
│   ├── editor/                   # 编辑器组件
│   ├── project/                  # 项目相关组件
│   ├── skill/                    # 技能相关组件
│   └── search/                   # 搜索组件
│
├── composables/                  # Vue 组合式函数
│   ├── index.ts
│   ├── useArticle.ts
│   ├── useAuth.ts
│   ├── useConfig.ts
│   ├── useDailyLog.ts
│   └── useTheme.ts
│
├── constants/                    # 常量定义（新增）
│   ├── index.ts                  # 业务常量
│   └── api.ts                    # API 常量
│
├── layouts/                      # 布局组件
│   ├── DefaultLayout.vue         # 默认布局
│   ├── AdminLayout.vue           # 管理后台布局
│   └── BlankLayout.vue           # 空白布局
│
├── router/                       # 路由配置
│   ├── index.ts                  # 路由入口
│   ├── routes.ts                 # 路由定义
│   └── guards.ts                 # 路由守卫
│
├── stores/                       # Pinia 状态管理
│   ├── index.ts
│   └── modules/
│       ├── app.ts                # 应用状态
│       ├── article.ts            # 文章状态
│       ├── config.ts             # 配置状态
│       ├── dailyLog.ts           # 日志状态
│       └── user.ts               # 用户状态
│
├── styles/                       # 全局样式（可选）
│
├── types/                        # TypeScript 类型定义
│   ├── index.ts
│   ├── api.ts
│   ├── article.ts
│   ├── category.ts
│   ├── config.ts
│   ├── dailyLog.ts
│   ├── project.ts
│   ├── skill.ts
│   ├── tag.ts
│   └── user.ts
│
├── utils/                        # 工具函数
│   ├── request.ts                # HTTP 请求封装
│   ├── storage.ts                # 本地存储封装
│   ├── format.ts                 # 格式化工具
│   ├── markdown.ts               # Markdown 处理
│   └── validate.ts               # 验证工具
│
└── views/                        # 页面视图
    ├── home/                     # 首页
    ├── article/                  # 文章页面
    ├── dailyLog/                 # 日志页面
    ├── category/                 # 分类页面
    ├── tag/                      # 标签页面
    ├── project/                  # 项目页面
    ├── about/                    # 关于页面
    ├── auth/                     # 认证页面
    ├── admin/                    # 管理后台
    │   ├── article/
    │   ├── dailyLog/
    │   ├── category/
    │   ├── tag/
    │   ├── project/
    │   ├── skill/
    │   └── config/
    └── error/                    # 错误页面
```

## 新增 constants 目录

`constants/` 目录用于存放应用中的常量，包括：

- 枚举值定义（文章状态、技能分类等）
- 业务常量（默认分页大小、应用名称等）
- 存储键名
- 路由名称

示例：
```typescript
// constants/index.ts
export enum ArticleStatus {
  DRAFT = 0,
  PUBLISHED = 1,
  RECYCLED = 2,
}

export const DEFAULT_PAGE_SIZE = 10
export const STORAGE_KEYS = {
  TOKEN: 'blog_token',
  USER: 'blog_user',
}
```

## 命名规范

- **组件文件**：PascalCase，如 `ArticleCard.vue`
- **工具/组合式函数**：camelCase 前缀 use，如 `useArticle.ts`
- **常量**：SCREAMING_SNAKE_CASE，如 `DEFAULT_PAGE_SIZE`
- **类型**：PascalCase，如 `Article.ts`
