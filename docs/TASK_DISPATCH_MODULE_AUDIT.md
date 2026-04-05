# 模块排查任务分派文档

> **项目**: Nanmuli Blog  
> **日期**: 2026-04-05  
> **任务类型**: 代码审查与问题排查  
> **执行方式**: 并行分派给多个AI代理

---

## 📌 任务总览

### 排查目标
对博客系统各模块进行全面代码审查，识别以下类型问题：

| 优先级 | 问题类型 | 说明 |
|--------|----------|------|
| P0 | 功能缺陷 | 可能导致功能异常的代码问题 |
| P1 | 架构违规 | 违反DDD分层架构规范的调用 |
| P2 | 性能隐患 | N+1查询、全表扫描、缓存缺失等 |
| P3 | 安全隐患 | 输入校验缺失、越权访问、SQL注入风险 |
| P4 | 代码质量 | 重复代码、命名不一致、缺失边界处理 |

### 模块清单

```
后端模块 (backend/src/main/java/com/nanmuli/blog/)
├── domain/           # 领域层 - 实体、值对象、仓储接口
├── application/      # 应用层 - AppService、DTO、Command
├── interfaces/       # 接口层 - Controller、异常处理器
├── infrastructure/   # 基础设施层 - Mapper、RepositoryImpl
└── shared/           # 共享内核

前端模块 (frontend/src/)
├── api/              # API请求封装
├── stores/           # Pinia状态管理
├── views/            # 页面视图
├── components/       # 组件
├── router/           # 路由配置
└── utils/            # 工具函数
```

---

## 🎯 任务1: 后端-文章模块排查

### 执行AI
`Agent-Backend-Article`

### 负责范围
```
backend/src/main/java/com/nanmuli/blog/
├── domain/article/
│   ├── Article.java
│   ├── ArticleId.java
│   ├── ArticleStatus.java
│   ├── ArticleRepository.java
│   └── ArticleTag.java
├── application/article/
│   ├── ArticleAppService.java
│   ├── command/CreateArticleCommand.java
│   ├── command/UpdateArticleCommand.java
│   ├── dto/ArticleDTO.java
│   ├── dto/ArticleArchiveDTO.java
│   └── query/ArticlePageQuery.java
├── infrastructure/persistence/article/
│   ├── ArticleMapper.java
│   ├── ArticleTagMapper.java
│   ├── ArticleRepositoryImpl.java
│   └── ArticleTagRepositoryImpl.java
└── interfaces/rest/ArticleController.java
```

### 检查清单

#### 功能缺陷 (P0)
- [ ] `ArticleAppService.toDTO()` 中标签设置为单元素列表 `Collections.singletonList(category.getName())`，与Tag系统设计不符
- [ ] `ArticleAppService.getArchive()` 中使用原始Map转换，字段类型转换是否安全
- [ ] `incrementViewCount` 为异步方法但无独立事务控制，可能存在事务传播问题

#### 架构违规 (P1)
- [ ] `ArticleAppService` 同时依赖 `CategoryRepository` 和 `CategoryAppService`，存在跨服务直接调用
- [ ] `buildCategoryPath()` 循环查询上级分类，存在N+1问题
- [ ] 检查Controller是否直接返回实体而非DTO

#### 性能隐患 (P2)
- [ ] `findTopArticles` 使用 `.last("LIMIT " + limit)` 硬编码SQL
- [ ] 缓存注解 `@Cacheable(key = "#slug")` 在slug变更时如何处理缓存失效
- [ ] 分类路径查询未缓存，每次都需要递归查询

#### 安全隐患 (P3)
- [ ] `generateSlug()` 生成slug时是否处理了SQL注入特殊字符
- [ ] Markdown内容XSS过滤检查

#### 代码质量 (P4)
- [ ] `ensureUniqueSlug()` 数字后缀算法在并发场景下的唯一性保证
- [ ] BeanUtils.copyProperties字段映射是否完整

### 输出要求
1. 问题列表（按优先级排序）
2. 每个问题标注：文件路径、行号、问题描述、修复建议
3. 关键代码截图

---

## 🎯 任务2: 后端-分类标签模块排查

### 执行AI
`Agent-Backend-Category`

### 负责范围
```
backend/src/main/java/com/nanmuli/blog/
├── domain/category/
│   ├── Category.java
│   └── CategoryRepository.java
├── domain/tag/
│   ├── Tag.java
│   └── TagRepository.java
├── application/category/
│   ├── CategoryAppService.java
│   ├── command/
│   ├── dto/CategoryDTO.java
│   └── query/
├── application/tag/
│   ├── TagAppService.java
│   └── dto/TagDTO.java
├── infrastructure/persistence/category/
│   ├── CategoryMapper.java
│   └── CategoryRepositoryImpl.java
├── infrastructure/persistence/tag/
│   ├── TagMapper.java
│   └── TagRepositoryImpl.java
└── interfaces/rest/CategoryController.java, TagController.java
```

