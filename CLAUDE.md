# Nanmuli Blog - 项目开发规范

> 个人技术博客系统 - 开发规范文档
> 基于 Spring Boot 3.3 + Java 21 + DDD 架构

---

## 一、项目概述

### 1.1 项目定位
个人技术博客系统，记录技术学习、分享技术文章，展示个人技能与项目经历。

### 1.2 用户角色
- **管理员（仅1人）**：内容管理、系统配置
- **访客**：只读访问，浏览文章、项目、技能展示

### 1.3 核心模块
| 模块 | 功能 |
|------|------|
| 文章管理 | Markdown编辑、发布、分类、自动生成摘要/HTML、置顶 |
| 技术日志 | 快速记录每日技术学习、时间线展示 |
| 个人展示 | 技能云展示、项目展示 |
| 分类管理 | 树形分类结构，仅叶子分类可关联文章 |
| 系统配置 | 动态配置项管理 |
| AI辅助 | 智能标签、文章摘要（预留，当前禁用） |

---

## 二、技术栈

### 2.1 后端
| 层级 | 技术 | 版本 |
|------|------|------|
| 框架 | Spring Boot | 3.3.5 |
| JDK | Java | 21 LTS |
| ORM | MyBatis Plus | 3.5.9 |
| 数据库 | PostgreSQL | 15+ |
| 缓存 | Redis | 7+ |
| 认证 | Sa-Token | 1.44.0 |
| API文档 | Knife4j | 4.4.0 |
| 工具库 | Hutool | 5.8.36 |
| Markdown | Flexmark | 0.64.8 |
| 向量扩展 | pgvector | 0.1.4 |

### 2.2 前端
| 技术 | 版本 |
|------|------|
| 框架 | Vue 3 | 3.4.15 |
| 构建工具 | Vite | 5.0.11 |
| UI组件库 | Element Plus | 2.5.1 |
| 状态管理 | Pinia | 2.1.7 |
| 路由 | Vue Router | 4.2.5 |
| CSS框架 | Tailwind CSS | 3.4.1 |
| Markdown编辑器 | md-editor-v3 | 4.11.0 |
| 代码高亮 | highlight.js | 11.9.0 |

---

## 三、架构设计（DDD分层）

### 3.1 分层架构

```
┌─────────────────────────────────────────────────────────────────┐
│                      Interfaces 接口层                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ Controller  │  │  Exception  │  │      DTO/Command        │  │
│  │   REST API  │  │   Handler   │  │     (入参/出参)          │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│                    Application 应用层                           │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              AppService (应用服务)                       │   │
│  │     - 编排领域对象完成用例                                │   │
│  │     - 事务控制                                           │   │
│  │     - 跨聚合协调                                         │   │
│  │     - 发布领域事件                                       │   │
│  └─────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────┤
│                     Domain 领域层                               │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐                │
│  │  Entity    │  │ ValueObject│  │ Repository │                │
│  │  (聚合根)   │  │   (值对象)  │  │  (接口)     │                │
│  ├────────────┤  ├────────────┤  ├────────────┤                │
│  │ DomainEvent│  │  Enum      │  │ DomainSvc  │                │
│  └────────────┘  └────────────┘  └────────────┘                │
├─────────────────────────────────────────────────────────────────┤
│                  Infrastructure 基础设施层                       │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐                │
│  │  Mapper    │  │RepositoryImpl│  │   Config   │                │
│  │ (数据访问)  │  │  (仓储实现)  │  │   (配置类)  │                │
│  └────────────┘  └────────────┘  └────────────┘                │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 包结构规范

```
com.nanmuli.blog
├── domain                          # 领域层 - 核心业务逻辑
│   ├── article                     # 文章聚合
│   │   ├── Article.java            # 聚合根实体
│   │   ├── ArticleId.java          # 值对象（ID包装）
│   │   ├── ArticleStatus.java      # 枚举（1=发布, 2=草稿, 3=回收）
│   │   ├── ArticleRepository.java  # 仓储接口
│   │   └── event/                  # 领域事件
│   │       ├── ArticleCreatedEvent.java
│   │       └── ArticlePublishedEvent.java
│   ├── category                    # 分类聚合
│   ├── tag                         # 标签聚合
│   ├── dailylog                    # 技术日志聚合
│   ├── skill                       # 技能展示聚合
│   ├── project                     # 项目展示聚合
│   ├── friendlink                  # 友链聚合
│   ├── config                      # 系统配置聚合
│   ├── file                        # 文件聚合
│   ├── user                        # 用户聚合
│   └── ai                          # AI生成聚合
│
├── application                     # 应用层 - 用例编排
│   ├── article
│   │   ├── ArticleAppService.java           # 应用服务
│   │   ├── command/CreateArticleCommand.java # 命令对象（写）
│   │   ├── dto/ArticleDTO.java               # 数据传输对象（读）
│   │   └── query/ArticlePageQuery.java       # 查询对象
│   └── ...
│
├── interfaces                      # 接口层 - 外部交互
│   ├── rest                        # REST控制器
│   ├── handler                     # 异常处理器
│   └── filter                      # 过滤器
│
├── infrastructure                  # 基础设施层
│   ├── config                      # 配置类
│   │   ├── db/MyBatisPlusConfig.java
│   │   ├── cache/CacheConfig.java
│   │   ├── cache/RedisConfig.java
│   │   ├── security/SaTokenConfig.java
│   │   └── web/Knife4jConfig.java
│   └── persistence                 # 持久化实现
│       └── article
│           ├── ArticleMapper.java
│           └── ArticleRepositoryImpl.java
│
└── shared                          # 共享内核
    ├── domain                      # 共享领域基类
    │   └── BaseAggregateRoot.java
    ├── result                      # 统一响应
    │   ├── Result.java
    │   └── PageResult.java
    ├── exception                   # 异常定义
    │   └── BusinessException.java
    └── util                        # 工具类
        └── MarkdownUtil.java
