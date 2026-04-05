# Spring AI 1.1.4 开发指南

> **文档版本**: v1.0  
> **编写日期**: 2025年11月  
> **Spring AI版本**: 1.1.4  
> **适用范围**: AI智能备课助手项目

---

## 目录

1. [版本概述](#一版本概述)
2. [核心API详解](#二核心api详解)
3. [Maven依赖配置](#三maven依赖配置)
4. [PgVector向量存储](#四pgvector向量存储)
5. [ChatClient使用](#五chatclient使用)
6. [EmbeddingModel使用](#六embeddingmodel使用)
7. [与Spring AI 2.0的区别](#七与spring-ai-20的区别)
8. [常见问题与解决方案](#八常见问题与解决方案)

---

## 一、版本概述

### 1.1 Spring AI 1.1.4 简介

Spring AI 1.1.4 是 Spring AI 的稳定版本，发布于2026年3月，包含以下主要改进：

| 特性 | 说明 |
|------|------|
| **新功能** | 1个新特性：动态禁用结构化输出功能 |
| **Bug修复** | 11个bug修复，提升向量存储和模型集成稳定性 |
| **依赖升级** | Google GenAI SDK 1.44.0, OpenAI SDK 4.28.0, Anthropic SDK 2.17.0 |
| **稳定性** | Oracle和PgVector向量存储集成测试稳定性提升 |

### 1.2 核心组件

```
┌─────────────────────────────────────────────────────────────────┐
│                      Spring AI 1.1.4 核心组件                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│   │  ChatModel   │  │EmbeddingModel│  │  VectorStore │         │
│   │              │  │              │  │              │         │
│   │ - OpenAI     │  │ - OpenAI     │  │ - PgVector   │         │
│   │ - Azure      │  │ - Azure      │  │ - Redis      │         │
│   │ - Ollama     │  │ - Ollama     │  │ - Milvus     │         │
│   │ - Anthropic  │  │ - Bedrock    │  │ - Elasticsearch│       │
│   └──────────────┘  └──────────────┘  └──────────────┘         │
│                                                                  │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│   │  ChatClient  │  │  ChatMemory  │  │   Advisors   │         │
│   │              │  │              │  │              │         │
│   │ - Fluent API │  │ - InMemory   │  │ - QuestionAnswer│      │
│   │ - Stream     │  │ - JDBC       │  │ - Memory     │         │
│   │ - Call       │  │ - Cassandra  │  │ - Logger     │         │
│   └──────────────┘  └──────────────┘  └──────────────┘         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 二、核心API详解

### 2.1 SearchRequest API

`SearchRequest` 是向量相似度搜索的请求对象，在1.1.4版本中使用 **Builder模式** 创建。

```java
// 1.1.4 版本 - 使用 Builder 模式
SearchRequest searchRequest = SearchRequest.builder()
    .query("搜索文本")                    // 查询文本
    .topK(5)                            // 返回前5个结果
    .similarityThreshold(0.7)           // 相似度阈值 (0.0-1.0)
    .filterExpression("key == 'value'") // 元数据过滤
    .build();

// 执行搜索
List<Document> results = vectorStore.similaritySearch(searchRequest);
```

**SearchRequest.Builder 方法说明：**

| 方法 | 参数 | 说明 |
|------|------|------|
| `query(String)` | 查询文本 | 用于计算相似度的文本 |
| `topK(int)` | 返回数量 | 返回最相似的K个结果，默认4 |
| `similarityThreshold(double)` | 阈值 | 相似度过滤，0.0表示接受所有，1.0表示精确匹配 |
| `similarityThresholdAll()` | - | 禁用相似度过滤 |
| `filterExpression(String)` | 过滤表达式 | 元数据过滤条件 |

### 2.2 过滤表达式语法

```java
// 基本相等
.filterExpression("country == 'UK'")

// 数值比较
.filterExpression("year >= 2020")

// 逻辑与
.filterExpression("country == 'UK' && year >= 2020")

// 逻辑或
.filterExpression("country == 'UK' || country == 'US'")

// 包含
.filterExpression("author in ['john', 'jill']")

// ISNULL / ISNOTNULL
.filterExpression("optionalField isNotNull()")

// 复杂表达式
.filterExpression("(country == 'UK' || country == 'US') && year >= 2020 && isActive == true")
```

### 2.3 Filter.Expression DSL (程序化构建)

```java
import org.springframework.ai.vectorstore.filter.Filter;
import org.springframework.ai.vectorstore.filter.FilterExpressionBuilder;

FilterExpressionBuilder b = new FilterExpressionBuilder();

// 构建复杂过滤表达式
Filter.Expression expression = b.and(
    b.in("author", "john", "jill"),
    b.eq("article_type", "blog"),
    b.gte("year", 2020)
).build();

SearchRequest request = SearchRequest.builder()
    .query("search text")
    .topK(5)
    .filterExpression(expression)
    .build();
```

---

## 三、Maven依赖配置

### 3.1 完整pom.xml

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 
                             http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    
    <parent>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-parent</artifactId>
        <version>3.3.5</version>
        <relativePath/>
    </parent>
    
    <groupId>com.aiprep</groupId>
    <artifactId>ai-prep</artifactId>
    <version>1.0.0</version>
    <packaging>jar</packaging>
    
    <properties>
        <java.version>21</java.version>
        <!-- Spring AI 1.1.4 -->
        <spring-ai.version>1.1.4</spring-ai.version>
    </properties>
    
    <dependencies>
        <!-- ==================== Spring Boot ==================== -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-web</artifactId>
        </dependency>
        
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-webflux</artifactId>
        </dependency>
        
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-data-jpa</artifactId>
        </dependency>
        
        <!-- ==================== Spring AI ==================== -->
        <!-- OpenAI 模型支持 -->
        <dependency>
            <groupId>org.springframework.ai</groupId>
            <artifactId>spring-ai-openai</artifactId>
        </dependency>
        
        <!-- PgVector 向量存储 (1.1.4版本) -->
        <dependency>
            <groupId>org.springframework.ai</groupId>
            <artifactId>spring-ai-pgvector-store</artifactId>
        </dependency>
        
        <!-- ==================== 数据库 ==================== -->
        <dependency>
            <groupId>org.postgresql</groupId>
            <artifactId>postgresql</artifactId>
            <scope>runtime</scope>
        </dependency>
        
        <!-- 连接池 -->
        <dependency>
            <groupId>com.zaxxer</groupId>
            <artifactId>HikariCP</artifactId>
        </dependency>
        
        <!-- ==================== 工具 ==================== -->
        <dependency>
            <groupId>org.projectlombok</groupId>
            <artifactId>lombok</artifactId>
            <optional>true</optional>
        </dependency>
        
        <!-- JSON处理 -->
        <dependency>
            <groupId>com.fasterxml.jackson.datatype</groupId>
            <artifactId>jackson-datatype-jsr310</artifactId>
        </dependency>
        
        <!-- ==================== 测试 ==================== -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-test</artifactId>
            <scope>test</scope>
        </dependency>
    </dependencies>
    
    <!-- ==================== 依赖管理 ==================== -->
    <dependencyManagement>
        <dependencies>
            <dependency>
                <groupId>org.springframework.ai</groupId>
                <artifactId>spring-ai-bom</artifactId>
                <version>${spring-ai.version}</version>
                <type>pom</type>
                <scope>import</scope>
            </dependency>
        </dependencies>
    </dependencyManagement>
    
    <build>
        <plugins>
            <plugin>
                <groupId>org.springframework.boot</groupId>
                <artifactId>spring-boot-maven-plugin</artifactId>
            </plugin>
        </plugins>
    </build>
</project>
```

### 3.2 关键依赖说明

| 依赖 | 版本(1.1.4) | 说明 |
|------|------------|------|
| `spring-ai-openai` | 1.1.4 | OpenAI模型支持 |
| `spring-ai-pgvector-store` | 1.1.4 | PostgreSQL向量存储 |
| `spring-ai-bom` | 1.1.4 | 依赖版本管理 |

**注意**：1.1.4版本的PgVector依赖名为 `spring-ai-pgvector-store`，而不是 `spring-ai-pgvector-store-spring-boot-starter`。

---

## 四、PgVector向量存储

### 4.1 配置类

```java
import org.springframework.ai.embedding.EmbeddingModel;
import org.springframework.ai.vectorstore.pgvector.PgVectorStore;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.jdbc.core.JdbcTemplate;

import javax.sql.DataSource;

@Configuration
public class PgVectorConfig {
    
    @Value("${spring.ai.vectorstore.pgvector.dimensions:1536}")
    private int dimensions;
    
    @Value("${spring.ai.vectorstore.pgvector.distance-type:cosine_distance}")
    private String distanceType;
    
    /**
     * 配置PgVectorStore (Spring AI 1.1.4版本)
     */
    @Bean
    public PgVectorStore pgVectorStore(
            DataSource dataSource,
            EmbeddingModel embeddingModel) {
        
        JdbcTemplate jdbcTemplate = new JdbcTemplate(dataSource);
        
        // 1.1.4版本使用构造函数创建
        return new PgVectorStore(
            jdbcTemplate,                                    // JdbcTemplate
            embeddingModel,                                  // EmbeddingModel
            dimensions,                                      // 向量维度
            PgVectorStore.PgDistanceType.COSINE_DISTANCE,    // 距离类型
            true,                                            // 初始化Schema
            "vector_store"                                   // 表名
        );
    }
}
```

### 4.2 PgVectorStore构造函数参数

```java
public PgVectorStore(
    JdbcTemplate jdbcTemplate,           // JDBC模板
    EmbeddingModel embeddingModel,       // 嵌入模型
    int dimensions,                      // 向量维度 (默认1536)
    PgDistanceType distanceType,         // 距离类型
    boolean initializeSchema,            // 是否初始化Schema
    String vectorTableName               // 向量表名
)
```

**PgDistanceType 枚举值：**

| 类型 | 说明 | 适用场景 |
|------|------|---------|
| `COSINE_DISTANCE` | 余弦距离 (默认) | 大多数场景 |
| `EUCLIDEAN_DISTANCE` | 欧几里得距离 (L2) | 向量未归一化 |
| `NEGATIVE_INNER_PRODUCT` | 负内积 | 向量已归一化，性能最佳 |

### 4.3 application.yml配置

```yaml
spring:
  # 数据库配置
  datasource:
    url: jdbc:postgresql://localhost:5432/aiprep
    username: aiprep
    password: aiprep123
    driver-class-name: org.postgresql.Driver
    hikari:
      maximum-pool-size: 10
      minimum-idle: 5
      connection-timeout: 30000
  
  # JPA配置
  jpa:
    hibernate:
      ddl-auto: update
    show-sql: false
    properties:
      hibernate:
        dialect: org.hibernate.dialect.PostgreSQLDialect
  
  # PgVector配置 (1.1.4版本)
  ai:
    vectorstore:
      pgvector:
        dimensions: 1536                    # 向量维度
        distance-type: cosine_distance      # 距离类型
        table-name: vector_store            # 表名
        initialize-schema: true             # 自动初始化Schema

# Kimi API配置
ai:
  kimi:
    api-key: ${AI_KIMI_API_KEY}
    base-url: https://api.moonshot.cn/v1
    model: moonshot-v1-32k
```

### 4.4 向量存储使用示例

```java
import org.springframework.ai.document.Document;
import org.springframework.ai.vectorstore.SearchRequest;
import org.springframework.ai.vectorstore.VectorStore;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;

@Service
public class KnowledgeService {
    
    private final VectorStore vectorStore;
    
    public KnowledgeService(VectorStore vectorStore) {
        this.vectorStore = vectorStore;
    }
    
    /**
     * 添加文档到向量库
     */
    public void addDocuments(List<String> contents) {
        List<Document> documents = contents.stream()
            .map(content -> new Document(content, Map.of(
                "source", "教育心理学",
                "type", "theory"
            )))
            .toList();
        
        vectorStore.add(documents);
    }
    
    /**
     * 相似度搜索 (1.1.4版本 - Builder模式)
     */
    public List<Document> search(String query, int topK) {
        SearchRequest request = SearchRequest.builder()
            .query(query)
            .topK(topK)
            .similarityThreshold(0.7)
            .build();
        
        return vectorStore.similaritySearch(request);
    }
    
    /**
     * 带过滤条件的搜索
     */
    public List<Document> searchWithFilter(String query, String source) {
        SearchRequest request = SearchRequest.builder()
            .query(query)
            .topK(3)
            .similarityThreshold(0.7)
            .filterExpression("source == '" + source + "'")
            .build();
        
        return vectorStore.similaritySearch(request);
    }
}
```

---

## 五、ChatClient使用

### 5.1 配置类

```java
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.model.ChatModel;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class ChatClientConfig {
    
    /**
     * 配置ChatClient
     */
    @Bean
    public ChatClient chatClient(ChatModel chatModel) {
        return ChatClient.builder(chatModel)
            // 默认系统提示词
            .defaultSystem("你是一位资深的教学设计专家，精通教育心理学理论。")
            // 默认选项
            .defaultOptions(
                OpenAiChatOptions.builder()
                    .withTemperature(0.7)
                    .withMaxTokens(2000)
                    .build()
            )
            .build();
    }
}
```

### 5.2 同步调用

```java
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.stereotype.Service;

@Service
public class LessonService {
    
    private final ChatClient chatClient;
    
    public LessonService(ChatClient chatClient) {
        this.chatClient = chatClient;
    }
    
    /**
     * 同步生成教案
     */
    public String generateLesson(String topic) {
        return chatClient.prompt()
            .user("请为课题【" + topic + "】设计一份教案")
            .call()                    // 同步调用
            .content();                // 获取文本内容
    }
    
    /**
     * 带系统提示词的调用
     */
    public String generateWithSystem(String systemPrompt, String userPrompt) {
        return chatClient.prompt()
            .system(systemPrompt)
            .user(userPrompt)
            .call()
            .content();
    }
}
```

### 5.3 流式调用 (SSE)

```java
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.model.ChatResponse;
import org.springframework.stereotype.Service;
import reactor.core.publisher.Flux;

@Service
public class StreamingService {
    
    private final ChatClient chatClient;
    
    public StreamingService(ChatClient chatClient) {
        this.chatClient = chatClient;
    }
    
    /**
     * 流式生成 (返回Flux)
     */
    public Flux<String> streamLesson(String topic) {
        return chatClient.prompt()
            .user("请为课题【" + topic + "】设计一份教案")
            .stream()                  // 流式调用
            .content();                // 获取内容流
    }
    
    /**
     * 流式生成 (返回完整ChatResponse)
     */
    public Flux<ChatResponse> streamWithResponse(String topic) {
        return chatClient.prompt()
            .user("请为课题【" + topic + "】设计一份教案")
            .stream()
            .chatResponse();           // 获取完整响应流
    }
}
```

### 5.4 控制器中使用SSE

```java
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;
import reactor.core.publisher.Flux;

import java.io.IOException;
import java.time.Duration;

@RestController
@RequestMapping("/api/lesson")
public class LessonController {
    
    private final ChatClient chatClient;
    
    public LessonController(ChatClient chatClient) {
        this.chatClient = chatClient;
    }
    
    /**
     * 流式生成教案 (SSE)
     */
    @PostMapping(value = "/generate", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter generateLesson(@RequestBody LessonReq req) {
        SseEmitter emitter = new SseEmitter(180_000L); // 3分钟超时
        
        Flux<String> flux = chatClient.prompt()
            .user(buildPrompt(req))
            .stream()
            .content();
        
        flux.subscribe(
            content -> {
                try {
                    emitter.send(content);
                } catch (IOException e) {
                    emitter.completeWithError(e);
                }
            },
            emitter::completeWithError,
            emitter::complete
        );
        
        return emitter;
    }
    
    /**
     * 流式生成 (直接返回Flux)
     */
    @PostMapping(value = "/generate-flux", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public Flux<String> generateLessonFlux(@RequestBody LessonReq req) {
        return chatClient.prompt()
            .user(buildPrompt(req))
            .stream()
            .content()
            .delayElements(Duration.ofMillis(50)); // 控制流速
    }
    
    private String buildPrompt(LessonReq req) {
        return String.format("""
            请为 %s 年级的【%s】课题设计一份 %d 分钟的教案。
            学科: %s
            教学风格: %s
            """,
            req.getGrade(),
            req.getTopic(),
            req.getDuration(),
            req.getSubject(),
            req.getStyle()
        );
    }
}
```

---

## 六、EmbeddingModel使用

### 6.1 配置类

```java
import org.springframework.ai.embedding.EmbeddingModel;
import org.springframework.ai.openai.OpenAiEmbeddingModel;
import org.springframework.ai.openai.api.OpenAiApi;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class EmbeddingConfig {
    
    @Value("${ai.kimi.api-key}")
    private String apiKey;
    
    @Value("${ai.kimi.base-url:https://api.moonshot.cn/v1}")
    private String baseUrl;
    
    /**
     * 配置EmbeddingModel (Kimi/OpenAI兼容)
     */
    @Bean
    public EmbeddingModel embeddingModel() {
        OpenAiApi api = OpenAiApi.builder()
            .apiKey(apiKey)
            .baseUrl(baseUrl)
            .build();
        
        return new OpenAiEmbeddingModel(api);
    }
}
```

### 6.2 使用示例

```java
import org.springframework.ai.document.Document;
import org.springframework.ai.embedding.EmbeddingModel;
import org.springframework.ai.embedding.EmbeddingResponse;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class EmbeddingService {
    
    private final EmbeddingModel embeddingModel;
    
    public EmbeddingService(EmbeddingModel embeddingModel) {
        this.embeddingModel = embeddingModel;
    }
    
    /**
     * 嵌入单个文本
     */
    public List<Double> embed(String text) {
        EmbeddingResponse response = embeddingModel.embedForResponse(List.of(text));
        return response.getResults().get(0).getOutput();
    }
    
    /**
     * 批量嵌入
     */
    public List<List<Double>> embedBatch(List<String> texts) {
        EmbeddingResponse response = embeddingModel.embedForResponse(texts);
        return response.getResults().stream()
            .map(result -> result.getOutput())
            .toList();
    }
    
    /**
     * 获取嵌入维度
     */
    public int getDimensions() {
        return embeddingModel.dimensions();
    }
}
```

---

## 七、与Spring AI 2.0的区别

### 7.1 API变化对比

| 功能 | 1.1.4版本 | 2.0版本 |
|------|----------|---------|
| **SearchRequest** | `SearchRequest.builder().query().topK().build()` | `SearchRequest.query().withTopK()` |
| **PgVectorStore** | `new PgVectorStore(jdbc, model, dims, type, init, table)` | `PgVectorStore.builder().dimensions().build()` |
| **依赖名称** | `spring-ai-pgvector-store` | `spring-ai-pgvector-store-spring-boot-starter` |
| **配置前缀** | `spring.ai.vectorstore.pgvector` | `spring.ai.vectorstore.pgvector` |
| **相似度阈值** | `.similarityThreshold(0.7)` | `.withSimilarityThreshold(0.7)` |

### 7.2 代码对比

#### SearchRequest 创建方式

```java
// Spring AI 1.1.4
SearchRequest request = SearchRequest.builder()
    .query("搜索文本")
    .topK(5)
    .similarityThreshold(0.7)
    .build();

// Spring AI 2.0
SearchRequest request = SearchRequest.query("搜索文本")
    .withTopK(5)
    .withSimilarityThreshold(0.7);
```

#### PgVectorStore 创建方式

```java
// Spring AI 1.1.4
@Bean
public PgVectorStore pgVectorStore(DataSource ds, EmbeddingModel em) {
    return new PgVectorStore(
        new JdbcTemplate(ds),
        em,
        1536,
        PgVectorStore.PgDistanceType.COSINE_DISTANCE,
        true,
        "vector_store"
    );
}

// Spring AI 2.0
@Bean
public PgVectorStore pgVectorStore(DataSource ds, EmbeddingModel em) {
    return PgVectorStore.builder(new JdbcTemplate(ds), em)
        .dimensions(1536)
        .distanceType(PgDistanceType.COSINE_DISTANCE)
        .initializeSchema(true)
        .vectorTableName("vector_store")
        .build();
}
```

### 7.3 依赖变化

```xml
<!-- Spring AI 1.1.4 -->
<dependency>
    <groupId>org.springframework.ai</groupId>
    <artifactId>spring-ai-pgvector-store</artifactId>
</dependency>

<!-- Spring AI 2.0 -->
<dependency>
    <groupId>org.springframework.ai</groupId>
    <artifactId>spring-ai-pgvector-store-spring-boot-starter</artifactId>
</dependency>
```

### 7.4 选择建议

| 场景 | 推荐版本 | 理由 |
|------|---------|------|
| **比赛项目** | 1.1.4 | 稳定版本，文档完善 |
| **生产环境** | 1.1.4 | 经过充分测试，bug少 |
| **新功能尝试** | 2.0 | 新特性多，但可能有bug |
| **长期维护** | 2.0 | 未来主流版本 |

---

## 八、常见问题与解决方案

### 8.1 PgVectorStore初始化失败

**问题**：`PgVectorStore` 初始化时报错，提示表不存在。

**解决方案**：
```java
// 确保 initializeSchema = true
@Bean
public PgVectorStore pgVectorStore(DataSource ds, EmbeddingModel em) {
    return new PgVectorStore(
        new JdbcTemplate(ds),
        em,
        1536,
        PgVectorStore.PgDistanceType.COSINE_DISTANCE,
        true,  // 必须设置为true
        "vector_store"
    );
}
```

### 8.2 向量检索返回空结果

**问题**：`similaritySearch` 返回空列表。

**排查步骤**：
1. 检查向量库中是否有数据
2. 检查相似度阈值是否设置过高
3. 检查查询文本是否正确

```java
// 调试代码
List<Document> allDocs = vectorStore.similaritySearch(
    SearchRequest.builder()
        .query("test")
        .topK(100)
        .similarityThresholdAll()  // 禁用阈值过滤
        .build()
);
System.out.println("总文档数: " + allDocs.size());
```

### 8.3 流式输出乱码

**问题**：SSE流式输出中文乱码。

**解决方案**：
```java
@GetMapping(value = "/stream", produces = "text/html;charset=utf-8")
// 或
@GetMapping(value = "/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
public Flux<String> stream() {
    return chatClient.prompt()
        .user("你好")
        .stream()
        .content()
        .map(content -> new String(content.getBytes(StandardCharsets.UTF_8), StandardCharsets.UTF_8));
}
```

### 8.4 依赖冲突

**问题**：`NoSuchMethodError` 或 `ClassNotFoundException`。

**解决方案**：
```xml
<!-- 确保使用BOM管理版本 -->
<dependencyManagement>
    <dependencies>
        <dependency>
            <groupId>org.springframework.ai</groupId>
            <artifactId>spring-ai-bom</artifactId>
            <version>1.1.4</version>
            <type>pom</type>
            <scope>import</scope>
        </dependency>
    </dependencies>
</dependencyManagement>
```

### 8.5 配置参数参考

| 参数 | 1.1.4版本 | 说明 |
|------|----------|------|
| `spring.ai.vectorstore.pgvector.dimensions` | ✅ | 向量维度 |
| `spring.ai.vectorstore.pgvector.distance-type` | ✅ | 距离类型 |
| `spring.ai.vectorstore.pgvector.table-name` | ✅ | 表名 |
| `spring.ai.vectorstore.pgvector.initialize-schema` | ✅ | 初始化Schema |
| `spring.ai.vectorstore.pgvector.index-type` | ❌ | 2.0新增 |
| `spring.ai.vectorstore.pgvector.schema-name` | ❌ | 2.0新增 |

---

## 附录：完整示例代码

### RAG增强教案生成

```java
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.document.Document;
import org.springframework.ai.vectorstore.SearchRequest;
import org.springframework.ai.vectorstore.VectorStore;
import org.springframework.stereotype.Service;
import reactor.core.publisher.Flux;

import java.util.List;
import java.util.stream.Collectors;

@Service
public class RAGLessonService {
    
    private final ChatClient chatClient;
    private final VectorStore vectorStore;
    
    public RAGLessonService(ChatClient chatClient, VectorStore vectorStore) {
        this.chatClient = chatClient;
        this.vectorStore = vectorStore;
    }
    
    /**
     * RAG增强的流式教案生成
     */
    public Flux<String> generateLessonWithRAG(String topic, String subject, String grade) {
        // 1. 检索相关知识
        String query = topic + " " + subject + " 教学设计";
        SearchRequest request = SearchRequest.builder()
            .query(query)
            .topK(3)
            .similarityThreshold(0.7)
            .build();
        
        List<Document> knowledge = vectorStore.similaritySearch(request);
        
        // 2. 构建带知识的Prompt
        String knowledgeText = knowledge.stream()
            .map(doc -> "【参考】" + doc.getContent())
            .collect(Collectors.joining("\n\n"));
        
        String prompt = String.format("""
            请为 %s 年级的【%s】课题设计一份教案。
            
            参考教育理论:
            %s
            
            请基于上述理论设计教案，并在设计意图中说明理论依据。
            """, grade, topic, knowledgeText);
        
        // 3. 流式生成
        return chatClient.prompt()
            .system("你是一位资深的教学设计专家，精通教育心理学理论。")
            .user(prompt)
            .stream()
            .content();
    }
}
```

---

**文档版本**: v1.0  
**Spring AI版本**: 1.1.4  
**最后更新**: 2025年11月
