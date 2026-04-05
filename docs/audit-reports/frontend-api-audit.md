# Nanmuli Blog 前端 API 层与状态管理层审计报告

**审计日期**: 2026-04-05  
**审计范围**: frontend/src/api/、frontend/src/stores/、frontend/src/utils/request.ts  
**审计人员**: Claude Code (代码审计技能)

---

## 执行摘要

本次审计针对 Nanmuli Blog 前端项目的 API 层和状态管理层进行了全面检查，发现以下关键问题：

- **P0 功能缺陷**: 3 项（401处理、并发请求、类型一致性）
- **P1 架构问题**: 4 项（Store划分、重复状态、错误处理）
- **P4 代码质量**: 5 项（类型定义、参数一致性）

---

## 一、功能缺陷 (P0)

### 1.1 [P0-Critical] request.ts 中 401 处理直接跳转导致未完成请求被中断

**文件**: `frontend/src/utils/request.ts`  
**位置**: 第 33-36 行

```typescript
if (data.code === 401) {
  localStorage.removeItem('token')
  window.location.href = '/login'
}
```

**问题描述**:
1. **未完成的请求被强制中断**: 当收到 401 响应时，代码直接执行 `window.location.href = '/login'`，这会立即中断所有正在进行的请求，导致数据丢失或状态不一致。
2. **无请求队列刷新机制**: 在跳转前没有等待其他并发请求完成或取消，可能导致部分请求处于 pending 状态。
3. **用户体验差**: 如果用户正在编辑内容，直接跳转会导致未保存的数据丢失。

**攻击场景/影响**:
- 用户在提交表单时 Token 过期，表单数据丢失
- 多个 API 并发请求时，其中一个触发 401，其他请求被强制中断，导致页面状态部分更新

**修复建议**:
```typescript
// 建议实现请求队列管理和优雅降级
let isRefreshing = false
let failedQueue: Array<() => void> = []

// 在 401 处理中
if (data.code === 401) {
  localStorage.removeItem('token')
  
  // 方案1: 使用 Vue Router 进行导航（不会强制刷新页面）
  import('@/router').then(({ default: router }) => {
    router.push('/login')
  })
  
  // 方案2: 触发全局事件让应用层处理
  window.dispatchEvent(new CustomEvent('auth:expired', { detail: data.message }))
}
```

---

### 1.2 [P0-High] Token 过期后并发请求的处理问题

**文件**: `frontend/src/utils/request.ts`  
**位置**: 第 12-24 行（请求拦截器）

**问题描述**:
1. **无 Token 刷新机制**: 当 Token 过期时，系统没有实现自动刷新 Token 的机制，而是直接跳转登录页。
2. **并发请求竞争**: 如果多个请求同时触发 401，每个请求都会尝试清除 token 并跳转，可能导致竞态条件。
3. **无请求重试机制**: 刷新 Token 后，失败的请求没有被重新发起。

**修复建议**:
```typescript
// 实现 Token 刷新队列
let isRefreshing = false
let subscribers: Array<(token: string) => void> = []

function onTokenRefreshed(token: string) {
  subscribers.forEach(callback => callback(token))
  subscribers = []
}

function addSubscriber(callback: (token: string) => void) {
  subscribers.push(callback)
}

// 在响应拦截器中
if (error.response?.status === 401 && !originalRequest._retry) {
  if (isRefreshing) {
    // 等待 Token 刷新完成
    return new Promise(resolve => {
      addSubscriber(token => {
        originalRequest.headers.Authorization = token
        resolve(request(originalRequest))
      })
    })
  }
  // ... 刷新 Token 逻辑
}
```

---

### 1.3 [P0-Medium] API 返回类型定义与实际响应一致性风险

**文件**: `frontend/src/utils/request.ts`  
**位置**: 第 27-41 行

**问题描述**:
1. **类型断言风险**: 响应拦截器返回 `data.data`，但 TypeScript 类型系统无法验证实际返回的数据结构是否与声明的类型一致。
2. **缺少运行时类型校验**: 没有使用 Zod、Yup 或 io-ts 等运行时类型校验库。
3. **泛型滥用**: `get<T>`、`post<T>` 等函数的泛型参数可以被任意指定，缺乏约束。