```

### 3.3 分层调用规则

| 规则 | 说明 |
|------|------|
| ✅ 允许 | `Controller` → `AppService` → `Repository` |
| ✅ 允许 | `AppService` 调用多个聚合的 `Repository` |
| ✅ 允许 | `RepositoryImpl` 实现 `Repository` 接口 |
| ❌ 禁止 | `Controller` 直接调用 `Repository` |
| ❌ 禁止 | `AppService` 之间互相调用 |
| ❌ 禁止 | 领域层依赖应用层/接口层 |
| ❌ 禁止 | 跨聚合直接操作实体（必须通过聚合根） |

---

## 四、编码规范

### 4.1 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 包名 | 全小写，点分隔 | `com.nanmuli.blog.domain.article` |
| 类名 | 大驼峰，名词 | `ArticleService`, `CreateArticleCommand` |
| 接口名 | 大驼峰，形容词/名词 | `ArticleRepository`, `Identifiable` |
| 方法名 | 小驼峰，动词开头 | `create()`, `findById()`, `publish()` |
| 常量 | 全大写，下划线分隔 | `MAX_TITLE_LENGTH`, `STATUS_PUBLISHED` |
| 变量 | 小驼峰 | `articleId`, `createTime` |
| 布尔 | is/has/can 开头 | `isPublished`, `hasTags` |

### 4.2 实体基类（BaseAggregateRoot）

```java
@Getter
public abstract class BaseAggregateRoot<ID extends Serializable> implements Serializable {
    @TableId(type = IdType.ASSIGN_ID)
    protected ID id;

    @TableField(fill = FieldFill.INSERT)
    protected LocalDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    protected LocalDateTime updatedAt;

    @TableLogic
    @TableField(fill = FieldFill.INSERT)
    protected Boolean isDeleted;

    public boolean isNew() {
        return id == null;
    }
}
```

### 4.3 文章实体（Article）

```java
@Getter
@Setter
@EqualsAndHashCode(callSuper = false)
public class Article extends BaseAggregateRoot<Long> {
    private String title;           // 标题
    private String slug;            // 别名（URL友好）
    private String content;         // Markdown内容
    private String contentHtml;     // 渲染后的HTML
    private String summary;         // 摘要
    private String cover;           // 封面图URL
    private Long categoryId;        // 分类ID
    private Long userId;            // 作者ID
    private Integer viewCount;      // 浏览量
    private Integer likeCount;      // 点赞数
    private Integer wordCount;      // 字数
    private Integer readingTime;    // 阅读时间（分钟）
    private Integer status;         // 状态（1=发布, 2=草稿, 3=回收）
    private Boolean isTop;          // 是否置顶
    private Boolean isOriginal;     // 是否原创
    private String originalUrl;     // 原文链接（非原创时）
    private LocalDateTime publishTime; // 发布时间

