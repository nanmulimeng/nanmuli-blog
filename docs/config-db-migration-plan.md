# 系统配置全量数据库迁移 — 开发文档

> 版本: v1.0 | 日期: 2026-05-15 | 作者: nanmuli
>
> 目标: 将所有系统/环境/爬虫配置纳入 `sys_config` 表，实现「修改数据库 → 运行时生效」的配置管理闭环。

---

## 目录

1. [现状分析](#1-现状分析)
2. [目标架构](#2-目标架构)
3. [Phase 1: Schema 统合 + 基础设施改造](#3-phase-1-schema-统合--基础设施改造)
4. [Phase 2: Java 侧 @Value → DB 迁移](#4-phase-2-java-侧-value--db-迁移)
5. [Phase 3: Python 侧全量配置 DB 化](#5-phase-3-python-侧全量配置-db-化)
6. [Phase 4: 前端管理页增强](#6-phase-4-前端管理页增强)
7. [测试计划](#7-测试计划)
8. [回滚方案](#8-回滚方案)

---

## 1. 现状分析

### 1.1 配置散落位置

```
┌────────────────────────────────────────────────────────────────────┐
│                          配置来源分布                                │
│                                                                    │
│  ┌── application-dev.yml ──────────────────────────────────────┐   │
│  │ crawler.service.* (5项): base-url, api-key, connect/read    │   │
│  │   timeout, 连接池参数                                        │   │
│  │ crawler.callback.api-key (1项)                               │   │
│  │ blog.cache.ttl.* (10项)                                     │   │
│  │ blog.security.encryption-key (1项, 有硬编码默认值)           │   │
│  │ mihomo.api.url (1项)                                        │   │
│  │ cors.* (2项)                                                │   │
│  │ spring.datasource.*, spring.data.redis.* (基础架构)          │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                    │
│  ┌── crawler-service/.env ─────────────────────────────────────┐   │
│  │ 基础服务 (5项): HOST, PORT, DEBUG, LOG_LEVEL, STANDALONE    │   │
│  │ 爬取限制 (3项): MAX_PAGES_LIMIT, MAX_DEPTH_LIMIT,           │   │
│  │   MAX_CONCURRENT_CRAWLS                                     │   │
│  │ 质量过滤 (1项): MIN_CONTENT_LENGTH                          │   │
│  │ 搜索策略 (3项): MAX_CONSECUTIVE_EMPTY, MAX_VARIANTS,        │   │
│  │   INTER_SEARCH_DELAY                                        │   │
│  │ 搜索超时 (10项): PAGE_TIMEOUT_MS, BROWSER_FETCH_TIMEOUT_MS, │   │
│  │   HTTPX_FALLBACK_TIMEOUT, CLIENT_TIMEOUT, WARMUP_TIMEOUT,   │   │
│  │   PAGE_RETRIES, MAX_PAGES_PER_ENGINE, MIN_WORD_COUNT        │   │
│  │ 搜索引擎延迟 (7项): SWITCH_DELAY_MIN/MAX, PAGE_DELAY_MIN/   │   │
│  │   MAX, CRAWL_DEADLINE, PROGRESSIVE_FALLBACK, OPT_*          │   │
│  │ 质量评估 (10项): SOURCE_WEIGHT, CONTENT_WEIGHT, 各类阈值     │   │
│  │ 评估权重 (6项): ANGLE/SOURCE/DEPTH/TEMPORAL/PERSPECTIVE/    │   │
│  │   LANGUAGE                                                   │   │
│  │ 日报配置 (7项): DIGEST_*                                     │   │
│  │ 回调配置 (3项): CALLBACK_URL, CALLBACK_API_KEY, JAVA_API_URL │   │
│  │ 优化配置 (5项): OPTIMIZATION_*                               │   │
│  │ 茧房突破 (3项): BUBBLE_*                                     │   │
│  │ 关键词检测 (3项): QUALITY_CLICKBAIT/AD/PAYWALL_KEYWORDS     │   │
│  │ SQLite配置 (1项): DB_BUSY_TIMEOUT                            │   │
│  │ 独立模式 (5项): API_KEYS, AUTH_ENABLED, DB_PATH,             │   │
│  │   MAX_CONCURRENT_TASKS, AUTH_*                               │   │
│  │ 代理配置 (1项): PROXY_URL                                    │   │
│  │ 搜索去重 (1项): MAX_DOMAIN_DEDUP                             │   │
│  │ AI 配置 (17项): 已在 sys_config 中                           │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                    │
│  ┌── sys_config 表 (PostgreSQL) ───────────────────────────────┐   │
│  │ site.* (11项): 站点名称/描述/Logo/ICP/Footer/About/...      │   │
│  │ ai.* (4项): enabled, model, autoTags, autoSummary           │   │
│  │ crawler.ai.* (16项): AI模型/超时/Token/阈值                 │   │
│  │ crawler.digest.enabled (1项): 日报开关                      │   │
│  │ crawler.proxy.* (3项): 代理开关/地址/订阅URL                │   │
│  └──────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────┘
```

### 1.2 关键文件清单

| 文件 | 角色 | 影响 Phase |
|------|------|------------|
| `backend/src/main/resources/db/init.sql:882-917` | Java 种子数据 (含 crawler.* 32项) | Phase 1 |
| `deploy/db/init-scripts/schema.sql:417-441, 910-958` | Docker 初始化 schema + 种子 | Phase 1 |
| `backend/src/main/java/.../domain/config/Config.java` | 配置实体 (13行) | Phase 1,2 |
| `backend/src/main/java/.../domain/config/ConfigRepository.java` | 仓储接口 (19行) | Phase 2 |
| `backend/src/main/java/.../infrastructure/persistence/config/ConfigRepositoryImpl.java` | 仓储实现 (60行) | Phase 2 |
| `backend/src/main/java/.../application/config/ConfigAppService.java` | 应用服务 (152行) | Phase 2 |
| `backend/src/main/java/.../interfaces/rest/ConfigController.java` | 配置管理 API (74行) | Phase 2,4 |
| `backend/src/main/java/.../interfaces/rest/InternalCallbackController.java` | 内部 API (100行) | Phase 2,3 |
| `backend/src/main/java/.../infrastructure/config/security/AesEncryptor.java` | AES-128 加解密 (56行) | Phase 2 |
| `backend/src/main/java/.../infrastructure/crawler/CrawlerTaskClient.java` | 爬虫客户端 (239行) | Phase 2 |
| `backend/src/main/resources/application-dev.yml` | Spring Boot 配置 | Phase 2 |
| `crawler-service/config.py` | Python Pydantic Settings (148行) | Phase 3 |
| `crawler-service/.env` | Python 环境变量 | Phase 3 |
| `crawler-service/standalone/backend_config.py` | Python 配置拉取 (113行) | Phase 3 |
| `crawler-service/standalone/routes.py:373-380` | Python 配置刷新端点 | Phase 3 |
| `frontend/src/views/admin/config/Index.vue` | 配置管理页 (304行) | Phase 4 |
| `frontend/src/api/config.ts` | 配置 API 调用 (47行) | Phase 4 |

### 1.3 Schema 分歧详情

| 列名 | `init.sql` (Java基线) | `deploy/.../schema.sql` (Docker) | Java `Config` 实体 |
|------|----------------------|----------------------------------|-------------------|
| `id` | BIGSERIAL PK | BIGSERIAL PK | `Long id` (BaseAggregateRoot) |
| `config_key` | VARCHAR(100) UNIQUE | VARCHAR(100) NOT NULL UNIQUE | `String configKey` |
| `config_value` | TEXT | TEXT | `String configValue` |
| `default_value` | ❌ 不存在 | TEXT | ❌ 不存在 |
| `description` | VARCHAR(200) | VARCHAR(200) | `String description` |
| `group_name` | VARCHAR(50) | VARCHAR(50) | `String groupName` |
| `is_public` | BOOLEAN DEFAULT FALSE | BOOLEAN DEFAULT FALSE | `Boolean isPublic` |
| `input_type` | VARCHAR(20) | ❌ 不存在 | `String inputType` |
| `created_at` | (BaseAggregateRoot) | TIMESTAMP DEFAULT NOW() | (BaseAggregateRoot) |
| `updated_at` | (BaseAggregateRoot) | TIMESTAMP DEFAULT NOW() | (BaseAggregateRoot) |
| `is_deleted` | (BaseAggregateRoot) | BOOLEAN DEFAULT FALSE | (BaseAggregateRoot) |

**结论**: 两份 schema 同时缺少 `default_value` 和 `input_type` 列，需统合为包含全部列的版本。

### 1.4 种子数据分歧

| config_key | init.sql (Java) | schema.sql (Docker) |
|------------|-----------------|---------------------|
| `crawler.ai.*` (16项) | ✅ 存在 | ✅ 存在 (但仅 2项) |
| `crawler.digest.enabled` | ✅ 存在 | ✅ 存在 |
| `crawler.proxy.*` (3项) | ✅ 存在 | ✅ 存在 (仅 2项) |
| `ai.enabled/ai.model/ai.autoTags/ai.autoSummary` | ❌ 在 init.sql | ✅ 在 schema.sql |
| `crawler.ai.base_url` | ✅ DashScope URL | ❌ 不存在 |
| `crawler.ai.temperature` ~ `crawler.ai.max_tags` (12项) | ✅ 存在 | ❌ 不存在 |

---

## 2. 目标架构

### 2.1 配置变更流程（改造后）

```
┌──────────────────────────────────────────────────────────────────┐
│                        管理员操作                                  │
│  前端配置管理页 → PUT /api/admin/config/{key}                     │
│                              │                                    │
│              ┌───────────────┼───────────────┐                   │
│              ▼               ▼               ▼                   │
│        sys_config 表    通知 Python      通知 Java               │
│        (PostgreSQL)     refreshConfig    reloadConfig            │
│                              │               │                   │
│              ┌───────────────┼───────────────┐                   │
│              ▼               ▼               ▼                   │
│        配置写入磁盘      Python 重拉       Java 重载              │
│        (AES加密敏感值)   配置并应用        配置Bean               │
└──────────────────────────────────────────────────────────────────┘
```

### 2.2 分组规范

| group_name | 说明 | is_public | 示例 key |
|------------|------|-----------|----------|
| `site` | 站点信息 | true | `site.name`, `site.logo` |
| `blog` | 博客运行参数 | false | `blog.security.encryption-key`, `blog.cache.ttl.*` |
| `crawler` | 爬虫通用配置 | false | `crawler.service.base-url`, `crawler.callback.api-key` |
| `crawler.ai` | 爬虫 AI 参数 | false | `crawler.ai.model`, `crawler.ai.temperature` |
| `crawler.proxy` | 爬虫代理配置 | false | `crawler.proxy.enabled`, `crawler.proxy.url` |
| `crawler.search` | 搜索引擎参数 | false | `crawler.search.page_timeout_ms` |
| `crawler.quality` | 质量评估参数 | false | `crawler.quality.source_weight` |
| `crawler.digest` | 日报配置 | false | `crawler.digest.enabled`, `crawler.digest.cron` |
| `crawler.optimization` | 搜索优化 | false | `crawler.optimization.enabled` |
| `crawler.bubble` | 茧房突破 | false | `crawler.bubble.enabled` |

---

## 3. Phase 1: Schema 统合 + 基础设施改造

**目标**: 统一两份 schema，补齐缺失列，创建 Flyway 迁移，增加 `is_encrypted` 列支持。

### 3.1 Flyway 迁移脚本

**文件**: `backend/src/main/resources/db/migration/V1_12__unify_sys_config.sql`

```sql
-- ============================================
-- V1.12: sys_config 表统合与扩展
-- 合并 init.sql 与 deploy/db/init-scripts/schema.sql 的分歧
-- ============================================

-- 1. 补齐 deploy/schema.sql 缺失的 input_type 列
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'sys_config' AND column_name = 'input_type'
    ) THEN
        ALTER TABLE sys_config ADD COLUMN input_type VARCHAR(20) NOT NULL DEFAULT 'text';
    END IF;
END $$;

-- 2. 补齐 init.sql 缺失的 default_value 列
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'sys_config' AND column_name = 'default_value'
    ) THEN
        ALTER TABLE sys_config ADD COLUMN default_value TEXT;
    END IF;
END $$;

-- 3. 新增 is_encrypted 列（标记值是否需要 AES 加解密存储）
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'sys_config' AND column_name = 'is_encrypted'
    ) THEN
        ALTER TABLE sys_config ADD COLUMN is_encrypted BOOLEAN NOT NULL DEFAULT FALSE;
        COMMENT ON COLUMN sys_config.is_encrypted IS '是否加密存储（AES-128），敏感值如 API Key 设为 true';
    END IF;
END $$;

-- 4. 新增 is_sensitive 列（标记配置是否为敏感信息，前端需遮罩显示）
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'sys_config' AND column_name = 'is_sensitive'
    ) THEN
        ALTER TABLE sys_config ADD COLUMN is_sensitive BOOLEAN NOT NULL DEFAULT FALSE;
        COMMENT ON COLUMN sys_config.is_sensitive IS '是否敏感配置，前端显示为 ****，编辑需提供真实值';
    END IF;
END $$;

-- 5. 标记已有敏感配置
UPDATE sys_config
SET is_encrypted = TRUE, is_sensitive = TRUE
WHERE config_key IN (
    'crawler.ai.api_key',
    'crawler.callback.api-key'
);

-- 6. 统一 group_name: 将旧 ai 组配置迁移至 crawler.ai 组
UPDATE sys_config
SET group_name = 'crawler'
WHERE config_key LIKE 'crawler.ai.%' AND group_name != 'crawler';

-- 7. 清理 deploy/schema.sql 中的遗留旧 AI 配置（如果存在）
DELETE FROM sys_config
WHERE config_key IN ('ai.enabled', 'ai.model', 'ai.autoTags', 'ai.autoSummary')
  AND NOT EXISTS (
    SELECT 1 FROM sys_config sc2
    WHERE sc2.config_key LIKE 'crawler.ai.%'
  );
```

### 3.2 Config 实体更新

**文件**: `backend/src/main/java/com/nanmuli/blog/domain/config/Config.java`

```java
package com.nanmuli.blog.domain.config;

import com.baomidou.mybatisplus.annotation.TableName;
import com.nanmuli.blog.shared.domain.BaseAggregateRoot;
import lombok.EqualsAndHashCode;
import lombok.Getter;
import lombok.Setter;

@Getter
@Setter
@EqualsAndHashCode(callSuper = false)
@TableName("sys_config")
public class Config extends BaseAggregateRoot<Long> {
    private static final long serialVersionUID = 1L;

    private String configKey;
    private String configValue;
    private String defaultValue;
    private String description;
    private String groupName;
    private Boolean isPublic;
    private String inputType;
    private Boolean isEncrypted;   // 新增: AES 加密标记
    private Boolean isSensitive;   // 新增: 前端遮罩标记
}
```

### 3.3 更新 ConfigAppService 敏感检测逻辑

**文件**: `backend/src/main/java/com/nanmuli/blog/application/config/ConfigAppService.java`

改动点:
- **删除** `SENSITIVE_KEYWORDS` 和 `NON_SENSITIVE_WHITELIST` 常量
- **删除** `isSensitiveConfig(String)` 方法
- `isSensitiveConfig()` 改为读实体的 `isSensitive` 字段
- `update()` / `set()` 中的加密判断改为读 `isEncrypted` 字段

```java
// 修改前 (关键词匹配，脆弱)
private boolean isSensitiveConfig(String configKey) {
    if (configKey == null) return false;
    if (NON_SENSITIVE_WHITELIST.contains(configKey)) return false;
    String lowerKey = configKey.toLowerCase();
    return SENSITIVE_KEYWORDS.stream().anyMatch(lowerKey::contains);
}

// 修改后 (读取实体字段，可靠)
private boolean isEncrypted(Config config) {
    return Boolean.TRUE.equals(config.getIsEncrypted());
}

private boolean isSensitive(Config config) {
    return Boolean.TRUE.equals(config.getIsSensitive());
}
```

### 3.4 更新 InternalCallbackController 解密逻辑

**文件**: `backend/src/main/java/com/nanmuli/blog/interfaces/rest/InternalCallbackController.java:90-95`

```java
// 修改前: 对所有 crawler 组的值解密（浪费 CPU）
configMap = configRepository.findByGroup("crawler").stream()
    .collect(Collectors.toMap(
        c -> c.getConfigKey().replace("crawler.", ""),
        c -> aesEncryptor.decrypt(c.getConfigValue() != null ? c.getConfigValue() : ""),
        ...));

// 修改后: 仅对 is_encrypted=true 的值解密
configMap = configRepository.findByGroup("crawler").stream()
    .collect(Collectors.toMap(
        c -> c.getConfigKey().replace("crawler.", ""),
        c -> {
            String val = c.getConfigValue() != null ? c.getConfigValue() : "";
            return Boolean.TRUE.equals(c.getIsEncrypted()) ? aesEncryptor.decrypt(val) : val;
        },
        ...));
```

### 3.5 同步 deploy/schema.sql

更新 `deploy/db/init-scripts/schema.sql` 的 `sys_config` 建表语句，与 Flyway 迁移后的最终结构一致:

```sql
CREATE TABLE IF NOT EXISTS sys_config (
    id BIGSERIAL PRIMARY KEY,
    config_key VARCHAR(100) NOT NULL UNIQUE,
    config_value TEXT,
    default_value TEXT,
    description VARCHAR(200),
    group_name VARCHAR(50),
    is_public BOOLEAN DEFAULT FALSE,
    input_type VARCHAR(20) NOT NULL DEFAULT 'text',
    is_encrypted BOOLEAN NOT NULL DEFAULT FALSE,
    is_sensitive BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE
);
```

同时同步种子数据 SQL（详见 Phase 2+3 的新增种子数据）。

### 3.6 更新 init.sql 种子数据

在 `init.sql` 中同步更新种子数据，确保与 Flyway 迁移后的最终状态一致。

---

## 4. Phase 2: Java 侧 @Value → DB 迁移

### 4.1 迁移清单

| 原 @Value 注解 | sys_config key | group_name | is_encrypted | 说明 |
|---------------|---------------|------------|--------------|------|
| `${crawler.service.base-url}` | `crawler.service.base-url` | crawler | false | Python 服务地址 |
| `${crawler.service.api-key}` | `crawler.service.api-key` | crawler | true | Python API 认证密钥 |
| `${crawler.service.connect-timeout}` | `crawler.service.connect-timeout` | crawler | false | 连接超时(ms) |
| `${crawler.service.read-timeout}` | `crawler.service.read-timeout` | crawler | false | 读取超时(ms) |
| `${crawler.http.pool.max-total}` | `crawler.http.pool.max-total` | crawler | false | 连接池最大连接数 |
| `${crawler.http.pool.max-per-route}` | `crawler.http.pool.max-per-route` | crawler | false | 单路由最大连接数 |
| `${crawler.callback.api-key}` | `crawler.callback.api-key` | crawler | true | 回调认证密钥 |
| `${blog.security.encryption-key}` | `blog.security.encryption-key` | blog | true | AES 加密密钥 |

**不迁移项**（基础设施层，需在应用启动前就绪）:

| @Value 注解 | 保留原因 |
|-------------|----------|
| `spring.datasource.*` | 数据库连接 — 必须先于 Spring 上下文初始化 |
| `spring.data.redis.*` | Redis 连接 — 同上 |
| `sa-token.*` | Sa-Token 配置 — 框架级别 |

### 4.2 新建 ConfigService（统一配置读取层）

**文件**: `backend/src/main/java/com/nanmuli/blog/infrastructure/config/ConfigService.java` (新建)

```java
package com.nanmuli.blog.infrastructure.config;

import com.nanmuli.blog.domain.config.Config;
import com.nanmuli.blog.domain.config.ConfigRepository;
import com.nanmuli.blog.infrastructure.config.security.AesEncryptor;
import jakarta.annotation.PostConstruct;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 统一配置读取服务
 *
 * 启动时从 sys_config 表加载所有配置到内存 Map，
 * 提供 get/getInt/getBool 方法替代 @Value 注入。
 * 支持运行时刷新（/api/admin/config/refresh 触发）。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class ConfigService {

    private final ConfigRepository configRepository;
    private final AesEncryptor aesEncryptor;

    private final Map<String, String> cache = new ConcurrentHashMap<>();

    @PostConstruct
    public void init() {
        reload();
    }

    /** 全量重新加载（从 DB 读取所有配置，解密敏感值） */
    public synchronized void reload() {
        cache.clear();
        for (Config config : configRepository.findAll()) {
            String value = config.getConfigValue() != null ? config.getConfigValue() : "";
            if (Boolean.TRUE.equals(config.getIsEncrypted())) {
                value = aesEncryptor.decrypt(value);
            }
            cache.put(config.getConfigKey(), value);
        }
        log.info("[ConfigService] Loaded {} configs from DB", cache.size());
    }

    public String get(String key) {
        return cache.getOrDefault(key, "");
    }

    public String get(String key, String defaultValue) {
        return cache.getOrDefault(key, defaultValue);
    }

    public int getInt(String key, int defaultValue) {
        String val = cache.get(key);
        if (val == null || val.isEmpty()) return defaultValue;
        try {
            return Integer.parseInt(val);
        } catch (NumberFormatException e) {
            return defaultValue;
        }
    }

    public boolean getBool(String key, boolean defaultValue) {
        String val = cache.get(key);
        if (val == null || val.isEmpty()) return defaultValue;
        return "true".equalsIgnoreCase(val) || "1".equals(val);
    }
}
```

### 4.3 修改 CrawlerTaskClient 使用 ConfigService

**文件**: `backend/src/main/java/com/nanmuli/blog/infrastructure/crawler/CrawlerTaskClient.java`

```java
// 修改前: 构造器注入 6 个 @Value 参数
public CrawlerTaskClient(
        @Value("${crawler.service.base-url:http://localhost:8500}") String baseUrl,
        @Value("${crawler.service.api-key:}") String apiKey,
        @Value("${crawler.service.connect-timeout:10000}") int connectTimeout,
        @Value("${crawler.service.read-timeout:30000}") int readTimeout,
        @Value("${crawler.http.pool.max-total:20}") int maxTotal,
        @Value("${crawler.http.pool.max-per-route:10}") int maxPerRoute,
        ObjectMapper objectMapper) {
    // ...
}

// 修改后: 从 ConfigService 读取，简化构造器
public CrawlerTaskClient(ConfigService configService, ObjectMapper objectMapper) {
    this.configService = configService;
    this.baseUrl = configService.get("crawler.service.base-url", "http://localhost:8500");
    this.apiKey = configService.get("crawler.service.api-key", "");
    // ...连接池参数同理
}
```

**重要**: 连接池在构造时创建，修改连接池参数后需重建 `CrawlerTaskClient` 实例。为支持热更新，新增 `reloadPool()` 方法:

```java
/**
 * 运行时重载连接池配置（不需要重启）
 * 注意: 此方法会关闭旧连接池并创建新的
 */
public synchronized void reloadPool() {
    int connectTimeout = configService.getInt("crawler.service.connect-timeout", 10000);
    int readTimeout = configService.getInt("crawler.service.read-timeout", 30000);
    // ... 重建 httpClient 和 restTemplate
    log.info("[CrawlerTaskClient] pool reloaded: connectTimeout={}, readTimeout={}", connectTimeout, readTimeout);
}
```

### 4.4 修改 InternalCallbackController 的 callbackApiKey

```java
// 修改前
@Value("${crawler.callback.api-key:}")
private String callbackApiKey;

// 修改后: 从 ConfigService 获取
private final ConfigService configService;

private String getCallbackApiKey() {
    return configService.get("crawler.callback.api-key", "");
}
```

### 4.5 修改 AesEncryptor 的 encryptionKey

```java
// 修改前: 从 @Value 读取（有硬编码默认值）
public AesEncryptor(@Value("${blog.security.encryption-key:nanmuli-blog-key}") String secretKey) {
    // ...
}

// 修改后: 从 ConfigService 读取
public AesEncryptor(ConfigService configService) {
    String key = configService.get("blog.security.encryption-key", "nanmuli-blog-key");
    // ... 同样的 keyBytes 处理逻辑
}
```

### 4.6 运行时刷新端点

在 `ConfigController` 中新增:

```java
@PostMapping("/admin/config/refresh")
public Result<Map<String, Object>> refreshAll() {
    configAppService.refreshCache();          // 清空 Spring Cache
    configService.reload();                   // 重载 DB 配置到内存
    crawlerTaskClient.reloadPool();           // 重建 HTTP 连接池
    crawlerTaskClient.refreshConfig();        // 通知 Python 刷新
    return Result.success(Map.of(
        "message", "所有配置已刷新",
        "affected", List.of("Java ConfigService", "CrawlerTaskClient pool", "Python crawler")
    ));
}
```

### 4.7 application-dev.yml 清理

移除已迁移的配置项，仅保留注释说明其已迁移至 `sys_config`:

```yaml
# ===== 爬虫服务配置（已迁移至 sys_config 表，此处仅保留注释） =====
# crawler.service.* → sys_config WHERE group_name='crawler'
# crawler.callback.* → 同上
# blog.security.*     → sys_config WHERE group_name='blog'

# ===== 数据库/Redis（基础设施，保留在 yml） =====
spring:
  datasource:
    url: jdbc:postgresql://localhost:5433/nanmuli_blog
    # ...
```

### 4.8 新增种子数据

在 Flyway 迁移中新增:

```sql
INSERT INTO sys_config (config_key, config_value, default_value, description, group_name, is_public, input_type, is_encrypted, is_sensitive)
VALUES
    ('crawler.service.base-url', 'http://localhost:8500', 'http://localhost:8500', 'Python爬虫服务地址', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.service.api-key', '', '', 'Python API认证密钥', 'crawler', FALSE, 'password', TRUE, TRUE),
    ('crawler.service.connect-timeout', '10000', '10000', '连接超时(毫秒)', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.service.read-timeout', '30000', '30000', '读取超时(毫秒)', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.http.pool.max-total', '20', '20', 'HTTP连接池最大连接数', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.http.pool.max-per-route', '10', '10', '单路由最大连接数', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.callback.api-key', '', '', '回调认证密钥（Java/Python共享）', 'crawler', FALSE, 'password', TRUE, TRUE),
    ('blog.security.encryption-key', 'nanmuli-blog-key', 'nanmuli-blog-key', 'AES-128加密密钥（16字节）', 'blog', FALSE, 'password', TRUE, TRUE)
ON CONFLICT (config_key) DO UPDATE SET
    description = EXCLUDED.description,
    group_name = EXCLUDED.group_name,
    is_encrypted = EXCLUDED.is_encrypted,
    is_sensitive = EXCLUDED.is_sensitive;
```

---

## 5. Phase 3: Python 侧全量配置 DB 化

### 5.1 配置分组与命名规范

Python `.env` 变量名 → DB `config_key` 映射规则:

```
.env: MAX_PAGES_LIMIT     → DB: crawler.limit.max_pages
.env: SEARCH_PAGE_TIMEOUT_MS → DB: crawler.search.page_timeout_ms
.env: QUALITY_SOURCE_WEIGHT   → DB: crawler.quality.source_weight
.env: DIGEST_CRON             → DB: crawler.digest.cron
```

完整映射表（65 项）:

#### 5.1.1 基础服务 (5项) → group: crawler

| .env key | DB config_key | 默认值 |
|----------|---------------|--------|
| `HOST` | `crawler.host` | 0.0.0.0 |
| `PORT` | `crawler.port` | 8500 |
| `DEBUG` | `crawler.debug` | false |
| `LOG_LEVEL` | `crawler.log_level` | INFO |
| `STANDALONE` | `crawler.standalone` | false |

#### 5.1.2 爬取限制 (3项) → group: crawler

| .env key | DB config_key | 默认值 |
|----------|---------------|--------|
| `MAX_PAGES_LIMIT` | `crawler.limit.max_pages` | 20 |
| `MAX_DEPTH_LIMIT` | `crawler.limit.max_depth` | 3 |
| `MAX_CONCURRENT_CRAWLS` | `crawler.limit.max_concurrent` | 3 |

#### 5.1.3 搜索配置 (10项) → group: crawler.search

| .env key | DB config_key | 默认值 |
|----------|---------------|--------|
| `SEARCH_PAGE_TIMEOUT_MS` | `crawler.search.page_timeout_ms` | 15000 |
| `SEARCH_BROWSER_FETCH_TIMEOUT_MS` | `crawler.search.browser_fetch_timeout_ms` | 20000 |
| `SEARCH_HTTPX_FALLBACK_TIMEOUT` | `crawler.search.httpx_fallback_timeout` | 15 |
| `SEARCH_CLIENT_TIMEOUT` | `crawler.search.client_timeout` | 30 |
| `SEARCH_WARMUP_TIMEOUT` | `crawler.search.warmup_timeout` | 10 |
| `SEARCH_PAGE_RETRIES` | `crawler.search.page_retries` | 2 |
| `SEARCH_MAX_PAGES_PER_ENGINE` | `crawler.search.max_pages_per_engine` | 5 |
| `SEARCH_MIN_WORD_COUNT` | `crawler.search.min_word_count` | 50 |
| `MAX_DOMAIN_DEDUP` | `crawler.search.max_domain_dedup` | 2 |
| `SEARCH_CRAWL_DEADLINE_SECONDS` | `crawler.search.crawl_deadline_seconds` | 300 |
| `SEARCH_PROGRESSIVE_FALLBACK_ENABLED` | `crawler.search.progressive_fallback_enabled` | true |

#### 5.1.4 搜索引擎延迟 (6项) → group: crawler.search

| .env key | DB config_key | 默认值 |
|----------|---------------|--------|
| `SEARCH_ENGINE_SWITCH_DELAY_MIN` | `crawler.search.engine_switch_delay_min` | 2.0 |
| `SEARCH_ENGINE_SWITCH_DELAY_MAX` | `crawler.search.engine_switch_delay_max` | 5.0 |
| `SEARCH_PAGE_DELAY_MIN` | `crawler.search.page_delay_min` | 0.8 |
| `SEARCH_PAGE_DELAY_MAX` | `crawler.search.page_delay_max` | 2.0 |
| `OPTIMIZATION_ROUND_DELAY_MIN` | `crawler.search.optimization_round_delay_min` | 2.0 |
| `OPTIMIZATION_ROUND_DELAY_MAX` | `crawler.search.optimization_round_delay_max` | 4.0 |

#### 5.1.5 质量评估 (16项) → group: crawler.quality

| .env key | DB config_key | 默认值 |
|----------|---------------|--------|
| `MIN_CONTENT_LENGTH` | `crawler.quality.min_content_length` | 100 |
| `QUALITY_SOURCE_WEIGHT` | `crawler.quality.source_weight` | 0.4 |
| `QUALITY_CONTENT_WEIGHT` | `crawler.quality.content_weight` | 0.6 |
| `QUALITY_KEEP_THRESHOLD` | `crawler.quality.keep_threshold` | 70 |
| `QUALITY_REVIEW_THRESHOLD` | `crawler.quality.review_threshold` | 50 |
| `EVAL_PASS_THRESHOLD` | `crawler.quality.eval_pass_threshold` | 65 |
| `EVAL_REVIEW_THRESHOLD` | `crawler.quality.eval_review_threshold` | 45 |
| `DEEP_EVAL_REVIEW_THRESHOLD` | `crawler.quality.deep_eval_review_threshold` | 25 |
| `EVAL_WEIGHT_ANGLE` | `crawler.quality.weight_angle` | 0.25 |
| `EVAL_WEIGHT_SOURCE` | `crawler.quality.weight_source` | 0.20 |
| `EVAL_WEIGHT_DEPTH` | `crawler.quality.weight_depth` | 0.15 |
| `EVAL_WEIGHT_TEMPORAL` | `crawler.quality.weight_temporal` | 0.15 |
| `EVAL_WEIGHT_PERSPECTIVE` | `crawler.quality.weight_perspective` | 0.15 |
| `EVAL_WEIGHT_LANGUAGE` | `crawler.quality.weight_language` | 0.10 |
| `QUALITY_CLICKBAIT_KEYWORDS` | `crawler.quality.clickbait_keywords` | (长字符串) |
| `QUALITY_AD_KEYWORDS` | `crawler.quality.ad_keywords` | (长字符串) |
| `QUALITY_PAYWALL_INDICATORS` | `crawler.quality.paywall_indicators` | (长字符串) |

#### 5.1.6 日报配置 (7项) → group: crawler.digest

| .env key | DB config_key | 默认值 |
|----------|---------------|--------|
| `DIGEST_ENABLED` | `crawler.digest.enabled` | false |
| `DIGEST_CRON` | `crawler.digest.cron` | 0 8 * * 1-5 |
| `DIGEST_SEARCH_ENGINE` | `crawler.digest.search_engine` | bing |
| `DIGEST_SECTIONS` | `crawler.digest.sections` | (JSON数组) |
| `DIGEST_SECTION_RESULT_MULTIPLIER` | `crawler.digest.section_result_multiplier` | 2 |
| `DIGEST_INTER_SECTION_DELAY` | `crawler.digest.inter_section_delay` | 2.0 |
| `DIGEST_HISTORY_LOAD_COUNT` | `crawler.digest.history_load_count` | 3 |

#### 5.1.7 回调配置 (3项) → group: crawler.callback

| .env key | DB config_key | 默认值 | is_encrypted |
|----------|---------------|--------|--------------|
| `CALLBACK_URL` | `crawler.callback.url` | (空) | false |
| `CALLBACK_API_KEY` | `crawler.callback.api_key` | (空) | true |
| `JAVA_API_URL` | `crawler.callback.java_api_url` | (空) | false |

#### 5.1.8 优化配置 (5项) → group: crawler.optimization

| .env key | DB config_key | 默认值 |
|----------|---------------|--------|
| `OPTIMIZATION_ENABLED` | `crawler.optimization.enabled` | false |
| `OPTIMIZATION_TARGET_SCORE` | `crawler.optimization.target_score` | 0.7 |
| `OPTIMIZATION_MAX_ROUNDS` | `crawler.optimization.max_rounds` | 3 |
| `OPTIMIZATION_MIN_IMPROVEMENT` | `crawler.optimization.min_improvement` | 0.03 |
| `OPTIMIZATION_MODE` | `crawler.optimization.mode` | keyword |

#### 5.1.9 茧房突破 (3项) → group: crawler.bubble

| .env key | DB config_key | 默认值 |
|----------|---------------|--------|
| `BUBBLE_BREAKER_ENABLED` | `crawler.bubble.enabled` | false |
| `BUBBLE_MIN_SOURCE_DIVERSITY` | `crawler.bubble.min_source_diversity` | 0.6 |
| `BUBBLE_CROSS_LANGUAGE` | `crawler.bubble.cross_language` | true |
| `BUBBLE_MAX_TRANSLATE_TOKENS` | `crawler.bubble.max_translate_tokens` | 200 |

#### 5.1.10 独立模式认证 (5项) → group: crawler.auth

| .env key | DB config_key | 默认值 | is_encrypted |
|----------|---------------|--------|--------------|
| `API_KEYS` | `crawler.auth.api_keys` | (空) | true |
| `AUTH_ENABLED` | `crawler.auth.enabled` | true | false |
| `AUTH_PROTECTED_PREFIXES` | `crawler.auth.protected_prefixes` | /api/v1,/crawl,... | false |
| `AUTH_HEADER_NAME` | `crawler.auth.header_name` | X-API-Key | false |

#### 5.1.11 独立模式 DB 配置 (3项) → group: crawler.db

| .env key | DB config_key | 默认值 |
|----------|---------------|--------|
| `DB_PATH` | `crawler.db.path` | data/crawler.db |
| `DB_BUSY_TIMEOUT` | `crawler.db.busy_timeout` | 5000 |
| `MAX_CONCURRENT_TASKS` | `crawler.db.max_concurrent_tasks` | 3 |

#### 5.1.12 关键词搜索配置 (3项) → group: crawler.keyword

| .env key | DB config_key | 默认值 |
|----------|---------------|--------|
| `KEYWORD_MAX_CONSECUTIVE_EMPTY` | `crawler.keyword.max_consecutive_empty` | 2 |
| `KEYWORD_MAX_VARIANTS` | `crawler.keyword.max_variants` | 4 |
| `KEYWORD_INTER_SEARCH_DELAY` | `crawler.keyword.inter_search_delay` | 2.0 |

### 5.2 Python 侧改造

#### 5.2.1 扩展 backend_config.py

**文件**: `crawler-service/standalone/backend_config.py` (大幅扩展)

核心改动: `fetch_from_backend()` 拉取到的配置，通过 `_apply_all_settings()` 方法写入 `settings` Pydantic 对象:

```python
async def _apply_all_settings(config: dict[str, str]) -> None:
    """将从 Java 后端拉取的全部配置写入 Pydantic Settings"""
    _apply_proxy_config(config)  # 已有逻辑

    # AI 配置
    _apply_ai_config(config)

    # 搜索配置
    _apply_search_config(config)

    # 质量评估配置
    _apply_quality_config(config)

    # 日报配置
    _apply_digest_config(config)

    # 回调配置
    _apply_callback_config(config)

    # 优化/茧房/认证/DB 配置
    _apply_misc_config(config)

    # 关键词检测列表（长字符串）
    _apply_keyword_lists(config)

    logger.info("[BackendConfig] All settings applied from backend")
```

每个子函数按 DB key 映射到 settings 属性:

```python
def _apply_search_config(config: dict[str, str]) -> None:
    settings.search_page_timeout_ms = _int(config, "search.page_timeout_ms", 15000)
    settings.search_browser_fetch_timeout_ms = _int(config, "search.browser_fetch_timeout_ms", 20000)
    # ... 其余搜索配置
```

#### 5.2.2 更新 main.py lifespan 中的配置拉取

**文件**: `crawler-service/main.py:70-75`

```python
# 原有代码只拉取了 AI/代理配置，改后拉取全部配置
if settings.standalone:
    from standalone import backend_config
    await backend_config.fetch_from_backend()
```

无需大改，因为 `backend_config.fetch_from_backend()` 内部已扩展为全量加载。

#### 5.2.3 扩展 /api/v1/config/refresh 端点

**文件**: `crawler-service/standalone/routes.py:373-380`

现有代码已支持，无需改动。`backend_config.refresh()` 内部会重新拉取并应用全量配置。

### 5.3 新增 Java 侧种子数据

在 V1.12 Flyway 迁移中追加 Phase 3 的新增配置种子（65 项）:

```sql
-- ===== 爬虫基础服务 (5项) =====
INSERT INTO sys_config (config_key, config_value, default_value, description, group_name, is_public, input_type)
VALUES
    ('crawler.host', '0.0.0.0', '0.0.0.0', '爬虫服务监听地址', 'crawler', FALSE, 'text'),
    ('crawler.port', '8500', '8500', '爬虫服务监听端口', 'crawler', FALSE, 'text'),
    ('crawler.debug', 'false', 'false', '爬虫Debug模式', 'crawler', FALSE, 'switch'),
    ('crawler.log_level', 'INFO', 'INFO', '爬虫日志级别', 'crawler', FALSE, 'text'),
    ('crawler.standalone', 'true', 'true', '独立模式开关', 'crawler', FALSE, 'switch')
ON CONFLICT (config_key) DO NOTHING;

-- ===== 爬取限制 (3项) =====
INSERT INTO sys_config (config_key, config_value, default_value, description, group_name, is_public, input_type)
VALUES
    ('crawler.limit.max_pages', '20', '20', '最大爬取页数', 'crawler', FALSE, 'text'),
    ('crawler.limit.max_depth', '3', '3', '最大爬取深度', 'crawler', FALSE, 'text'),
    ('crawler.limit.max_concurrent', '3', '3', '最大并发爬取数', 'crawler', FALSE, 'text')
ON CONFLICT (config_key) DO NOTHING;

-- ... (其余 57 项同理)
```

完整 INSERT 语句见附录 A。

### 5.4 Python 侧 .env 文件清理

`.env` 文件保留以下基础设施配置（Python 启动必须的环境变量）:

```env
# ===== 基础设施（保留在 .env，不进入 DB） =====
PYTHONUTF8=1
NO_PROXY=localhost,127.0.0.1,.local

# ===== 以下配置已迁移至 sys_config 表，DB 不可用时作为 fallback =====
# HOST=0.0.0.0
# PORT=8500
# ... (注释掉所有已迁移项)
```

`config.py` 中的 Pydantic Settings 保留默认值作为 fallback（DB 不可用时的降级方案）。

---

## 6. Phase 4: 前端管理页增强

### 6.1 后端 API 扩展

#### 6.1.1 新增按分组查询接口

**文件**: `ConfigController.java` — 新增:

```java
@GetMapping("/admin/config/group/{groupName}")
public Result<List<ConfigDTO>> listByGroup(@PathVariable String groupName) {
    return Result.success(configAppService.getByGroup(groupName));
}
```

**文件**: `ConfigAppService.java` — 新增:

```java
@Transactional(readOnly = true)
public List<ConfigDTO> getByGroup(String groupName) {
    return configRepository.findByGroup(groupName).stream()
            .map(this::toAdminDTO)
            .collect(Collectors.toList());
}
```

#### 6.1.2 配置刷新端点（Phase 2 已完成）

```java
@PostMapping("/admin/config/refresh")
public Result<Map<String, Object>> refreshAll() { ... }
```

### 6.2 前端改造

**文件**: `frontend/src/views/admin/config/Index.vue` — 主要改动:

1. **Tab 切换改为按 `group_name` 动态生成**

```typescript
// 修改前: 硬编码 groupNames + groupOrder
const groupNames: Record<string, string> = {
  site: '站点配置',
  'crawler-ai': '爬虫AI配置',
  'crawler-proxy': '代理配置',
}

// 修改后: 动态从 group_name 聚合，支持 10 个分组
const groupLabels: Record<string, string> = {
  site: '站点配置',
  blog: '博客运行参数',
  crawler: '爬虫基础',
  'crawler.ai': '爬虫AI配置',
  'crawler.proxy': '代理配置',
  'crawler.search': '搜索引擎参数',
  'crawler.quality': '质量评估',
  'crawler.digest': '日报配置',
  'crawler.optimization': '搜索优化',
  'crawler.bubble': '茧房突破',
  'crawler.callback': '回调配置',
  'crawler.auth': '认证配置',
  'crawler.db': '数据库配置',
  'crawler.limit': '爬取限制',
  'crawler.keyword': '关键词搜索',
}

const groupedConfigs = computed(() => {
  const groups: Record<string, Config[]> = {}
  configs.value.forEach((config) => {
    const group = config.groupName || 'other'
    if (!groups[group]) groups[group] = []
    groups[group]!.push(config)
  })
  return groups
})
```

2. **增加「刷新配置」按钮**

```vue
<el-button type="warning" @click="handleRefreshAll">
  刷新全部配置（通知所有服务重载）
</el-button>
```

3. **敏感配置遮罩显示**

```vue
<template v-if="config.isSensitive">
  <el-tag type="danger" size="small" effect="plain">
    敏感配置 — 保存后加密存储，此处显示为脱敏值
  </el-tag>
</template>
```

4. **加密标记显示**

```vue
<template v-if="config.isEncrypted">
  <el-tag type="warning" size="small" effect="plain">
    AES-128 加密存储
  </el-tag>
</template>
```

### 6.3 TypeScript 类型更新

**文件**: `frontend/src/types/config.ts`:

```typescript
export interface Config {
  id: number
  configKey: string
  configValue: string
  defaultValue?: string
  description: string
  groupName: string
  isPublic: boolean
  inputType: string
  isEncrypted: boolean    // 新增
  isSensitive: boolean    // 新增 (替代前端关键词匹配判断)
  sensitive?: boolean     // 保留兼容旧字段
  createdAt: string
  updatedAt: string
}
```

---

## 7. 测试计划

### 7.1 Phase 1 验证

| # | 测试项 | 验证方法 |
|---|--------|----------|
| 1 | Flyway 迁移成功执行 | `./mvnw flyway:migrate` 无错误 |
| 2 | 新列存在且默认值正确 | `SELECT column_name, data_type, column_default FROM information_schema.columns WHERE table_name='sys_config'` |
| 3 | 已有数据未丢失 | `SELECT count(*) FROM sys_config` 与迁移前一致 |
| 4 | Docker 初始化 schema 一致 | 对比 `deploy/db/init-scripts/schema.sql` 与 Flyway 最终态 |

### 7.2 Phase 2 验证

| # | 测试项 | 验证方法 |
|---|--------|----------|
| 1 | ConfigService 启动加载 | 启动日志含 `Loaded N configs from DB` |
| 2 | CrawlerTaskClient 正常初始化 | 日志含 `[CrawlerTaskClient] initialized` |
| 3 | 回调认证正常工作 | `curl -X POST /api/internal/collector/callback -H "X-Callback-Key: {key}"` 返回 200 |
| 4 | 运行时修改配置生效 | 改 `crawler.service.read-timeout` → 调 `POST /api/admin/config/refresh` → 日志确认连接池已重载 |
| 5 | AES 加密/解密正确 | 改 `blog.security.encryption-key` → 刷新 → 新密钥能正确解密旧数据 |

### 7.3 Phase 3 验证

| # | 测试项 | 验证方法 |
|---|--------|----------|
| 1 | Python 启动拉取全部配置 | 日志含 `Applied all settings from backend` + 具体配置数量 |
| 2 | `/crawl/search` 使用 DB 配置参数 | 创建搜索任务 → 日志确认 search_page_timeout_ms 等参数为 DB 值 |
| 3 | 前端改 crawler 配置后 Python 刷新 | 改 `crawler.quality.min_content_length` → 刷新 → Python 日志确认新值生效 |
| 4 | .env fallback 降级正常 | 停止 Java 后端 → Python 启动 → 使用 .env 默认值 + 日志 Warn |

### 7.4 Phase 4 验证

| # | 测试项 | 验证方法 |
|---|--------|----------|
| 1 | 配置管理页显示所有分组 | 浏览器访问 `/admin/config` → 确认 10+ 分组 Tab 显示 |
| 2 | 敏感配置遮罩显示 | `crawler.ai.api_key` 显示为 `********` |
| 3 | 加密配置标记显示 | `isEncrypted=true` 的项显示「AES-128 加密存储」标签 |
| 4 | 「刷新全部配置」按钮生效 | 点击 → 弹窗确认 → 所有服务日志显示重新加载 |

---

## 8. 回滚方案

### 8.1 Flyway 回滚

Flyway 不支持自动回滚。回滚 V1.12 需手动执行:

```sql
-- 删除新增列
ALTER TABLE sys_config DROP COLUMN IF EXISTS is_encrypted;
ALTER TABLE sys_config DROP COLUMN IF EXISTS is_sensitive;
ALTER TABLE sys_config DROP COLUMN IF EXISTS default_value;

-- 恢复旧的 group_name
UPDATE sys_config SET group_name = 'ai' WHERE config_key IN ('ai.enabled', 'ai.model', 'ai.autoTags', 'ai.autoSummary');
```

然后删除 Flyway 历史记录: `DELETE FROM flyway_schema_history WHERE version = '1.12';`

### 8.2 Java 侧回滚

`ConfigService` 加载失败时打印 ERROR 日志但**不阻塞启动**，各消费方使用 `@Value` 的 fallback 默认值。

回滚步骤:
1. 恢复 `application-dev.yml` 中被注释的 `crawler.*` 配置
2. 恢复 `CrawlerTaskClient` 的 `@Value` 构造器注入
3. 恢复 `AesEncryptor` 的 `@Value` 注入
4. 重启 Java 后端

### 8.3 Python 侧回滚

`backend_config.fetch_from_backend()` 失败时仅打印 warning 日志，不影响启动。撤销 `.env` 注释即可恢复 env-only 模式。

---

## 附录 A: 完整种子数据 SQL

```sql
-- ============================================
-- sys_config 全量种子数据 (Phase 1-3 合并)
-- 执行于 Flyway V1.12 迁移中
-- ============================================

-- Phase 2: Java 侧迁移配置 (8项)
INSERT INTO sys_config (config_key, config_value, default_value, description, group_name, is_public, input_type, is_encrypted, is_sensitive)
VALUES
    ('crawler.service.base-url', 'http://localhost:8500', 'http://localhost:8500', 'Python爬虫服务地址', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.service.api-key', '', '', 'Python API认证密钥', 'crawler', FALSE, 'password', TRUE, TRUE),
    ('crawler.service.connect-timeout', '10000', '10000', '连接超时(毫秒)', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.service.read-timeout', '30000', '30000', '读取超时(毫秒)', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.http.pool.max-total', '20', '20', 'HTTP连接池最大连接数', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.http.pool.max-per-route', '10', '10', '单路由最大连接数', 'crawler', FALSE, 'text', FALSE, FALSE),
    ('crawler.callback.api-key', '', '', '回调认证密钥（Java/Python共享）', 'crawler', FALSE, 'password', TRUE, TRUE),
    ('blog.security.encryption-key', 'nanmuli-blog-key', 'nanmuli-blog-key', 'AES-128加密密钥（16字节）', 'blog', FALSE, 'password', TRUE, TRUE)
ON CONFLICT (config_key) DO NOTHING;

-- Phase 3: Python 侧迁移配置 (65项)
-- 基础服务
INSERT INTO sys_config (config_key, config_value, default_value, description, group_name, is_public, input_type)
VALUES
    ('crawler.host', '0.0.0.0', '0.0.0.0', '爬虫服务监听地址', 'crawler', FALSE, 'text'),
    ('crawler.port', '8500', '8500', '爬虫服务监听端口', 'crawler', FALSE, 'text'),
    ('crawler.debug', 'false', 'false', '爬虫Debug模式', 'crawler', FALSE, 'switch'),
    ('crawler.log_level', 'INFO', 'INFO', '爬虫日志级别', 'crawler', FALSE, 'text'),
    ('crawler.standalone', 'true', 'true', '独立模式开关', 'crawler', FALSE, 'switch')
ON CONFLICT (config_key) DO NOTHING;

-- 爬取限制
INSERT INTO sys_config (config_key, config_value, default_value, description, group_name, is_public, input_type)
VALUES
    ('crawler.limit.max_pages', '20', '20', '最大爬取页数', 'crawler', FALSE, 'text'),
    ('crawler.limit.max_depth', '3', '3', '最大爬取深度', 'crawler', FALSE, 'text'),
    ('crawler.limit.max_concurrent', '3', '3', '最大并发爬取数', 'crawler', FALSE, 'text')
ON CONFLICT (config_key) DO NOTHING;

-- (后续 57 项见 5.1.3 ~ 5.1.12 的完整映射表，此处省略以保持文档可读性)
-- 完整 SQL 通过 Flyway 迁移脚本 V1_12__unify_sys_config.sql 发布
```

---

## 附录 B: 实施优先级与估算

| Phase | 文件数 | 新增文件 | 修改文件 | 估算工时 | 风险 |
|-------|--------|----------|----------|----------|------|
| Phase 1 | 5 | 1 (Flyway) | 4 | 2h | 低 — 纯 schema 变更，增加列不影响现有逻辑 |
| Phase 2 | 7 | 1 (ConfigService) | 6 | 4h | 中 — CrawlerTaskClient/AesEncryptor 是核心链路 |
| Phase 3 | 3 | 0 | 3 | 6h | 高 — backend_config.py 改动大，需逐项映射测试 |
| Phase 4 | 4 | 0 | 4 | 3h | 低 — 纯 UI 增强，不影响核心逻辑 |

**建议执行顺序**: Phase 1 → Phase 2 → Phase 3 → Phase 4，每阶段完成后验证再进入下一阶段。