**修复建议**:
```typescript
// 引入运行时类型校验（如 Zod）
import { z } from 'zod'

const ApiResponseSchema = <T extends z.ZodType>(dataSchema: T) =>
  z.object({
    code: z.number(),
    message: z.string(),
    data: dataSchema,
    timestamp: z.number()
  })

export async function get<T extends z.ZodType>(
  url: string, 
  schema: T,
  config?: AxiosRequestConfig
): Promise<z.infer<T>> {
  const response = await request.get(url, config)
  const validated = ApiResponseSchema(schema).parse(response.data)
  return validated.data
}
```

---

## 二、架构问题 (P1)

### 2.1 [P1-High] Store 模块划分合理性

**文件**: `frontend/src/stores/modules/`  
**相关文件**: `article.ts`、`dailyLog.ts`

**问题描述**:
1. **Store 职责过重**: `articleStore` 和 `dailyLogStore` 同时管理列表数据、当前详情、分页状态和加载状态，违反了单一职责原则。
2. **缺少分类/标签/项目/技能的 Store**: 这些模块只有 API 层，没有对应的状态管理，数据获取逻辑可能分散在组件中。
3. **Store 与 API 层耦合**: Store 直接调用 API，但没有缓存策略或数据失效机制。

**建议的 Store 划分**:
```
stores/
├── entities/           # 实体状态（归一化存储）
│   ├── articles.ts
│   ├── dailyLogs.ts
│   ├── categories.ts
│   └── tags.ts
├── ui/                 # UI 状态
│   ├── articleList.ts
│   ├── articleDetail.ts
│   └── pagination.ts
└── auth/               # 认证状态
    └── user.ts
```

---

### 2.2 [P1-Medium] 存在重复状态

**文件**: `frontend/src/stores/modules/article.ts`、`dailyLog.ts`

**问题描述**:
1. **重复的 pagination 结构**: 两个 Store 中都定义了相同的 pagination 结构
2. **重复的 loading 模式**: 每个 Store 都独立管理 loading 状态，没有统一封装。
3. **重复的 CRUD 操作**: `saveArticle` 和 `saveLog` 等操作逻辑高度相似。

**修复建议**:
```typescript
// 创建可复用的 Store 工厂函数
function createEntityStore<T>(name: string, api: EntityApi<T>) {
  return defineStore(name, () => {
    const items = ref<T[]>([])
    const currentItem = ref<T | null>(null)
    const loading = ref(false)
    const pagination = usePagination() // 复用分页逻辑
    
    // 通用的 CRUD 操作
    async function fetchList(query?: QueryParams) { /* ... */ }
    async function save(data: Partial<T>) { /* ... */ }
    
    return { items, currentItem, loading, pagination, fetchList, save }
  })
}
```

---

### 2.3 [P1-Medium] API 层错误处理不一致

**文件**: `frontend/src/api/*.ts`

**问题描述**:
1. **部分 API 无错误处理**: 所有 API 函数都依赖 request.ts 的全局错误处理，没有本地错误处理或降级策略。
2. **错误信息无法定制**: 全局统一使用 `ElMessage.error`，某些场景需要更友好的错误提示。
3. **无重试机制**: 网络抖动或临时故障时没有自动重试。

---

### 2.4 [P1-Low] Store persist 配置与 request.ts 的 Token 管理不一致

**文件**: `frontend/src/stores/modules/user.ts`  
**位置**: 第 60-64 行

**问题描述**:
1. **双重存储**: Token 同时存储在 Pinia 的 persist 和 localStorage 中，可能导致不一致。
2. **userStore 依赖 localStorage**: 初始化时从 localStorage 读取，但 persist 也会恢复状态。

---

## 三、代码质量 (P4)

### 3.1 [P4-Medium] TypeScript 类型定义不完整

**文件**: `frontend/src/api/file.ts`  
**位置**: 第 3 行

**问题描述**:
`usageType` 参数使用 `string` 类型，但应该是有限的枚举值。

