# 第八轮项目检查计划

> 深度检查45个修改文件 | 2026-04-06

## 一、检查目标

对全部45个修改文件进行模块化的深度检查，确保：
1. 代码逻辑正确性
2. 前后端一致性
3. 无引入新问题
4. 符合项目规范

## 二、文件分类与分派

### 模块A：后端安全配置模块 (5文件)
**代理**: `check-backend-security`

| 文件 | 检查重点 |
|------|----------|
| `backend/pom.xml` | jsoup版本升级至1.19.1，检查依赖冲突 |
| `backend/.../shared/util/MarkdownUtil.java` | Safelist配置严格性，XSS防护完整性 |
| `backend/.../handler/GlobalExceptionHandler.java` | 异常处理逻辑，敏感信息脱敏 |
| `backend/.../file/FileAppService.java` | 文件大小限制、类型白名单、UUID重命名 |
| `backend/.../application.yml` | 安全配置参数，日志脱敏配置 |

---

### 模块B：后端文章模块 (5文件)
**代理**: `check-backend-article`

| 文件 | 检查重点 |
|------|----------|
| `backend/.../article/ArticleAppService.java` | 阅读量更新逻辑、缓存策略、事务边界 |
| `backend/.../article/query/ArticlePageQuery.java` | 分页参数校验、排序字段合法性 |
| `backend/.../domain/article/Article.java` | 实体字段、乐观锁@Version配置 |
| `backend/.../article/ArticleRepositoryImpl.java` | SQL注入防护、分页查询正确性 |
| `backend/.../db/migration/V1_3__add_version_to_article.sql` | 迁移脚本正确性 |

---

### 模块C：后端分类与缓存模块 (4文件)
**代理**: `check-backend-category`

| 文件 | 检查重点 |
|------|----------|
| `backend/.../category/CategoryAppService.java` | 分类删除约束、叶子分类校验 |
| `backend/.../category/CategoryRepository.java` | 接口方法定义完整性 |
| `backend/.../category/CategoryRepositoryImpl.java` | LIKE查询转义、树查询正确性 |
| `backend/.../config/cache/CacheConfig.java` | 缓存配置、TTL设置、序列化配置 |

---

### 模块D：前端核心工具模块 (6文件)
**代理**: `check-frontend-core`

| 文件 | 检查重点 |
|------|----------|
| `frontend/src/utils/request.ts` | 请求取消机制、重试逻辑、错误处理 |
| `frontend/src/stores/modules/user.ts` | Pinia状态持久化、登录状态管理 |
| `frontend/src/composables/useAuth.ts` | 权限检查逻辑、路由守卫集成 |
| `frontend/src/utils/format.ts` | 格式化函数正确性 |
| `frontend/src/styles/themes.ts` | 主题切换逻辑、系统偏好检测 |
| `frontend/index.html` | 主题防闪烁脚本、CSS变量定义 |

---

### 模块E：前端UI组件模块 (5文件)
**代理**: `check-frontend-ui`

| 文件 | 检查重点 |
|------|----------|
| `frontend/src/components/common/AppHeader.vue` | 导航状态、主题切换按钮 |
| `frontend/src/components/common/AppSidebar.vue` | 菜单状态、移动端适配 |
| `frontend/src/components/skill/SkillCloud.vue` | 技能云渲染、动画效果 |
| `frontend/src/components/skill/SkillItem.vue` | 单个技能展示、交互 |
| `frontend/src/styles/index.scss` | 全局样式、主题变量使用 |

---

### 模块F：前端文章页面模块 (4文件)
**代理**: `check-frontend-article`

| 文件 | 检查重点 |
|------|----------|
| `frontend/src/views/article/List.vue` | 防抖机制、请求取消、URL同步 |
| `frontend/src/views/article/Detail.vue` | UV统计、TOC导航、代码高亮 |
| `frontend/src/views/home/Index.vue` | 首页文章列表、分类导航防抖 |
| `frontend/src/components.d.ts` | 组件类型声明 |

---

### 模块G：前端管理后台模块 (6文件)
**代理**: `check-frontend-admin`

| 文件 | 检查重点 |
|------|----------|
| `frontend/src/views/admin/article/Create.vue` | 表单验证、maxlength限制、Markdown编辑器 |
| `frontend/src/views/admin/article/Edit.vue` | 数据加载、保存逻辑、缓存刷新 |
| `frontend/src/views/admin/article/List.vue` | 列表展示、分页、操作按钮 |
| `frontend/src/views/admin/Dashboard.vue` | 统计数据展示、图表 |
| `frontend/src/views/admin/project/Index.vue` | 项目管理CRUD |
| `frontend/src/views/admin/category/Index.vue` | 分类树管理 |

---

### 模块H：前端其他页面与配置 (6文件)
**代理**: `check-frontend-other`

| 文件 | 检查重点 |
|------|----------|
| `frontend/src/views/auth/Login.vue` | 登录表单、验证、错误处理 |
| `frontend/src/views/about/Index.vue` | 关于页面内容、响应式 |
| `frontend/src/views/project/Index.vue` | 项目展示、筛选 |
| `frontend/src/views/dailyLog/List.vue` | 日志时间线 |
| `frontend/src/views/dailyLog/Detail.vue` | 日志详情 |
| `frontend/tailwind.config.js` | 主题扩展配置 |

---

### 模块I：文档与数据库模块 (4文件)
**代理**: `check-docs-db`

| 文件 | 检查重点 |
|------|----------|
| `docs/project-plan.md` | 文档完整性、与实际代码一致性 |
| `docs/compatibility-test-report.md` | 兼容性报告准确性 |
| `backend/src/main/resources/db/init.sql` | 初始化脚本完整性 |
| `backend/src/main/resources/application-prod.yml` | 生产环境配置 |

---

## 三、检查标准

### 代码质量检查清单
- [ ] 无语法错误
- [ ] 无类型错误（TypeScript）
- [ ] 无未使用变量/导入
- [ ] 错误处理完善
- [ ] 边界条件处理

### 安全合规检查清单
- [ ] XSS防护到位
- [ ] SQL注入防护
- [ ] 文件上传安全
- [ ] 敏感信息脱敏

### 一致性检查清单
- [ ] 前后端接口一致
- [ ] 命名规范一致
- [ ] 错误码一致
- [ ] 缓存策略一致

## 四、报告格式

```markdown
## 模块X检查报告

### 检查文件清单
- [x] file1 - 状态
- [ ] file2 - 问题描述

### 发现问题
| 序号 | 文件 | 问题 | 严重程度 | 修复建议 |

### 修复内容（如有）
```

## 五、执行顺序

1. 并行启动模块A-I的检查代理
2. 汇总问题清单
3. 统一修复
4. 最终回归验证
