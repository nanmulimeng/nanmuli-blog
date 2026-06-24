# 集成测试基建方案（X03-02/03）

> 状态：**依赖铺路就绪，集成测试待补**
> 背景：审计 X03 发现 backend 111 个测试全 Mockito 单测、零集成——Sa-Token/MyBatis-Plus/真实 PG schema 从未在 CI 跑过，看不住"登录失败/配置不生效/schema 缺列/日报不触发"。本方案引入 testcontainers 集成测试基建，补齐关键路径。

## 已完成的铺路

1. **pom.xml**：加 `spring-boot-testcontainers` + `testcontainers:junit-jupiter` + `testcontainers:postgresql`（test scope）
2. **maven-surefire-plugin**：`<excludedGroups>integration</excludedGroups>` —— 默认 `mvn test` 不跑 `@Tag("integration")` 的集成测试（不破坏现有 111 单测）
3. 运行集成测试：`mvn verify -Dgroups=integration -DexcludedGroups=`（需 Docker）

## 待补的集成测试（建议优先级）

### 基类 AbstractIntegrationTest
```java
@SpringBootTest
@Testcontainers
@Tag("integration")
abstract class AbstractIntegrationTest {
    @Container @ServiceConnection
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("nanmuli-postgres:pgvector-zhparser");
    // Redis：项目用 Sa-Token alone-redis + 业务缓存，集成测试需 Redis。
    //   方案 A：testcontainers GenericContainer + @ServiceConnection（spring-boot-testcontainers 3.3 支持 Redis）
    //   方案 B：@MockBean RedisTemplate + Sa-Token mock（避开 Redis 容器，但牺牲真实性）
    //   推荐先 A（与生产一致），Redis container 用 redis:7-alpine
}
```

注：`@ServiceConnection`（Spring Boot 3.1+）自动注入 container 的 PG 连接到 DataSource，无需写 @DynamicPropertySource。

### 关键路径集成测试（X03-03 补齐覆盖）
| 优先级 | 测试 | 验证 |
|---|---|---|
| P0 | AuthController + 真实 PG/Redis | 登录/登出/token 失效（X03 发现 Auth 零测试） |
| P0 | schema 完整性 | 真实 PG 启动 + Flyway/​schema.sql 建表成功（B15/X02） |
| P1 | ConfigAppService | 配置 CRUD + AES 加密落库 + crawler 重载（B07） |
| P1 | WebCollectorAppService 状态机 | 任务状态流转 + 乐观锁 + 转文章（真实事务） |
| P2 | DigestFingerprint saveAll | B09-01 修复的指纹批量 insert（真实 PG，验证 @Insert 补 id） |

## 为什么本批没直接写集成测试

1. **Redis 处理需设计**：Sa-Token alone-redis + 业务缓存都依赖 Redis，集成测试需 Redis container（方案 A/B 取舍），需确认不与 Sa-Token 配置冲突
2. **需 Docker 运行验证**：testcontainers 集成测试需本地/CI Docker，我无法在此环境跑通验证基类正确
3. **pgvector 自建镜像**：项目用 `nanmuli-postgres:pgvector-zhparser`（自建，含 zhparser/pgvector），集成测试 container 要用该镜像（需本地构建）或用标准 pgvector 镜像 + 手动建扩展

## 启用步骤（专注窗口）

1. 本地构建 `nanmuli-postgres:pgvector-zhparser` 镜像（`cd deploy/db && docker build .`）
2. 写 `AbstractIntegrationTest`（PG + Redis container + @ServiceConnection），跑通一个冒烟测试
3. 逐个补 P0/P1 集成测试（Auth / schema / Config / WebCollector）
4. CI 加 `integration` job（`mvn verify -Dgroups=integration`，需 Docker service）
