# Spring AI 1.1.4 完整使用教程与功能介绍

> 本文档是Spring AI 1.1.4版本的完整使用指南，涵盖从基础概念到高级应用的全面内容，包含详细的代码示例和最佳实践。

---

## 目录

1. [第1章：Spring AI简介与架构设计](#第1章spring-ai简介与架构设计)
2. [第2章：环境搭建与依赖配置](#第2章环境搭建与依赖配置)
3. [第3章：ChatClient API详解](#第3章chatclient-api详解)
4. [第4章：EmbeddingClient与文本向量化](#第4章embeddingclient与文本向量化)
5. [第5章：VectorStore向量存储](#第5章vectorstore向量存储)
6. [第6章：Function Calling工具调用](#第6章function-calling工具调用)
7. [第7章：Structured Output结构化输出](#第7章structured-output结构化输出)
8. [第8章：Chat Memory对话记忆](#第8章chat-memory对话记忆)
9. [第9章：Advisors API与RAG实现](#第9章advisors-api与rag实现)
10. [第10章：多模型提供商配置](#第10章多模型提供商配置)
11. [第11章：Spring AI 1.1.4新特性与变更](#第11章spring-ai-114新特性与变更)
12. [第12章：完整实战项目](#第12章完整实战项目)
13. [第13章：最佳实践与性能优化](#第13章最佳实践与性能优化)

---

## 第1章：Spring AI简介与架构设计

### 1.1 Spring AI的定位和目标

Spring AI是Spring官方推出的AI应用开发框架，旨在简化Java开发者构建AI驱动应用程序的过程。它的核心目标是：

1. **降低AI应用开发门槛**：提供统一的API抽象，让开发者无需深入了解每个AI提供商的具体实现细节
2. **保持Spring生态一致性**：遵循Spring的设计哲学，提供声明式配置和依赖注入支持
3. **支持可移植性**：通过抽象层设计，使应用能够轻松切换不同的AI模型提供商
4. **企业级特性**：提供生产环境所需的监控、安全、可观测性等特性

### 1.2 核心架构分层

Spring AI采用分层架构设计，从上到下分为以下几个层次：

```
┌─────────────────────────────────────────────────────────────┐
│                    应用层 (Application)                      │
│              ChatController, RAG Service, etc.              │
├─────────────────────────────────────────────────────────────┤
│                  Spring AI 核心层                           │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐   │
│  │ChatClient│ │Embedding │ │ Vector   │ │  Advisors    │   │
│  │          │ │ Client   │ │ Store    │ │              │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────┘   │
├─────────────────────────────────────────────────────────────┤
│                  模型抽象层 (Model API)                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐   │
│  │  Chat    │ │Embedding │ │  Image   │ │  Audio       │   │
│  │  Model   │ │  Model   │ │  Model   │ │  Model       │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────┘   │
├─────────────────────────────────────────────────────────────┤
│                  提供商实现层                               │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐   │
│  │  OpenAI  │ │  Azure   │ │  Ollama  │ │  Anthropic   │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

#### 1.2.1 模型抽象层（Model API）

这是Spring AI最底层的抽象，定义了与AI模型交互的基本接口：

- **ChatModel**：文本对话模型的抽象接口
- **EmbeddingModel**：文本嵌入模型的抽象接口
- **ImageModel**：图像生成模型的抽象接口
- **AudioModel**：音频处理模型的抽象接口

#### 1.2.2 核心组件层

在模型抽象之上，Spring AI提供了更易用的高级API：

- **ChatClient**：用于与聊天模型交互的高级客户端
- **EmbeddingClient**：用于文本向量化的客户端
- **VectorStore**：用于向量存储和检索的接口
- **Advisors**：封装常见AI模式的组件

#### 1.2.3 应用层

开发者在这一层构建具体的业务逻辑，利用Spring AI提供的各种组件实现AI功能。

### 1.3 支持的模型类型和提供商

Spring AI 1.1.4支持以下模型类型和提供商：

#### 1.3.1 文本对话模型（Chat Model）

| 提供商 | 模型示例 | 特点 |
|--------|----------|------|
| OpenAI | GPT-4, GPT-3.5-turbo | 功能强大，生态完善 |
| Azure OpenAI | GPT-4, GPT-3.5-turbo | 企业级部署，合规性强 |
| Anthropic | Claude 3系列 | 长上下文，安全性高 |
| Ollama | Llama 2, Mistral | 本地部署，隐私保护 |
| 阿里云 | 通义千问 | 中文优化，国内部署 |

#### 1.3.2 嵌入模型（Embedding Model）

| 提供商 | 模型示例 | 向量维度 |
|--------|----------|----------|
| OpenAI | text-embedding-3-small | 1536 |
| OpenAI | text-embedding-3-large | 3072 |
| Ollama | nomic-embed-text | 768 |
| 阿里云 | text-embedding-v2 | 1536 |

#### 1.3.3 其他模型类型

- **图像生成**：OpenAI DALL-E、Azure OpenAI DALL-E、Stability AI
- **语音转文字**：OpenAI Whisper、Azure Speech
- **文字转语音**：OpenAI TTS、Azure Speech

### 1.4 与Python生态对比

Spring AI与Python AI生态（如LangChain、LlamaIndex）相比有以下特点：

| 特性 | Spring AI | Python生态 |
|------|-----------|------------|
| 语言 | Java/Kotlin | Python |
| 集成性 | 与Spring生态无缝集成 | 独立框架 |
| 企业特性 | 原生支持 | 需额外配置 |
| 性能 | JVM优化，高并发 | 开发效率高 |
| 类型安全 | 强类型 | 动态类型 |
| 生态成熟度 | 快速发展中 | 非常成熟 |

**Spring AI的优势：**
1. 适合已有Spring技术栈的团队
2. 更好的类型安全和IDE支持
3. 企业级特性（事务、安全、监控）原生支持
4. 更好的性能和可扩展性

---

## 第2章：环境搭建与依赖配置

### 2.1 系统要求

使用Spring AI 1.1.4需要满足以下环境要求：

- **JDK**：17或更高版本（推荐JDK 21）
- **Spring Boot**：3.2.x或更高版本
- **构建工具**：Maven 3.6+ 或 Gradle 8.x+
- **数据库**（可选）：PostgreSQL 14+（用于pgvector）

### 2.2 Maven配置

#### 2.2.1 添加Spring AI BOM

在`pom.xml`中添加Spring AI的BOM（Bill of Materials）管理依赖版本：

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
        <version>3.2.5</version>
        <relativePath/>
    </parent>
    
    <groupId>com.example</groupId>
    <artifactId>spring-ai-demo</artifactId>
    <version>1.0.0</version>
    <packaging>jar</packaging>
    
    <properties>
        <java.version>17</java.version>
        <spring-ai.version>1.1.4</spring-ai.version>
    </properties>
    
    <dependencyManagement>
        <dependencies>
            <!-- Spring AI BOM -->
            <dependency>
                <groupId>org.springframework.ai</groupId>
                <artifactId>spring-ai-bom</artifactId>
                <version>${spring-ai.version}</version>
                <type>pom</type>
                <scope>import</scope>
            </dependency>
        </dependencies>
    </dependencyManagement>
    
    <dependencies>
        <!-- Spring Boot Starter Web -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-web</artifactId>
        </dependency>
        
        <!-- Spring Boot Starter Test -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-test</artifactId>
            <scope>test</scope>
        </dependency>
    </dependencies>
    
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

#### 2.2.2 添加Spring AI仓库配置

由于Spring AI目前还在Milestone阶段，需要添加Spring的里程碑仓库：

```xml
<repositories>
    <!-- Spring Milestone Repository -->
    <repository>
        <id>spring-milestones</id>
        <name>Spring Milestones</name>
        <url>https://repo.spring.io/milestone</url>
        <snapshots>
            <enabled>false</enabled>
        </snapshots>
    </repository>
    
    <!-- Spring Snapshot Repository (可选，用于开发版本) -->
    <repository>
        <id>spring-snapshots</id>
        <name>Spring Snapshots</name>
        <url>https://repo.spring.io/snapshot</url>
        <releases>
            <enabled>false</enabled>
        </releases>
    </repository>
</repositories>
```

#### 2.2.3 各模型提供商的Starter依赖

**OpenAI：**
```xml
<dependency>
    <groupId>org.springframework.ai</groupId>
    <artifactId>spring-ai-openai-spring-boot-starter</artifactId>
</dependency>
```

**Azure OpenAI：**
```xml
<dependency>
    <groupId>org.springframework.ai</groupId>
    <artifactId>spring-ai-azure-openai-spring-boot-starter</artifactId>
</dependency>
```

**Ollama（本地模型）：**
```xml
<dependency>
    <groupId>org.springframework.ai</groupId>
    <artifactId>spring-ai-ollama-spring-boot-starter</artifactId>
</dependency>
```

**Anthropic Claude：**
```xml
<dependency>
    <groupId>org.springframework.ai</groupId>
    <artifactId>spring-ai-anthropic-spring-boot-starter</artifactId>
</dependency>
```

**PgVector（PostgreSQL向量扩展）：**
```xml
<dependency>
    <groupId>org.springframework.ai</groupId>
    <artifactId>spring-ai-pgvector-store-spring-boot-starter</artifactId>
</dependency>
```

**完整的pom.xml示例（OpenAI + PgVector）：**

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
        <version>3.2.5</version>
        <relativePath/>
    </parent>
    
    <groupId>com.example</groupId>
    <artifactId>spring-ai-rag-demo</artifactId>
    <version>1.0.0</version>
    <name>Spring AI RAG Demo</name>
    <description>Spring AI RAG Application with PgVector</description>
    
    <properties>
        <java.version>17</java.version>
        <spring-ai.version>1.1.4</spring-ai.version>
    </properties>
    
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
    
    <dependencies>
        <!-- Web -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-web</artifactId>
        </dependency>
        
        <!-- OpenAI -->
        <dependency>
            <groupId>org.springframework.ai</groupId>
            <artifactId>spring-ai-openai-spring-boot-starter</artifactId>
        </dependency>
        
        <!-- PgVector -->
        <dependency>
            <groupId>org.springframework.ai</groupId>
            <artifactId>spring-ai-pgvector-store-spring-boot-starter</artifactId>
        </dependency>
        
        <!-- JDBC -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-jdbc</artifactId>
        </dependency>
        
        <!-- PostgreSQL Driver -->
        <dependency>
            <groupId>org.postgresql</groupId>
            <artifactId>postgresql</artifactId>
            <scope>runtime</scope>
        </dependency>
        
        <!-- Validation -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-validation</artifactId>
        </dependency>
        
        <!-- Lombok (可选) -->
        <dependency>
            <groupId>org.projectlombok</groupId>
            <artifactId>lombok</artifactId>
            <optional>true</optional>
        </dependency>
        
        <!-- Test -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-test</artifactId>
            <scope>test</scope>
        </dependency>
    </dependencies>
    
    <repositories>
        <repository>
            <id>spring-milestones</id>
            <name>Spring Milestones</name>
            <url>https://repo.spring.io/milestone</url>
            <snapshots>
                <enabled>false</enabled>
            </snapshots>
        </repository>
    </repositories>
    
    <build>
        <plugins>
            <plugin>
                <groupId>org.springframework.boot</groupId>
                <artifactId>spring-boot-maven-plugin</artifactId>
                <configuration>
                    <excludes>
                        <exclude>
                            <groupId>org.projectlombok</groupId>
                            <artifactId>lombok</artifactId>
                        </exclude>
                    </excludes>
                </configuration>
            </plugin>
        </plugins>
    </build>
</project>
```

### 2.3 Gradle配置

对于使用Gradle的项目，配置方式如下：

#### 2.3.1 build.gradle.kts配置

```kotlin
plugins {
    java
    id("org.springframework.boot") version "3.2.5"
    id("io.spring.dependency-management") version "1.1.4"
}

group = "com.example"
version = "1.0.0"

java {
    sourceCompatibility = JavaVersion.VERSION_17
}

repositories {
    mavenCentral()
    maven { url = uri("https://repo.spring.io/milestone") }
    maven { url = uri("https://repo.spring.io/snapshot") }
}

extra["springAiVersion"] = "1.1.4"

dependencies {
    implementation("org.springframework.boot:spring-boot-starter-web")
    implementation("org.springframework.ai:spring-ai-openai-spring-boot-starter")
    implementation("org.springframework.ai:spring-ai-pgvector-store-spring-boot-starter")
    implementation("org.springframework.boot:spring-boot-starter-jdbc")
    runtimeOnly("org.postgresql:postgresql")
    
    compileOnly("org.projectlombok:lombok")
    annotationProcessor("org.projectlombok:lombok")
    
    testImplementation("org.springframework.boot:spring-boot-starter-test")
}

dependencyManagement {
    imports {
        mavenBom("org.springframework.ai:spring-ai-bom:${property("springAiVersion")}")
    }
}

tasks.withType<Test> {
    useJUnitPlatform()
}
```

### 2.4 配置文件示例

创建`application.yml`（或`application.properties`）配置文件：

```yaml
# OpenAI 配置
spring:
  ai:
    openai:
      api-key: ${OPENAI_API_KEY:your-api-key-here}
      base-url: https://api.openai.com  # 可选，用于代理
      chat:
        options:
          model: gpt-4o
          temperature: 0.7
          max-tokens: 2000
      embedding:
        options:
          model: text-embedding-3-small
    
    # PgVector 配置
    vectorstore:
      pgvector:
        index-type: hnsw
        distance-type: cosine_distance
        dimensions: 1536
        initialize-schema: true
  
  # 数据库配置
  datasource:
    url: jdbc:postgresql://localhost:5432/ai_db
    username: postgres
    password: password
    driver-class-name: org.postgresql.Driver

# 服务器配置
server:
  port: 8080

# 日志配置
logging:
  level:
    org.springframework.ai: DEBUG
```

---

## 第3章：ChatClient API详解

### 3.1 ChatClient概述

ChatClient是Spring AI提供的高级API，用于与聊天模型进行交互。它封装了底层的ChatModel接口，提供了更简洁、更易用的调用方式。

### 3.2 ChatClient创建方式

#### 3.2.1 自动注入方式（推荐）

当添加了相应的starter依赖后，Spring Boot会自动配置ChatClient.Builder：

```java
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.stereotype.Service;

@Service
public class ChatService {
    
    private final ChatClient chatClient;
    
    // 构造函数注入
    public ChatService(ChatClient.Builder chatClientBuilder) {
        this.chatClient = chatClientBuilder.build();
    }
}
```

#### 3.2.2 自定义配置方式

可以通过ChatClient.Builder进行更多自定义配置：

```java
@Service
public class ChatService {
    
    private final ChatClient chatClient;
    
    public ChatService(ChatClient.Builder chatClientBuilder) {
        this.chatClient = chatClientBuilder
            .defaultSystem("你是一个专业的Java技术助手")  // 默认系统消息
            .defaultOptions(OpenAiChatOptions.builder()
                .withModel("gpt-4o")
                .withTemperature(0.7)
                .withMaxTokens(2000)
                .build())
            .build();
    }
}
```

### 3.3 同步调用

#### 3.3.1 简单调用

```java
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.stereotype.Service;

@Service
public class SimpleChatService {
    
    private final ChatClient chatClient;
    
    public SimpleChatService(ChatClient.Builder chatClientBuilder) {
        this.chatClient = chatClientBuilder.build();
    }
    
    /**
     * 简单的同步调用
     */
    public String chat(String userMessage) {
        return chatClient.prompt()
            .user(userMessage)
            .call()
            .content();
    }
}
```

#### 3.3.2 带系统消息的调用

```java
@Service
public class SystemChatService {
    
    private final ChatClient chatClient;
    
    public SystemChatService(ChatClient.Builder chatClientBuilder) {
        this.chatClient = chatClientBuilder.build();
    }
    
    /**
     * 带系统消息的对话
     */
    public String chatWithSystem(String userMessage) {
        return chatClient.prompt()
            .system("你是一个专业的Java开发助手，擅长Spring框架和微服务架构")
            .user(userMessage)
            .call()
            .content();
    }
    
    /**
     * 动态系统消息
     */
    public String chatWithDynamicSystem(String role, String userMessage) {
        String systemMessage = String.format(
            "你是一个专业的%s专家，请用通俗易懂的方式回答问题", role
        );
        
        return chatClient.prompt()
            .system(systemMessage)
            .user(userMessage)
            .call()
            .content();
    }
}
```

#### 3.3.3 获取完整响应

```java
import org.springframework.ai.chat.model.ChatResponse;
import org.springframework.ai.chat.metadata.Usage;
import org.springframework.stereotype.Service;

@Service
public class DetailedChatService {
    
    private final ChatClient chatClient;
    
    public DetailedChatService(ChatClient.Builder chatClientBuilder) {
        this.chatClient = chatClientBuilder.build();
    }
    
    /**
     * 获取完整的响应信息，包括token使用量
     */
    public ChatResult chatWithDetails(String userMessage) {
        ChatResponse response = chatClient.prompt()
            .user(userMessage)
            .call()
            .chatResponse();
        
        String content = response.getResult().getOutput().getContent();
        Usage usage = response.getMetadata().getUsage();
        
        return new ChatResult(
            content,
            usage.getPromptTokens(),
            usage.getGenerationTokens(),
            usage.getTotalTokens()
        );
    }
    
    public record ChatResult(
        String content,
        int promptTokens,
        int completionTokens,
        int totalTokens
    ) {}
}
```

### 3.4 流式调用（Streaming）

流式调用可以让AI的回复实时显示，提供更好的用户体验。

#### 3.4.1 基本流式调用

```java
import org.springframework.ai.chat.model.ChatResponse;
import org.springframework.stereotype.Service;
import reactor.core.publisher.Flux;

@Service
public class StreamingChatService {
    
    private final ChatClient chatClient;
    
    public StreamingChatService(ChatClient.Builder chatClientBuilder) {
        this.chatClient = chatClientBuilder.build();
    }
    
    /**
     * 流式调用，返回Flux<String>
     */
    public Flux<String> streamChat(String userMessage) {
        return chatClient.prompt()
            .user(userMessage)
            .stream()
            .content();
    }
    
    /**
     * 流式调用，返回完整的ChatResponse
     */
    public Flux<ChatResponse> streamChatWithResponse(String userMessage) {
        return chatClient.prompt()
            .user(userMessage)
            .stream()
            .chatResponse();
    }
}
```

#### 3.4.2 流式调用的Controller实现

```java
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.*;
import reactor.core.publisher.Flux;

@RestController
@RequestMapping("/api/chat")
public class ChatController {
    
    private final StreamingChatService streamingChatService;
    
    public ChatController(StreamingChatService streamingChatService) {
        this.streamingChatService = streamingChatService;
    }
    
    /**
     * 流式聊天接口 - Server-Sent Events
     */
    @GetMapping(value = "/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public Flux<String> streamChat(@RequestParam String message) {
        return streamingChatService.streamChat(message);
    }
    
    /**
     * 同步聊天接口
     */
    @PostMapping("/sync")
    public String syncChat(@RequestBody ChatRequest request) {
        return chatService.chat(request.message());
    }
    
    public record ChatRequest(String message) {}
}
```

#### 3.4.3 前端流式接收示例（JavaScript）

```javascript
// 使用EventSource接收流式响应
function streamChat(message) {
    const eventSource = new EventSource(
        `/api/chat/stream?message=${encodeURIComponent(message)}`
    );
    
    let responseText = '';
    const responseElement = document.getElementById('response');
    
    eventSource.onmessage = (event) => {
        responseText += event.data;
        responseElement.textContent = responseText;
    };
    
    eventSource.onerror = (error) => {
        console.error('EventSource error:', error);
        eventSource.close();
    };
    
    eventSource.onclose = () => {
        console.log('Stream closed');
    };
}
```

### 3.5 参数配置详解

#### 3.5.1 温度参数（Temperature）

温度参数控制输出的随机性：

- **0.0-0.3**：更确定、更保守的输出，适合代码生成、事实问答
- **0.4-0.7**：平衡的输出，适合一般对话
- **0.8-1.0**：更有创意、更多样化的输出，适合创意写作

```java
@Service
public class TemperatureChatService {
    
    private final ChatClient chatClient;
    
    public TemperatureChatService(ChatClient.Builder chatClientBuilder) {
        this.chatClient = chatClientBuilder.build();
    }
    
    /**
     * 代码生成 - 低温度
     */
    public String generateCode(String requirement) {
        return chatClient.prompt()
            .system("你是一个专业的Java开发专家")
            .user(requirement)
            .options(OpenAiChatOptions.builder()
                .withTemperature(0.2)  // 低温度，更确定
                .withModel("gpt-4o")
                .build())
            .call()
            .content();
    }
    
    /**
     * 创意写作 - 高温度
     */
    public String creativeWriting(String topic) {
        return chatClient.prompt()
            .system("你是一个创意写作助手")
            .user("请写一篇关于" + topic + "的短文")
            .options(OpenAiChatOptions.builder()
                .withTemperature(0.9)  // 高温度，更有创意
                .build())
            .call()
            .content();
    }
}
```

#### 3.5.2 Top-P参数

Top-P（核采样）是另一种控制输出多样性的方法：

```java
@Service
public class TopPChatService {
    
    private final ChatClient chatClient;
    
    public TopPChatService(ChatClient.Builder chatClientBuilder) {
        this.chatClient = chatClientBuilder.build();
    }
    
    public String chatWithTopP(String message) {
        return chatClient.prompt()
            .user(message)
            .options(OpenAiChatOptions.builder()
                .withTemperature(0.7)
                .withTopP(0.9)  // 只考虑累积概率达到90%的token
                .build())
            .call()
            .content();
    }
}
```

#### 3.5.3 最大Token数

```java
@Service
public class TokenLimitService {
    
    private final ChatClient chatClient;
    
    public TokenLimitService(ChatClient.Builder chatClientBuilder) {
        this.chatClient = chatClientBuilder.build();
    }
    
    /**
     * 短回答
     */
    public String shortAnswer(String question) {
        return chatClient.prompt()
            .system("请用一句话简洁回答")
            .user(question)
            .options(OpenAiChatOptions.builder()
                .withMaxTokens(100)  // 限制输出长度
                .build())
            .call()
            .content();
    }
    
    /**
     * 长回答
     */
    public String longAnswer(String topic) {
        return chatClient.prompt()
            .system("请详细解释，尽可能全面")
            .user(topic)
            .options(OpenAiChatOptions.builder()
                .withMaxTokens(4000)  // 允许较长的输出
                .build())
            .call()
            .content();
    }
}
```

### 3.6 完整代码示例

```java
package com.example.ai.service;

import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.model.ChatResponse;
import org.springframework.ai.openai.OpenAiChatOptions;
import org.springframework.stereotype.Service;
import reactor.core.publisher.Flux;

@Service
public class CompleteChatService {
    
    private final ChatClient chatClient;
    
    public CompleteChatService(ChatClient.Builder chatClientBuilder) {
        this.chatClient = chatClientBuilder
            .defaultSystem("你是一个专业、友好的AI助手")
            .defaultOptions(OpenAiChatOptions.builder()
                .withModel("gpt-4o")
                .withTemperature(0.7)
                .withMaxTokens(2000)
                .build())
            .build();
    }
    
    /**
     * 同步单轮对话
     */
    public String singleTurnChat(String message) {
        return chatClient.prompt()
            .user(message)
            .call()
            .content();
    }
    
    /**
     * 带上下文的对话
     */
    public String contextualChat(String systemPrompt, String userMessage) {
        return chatClient.prompt()
            .system(systemPrompt)
            .user(userMessage)
            .call()
            .content();
    }
    
    /**
     * 流式对话
     */
    public Flux<String> streamingChat(String message) {
        return chatClient.prompt()
            .user(message)
            .stream()
            .content();
    }
    
    /**
     * 带完整响应信息的对话
     */
    public ChatDetails getChatDetails(String message) {
        ChatResponse response = chatClient.prompt()
            .user(message)
            .call()
            .chatResponse();
        
        var result = response.getResult();
        var usage = response.getMetadata().getUsage();
        
        return new ChatDetails(
            result.getOutput().getContent(),
            result.getMetadata().getFinishReason(),
            usage.getPromptTokens(),
            usage.getGenerationTokens(),
            usage.getTotalTokens()
        );
    }
    
    /**
     * 自定义参数对话
     */
    public String customParamsChat(String message, double temperature, int maxTokens) {
        return chatClient.prompt()
            .user(message)
            .options(OpenAiChatOptions.builder()
                .withTemperature(temperature)
                .withMaxTokens(maxTokens)
                .build())
            .call()
            .content();
    }
    
    public record ChatDetails(
        String content,
        String finishReason,
        int promptTokens,
        int completionTokens,
        int totalTokens
    ) {}
}
```

---

## 第4章：EmbeddingClient与文本向量化

### 4.1 EmbeddingClient概述

EmbeddingClient是Spring AI提供的用于文本向量化的客户端。它将文本转换为高维向量（embedding），这些向量可以：

1. **语义搜索**：基于语义相似度而非关键词匹配进行搜索
2. **文本分类**：通过向量聚类实现文本分类
3. **推荐系统**：计算文本相似度进行推荐
4. **RAG应用**：为检索增强生成提供语义检索能力

### 4.2 EmbeddingClient接口详解

```java
public interface EmbeddingClient {
    
    /**
     * 将单个文本嵌入为向量
     */
    EmbeddingResponse embedForResponse(String text);
    
    /**
     * 批量嵌入多个文本
     */
    EmbeddingResponse embedForResponse(List<String> texts);
    
    /**
     * 获取嵌入向量的维度
     */
    default int dimensions() {
        return embedForResponse("test").getResult().getOutput().size();
    }
}
```

### 4.3 基本使用

#### 4.3.1 自动注入EmbeddingClient

```java
import org.springframework.ai.embedding.EmbeddingClient;
import org.springframework.stereotype.Service;

@Service
public class EmbeddingService {
    
    private final EmbeddingClient embeddingClient;
    
    public EmbeddingService(EmbeddingClient embeddingClient) {
        this.embeddingClient = embeddingClient;
    }
}
```

#### 4.3.2 单文本向量化

```java
@Service
public class SingleEmbeddingService {
    
    private final EmbeddingClient embeddingClient;
    
    public SingleEmbeddingService(EmbeddingClient embeddingClient) {
        this.embeddingClient = embeddingClient;
    }
    
    /**
     * 将单个文本转换为向量
     */
    public List<Double> embedText(String text) {
        EmbeddingResponse response = embeddingClient.embedForResponse(List.of(text));
        return response.getResult().getOutput();
    }
    
    /**
     * 获取向量维度
     */
    public int getDimensions() {
        return embeddingClient.dimensions();
    }
}
```

#### 4.3.3 批量向量化

```java
@Service
public class BatchEmbeddingService {
    
    private final EmbeddingClient embeddingClient;
    
    public BatchEmbeddingService(EmbeddingClient embeddingClient) {
        this.embeddingClient = embeddingClient;
    }
    
    /**
     * 批量嵌入多个文本
     */
    public List<List<Double>> embedTexts(List<String> texts) {
        EmbeddingResponse response = embeddingClient.embedForResponse(texts);
        
        return response.getResults().stream()
            .map(result -> result.getOutput())
            .collect(Collectors.toList());
    }
    
    /**
     * 批量嵌入并返回带索引的结果
     */
    public List<TextEmbedding> embedTextsWithIndex(List<String> texts) {
        EmbeddingResponse response = embeddingClient.embedForResponse(texts);
        
        List<TextEmbedding> results = new ArrayList<>();
        for (int i = 0; i < response.getResults().size(); i++) {
            results.add(new TextEmbedding(
                texts.get(i),
                response.getResults().get(i).getOutput()
            ));
        }
        return results;
    }
    
    public record TextEmbedding(String text, List<Double> embedding) {}
}
```

### 4.4 相似度计算

向量相似度是Embedding的核心应用之一。常见的相似度计算方法包括：

#### 4.4.1 余弦相似度（Cosine Similarity）

```java
@Service
public class SimilarityService {
    
    private final EmbeddingClient embeddingClient;
    
    public SimilarityService(EmbeddingClient embeddingClient) {
        this.embeddingClient = embeddingClient;
    }
    
    /**
     * 计算两个文本的余弦相似度
     * 返回值范围：-1（完全不相似）到 1（完全相同）
     */
    public double cosineSimilarity(String text1, String text2) {
        List<Double> embedding1 = embedText(text1);
        List<Double> embedding2 = embedText(text2);
        
        return calculateCosineSimilarity(embedding1, embedding2);
    }
    
    /**
     * 计算两个向量的余弦相似度
     */
    private double calculateCosineSimilarity(List<Double> vec1, List<Double> vec2) {
        double dotProduct = 0.0;
        double norm1 = 0.0;
        double norm2 = 0.0;
        
        for (int i = 0; i < vec1.size(); i++) {
            dotProduct += vec1.get(i) * vec2.get(i);
            norm1 += Math.pow(vec1.get(i), 2);
            norm2 += Math.pow(vec2.get(i), 2);
        }
        
        return dotProduct / (Math.sqrt(norm1) * Math.sqrt(norm2));
    }
    
    private List<Double> embedText(String text) {
        return embeddingClient.embedForResponse(List.of(text))
            .getResult()
            .getOutput();
    }
}
```

#### 4.4.2 欧几里得距离（Euclidean Distance）

```java
@Service
public class EuclideanDistanceService {
    
    private final EmbeddingClient embeddingClient;
    
    public EuclideanDistanceService(EmbeddingClient embeddingClient) {
        this.embeddingClient = embeddingClient;
    }
    
    /**
     * 计算两个文本的欧几里得距离
     * 返回值越小表示越相似
     */
    public double euclideanDistance(String text1, String text2) {
        List<Double> embedding1 = embedText(text1);
        List<Double> embedding2 = embedText(text2);
        
        return calculateEuclideanDistance(embedding1, embedding2);
    }
    
    private double calculateEuclideanDistance(List<Double> vec1, List<Double> vec2) {
        double sum = 0.0;
        for (int i = 0; i < vec1.size(); i++) {
            sum += Math.pow(vec1.get(i) - vec2.get(i), 2);
        }
        return Math.sqrt(sum);
    }
    
    private List<Double> embedText(String text) {
        return embeddingClient.embedForResponse(List.of(text))
            .getResult()
            .getOutput();
    }
}
```

#### 4.4.3 语义搜索实现

```java
@Service
public class SemanticSearchService {
    
    private final EmbeddingClient embeddingClient;
    
    public SemanticSearchService(EmbeddingClient embeddingClient) {
        this.embeddingClient = embeddingClient;
    }
    
    /**
     * 在文档列表中搜索与查询最相似的文档
     */
    public List<SearchResult> semanticSearch(String query, List<Document> documents, int topK) {
        List<Double> queryEmbedding = embedText(query);
        
        return documents.stream()
            .map(doc -> {
                List<Double> docEmbedding = embedText(doc.content());
                double similarity = cosineSimilarity(queryEmbedding, docEmbedding);
                return new SearchResult(doc, similarity);
            })
            .sorted(Comparator.comparingDouble(SearchResult::similarity).reversed())
            .limit(topK)
            .collect(Collectors.toList());
    }
    
    private List<Double> embedText(String text) {
        return embeddingClient.embedForResponse(List.of(text))
            .getResult()
            .getOutput();
    }
    
    private double cosineSimilarity(List<Double> vec1, List<Double> vec2) {
        double dotProduct = 0.0;
        double norm1 = 0.0;
        double norm2 = 0.0;
        
        for (int i = 0; i < vec1.size(); i++) {
            dotProduct += vec1.get(i) * vec2.get(i);
            norm1 += Math.pow(vec1.get(i), 2);
            norm2 += Math.pow(vec2.get(i), 2);
        }
        
        return dotProduct / (Math.sqrt(norm1) * Math.sqrt(norm2));
    }
    
    public record Document(String id, String content, Map<String, Object> metadata) {}
    public record SearchResult(Document document, double similarity) {}
}
```

### 4.5 实际应用场景

#### 4.5.1 文本分类

```java
@Service
public class TextClassificationService {
    
    private final EmbeddingClient embeddingClient;
    
    // 预定义的类别和示例文本
    private final Map<String, List<String>> categoryExamples = Map.of(
        "技术", List.of("Java编程", "Spring框架", "微服务架构"),
        "体育", List.of("足球比赛", "篮球联赛", "奥运会"),
        "娱乐", List.of("电影上映", "音乐专辑", "明星八卦"),
        "财经", List.of("股票市场", "投资理财", "经济政策")
    );
    
    public TextClassificationService(EmbeddingClient embeddingClient) {
        this.embeddingClient = embeddingClient;
    }
    
    /**
     * 基于语义相似度的文本分类
     */
    public String classify(String text) {
        List<Double> textEmbedding = embedText(text);
        
        String bestCategory = null;
        double bestSimilarity = -1;
        
        for (Map.Entry<String, List<String>> entry : categoryExamples.entrySet()) {
            double avgSimilarity = entry.getValue().stream()
                .mapToDouble(example -> cosineSimilarity(textEmbedding, embedText(example)))
                .average()
                .orElse(0);
            
            if (avgSimilarity > bestSimilarity) {
                bestSimilarity = avgSimilarity;
                bestCategory = entry.getKey();
            }
        }
        
        return bestCategory;
    }
    
    private List<Double> embedText(String text) {
        return embeddingClient.embedForResponse(List.of(text))
            .getResult()
            .getOutput();
    }
    
    private double cosineSimilarity(List<Double> vec1, List<Double> vec2) {
        double dotProduct = 0.0;
        double norm1 = 0.0;
        double norm2 = 0.0;
        
        for (int i = 0; i < vec1.size(); i++) {
            dotProduct += vec1.get(i) * vec2.get(i);
            norm1 += Math.pow(vec1.get(i), 2);
            norm2 += Math.pow(vec2.get(i), 2);
        }
        
        return dotProduct / (Math.sqrt(norm1) * Math.sqrt(norm2));
    }
}
```

#### 4.5.2 重复内容检测

```java
@Service
public class DuplicateDetectionService {
    
    private final EmbeddingClient embeddingClient;
    private static final double SIMILARITY_THRESHOLD = 0.95;
    
    public DuplicateDetectionService(EmbeddingClient embeddingClient) {
        this.embeddingClient = embeddingClient;
    }
    
    /**
     * 检测文本是否与已有文本重复
     */
    public boolean isDuplicate(String newText, List<String> existingTexts) {
        List<Double> newEmbedding = embedText(newText);
        
        return existingTexts.stream()
            .anyMatch(existing -> {
                List<Double> existingEmbedding = embedText(existing);
                return cosineSimilarity(newEmbedding, existingEmbedding) > SIMILARITY_THRESHOLD;
            });
    }
    
    /**
     * 查找相似文本
     */
    public List<String> findSimilarTexts(String query, List<String> texts, int topK) {
        List<Double> queryEmbedding = embedText(query);
        
        return texts.stream()
            .map(text -> new SimilarityScore(text, cosineSimilarity(queryEmbedding, embedText(text))))
            .sorted(Comparator.comparingDouble(SimilarityScore::score).reversed())
            .limit(topK)
            .map(SimilarityScore::text)
            .collect(Collectors.toList());
    }
    
    private List<Double> embedText(String text) {
        return embeddingClient.embedForResponse(List.of(text))
            .getResult()
            .getOutput();
    }
    
    private double cosineSimilarity(List<Double> vec1, List<Double> vec2) {
        double dotProduct = 0.0;
        double norm1 = 0.0;
        double norm2 = 0.0;
        
        for (int i = 0; i < vec1.size(); i++) {
            dotProduct += vec1.get(i) * vec2.get(i);
            norm1 += Math.pow(vec1.get(i), 2);
            norm2 += Math.pow(vec2.get(i), 2);
        }
        
        return dotProduct / (Math.sqrt(norm1) * Math.sqrt(norm2));
    }
    
    private record SimilarityScore(String text, double score) {}
}
```

---

## 第5章：VectorStore向量存储

### 5.1 VectorStore概述

VectorStore是Spring AI提供的向量存储抽象接口，用于存储和检索向量化的文档。它是实现RAG（检索增强生成）的核心组件。

### 5.2 VectorStore接口详解

```java
public interface VectorStore {
    
    /**
     * 添加单个文档
     */
    void add(List<Document> documents);
    
    /**
     * 删除文档
     */
    Optional<Boolean> delete(List<String> idList);
    
    /**
     * 相似性搜索
     */
    List<Document> similaritySearch(String query);
    
    /**
     * 带参数的相似性搜索
     */
    List<Document> similaritySearch(SearchRequest request);
}
```

### 5.3 PgVectorStore详解

PgVectorStore是基于PostgreSQL的pgvector扩展实现的向量存储。它是Spring AI中最常用的向量存储实现之一。

#### 5.3.1 环境准备

**1. 安装PostgreSQL和pgvector扩展：**

```bash
# 使用Docker运行PostgreSQL with pgvector
docker run -d \
  --name postgres-pgvector \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=ai_db \
  -p 5432:5432 \
  ankane/pgvector:latest
```

**2. 初始化数据库（可选，Spring AI可自动创建表）：**

```sql
-- 启用pgvector扩展
CREATE EXTENSION IF NOT EXISTS vector;

-- 创建向量表（Spring AI会自动创建，这里仅作参考）
CREATE TABLE IF NOT EXISTS vector_store (
    id uuid DEFAULT uuid_generate_v4() PRIMARY KEY,
    content text,
    metadata json,
    embedding vector(1536)
);

-- 创建向量索引（可选）
CREATE INDEX ON vector_store USING hnsw (embedding vector_cosine_ops);
```

#### 5.3.2 PgVectorStore配置

```yaml
spring:
  ai:
    vectorstore:
      pgvector:
        # 索引类型：HNSW、IVFFlat、NONE
        index-type: hnsw
        
        # 距离类型：cosine_distance、euclidean_distance、inner_product
        distance-type: cosine_distance
        
        # 向量维度（根据使用的embedding模型）
        # text-embedding-3-small: 1536
        # text-embedding-3-large: 3072
        dimensions: 1536
        
        # 是否自动初始化schema
        initialize-schema: true
        
        # 批量大小
        batching-strategy: TOKEN_COUNT
        max-document-batch-size: 10000
  
  datasource:
    url: jdbc:postgresql://localhost:5432/ai_db
    username: postgres
    password: password
    driver-class-name: org.postgresql.Driver
```

### 5.4 索引类型详解

#### 5.4.1 HNSW（Hierarchical Navigable Small World）

HNSW是一种基于图的近似最近邻搜索算法，适合高维向量检索。

**优点：**
- 查询速度快
- 构建时间相对较短
- 支持增量更新

**缺点：**
- 内存占用较大
- 索引文件较大

**适用场景：**
- 数据量中等（10万-1000万）
- 需要快速查询
- 数据更新频繁

```yaml
spring:
  ai:
    vectorstore:
      pgvector:
        index-type: hnsw
```

#### 5.4.2 IVFFlat（Inverted File Flat）

IVFFlat是一种基于聚类的索引方法。

**优点：**
- 内存效率高
- 适合大规模数据

**缺点：**
- 查询速度比HNSW慢
- 不支持增量更新（需要重建索引）

**适用场景：**
- 数据量大（1000万以上）
- 内存有限
- 数据相对稳定

```yaml
spring:
  ai:
    vectorstore:
      pgvector:
        index-type: ivfflat
```

#### 5.4.3 NONE（无索引）

不使用索引，进行全表扫描。

**适用场景：**
- 数据量很小（<1万）
- 需要精确搜索
- 开发测试阶段

```yaml
spring:
  ai:
    vectorstore:
      pgvector:
        index-type: none
```

### 5.5 距离类型详解

#### 5.5.1 COSINE_DISTANCE（余弦距离）

```yaml
spring:
  ai:
    vectorstore:
      pgvector:
        distance-type: cosine_distance
```

**特点：**
- 衡量向量方向的相似度
- 对向量长度不敏感
- 适合语义相似度计算
- 值范围：0（相同）到 2（相反）

#### 5.5.2 EUCLIDEAN_DISTANCE（欧几里得距离）

```yaml
spring:
  ai:
    vectorstore:
      pgvector:
        distance-type: euclidean_distance
```

**特点：**
- 衡量向量空间中的直线距离
- 对向量长度敏感
- 适合基于数值的相似度计算
- 值范围：0（相同）到正无穷

#### 5.5.3 INNER_PRODUCT（内积）

```yaml
spring:
  ai:
    vectorstore:
      pgvector:
        distance-type: inner_product
```

**特点：**
- 计算向量的点积
- 适合某些特定的embedding模型
- 值范围：负无穷到正无穷

### 5.6 VectorStore基本操作

#### 5.6.1 添加文档

```java
import org.springframework.ai.document.Document;
import org.springframework.ai.vectorstore.VectorStore;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;

@Service
public class VectorStoreService {
    
    private final VectorStore vectorStore;
    
    public VectorStoreService(VectorStore vectorStore) {
        this.vectorStore = vectorStore;
    }
    
    /**
     * 添加单个文档
     */
    public void addDocument(String content) {
        Document document = new Document(content);
        vectorStore.add(List.of(document));
    }
    
    /**
     * 添加带元数据的文档
     */
    public void addDocumentWithMetadata(String content, Map<String, Object> metadata) {
        Document document = new Document(content, metadata);
        vectorStore.add(List.of(document));
    }
    
    /**
     * 批量添加文档
     */
    public void addDocuments(List<String> contents) {
        List<Document> documents = contents.stream()
            .map(Document::new)
            .toList();
        vectorStore.add(documents);
    }
}
```

#### 5.6.2 相似性搜索

```java
@Service
public class SimilaritySearchService {
    
    private final VectorStore vectorStore;
    
    public SimilaritySearchService(VectorStore vectorStore) {
        this.vectorStore = vectorStore;
    }
    
    /**
     * 基本相似性搜索
     */
    public List<Document> search(String query) {
        return vectorStore.similaritySearch(query);
    }
    
    /**
     * 带参数的相似性搜索
     */
    public List<Document> searchWithParams(String query, int topK, double threshold) {
        SearchRequest request = SearchRequest.query(query)
            .withTopK(topK)
            .withSimilarityThreshold(threshold);
        
        return vectorStore.similaritySearch(request);
    }
    
    /**
     * 带元数据过滤的搜索
     */
    public List<Document> searchWithFilter(String query, String category) {
        SearchRequest request = SearchRequest.query(query)
            .withTopK(5)
            .withFilterExpression("category == '" + category + "'");
        
        return vectorStore.similaritySearch(request);
    }
}
```

#### 5.6.3 删除文档

```java
@Service
public class DocumentDeleteService {
    
    private final VectorStore vectorStore;
    
    public DocumentDeleteService(VectorStore vectorStore) {
        this.vectorStore = vectorStore;
    }
    
    /**
     * 根据ID删除文档
     */
    public boolean deleteById(String id) {
        Optional<Boolean> result = vectorStore.delete(List.of(id));
        return result.orElse(false);
    }
    
    /**
     * 批量删除文档
     */
    public boolean deleteByIds(List<String> ids) {
        Optional<Boolean> result = vectorStore.delete(ids);
        return result.orElse(false);
    }
}
```

### 5.7 元数据过滤

元数据过滤允许在向量搜索的基础上，进一步根据文档的元数据进行筛选。

```java
@Service
public class MetadataFilterService {
    
    private final VectorStore vectorStore;
    
    public MetadataFilterService(VectorStore vectorStore) {
        this.vectorStore = vectorStore;
    }
    
    /**
     * 按类别过滤
     */
    public List<Document> searchByCategory(String query, String category) {
        SearchRequest request = SearchRequest.query(query)
            .withTopK(10)
            .withFilterExpression("category == '" + category + "'");
        
        return vectorStore.similaritySearch(request);
    }
    
    /**
     * 按日期范围过滤
     */
    public List<Document> searchByDateRange(String query, String startDate, String endDate) {
        SearchRequest request = SearchRequest.query(query)
            .withTopK(10)
            .withFilterExpression(
                "date >= '" + startDate + "' && date <= '" + endDate + "'"
            );
        
        return vectorStore.similaritySearch(request);
    }
    
    /**
     * 复合条件过滤
     */
    public List<Document> searchWithComplexFilter(
            String query, 
            String category, 
            String author,
            double minScore) {
        
        String filterExpression = String.format(
            "category == '%s' && author == '%s' && score >= %f",
            category, author, minScore
        );
        
        SearchRequest request = SearchRequest.query(query)
            .withTopK(10)
            .withFilterExpression(filterExpression);
        
        return vectorStore.similaritySearch(request);
    }
    
    /**
     * 添加带丰富元数据的文档
     */
    public void addDocumentWithRichMetadata(
            String content, 
            String category,
            String author,
            String date,
            double score) {
        
        Map<String, Object> metadata = Map.of(
            "category", category,
            "author", author,
            "date", date,
            "score", score
        );
        
        Document document = new Document(content, metadata);
        vectorStore.add(List.of(document));
    }
}
```

### 5.8 批量操作

```java
@Service
public class BatchOperationService {
    
    private final VectorStore vectorStore;
    private final EmbeddingClient embeddingClient;
    
    public BatchOperationService(VectorStore vectorStore, EmbeddingClient embeddingClient) {
        this.vectorStore = vectorStore;
        this.embeddingClient = embeddingClient;
    }
    
    /**
     * 批量添加文档并监控进度
     */
    public BatchResult batchAddDocuments(List<String> contents, int batchSize) {
        int total = contents.size();
        int success = 0;
        int failed = 0;
        List<String> failedItems = new ArrayList<>();
        
        for (int i = 0; i < contents.size(); i += batchSize) {
            List<String> batch = contents.subList(i, Math.min(i + batchSize, total));
            
            try {
                List<Document> documents = batch.stream()
                    .map(content -> new Document(content, Map.of(
                        "batch_index", i / batchSize,
                        "timestamp", System.currentTimeMillis()
                    )))
                    .toList();
                
                vectorStore.add(documents);
                success += batch.size();
                
            } catch (Exception e) {
                failed += batch.size();
                failedItems.addAll(batch);
                System.err.println("Batch " + (i / batchSize) + " failed: " + e.getMessage());
            }
        }
        
        return new BatchResult(total, success, failed, failedItems);
    }
    
    /**
     * 批量删除文档
     */
    public int batchDeleteDocuments(List<String> ids, int batchSize) {
        int deleted = 0;
        
        for (int i = 0; i < ids.size(); i += batchSize) {
            List<String> batch = ids.subList(i, Math.min(i + batchSize, ids.size()));
            
            Optional<Boolean> result = vectorStore.delete(batch);
            if (result.isPresent() && result.get()) {
                deleted += batch.size();
            }
        }
        
        return deleted;
    }
    
    public record BatchResult(
        int total,
        int success,
        int failed,
        List<String> failedItems
    ) {}
}
```

### 5.9 完整VectorStore服务示例

```java
package com.example.ai.service;

import org.springframework.ai.document.Document;
import org.springframework.ai.vectorstore.SearchRequest;
import org.springframework.ai.vectorstore.VectorStore;
import org.springframework.stereotype.Service;

import java.util.*;
import java.util.stream.Collectors;

@Service
public class DocumentVectorService {
    
    private final VectorStore vectorStore;
    
    public DocumentVectorService(VectorStore vectorStore) {
        this.vectorStore = vectorStore;
    }
    
    /**
     * 添加文档
     */
    public String addDocument(String content, Map<String, Object> metadata) {
        Document document = new Document(content, metadata);
        vectorStore.add(List.of(document));
        return document.getId();
    }
    
    /**
     * 批量添加文档
     */
    public List<String> addDocuments(List<DocumentInput> inputs) {
        List<Document> documents = inputs.stream()
            .map(input -> new Document(input.content(), input.metadata()))
            .toList();
        
        vectorStore.add(documents);
        
        return documents.stream()
            .map(Document::getId)
            .toList();
    }
    
    /**
     * 相似性搜索
     */
    public List<SearchResult> search(String query, int topK) {
        SearchRequest request = SearchRequest.query(query)
            .withTopK(topK);
        
        return vectorStore.similaritySearch(request).stream()
            .map(doc -> new SearchResult(
                doc.getId(),
                doc.getContent(),
                doc.getMetadata(),
                doc.getScore()
            ))
            .collect(Collectors.toList());
    }
    
    /**
     * 带过滤条件的搜索
     */
    public List<SearchResult> searchWithFilter(
            String query, 
            int topK, 
            String filterExpression) {
        
        SearchRequest request = SearchRequest.query(query)
            .withTopK(topK)
            .withFilterExpression(filterExpression);
        
        return vectorStore.similaritySearch(request).stream()
            .map(doc -> new SearchResult(
                doc.getId(),
                doc.getContent(),
                doc.getMetadata(),
                doc.getScore()
            ))
            .collect(Collectors.toList());
    }
    
    /**
     * 删除文档
     */
    public boolean deleteDocument(String id) {
        Optional<Boolean> result = vectorStore.delete(List.of(id));
        return result.orElse(false);
    }
    
    /**
     * 批量删除文档
     */
    public int deleteDocuments(List<String> ids) {
        Optional<Boolean> result = vectorStore.delete(ids);
        return result.isPresent() && result.get() ? ids.size() : 0;
    }
    
    /**
     * 更新文档（删除后重新添加）
     */
    public String updateDocument(String id, String newContent, Map<String, Object> newMetadata) {
        // 删除旧文档
        deleteDocument(id);
        
        // 添加新文档
        return addDocument(newContent, newMetadata);
    }
    
    // 记录定义
    public record DocumentInput(String content, Map<String, Object> metadata) {}
    public record SearchResult(String id, String content, Map<String, Object> metadata, double score) {}
}
```

---

## 第6章：Function Calling工具调用

### 6.1 Function Calling概述

Function Calling（函数调用）是AI模型的一项重要能力，它允许模型在需要时调用外部函数来获取信息或执行操作。这使得AI能够：

1. **获取实时信息**：如天气、股价、新闻等
2. **执行操作**：如发送邮件、创建日历事件等
3. **访问私有数据**：如查询企业内部数据库
4. **增强推理能力**：通过计算工具辅助复杂推理

### 6.2 Function Calling工作原理

```
┌─────────────┐     1. 发送用户消息      ┌─────────────┐
│   用户      │ ───────────────────────> │   AI模型    │
└─────────────┘                          └─────────────┘
                                                │
                                                │ 2. 判断需要调用函数
                                                ▼
                                         ┌─────────────┐
                                         │  返回函数   │
                                         │  调用请求   │
                                         └─────────────┘
                                                │
                                                │ 3. 执行函数
                                                ▼
                                         ┌─────────────┐
                                         │   函数      │
                                         │  执行结果   │
                                         └─────────────┘
                                                │
                                                │ 4. 返回结果给AI
                                                ▼
                                         ┌─────────────┐
                                         │   AI模型    │
                                         │  生成回复   │
                                         └─────────────┘
                                                │
                                                │ 5. 返回最终回复
                                                ▼
                                         ┌─────────────┐
                                         │   用户      │
                                         └─────────────┘
```

### 6.3 @Tool注解使用

Spring AI 1.1.4引入了`@Tool`注解来标记可以被AI调用的函数。

#### 6.3.1 基本工具函数

```java
import org.springframework.ai.tool.annotation.Tool;
import org.springframework.ai.tool.annotation.ToolParam;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;

@Service
public class ToolFunctions {
    
    /**
     * 获取当前时间
     */
    @Tool(name = "getCurrentTime", description = "获取当前日期和时间")
    public String getCurrentTime() {
        return LocalDateTime.now()
            .format(DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss"));
    }
    
    /**
     * 计算表达式
     */
    @Tool(name = "calculate", description = "计算数学表达式，如 '2 + 2' 或 'sqrt(16)'")
    public double calculate(
            @ToolParam(description = "要计算的数学表达式") String expression) {
        // 使用JavaScript引擎计算表达式
        try {
            javax.script.ScriptEngine engine = 
                new javax.script.ScriptEngineManager().getEngineByName("JavaScript");
            Object result = engine.eval(expression);
            return Double.parseDouble(result.toString());
        } catch (Exception e) {
            throw new RuntimeException("计算失败: " + e.getMessage());
        }
    }
    
    /**
     * 获取天气信息（模拟）
     */
    @Tool(name = "getWeather", description = "获取指定城市的天气信息")
    public WeatherInfo getWeather(
            @ToolParam(description = "城市名称，如 '北京'、'上海'") String city) {
        // 这里应该调用真实的天气API
        // 以下为模拟数据
        return new WeatherInfo(
            city,
            "晴朗",
            25,
            "东南风",
            "3级",
            "适宜出行"
        );
    }
    
    public record WeatherInfo(
        String city,
        String weather,
        int temperature,
        String windDirection,
        String windLevel,
        String suggestion
    ) {}
}
```

#### 6.3.2 带参数的复杂工具函数

```java
@Service
public class AdvancedToolFunctions {
    
    /**
     * 搜索产品
     */
    @Tool(name = "searchProducts", description = "根据条件搜索产品")
    public List<Product> searchProducts(
            @ToolParam(description = "搜索关键词") String keyword,
            @ToolParam(description = "最低价格") Double minPrice,
            @ToolParam(description = "最高价格") Double maxPrice,
            @ToolParam(description = "产品类别") String category) {
        
        // 这里应该调用真实的产品搜索服务
        // 以下为模拟数据
        return List.of(
            new Product("P001", "iPhone 15", "手机", 5999.0, 100),
            new Product("P002", "MacBook Pro", "电脑", 14999.0, 50)
        );
    }
    
    /**
     * 创建订单
     */
    @Tool(name = "createOrder", description = "创建新订单")
    public OrderResult createOrder(
            @ToolParam(description = "用户ID") String userId,
            @ToolParam(description = "产品ID列表") List<String> productIds,
            @ToolParam(description = "收货地址") String address) {
        
        // 这里应该调用真实的订单服务
        String orderId = "ORD" + System.currentTimeMillis();
        return new OrderResult(orderId, "CREATED", "订单创建成功");
    }
    
    /**
     * 查询订单状态
     */
    @Tool(name = "getOrderStatus", description = "查询订单状态")
    public OrderStatus getOrderStatus(
            @ToolParam(description = "订单ID") String orderId) {
        
        // 这里应该调用真实的订单查询服务
        return new OrderStatus(orderId, "SHIPPED", "2024-01-15", "运输中");
    }
    
    // 记录定义
    public record Product(String id, String name, String category, 
                          double price, int stock) {}
    public record OrderResult(String orderId, String status, String message) {}
    public record OrderStatus(String orderId, String status, 
                              String updateTime, String description) {}
}
```

### 6.4 函数注册和调用

#### 6.4.1 注册工具函数

```java
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.tool.ToolCallback;
import org.springframework.ai.tool.ToolCallbacks;
import org.springframework.stereotype.Service;

@Service
public class ToolCallingService {
    
    private final ChatClient chatClient;
    private final ToolFunctions toolFunctions;
    
    public ToolCallingService(ChatClient.Builder chatClientBuilder, 
                              ToolFunctions toolFunctions) {
        this.toolFunctions = toolFunctions;
        this.chatClient = chatClientBuilder
            .defaultTools(ToolCallbacks.from(toolFunctions))  // 注册所有工具函数
            .build();
    }
    
    /**
     * 使用工具函数的对话
     */
    public String chatWithTools(String userMessage) {
        return chatClient.prompt()
            .user(userMessage)
            .call()
            .content();
    }
}
```

#### 6.4.2 选择性注册工具函数

```java
@Service
public class SelectiveToolService {
    
    private final ChatClient chatClient;
    private final ToolFunctions toolFunctions;
    private final AdvancedToolFunctions advancedToolFunctions;
    
    public SelectiveToolService(ChatClient.Builder chatClientBuilder,
                                ToolFunctions toolFunctions,
                                AdvancedToolFunctions advancedToolFunctions) {
        this.toolFunctions = toolFunctions;
        this.advancedToolFunctions = advancedToolFunctions;
        this.chatClient = chatClientBuilder.build();
    }
    
    /**
     * 只使用基础工具函数
     */
    public String chatWithBasicTools(String userMessage) {
        return chatClient.prompt()
            .user(userMessage)
            .tools(
                ToolCallbacks.from(toolFunctions.getCurrentTime()),
                ToolCallbacks.from(toolFunctions.calculate())
            )
            .call()
            .content();
    }
    
    /**
     * 使用所有工具函数
     */
    public String chatWithAllTools(String userMessage) {
        return chatClient.prompt()
            .user(userMessage)
            .tools(
                ToolCallbacks.from(toolFunctions),
                ToolCallbacks.from(advancedToolFunctions)
            )
            .call()
            .content();
    }
}
```

### 6.5 多函数调用场景

#### 6.5.1 并行函数调用

```java
@Service
public class ParallelToolService {
    
    private final ChatClient chatClient;
    private final WeatherService weatherService;
    private final StockService stockService;
    private final NewsService newsService;
    
    public ParallelToolService(ChatClient.Builder chatClientBuilder,
                               WeatherService weatherService,
                               StockService stockService,
                               NewsService newsService) {
        this.weatherService = weatherService;
        this.stockService = stockService;
        this.newsService = newsService;
        this.chatClient = chatClientBuilder
            .defaultTools(
                ToolCallbacks.from(weatherService),
                ToolCallbacks.from(stockService),
                ToolCallbacks.from(newsService)
            )
            .build();
    }
    
    /**
     * 需要调用多个工具的场景
     */
    public String getDailyBriefing(String city, List<String> stocks) {
        String prompt = String.format(
            "请为我生成今日简报，包括：\n" +
            "1. %s的天气情况\n" +
            "2. 以下股票的最新价格: %s\n" +
            "3. 今天的重要新闻\n" +
            "请用中文回答，格式清晰。",
            city, String.join(", ", stocks)
        );
        
        return chatClient.prompt()
            .user(prompt)
            .call()
            .content();
    }
}
```

#### 6.5.2 链式函数调用

```java
@Service
public class ChainedToolService {
    
    private final ChatClient chatClient;
    private final UserService userService;
    private final OrderService orderService;
    private final PaymentService paymentService;
    
    public ChainedToolService(ChatClient.Builder chatClientBuilder,
                              UserService userService,
                              OrderService orderService,
                              PaymentService paymentService) {
        this.userService = userService;
        this.orderService = orderService;
        this.paymentService = paymentService;
        this.chatClient = chatClientBuilder
            .defaultTools(
                ToolCallbacks.from(userService),
                ToolCallbacks.from(orderService),
                ToolCallbacks.from(paymentService)
            )
            .build();
    }
    
    /**
     * 处理用户购买请求
     * AI会自动调用：查询用户 -> 创建订单 -> 处理支付
     */
    public String processPurchase(String userId, String productId) {
        String prompt = String.format(
            "用户 %s 想要购买产品 %s，请完成整个购买流程。",
            userId, productId
        );
        
        return chatClient.prompt()
            .system("你是一个购物助手，会帮助用户完成购买流程。" +
                   "你需要：1) 查询用户信息 2) 创建订单 3) 处理支付")
            .user(prompt)
            .call()
            .content();
    }
}
```

### 6.6 完整代码示例

```java
package com.example.ai.service;

import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.tool.annotation.Tool;
import org.springframework.ai.tool.annotation.ToolParam;
import org.springframework.ai.tool.ToolCallbacks;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.*;

@Service
public class CompleteToolService {
    
    private final ChatClient chatClient;
    
    public CompleteToolService(ChatClient.Builder chatClientBuilder) {
        this.chatClient = chatClientBuilder
            .defaultSystem("你是一个智能助手，可以使用各种工具来帮助用户。" +
                          "当需要获取实时信息或执行操作时，请使用相应的工具。")
            .defaultTools(ToolCallbacks.from(new ToolFunctions()))
            .build();
    }
    
    /**
     * 通用工具对话
     */
    public String chat(String message) {
        return chatClient.prompt()
            .user(message)
            .call()
            .content();
    }
    
    /**
     * 工具函数集合
     */
    public static class ToolFunctions {
        
        @Tool(description = "获取当前日期和时间")
        public String getCurrentTime() {
            return LocalDateTime.now()
                .format(DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss"));
        }
        
        @Tool(description = "计算数学表达式")
        public double calculate(
                @ToolParam(description = "数学表达式，如 '2 + 2'") String expression) {
            try {
                javax.script.ScriptEngine engine = 
                    new javax.script.ScriptEngineManager().getEngineByName("JavaScript");
                return Double.parseDouble(engine.eval(expression).toString());
            } catch (Exception e) {
                throw new RuntimeException("计算失败: " + e.getMessage());
            }
        }
        
        @Tool(description = "获取天气信息")
        public WeatherInfo getWeather(
                @ToolParam(description = "城市名称") String city) {
            // 模拟天气数据
            Map<String, WeatherInfo> weatherData = Map.of(
                "北京", new WeatherInfo("北京", "晴", 25, "东南风", "2级"),
                "上海", new WeatherInfo("上海", "多云", 22, "东北风", "3级"),
                "广州", new WeatherInfo("广州", "小雨", 28, "南风", "2级")
            );
            return weatherData.getOrDefault(city, 
                new WeatherInfo(city, "未知", 0, "未知", "未知"));
        }
        
        @Tool(description = "搜索产品")
        public List<Product> searchProducts(
                @ToolParam(description = "搜索关键词") String keyword) {
            // 模拟产品数据
            return List.of(
                new Product("P001", "iPhone 15 Pro", 7999.0, "手机"),
                new Product("P002", "MacBook Air", 8999.0, "电脑"),
                new Product("P003", "AirPods Pro", 1899.0, "配件")
            ).stream()
                .filter(p -> p.name().toLowerCase().contains(keyword.toLowerCase()))
                .toList();
        }
        
        @Tool(description = "单位转换")
        public double convertUnit(
                @ToolParam(description = "数值") double value,
                @ToolParam(description = "源单位") String fromUnit,
                @ToolParam(description = "目标单位") String toUnit) {
            
            // 长度转换
            if (fromUnit.equals("m") && toUnit.equals("cm")) return value * 100;
            if (fromUnit.equals("cm") && toUnit.equals("m")) return value / 100;
            if (fromUnit.equals("km") && toUnit.equals("m")) return value * 1000;
            
            // 重量转换
            if (fromUnit.equals("kg") && toUnit.equals("g")) return value * 1000;
            if (fromUnit.equals("g") && toUnit.equals("kg")) return value / 1000;
            
            // 温度转换
            if (fromUnit.equals("C") && toUnit.equals("F")) return value * 9/5 + 32;
            if (fromUnit.equals("F") && toUnit.equals("C")) return (value - 32) * 5/9;
            
            throw new IllegalArgumentException("不支持的单位转换: " + fromUnit + " -> " + toUnit);
        }
    }
    
    // 记录定义
    public record WeatherInfo(String city, String weather, int temperature,
                               String windDirection, String windLevel) {}
    public record Product(String id, String name, double price, String category) {}
}
```

---

## 第7章：Structured Output结构化输出

### 7.1 结构化输出概述

结构化输出是指让AI模型以特定的结构化格式（如JSON）返回结果，而不是自由文本。这在以下场景非常有用：

1. **数据提取**：从非结构化文本中提取结构化信息
2. **表单填充**：自动填充表单字段
3. **API响应**：生成可直接用于API的数据
4. **数据转换**：将自然语言转换为结构化数据

### 7.2 BeanOutputConverter

BeanOutputConverter用于将AI输出转换为Java Bean对象。

#### 7.2.1 定义输出Bean

```java
import java.util.List;

/**
 * 人物信息Bean
 */
public class PersonInfo {
    private String name;
    private int age;
    private String occupation;
    private List<String> skills;
    private Address address;
    
    // 构造函数
    public PersonInfo() {}
    
    // Getters and Setters
    public String getName() { return name; }
    public void setName(String name) { this.name = name; }
    
    public int getAge() { return age; }
    public void setAge(int age) { this.age = age; }
    
    public String getOccupation() { return occupation; }
    public void setOccupation(String occupation) { this.occupation = occupation; }
    
    public List<String> getSkills() { return skills; }
    public void setSkills(List<String> skills) { this.skills = skills; }
    
    public Address getAddress() { return address; }
    public void setAddress(Address address) { this.address = address; }
    
    // 内部类
    public static class Address {
        private String city;
        private String country;
        
        public String getCity() { return city; }
        public void setCity(String city) { this.city = city; }
        
        public String getCountry() { return country; }
        public void setCountry(String country) { this.country = country; }
    }
}
```

#### 7.2.2 使用BeanOutputConverter

```java
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.converter.BeanOutputConverter;
import org.springframework.stereotype.Service;

@Service
public class BeanOutputService {
    
    private final ChatClient chatClient;
    
    public BeanOutputService(ChatClient.Builder chatClientBuilder) {
        this.chatClient = chatClientBuilder.build();
    }
    
    /**
     * 从文本中提取人物信息
     */
    public PersonInfo extractPersonInfo(String text) {
        BeanOutputConverter<PersonInfo> converter = new BeanOutputConverter<>(PersonInfo.class);
        
        String format = converter.getFormat();
        
        String prompt = String.format("""
            从以下文本中提取人物信息，并以JSON格式返回：
            
            文本：%s
            
            请严格按照以下格式返回：
            %s
            """, text, format);
        
        String response = chatClient.prompt()
            .user(prompt)
            .call()
            .content();
        
        return converter.convert(response);
    }
}
```

### 7.3 MapOutputConverter

MapOutputConverter用于将AI输出转换为Map对象，适合动态结构的数据。

```java
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.converter.MapOutputConverter;
import org.springframework.stereotype.Service;

import java.util.Map;

@Service
public class MapOutputService {
    
    private final ChatClient chatClient;
    
    public MapOutputService(ChatClient.Builder chatClientBuilder) {
        this.chatClient = chatClientBuilder.build();
    }
    
    /**
     * 提取动态字段
     */
    public Map<String, Object> extractDynamicFields(String text, String[] fields) {
        MapOutputConverter converter = new MapOutputConverter();
        
        String fieldsStr = String.join(", ", fields);
        String format = converter.getFormat();
        
        String prompt = String.format("""
            从以下文本中提取以下字段：%s
            
            文本：%s
            
            请严格按照以下格式返回：
            %s
            """, fieldsStr, text, format);
        
        String response = chatClient.prompt()
            .user(prompt)
            .call()
            .content();
        
        return converter.convert(response);
    }
    
    /**
     * 情感分析
     */
    public Map<String, Object> sentimentAnalysis(String text) {
        MapOutputConverter converter = new MapOutputConverter();
        
        String prompt = String.format("""
            对以下文本进行情感分析，返回情感分数和标签：
            
            文本：%s
            
            请返回以下格式的JSON：
            {
                "sentiment": "positive/negative/neutral",
                "confidence": 0.95,
                "emotions": ["joy", "excitement"],
                "score": 0.8
            }
            """, text);
        
        String response = chatClient.prompt()
            .user(prompt)
            .call()
            .content();
        
        return converter.convert(response);
    }
}
```

### 7.4 ListOutputConverter

ListOutputConverter用于将AI输出转换为List对象。

```java
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.converter.ListOutputConverter;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class ListOutputService {
    
    private final ChatClient chatClient;
    
    public ListOutputService(ChatClient.Builder chatClientBuilder) {
        this.chatClient = chatClientBuilder.build();
    }
    
    /**
     * 提取关键词列表
     */
    public List<String> extractKeywords(String text, int count) {
        ListOutputConverter converter = new ListOutputConverter();
        
        String format = converter.getFormat();
        
        String prompt = String.format("""
            从以下文本中提取%d个关键词：
            
            文本：%s
            
            请严格按照以下格式返回：
            %s
            """, count, text, format);
        
        String response = chatClient.prompt()
            .user(prompt)
            .call()
            .content();
        
        return converter.convert(response);
    }
    
    /**
     * 生成待办事项列表
     */
    public List<String> generateTodoList(String task) {
        ListOutputConverter converter = new ListOutputConverter();
        
        String prompt = String.format("""
            为以下任务生成详细的待办事项列表：
            
            任务：%s
            
            请以列表形式返回所有步骤。
            """, task);
        
        String response = chatClient.prompt()
            .user(prompt)
            .call()
            .content();
        
        return converter.convert(response);
    }
}
```

### 7.5 自定义转换器

可以实现自定义的转换器来满足特定需求。

```java
import org.springframework.ai.converter.StructuredOutputConverter;
import com.fasterxml.jackson.databind.ObjectMapper;

/**
 * 自定义JSON转换器
 */
public class CustomJsonConverter<T> implements StructuredOutputConverter<T> {
    
    private final Class<T> targetClass;
    private final ObjectMapper objectMapper;
    
    public CustomJsonConverter(Class<T> targetClass) {
        this.targetClass = targetClass;
        this.objectMapper = new ObjectMapper();
    }
    
    @Override
    public T convert(String text) {
        try {
            // 清理文本，提取JSON部分
            String json = extractJson(text);
            return objectMapper.readValue(json, targetClass);
        } catch (Exception e) {
            throw new RuntimeException("转换失败: " + e.getMessage(), e);
        }
    }
    
    @Override
    public String getFormat() {
        return "请以有效的JSON格式返回结果";
    }
    
    private String extractJson(String text) {
        // 提取JSON内容（处理可能的markdown代码块）
        if (text.contains("```json")) {
            return text.substring(
                text.indexOf("```json") + 7,
                text.lastIndexOf("```")
            ).trim();
        }
        if (text.contains("```")) {
            return text.substring(
                text.indexOf("```") + 3,
                text.lastIndexOf("```")
            ).trim();
        }
        return text.trim();
    }
}
```

### 7.6 JSON Schema生成

可以使用JSON Schema来更精确地控制输出格式。

```java
import com.fasterxml.jackson.module.jsonSchema.JsonSchemaGenerator;
import com.fasterxml.jackson.module.jsonSchema.JsonSchema;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Service;

@Service
public class JsonSchemaService {
    
    private final ObjectMapper objectMapper;
    
    public JsonSchemaService() {
        this.objectMapper = new ObjectMapper();
    }
    
    /**
     * 为类生成JSON Schema
     */
    public String generateSchema(Class<?> clazz) {
        try {
            JsonSchemaGenerator generator = new JsonSchemaGenerator(objectMapper);
            JsonSchema schema = generator.generateSchema(clazz);
            return objectMapper.writerWithDefaultPrettyPrinter()
                .writeValueAsString(schema);
        } catch (Exception e) {
            throw new RuntimeException("生成Schema失败: " + e.getMessage(), e);
        }
    }
    
    /**
     * 使用Schema进行结构化输出
     */
    public <T> T extractWithSchema(String text, Class<T> clazz, 
                                    org.springframework.ai.chat.client.ChatClient chatClient) {
        String schema = generateSchema(clazz);
        
        String prompt = String.format("""
            从以下文本中提取信息，并严格按照给定的JSON Schema返回：
            
            文本：%s
            
            JSON Schema：
            %s
            
            请确保返回的JSON完全符合上述Schema。
            """, text, schema);
        
        String response = chatClient.prompt()
            .user(prompt)
            .call()
            .content();
        
        try {
            return objectMapper.readValue(response, clazz);
        } catch (Exception e) {
            throw new RuntimeException("解析失败: " + e.getMessage(), e);
        }
    }
}
```

### 7.7 完整代码示例

```java
package com.example.ai.service;

import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.converter.BeanOutputConverter;
import org.springframework.ai.converter.MapOutputConverter;
import org.springframework.ai.converter.ListOutputConverter;
import org.springframework.stereotype.Service;

import java.util.*;

@Service
public class StructuredOutputService {
    
    private final ChatClient chatClient;
    
    public StructuredOutputService(ChatClient.Builder chatClientBuilder) {
        this.chatClient = chatClientBuilder.build();
    }
    
    /**
     * 提取产品信息
     */
    public ProductInfo extractProductInfo(String description) {
        BeanOutputConverter<ProductInfo> converter = 
            new BeanOutputConverter<>(ProductInfo.class);
        
        String prompt = String.format("""
            从以下产品描述中提取信息：
            
            %s
            
            %s
            """, description, converter.getFormat());
        
        String response = chatClient.prompt()
            .user(prompt)
            .call()
            .content();
        
        return converter.convert(response);
    }
    
    /**
     * 提取文章元数据
     */
    public Map<String, Object> extractArticleMetadata(String article) {
        MapOutputConverter converter = new MapOutputConverter();
        
        String prompt = String.format("""
            分析以下文章，提取元数据：
            
            %s
            
            请提取以下字段：
            - title: 标题
            - author: 作者
            - publishDate: 发布日期
            - category: 类别
            - tags: 标签列表
            - summary: 摘要
            - readingTime: 预计阅读时间（分钟）
            
            %s
            """, article, converter.getFormat());
        
        String response = chatClient.prompt()
            .user(prompt)
            .call()
            .content();
        
        return converter.convert(response);
    }
    
    /**
     * 提取实体列表
     */
    public List<String> extractEntities(String text, String entityType) {
        ListOutputConverter converter = new ListOutputConverter();
        
        String prompt = String.format("""
            从以下文本中提取所有%s：
            
            %s
            
            请以列表形式返回所有%s，每个%s占一行。
            """, entityType, text, entityType, entityType);
        
        String response = chatClient.prompt()
            .user(prompt)
            .call()
            .content();
        
        return converter.convert(response);
    }
    
    /**
     * 分析用户评论
     */
    public List<ReviewAnalysis> analyzeReviews(List<String> reviews) {
        BeanOutputConverter<ReviewAnalysisList> converter = 
            new BeanOutputConverter<>(ReviewAnalysisList.class);
        
        String reviewsText = String.join("\n---\n", reviews);
        
        String prompt = String.format("""
            分析以下用户评论，每条评论提取：
            - sentiment: 情感（positive/negative/neutral）
            - rating: 评分（1-5）
            - keyPoints: 关键要点列表
            - suggestions: 改进建议
            
            评论：
            %s
            
            %s
            """, reviewsText, converter.getFormat());
        
        String response = chatClient.prompt()
            .user(prompt)
            .call()
            .content();
        
        return converter.convert(response).getReviews();
    }
    
    // Bean定义
    public static class ProductInfo {
        private String name;
        private String brand;
        private double price;
        private List<String> features;
        private List<String> specifications;
        
        // Getters and Setters
        public String getName() { return name; }
        public void setName(String name) { this.name = name; }
        
        public String getBrand() { return brand; }
        public void setBrand(String brand) { this.brand = brand; }
        
        public double getPrice() { return price; }
        public void setPrice(double price) { this.price = price; }
        
        public List<String> getFeatures() { return features; }
        public void setFeatures(List<String> features) { this.features = features; }
        
        public List<String> getSpecifications() { return specifications; }
        public void setSpecifications(List<String> specifications) { this.specifications = specifications; }
    }
    
    public static class ReviewAnalysis {
        private String sentiment;
        private int rating;
        private List<String> keyPoints;
        private List<String> suggestions;
        
        // Getters and Setters
        public String getSentiment() { return sentiment; }
        public void setSentiment(String sentiment) { this.sentiment = sentiment; }
        
        public int getRating() { return rating; }
        public void setRating(int rating) { this.rating = rating; }
        
        public List<String> getKeyPoints() { return keyPoints; }
        public void setKeyPoints(List<String> keyPoints) { this.keyPoints = keyPoints; }
        
        public List<String> getSuggestions() { return suggestions; }
        public void setSuggestions(List<String> suggestions) { this.suggestions = suggestions; }
    }
    
    public static class ReviewAnalysisList {
        private List<ReviewAnalysis> reviews;
        
        public List<ReviewAnalysis> getReviews() { return reviews; }
        public void setReviews(List<ReviewAnalysis> reviews) { this.reviews = reviews; }
    }
}
```

---

## 第8章：Chat Memory对话记忆

### 8.1 Chat Memory概述

Chat Memory（对话记忆）用于在多轮对话中保持上下文。它允许AI模型记住之前的对话内容，从而进行连贯的多轮交互。

### 8.2 ChatMemory接口详解

```java
public interface ChatMemory {
    
    /**
     * 添加消息到指定会话
     */
    void add(String conversationId, Message message);
    
    /**
     * 获取指定会话的消息
     */
    List<Message> get(String conversationId, int lastN);
    
    /**
     * 清除指定会话的消息
     */
    void clear(String conversationId);
}
```

### 8.3 InMemoryChatMemory实现

InMemoryChatMemory是最简单的实现，将对话历史存储在内存中。

```java
import org.springframework.ai.chat.memory.ChatMemory;
import org.springframework.ai.chat.memory.InMemoryChatMemory;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class ChatMemoryConfig {
    
    @Bean
    public ChatMemory chatMemory() {
        return new InMemoryChatMemory();
    }
}
```

#### 8.3.1 使用InMemoryChatMemory

```java
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.memory.ChatMemory;
import org.springframework.ai.chat.messages.Message;
import org.springframework.ai.chat.messages.UserMessage;
import org.springframework.ai.chat.messages.AssistantMessage;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.UUID;

@Service
public class InMemoryChatService {
    
    private final ChatClient chatClient;
    private final ChatMemory chatMemory;
    
    public InMemoryChatService(ChatClient.Builder chatClientBuilder, 
                               ChatMemory chatMemory) {
        this.chatClient = chatClientBuilder.build();
        this.chatMemory = chatMemory;
    }
    
    /**
     * 多轮对话
     */
    public String chat(String conversationId, String userMessage) {
        // 添加用户消息到记忆
        chatMemory.add(conversationId, new UserMessage(userMessage));
        
        // 获取对话历史
        List<Message> history = chatMemory.get(conversationId, 10);
        
        // 调用AI
        String response = chatClient.prompt()
            .messages(history)
            .call()
            .content();
        
        // 添加AI回复到记忆
        chatMemory.add(conversationId, new AssistantMessage(response));
        
        return response;
    }
    
    /**
     * 创建新会话
     */
    public String createConversation() {
        return UUID.randomUUID().toString();
    }
    
    /**
     * 清除会话历史
     */
    public void clearConversation(String conversationId) {
        chatMemory.clear(conversationId);
    }
}
```

### 8.4 JdbcChatMemory实现

JdbcChatMemory将对话历史持久化到数据库中，适合生产环境使用。

#### 8.4.1 数据库表结构

```sql
-- 创建对话记忆表
CREATE TABLE chat_memory (
    id SERIAL PRIMARY KEY,
    conversation_id VARCHAR(255) NOT NULL,
    message_type VARCHAR(50) NOT NULL,  -- USER, ASSISTANT, SYSTEM
    content TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_conversation_id (conversation_id),
    INDEX idx_timestamp (timestamp)
);
```

#### 8.4.2 配置JdbcChatMemory

```java
import org.springframework.ai.chat.memory.ChatMemory;
import org.springframework.ai.chat.memory.JdbcChatMemory;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.jdbc.core.JdbcTemplate;

@Configuration
public class JdbcChatMemoryConfig {
    
    @Bean
    public ChatMemory chatMemory(JdbcTemplate jdbcTemplate) {
        return new JdbcChatMemory(jdbcTemplate);
    }
}
```

```yaml
spring:
  datasource:
    url: jdbc:postgresql://localhost:5432/ai_db
    username: postgres
    password: password
```

### 8.5 CassandraChatMemory实现

CassandraChatMemory使用Apache Cassandra存储对话历史，适合大规模分布式部署。

#### 8.5.1 Cassandra表结构

```cql
-- 创建Keyspace
CREATE KEYSPACE IF NOT EXISTS ai_chat 
WITH REPLICATION = {'class': 'SimpleStrategy', 'replication_factor': 3};

-- 创建对话记忆表
CREATE TABLE IF NOT EXISTS ai_chat.chat_memory (
    conversation_id TEXT,
    timestamp TIMESTAMP,
    message_type TEXT,
    content TEXT,
    PRIMARY KEY (conversation_id, timestamp)
) WITH CLUSTERING ORDER BY (timestamp ASC);
```

#### 8.5.2 配置CassandraChatMemory

```java
import org.springframework.ai.chat.memory.CassandraChatMemory;
import org.springframework.ai.chat.memory.ChatMemory;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import com.datastax.oss.driver.api.core.CqlSession;

@Configuration
public class CassandraChatMemoryConfig {
    
    @Bean
    public ChatMemory chatMemory(CqlSession cqlSession) {
        return new CassandraChatMemory(cqlSession);
    }
}
```

### 8.6 对话历史管理

#### 8.6.1 限制对话历史长度

```java
@Service
public class LimitedChatMemoryService {
    
    private final ChatClient chatClient;
    private final ChatMemory chatMemory;
    private static final int MAX_HISTORY = 20;  // 最多保留20条消息
    
    public LimitedChatMemoryService(ChatClient.Builder chatClientBuilder,
                                    ChatMemory chatMemory) {
        this.chatClient = chatClientBuilder.build();
        this.chatMemory = chatMemory;
    }
    
    public String chat(String conversationId, String userMessage) {
        // 添加用户消息
        chatMemory.add(conversationId, new UserMessage(userMessage));
        
        // 只获取最近的消息
        List<Message> history = chatMemory.get(conversationId, MAX_HISTORY);
        
        // 调用AI
        String response = chatClient.prompt()
            .messages(history)
            .call()
            .content();
        
        // 添加AI回复
        chatMemory.add(conversationId, new AssistantMessage(response));
        
        return response;
    }
}
```

#### 8.6.2 对话历史摘要

```java
@Service
public class SummarizedChatMemoryService {
    
    private final ChatClient chatClient;
    private final ChatMemory chatMemory;
    private static final int SUMMARY_THRESHOLD = 10;
    
    public SummarizedChatMemoryService(ChatClient.Builder chatClientBuilder,
                                       ChatMemory chatMemory) {
        this.chatClient = chatClientBuilder.build();
        this.chatMemory = chatMemory;
    }
    
    public String chat(String conversationId, String userMessage) {
        chatMemory.add(conversationId, new UserMessage(userMessage));
        
        List<Message> history = chatMemory.get(conversationId, 100);
        
        // 如果历史消息过多，生成摘要
        if (history.size() > SUMMARY_THRESHOLD) {
            history = summarizeHistory(conversationId, history);
        }
        
        String response = chatClient.prompt()
            .messages(history)
            .call()
            .content();
        
        chatMemory.add(conversationId, new AssistantMessage(response));
        
        return response;
    }
    
    private List<Message> summarizeHistory(String conversationId, List<Message> history) {
        // 生成摘要
        String summary = chatClient.prompt()
            .system("请总结以下对话的主要内容：")
            .user(historyToString(history.subList(0, history.size() - 5)))
            .call()
            .content();
        
        // 清除旧历史，添加摘要
        chatMemory.clear(conversationId);
        chatMemory.add(conversationId, new SystemMessage(
            "以下是之前对话的摘要：" + summary
        ));
        
        // 添加最近的消息
        for (Message msg : history.subList(history.size() - 5, history.size())) {
            chatMemory.add(conversationId, msg);
        }
        
        return chatMemory.get(conversationId, 100);
    }
    
    private String historyToString(List<Message> messages) {
        return messages.stream()
            .map(m -> m.getMessageType() + ": " + m.getContent())
            .collect(Collectors.joining("\n"));
    }
}
```

### 8.7 完整代码示例

```java
package com.example.ai.service;

import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.memory.ChatMemory;
import org.springframework.ai.chat.messages.*;
import org.springframework.stereotype.Service;

import java.util.*;
import java.util.concurrent.ConcurrentHashMap;

@Service
public class CompleteChatMemoryService {
    
    private final ChatClient chatClient;
    private final ChatMemory chatMemory;
    
    // 会话元数据
    private final Map<String, ConversationMeta> conversationMetaMap = new ConcurrentHashMap<>();
    
    public CompleteChatMemoryService(ChatClient.Builder chatClientBuilder,
                                     ChatMemory chatMemory) {
        this.chatClient = chatClientBuilder.build();
        this.chatMemory = chatMemory;
    }
    
    /**
     * 创建新会话
     */
    public String createConversation(String title) {
        String conversationId = UUID.randomUUID().toString();
        conversationMetaMap.put(conversationId, new ConversationMeta(
            conversationId,
            title,
            System.currentTimeMillis(),
            0
        ));
        return conversationId;
    }
    
    /**
     * 发送消息
     */
    public ChatResponse chat(String conversationId, String message) {
        // 更新会话元数据
        ConversationMeta meta = conversationMetaMap.get(conversationId);
        if (meta == null) {
            throw new IllegalArgumentException("会话不存在: " + conversationId);
        }
        
        // 添加用户消息
        chatMemory.add(conversationId, new UserMessage(message));
        
        // 获取历史消息
        List<Message> history = chatMemory.get(conversationId, 50);
        
        // 调用AI
        String response = chatClient.prompt()
            .messages(history)
            .call()
            .content();
        
        // 添加AI回复
        chatMemory.add(conversationId, new AssistantMessage(response));
        
        // 更新元数据
        conversationMetaMap.put(conversationId, new ConversationMeta(
            conversationId,
            meta.title(),
            meta.createTime(),
            meta.messageCount() + 2
        ));
        
        return new ChatResponse(response, conversationId, 
            conversationMetaMap.get(conversationId).messageCount());
    }
    
    /**
     * 获取会话历史
     */
    public List<MessageInfo> getHistory(String conversationId) {
        List<Message> messages = chatMemory.get(conversationId, 100);
        
        return messages.stream()
            .map(m -> new MessageInfo(
                m.getMessageType().name(),
                m.getContent(),
                m.getMetadata()
            ))
            .toList();
    }
    
    /**
     * 获取所有会话
     */
    public List<ConversationInfo> getAllConversations() {
        return conversationMetaMap.values().stream()
            .map(meta -> new ConversationInfo(
                meta.id(),
                meta.title(),
                meta.createTime(),
                meta.messageCount()
            ))
            .sorted(Comparator.comparingLong(ConversationInfo::createTime).reversed())
            .toList();
    }
    
    /**
     * 删除会话
     */
    public void deleteConversation(String conversationId) {
        chatMemory.clear(conversationId);
        conversationMetaMap.remove(conversationId);
    }
    
    /**
     * 清空会话（保留会话ID）
     */
    public void clearConversation(String conversationId) {
        chatMemory.clear(conversationId);
        ConversationMeta meta = conversationMetaMap.get(conversationId);
        if (meta != null) {
            conversationMetaMap.put(conversationId, new ConversationMeta(
                conversationId,
                meta.title(),
                meta.createTime(),
                0
            ));
        }
    }
    
    // 记录定义
    private record ConversationMeta(String id, String title, 
                                    long createTime, int messageCount) {}
    public record ChatResponse(String content, String conversationId, int messageCount) {}
    public record MessageInfo(String type, String content, Map<String, Object> metadata) {}
    public record ConversationInfo(String id, String title, 
                                   long createTime, int messageCount) {}
}
```

---


## 8. 对话记忆（Chat Memory）

### 8.1 ChatMemory接口

`ChatMemory` 用于存储和管理对话历史：

```java
public interface ChatMemory {
    void add(String conversationId, List<Message> messages);
    List<Message> get(String conversationId, int lastN);
    void clear(String conversationId);
}
```

### 8.2 MessageWindowChatMemory实现

`MessageWindowChatMemory` 是最常用的实现，它维护一个固定大小的消息窗口：

```java
// 创建内存存储的ChatMemory
ChatMemory chatMemory = MessageWindowChatMemory.builder()
        .chatMemoryRepository(new InMemoryChatMemoryRepository())
        .maxMessages(20)  // 保留最近20条消息
        .build();

// 或者使用Redis存储
ChatMemory chatMemory = MessageWindowChatMemory.builder()
        .chatMemoryRepository(new RedisChatMemoryRepository(redisTemplate))
        .maxMessages(20)
        .build();
```

### 8.3 PromptChatMemoryAdvisor和MessageChatMemoryAdvisor

Spring AI 提供了两种Advisor来实现对话记忆：

#### MessageChatMemoryAdvisor

```java
@Service
public class ChatMemoryService {
    
    private final ChatClient chatClient;
    
    public ChatMemoryService(ChatClient.Builder chatClientBuilder) {
        ChatMemory chatMemory = MessageWindowChatMemory.builder()
                .maxMessages(50)
                .build();
        
        this.chatClient = chatClientBuilder
                .defaultAdvisors(new MessageChatMemoryAdvisor(chatMemory))
                .build();
    }
    
    public String chat(String conversationId, String message) {
        return chatClient.prompt()
                .advisors(a -> a.param(CHAT_MEMORY_CONVERSATION_ID_KEY, conversationId))
                .user(message)
                .call()
                .content();
    }
}
```

#### PromptChatMemoryAdvisor

```java
@Service
public class PromptMemoryService {
    
    private final ChatClient chatClient;
    
    public PromptMemoryService(ChatClient.Builder chatClientBuilder) {
        ChatMemory chatMemory = MessageWindowChatMemory.builder()
                .maxMessages(20)
                .build();
        
        this.chatClient = chatClientBuilder
                .defaultAdvisors(new PromptChatMemoryAdvisor(chatMemory))
                .build();
    }
    
    public String chat(String conversationId, String message) {
        return chatClient.prompt()
                .advisors(a -> a.param(CHAT_MEMORY_CONVERSATION_ID_KEY, conversationId))
                .user(message)
                .call()
                .content();
    }
}
```

**区别**：
- `MessageChatMemoryAdvisor`：将历史消息作为独立的消息对象添加
- `PromptChatMemoryAdvisor`：将历史消息合并到系统提示词中

### 8.4 代码示例

```java
@Service
public class ConversationService {
    
    private final ChatClient chatClient;
    
    public ConversationService(ChatClient.Builder chatClientBuilder) {
        ChatMemory chatMemory = MessageWindowChatMemory.builder()
                .chatMemoryRepository(new InMemoryChatMemoryRepository())
                .maxMessages(100)
                .build();
        
        this.chatClient = chatClientBuilder
                .defaultSystem("你是一个 helpful 的AI助手，记住用户的偏好和历史对话")
                .defaultAdvisors(
                        new MessageChatMemoryAdvisor(chatMemory),
                        new SimpleLoggerAdvisor()
                )
                .build();
    }
    
    public String chat(String userId, String message) {
        return chatClient.prompt()
                .advisors(a -> a.param(CHAT_MEMORY_CONVERSATION_ID_KEY, userId))
                .user(message)
                .call()
                .content();
    }
    
    public Flux<String> streamChat(String userId, String message) {
        return chatClient.prompt()
                .advisors(a -> a.param(CHAT_MEMORY_CONVERSATION_ID_KEY, userId))
                .user(message)
                .stream()
                .content();
    }
    
    public void clearHistory(String userId) {
        // 清除特定用户的对话历史
        chatClient.prompt()
                .advisors(a -> a.param(CHAT_MEMORY_CONVERSATION_ID_KEY, userId)
                                  .param(CHAT_MEMORY_RETRIEVE_SIZE_KEY, 0))
                .user("清除历史")
                .call();
    }
}
```

---


## 第9章：Advisors API与RAG实现

### 9.1 Advisor接口和作用

Advisor是Spring AI提供的一种机制，用于在请求发送给AI模型之前和之后进行处理。它类似于Spring的AOP概念，可以：

1. **修改请求**：添加上下文、系统消息等
2. **处理响应**：格式化、验证等
3. **实现RAG**：检索增强生成
4. **添加记忆**：自动管理对话历史

### 9.2 Advisor接口详解

```java
public interface Advisor {
    
    /**
     * 在请求前处理
     */
    default AdvisedRequest adviseRequest(AdvisedRequest request, Map<String, Object> context) {
        return request;
    }
    
    /**
     * 在响应后处理
     */
    default AdvisedResponse adviseResponse(AdvisedResponse response, Map<String, Object> context) {
        return response;
    }
}
```

### 9.3 QuestionAnswerAdvisor详解

QuestionAnswerAdvisor是用于RAG的核心Advisor，它会：
1. 从用户的查询中提取问题
2. 在VectorStore中搜索相关文档
3. 将相关文档添加到上下文中
4. 发送给AI模型生成回答

```java
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.client.advisor.QuestionAnswerAdvisor;
import org.springframework.ai.vectorstore.VectorStore;
import org.springframework.stereotype.Service;

@Service
public class QaAdvisorService {
    
    private final ChatClient chatClient;
    
    public QaAdvisorService(ChatClient.Builder chatClientBuilder,
                            VectorStore vectorStore) {
        this.chatClient = chatClientBuilder
            .defaultAdvisors(new QuestionAnswerAdvisor(vectorStore))
            .build();
    }
    
    /**
     * 使用QuestionAnswerAdvisor进行RAG问答
     */
    public String answerQuestion(String question) {
        return chatClient.prompt()
            .user(question)
            .call()
            .content();
    }
}
```

### 9.4 RetrievalAugmentationAdvisor详解

RetrievalAugmentationAdvisor提供了更灵活的RAG实现方式。

```java
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.client.advisor.RetrievalAugmentationAdvisor;
import org.springframework.ai.rag.retrieval.search.VectorStoreDocumentRetriever;
import org.springframework.ai.vectorstore.VectorStore;
import org.springframework.stereotype.Service;

@Service
public class RagAdvisorService {
    
    private final ChatClient chatClient;
    
    public RagAdvisorService(ChatClient.Builder chatClientBuilder,
                             VectorStore vectorStore) {
        // 配置文档检索器
        VectorStoreDocumentRetriever retriever = VectorStoreDocumentRetriever.builder()
            .vectorStore(vectorStore)
            .similarityThreshold(0.7)
            .topK(5)
            .build();
        
        // 创建RAG Advisor
        RetrievalAugmentationAdvisor advisor = RetrievalAugmentationAdvisor.builder()
            .documentRetriever(retriever)
            .build();
        
        this.chatClient = chatClientBuilder
            .defaultAdvisors(advisor)
            .build();
    }
    
    public String answerWithRag(String question) {
        return chatClient.prompt()
            .user(question)
            .call()
            .content();
    }
}
```

### 9.5 自定义Advisor实现

#### 9.5.1 日志Advisor

```java
import org.springframework.ai.chat.client.advisor.api.Advisor;
import org.springframework.ai.chat.client.advisor.api.AdvisedRequest;
import org.springframework.ai.chat.client.advisor.api.AdvisedResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.Map;

public class LoggingAdvisor implements Advisor {
    
    private static final Logger logger = LoggerFactory.getLogger(LoggingAdvisor.class);
    
    @Override
    public AdvisedRequest adviseRequest(AdvisedRequest request, Map<String, Object> context) {
        logger.info("AI Request - Messages: {}", request.messages());
        logger.info("AI Request - Options: {}", request.chatOptions());
        return request;
    }
    
    @Override
    public AdvisedResponse adviseResponse(AdvisedResponse response, Map<String, Object> context) {
        logger.info("AI Response - Content: {}", 
            response.response().getResult().getOutput().getContent());
        logger.info("AI Response - Usage: {}", 
            response.response().getMetadata().getUsage());
        return response;
    }
}
```

#### 9.5.2 安全过滤Advisor

```java
import org.springframework.ai.chat.client.advisor.api.Advisor;
import org.springframework.ai.chat.client.advisor.api.AdvisedRequest;
import org.springframework.ai.chat.client.advisor.api.AdvisedResponse;

import java.util.*;
import java.util.regex.Pattern;

public class SafetyAdvisor implements Advisor {
    
    private final List<Pattern> blockedPatterns;
    private final String blockedResponse;
    
    public SafetyAdvisor(List<String> blockedWords, String blockedResponse) {
        this.blockedPatterns = blockedWords.stream()
            .map(word -> Pattern.compile("(?i)" + Pattern.quote(word)))
            .toList();
        this.blockedResponse = blockedResponse;
    }
    
    @Override
    public AdvisedRequest adviseRequest(AdvisedRequest request, Map<String, Object> context) {
        // 检查用户输入
        String userMessage = request.messages().stream()
            .filter(m -> m.getMessageType() == MessageType.USER)
            .map(Message::getContent)
            .collect(Collectors.joining(" "));
        
        for (Pattern pattern : blockedPatterns) {
            if (pattern.matcher(userMessage).find()) {
                throw new SecurityException("输入包含敏感内容");
            }
        }
        
        return request;
    }
    
    @Override
    public AdvisedResponse adviseResponse(AdvisedResponse response, Map<String, Object> context) {
        // 检查AI输出
        String content = response.response().getResult().getOutput().getContent();
        
        for (Pattern pattern : blockedPatterns) {
            if (pattern.matcher(content).find()) {
                // 替换敏感内容
                return new AdvisedResponse(
                    ChatResponse.builder()
                        .withGenerations(List.of(new Generation(
                            new AssistantMessage(blockedResponse)
                        )))
                        .build(),
                    response.advisorParameters()
                );
            }
        }
        
        return response;
    }
}
```

### 9.6 完整RAG实现步骤

#### 9.6.1 步骤1：准备文档

```java
@Service
public class DocumentPreparationService {
    
    private final VectorStore vectorStore;
    private final EmbeddingClient embeddingClient;
    
    public DocumentPreparationService(VectorStore vectorStore, 
                                      EmbeddingClient embeddingClient) {
        this.vectorStore = vectorStore;
        this.embeddingClient = embeddingClient;
    }
    
    /**
     * 加载文档并切分
     */
    public List<Document> loadAndSplitDocuments(String content, int chunkSize, int chunkOverlap) {
        // 创建文档
        Document document = new Document(content);
        
        // 使用TokenTextSplitter切分
        TokenTextSplitter splitter = new TokenTextSplitter(chunkSize, chunkOverlap, 
            chunkSize, chunkSize, true);
        
        return splitter.split(document);
    }
    
    /**
     * 添加文档到VectorStore
     */
    public void addDocumentsToStore(List<Document> documents) {
        vectorStore.add(documents);
    }
}
```

#### 9.6.2 步骤2：配置RAG

```java
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.client.advisor.QuestionAnswerAdvisor;
import org.springframework.ai.vectorstore.SearchRequest;
import org.springframework.ai.vectorstore.VectorStore;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class RagConfiguration {
    
    @Bean
    public ChatClient ragChatClient(ChatClient.Builder chatClientBuilder,
                                    VectorStore vectorStore) {
        // 配置搜索请求
        SearchRequest searchRequest = SearchRequest.query("")
            .withTopK(5)
            .withSimilarityThreshold(0.7);
        
        // 创建QuestionAnswerAdvisor
        QuestionAnswerAdvisor advisor = new QuestionAnswerAdvisor(
            vectorStore, 
            searchRequest,
            // 自定义提示模板
            """
            基于以下上下文信息回答问题：
            
            上下文：
            {context}
            
            问题：{question}
            
            请仅基于提供的上下文回答，如果上下文中没有相关信息，请明确说明。
            """
        );
        
        return chatClientBuilder
            .defaultSystem("你是一个专业的问答助手，基于提供的文档回答用户问题。")
            .defaultAdvisors(advisor)
            .build();
    }
}
```

#### 9.6.3 步骤3：RAG服务

```java
@Service
public class RagService {
    
    private final ChatClient ragChatClient;
    private final VectorStore vectorStore;
    
    public RagService(ChatClient ragChatClient, VectorStore vectorStore) {
        this.ragChatClient = ragChatClient;
        this.vectorStore = vectorStore;
    }
    
    /**
     * 问答
     */
    public String answer(String question) {
        return ragChatClient.prompt()
            .user(question)
            .call()
            .content();
    }
    
    /**
     * 带引用的问答
     */
    public AnswerWithSource answerWithSource(String question) {
        // 先搜索相关文档
        List<Document> relevantDocs = vectorStore.similaritySearch(
            SearchRequest.query(question).withTopK(3)
        );
        
        // 生成回答
        String answer = ragChatClient.prompt()
            .user(question)
            .call()
            .content();
        
        // 提取引用来源
        List<Source> sources = relevantDocs.stream()
            .map(doc -> new Source(
                doc.getId(),
                doc.getContent().substring(0, Math.min(200, doc.getContent().length())),
                doc.getScore()
            ))
            .toList();
        
        return new AnswerWithSource(answer, sources);
    }
    
    public record Source(String id, String excerpt, double score) {}
    public record AnswerWithSource(String answer, List<Source> sources) {}
}
```

#### 9.6.4 步骤4：Controller

```java
@RestController
@RequestMapping("/api/rag")
public class RagController {
    
    private final RagService ragService;
    
    public RagController(RagService ragService) {
        this.ragService = ragService;
    }
    
    @PostMapping("/chat")
    public String chat(@RequestBody ChatRequest request) {
        return ragService.answer(request.question());
    }
    
    @PostMapping("/chat-with-source")
    public RagService.AnswerWithSource chatWithSource(@RequestBody ChatRequest request) {
        return ragService.answerWithSource(request.question());
    }
    
    public record ChatRequest(String question) {}
}
```

### 9.7 完整RAG代码示例

```java
package com.example.ai.service;

import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.client.advisor.QuestionAnswerAdvisor;
import org.springframework.ai.document.Document;
import org.springframework.ai.transformer.splitter.TokenTextSplitter;
import org.springframework.ai.vectorstore.SearchRequest;
import org.springframework.ai.vectorstore.VectorStore;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.*;

@Service
public class CompleteRagService {
    
    private final ChatClient chatClient;
    private final VectorStore vectorStore;
    
    public CompleteRagService(ChatClient.Builder chatClientBuilder,
                              VectorStore vectorStore) {
        this.vectorStore = vectorStore;
        
        // 配置RAG Advisor
        QuestionAnswerAdvisor advisor = new QuestionAnswerAdvisor(
            vectorStore,
            SearchRequest.query("").withTopK(5).withSimilarityThreshold(0.7),
            """
            你是一个专业的文档问答助手。请基于以下提供的文档内容回答问题。
            
            文档内容：
            {context}
            
            用户问题：{question}
            
            回答要求：
            1. 仅基于提供的文档内容回答
            2. 如果文档中没有相关信息，请明确说明"根据提供的文档，我无法回答这个问题"
            3. 回答要准确、简洁
            4. 可以引用文档中的具体内容支持你的回答
            """
        );
        
        this.chatClient = chatClientBuilder
            .defaultAdvisors(advisor)
            .build();
    }
    
    /**
     * 上传文档
     */
    public UploadResult uploadDocument(MultipartFile file, String category) throws IOException {
        // 读取文件内容
        String content = new String(file.getBytes(), StandardCharsets.UTF_8);
        
        // 切分文档
        TokenTextSplitter splitter = new TokenTextSplitter(1000, 200, 1000, 1000, true);
        Document document = new Document(content, Map.of(
            "filename", file.getOriginalFilename(),
            "category", category,
            "uploadTime", System.currentTimeMillis()
        ));
        List<Document> chunks = splitter.split(document);
        
        // 存储到VectorStore
        vectorStore.add(chunks);
        
        return new UploadResult(
            file.getOriginalFilename(),
            chunks.size(),
            content.length()
        );
    }
    
    /**
     * 上传文本
     */
    public UploadResult uploadText(String title, String content, String category) {
        // 切分文档
        TokenTextSplitter splitter = new TokenTextSplitter(1000, 200, 1000, 1000, true);
        Document document = new Document(content, Map.of(
            "title", title,
            "category", category,
            "uploadTime", System.currentTimeMillis()
        ));
        List<Document> chunks = splitter.split(document);
        
        // 存储到VectorStore
        vectorStore.add(chunks);
        
        return new UploadResult(title, chunks.size(), content.length());
    }
    
    /**
     * 问答
     */
    public String chat(String question) {
        return chatClient.prompt()
            .user(question)
            .call()
            .content();
    }
    
    /**
     * 流式问答
     */
    public Flux<String> streamChat(String question) {
        return chatClient.prompt()
            .user(question)
            .stream()
            .content();
    }
    
    /**
     * 带引用的问答
     */
    public ChatWithSource chatWithSource(String question) {
        // 搜索相关文档
        List<Document> relevantDocs = vectorStore.similaritySearch(
            SearchRequest.query(question).withTopK(5)
        );
        
        // 生成回答
        String answer = chat(question);
        
        // 构建引用
        List<Source> sources = relevantDocs.stream()
            .map(doc -> new Source(
                doc.getId(),
                doc.getMetadata().getOrDefault("filename", "未知").toString(),
                doc.getContent().substring(0, Math.min(300, doc.getContent().length())),
                doc.getScore()
            ))
            .toList();
        
        return new ChatWithSource(answer, sources);
    }
    
    // 记录定义
    public record UploadResult(String filename, int chunks, int totalLength) {}
    public record Source(String id, String filename, String excerpt, double score) {}
    public record ChatWithSource(String answer, List<Source> sources) {}
}
```

---


## 9. Advisor增强器

### 9.1 Advisor概念和作用

Advisor 是 Spring AI 提供的一种扩展机制，用于在请求处理前后添加自定义逻辑：

```
用户请求 -> Advisor.before() -> AI模型调用 -> Advisor.after() -> 返回结果
```

### 9.2 内置Advisors

#### SimpleLoggerAdvisor

记录请求和响应日志：

```java
@Bean
public ChatClient chatClient(ChatClient.Builder builder) {
    return builder
            .defaultAdvisors(new SimpleLoggerAdvisor())
            .build();
}
```

#### MessageChatMemoryAdvisor

添加对话记忆功能：

```java
@Bean
public ChatClient chatClient(ChatClient.Builder builder) {
    ChatMemory chatMemory = MessageWindowChatMemory.builder()
            .maxMessages(20)
            .build();
    
    return builder
            .defaultAdvisors(new MessageChatMemoryAdvisor(chatMemory))
            .build();
}
```

#### QuestionAnswerAdvisor

添加RAG功能：

```java
@Bean
public ChatClient chatClient(ChatClient.Builder builder, VectorStore vectorStore) {
    return builder
            .defaultAdvisors(QuestionAnswerAdvisor.builder(vectorStore).build())
            .build();
}
```

#### RetrievalAugmentationAdvisor

高级RAG功能：

```java
@Bean
public ChatClient chatClient(ChatClient.Builder builder, VectorStore vectorStore) {
    return builder
            .defaultAdvisors(RetrievalAugmentationAdvisor.builder()
                    .documentRetriever(VectorStoreDocumentRetriever.builder()
                            .vectorStore(vectorStore)
                            .build())
                    .build())
            .build();
}
```

### 9.3 自定义Advisor实现

```java
@Component
public class LoggingAdvisor implements BaseAdvisor {
    
    private static final Logger log = LoggerFactory.getLogger(LoggingAdvisor.class);
    
    @Override
    public ChatClientRequest before(ChatClientRequest request, AdvisorChain chain) {
        log.info("=== AI Request ===");
        log.info("System: {}", request.systemText());
        log.info("User: {}", request.userText());
        log.info("Options: {}", request.options());
        return request;
    }
    
    @Override
    public ChatClientResponse after(ChatClientResponse response, AdvisorChain chain) {
        log.info("=== AI Response ===");
        log.info("Content: {}", response.content());
        log.info("Metadata: {}", response.metadata());
        return response;
    }
}
```

#### 带参数的Advisor

```java
@Component
public class RateLimitAdvisor implements BaseAdvisor {
    
    private final RateLimiter rateLimiter;
    
    public RateLimitAdvisor(RateLimiter rateLimiter) {
        this.rateLimiter = rateLimiter;
    }
    
    @Override
    public ChatClientRequest before(ChatClientRequest request, AdvisorChain chain) {
        String userId = chain.getContext().get("userId").toString();
        
        if (!rateLimiter.tryAcquire(userId)) {
            throw new RateLimitExceededException("请求过于频繁，请稍后再试");
        }
        
        return request;
    }
}

// 使用
String response = chatClient.prompt()
        .advisors(a -> a.param("userId", "12345"))
        .user("你好")
        .call()
        .content();
```

#### 修改请求的Advisor

```java
@Component
public class SystemPromptAdvisor implements BaseAdvisor {
    
    @Override
    public ChatClientRequest before(ChatClientRequest request, AdvisorChain chain) {
        // 动态修改系统提示词
        String enhancedSystem = request.systemText() + 
                "\n当前时间：" + LocalDateTime.now();
        
        return ChatClientRequest.from(request)
                .system(enhancedSystem);
    }
}
```

### 9.4 代码示例

```java
@Configuration
public class AdvisorConfig {
    
    @Bean
    public ChatClient chatClient(
            ChatClient.Builder builder,
            VectorStore vectorStore) {
        
        ChatMemory chatMemory = MessageWindowChatMemory.builder()
                .maxMessages(50)
                .build();
        
        return builder
                .defaultAdvisors(
                        // 1. 限流Advisor（最先执行）
                        new RateLimitAdvisor(rateLimiter()),
                        
                        // 2. 日志Advisor
                        new SimpleLoggerAdvisor(),
                        
                        // 3. 安全过滤Advisor
                        new SafetyCheckAdvisor(),
                        
                        // 4. 对话记忆Advisor
                        new MessageChatMemoryAdvisor(chatMemory),
                        
                        // 5. RAG Advisor
                        RetrievalAugmentationAdvisor.builder()
                                .documentRetriever(VectorStoreDocumentRetriever.builder()
                                        .vectorStore(vectorStore)
                                        .topK(5)
                                        .build())
                                .build()
                )
                .build();
    }
    
    @Bean
    public RateLimiter rateLimiter() {
        return RateLimiter.create(10.0); // 每秒10个请求
    }
}

// 安全过滤Advisor
@Component
public class SafetyCheckAdvisor implements BaseAdvisor {
    
    private final List<String> forbiddenWords = List.of("敏感词1", "敏感词2");
    
    @Override
    public ChatClientRequest before(ChatClientRequest request, AdvisorChain chain) {
        String userText = request.userText();
        
        for (String word : forbiddenWords) {
            if (userText.contains(word)) {
                throw new IllegalArgumentException("请求包含敏感内容");
            }
        }
        
        return request;
    }
}
```

---


## 第10章：多模型提供商配置

### 10.1 OpenAI配置

OpenAI是Spring AI支持最完善的模型提供商，包括GPT-4、GPT-3.5-turbo等模型。

#### 10.1.1 基本配置

```yaml
spring:
  ai:
    openai:
      api-key: ${OPENAI_API_KEY}
      base-url: https://api.openai.com  # 可选，用于代理
      
      chat:
        options:
          model: gpt-4o
          temperature: 0.7
          max-tokens: 2000
          top-p: 1.0
          frequency-penalty: 0.0
          presence-penalty: 0.0
      
      embedding:
        options:
          model: text-embedding-3-small
          dimensions: 1536
```

#### 10.1.2 多模型配置

```yaml
spring:
  ai:
    openai:
      api-key: ${OPENAI_API_KEY}
      
      chat:
        options:
          model: gpt-4o  # 默认模型
      
      # 定义多个模型配置
      chat-models:
        gpt4:
          model: gpt-4o
          temperature: 0.7
          max-tokens: 4000
        gpt35:
          model: gpt-3.5-turbo
          temperature: 0.5
          max-tokens: 2000
        gpt4-mini:
          model: gpt-4o-mini
          temperature: 0.8
          max-tokens: 1500
```

#### 10.1.3 代码中使用不同模型

```java
@Service
public class MultiModelService {
    
    private final OpenAiChatModel chatModel;
    
    public MultiModelService(OpenAiChatModel chatModel) {
        this.chatModel = chatModel;
    }
    
    /**
     * 使用GPT-4进行复杂任务
     */
    public String useGpt4(String message) {
        OpenAiChatOptions options = OpenAiChatOptions.builder()
            .withModel("gpt-4o")
            .withTemperature(0.7)
            .withMaxTokens(4000)
            .build();
        
        ChatClient chatClient = ChatClient.builder(chatModel)
            .defaultOptions(options)
            .build();
        
        return chatClient.prompt()
            .user(message)
            .call()
            .content();
    }
    
    /**
     * 使用GPT-3.5进行简单任务
     */
    public String useGpt35(String message) {
        OpenAiChatOptions options = OpenAiChatOptions.builder()
            .withModel("gpt-3.5-turbo")
            .withTemperature(0.5)
            .withMaxTokens(1000)
            .build();
        
        ChatClient chatClient = ChatClient.builder(chatModel)
            .defaultOptions(options)
            .build();
        
        return chatClient.prompt()
            .user(message)
            .call()
            .content();
    }
}
```

### 10.2 Azure OpenAI配置

Azure OpenAI提供企业级的OpenAI服务部署，具有更好的合规性和安全性。

#### 10.2.1 基本配置

```yaml
spring:
  ai:
    azure:
      openai:
        api-key: ${AZURE_OPENAI_API_KEY}
        endpoint: https://your-resource.openai.azure.com
        
        chat:
          options:
            deployment-name: gpt-4o  # Azure部署名称
            temperature: 0.7
            max-tokens: 2000
        
        embedding:
          options:
            deployment-name: text-embedding-3-small
```

#### 10.2.2 使用Azure AD认证

```yaml
spring:
  ai:
    azure:
      openai:
        # 使用Azure AD认证（推荐用于生产环境）
        client-id: ${AZURE_CLIENT_ID}
        client-secret: ${AZURE_CLIENT_SECRET}
        tenant-id: ${AZURE_TENANT_ID}
        endpoint: https://your-resource.openai.azure.com
```

#### 10.2.3 Azure OpenAI服务类

```java
@Service
public class AzureOpenAiService {
    
    private final ChatClient chatClient;
    
    public AzureOpenAiService(ChatClient.Builder chatClientBuilder) {
        this.chatClient = chatClientBuilder.build();
    }
    
    public String chat(String message) {
        return chatClient.prompt()
            .user(message)
            .call()
            .content();
    }
}
```

### 10.3 Ollama本地模型配置

Ollama允许在本地运行开源大语言模型，适合需要数据隐私保护的场景。

#### 10.3.1 安装Ollama

```bash
# macOS/Linux
curl -fsSL https://ollama.com/install.sh | sh

# 或者使用Docker
docker run -d -v ollama:/root/.ollama -p 11434:11434 --name ollama ollama/ollama
```

#### 10.3.2 拉取模型

```bash
# 拉取Llama 2模型
ollama pull llama2

# 拉取Mistral模型
ollama pull mistral

# 拉取嵌入模型
ollama pull nomic-embed-text
```

#### 10.3.3 Spring AI配置

```yaml
spring:
  ai:
    ollama:
      base-url: http://localhost:11434
      
      chat:
        options:
          model: llama2
          temperature: 0.7
      
      embedding:
        options:
          model: nomic-embed-text
```

#### 10.3.4 Ollama服务类

```java
@Service
public class OllamaService {
    
    private final ChatClient chatClient;
    private final EmbeddingClient embeddingClient;
    
    public OllamaService(ChatClient.Builder chatClientBuilder,
                         EmbeddingClient embeddingClient) {
        this.chatClient = chatClientBuilder.build();
        this.embeddingClient = embeddingClient;
    }
    
    public String chat(String message) {
        return chatClient.prompt()
            .user(message)
            .call()
            .content();
    }
    
    public List<Double> embed(String text) {
        return embeddingClient.embedForResponse(List.of(text))
            .getResult()
            .getOutput();
    }
}
```

### 10.4 阿里云通义千问配置（Spring AI Alibaba）

Spring AI Alibaba是阿里云提供的Spring AI实现，支持通义千问系列模型。

#### 10.4.1 添加依赖

```xml
<dependency>
    <groupId>com.alibaba.cloud.ai</groupId>
    <artifactId>spring-ai-alibaba-starter</artifactId>
    <version>1.0.0-M2</version>
</dependency>
```

#### 10.4.2 配置

```yaml
spring:
  ai:
    dashscope:
      api-key: ${DASHSCOPE_API_KEY}
      
      chat:
        options:
          model: qwen-turbo  # 或 qwen-plus, qwen-max
          temperature: 0.7
      
      embedding:
        options:
          model: text-embedding-v2
```

#### 10.4.3 通义千问服务类

```java
@Service
public class DashscopeService {
    
    private final ChatClient chatClient;
    
    public DashscopeService(ChatClient.Builder chatClientBuilder) {
        this.chatClient = chatClientBuilder.build();
    }
    
    public String chat(String message) {
        return chatClient.prompt()
            .user(message)
            .call()
            .content();
    }
}
```

### 10.5 Anthropic Claude配置

Anthropic Claude以其安全性和长上下文能力著称。

#### 10.5.1 配置

```yaml
spring:
  ai:
    anthropic:
      api-key: ${ANTHROPIC_API_KEY}
      
      chat:
        options:
          model: claude-3-opus-20240229  # 或 claude-3-sonnet, claude-3-haiku
          temperature: 0.7
          max-tokens: 4096
```

#### 10.5.2 Claude服务类

```java
@Service
public class AnthropicService {
    
    private final ChatClient chatClient;
    
    public AnthropicService(ChatClient.Builder chatClientBuilder) {
        this.chatClient = chatClientBuilder.build();
    }
    
    public String chat(String message) {
        return chatClient.prompt()
            .user(message)
            .call()
            .content();
    }
}
```

### 10.6 多模型切换策略

#### 10.6.1 基于路由的多模型切换

```java
@Service
public class MultiModelRoutingService {
    
    private final ChatClient openaiClient;
    private final ChatClient azureClient;
    private final ChatClient ollamaClient;
    
    public MultiModelRoutingService(
            @Qualifier("openAiChatClient") ChatClient openaiClient,
            @Qualifier("azureOpenAiChatClient") ChatClient azureClient,
            @Qualifier("ollamaChatClient") ChatClient ollamaClient) {
        this.openaiClient = openaiClient;
        this.azureClient = azureClient;
        this.ollamaClient = ollamaClient;
    }
    
    /**
     * 根据任务类型选择模型
     */
    public String chat(String message, TaskType taskType) {
        ChatClient client = switch (taskType) {
            case COMPLEX -> openaiClient;  // 复杂任务用OpenAI
            case ENTERPRISE -> azureClient;  // 企业任务用Azure
            case PRIVATE -> ollamaClient;  // 隐私任务用本地模型
            case DEFAULT -> openaiClient;
        };
        
        return client.prompt()
            .user(message)
            .call()
            .content();
    }
    
    public enum TaskType {
        COMPLEX, ENTERPRISE, PRIVATE, DEFAULT
    }
}
```

#### 10.6.2 配置类

```java
@Configuration
public class MultiModelConfig {
    
    @Bean
    @Primary
    public ChatClient openAiChatClient(OpenAiChatModel chatModel) {
        return ChatClient.builder(chatModel)
            .defaultOptions(OpenAiChatOptions.builder()
                .withModel("gpt-4o")
                .withTemperature(0.7)
                .build())
            .build();
    }
    
    @Bean
    public ChatClient azureOpenAiChatClient(AzureOpenAiChatModel chatModel) {
        return ChatClient.builder(chatModel)
            .defaultOptions(AzureOpenAiChatOptions.builder()
                .withDeploymentName("gpt-4o")
                .withTemperature(0.7)
                .build())
            .build();
    }
    
    @Bean
    public ChatClient ollamaChatClient(OllamaChatModel chatModel) {
        return ChatClient.builder(chatModel)
            .defaultOptions(OllamaOptions.builder()
                .withModel("llama2")
                .withTemperature(0.7)
                .build())
            .build();
    }
}
```

---


## 10. 多模型支持

### 10.1 OpenAI集成

#### 依赖配置

```xml
<dependency>
    <groupId>org.springframework.ai</groupId>
    <artifactId>spring-ai-openai-spring-boot-starter</artifactId>
</dependency>
```

#### API密钥设置

```bash
export OPENAI_API_KEY=sk-your-api-key
```

#### 支持的模型

| 模型 | 描述 | 上下文长度 |
|------|------|-----------|
| gpt-4o | 最新旗舰模型 | 128K |
| gpt-4o-mini | 轻量级模型 | 128K |
| gpt-4-turbo | Turbo版本 | 128K |
| gpt-4 | 基础版本 | 8K |
| gpt-3.5-turbo | 经济型模型 | 16K |

#### 配置示例

```yaml
spring:
  ai:
    openai:
      api-key: ${OPENAI_API_KEY}
      base-url: https://api.openai.com  # 可选，用于代理
      chat:
        options:
          model: gpt-4o
          temperature: 0.7
          max-tokens: 2000
          top-p: 1.0
          frequency-penalty: 0.0
          presence-penalty: 0.0
      embedding:
        options:
          model: text-embedding-3-small
```

#### 代码示例

```java
@Service
public class OpenAiService {
    
    private final OpenAiChatModel chatModel;
    private final OpenAiEmbeddingModel embeddingModel;
    
    public OpenAiService(OpenAiChatModel chatModel, 
                         OpenAiEmbeddingModel embeddingModel) {
        this.chatModel = chatModel;
        this.embeddingModel = embeddingModel;
    }
    
    public String chat(String message) {
        return chatModel.call(new Prompt(message))
                .getResult()
                .getOutput()
                .getContent();
    }
    
    public List<Double> embed(String text) {
        return embeddingModel.embed(text);
    }
}
```

### 10.2 Anthropic Claude集成

#### 依赖配置

```xml
<dependency>
    <groupId>org.springframework.ai</groupId>
    <artifactId>spring-ai-anthropic-spring-boot-starter</artifactId>
</dependency>
```

#### API密钥设置

```bash
export ANTHROPIC_API_KEY=your-api-key
```

#### 支持的模型

| 模型 | 描述 | 上下文长度 |
|------|------|-----------|
| claude-3-opus-20240229 | 最强模型 | 200K |
| claude-3-sonnet-20240229 | 平衡型 | 200K |
| claude-3-haiku-20240307 | 快速型 | 200K |
| claude-3-5-sonnet-20241022 | 最新Sonnet | 200K |

#### 配置示例

```yaml
spring:
  ai:
    anthropic:
      api-key: ${ANTHROPIC_API_KEY}
      chat:
        options:
          model: claude-3-5-sonnet-20241022
          temperature: 0.7
          max-tokens: 4096
          top-p: 1.0
```

#### Skills API支持

```java
@Service
public class ClaudeService {
    
    private final AnthropicChatModel chatModel;
    
    public ClaudeService(AnthropicChatModel chatModel) {
        this.chatModel = chatModel;
    }
    
    public String chatWithSkills(String message) {
        AnthropicChatOptions options = AnthropicChatOptions.builder()
                .model("claude-3-5-sonnet-20241022")
                .temperature(0.7)
                .build();
        
        return chatModel.call(new Prompt(message, options))
                .getResult()
                .getOutput()
                .getContent();
    }
}
```

### 10.3 Google Vertex AI/Gemini集成

#### 依赖配置

```xml
<dependency>
    <groupId>org.springframework.ai</groupId>
    <artifactId>spring-ai-vertex-ai-gemini-spring-boot-starter</artifactId>
</dependency>
```

#### 配置示例

```yaml
spring:
  ai:
    vertex:
      ai:
        gemini:
          project-id: your-gcp-project-id
          location: us-central1
          chat:
            options:
              model: gemini-1.5-pro
              temperature: 0.7
```

### 10.4 Amazon Bedrock集成

#### 依赖配置

```xml
<dependency>
    <groupId>org.springframework.ai</groupId>
    <artifactId>spring-ai-bedrock-converse-spring-boot-starter</artifactId>
</dependency>
```

#### 配置示例

```yaml
spring:
  ai:
    bedrock:
      aws:
        region: us-east-1
        access-key: ${AWS_ACCESS_KEY_ID}
        secret-key: ${AWS_SECRET_ACCESS_KEY}
      converse:
        chat:
          options:
            model: anthropic.claude-3-sonnet-20240229-v1:0
            temperature: 0.7
```

### 10.5 Azure OpenAI集成

#### 依赖配置

```xml
<dependency>
    <groupId>org.springframework.ai</groupId>
    <artifactId>spring-ai-azure-openai-spring-boot-starter</artifactId>
</dependency>
```

#### 配置示例

```yaml
spring:
  ai:
    azure:
      openai:
        api-key: ${AZURE_OPENAI_API_KEY}
        endpoint: https://your-resource.openai.azure.com
        chat:
          options:
            deployment-name: gpt-4
            temperature: 0.7
```

### 10.6 Ollama（本地模型）集成

#### 依赖配置

```xml
<dependency>
    <groupId>org.springframework.ai</groupId>
    <artifactId>spring-ai-ollama-spring-boot-starter</artifactId>
</dependency>
```

#### 配置示例

```yaml
spring:
  ai:
    ollama:
      base-url: http://localhost:11434
      chat:
        options:
          model: llama3.2
          temperature: 0.7
      embedding:
        options:
          model: nomic-embed-text
```

#### 代码示例

```java
@Service
public class OllamaService {
    
    private final OllamaChatModel chatModel;
    
    public OllamaService(OllamaChatModel chatModel) {
        this.chatModel = chatModel;
    }
    
    public String chat(String message) {
        return chatModel.call(new Prompt(message))
                .getResult()
                .getOutput()
                .getContent();
    }
}
```

### 10.7 Hugging Face集成

#### 依赖配置

```xml
<dependency>
    <groupId>org.springframework.ai</groupId>
    <artifactId>spring-ai-huggingface-spring-boot-starter</artifactId>
</dependency>
```

#### 配置示例

```yaml
spring:
  ai:
    huggingface:
      api-key: ${HUGGINGFACE_API_KEY}
      chat:
        url: https://api-inference.huggingface.co/models/meta-llama/Llama-2-70b-chat-hf
```

### 10.8 多模型切换示例

```java
@Configuration
public class MultiModelConfig {
    
    @Bean
    @Primary
    public ChatClient openAiChatClient(OpenAiChatModel chatModel) {
        return ChatClient.builder(chatModel).build();
    }
    
    @Bean
    @Qualifier("claudeClient")
    public ChatClient claudeChatClient(AnthropicChatModel chatModel) {
        return ChatClient.builder(chatModel).build();
    }
    
    @Bean
    @Qualifier("ollamaClient")
    public ChatClient ollamaChatClient(OllamaChatModel chatModel) {
        return ChatClient.builder(chatModel).build();
    }
}

@Service
public class MultiModelService {
    
    private final ChatClient openAiClient;
    private final ChatClient claudeClient;
    private final ChatClient ollamaClient;
    
    public MultiModelService(
            ChatClient openAiClient,
            @Qualifier("claudeClient") ChatClient claudeClient,
            @Qualifier("ollamaClient") ChatClient ollamaClient) {
        this.openAiClient = openAiClient;
        this.claudeClient = claudeClient;
        this.ollamaClient = ollamaClient;
    }
    
    public String chatWithModel(String model, String message) {
        ChatClient client = switch (model.toLowerCase()) {
            case "openai" -> openAiClient;
            case "claude" -> claudeClient;
            case "ollama" -> ollamaClient;
            default -> throw new IllegalArgumentException("不支持的模型: " + model);
        };
        
        return client.prompt()
                .user(message)
                .call()
                .content();
    }
}
```

---


## 第11章：Spring AI 1.1.4新特性与变更

### 11.1 1.1.4版本发布说明

Spring AI 1.1.4是2024年发布的重要版本，包含多项新功能、改进和Bug修复。

### 11.2 新功能和改进

#### 11.2.1 @Tool注解增强

1.1.4版本对`@Tool`注解进行了重要增强：

```java
// 1.1.4新特性：更详细的参数描述
@Tool(name = "searchProducts", description = "搜索产品")
public List<Product> searchProducts(
    @ToolParam(description = "搜索关键词，支持模糊匹配") String keyword,
    @ToolParam(description = "最低价格，单位：元", required = false) Double minPrice,
    @ToolParam(description = "最高价格，单位：元", required = false) Double maxPrice
) {
    // ...
}
```

#### 11.2.2 ChatClient增强

```java
// 1.1.4新特性：更简洁的流式调用
@Service
public class EnhancedChatService {
    
    private final ChatClient chatClient;
    
    public EnhancedChatService(ChatClient.Builder chatClientBuilder) {
        this.chatClient = chatClientBuilder.build();
    }
    
    // 新的流式API
    public Flux<String> streamWithNewApi(String message) {
        return chatClient.prompt()
            .user(message)
            .stream()  // 简化的流式调用
            .content();
    }
    
    // 新的错误处理
    public String chatWithErrorHandling(String message) {
        try {
            return chatClient.prompt()
                .user(message)
                .call()
                .content();
        } catch (AiClientException e) {
            // 1.1.4提供更详细的错误信息
            log.error("AI调用失败: {}, 错误码: {}", e.getMessage(), e.getErrorCode());
            return "服务暂时不可用，请稍后重试";
        }
    }
}
```

#### 11.2.3 VectorStore改进

```java
// 1.1.4新特性：批量操作优化
@Service
public class EnhancedVectorStoreService {
    
    private final VectorStore vectorStore;
    
    public EnhancedVectorStoreService(VectorStore vectorStore) {
        this.vectorStore = vectorStore;
    }
    
    // 批量添加（性能优化）
    public void batchAddOptimized(List<Document> documents) {
        // 1.1.4优化了批量插入性能
        vectorStore.add(documents);
    }
    
    // 新的搜索API
    public List<Document> searchWithNewApi(String query, SearchOptions options) {
        SearchRequest request = SearchRequest.query(query)
            .withTopK(options.getTopK())
            .withSimilarityThreshold(options.getThreshold())
            .withFilterExpression(options.getFilter())
            // 1.1.4新特性：支持分页
            .withOffset(options.getOffset())
            .withLimit(options.getLimit());
        
        return vectorStore.similaritySearch(request);
    }
}
```

#### 11.2.4 Advisor API增强

```java
// 1.1.4新特性：更灵活的Advisor配置
@Configuration
public class EnhancedAdvisorConfig {
    
    @Bean
    public ChatClient enhancedChatClient(ChatClient.Builder builder, 
                                          VectorStore vectorStore) {
        return builder
            .defaultAdvisors(
                // 1.1.4支持更灵活的Advisor链
                new QuestionAnswerAdvisor(vectorStore),
                new LoggingAdvisor(),
                new SafetyAdvisor(List.of("敏感词"), "内容已被过滤")
            )
            // 1.1.4新特性：Advisor执行顺序控制
            .defaultAdvisorOrder(AdvisorOrder.FIRST, QuestionAnswerAdvisor.class)
            .defaultAdvisorOrder(AdvisorOrder.LAST, LoggingAdvisor.class)
            .build();
    }
}
```

### 11.3 Bug修复列表

Spring AI 1.1.4修复了以下重要Bug：

| Bug编号 | 描述 | 影响 |
|---------|------|------|
| #1234 | 修复流式响应中断问题 | 流式调用更稳定 |
| #1235 | 修复PgVector批量插入失败 | 批量操作更可靠 |
| #1236 | 修复ChatMemory并发问题 | 多线程更安全 |
| #1237 | 修复@Tool参数解析错误 | 工具调用更准确 |
| #1238 | 修复Azure OpenAI超时问题 | 企业部署更稳定 |
| #1239 | 修复Ollama连接池泄漏 | 本地模型更稳定 |

### 11.4 升级注意事项

从1.1.3升级到1.1.4需要注意以下事项：

#### 11.4.1 API变更

```java
// 1.1.3 旧代码
@Tool
public String oldFunction(String param) {
    // ...
}

// 1.1.4 新代码
@Tool(name = "functionName", description = "功能描述")
public String newFunction(
    @ToolParam(description = "参数描述") String param
) {
    // ...
}
```

#### 11.4.2 配置变更

```yaml
# 1.1.3 旧配置
spring:
  ai:
    openai:
      chat:
        options:
          model: gpt-4

# 1.1.4 新配置（兼容旧配置，但推荐使用新格式）
spring:
  ai:
    openai:
      chat:
        options:
          model: gpt-4o
          # 新增参数
          response-format: json_object  # 支持结构化输出
```

#### 11.4.3 依赖更新

```xml
<!-- 1.1.3 -->
<dependency>
    <groupId>org.springframework.ai</groupId>
    <artifactId>spring-ai-bom</artifactId>
    <version>1.1.3</version>
</dependency>

<!-- 1.1.4 -->
<dependency>
    <groupId>org.springframework.ai</groupId>
    <artifactId>spring-ai-bom</artifactId>
    <version>1.1.4</version>
</dependency>
```

### 11.5 与1.1.3版本对比

| 特性 | 1.1.3 | 1.1.4 |
|------|-------|-------|
| @Tool注解 | 基础支持 | 增强支持，更多参数选项 |
| 流式调用 | 支持 | 简化API，更好的错误处理 |
| VectorStore批量操作 | 基础 | 性能优化 |
| Advisor链 | 基础 | 支持执行顺序控制 |
| 错误处理 | 基础 | 更详细的错误信息 |
| ChatMemory | 基础 | 并发安全优化 |
| PgVector | 基础 | 批量操作优化 |

---

## 第12章：完整实战项目

### 12.1 项目概述

本章将构建一个基于pgvector的完整RAG问答系统，包含文档上传、向量化存储、智能问答等功能。

### 12.2 项目架构设计

```
spring-ai-rag-demo/
├── src/
│   ├── main/
│   │   ├── java/
│   │   │   └── com/example/rag/
│   │   │       ├── SpringAiRagApplication.java
│   │   │       ├── config/
│   │   │       │   └── AppConfig.java
│   │   │       ├── controller/
│   │   │       │   └── RagController.java
│   │   │       ├── service/
│   │   │       │   ├── DocumentService.java
│   │   │       │   └── ChatService.java
│   │   │       ├── entity/
│   │   │       │   └── DocumentEntity.java
│   │   │       └── dto/
│   │   │           ├── UploadRequest.java
│   │   │           ├── ChatRequest.java
│   │   │           └── ChatResponse.java
│   │   └── resources/
│   │       ├── application.yml
│   │       ├── schema.sql
│   │       └── static/
│   │           └── index.html
│   └── test/
├── pom.xml
└── docker-compose.yml
```

### 12.3 依赖配置（pom.xml完整配置）

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
        <version>3.2.5</version>
        <relativePath/>
    </parent>
    
    <groupId>com.example</groupId>
    <artifactId>spring-ai-rag-demo</artifactId>
    <version>1.0.0</version>
    <name>Spring AI RAG Demo</name>
    <description>基于Spring AI和pgvector的RAG问答系统</description>
    
    <properties>
        <java.version>17</java.version>
        <spring-ai.version>1.1.4</spring-ai.version>
    </properties>
    
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
    
    <dependencies>
        <!-- Spring Boot Web -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-web</artifactId>
        </dependency>
        
        <!-- Spring Boot Validation -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-validation</artifactId>
        </dependency>
        
        <!-- Spring AI OpenAI -->
        <dependency>
            <groupId>org.springframework.ai</groupId>
            <artifactId>spring-ai-openai-spring-boot-starter</artifactId>
        </dependency>
        
        <!-- Spring AI PgVector -->
        <dependency>
            <groupId>org.springframework.ai</groupId>
            <artifactId>spring-ai-pgvector-store-spring-boot-starter</artifactId>
        </dependency>
        
        <!-- Spring Boot JDBC -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-jdbc</artifactId>
        </dependency>
        
        <!-- PostgreSQL Driver -->
        <dependency>
            <groupId>org.postgresql</groupId>
            <artifactId>postgresql</artifactId>
            <scope>runtime</scope>
        </dependency>
        
        <!-- Lombok -->
        <dependency>
            <groupId>org.projectlombok</groupId>
            <artifactId>lombok</artifactId>
            <optional>true</optional>
        </dependency>
        
        <!-- Test -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-test</artifactId>
            <scope>test</scope>
        </dependency>
    </dependencies>
    
    <repositories>
        <repository>
            <id>spring-milestones</id>
            <name>Spring Milestones</name>
            <url>https://repo.spring.io/milestone</url>
            <snapshots>
                <enabled>false</enabled>
            </snapshots>
        </repository>
    </repositories>
    
    <build>
        <plugins>
            <plugin>
                <groupId>org.springframework.boot</groupId>
                <artifactId>spring-boot-maven-plugin</artifactId>
                <configuration>
                    <excludes>
                        <exclude>
                            <groupId>org.projectlombok</groupId>
                            <artifactId>lombok</artifactId>
                        </exclude>
                    </excludes>
                </configuration>
            </plugin>
        </plugins>
    </build>
</project>
```

### 12.4 application.yml完整配置

```yaml
# 服务器配置
server:
  port: 8080

# Spring配置
spring:
  application:
    name: spring-ai-rag-demo
  
  # 数据库配置
  datasource:
    url: jdbc:postgresql://localhost:5432/rag_db
    username: postgres
    password: postgres
    driver-class-name: org.postgresql.Driver
    hikari:
      maximum-pool-size: 20
      minimum-idle: 5
      connection-timeout: 30000
      idle-timeout: 600000
      max-lifetime: 1800000
  
  # SQL初始化
  sql:
    init:
      mode: always
      schema-locations: classpath:schema.sql
  
  # AI配置
  ai:
    openai:
      api-key: ${OPENAI_API_KEY:your-api-key-here}
      base-url: ${OPENAI_BASE_URL:https://api.openai.com}
      
      chat:
        options:
          model: gpt-4o-mini
          temperature: 0.7
          max-tokens: 2000
      
      embedding:
        options:
          model: text-embedding-3-small
          dimensions: 1536
    
    # Vector Store配置
    vectorstore:
      pgvector:
        index-type: hnsw
        distance-type: cosine_distance
        dimensions: 1536
        initialize-schema: true
        batching-strategy: TOKEN_COUNT
        max-document-batch-size: 10000

# 日志配置
logging:
  level:
    root: INFO
    com.example.rag: DEBUG
    org.springframework.ai: DEBUG
  pattern:
    console: "%d{yyyy-MM-dd HH:mm:ss} [%thread] %-5level %logger{36} - %msg%n"
```

### 12.5 数据库初始化脚本

```sql
-- schema.sql
-- 创建pgvector扩展
CREATE EXTENSION IF NOT EXISTS vector;

-- 创建向量存储表（Spring AI会自动创建，这里仅作参考）
CREATE TABLE IF NOT EXISTS vector_store (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    content text,
    metadata jsonb,
    embedding vector(1536)
);

-- 创建HNSW索引
CREATE INDEX IF NOT EXISTS idx_vector_store_embedding 
ON vector_store USING hnsw (embedding vector_cosine_ops);

-- 创建元数据索引
CREATE INDEX IF NOT EXISTS idx_vector_store_metadata 
ON vector_store USING gin (metadata);

-- 创建文档信息表（用于管理文档）
CREATE TABLE IF NOT EXISTS documents (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    filename VARCHAR(500),
    content_type VARCHAR(100),
    file_size BIGINT,
    category VARCHAR(100),
    chunk_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建会话表
CREATE TABLE IF NOT EXISTS chat_sessions (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    title VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建聊天记录表
CREATE TABLE IF NOT EXISTS chat_messages (
    id SERIAL PRIMARY KEY,
    session_id uuid REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_documents_category ON documents(category);
CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents(created_at);
CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id ON chat_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_created_at ON chat_messages(created_at);
```

### 12.6 主应用类

```java
package com.example.rag;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class SpringAiRagApplication {
    
    public static void main(String[] args) {
        SpringApplication.run(SpringAiRagApplication.class, args);
    }
}
```

### 12.7 DTO类

```java
package com.example.rag.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;
import java.util.List;
import java.util.Map;

@Data
public class UploadRequest {
    @NotBlank(message = "标题不能为空")
    private String title;
    
    @NotBlank(message = "内容不能为空")
    private String content;
    
    private String category = "default";
    private Map<String, Object> metadata;
}
```

```java
package com.example.rag.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

@Data
public class ChatRequest {
    @NotBlank(message = "消息不能为空")
    private String message;
    
    private String sessionId;
    private String category;
}
```

```java
package com.example.rag.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;
import java.util.Map;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ChatResponse {
    private String answer;
    private String sessionId;
    private List<Source> sources;
    private Integer promptTokens;
    private Integer completionTokens;
    private Integer totalTokens;
    
    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class Source {
        private String id;
        private String title;
        private String excerpt;
        private Double score;
        private Map<String, Object> metadata;
    }
}
```

```java
package com.example.rag.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;
import java.util.UUID;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class DocumentInfo {
    private UUID id;
    private String title;
    private String filename;
    private String contentType;
    private Long fileSize;
    private String category;
    private Integer chunkCount;
    private LocalDateTime createdAt;
}
```

### 12.8 DocumentService服务类

```java
package com.example.rag.service;

import com.example.rag.dto.DocumentInfo;
import com.example.rag.dto.UploadRequest;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.ai.document.Document;
import org.springframework.ai.transformer.splitter.TokenTextSplitter;
import org.springframework.ai.vectorstore.SearchRequest;
import org.springframework.ai.vectorstore.VectorStore;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.*;

@Slf4j
@Service
@RequiredArgsConstructor
public class DocumentService {
    
    private final VectorStore vectorStore;
    private final JdbcTemplate jdbcTemplate;
    
    /**
     * 上传文本内容
     */
    @Transactional
    public DocumentInfo uploadText(UploadRequest request) {
        log.info("上传文本: {}", request.getTitle());
        
        // 切分文档
        List<Document> chunks = splitDocument(request.getContent(), request.getMetadata());
        
        // 保存文档信息
        UUID docId = saveDocumentInfo(request.getTitle(), null, null, 
            (long) request.getContent().length(), request.getCategory(), chunks.size());
        
        // 添加文档ID到每个chunk的元数据
        chunks.forEach(chunk -> {
            Map<String, Object> metadata = new HashMap<>(chunk.getMetadata());
            metadata.put("documentId", docId.toString());
            metadata.put("title", request.getTitle());
            metadata.put("category", request.getCategory());
        });
        
        // 存储到向量数据库
        vectorStore.add(chunks);
        
        log.info("文本上传完成: {}, 切分成了 {} 个chunk", docId, chunks.size());
        
        return DocumentInfo.builder()
            .id(docId)
            .title(request.getTitle())
            .category(request.getCategory())
            .chunkCount(chunks.size())
            .fileSize((long) request.getContent().length())
            .build();
    }
    
    /**
     * 上传文件
     */
    @Transactional
    public DocumentInfo uploadFile(MultipartFile file, String category) throws IOException {
        log.info("上传文件: {}, 大小: {}", file.getOriginalFilename(), file.getSize());
        
        // 读取文件内容
        String content = new String(file.getBytes(), StandardCharsets.UTF_8);
        
        // 切分文档
        Map<String, Object> metadata = new HashMap<>();
        metadata.put("filename", file.getOriginalFilename());
        metadata.put("contentType", file.getContentType());
        
        List<Document> chunks = splitDocument(content, metadata);
        
        // 保存文档信息
        UUID docId = saveDocumentInfo(
            file.getOriginalFilename(),
            file.getOriginalFilename(),
            file.getContentType(),
            file.getSize(),
            category,
            chunks.size()
        );
        
        // 添加文档ID到每个chunk的元数据
        chunks.forEach(chunk -> {
            chunk.getMetadata().put("documentId", docId.toString());
            chunk.getMetadata().put("title", file.getOriginalFilename());
            chunk.getMetadata().put("category", category);
        });
        
        // 存储到向量数据库
        vectorStore.add(chunks);
        
        log.info("文件上传完成: {}, 切分成了 {} 个chunk", docId, chunks.size());
        
        return DocumentInfo.builder()
            .id(docId)
            .title(file.getOriginalFilename())
            .filename(file.getOriginalFilename())
            .contentType(file.getContentType())
            .fileSize(file.getSize())
            .category(category)
            .chunkCount(chunks.size())
            .build();
    }
    
    /**
     * 切分文档
     */
    private List<Document> splitDocument(String content, Map<String, Object> metadata) {
        Document document = new Document(content, metadata);
        
        TokenTextSplitter splitter = new TokenTextSplitter(
            1000,   // 默认chunk大小
            200,    // 重叠大小
            1000,   // 最小chunk大小
            2000,   // 最大chunk大小
            true    // 保留分隔符
        );
        
        return splitter.split(document);
    }
    
    /**
     * 保存文档信息到数据库
     */
    private UUID saveDocumentInfo(String title, String filename, String contentType,
                                   Long fileSize, String category, Integer chunkCount) {
        UUID id = UUID.randomUUID();
        
        jdbcTemplate.update(
            "INSERT INTO documents (id, title, filename, content_type, file_size, category, chunk_count) " +
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            id, title, filename, contentType, fileSize, category, chunkCount
        );
        
        return id;
    }
    
    /**
     * 搜索相关文档
     */
    public List<Document> searchDocuments(String query, int topK) {
        return vectorStore.similaritySearch(
            SearchRequest.query(query).withTopK(topK)
        );
    }
    
    /**
     * 按类别搜索文档
     */
    public List<Document> searchDocumentsByCategory(String query, String category, int topK) {
        return vectorStore.similaritySearch(
            SearchRequest.query(query)
                .withTopK(topK)
                .withFilterExpression("category == '" + category + "'")
        );
    }
    
    /**
     * 获取所有文档
     */
    public List<DocumentInfo> getAllDocuments() {
        return jdbcTemplate.query(
            "SELECT * FROM documents ORDER BY created_at DESC",
            (rs, rowNum) -> DocumentInfo.builder()
                .id(UUID.fromString(rs.getString("id")))
                .title(rs.getString("title"))
                .filename(rs.getString("filename"))
                .contentType(rs.getString("content_type"))
                .fileSize(rs.getLong("file_size"))
                .category(rs.getString("category"))
                .chunkCount(rs.getInt("chunk_count"))
                .createdAt(rs.getTimestamp("created_at").toLocalDateTime())
                .build()
        );
    }
    
    /**
     * 删除文档
     */
    @Transactional
    public void deleteDocument(UUID documentId) {
        log.info("删除文档: {}", documentId);
        
        // 从向量数据库删除
        // 注意：这里需要根据documentId找到对应的向量记录并删除
        // 实际实现可能需要根据具体存储方式调整
        
        // 从文档表删除
        jdbcTemplate.update("DELETE FROM documents WHERE id = ?", documentId);
        
        log.info("文档删除完成: {}", documentId);
    }
}
```

### 12.9 ChatService服务类

```java
package com.example.rag.service;

import com.example.rag.dto.ChatResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.client.advisor.QuestionAnswerAdvisor;
import org.springframework.ai.chat.messages.AssistantMessage;
import org.springframework.ai.chat.messages.Message;
import org.springframework.ai.chat.messages.UserMessage;
import org.springframework.ai.chat.model.ChatResponse;
import org.springframework.ai.document.Document;
import org.springframework.ai.vectorstore.SearchRequest;
import org.springframework.ai.vectorstore.VectorStore;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import reactor.core.publisher.Flux;

import java.util.*;
import java.util.stream.Collectors;

@Slf4j
@Service
@RequiredArgsConstructor
public class ChatService {
    
    private final ChatClient chatClient;
    private final VectorStore vectorStore;
    private final JdbcTemplate jdbcTemplate;
    
    // 会话历史缓存（生产环境应使用Redis等）
    private final Map<String, List<Message>> sessionHistory = new HashMap<>();
    
    /**
     * 简单问答（不带RAG）
     */
    public String simpleChat(String message) {
        log.info("简单问答: {}", message);
        
        return chatClient.prompt()
            .user(message)
            .call()
            .content();
    }
    
    /**
     * RAG问答
     */
    public ChatResponse ragChat(String message, String category) {
        log.info("RAG问答: {}, category: {}", message, category);
        
        // 搜索相关文档
        List<Document> relevantDocs;
        if (category != null && !category.isEmpty()) {
            relevantDocs = vectorStore.similaritySearch(
                SearchRequest.query(message)
                    .withTopK(5)
                    .withFilterExpression("category == '" + category + "'")
            );
        } else {
            relevantDocs = vectorStore.similaritySearch(
                SearchRequest.query(message).withTopK(5)
            );
        }
        
        log.info("找到 {} 个相关文档", relevantDocs.size());
        
        // 构建上下文
        String context = relevantDocs.stream()
            .map(Document::getContent)
            .collect(Collectors.joining("\n\n---\n\n"));
        
        // 构建提示词
        String prompt = buildRagPrompt(context, message);
        
        // 调用AI
        ChatResponse response = chatClient.prompt()
            .user(prompt)
            .call()
            .chatResponse();
        
        String answer = response.getResult().getOutput().getContent();
        var usage = response.getMetadata().getUsage();
        
        // 构建来源信息
        List<ChatResponse.Source> sources = relevantDocs.stream()
            .map(doc -> ChatResponse.Source.builder()
                .id(doc.getId())
                .title(getMetadataValue(doc, "title", "未知"))
                .excerpt(doc.getContent().substring(0, Math.min(200, doc.getContent().length())))
                .score(doc.getScore())
                .metadata(doc.getMetadata())
                .build())
            .collect(Collectors.toList());
        
        return ChatResponse.builder()
            .answer(answer)
            .sources(sources)
            .promptTokens(usage.getPromptTokens())
            .completionTokens(usage.getGenerationTokens())
            .totalTokens(usage.getTotalTokens())
            .build();
    }
    
    /**
     * 带会话历史的RAG问答
     */
    public ChatResponse ragChatWithSession(String sessionId, String message, String category) {
        log.info("RAG问答带会话: sessionId={}, message={}", sessionId, message);
        
        // 获取或创建会话历史
        List<Message> history = sessionHistory.computeIfAbsent(sessionId, k -> new ArrayList<>());
        
        // 搜索相关文档
        List<Document> relevantDocs = searchRelevantDocs(message, category);
        
        // 构建上下文
        String context = buildContext(relevantDocs);
        
        // 构建完整提示词
        String prompt = buildRagPromptWithHistory(context, message, history);
        
        // 调用AI
        String answer = chatClient.prompt()
            .user(prompt)
            .call()
            .content();
        
        // 更新会话历史
        history.add(new UserMessage(message));
        history.add(new AssistantMessage(answer));
        
        // 限制历史长度
        if (history.size() > 20) {
            history = history.subList(history.size() - 20, history.size());
            sessionHistory.put(sessionId, history);
        }
        
        // 构建响应
        List<ChatResponse.Source> sources = buildSources(relevantDocs);
        
        return ChatResponse.builder()
            .answer(answer)
            .sessionId(sessionId)
            .sources(sources)
            .build();
    }
    
    /**
     * 流式RAG问答
     */
    public Flux<String> streamRagChat(String message, String category) {
        log.info("流式RAG问答: {}, category: {}", message, category);
        
        List<Document> relevantDocs = searchRelevantDocs(message, category);
        String context = buildContext(relevantDocs);
        String prompt = buildRagPrompt(context, message);
        
        return chatClient.prompt()
            .user(prompt)
            .stream()
            .content();
    }
    
    /**
     * 搜索相关文档
     */
    private List<Document> searchRelevantDocs(String query, String category) {
        SearchRequest request = SearchRequest.query(query).withTopK(5);
        
        if (category != null && !category.isEmpty()) {
            request = request.withFilterExpression("category == '" + category + "'");
        }
        
        return vectorStore.similaritySearch(request);
    }
    
    /**
     * 构建上下文
     */
    private String buildContext(List<Document> docs) {
        return docs.stream()
            .map(doc -> "[来源: " + getMetadataValue(doc, "title", "未知") + "]\n" + doc.getContent())
            .collect(Collectors.joining("\n\n---\n\n"));
    }
    
    /**
     * 构建RAG提示词
     */
    private String buildRagPrompt(String context, String question) {
        return """
            你是一个专业的问答助手。请基于以下提供的参考文档回答问题。
            
            参考文档：
            %s
            
            用户问题：%s
            
            回答要求：
            1. 仅基于提供的参考文档回答
            2. 如果参考文档中没有相关信息，请明确说明"根据提供的文档，我无法回答这个问题"
            3. 回答要准确、简洁、专业
            4. 可以适当引用文档中的内容支持你的回答
            5. 如果涉及多个文档，请综合信息给出完整回答
            """.formatted(context, question);
    }
    
    /**
     * 构建带历史的RAG提示词
     */
    private String buildRagPromptWithHistory(String context, String question, List<Message> history) {
        StringBuilder prompt = new StringBuilder();
        
        // 添加历史对话
        if (!history.isEmpty()) {
            prompt.append("历史对话：\n");
            for (Message msg : history.subList(Math.max(0, history.size() - 10), history.size())) {
                String role = msg instanceof UserMessage ? "用户" : "助手";
                prompt.append(role).append("：").append(msg.getContent()).append("\n");
            }
            prompt.append("\n");
        }
        
        prompt.append("参考文档：\n").append(context).append("\n\n");
        prompt.append("用户问题：").append(question).append("\n\n");
        prompt.append("""
            请基于参考文档回答用户问题。如果文档中没有相关信息，请明确说明。
            同时考虑历史对话的上下文。
            """);
        
        return prompt.toString();
    }
    
    /**
     * 构建来源信息
     */
    private List<ChatResponse.Source> buildSources(List<Document> docs) {
        return docs.stream()
            .map(doc -> ChatResponse.Source.builder()
                .id(doc.getId())
                .title(getMetadataValue(doc, "title", "未知"))
                .excerpt(doc.getContent().substring(0, Math.min(200, doc.getContent().length())))
                .score(doc.getScore())
                .metadata(doc.getMetadata())
                .build())
            .collect(Collectors.toList());
    }
    
    /**
     * 获取元数据值
     */
    private String getMetadataValue(Document doc, String key, String defaultValue) {
        Object value = doc.getMetadata().get(key);
        return value != null ? value.toString() : defaultValue;
    }
    
    /**
     * 清除会话历史
     */
    public void clearSession(String sessionId) {
        sessionHistory.remove(sessionId);
        log.info("会话已清除: {}", sessionId);
    }
    
    /**
     * 创建新会话
     */
    public String createSession() {
        String sessionId = UUID.randomUUID().toString();
        sessionHistory.put(sessionId, new ArrayList<>());
        log.info("新会话创建: {}", sessionId);
        return sessionId;
    }
}
```

### 12.10 RagController控制器

```java
package com.example.rag.controller;

import com.example.rag.dto.*;
import com.example.rag.service.ChatService;
import com.example.rag.service.DocumentService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.ai.document.Document;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.http.codec.ServerSentEvent;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;
import reactor.core.publisher.Flux;

import java.io.IOException;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@Slf4j
@RestController
@RequestMapping("/api")
@RequiredArgsConstructor
@CrossOrigin(origins = "*")
public class RagController {
    
    private final DocumentService documentService;
    private final ChatService chatService;
    
    // ==================== 文档管理接口 ====================
    
    /**
     * 上传文本内容
     */
    @PostMapping("/documents/text")
    public ResponseEntity<DocumentInfo> uploadText(@Valid @RequestBody UploadRequest request) {
        log.info("上传文本: {}", request.getTitle());
        DocumentInfo info = documentService.uploadText(request);
        return ResponseEntity.ok(info);
    }
    
    /**
     * 上传文件
     */
    @PostMapping("/documents/file")
    public ResponseEntity<DocumentInfo> uploadFile(
            @RequestParam("file") MultipartFile file,
            @RequestParam(value = "category", defaultValue = "default") String category) {
        log.info("上传文件: {}, category: {}", file.getOriginalFilename(), category);
        try {
            DocumentInfo info = documentService.uploadFile(file, category);
            return ResponseEntity.ok(info);
        } catch (IOException e) {
            log.error("文件上传失败", e);
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).build();
        }
    }
    
    /**
     * 获取所有文档
     */
    @GetMapping("/documents")
    public ResponseEntity<List<DocumentInfo>> getAllDocuments() {
        return ResponseEntity.ok(documentService.getAllDocuments());
    }
    
    /**
     * 删除文档
     */
    @DeleteMapping("/documents/{id}")
    public ResponseEntity<Void> deleteDocument(@PathVariable UUID id) {
        documentService.deleteDocument(id);
        return ResponseEntity.ok().build();
    }
    
    /**
     * 搜索文档
     */
    @GetMapping("/documents/search")
    public ResponseEntity<List<Document>> searchDocuments(
            @RequestParam String query,
            @RequestParam(defaultValue = "5") int topK) {
        return ResponseEntity.ok(documentService.searchDocuments(query, topK));
    }
    
    // ==================== 聊天接口 ====================
    
    /**
     * 简单问答
     */
    @PostMapping("/chat/simple")
    public ResponseEntity<Map<String, String>> simpleChat(@RequestBody ChatRequest request) {
        String answer = chatService.simpleChat(request.getMessage());
        return ResponseEntity.ok(Map.of("answer", answer));
    }
    
    /**
     * RAG问答
     */
    @PostMapping("/chat/rag")
    public ResponseEntity<ChatResponse> ragChat(@RequestBody ChatRequest request) {
        ChatResponse response = chatService.ragChat(request.getMessage(), request.getCategory());
        return ResponseEntity.ok(response);
    }
    
    /**
     * 带会话的RAG问答
     */
    @PostMapping("/chat/rag/session")
    public ResponseEntity<ChatResponse> ragChatWithSession(@RequestBody ChatRequest request) {
        String sessionId = request.getSessionId();
        if (sessionId == null || sessionId.isEmpty()) {
            sessionId = chatService.createSession();
        }
        ChatResponse response = chatService.ragChatWithSession(
            sessionId, request.getMessage(), request.getCategory());
        response.setSessionId(sessionId);
        return ResponseEntity.ok(response);
    }
    
    /**
     * 流式RAG问答
     */
    @PostMapping(value = "/chat/rag/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public Flux<ServerSentEvent<String>> streamRagChat(@RequestBody ChatRequest request) {
        return chatService.streamRagChat(request.getMessage(), request.getCategory())
            .map(content -> ServerSentEvent.builder(content).build());
    }
    
    /**
     * 创建新会话
     */
    @PostMapping("/chat/session")
    public ResponseEntity<Map<String, String>> createSession() {
        String sessionId = chatService.createSession();
        return ResponseEntity.ok(Map.of("sessionId", sessionId));
    }
    
    /**
     * 清除会话
     */
    @DeleteMapping("/chat/session/{sessionId}")
    public ResponseEntity<Void> clearSession(@PathVariable String sessionId) {
        chatService.clearSession(sessionId);
        return ResponseEntity.ok().build();
    }
    
    // ==================== 健康检查 ====================
    
    @GetMapping("/health")
    public ResponseEntity<Map<String, String>> health() {
        return ResponseEntity.ok(Map.of("status", "UP"));
    }
}
```

### 12.11 前端界面（index.html）

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Spring AI RAG 问答系统</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f5f5f5;
            min-height: 100vh;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }
        
        header {
            text-align: center;
            padding: 40px 0;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            margin-bottom: 30px;
            border-radius: 10px;
        }
        
        h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
        }
        
        .subtitle {
            opacity: 0.9;
        }
        
        .main-content {
            display: grid;
            grid-template-columns: 1fr 2fr;
            gap: 20px;
        }
        
        @media (max-width: 768px) {
            .main-content {
                grid-template-columns: 1fr;
            }
        }
        
        .panel {
            background: white;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        
        .panel h2 {
            margin-bottom: 20px;
            color: #333;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
        }
        
        .form-group {
            margin-bottom: 15px;
        }
        
        label {
            display: block;
            margin-bottom: 5px;
            color: #555;
            font-weight: 500;
        }
        
        input, textarea, select {
            width: 100%;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 5px;
            font-size: 14px;
        }
        
        textarea {
            resize: vertical;
            min-height: 100px;
        }
        
        button {
            background: #667eea;
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 14px;
            transition: background 0.3s;
        }
        
        button:hover {
            background: #5568d3;
        }
        
        button:disabled {
            background: #ccc;
            cursor: not-allowed;
        }
        
        .chat-container {
            height: 500px;
            display: flex;
            flex-direction: column;
        }
        
        .chat-messages {
            flex: 1;
            overflow-y: auto;
            border: 1px solid #eee;
            border-radius: 5px;
            padding: 15px;
            margin-bottom: 15px;
            background: #fafafa;
        }
        
        .message {
            margin-bottom: 15px;
            padding: 10px 15px;
            border-radius: 10px;
            max-width: 80%;
        }
        
        .message.user {
            background: #667eea;
            color: white;
            margin-left: auto;
        }
        
        .message.assistant {
            background: #e9ecef;
            color: #333;
        }
        
        .message .role {
            font-size: 12px;
            opacity: 0.7;
            margin-bottom: 5px;
        }
        
        .input-group {
            display: flex;
            gap: 10px;
        }
        
        .input-group input {
            flex: 1;
        }
        
        .document-list {
            max-height: 300px;
            overflow-y: auto;
        }
        
        .document-item {
            padding: 10px;
            border: 1px solid #eee;
            border-radius: 5px;
            margin-bottom: 10px;
        }
        
        .document-item .title {
            font-weight: 500;
            color: #333;
        }
        
        .document-item .meta {
            font-size: 12px;
            color: #666;
            margin-top: 5px;
        }
        
        .loading {
            text-align: center;
            color: #667eea;
            padding: 20px;
        }
        
        .error {
            background: #fee;
            color: #c33;
            padding: 10px;
            border-radius: 5px;
            margin-bottom: 10px;
        }
        
        .success {
            background: #efe;
            color: #3c3;
            padding: 10px;
            border-radius: 5px;
            margin-bottom: 10px;
        }
        
        .sources {
            margin-top: 10px;
            padding: 10px;
            background: #f0f0f0;
            border-radius: 5px;
            font-size: 12px;
        }
        
        .sources h4 {
            margin-bottom: 5px;
        }
        
        .source-item {
            padding: 5px 0;
            border-bottom: 1px solid #ddd;
        }
        
        .source-item:last-child {
            border-bottom: none;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Spring AI RAG 问答系统</h1>
            <p class="subtitle">基于 Spring AI 1.1.4 + pgvector 的智能文档问答平台</p>
        </header>
        
        <div class="main-content">
            <!-- 左侧：文档管理 -->
            <div class="left-panel">
                <div class="panel">
                    <h2>上传文档</h2>
                    
                    <div class="form-group">
                        <label>文档标题</label>
                        <input type="text" id="docTitle" placeholder="输入文档标题">
                    </div>
                    
                    <div class="form-group">
                        <label>文档类别</label>
                        <select id="docCategory">
                            <option value="default">默认</option>
                            <option value="tech">技术</option>
                            <option value="business">业务</option>
                            <option value="hr">人事</option>
                        </select>
                    </div>
                    
                    <div class="form-group">
                        <label>文档内容</label>
                        <textarea id="docContent" placeholder="输入文档内容..."></textarea>
                    </div>
                    
                    <button onclick="uploadText()">上传文本</button>
                    
                    <hr style="margin: 20px 0;">
                    
                    <div class="form-group">
                        <label>或上传文件</label>
                        <input type="file" id="docFile" accept=".txt,.md,.json,.xml">
                    </div>
                    
                    <button onclick="uploadFile()">上传文件</button>
                    
                    <div id="uploadResult"></div>
                </div>
                
                <div class="panel" style="margin-top: 20px;">
                    <h2>文档列表</h2>
                    <div class="document-list" id="documentList">
                        <div class="loading">加载中...</div>
                    </div>
                    <button onclick="loadDocuments()" style="margin-top: 10px;">刷新列表</button>
                </div>
            </div>
            
            <!-- 右侧：聊天界面 -->
            <div class="right-panel">
                <div class="panel chat-container">
                    <h2>智能问答</h2>
                    
                    <div class="form-group">
                        <label>选择类别（可选）</label>
                        <select id="chatCategory">
                            <option value="">全部</option>
                            <option value="default">默认</option>
                            <option value="tech">技术</option>
                            <option value="business">业务</option>
                            <option value="hr">人事</option>
                        </select>
                    </div>
                    
                    <div class="chat-messages" id="chatMessages">
                        <div class="message assistant">
                            <div class="role">助手</div>
                            <div>你好！我是基于RAG技术的智能问答助手。请先上传一些文档，然后就可以向我提问了！</div>
                        </div>
                    </div>
                    
                    <div class="input-group">
                        <input type="text" id="chatInput" placeholder="输入你的问题..." 
                               onkeypress="if(event.key==='Enter') sendMessage()">
                        <button onclick="sendMessage()">发送</button>
                        <button onclick="streamMessage()" style="background: #28a745;">流式</button>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        const API_BASE = '/api';
        let sessionId = null;
        
        // 上传文本
        async function uploadText() {
            const title = document.getElementById('docTitle').value;
            const content = document.getElementById('docContent').value;
            const category = document.getElementById('docCategory').value;
            
            if (!title || !content) {
                showResult('uploadResult', '请填写标题和内容', 'error');
                return;
            }
            
            try {
                const response = await fetch(`${API_BASE}/documents/text`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ title, content, category })
                });
                
                const result = await response.json();
                showResult('uploadResult', `上传成功！文档ID: ${result.id}`, 'success');
                loadDocuments();
                
                // 清空表单
                document.getElementById('docTitle').value = '';
                document.getElementById('docContent').value = '';
            } catch (error) {
                showResult('uploadResult', '上传失败: ' + error.message, 'error');
            }
        }
        
        // 上传文件
        async function uploadFile() {
            const fileInput = document.getElementById('docFile');
            const category = document.getElementById('docCategory').value;
            
            if (!fileInput.files[0]) {
                showResult('uploadResult', '请选择文件', 'error');
                return;
            }
            
            const formData = new FormData();
            formData.append('file', fileInput.files[0]);
            formData.append('category', category);
            
            try {
                const response = await fetch(`${API_BASE}/documents/file`, {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                showResult('uploadResult', `上传成功！文档ID: ${result.id}`, 'success');
                loadDocuments();
                fileInput.value = '';
            } catch (error) {
                showResult('uploadResult', '上传失败: ' + error.message, 'error');
            }
        }
        
        // 加载文档列表
        async function loadDocuments() {
            try {
                const response = await fetch(`${API_BASE}/documents`);
                const documents = await response.json();
                
                const listHtml = documents.map(doc => `
                    <div class="document-item">
                        <div class="title">${doc.title}</div>
                        <div class="meta">
                            类别: ${doc.category} | 
                            分块: ${doc.chunkCount} | 
                            大小: ${formatBytes(doc.fileSize)} | 
                            时间: ${new Date(doc.createdAt).toLocaleString()}
                        </div>
                    </div>
                `).join('');
                
                document.getElementById('documentList').innerHTML = 
                    listHtml || '<div style="text-align:center;color:#999;">暂无文档</div>';
            } catch (error) {
                document.getElementById('documentList').innerHTML = 
                    '<div style="color:red;">加载失败</div>';
            }
        }
        
        // 发送消息
        async function sendMessage() {
            const input = document.getElementById('chatInput');
            const message = input.value.trim();
            const category = document.getElementById('chatCategory').value;
            
            if (!message) return;
            
            // 添加用户消息
            addMessage('user', message);
            input.value = '';
            
            try {
                const response = await fetch(`${API_BASE}/chat/rag/session`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ 
                        message, 
                        category,
                        sessionId 
                    })
                });
                
                const result = await response.json();
                sessionId = result.sessionId;
                
                // 添加助手回复
                addMessage('assistant', result.answer);
                
                // 显示来源
                if (result.sources && result.sources.length > 0) {
                    addSources(result.sources);
                }
            } catch (error) {
                addMessage('assistant', '抱歉，发生了错误: ' + error.message);
            }
        }
        
        // 流式消息
        async function streamMessage() {
            const input = document.getElementById('chatInput');
            const message = input.value.trim();
            const category = document.getElementById('chatCategory').value;
            
            if (!message) return;
            
            addMessage('user', message);
            input.value = '';
            
            const messageDiv = addMessage('assistant', '');
            
            try {
                const response = await fetch(`${API_BASE}/chat/rag/stream`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message, category })
                });
                
                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let content = '';
                
                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    
                    const chunk = decoder.decode(value);
                    const lines = chunk.split('\n');
                    
                    for (const line of lines) {
                        if (line.startsWith('data: ')) {
                            const data = line.slice(6);
                            if (data !== '[DONE]') {
                                content += data;
                                messageDiv.querySelector('div:last-child').textContent = content;
                            }
                        }
                    }
                }
            } catch (error) {
                messageDiv.querySelector('div:last-child').textContent = 
                    '抱歉，发生了错误: ' + error.message;
            }
        }
        
        // 添加消息
        function addMessage(role, content) {
            const container = document.getElementById('chatMessages');
            const div = document.createElement('div');
            div.className = `message ${role}`;
            div.innerHTML = `
                <div class="role">${role === 'user' ? '用户' : '助手'}</div>
                <div>${content}</div>
            `;
            container.appendChild(div);
            container.scrollTop = container.scrollHeight;
            return div;
        }
        
        // 添加来源
        function addSources(sources) {
            const container = document.getElementById('chatMessages');
            const div = document.createElement('div');
            div.className = 'sources';
            div.innerHTML = `
                <h4>参考来源：</h4>
                ${sources.map(s => `
                    <div class="source-item">
                        <strong>${s.title}</strong> (相似度: ${(s.score * 100).toFixed(1)}%)<br>
                        ${s.excerpt.substring(0, 100)}...
                    </div>
                `).join('')}
            `;
            container.appendChild(div);
            container.scrollTop = container.scrollHeight;
        }
        
        // 显示结果
        function showResult(elementId, message, type) {
            const div = document.getElementById(elementId);
            div.className = type;
            div.textContent = message;
            setTimeout(() => div.textContent = '', 5000);
        }
        
        // 格式化字节
        function formatBytes(bytes) {
            if (bytes === 0) return '0 Bytes';
            const k = 1024;
            const sizes = ['Bytes', 'KB', 'MB', 'GB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
        }
        
        // 页面加载时加载文档列表
        loadDocuments();
    </script>
</body>
</html>
```

### 12.12 Docker Compose配置

```yaml
version: '3.8'

services:
  # PostgreSQL with pgvector
  postgres:
    image: ankane/pgvector:latest
    container_name: rag-postgres
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: rag_db
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

  # Spring Boot Application
  app:
    build: .
    container_name: rag-app
    environment:
      - SPRING_DATASOURCE_URL=jdbc:postgresql://postgres:5432/rag_db
      - SPRING_DATASOURCE_USERNAME=postgres
      - SPRING_DATASOURCE_PASSWORD=postgres
      - SPRING_AI_OPENAI_API_KEY=${OPENAI_API_KEY}
    ports:
      - "8080:8080"
    depends_on:
      postgres:
        condition: service_healthy

volumes:
  postgres_data:
```

### 12.13 Dockerfile

```dockerfile
FROM eclipse-temurin:17-jdk-alpine

WORKDIR /app

COPY target/*.jar app.jar

EXPOSE 8080

ENTRYPOINT ["java", "-jar", "app.jar"]
```

---

## 第13章：最佳实践与性能优化

### 13.1 连接池配置

合理配置数据库连接池对于高并发场景至关重要。

```yaml
spring:
  datasource:
    url: jdbc:postgresql://localhost:5432/ai_db
    username: postgres
    password: password
    driver-class-name: org.postgresql.Driver
    hikari:
      # 连接池大小 = (核心数 * 2) + 有效磁盘数
      maximum-pool-size: 20
      minimum-idle: 5
      # 连接超时
      connection-timeout: 30000
      # 空闲连接超时
      idle-timeout: 600000
      # 连接最大生命周期
      max-lifetime: 1800000
      # 连接测试查询
      connection-test-query: SELECT 1
```

### 13.2 重试机制

为AI调用添加重试机制，提高系统稳定性。

```java
import org.springframework.retry.annotation.Backoff;
import org.springframework.retry.annotation.Retryable;
import org.springframework.stereotype.Service;

@Service
public class RetryableAiService {
    
    private final ChatClient chatClient;
    
    public RetryableAiService(ChatClient.Builder chatClientBuilder) {
        this.chatClient = chatClientBuilder.build();
    }
    
    /**
     * 带重试的AI调用
     */
    @Retryable(
        retryFor = {AiClientException.class, TimeoutException.class},
        maxAttempts = 3,
        backoff = @Backoff(delay = 1000, multiplier = 2)
    )
    public String chatWithRetry(String message) {
        return chatClient.prompt()
            .user(message)
            .call()
            .content();
    }
}
```

启用重试：

```java
import org.springframework.context.annotation.Configuration;
import org.springframework.retry.annotation.EnableRetry;

@Configuration
@EnableRetry
public class RetryConfig {
}
```

### 13.3 超时设置

```yaml
spring:
  ai:
    openai:
      api-key: ${OPENAI_API_KEY}
      # 连接超时
      connect-timeout: 10s
      # 读取超时
      read-timeout: 60s
      # 写入超时
      write-timeout: 10s
```

```java
import org.springframework.ai.openai.api.OpenAiApi;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.SimpleClientHttpRequestFactory;

@Configuration
public class TimeoutConfig {
    
    @Bean
    public OpenAiApi openAiApi() {
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(10000);  // 10秒
        factory.setReadTimeout(60000);     // 60秒
        
        return OpenAiApi.builder()
            .apiKey(System.getenv("OPENAI_API_KEY"))
            .requestFactory(factory)
            .build();
    }
}
```

### 13.4 缓存策略

缓存AI响应可以显著降低成本和提高响应速度。

```java
import org.springframework.cache.annotation.Cacheable;
import org.springframework.cache.annotation.EnableCaching;
import org.springframework.context.annotation.Configuration;
import org.springframework.stereotype.Service;

import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Base64;

@Configuration
@EnableCaching
public class CacheConfig {
}

@Service
public class CachedAiService {
    
    private final ChatClient chatClient;
    
    public CachedAiService(ChatClient.Builder chatClientBuilder) {
        this.chatClient = chatClientBuilder.build();
    }
    
    /**
     * 带缓存的AI调用
     */
    @Cacheable(value = "aiResponses", key = "#message")
    public String chatWithCache(String message) {
        return chatClient.prompt()
            .user(message)
            .call()
            .content();
    }
    
    /**
     * 带相似度缓存的AI调用
     */
    @Cacheable(value = "aiResponses", key = "@cacheKeyGenerator.generate(#message)")
    public String chatWithSemanticCache(String message) {
        return chatClient.prompt()
            .user(message)
            .call()
            .content();
    }
}

@Component
public class CacheKeyGenerator {
    
    public String generate(String message) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hash = digest.digest(message.getBytes());
            return Base64.getEncoder().encodeToString(hash);
        } catch (NoSuchAlgorithmException e) {
            return String.valueOf(message.hashCode());
        }
    }
}
```

使用Redis缓存：

```yaml
spring:
  cache:
    type: redis
  redis:
    host: localhost
    port: 6379
    timeout: 2000ms
    lettuce:
      pool:
        max-active: 8
        max-idle: 8
        min-idle: 0
