# 个人技术博客系统 - 开发方案
## 基于 Spring Boot 3.3 + Vue 3 + DDD 架构

---

## 一、项目定位

### 1.1 核心定位
- **个人技术博客**：记录技术学习、分享技术文章
- **个人展示网站**：展示个人技能、项目经历
- **技术日志**：每日技术笔记、学习总结

### 1.2 用户角色
- **仅有一个管理员**：自己
- **访客**：只能浏览，不能互动（无评论）

### 1.3 核心功能
1. 文章管理（Markdown编辑、发布、分类、标签）
2. 技术日志（快速记录、时间线展示）
3. 个人展示（关于页面、技能展示、项目展示）
4. 数据统计（文章浏览量、独立访客统计）
5. AI辅助（智能标签、文章摘要 - 预留接口）

---

## 二、技术架构

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        个人技术博客系统                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────────┐         ┌──────────────────────────┐ │
│  │       前端层          │         │          后端层           │ │
│  │  ┌────────────────┐  │         │  ┌────────────────────┐   │ │
│  │  │   Vue 3        │  │         │  │  Spring Boot 3.3   │   │ │
│  │  │   + Vite       │  │◄───────►│  │  + Java 21         │   │ │
│  │  │   + TypeScript │  │  HTTP   │  │  + DDD架构         │   │ │
│  │  │   + Tailwind   │  │         │  │  + MyBatis Plus    │   │ │
│  │  │   + Pinia      │  │         │  │  + Sa-Token        │   │ │
│  │  │   + Element+   │  │         │  └────────────────────┘   │ │
│  │  └────────────────┘  │         └───────────┬───────────────┘ │
│  └──────────────────────┘                     │                 │
│  ┌──────────────────────┐         ┌───────────▼───────────┐    │
│  │    客户端搜索         │         │       数据层           │    │
│  │  ┌────────────────┐  │         │  ┌─────────────────┐   │    │
│  │  │   Pagefind     │  │         │  │   PostgreSQL    │   │    │
│  │  │   (全文搜索)    │  │         │  │   (主数据库)     │   │    │
│  │  └────────────────┘  │         │  └─────────────────┘   │    │
│  └──────────────────────┘         │  ┌─────────────────┐   │    │
│                                     │  │     Redis       │   │    │
│                                     │  │   (缓存/会话)    │   │    │
│                                     │  └─────────────────┘   │    │
│                                     └────────────────────────┘    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 技术栈

| 层级 | 技术选型 | 版本 |
|------|----------|------|
| **后端** | Spring Boot | 3.3.5 |
| **JDK** | Java | 21 LTS |
| **ORM** | MyBatis Plus | 3.5.9 |
| **数据库** | PostgreSQL | 15+ |
| **缓存** | Redis | 7+ |
| **认证** | Sa-Token | 1.44.0 |
| **API文档** | Knife4j | 4.4.0 |
| **工具库** | Hutool | 5.8.36 |
| **前端** | Vue | 3.4.15 |
| **构建** | Vite | 5.0.11 |
| **类型** | TypeScript | 5.3.3 |
| **样式** | Tailwind CSS | 3.4.1 |
| **UI组件** | Element Plus | 2.5.1 |
| **状态** | Pinia | 2.1.7 |
| **Markdown** | md-editor-v3 | 4.11.0 |
| **搜索** | Pagefind | 1+ |

---

## 三、DDD 分层架构

### 3.1 架构分层图

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

### 3.2 分层调用规则

| 规则 | 说明 |
|------|------|
| 允许 | `Controller` → `AppService` → `Repository` |
| 允许 | `AppService` 调用多个聚合的 `Repository` |
| 允许 | `RepositoryImpl` 实现 `Repository` 接口 |
| 禁止 | `Controller` 直接调用 `Repository` |
| 禁止 | `AppService` 之间互相调用 |
| 禁止 | 领域层依赖应用层/接口层 |
| 禁止 | 跨聚合直接操作实体（必须通过聚合根）|

