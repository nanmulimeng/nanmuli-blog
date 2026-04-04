# 后端架构说明

## 目录结构规范

```
com.nanmuli.blog
├── domain                          # 领域层 - 核心业务逻辑
│   ├── article                     # 文章聚合
│   │   ├── Article.java            # 聚合根实体
│   │   ├── ArticleId.java          # 值对象（ID）
│   │   ├── ArticleStatus.java      # 枚举
│   │   ├── ArticleRepository.java  # 仓储接口
│   │   └── event/                  # 领域事件
│   │       ├── ArticlePublishedEvent.java
│   │       └── ArticleCreatedEvent.java
│   ├── category                    # 分类聚合
│   ├── tag                         # 标签聚合
│   ├── ai                          # AI领域
│   │   ├── AiService.java          # AI服务接口（防腐层）
│   │   └── AiGeneration.java       # AI生成记录实体
│   └── ...                         # 其他聚合
│
├── application                     # 应用层 - 用例编排
│   ├── article
│   │   ├── ArticleAppService.java           # 应用服务
│   │   ├── command/CreateArticleCommand.java # 命令对象（写）
│   │   ├── dto/ArticleDTO.java               # 数据传输对象（读）
│   │   └── query/ArticlePageQuery.java       # 查询对象
│   ├── event/
│   │   └── ArticleEventHandler.java          # 领域事件处理器
│   └── ...
│
├── interfaces                      # 接口层 - 外部交互
│   ├── rest/                       # REST控制器
│   │   ├── ArticleController.java
│   │   └── ...
│   ├── handler/                    # 处理器
│   │   └── GlobalExceptionHandler.java
│   └── filter/                     # 过滤器
│       └── TraceIdFilter.java
│
├── infrastructure                  # 基础设施层
│   ├── config/                     # 配置类（按功能细分）
│   │   ├── ai/                     # AI配置
│   │   │   ├── AiConfig.java
│   │   │   └── AsyncConfig.java
│   │   ├── cache/                  # 缓存配置
│   │   │   ├── CacheConfig.java
│   │   │   └── RedisConfig.java
│   │   ├── db/                     # 数据库配置
│   │   │   └── MyBatisPlusConfig.java
│   │   ├── security/               # 安全配置
│   │   │   └── SaTokenConfig.java
│   │   └── web/                    # Web配置
│   │       ├── Knife4jConfig.java
│   │       └── WebMvcConfig.java
│   ├── persistence                 # 持久化实现
│   │   ├── article/
│   │   │   ├── ArticleMapper.java
│   │   │   └── ArticleRepositoryImpl.java
│   │   └── ...
│   └── ai                          # AI服务实现
│       └── DashScopeAiService.java
│
└── shared                          # 共享内核
    ├── common                      # 通用工具
    ├── domain                      # 共享领域概念
    │   ├── DomainEvent.java
    │   ├── Identifier.java
    │   └── AbstractDomainEntity.java
    ├── dto                         # 共享DTO
    │   ├── Result.java
    │   └── PageResult.java
    └── exception                   # 异常定义
        └── BusinessException.java
```

## 分层调用规则

| 规则 | 说明 |
|------|------|
| ✅ 允许 | `Controller` → `AppService` → `Repository` |
| ✅ 允许 | `AppService` 调用多个聚合的 `Repository` |
| ✅ 允许 | `RepositoryImpl` 实现 `Repository` 接口 |
| ❌ 禁止 | `Controller` 直接调用 `Repository` |
| ❌ 禁止 | `AppService` 之间互相调用 |
| ❌ 禁止 | 领域层依赖应用层/接口层 |
| ❌ 禁止 | 跨聚合直接操作实体（必须通过聚合根）|

## 配置目录规范

配置类按功能划分到不同子包：

- `config/ai/` - AI相关配置（Spring AI、异步任务）
- `config/cache/` - 缓存配置（Redis、Spring Cache）
- `config/db/` - 数据库配置（MyBatis Plus）
- `config/security/` - 安全配置（Sa-Token）
- `config/web/` - Web配置（CORS、Knife4j）

## 领域事件机制

1. 领域事件定义在 `domain/{aggregate}/event/` 包下
2. 事件处理器定义在 `application/event/` 包下
3. 使用 Spring 的 `@EventListener` 机制
4. 异步处理使用 `@Async("aiTaskExecutor")`

## AI 防腐层

- `domain/ai/AiService` - 领域层定义的接口
- `infrastructure/ai/DashScopeAiService` - 基础设施层实现
- 通过防腐层与外部AI服务解耦，便于后续切换AI提供商