### 检查清单

#### 功能缺陷 (P0)
- [ ] 树形分类删除时，子分类处理逻辑（级联删除/禁止删除/上移）
- [ ] 分类变更parentId时，is_leaf字段是否正确更新
- [ ] 叶子分类关联文章后，被改为父分类的数据一致性

#### 架构违规 (P1)
- [ ] 检查是否存在跨聚合直接操作实体
- [ ] CategoryAppService和TagAppService之间是否有循环依赖

#### 性能隐患 (P2)
- [ ] 树形分类查询是否使用递归，是否有堆栈溢出风险
- [ ] 分类树缓存策略

#### 安全隐患 (P3)
- [ ] 分类slug唯一性校验

### 输出要求
同上

---

## 🎯 任务3: 后端-技术日志模块排查

### 执行AI
`Agent-Backend-DailyLog`

### 负责范围
```
backend/src/main/java/com/nanmuli/blog/
├── domain/dailylog/
├── application/dailylog/
├── infrastructure/persistence/dailylog/
└── interfaces/rest/DailyLogController.java
```

### 检查清单

#### 功能缺陷 (P0)
- [ ] 按日期(log_date)查询时，时区处理是否正确
- [ ] content_html生成是否使用MarkdownUtil统一处理

#### 性能隐患 (P2)
- [ ] 时间线展示接口是否分页，大数据量时性能

### 输出要求
同上

---

## 🎯 任务4: 后端-基础设施层排查

### 执行AI
`Agent-Backend-Infrastructure`

### 负责范围
```
backend/src/main/java/com/nanmuli/blog/
├── infrastructure/
│   ├── config/
│   │   ├── db/MyBatisPlusConfig.java
│   │   ├── cache/CacheConfig.java
│   │   ├── cache/RedisConfig.java
│   │   ├── security/SaTokenConfig.java
│   │   └── web/Knife4jConfig.java
│   └── persistence/
│       ├── **/Mapper.java
│       └── **/RepositoryImpl.java
├── shared/
│   ├── exception/
│   ├── result/
│   └── util/
└── resources/
    ├── application.yml
    ├── application-dev.yml
    ├── application-prod.yml
    └── data.sql
```

### 检查清单

#### 配置问题 (P0)
- [ ] `application.yml` 中Sa-Token Redis配置与Spring Redis配置分离，端口不一致问题
- [ ] 开发/生产环境配置是否完整
- [ ] MyBatis Plus逻辑删除字段配置与实体字段是否一致

#### 异常处理 (P1)
- [ ] `GlobalExceptionHandler` 是否覆盖所有异常类型
- [ ] 业务异常与系统异常区分是否清晰

#### 工具类 (P2)
- [ ] `MarkdownUtil` 是否为单例，线程安全性
- [ ] Flexmark版本兼容性（已知历史问题）

#### 数据库 (P3)
- [ ] schema.sql与实体字段映射一致性
- [ ] 索引是否覆盖常用查询

### 输出要求
同上

---

## 🎯 任务5: 前端-API与状态管理层排查

### 执行AI
`Agent-Frontend-API`

### 负责范围
```
frontend/src/
├── api/
│   ├── index.ts
│   ├── article.ts
│   ├── category.ts
│   ├── tag.ts
│   ├── dailyLog.ts
│   ├── project.ts
│   ├── skill.ts
│   ├── auth.ts
│   ├── config.ts
│   ├── file.ts
│   └── home.ts
├── stores/
│   ├── index.ts
│   └── modules/
│       ├── user.ts
│       ├── app.ts
│       ├── config.ts
│       ├── article.ts
│       └── dailyLog.ts
└── utils/
    └── request.ts
```

### 检查清单

#### 功能缺陷 (P0)
- [ ] `request.ts` 401处理直接跳转导致未完成的请求被中断
- [ ] Token过期后并发请求的处理
- [ ] API返回类型定义与实际响应是否一致

#### 架构问题 (P1)
- [ ] Store模块划分是否合理，是否存在重复状态
- [ ] API层是否统一封装，错误处理是否一致

#### 代码质量 (P4)
- [ ] TypeScript类型定义完整性
- [ ] 请求参数拼写一致性

### 输出要求
同上