    // 领域方法
    public void publish() { this.status = 1; this.publishTime = LocalDateTime.now(); }
    public void draft() { this.status = 2; }
    public void recycle() { this.status = 3; }
    public boolean isPublished() { return status != null && status == 1; }

    public void calculateWordCount() {
        if (this.content != null) {
            this.wordCount = this.content.replaceAll("\\s+", "").length();
            this.readingTime = Math.max(1, this.wordCount / 300);
        }
    }
}
```

### 4.4 应用服务（Application）

```java
@Slf4j
@Service
@RequiredArgsConstructor
@CacheConfig(cacheNames = "article")
@Transactional(readOnly = true)
public class ArticleAppService {

    private final ArticleRepository articleRepository;
    private final CategoryRepository categoryRepository;
    private final ApplicationEventPublisher eventPublisher;
    private final MarkdownUtil markdownUtil;

    @Transactional
    @CacheEvict(cacheNames = "article:list", allEntries = true)
    public Long create(CreateArticleCommand command) {
        // 1. 验证（slug唯一性、叶子分类）
        // 2. 创建领域对象
        // 3. 生成HTML、摘要
        // 4. 持久化
        // 5. 发布事件
        // 6. 返回ID
    }

    @Cacheable(key = "#slug")
    public ArticleDTO getBySlug(String slug) { }
}
```

**要求：**
- 必须标注 `@Service` 和 `@Transactional`
- 使用构造器注入（`@RequiredArgsConstructor`）
- 一个方法对应一个用例
- 查询方法使用 `@Cacheable`，写操作使用 `@CacheEvict`
- 禁止在应用服务中写业务规则（应下沉到领域层）

### 4.5 控制器（Interface）

```java
@Tag(name = "文章管理")
@RestController
@RequestMapping("/api")
@RequiredArgsConstructor
public class ArticleController {

    private final ArticleAppService articleAppService;

    // 公开接口
    @GetMapping("/article/list")
    public Result<PageResult<ArticleDTO>> list(ArticlePageQuery query) { }

    @GetMapping("/article/{slug}")
    public Result<ArticleDTO> detail(@PathVariable String slug) { }

    // 管理接口（需登录）
    @PostMapping("/admin/article")
    public Result<Long> create(@Valid @RequestBody CreateArticleCommand command) { }

    @PutMapping("/admin/article/{id}")
    public Result<Void> update(@PathVariable Long id, @Valid @RequestBody UpdateArticleCommand command) { }