### 3.3 包结构规范

```
com.nanmuli.blog
├── domain                          # 领域层 - 核心业务逻辑
│   ├── article                     # 文章聚合
│   │   ├── Article.java            # 聚合根实体
│   │   ├── ArticleId.java          # 值对象（ID包装）
│   │   ├── ArticleStatus.java      # 枚举（1=发布, 2=草稿, 3=回收）
│   │   ├── ArticleRepository.java  # 仓储接口
│   │   ├── ArticleViewRecord.java  # 阅读记录实体
│   │   ├── ArticleVisitLog.java    # 访问日志实体
│   │   └── event/                  # 领域事件
│   │       ├── ArticleCreatedEvent.java
│   │       └── ArticlePublishedEvent.java
│   ├── category                    # 分类聚合
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
│   │   ├── ArticleController.java
│   │   ├── AuthController.java
│   │   └── ...
│   ├── handler                     # 异常处理器
│   └── filter                      # 过滤器
│       └── TraceIdFilter.java
│
├── infrastructure                  # 基础设施层
│   ├── config                      # 配置类
│   │   ├── db/MyBatisPlusConfig.java
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

### 3.4 核心实体设计

#### 实体基类（BaseAggregateRoot）

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

#### 文章实体（Article）

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

### 3.5 应用服务（Application Service）

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

### 3.6 控制器（Controller）

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

---

## 四、数据库设计

### 4.1 表结构概览

| 表名 | 说明 | 数据量预估 |
|------|------|------------|
| sys_user | 用户表（仅管理员） | < 5 |
| sys_login_log | 登录日志 | < 1,000 |
| sys_file | 文件表 | < 2,000 |
| sys_config | 系统配置 | < 30 |
| sys_operation_log | 操作日志 | < 10,000 |
| article | 文章表 | < 500 |
| article_view_record | 文章阅读记录（UV统计） | < 50,000 |
| article_visit_log | 文章访问日志（PV统计） | < 100,000 |
| daily_log | 技术日志表 | < 1,000 |
| category | 分类表 | < 15 |
| tag | 标签表 | < 50 |
| article_tag | 文章标签关联表 | < 2,000 |
| project | 项目展示表 | < 20 |
| skill | 技能表 | < 30 |
| friend_link | 友链表 | < 30 |
| ai_generation | AI生成记录表 | < 1,000 |

### 4.2 核心表设计

#### 文章表 (article)

```sql
CREATE TABLE article (
    id BIGSERIAL PRIMARY KEY COMMENT '文章ID',
    title VARCHAR(200) NOT NULL COMMENT '标题',
    slug VARCHAR(200) UNIQUE COMMENT 'URL别名',
    content TEXT NOT NULL COMMENT '内容（Markdown）',
    content_html TEXT COMMENT '内容（HTML渲染后）',
    summary VARCHAR(500) COMMENT '摘要',
    cover VARCHAR(255) COMMENT '封面图URL',
    category_id BIGINT COMMENT '分类ID',
    user_id BIGINT NOT NULL COMMENT '作者ID',
    view_count INT NOT NULL DEFAULT 0 COMMENT '浏览量',
    like_count INT NOT NULL DEFAULT 0 COMMENT '点赞数',
    word_count INT COMMENT '字数统计',
    reading_time INT COMMENT '阅读时间（分钟）',
    status INT NOT NULL DEFAULT 1 COMMENT '状态：1-已发布 2-草稿 3-回收站',
    is_top BOOLEAN NOT NULL DEFAULT FALSE COMMENT '是否置顶',
    is_original BOOLEAN NOT NULL DEFAULT TRUE COMMENT '是否原创',
    original_url VARCHAR(500) COMMENT '原文链接',
    publish_time TIMESTAMP COMMENT '发布时间',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '更新时间',
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE COMMENT '逻辑删除',
    version INT DEFAULT 0 COMMENT '乐观锁版本号'
);