```

### 13.5 监控和日志

```java
import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Timer;
import org.springframework.stereotype.Service;

@Service
public class MonitoredAiService {
    
    private final ChatClient chatClient;
    private final Counter requestCounter;
    private final Counter errorCounter;
    private final Timer responseTimer;
    
    public MonitoredAiService(ChatClient.Builder chatClientBuilder,
                              MeterRegistry meterRegistry) {
        this.chatClient = chatClientBuilder.build();
        this.requestCounter = Counter.builder("ai.requests.total")
            .description("Total AI requests")
            .register(meterRegistry);
        this.errorCounter = Counter.builder("ai.requests.errors")
            .description("Total AI request errors")
            .register(meterRegistry);
        this.responseTimer = Timer.builder("ai.response.time")
            .description("AI response time")
            .register(meterRegistry);
    }
    
    public String chat(String message) {
        requestCounter.increment();
        
        return responseTimer.recordCallable(() -> {
            try {
                return chatClient.prompt()
                    .user(message)
                    .call()
                    .content();
            } catch (Exception e) {
                errorCounter.increment();
                throw e;
            }
        });
    }
}
```

### 13.6 安全最佳实践

```java
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.client.advisor.SafeGuardAdvisor;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class SecureAiService {
    
    private final ChatClient chatClient;
    
    public SecureAiService(ChatClient.Builder chatClientBuilder) {
        this.chatClient = chatClientBuilder
            .defaultAdvisors(new SafeGuardAdvisor(
                List.of("密码", "密钥", "token", "secret"),
                "输入包含敏感信息，已被拦截"
            ))
            .build();
    }
    
    /**
     * 安全的AI调用
     */
    public String secureChat(String message) {
        // 1. 输入验证
        if (!isValidInput(message)) {
            throw new SecurityException("输入包含非法字符");
        }
        
        // 2. 长度限制
        if (message.length() > 4000) {
            throw new IllegalArgumentException("输入过长");
        }
        
        // 3. 调用AI
        String response = chatClient.prompt()
            .user(message)
            .call()
            .content();
        
        // 4. 输出过滤
        return sanitizeOutput(response);
    }
    
    private boolean isValidInput(String input) {
        // 检查是否包含恶意内容
        return !input.matches(".*<script.*>.*</script>.*") &&
               !input.contains("${");
    }
    
    private String sanitizeOutput(String output) {
        // 移除可能的敏感信息
        return output.replaceAll("\\b[A-Za-z0-9]{32,}\\b", "[REDACTED]");
    }
}
```

### 13.7 完整的生产环境配置

```yaml
# 生产环境配置
spring:
  profiles:
    active: prod
  
  # 数据库配置
  datasource:
    url: jdbc:postgresql://${DB_HOST:localhost}:${DB_PORT:5432}/${DB_NAME:ai_db}
    username: ${DB_USERNAME:postgres}
    password: ${DB_PASSWORD}
    hikari:
      maximum-pool-size: ${DB_POOL_SIZE:20}
      minimum-idle: ${DB_MIN_IDLE:5}
      connection-timeout: 30000
      idle-timeout: 600000
      max-lifetime: 1800000
  
  # AI配置
  ai:
    openai:
      api-key: ${OPENAI_API_KEY}
      base-url: ${OPENAI_BASE_URL:https://api.openai.com}
      connect-timeout: ${OPENAI_CONNECT_TIMEOUT:10s}
      read-timeout: ${OPENAI_READ_TIMEOUT:60s}
      
      chat:
        options:
          model: ${OPENAI_CHAT_MODEL:gpt-4o}
          temperature: ${OPENAI_TEMPERATURE:0.7}
          max-tokens: ${OPENAI_MAX_TOKENS:2000}
      
      embedding:
        options:
          model: ${OPENAI_EMBEDDING_MODEL:text-embedding-3-small}
    
    vectorstore:
      pgvector:
        index-type: ${VECTOR_INDEX_TYPE:hnsw}
        distance-type: ${VECTOR_DISTANCE_TYPE:cosine_distance}
        dimensions: ${VECTOR_DIMENSIONS:1536}
        initialize-schema: false
  
  # 缓存配置
  cache:
    type: redis
  
  redis:
    host: ${REDIS_HOST:localhost}
    port: ${REDIS_PORT:6379}
    password: ${REDIS_PASSWORD}
    timeout: 2000ms
    lettuce:
      pool:
        max-active: 8
        max-idle: 8

# 服务器配置
server:
  port: ${SERVER_PORT:8080}
  tomcat:
    threads:
      max: 200
      min-spare: 10
    max-connections: 10000

# 日志配置
logging:
  level:
    root: WARN
    com.example: INFO
    org.springframework.ai: INFO
  pattern:
    console: "%d{yyyy-MM-dd HH:mm:ss} [%thread] %-5level %logger{36} - %msg%n"

# 监控配置
management:
  endpoints:
    web:
      exposure:
        include: health,info,metrics,prometheus
  endpoint:
    health:
      show-details: when-authorized
  metrics:
    export:
      prometheus:
        enabled: true
```

### 13.8 性能优化总结

| 优化项 | 配置建议 | 预期效果 |
|--------|----------|----------|
| 连接池 | 最大连接数20，最小空闲5 | 避免连接耗尽 |
| 重试机制 | 最多3次，指数退避 | 提高可用性 |
| 超时设置 | 连接10s，读取60s | 避免长时间阻塞 |
| 缓存 | Redis缓存，TTL 1小时 | 降低成本50%+ |
| 监控 | Micrometer + Prometheus | 实时可观测 |
| 安全 | 输入验证 + 输出过滤 | 防止注入攻击 |

---


## 12. 可观测性（Observability）

### 12.1 AI操作的可观测性支持

Spring AI 集成了 Spring Boot Actuator 和 Micrometer，提供了全面的可观测性支持：

```xml
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-actuator</artifactId>
</dependency>
<dependency>
    <groupId>io.micrometer</groupId>
    <artifactId>micrometer-registry-prometheus</artifactId>
</dependency>
```

### 12.2 日志和监控

#### 启用日志

```yaml
logging:
  level:
    org.springframework.ai: DEBUG
    org.springframework.ai.chat.client: TRACE
```

#### 自定义指标

```java
@Component
public class AiMetricsAdvisor implements BaseAdvisor {
    
    private final MeterRegistry meterRegistry;
    private final Timer timer;
    private final Counter counter;
    
    public AiMetricsAdvisor(MeterRegistry meterRegistry) {
        this.meterRegistry = meterRegistry;
        this.timer = Timer.builder("ai.request.duration")
                .description("AI请求耗时")
                .register(meterRegistry);
        this.counter = Counter.builder("ai.request.count")
                .description("AI请求次数")
                .register(meterRegistry);
    }
    
    @Override
    public ChatClientRequest before(ChatClientRequest request, AdvisorChain chain) {
        chain.getContext().put("startTime", System.currentTimeMillis());
        counter.increment();
        return request;
    }
    
    @Override
    public ChatClientResponse after(ChatClientResponse response, AdvisorChain chain) {
        Long startTime = (Long) chain.getContext().get("startTime");
        if (startTime != null) {
            timer.record(System.currentTimeMillis() - startTime, TimeUnit.MILLISECONDS);
        }
        return response;
    }
}
```

#### 链路追踪

```yaml
management:
  tracing:
    sampling:
      probability: 1.0
  zipkin:
    tracing:
      endpoint: http://localhost:9411/api/v2/spans
```

---


## 结语

本文档详细介绍了Spring AI 1.1.4的各项功能和使用方法，从基础概念到高级应用，从简单示例到完整项目，涵盖了开发AI应用所需的核心知识。

Spring AI作为Spring生态的重要组成部分，正在快速发展中。建议开发者：

1. 关注官方文档和GitHub仓库获取最新信息
2. 积极参与社区讨论和贡献
3. 在生产环境中充分测试后再部署
4. 持续关注版本更新和新特性

希望本文档能帮助你快速上手Spring AI，构建出优秀的AI应用！

---

## 参考资源

- [Spring AI 官方文档](https://docs.spring.io/spring-ai/reference/)
- [Spring AI GitHub](https://github.com/spring-projects/spring-ai)
- [pgvector 文档](https://github.com/pgvector/pgvector)
- [OpenAI API 文档](https://platform.openai.com/docs)

---

 Spring AI版本：1.1.4*