---

## 🎯 任务6: 前端-视图组件层排查

### 执行AI
`Agent-Frontend-Views`

### 负责范围
```
frontend/src/
├── views/
│   ├── home/
│   ├── article/
│   ├── dailyLog/
│   ├── tag/
│   ├── project/
│   ├── about/
│   ├── auth/
│   ├── error/
│   └── admin/**
├── components/
│   ├── article/
│   ├── dailyLog/
│   ├── project/
│   ├── skill/
│   ├── common/
│   └── editor/
├── router/
│   ├── index.ts
│   ├── routes.ts
│   └── guards.ts
└── layouts/
    ├── DefaultLayout.vue
    ├── AdminLayout.vue
    └── BlankLayout.vue
```

### 检查清单

#### 功能缺陷 (P0)
- [ ] 路由守卫权限校验逻辑
- [ ] 管理后台是否所有路由都有`requiresAuth`标记
- [ ] 页面离开确认（未保存内容提示）

#### 性能问题 (P2)
- [ ] 组件懒加载配置
- [ ] 图片懒加载
- [ ] 列表虚拟滚动（大数据量时）

#### UI/UX (P4)
- [ ] 加载状态处理
- [ ] 错误页面友好性
- [ ] 移动端适配

### 输出要求
同上

---

## 🎯 任务7: 安全与性能专项排查

### 执行AI
`Agent-Security-Performance`

### 负责范围
全栈安全与性能审计

### 检查清单

#### 安全审计
- [ ] **认证**: Sa-Token配置是否安全，Token存储方式
- [ ] **授权**: 接口权限控制是否完整，`@SaCheckLogin`使用
- [ ] **输入校验**: 所有入参是否使用`@Valid`校验
- [ ] **XSS防护**: Markdown渲染后的HTML是否过滤危险标签
- [ ] **文件上传**: 类型白名单、大小限制、路径安全
- [ ] **SQL注入**: MyBatis参数绑定使用情况

#### 性能审计
- [ ] **数据库**: 慢查询、索引覆盖、N+1问题
- [ ] **缓存**: Redis缓存策略、缓存穿透/击穿防护
- [ ] **并发**: 热点数据并发控制（如浏览量计数）
- [ ] **前端**: 打包体积、资源懒加载、CDN配置

### 输出要求
1. 安全风险等级评估（Critical/High/Medium/Low）
2. 性能瓶颈分析
3. 优化建议清单

---

## 📊 任务汇总

| 任务 | 执行AI | 优先级 | 预估耗时 | 依赖 |
|------|--------|--------|----------|------|
| 后端-文章模块 | Agent-Backend-Article | P0 | 30min | 无 |
| 后端-分类标签 | Agent-Backend-Category | P0 | 25min | 无 |
| 后端-技术日志 | Agent-Backend-DailyLog | P1 | 15min | 无 |
| 后端-基础设施 | Agent-Backend-Infrastructure | P0 | 30min | 无 |
| 前端-API与Store | Agent-Frontend-API | P0 | 20min | 无 |
| 前端-视图组件 | Agent-Frontend-Views | P1 | 30min | 无 |
| 安全与性能 | Agent-Security-Performance | P0 | 25min | 无 |

**总计**: 约7个并行任务，预计30分钟内完成全部排查

---

## 📁 输出规范

每个AI代理完成后，在以下路径输出报告：

```
docs/audit-reports/
├── backend-article-audit.md
├── backend-category-audit.md
├── backend-dailylog-audit.md
├── backend-infrastructure-audit.md
├── frontend-api-audit.md
├── frontend-views-audit.md
└── security-performance-audit.md
```

### 报告模板

```markdown
# [模块名] 排查报告

## 执行AI: [Agent名称]
## 执行时间: [时间戳]

## 统计摘要
- 发现问题总数: X
- P0(严重): X
- P1(高): X
- P2(中): X
- P3/P4(低): X

## 详细问题列表

### P0: [问题标题]
- **文件**: [路径]:[行号]
- **问题**: [详细描述]
- **影响**: [功能/安全/性能影响]
- **修复建议**: [具体代码或方案]
- **代码截图**:
  ```java
  // 问题代码
  ```

## 正向发现（代码亮点）
- [亮点描述]

## 整体评估
[对该模块代码质量的整体评价]
```

---

## ⚡ 执行指令

所有AI代理并行执行，完成后由主AI（我）汇总所有报告，形成最终的项目健康度评估和修复计划。

**启动时间**: 2026-04-05  
**预计完成**: 30分钟内  
**报告汇总**: 主AI负责