-- 索引
CREATE INDEX idx_article_category_id ON article(category_id);
CREATE INDEX idx_article_status ON article(status);
CREATE INDEX idx_article_is_top ON article(is_top);
CREATE INDEX idx_article_publish_time ON article(publish_time DESC);
CREATE INDEX idx_article_is_deleted ON article(is_deleted);
```

#### 文章阅读记录表 (article_view_record)

```sql
CREATE TABLE article_view_record (
    id BIGSERIAL PRIMARY KEY COMMENT '记录ID',
    article_id BIGINT NOT NULL COMMENT '文章ID',
    visitor_id VARCHAR(64) NOT NULL COMMENT '访客标识',
    ip_address VARCHAR(50) COMMENT 'IP地址',
    user_agent VARCHAR(500) COMMENT '浏览器UA',
    first_view_time TIMESTAMP NOT NULL COMMENT '首次访问时间',
    last_view_time TIMESTAMP NOT NULL COMMENT '最后访问时间',
    view_count INT NOT NULL DEFAULT 1 COMMENT '访问次数',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT uk_article_visitor UNIQUE (article_id, visitor_id)
);

CREATE INDEX idx_avr_article_id ON article_view_record(article_id);
CREATE INDEX idx_avr_visitor_id ON article_view_record(visitor_id);
```

#### 分类表 (category)

```sql
CREATE TABLE category (
    id BIGSERIAL PRIMARY KEY COMMENT '分类ID',
    name VARCHAR(50) NOT NULL COMMENT '分类名称',
    slug VARCHAR(50) UNIQUE COMMENT 'URL别名',
    description VARCHAR(200) COMMENT '描述',
    icon VARCHAR(50) COMMENT '图标',
    color VARCHAR(20) COMMENT '颜色',
    sort INT NOT NULL DEFAULT 0 COMMENT '排序',
    parent_id BIGINT COMMENT '父分类ID（支持多级）',
    is_leaf BOOLEAN NOT NULL DEFAULT TRUE COMMENT '是否叶子节点',
    article_count INT NOT NULL DEFAULT 0 COMMENT '文章数量',
    status INT NOT NULL DEFAULT 1 COMMENT '状态：1-正常 0-禁用',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    
    CONSTRAINT fk_category_parent FOREIGN KEY (parent_id) REFERENCES category(id)
);
```

---

## 五、后端项目结构

### 5.1 项目结构

```
backend/
├── src/
│   ├── main/
│   │   ├── java/
│   │   │   └── com/nanmuli/blog/
│   │   │       ├── BlogApplication.java
│   │   │       │
│   │   │       ├── domain/                    # 领域层
│   │   │       │   ├── article/
│   │   │       │   │   ├── Article.java
│   │   │       │   │   ├── ArticleId.java
│   │   │       │   │   ├── ArticleStatus.java
│   │   │       │   │   ├── ArticleRepository.java
│   │   │       │   │   ├── ArticleViewRecord.java
│   │   │       │   │   ├── ArticleVisitLog.java
│   │   │       │   │   └── event/
│   │   │       │   ├── category/
│   │   │       │   ├── dailylog/
│   │   │       │   ├── skill/
│   │   │       │   ├── project/
│   │   │       │   ├── friendlink/
│   │   │       │   ├── config/
│   │   │       │   ├── file/
│   │   │       │   ├── user/
│   │   │       │   └── ai/
│   │   │       │
│   │   │       ├── application/               # 应用层
│   │   │       │   ├── article/
│   │   │       │   │   ├── ArticleAppService.java
│   │   │       │   │   ├── command/
│   │   │       │   │   │   ├── CreateArticleCommand.java
│   │   │       │   │   │   ├── UpdateArticleCommand.java
│   │   │       │   │   │   └── RecordArticleViewCommand.java
│   │   │       │   │   ├── dto/
│   │   │       │   │   │   ├── ArticleDTO.java
│   │   │       │   │   │   ├── ArticleArchiveDTO.java
│   │   │       │   │   │   └── ArticleStatsDTO.java
│   │   │       │   │   └── query/
│   │   │       │   │       └── ArticlePageQuery.java
│   │   │       │   ├── category/
│   │   │       │   ├── dailylog/
│   │   │       │   ├── skill/
│   │   │       │   ├── project/
│   │   │       │   ├── friendlink/
│   │   │       │   ├── config/
│   │   │       │   ├── file/
│   │   │       │   ├── user/
│   │   │       │   └── event/
│   │   │       │       └── ArticleEventHandler.java
│   │   │       │
│   │   │       ├── interfaces/                # 接口层
│   │   │       │   ├── rest/
│   │   │       │   │   ├── ArticleController.java
│   │   │       │   │   ├── AuthController.java
│   │   │       │   │   ├── CategoryController.java
│   │   │       │   │   ├── DailyLogController.java
│   │   │       │   │   ├── SkillController.java
│   │   │       │   │   ├── ProjectController.java
│   │   │       │   │   ├── FriendLinkController.java
│   │   │       │   │   ├── ConfigController.java
│   │   │       │   │   ├── FileController.java
│   │   │       │   │   └── DashboardController.java
│   │   │       │   ├── handler/
│   │   │       │   └── filter/
│   │   │       │       └── TraceIdFilter.java
│   │   │       │
│   │   │       ├── infrastructure/            # 基础设施层
│   │   │       │   ├── config/
│   │   │       │   │   ├── db/
│   │   │       │   │   │   └── MyBatisPlusConfig.java
│   │   │       │   │   ├── cache/
│   │   │       │   │   │   └── RedisConfig.java
│   │   │       │   │   ├── security/
│   │   │       │   │   │   └── SaTokenConfig.java
│   │   │       │   │   ├── web/
│   │   │       │   │   │   ├── Knife4jConfig.java
│   │   │       │   │   │   └── WebMvcConfig.java
│   │   │       │   │   └── ai/
│   │   │       │   │       └── AsyncConfig.java
│   │   │       │   ├── persistence/
│   │   │       │   │   ├── article/
│   │   │       │   │   │   ├── ArticleMapper.java
│   │   │       │   │   │   ├── ArticleRepositoryImpl.java
│   │   │       │   │   │   ├── ArticleViewRecordMapper.java
│   │   │       │   │   │   └── ArticleViewRecordRepositoryImpl.java
│   │   │       │   │   ├── category/
│   │   │       │   │   ├── dailylog/
│   │   │       │   │   ├── skill/
│   │   │       │   │   ├── project/
│   │   │       │   │   ├── friendlink/
│   │   │       │   │   ├── config/
│   │   │       │   │   ├── file/
│   │   │       │   │   ├── user/
│   │   │       │   │   └── ai/
│   │   │       │   └── ai/
│   │   │       │       └── NoOpAiService.java
│   │   │       │
│   │   │       └── shared/                    # 共享内核
│   │   │           ├── domain/
│   │   │           │   ├── BaseAggregateRoot.java
│   │   │           │   ├── DomainEvent.java
│   │   │           │   └── Identifier.java
│   │   │           ├── result/
│   │   │           │   ├── Result.java
│   │   │           │   └── PageResult.java
│   │   │           ├── exception/
│   │   │           │   └── BusinessException.java
│   │   │           └── util/
│   │   │               └── MarkdownUtil.java
│   │   │
│   │   └── resources/
│   │       ├── db/                            # 数据库迁移
│   │       ├── sql/                           # SQL脚本
│   │       ├── application.yml
│   │       ├── application-dev.yml
│   │       ├── application-prod.yml
│   │       └── logback-spring.xml
│   │
│   └── test/
│
├── pom.xml
└── Dockerfile
```

---

## 六、前端项目结构

### 6.1 项目结构

```
frontend/
├── public/
│   ├── favicon.ico
│   └── logo.png
│
├── src/
│   ├── api/                           # API接口
│   │   ├── auth.ts
│   │   ├── article.ts
│   │   ├── dailyLog.ts
│   │   ├── category.ts
│   │   ├── tag.ts
│   │   ├── file.ts
│   │   ├── config.ts
│   │   ├── project.ts
│   │   ├── skill.ts
│   │   └── dashboard.ts
│   │
│   ├── assets/                        # 静态资源
│   │   ├── images/
│   │   └── styles/
│   │       └── tailwind.css
│   │
│   ├── components/                    # 公共组件
│   │   ├── common/
│   │   │   ├── AppHeader.vue
│   │   │   ├── AppFooter.vue
│   │   │   └── AppSidebar.vue
│   │   ├── article/
│   │   │   ├── ArticleCard.vue
│   │   │   ├── ArticleList.vue
│   │   │   ├── ArticleMeta.vue
│   │   │   └── ArticleToc.vue
│   │   ├── dailyLog/
│   │   │   └── DailyLogTimeline.vue
│   │   ├── project/
│   │   │   └── ProjectCard.vue
│   │   └── skill/
│   │       └── SkillCloud.vue
│   │
│   ├── composables/                   # 组合式函数
│   │   ├── useAuth.ts
│   │   └── useTheme.ts
│   │
│   ├── layouts/                       # 布局组件
│   │   ├── DefaultLayout.vue
│   │   ├── AdminLayout.vue
│   │   └── BlankLayout.vue
│   │
│   ├── router/                        # 路由配置
│   │   ├── index.ts
│   │   └── routes.ts
│   │
│   ├── stores/                        # 状态管理
│   │   ├── index.ts
│   │   ├── modules/
│   │   │   ├── user.ts
│   │   │   ├── article.ts
│   │   │   └── config.ts
│   │   └── plugins/
│   │       └── persist.ts
│   │
│   ├── styles/                        # 样式文件
│   │   ├── index.scss
│   │   ├── markdown.scss
│   │   └── code.scss
│   │
│   ├── types/                         # 类型定义
│   │   ├── article.ts
│   │   ├── dailyLog.ts
│   │   └── api.ts
│   │
│   ├── utils/                         # 工具函数
│   │   ├── request.ts
│   │   ├── storage.ts
│   │   ├── format.ts
│   │   └── visitor.ts
│   │
│   ├── views/                         # 页面视图
│   │   ├── home/
│   │   │   └── Index.vue
│   │   ├── article/
│   │   │   ├── List.vue
│   │   │   └── Detail.vue
│   │   ├── dailyLog/
│   │   │   └── List.vue
│   │   ├── category/
│   │   │   └── Index.vue
│   │   ├── about/
│   │   │   └── Index.vue
│   │   ├── project/
│   │   │   └── Index.vue
│   │   ├── auth/
│   │   │   └── Login.vue
│   │   └── admin/
│   │       ├── Dashboard.vue
│   │       ├── article/
│   │       │   ├── List.vue
│   │       │   ├── Create.vue
│   │       │   └── Edit.vue
│   │       ├── dailyLog/
│   │       ├── category/
│   │       ├── tag/
│   │       ├── project/
│   │       ├── skill/
│   │       └── config/
│   │
│   ├── App.vue
│   ├── main.ts
│   └── env.d.ts
│
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
├── tailwind.config.js
├── postcss.config.js
├── eslint.config.js
└── .prettierrc
```

---

## 七、API设计规范

### 7.1 RESTful 路径规范

| 操作 | 公开接口 | 管理接口 | 说明 |
|------|----------|----------|------|
| 列表查询 | GET /api/article/list | GET /api/admin/article/list | 分页 |
| 详情查询 | GET /api/article/{slug} | GET /api/admin/article/{id} | |
| 归档查询 | GET /api/article/archive | - | 按年月归档 |
| 置顶文章 | GET /api/article/top | - | |
| 创建 | - | POST /api/admin/article | |
| 更新 | - | PUT /api/admin/article/{id} | |
| 删除 | - | DELETE /api/admin/article/{id} | 逻辑删除 |
| 记录浏览 | POST /api/article/{slug}/view | - | 异步 |

### 7.2 统一响应格式

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

### 7.3 HTTP状态码规范

| 场景 | 状态码 | 说明 |
|------|--------|------|
| 成功 | 200 | 标准成功 |
| 参数错误 | 400 | 客户端输入验证失败 |
| 未认证 | 401 | 需要登录（Sa-Token拦截）|
| 无权限 | 403 | 权限不足 |
| 资源不存在 | 404 | URL错误或资源已删除 |
| 业务错误 | 422 | 业务规则校验失败 |
| 系统错误 | 500 | 服务器内部错误 |

---

## 八、开发路线图

### 阶段一：基础架构（已完成）
- 后端DDD架构搭建
- 前端Vue3项目搭建
- 数据库设计与初始化

### 阶段二：核心功能（已完成）
- 用户认证模块
- 文章管理（CRUD、Markdown编辑）
- 分类标签管理
- 技术日志模块
- 文件上传

### 阶段三：功能增强（已完成）
- 文章浏览统计（PV/UV）
- 仪表盘数据展示
- 主题切换（明暗主题）

### 阶段四：部署优化（待完成）
- 生产环境配置
- Docker容器化
- CI/CD流程

---

## 九、部署架构

### 9.1 阿里云服务器部署

```
┌─────────────────────────────────────────┐
│           阿里云ECS (2核2G3M)            │
│                                         │
│  ┌─────────────┐    ┌───────────────┐  │
│  │   Nginx     │    │  Spring Boot  │  │
│  │   :80/:443  │◄──►│  :8080        │  │
│  │  (静态资源)  │    │  (JVM 512MB)  │  │
│  └─────────────┘    └───────────────┘  │
│                              │          │
│  ┌─────────────┐    ┌───────────────┐  │
│  │  PostgreSQL │    │     Redis     │  │
│  │   :5432     │    │    :6379      │  │
│  │  (400MB)    │    │  (限制100MB)  │  │
│  └─────────────┘    └───────────────┘  │
│                                         │
└─────────────────────────────────────────┘
```

### 9.2 JVM参数

```bash
java -Xms256m -Xmx512m \
     -XX:MetaspaceSize=128m \
     -XX:MaxMetaspaceSize=256m \
     -XX:+UseG1GC \
     -XX:MaxGCPauseMillis=200 \
     -jar blog-backend.jar
```

---

## 十、总结

### 10.1 技术栈总览

| 层级 | 技术选型 |
|------|----------|
| **后端** | Spring Boot 3.3 + Java 21 + DDD + MyBatis Plus + Sa-Token + PostgreSQL + Redis |
| **前端** | Vue 3 + Vite + TypeScript + Tailwind CSS + Element Plus + Pinia |
| **部署** | 阿里云ECS 2核2G + Nginx |

### 10.2 架构特点

1. **DDD分层架构**：清晰的领域层、应用层、接口层、基础设施层分离
2. **领域驱动设计**：聚合根、值对象、领域事件、仓储模式
3. **独立访客统计**：基于 visitorId 的 UV 统计，基于访问日志的 PV 统计
4. **缓存策略**：Spring Cache + Redis，支持多级缓存
5. **安全设计**：Sa-Token 认证、XSS 防护、SQL 注入防护

### 10.3 项目状态

- 后端核心功能：已完成
- 前端核心功能：已完成
- 数据统计：已完成
- AI功能：预留接口，待接入

---

**文档版本：** v2.0  
**最后更新：** 2026-04-06  
**架构：** DDD (Domain-Driven Design)