**修复建议**:
```typescript
export type FileUsageType = 'article' | 'avatar' | 'project' | 'skill' | 'daily-log'

export function uploadFile(
  file: File, 
  usageType: FileUsageType
): Promise<{ url: string; fileName: string }>
```

---

### 3.2 [P4-Low] 请求参数拼写一致性

**文件**: `frontend/src/api/article.ts`、`dailyLog.ts`、`category.ts`

**问题描述**:
- `article.ts` 使用 `params` 作为参数名
- `category.ts` 使用 `query` 作为参数名

**修复建议**: 统一使用 `params` 或 `query`。

---

### 3.3 [P4-Low] 类型文件中存在废弃定义

**文件**: `frontend/src/types/article.ts`  
**位置**: 第 44-49 行

**问题描述**:
`Tag` 接口被标记为"已废弃"，但仍然在类型文件中定义。

---

### 3.4 [P4-Low] Store 中的计算属性命名不一致

**文件**: `frontend/src/stores/modules/article.ts`、`dailyLog.ts`

**问题描述**:
- `articleStore` 使用 `articleList` 作为计算属性名
- `dailyLogStore` 使用 `logList` 作为计算属性名

---

### 3.5 [P4-Low] 缺少 API 请求超时和取消机制

**文件**: `frontend/src/utils/request.ts`

**问题描述**:
1. 虽然有全局 timeout 配置，但没有提供按请求定制的超时能力。
2. 没有请求取消机制（AbortController），在组件卸载时可能导致内存泄漏。

---

## 四、安全审计

### 4.1 认证安全

| 检查项 | 状态 | 说明 |
|--------|------|------|
| Token 存储 | 警告 | 使用 localStorage，存在 XSS 风险 |
| Token 传输 | 通过 | 使用 Authorization Header |
| Token 刷新 | 缺失 | 无自动刷新机制 |
| 登出处理 | 通过 | 清除 Token 并跳转 |

### 4.2 输入验证

| 检查项 | 状态 | 说明 |
|--------|------|------|
| 请求参数校验 | 缺失 | 无运行时类型校验 |
| SQL 注入防护 | N/A | 前端不直接操作数据库 |
| XSS 防护 | 通过 | 使用 Vue 模板，自动转义 |

### 4.3 错误处理

| 检查项 | 状态 | 说明 |
|--------|------|------|
| 错误信息泄露 | 警告 | 直接显示后端错误消息 |
| 堆栈信息 | 通过 | 不暴露堆栈 |
| 统一处理 | 通过 | 使用拦截器统一处理 |

---

## 五、修复优先级建议

### 立即修复 (本周)
1. **P0-1**: request.ts 401 处理导致请求中断
2. **P0-2**: Token 过期并发请求处理

### 短期修复 (本月)
3. **P1-1**: Store 模块划分优化
4. **P1-2**: 重复状态抽象
5. **P1-3**: API 错误处理一致性

### 中期优化 (下月)
6. **P0-3**: 运行时类型校验引入
7. **P4-1~5**: 代码质量改进

---

## 六、附录

### 文件清单

| 文件路径 | 行数 | 问题数 |
|----------|------|--------|
| frontend/src/utils/request.ts | 67 | 3 |
| frontend/src/api/article.ts | 46 | 1 |
| frontend/src/api/category.ts | 44 | 1 |
| frontend/src/api/dailyLog.ts | 24 | 1 |
| frontend/src/api/project.ts | 23 | 0 |
| frontend/src/api/skill.ts | 23 | 0 |
| frontend/src/api/auth.ts | 15 | 0 |
| frontend/src/api/config.ts | 23 | 0 |
| frontend/src/api/file.ts | 14 | 1 |
| frontend/src/api/home.ts | 7 | 0 |
| frontend/src/stores/modules/user.ts | 66 | 1 |
| frontend/src/stores/modules/app.ts | 23 | 0 |
| frontend/src/stores/modules/config.ts | 52 | 0 |
| frontend/src/stores/modules/article.ts | 116 | 2 |
| frontend/src/stores/modules/dailyLog.ts | 131 | 2 |

---

**报告生成时间**: 2026-04-05  
**审计版本**: commit HEAD