    @DeleteMapping("/admin/article/{id}")
    public Result<Void> delete(@PathVariable Long id) { }
}
```

**要求：**
- 路径前缀：公开接口 `/api/**`，管理接口 `/api/admin/**`
- 入参校验：`@Valid` 激活 Bean Validation
- 统一返回：`Result<T>` 包装
- 禁止在 Controller 中写业务逻辑

### 4.6 数据传输对象

```java
// Command：写操作入参
@Data
public class CreateArticleCommand {
    @NotBlank(message = "标题不能为空")
    @Size(max = 200, message = "标题长度不能超过200字符")
    private String title;

    @NotBlank(message = "内容不能为空")
    private String content;

    private String slug;            // 可选，自动生成
    private String summary;         // 可选，自动提取
    private String cover;
    private Long categoryId;
    private Integer status;         // 1=发布, 2=草稿
    private Boolean isTop;
    private Boolean isOriginal;
    private String originalUrl;
}

// DTO：读操作出参
@Data
public class ArticleDTO {
    private Long id;
    private String title;
    private String slug;
    private String content;
    private String contentHtml;
    private String summary;
    private String cover;
    private Integer viewCount;
    private Integer wordCount;
    private Integer readingTime;
    private Boolean isTop;
    private LocalDateTime publishTime;
    private LocalDateTime createTime;
    private CategoryDTO category;
    private List<CategoryDTO> categoryPath;  // 分类路径
}

// Query：分页查询参数
@Data
public class ArticlePageQuery {
    private Long current = 1L;
    private Long size = 10L;
    private Long categoryId;
    private String keyword;
    private String sort;  // "newest" | "oldest" | "popular"
}
```

---

## 五、数据访问规范

### 5.1 Repository 模式

```java
// 领域层定义接口
public interface ArticleRepository {
    Article save(Article article);
    Optional<Article> findById(ArticleId id);
    Optional<Article> findBySlug(String slug);
    boolean existsBySlug(String slug);
    boolean existsBySlugAndIdNot(String slug, Long id);
    IPage<Article> findPublishedPage(IPage<Article> page, String sort);
    IPage<Article> findByCategoryId(Long categoryId, IPage<Article> page);
    List<Article> findTopArticles(int limit);
    void deleteById(ArticleId id);
    void increaseViewCount(ArticleId id);
    Long countPublished();
    List<Map<String, Object>> findArchiveByYearMonth();
}

// 基础设施层实现
@Repository
@RequiredArgsConstructor
public class ArticleRepositoryImpl implements ArticleRepository {
    private final ArticleMapper articleMapper;

    @Override
    public Article save(Article article) {
        if (article.isNew()) {
            articleMapper.insert(article);
        } else {
            articleMapper.updateById(article);
        }
        return article;
    }
}
```

### 5.2 MyBatis Plus 使用规范

**全局配置（application.yml）：**

```yaml
mybatis-plus:
  configuration:
    log-impl: org.apache.ibatis.logging.slf4j.Slf4jImpl
    map-underscore-to-camel-case: true
  global-config:
    db-config:
      logic-delete-field: isDeleted      # 逻辑删除字段
      logic-delete-value: true           # 删除标记值
      logic-not-delete-value: false      # 未删除标记值
      id-type: assign_id                 # 雪花算法ID
```

**Mapper接口：**

```java
@Mapper
public interface ArticleMapper extends BaseMapper<Article> {

    @Update("UPDATE article SET view_count = view_count + 1 WHERE id = #{id}")
    void increaseViewCount(Long id);

    // 复杂查询使用XML或@Select
    @Select("""
        SELECT DATE_PART('year', publish_time) as year,
               DATE_PART('month', publish_time) as month,
               COUNT(*) as count
        FROM article
        WHERE status = 1 AND is_deleted = false
        GROUP BY DATE_PART('year', publish_time), DATE_PART('month', publish_time)
        ORDER BY year DESC, month DESC
        """)
    List<Map<String, Object>> selectArchiveByYearMonth();

    IPage<Article> selectByTagId(IPage<Article> page, @Param("tagId") Long tagId);
}
```

**查询优化清单：**
- ✅ 分页查询必须加索引条件过滤
- ✅ 关联查询用 JOIN，禁止循环查询
- ✅ 使用 LambdaQueryWrapper 保证类型安全
- ❌ 禁止在循环中执行SQL（N+1问题）
- ❌ 禁止无条件的全表 UPDATE/DELETE

---

## 六、安全规范

### 6.1 认证授权

```yaml
# Sa-Token 配置
sa-token:
  token-name: Authorization
  timeout: 2592000          # Token有效期30天
  active-timeout: -1
  is-concurrent: true
  is-share: false
  token-style: uuid
```

- 管理接口统一使用 Sa-Token 拦截：`/api/admin/**`
- 未登录访问管理接口返回 401
- 权限不足返回 403

### 6.2 输入安全

| 威胁 | 防护措施 |
|------|----------|
| SQL注入 | MyBatis参数绑定（#{}），禁止字符串拼接 |
| XSS攻击 | Markdown内容服务端渲染为HTML，前端使用v-html需谨慎 |
| 文件上传 | 限制类型（白名单），限制大小（10MB），重命名存储 |
| 路径遍历 | 文件名MD5重命名，禁止保留原始路径 |

### 6.3 异常处理

```java
@Slf4j
@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(BusinessException.class)
    public Result<Void> handleBusinessException(BusinessException e) {
        return Result.error(e.getCode(), e.getMessage());
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public Result<Void> handleValidationException(MethodArgumentNotValidException e) {
        String message = e.getBindingResult().getFieldErrors().stream()
                .findFirst()
                .map(error -> error.getDefaultMessage())
                .orElse("请求参数错误");
        return Result.error(400, message);
    }

    @ExceptionHandler(NotLoginException.class)
    public Result<Void> handleNotLoginException(NotLoginException e) {
        return Result.error(401, "请先登录");
    }

    @ExceptionHandler(Exception.class)
    public Result<Void> handleException(Exception e, HttpServletRequest request) {
        String traceId = MDC.get("traceId");
        log.error("[traceId={}] 系统异常, uri={}", traceId, request.getRequestURI(), e);
        return Result.error(500, "系统繁忙，请稍后再试");
    }
}
```

**HTTP状态码规范：**

| 场景 | 状态码 | 说明 |
|------|--------|------|
| 成功 | 200 | 标准成功 |
| 参数错误 | 400 | 客户端输入验证失败 |
| 未认证 | 401 | 需要登录（Sa-Token拦截） |
| 无权限 | 403 | 权限不足 |
| 资源不存在 | 404 | URL错误或资源已删除 |
| 业务错误 | 422 | 业务规则校验失败 |
| 系统错误 | 500 | 服务器内部错误 |

---

## 七、性能规范

### 7.1 缓存策略

```java
// Spring Cache 注解
@Cacheable(value = "article", key = "#slug")           // 详情缓存
@Cacheable(value = "article:list", key = "#query.current + '-' + #query.size")
@CacheEvict(value = "article", allEntries = true)       // 清空所有文章缓存
```

**缓存命名规范：**
- `article` - 文章详情（按slug）
- `article:list` - 文章列表
- `article:top-{limit}` - 置顶文章
- `category:list` - 分类列表
- `config:{key}` - 系统配置

### 7.2 慢查询防范

**分页上限：**
- 默认页大小：10
- 最大页大小：100

**索引检查清单：**
- `article.slug` - 唯一索引
- `article.status + publish_time` - 联合索引（列表查询）
- `article.category_id + status` - 联合索引（分类查询）
- `category.parent_id` - 普通索引（树查询）

### 7.3 异步处理

```java
// 非核心操作异步执行（如统计、AI生成）
@Async("taskExecutor")
@Transactional
public void incrementViewCount(String slug) {
    articleRepository.findBySlug(slug).ifPresent(article -> {
        articleRepository.increaseViewCount(new ArticleId(article.getId()));
    });
}
```

---

## 八、API设计规范

### 8.1 RESTful 路径规范

| 操作 | 公开接口 | 管理接口 | 说明 |
|------|----------|----------|------|
| 列表查询 | GET /api/article/list | GET /api/admin/article/list | 分页 |
| 详情查询 | GET /api/article/{slug} | GET /api/admin/article/{id} | |
| 归档查询 | GET /api/article/archive | - | 按年月归档 |
| 置顶文章 | GET /api/article/top | - | |
| 创建 | - | POST /api/admin/article | |
| 更新 | - | PUT /api/admin/article/{id} | |
| 删除 | - | DELETE /api/admin/article/{id} | 逻辑删除 |
| 增加浏览 | POST /api/article/{slug}/view | - | 异步 |

### 8.2 统一响应格式

```json
// 成功响应
{
  "code": 200,
  "message": "success",
  "data": { },
  "timestamp": 1712345678901
}

// 分页响应
{
  "code": 200,
  "message": "success",
  "data": {
    "total": 100,
    "pages": 10,
    "current": 1,
    "size": 10,
    "records": []
  }
}

// 错误响应
{
  "code": 400,
  "message": "标题不能为空",
  "data": null,
  "timestamp": 1712345678901
}
```

---

## 九、开发流程

### 9.1 新增功能开发流程

1. **领域层**（domain/xxx/）
   - 定义实体（Entity），继承 BaseAggregateRoot
   - 定义值对象（Value Object）
   - 定义仓储接口（Repository）
   - 定义领域事件（DomainEvent）

2. **应用层**（application/xxx/）
   - 定义 Command/DTO/Query
   - 实现 AppService

3. **接口层**（interfaces/rest/）
   - 实现 Controller

4. **基础设施层**（infrastructure/persistence/）
   - 实现 Mapper
   - 实现 RepositoryImpl

5. **测试验证**
   - 单元测试（领域逻辑）
   - 集成测试（API接口）

### 9.2 代码提交规范

```bash
# 格式：<type>(<scope>): <subject>
git commit -m "feat(article): 新增文章置顶功能"
git commit -m "fix(auth): 修复Token过期未刷新问题"
git commit -m "refactor(domain): 优化文章状态机实现"
git commit -m "docs(api): 更新文章接口文档"
git commit -m "chore(deps): 升级MyBatis Plus至3.5.9"
```

| Type | 说明 |
|------|------|
| feat | 新功能 |
| fix | Bug修复 |
| refactor | 重构（不改变行为） |
| docs | 文档更新 |
| test | 测试相关 |
| chore | 构建/依赖/工具 |

---

## 十、部署配置

### 10.1 环境配置

| 环境 | 配置文件 | 数据库 |
|------|----------|--------|
| 开发 | application-dev.yml | PostgreSQL (本地) |
| 生产 | application-prod.yml | PostgreSQL (生产) |

### 10.2 JVM参数（2核2G服务器）

```bash
java -Xms256m -Xmx512m \
     -XX:MetaspaceSize=128m \
     -XX:MaxMetaspaceSize=256m \
     -XX:+UseG1GC \
     -XX:MaxGCPauseMillis=200 \
     -jar blog-backend.jar
```

### 10.3 目录规范

```
/opt/nanmuli-blog/
├── blog-backend.jar      # 后端jar包
├── uploads/              # 文件上传目录
├── logs/                 # 日志目录
└── backup/               # 数据备份目录
```

---

## 十一、核心实体字段说明

### 11.1 Article（文章）

| 字段 | 类型 | 说明 |
|------|------|------|
| title | String | 标题，必填 |
| slug | String | URL别名，唯一，自动生成 |
| content | String | Markdown内容 |
| contentHtml | String | 渲染后的HTML |
| summary | String | 摘要，自动提取前200字 |
| cover | String | 封面图URL |
| categoryId | Long | 分类ID（必须关联叶子分类）|
| status | Integer | 1=发布, 2=草稿, 3=回收 |
| isTop | Boolean | 是否置顶 |
| viewCount | Integer | 浏览量 |
| wordCount | Integer | 字数统计 |
| readingTime | Integer | 预估阅读时间（分钟）|

### 11.2 Category（分类）

| 字段 | 类型 | 说明 |
|------|------|------|
| name | String | 分类名称 |
| slug | String | URL别名 |
| parentId | Long | 父分类ID（null=根分类）|
| isLeaf | Boolean | 是否叶子节点（可关联文章）|
| articleCount | Integer | 关联文章数 |
| sort | Integer | 排序权重 |

### 11.3 DailyLog（技术日志）

| 字段 | 类型 | 说明 |
|------|------|------|
| content | String | Markdown内容 |
| contentHtml | String | 渲染后的HTML |
| logDate | LocalDate | 日志日期 |
| mood | String | 心情 |
| weather | String | 天气 |
| tags | String | 标签（逗号分隔）|

---

## 十二、检查清单（Checklist）

### 12.1 代码审查清单

- [ ] 代码符合分层架构规范（无跨层调用）
- [ ] 实体继承 BaseAggregateRoot，使用 createdAt/updatedAt/isDeleted
- [ ] 领域方法封装了业务规则
- [ ] 入参有校验注解（@NotBlank, @Size等）
- [ ] 事务注解使用正确（@Transactional）
- [ ] 缓存注解使用正确（@Cacheable/@CacheEvict）
- [ ] 异常处理完善（无静默捕获）
- [ ] 无SQL注入风险（参数绑定）
- [ ] Repository返回实体，AppService转换为DTO

### 12.2 接口测试清单

- [ ] 正常流程返回200
- [ ] 参数缺失返回400
- [ ] 未登录访问管理接口返回401
- [ ] 资源不存在返回404
- [ ] 业务错误返回422
- [ ] 分页参数边界测试

---

## 附录：快速参考

### A. 依赖注入

```java
// 推荐：构造器注入（Lombok简化）
@Service
@RequiredArgsConstructor
public class XxxService {
    private final XxxRepository xxxRepository;
}
```

### B. 常用校验注解

```java
@NotBlank        // 字符串非空（trim后）
@NotNull         // 对象非null
@Size(max=200)   // 长度限制
@Min(1) @Max(100)// 数值范围
@Pattern(regexp="...") // 正则匹配
```

### C. 常用MyBatis Plus方法

```java
// 插入（ID自动填充）
mapper.insert(entity);

// 根据ID查询（自动过滤逻辑删除）
mapper.selectById(id);

// 条件查询
mapper.selectList(Wrappers.<Article>lambdaQuery()
    .eq(Article::getStatus, 1)
    .orderByDesc(Article::getPublishTime));

// 分页查询
mapper.selectPage(page, wrapper);

// 更新（乐观锁自动处理）
mapper.updateById(entity);

// 删除（逻辑删除）
mapper.deleteById(id);
```

### D. 缓存使用

```java
@CacheConfig(cacheNames = "article")
public class ArticleAppService {

    @Cacheable(key = "#slug")
    public ArticleDTO getBySlug(String slug) { }

    @CacheEvict(allEntries = true)
    public void update(UpdateArticleCommand command) { }
}
```

---

> 本文档版本：v1.1
> 最后更新：2026-04-05
> 维护者：nanmuli
