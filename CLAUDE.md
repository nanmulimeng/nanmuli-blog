# Nanmuli Blog - 项目开发规范

> 个人技术博客系统 - 后端开发规范文档
> 基于 Spring Boot 3.3 + Java 21 + DDD 架构

---

## 一、项目概述

### 1.1 项目定位
个人技术博客系统，记录技术学习、分享技术文章，展示个人技能与项目经历。

### 1.2 用户角色
- **管理员（仅1人）**：内容管理、系统配置
- **访客**：只读访问，无交互功能

### 1.3 核心模块
| 模块 | 功能 |
|------|------|
| 文章管理 | Markdown编辑、发布、分类、标签 |
| 技术日志 | 快速记录、时间线展示 |
| 个人展示 | 技能展示、项目展示 |
| AI辅助 | 智能标签、文章摘要（可选） |

---

## 二、技术栈

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
| 向量扩展 | pgvector | 0.1.4 |

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
│   │   ├── ArticleId.java          # 值对象（ID）
│   │   ├── ArticleStatus.java      # 枚举
│   │   └── ArticleRepository.java  # 仓储接口
│   ├── category                    # 分类聚合
│   ├── tag                         # 标签聚合
│   └── ...                         # 其他聚合
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
│   └── rest
│       ├── ArticleController.java  # REST控制器
│       └── ...
│
├── infrastructure                  # 基础设施层
│   ├── config                      # 配置类
│   │   ├── MyBatisPlusConfig.java
│   │   ├── SaTokenConfig.java
│   │   └── Knife4jConfig.java
│   └── persistence                 # 持久化实现
│       └── article
│           ├── ArticleMapper.java
│           └── ArticleRepositoryImpl.java
│
└── shared                          # 共享内核
    ├── domain                      # 共享领域基类
    │   ├── BaseAggregateRoot.java
    │   └── Identifier.java
    ├── result                      # 统一响应
    │   ├── Result.java
    │   └── PageResult.java
    └── exception                   # 异常定义
        └── BusinessException.java
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

### 4.2 类文件规范

#### 4.2.1 聚合根实体（Domain）

```java
@Getter
@Setter
@EqualsAndHashCode(callSuper = false)
public class Article extends BaseAggregateRoot<Long> {
    private static final long serialVersionUID = 1L;

    // 字段：private 修饰，按业务逻辑分组
    private String title;
    private String content;
    private Integer status;

    // 领域方法：封装业务规则
    public void publish() {
        this.status = ArticleStatus.PUBLISHED.getCode();
        this.publishTime = LocalDateTime.now();
    }

    public boolean isPublished() {
        return status != null && status == ArticleStatus.PUBLISHED.getCode();
    }
}
```

**要求：**
- 必须继承 `BaseAggregateRoot<ID>`
- 领域方法必须封装业务规则（如状态转换校验）
- 禁止直接暴露内部集合（返回副本或不可修改视图）

#### 4.2.2 应用服务（Application）

```java
@Service
@RequiredArgsConstructor  // Lombok：生成构造器注入
@Transactional(readOnly = true)  // 默认只读事务
public class ArticleAppService {

    private final ArticleRepository articleRepository;
    private final CategoryRepository categoryRepository;

    @Transactional  // 写操作需要写事务
    public Long create(CreateArticleCommand command) {
        // 1. 校验（必要时）
        // 2. 创建领域对象
        // 3. 执行业务操作
        // 4. 持久化
        // 5. 返回标识
    }

    public ArticleDTO getById(Long id) {
        // 查询并转换DTO
    }
}
```

**要求：**
- 必须标注 `@Service` 和 `@Transactional`
- 使用构造器注入（`@RequiredArgsConstructor`）
- 一个方法对应一个用例
- 禁止在应用服务中写业务规则（应下沉到领域层）

#### 4.2.3 控制器（Interface）

```java
@Tag(name = "文章管理")  // Swagger分组
@RestController
@RequestMapping("/api")
@RequiredArgsConstructor
public class ArticleController {

    private final ArticleAppService articleAppService;

    @GetMapping("/article/list")
    public Result<PageResult<ArticleDTO>> list(ArticlePageQuery query) {
        return Result.success(articleAppService.listPublished(query));
    }

    @PostMapping("/admin/article")
    public Result<Long> create(@Valid @RequestBody CreateArticleCommand command) {
        return Result.success(articleAppService.create(command));
    }
}
```

**要求：**
- 路径前缀：公开接口 `/api/**`，管理接口 `/api/admin/**`
- 入参校验：`@Valid` 激活 Bean Validation
- 统一返回：`Result<T>` 包装
- 禁止在 Controller 中写业务逻辑

#### 4.2.4 数据传输对象

```java
// Command：写操作入参
@Data
public class CreateArticleCommand {
    @NotBlank(message = "标题不能为空")
    @Size(max = 200, message = "标题长度不能超过200字符")
    private String title;

    @NotBlank(message = "内容不能为空")
    private String content;

    private Long categoryId;
}

// DTO：读操作出参
@Data
public class ArticleDTO {
    private Long id;
    private String title;
    private String summary;
    private LocalDateTime publishTime;
}

// Query：分页查询参数
@Data
public class ArticlePageQuery {
    private Long current = 1L;
    private Long size = 10L;
    private Long categoryId;
    private String keyword;
}
```

**要求：**
- Command/DTO/Query 严格分离
- 入参必须加校验注解
- 禁止在 DTO 中暴露敏感字段（如 password）

### 4.3 异常处理规范

```java
// 业务异常（预期内）
public class BusinessException extends RuntimeException {
    private final Integer code;

    public BusinessException(String message) {
        super(message);
        this.code = 400;
    }

    public BusinessException(Integer code, String message) {
        super(message);
        this.code = code;
    }
}

// 全局异常处理器
@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(BusinessException.class)
    public Result<Void> handleBusinessException(BusinessException e) {
        return Result.error(e.getCode(), e.getMessage());
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public Result<Void> handleValidationException(MethodArgumentNotValidException e) {
        String message = e.getBindingResult().getFieldErrors().stream()
                .map(FieldError::getDefaultMessage)
                .collect(Collectors.joining(", "));
        return Result.error(400, message);
    }

    @ExceptionHandler(Exception.class)
    public Result<Void> handleException(Exception e) {
        // 记录日志
        return Result.error(500, "系统繁忙，请稍后重试");
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
| 业务错误 | 422 | 业务规则校验失败（如重复创建） |
| 系统错误 | 500 | 服务器内部错误 |

---

## 五、数据访问规范

### 5.1 Repository 模式

```java
// 领域层定义接口
public interface ArticleRepository {
    void save(Article article);
    void deleteById(ArticleId id);
    Optional<Article> findById(ArticleId id);
    Optional<Article> findBySlug(String slug);
    IPage<Article> findPublishedPage(IPage<Article> page);
}

// 基础设施层实现
@Repository
@RequiredArgsConstructor
public class ArticleRepositoryImpl implements ArticleRepository {

    private final ArticleMapper articleMapper;

    @Override
    public void save(Article article) {
        if (article.isNew()) {
            articleMapper.insert(article);
        } else {
            articleMapper.updateById(article);
        }
    }

    @Override
    public Optional<Article> findById(ArticleId id) {
        return Optional.ofNullable(articleMapper.selectById(id.getValue()));
    }
}
```

### 5.2 MyBatis Plus 使用规范

#### 全局配置

```yaml
mybatis-plus:
  global-config:
    db-config:
      # 逻辑删除字段名（与实体类属性名一致，自动映射为数据库下划线命名）
      logic-delete-field: isDeleted
      logic-delete-value: true
      logic-not-delete-value: false
      # ID生成策略
      id-type: assign_id
  configuration:
    # 开启驼峰命名自动转换
    map-underscore-to-camel-case: true
    # 日志实现
    log-impl: org.apache.ibatis.logging.slf4j.Slf4jImpl
```

#### Mapper接口

```java
@Mapper
public interface ArticleMapper extends BaseMapper<Article> {

    // 复杂查询使用自定义SQL
    @Select("SELECT * FROM article WHERE status = #{status} ORDER BY publish_time DESC")
    List<Article> selectByStatus(@Param("status") Integer status);

    // 关联查询（避免N+1）
    @Select("""
        SELECT a.*, c.name as categoryName
        FROM article a
        LEFT JOIN category c ON a.category_id = c.id
        WHERE a.id = #{id}
        """)
    @Results({
        @Result(property = "id", column = "id"),
        @Result(property = "category.name", column = "categoryName")
    })
    Article selectDetailById(Long id);
}
```

**查询优化清单：**
- ✅ 分页查询必须加索引条件过滤
- ✅ 避免 `SELECT *`，只查询需要的字段
- ✅ 关联查询用 JOIN，禁止循环查询
- ❌ 禁止在循环中执行SQL（N+1问题）
- ❌ 禁止无条件的全表 UPDATE/DELETE

---

## 六、安全规范

### 6.1 认证授权

- 管理接口统一使用 Sa-Token 拦截：`/api/admin/**`
- Token 有效期：30天（2592000秒）
- 密码加密：BCrypt（自动处理）

### 6.2 输入安全

| 威胁 | 防护措施 |
|------|----------|
| SQL注入 | MyBatis参数绑定（#{}），禁止字符串拼接 |
| XSS攻击 | 富文本内容服务端净化，或客户端渲染转义 |
| 文件上传 | 限制类型（白名单），限制大小（10MB） |
| 路径遍历 | 文件名MD5重命名，禁止保留原始路径 |

### 6.3 敏感数据处理

```java
// 日志脱敏
log.info("用户登录: {}", StrUtil.hide(user.getPhone(), 3, 7));
// 输出: 138****1234

// 返回脱敏
userDTO.setPassword(null);  // 密码绝不返回
userDTO.setEmail(StrUtil.hide(email, 3, email.indexOf('@')));
```

---

## 七、性能规范

### 7.1 缓存策略

```java
// Spring Cache 注解
@Cacheable(value = "article", key = "#slug")
public ArticleDTO getBySlug(String slug) { }

@CacheEvict(value = "article", key = "#command.slug")
public void update(UpdateArticleCommand command) { }

@CacheEvict(value = "article", allEntries = true)
public void delete(Long id) { }
```

**缓存命名规范：**
- `article` - 文章详情
- `category:list` - 分类列表
- `tag:cloud` - 标签云
- `config:{key}` - 系统配置

### 7.2 慢查询防范

```yaml
# application.yml 配置
mybatis-plus:
  configuration:
    # 开发环境开启SQL日志
    log-impl: org.apache.ibatis.logging.slf4j.Slf4jImpl
```

**分页上限：**
- 默认页大小：10
- 最大页大小：100

### 7.3 异步处理

```java
// 非核心操作异步执行（如统计、AI生成）
@Async("taskExecutor")
public CompletableFuture<Void> generateTagsAsync(Long articleId) {
    // AI标签生成逻辑
}
```

---

## 八、API设计规范

### 8.1 RESTful 路径规范

| 操作 | 公开接口 | 管理接口 | 说明 |
|------|----------|----------|------|
| 列表查询 | GET /api/article/list | GET /api/admin/article/list | 分页 |
| 详情查询 | GET /api/article/{slug} | GET /api/admin/article/{id} | |
| 创建 | - | POST /api/admin/article | |
| 更新 | - | PUT /api/admin/article/{id} | |
| 删除 | - | DELETE /api/admin/article/{id} | 逻辑删除 |

### 8.2 统一响应格式

```json
// 成功响应
{
  "code": 200,
  "message": "success",
  "data": {
    "id": 1,
    "title": "文章标题"
  },
  "timestamp": 1712345678901
}

// 分页响应
{
  "code": 200,
  "message": "success",
  "data": {
    "total": 100,
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
   - 定义实体（Entity）
   - 定义值对象（Value Object）
   - 定义仓储接口（Repository）

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
# 示例：
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
| 生产 | application-prod.yml | PostgreSQL (阿里云) |

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

## 十一、检查清单（Checklist）

### 11.1 代码审查清单

- [ ] 代码符合分层架构规范（无跨层调用）
- [ ] 领域方法封装了业务规则
- [ ] 入参有校验注解（@NotBlank, @Size等）
- [ ] 事务注解使用正确（@Transactional）
- [ ] 异常处理完善（无静默捕获）
- [ ] 无SQL注入风险（参数绑定）
- [ ] 敏感数据已脱敏

### 11.2 接口测试清单

- [ ] 正常流程返回200
- [ ] 参数缺失返回400
- [ ] 未登录访问管理接口返回401
- [ ] 资源不存在返回404
- [ ] 业务错误返回422
- [ ] 分页参数边界测试

---

## 附录：快速参考

### A. 常用依赖注入

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
// 插入
mapper.insert(entity);

// 根据ID查询
mapper.selectById(id);

// 条件查询
mapper.selectList(Wrappers.<Article>lambdaQuery()
    .eq(Article::getStatus, 1)
    .orderByDesc(Article::getPublishTime));

// 分页查询
mapper.selectPage(page, wrapper);

// 更新
mapper.updateById(entity);

// 删除（逻辑删除）
mapper.deleteById(id);
```

---

> 本文档版本：v1.0
> 最后更新：2026-04-04
> 维护者：nanmuli
