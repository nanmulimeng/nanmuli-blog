# B07 系统配置 Config 排查报告

> **模块编号**：B07
> **排查范围**：DB 化配置（sys_config）、AES 加密、敏感配置脱敏、crawler 配置重载触发、缓存刷新、配置初始化
> **基线 commit**：`6ae930098405f4d0553d96a852f3345d0f39682e`
> **工作区状态**：脏。涉及本模块的未提交文件：`backend/src/main/java/com/nanmuli/blog/infrastructure/persistence/config/ConfigRepositoryImpl.java`（仅 `findAll()` 增加 `orderByAsc(configKey)`，无功能影响，见 B07-09）。其他脏文件（WebCollectPageMapper/search.py/knowledge_base.py 等）与本模块无关。
> **排查日期**：2026-06-23
> **排查人**：B07 模块排查 agent
> **状态**：草稿

---

## 模块概览

**职责**：将博客与 crawler 运行时配置从 application.yml 迁移到 `sys_config` 表，支持管理端 CRUD、敏感配置 AES 加密落库、前端脱敏回显、改后触发 crawler 配置刷新与 Java 侧 ConfigService/连接池重载、启动时按环境变量补种默认配置。

**关键文件**：
- `backend/src/main/java/com/nanmuli/blog/infrastructure/config/security/AesEncryptor.java:1-72` —— AES 加解密主类（AES-128/ECB/PKCS5Padding，密钥来源 @Value）
- `backend/src/main/java/com/nanmuli/blog/application/config/ConfigAppService.java:1-183` —— 配置 CRUD + 脱敏 + 缓存
- `backend/src/main/java/com/nanmuli/blog/interfaces/rest/ConfigController.java:1-115` —— 配置 Controller + crawler 重载编排
- `backend/src/main/java/com/nanmuli/blog/infrastructure/config/ConfigService.java:1-73` —— 内存缓存式配置读取（替代 @Value）
- `backend/src/main/java/com/nanmuli/blog/infrastructure/config/initializer/SystemConfigInitializer.java:1-139` —— 启动补种
- `backend/src/main/java/com/nanmuli/blog/infrastructure/persistence/config/ConfigRepositoryImpl.java:1-61` —— 仓储实现（脏文件）
- `backend/src/main/java/com/nanmuli/blog/infrastructure/crawler/CrawlerTaskClient.java:220-227` —— crawler 配置刷新通知（refreshConfig 吞异常）

**对外接口 / 依赖**：
- 对外：`/api/config/public`、`/api/config/list`（公开）；`/api/admin/config/{list,key,reset-default,refresh}`（admin）
- 依赖：`sys_config` 表；`BLOG_SECURITY_ENCRYPTION_KEY` 环境变量；CrawlerTaskClient（→ B10）；Sa-Token（→ B06）；Spring Cache Redis

**已读文件清单**：
- `infrastructure/config/security/AesEncryptor.java` —— 通读
- `application/config/ConfigAppService.java` —— 通读
- `interfaces/rest/ConfigController.java` —— 通读
- `infrastructure/config/ConfigService.java` —— 通读
- `infrastructure/config/initializer/SystemConfigInitializer.java` —— 通读
- `infrastructure/persistence/config/ConfigRepositoryImpl.java` —— 通读 + git diff
- `domain/config/Config.java`、`ConfigRepository.java`、`ConfigMapper.java` —— 通读
- `application/config/dto/ConfigDTO.java`、`command/*` —— 通读
- `infrastructure/config/security/SaTokenConfig.java` —— 通读（引用 B06）
- `infrastructure/crawler/CrawlerTaskClient.java` —— 通读（引用 B10）
- `infrastructure/config/cache/CacheConfig.java`、`RedisConfig.java` —— 通读
- `application.yml`/`application-dev.yml`/`application-prod.yml` —— 通读
- `db/migration/V1_21__remove_unnecessary_configs.sql`（片段）、`V1_12__unify_sys_config.sql`（片段）—— 片段
- 测试：`AesEncryptorTest`、`ConfigAppServiceTest`、`SystemConfigInitializerTest` —— 通读
- `BaseAggregateRoot.java` —— 通读

**主模块归属**：本模块是 **AES 加密 / `AesEncryptor`** 的主模块（计划 §8.6），深查。X06（配置一致性）引用本模块。CrawlerTaskClient 是 B10 主模块，本模块只引用。

---

## `[Bug]` 代码正确性与潜在缺陷

> 排查范围：AesEncryptor、ConfigAppService、ConfigController、ConfigService、SystemConfigInitializer、CrawlerTaskClient.refreshConfig。

### [P1] [Bug] `AesEncryptor` 的 `@Value` 默认值 `local-dev-encryption-key` 会通过弱密钥校验，dev/漏配场景下用公开弱密钥加密敏感配置  <!-- 编号：B07-01 -->
- **定位**：`backend/src/main/java/com/nanmuli/blog/infrastructure/config/security/AesEncryptor.java:21`（`@Value("${blog.security.encryption-key:local-dev-encryption-key}")`）配合 `:32-40` `isUnsafeKey`
- **现象**：`isUnsafeKey` 只拒绝 ①null/blank/长度<16 ②等于 `nanmuli-blog-key` ③前缀 `your_`/`sk-your-`。默认值 `local-dev-encryption-key`（24 字符、不在黑名单）**会通过**校验。当 dev profile 启动且未显式设置 `blog.security.encryption-key`（application-dev.yml 已注释"迁移至 sys_config"但 `AesEncryptor` 根本不读 sys_config），或任何环境漏配 `BLOG_SECURITY_ENCRYPTION_KEY` 且 yml 无强制占位符时，会用这个**写死在源码里的公开弱密钥**加密所有 API key。
- **影响**：攻击者拿到 DB 或密文后，可用源码中公开的 `local-dev-encryption-key` 直接解密所有 `crawler.service.api-key`/`crawler.callback.api-key`/`crawler.ai.api_key`。在 dev 误连生产库、或忘记设 env 的真实场景下，等于无加密。`application-prod.yml:71` 用 `${BLOG_SECURITY_ENCRYPTION_KEY}`（无默认值）能阻断 prod 漏配，但 dev 与未指定 profile 的启动无防护。
- **根因/分析**：默认值设计意图是"本地开发兜底"，但放在 `@Value` 默认位且能通过校验，使弱密钥成为静默成功路径。已排除误判：`application-prod.yml` 确实强制 env（已验证），但 `application.yml` 默认 `profiles.active: dev`（application.yml:5），dev profile 下 `AesEncryptor` 会落到此默认值。
- **修复方向**：①移除 `@Value` 默认值，改为 `${BLOG_SECURITY_ENCRYPTION_KEY}`（无默认值），所有环境强制设置（**小**）；②或把 `local-dev-encryption-key` 加入 `isUnsafeKey` 黑名单（**小**）；③dev profile 也应显式配置一个仅在本地有效的随机值，不写死源码（**小**）。
- **关联**：X06-06（占位符校验）、B15-03（encryption-key seed 三轨脱节）、risk-register 已记录 prod 默认值历史问题（已修 prod，未覆盖 dev）。

### [P2] [Bug] AES 使用 ECB 模式（`Cipher.getInstance("AES")`），无 IV，相同明文产生相同密文  <!-- 编号：B07-02 -->
- **定位**：`backend/src/main/java/com/nanmuli/blog/infrastructure/config/security/AesEncryptor.java:47`（`Cipher.getInstance(ALGORITHM)` 即 `"AES"`）、`:63`（解密同）
- **现象**：标准 JDK provider 下 `Cipher.getInstance("AES")` 解析为 `AES/ECB/PKCS5Padding`。全代码库无 `IvParameterSpec`/`SecureRandom`/`AES/GCM`/`AES/CBC`（已 grep 确认）。相同明文（如多个环境相同的 API key）产生完全相同的 `{AES}<base64>` 密文。
- **影响**：ECB 不抗模式分析，攻击者可识别相同密文（如发现两行 config_value 密文一致即可推断明文相同）。对短小且唯一的 API key 实际利用门槛高，但违反加密最佳实践，且 `isUnsafeKey` 的"严格"姿态与 ECB 的弱实现形成讽刺对比。
- **根因/分析**：实现时未指定 mode。已排除误判：非 CBC 误写漏 IV，是根本没指定 mode。
- **修复方向**：①改为 `AES/GCM/NoPadding`，每次加密生成随机 12 字节 IV 并与密文一同 base64（**中**，需数据迁移已有密文）；②或 `AES/CBC/PKCS5Padding` + 随机 16 字节 IV 前缀（**中**）。迁移需对已有 `{AES}` 密文做一次性解密-重加密。
- **关联**：B07-01（密钥）、X06-06。

### [P2] [Bug] `AesEncryptor.encrypt` 失败时静默回退明文，敏感配置以明文落库且无告警  <!-- 编号：B07-03 -->
- **定位**：`backend/src/main/java/com/nanmuli/blog/infrastructure/config/security/AesEncryptor.java:51-54`
- **现象**：`encrypt` catch 所有 `Exception`，只 `log.warn` 后 `return plainText`。`decrypt` 同样回退密文（`:67-70`）。
- **影响**：若加密因任何原因失败（如临时 provider 问题、密钥字节异常），`ConfigAppService.update():78` 会把**明文** API key 直接写入 `sys_config.config_value`，而该行 `is_encrypted=true`，后续读取会尝试 `decrypt` 明文（因无 `{AES}` 前缀直接返回原文，逻辑上自洽），但 DB 中存的是明文——与"加密存储"承诺矛盾，DB 泄露即明文泄露。无任何监控/告警/阻断。
- **根因/分析**：容错设计优先可用性，但敏感配置场景应 fail-fast 而非 fail-open。已排除误判：当前测试用强密钥不会触发，但生产环境任何 Cipher 异常都会走此路径。
- **修复方向**：①`encrypt` 对敏感配置应抛异常而非回退明文，由调用方决定是否允许明文（**小**）；②至少补 ERROR 级日志 + 监控告警（**小**）。
- **关联**：B07-01、B07-02。

### [P2] [Bug] crawler 配置重载链中 `CrawlerTaskClient.refreshConfig()` 吞异常，Python 侧刷新失败时 Java 侧无回滚无告警  <!-- 编号：B07-04 -->
- **定位**：`backend/src/main/java/com/nanmuli/blog/infrastructure/crawler/CrawlerTaskClient.java:220-227`
- **现象**：`refreshConfig()` catch `Exception` 只 `log.warn`。`ConfigController.refreshAfterConfigChange():102-109` 与 `create():73-77` 调用它后直接返回成功。
- **影响**：admin 改 `crawler.service.api-key` 后，Java 侧 ConfigService 已重载、连接池已重建（用新 key），但 Python 侧 `/api/v1/config/refresh` 若失败（网络/Python 重启/旧 key 已失效），Python 仍用旧 key，Java→Python 调用开始 401，而 admin 看到"刷新成功"。crawler 静默失效，需人工查日志。
- **根因/分析**：设计为"通知型"失败可接受（Python 下次请求会自取配置？需查证 Python 侧 config 刷新机制）。但 admin 端无失败反馈，违反闭环完整性。
- **修复方向**：①`refreshConfig` 返回 boolean/抛异常，Controller 聚合后返回部分成功状态（**中**）；②或 Python 侧确认有 fallback 自取机制后补充文档（**小**）。Python 侧 config 拉取行为 [需查证]（C11 主模块）。
- **关联**：B10（CrawlerTaskClient 主模块）、横向主题"跨服务契约一致性"。

### [P3] [Bug] `ConfigAppService.set()` 创建新配置时不强制 `isEncrypted` 跟随 `isSensitive`，可创建明文敏感配置  <!-- 编号：B07-05 -->
- **定位**：`backend/src/main/java/com/nanmuli/blog/application/config/ConfigAppService.java:99-131`（`set` 方法）；`CreateConfigCommand.java` 无 `isEncrypted`/`isSensitive` 字段
- **现象**：`CreateConfigCommand` 只有 `value/description/groupName/inputType/isPublic`，无 `isEncrypted`/`isSensitive`。`set()` 对新 Config 走 `else if (config.getIsEncrypted() == null)` 分支默认 `false`。即 admin 通过 POST 创建的任何新配置都是 `is_encrypted=false`、`is_sensitive=false`，即使 `inputType=password`。
- **影响**：admin 若通过 API 新增一个 API key 类配置，会明文落库。`inputType=password` 只是前端控件提示，不影响存储加密。
- **根因/分析**：Command 缺字段。已排除误判：现有敏感配置靠 `SystemConfigInitializer` 启动补种时设置标记，API 创建路径无法设置。
- **修复方向**：①`CreateConfigCommand` 增加 `isEncrypted`/`isSensitive` 字段（**小**）；②或 `set()` 根据 `inputType=password` 推断加密（**小**）。
- **关联**：B07-03。

---

## `[Security]` 安全漏洞

> 排查范围：AesEncryptor 密钥/IV/异常、脱敏机制、admin 越权、双向 key 比较。

### [P1] [Security] `/api/admin/config/**` 仅 `checkLogin` 不校验 admin 角色，普通登录用户可读写所有配置  <!-- 编号：B07-06 -->
- **定位**：`backend/src/main/java/com/nanmuli/blog/infrastructure/config/security/SaTokenConfig.java:32-34`（`SaInterceptor(handle -> StpUtil.checkLogin())`）；`ConfigAppService.getAllConfigsForAdmin():45-47` 只 `StpUtil.isLogin()` 二次校验；`ConfigController` 所有 `/api/admin/config/**` 无 `@SaCheckRole`/`@PreAuthorize`
- **现象**：拦截器对 `/api/admin/**` 只要求登录，不校验角色。任何登录用户（若系统有非 admin 用户）可 `GET /api/admin/config/list`（含敏感配置脱敏值）、`PUT /api/admin/config/{key}` 改配置、`POST /api/admin/config/refresh` 触发 crawler 重载。
- **影响**：当前若只有单一 admin 用户（单人博客），实际影响有限；但一旦有多用户或 token 泄露给普通用户，可篡改 crawler 配置、注入恶意 base-url 导致 SSRF（crawler 访问攻击者控制的 URL）、改 `crawler.callback.api-key` 劫持回调。
- **根因/分析**：鉴权纯靠 URL 前缀是已知薄弱点（§9）。本模块是重灾区之一（配置写入直接影响 crawler 行为）。已排除误判：无角色表/权限注解的 grep 结果显示全项目无 `@SaCheckRole`。
- **修复方向**：归 B06 主模块统一处理（加 `@SaCheckRole("admin")` 或拦截器增强）。本模块视角：所有 `/api/admin/config/**` 写操作应强制 admin 角色（**中**，跨 B06）。
- **关联**：B06（鉴权主模块）、§9 鉴权纯靠 URL 前缀。

### [P2] [Security] 敏感配置 admin 端"解密后脱敏回显"仍可能泄露：`toAdminDTO` 解密后只遮罩为 `********`，但 `getByKeyForAdmin` 对非 sensitive 但 isEncrypted 的配置返回解密后原值  <!-- 编号：B07-07 -->
- **定位**：`backend/src/main/java/com/nanmuli/blog/application/config/ConfigAppService.java:147-162`（`toAdminDTO`）、`164-169`（`toDTO`）
- **现象**：`toAdminDTO` 仅在 `isSensitive=true` 时遮罩并解密。若一个配置 `isEncrypted=true` 但 `isSensitive=false`（理论上可能，由 `set()` 或迁移脚本产生），admin 端 `GET /api/admin/config/{key}` 会通过 `toAdminDTO` 的 `isEncrypted` 分支 `setIsEncrypted(true)` 但**不遮罩**——此时返回的是**原始密文**（因 `BeanUtils.copyProperties` 复制的是 DB 中的 `{AES}...` 值，`toAdminDTO` 未对非 sensitive 调用 decrypt）。语义混乱但非明文泄露。
- **影响**：实际泄露风险低（返回密文非明文）。但行为不一致：`isEncrypted && !isSensitive` 返回密文、`isEncrypted && isSensitive` 返回 `********`、`!isEncrypted` 返回明文。admin 看到密文会困惑。
- **根因/分析**：`toAdminDTO` 逻辑分支耦合。已排除误判：现有 `SystemConfigInitializer` 种子的敏感配置都是 `isEncrypted=isSensitive=true`，此组合目前不出现，但 `set()` 路径可制造。
- **修复方向**：①统一 admin 端回显策略：加密配置一律遮罩或提供"查看明文"二次确认接口（**中**）；②补测试覆盖 `isEncrypted && !isSensitive` 组合（**小**）。
- **关联**：B07-05、B07-03。

### [P3] [Security] `SaTokenConfig.hasValidCallbackKey` 用 `String.equals` 而非恒定时间比较  <!-- 编号：B07-08 -->
- **定位**：`backend/src/main/java/com/nanmuli/blog/infrastructure/config/security/SaTokenConfig.java:55`（`expectedKey.equals(requestKey)`）
- **现象**：callback key 比较用普通 `String.equals`，理论上有时序侧信道。
- **影响**：内网调用场景下时序攻击门槛极高，实际风险低。但与 `InternalCallbackController` 同样问题，应统一。
- **根因/分析**：实现未用 `MessageDigest.isEqual`。
- **修复方向**：归 B09 主模块（双向 key）。本模块引用：`SaTokenConfig` 属 B16 全局基础设施范畴，但物理位于 config/security 包，本模块顺带记录。改 `MessageDigest.isEqual(expected.getBytes(UTF_8), request.getBytes(UTF_8))`（**小**）。
- **关联**：B09（内部回调主模块）、B16（全局基础设施）。

---

## `[Arch]` 架构与技术债

> 排查范围：encryption-key 取值路径与文档脱节、ConfigService vs @Value 双轨、refreshCache 空方法。

### [P2] [Arch] `blog.security.encryption-key` 取值路径与文档严重脱节：三处注释声称"在 sys_config"，实际 `AesEncryptor` 用 `@Value` 从 Spring 属性读，sys_config 中此 key 已被 V1_21 删除  <!-- 编号：B07-09 -->
- **定位**：`application-dev.yml:52-56`（注释"blog.security.* → sys_config (encryption-key)"）；`db/migration/V1_21__remove_unnecessary_configs.sql:188-192`（删除 DB 中此 key 并注释"通过 @Value 从 application.yml 读取，DB 中的值完全无效"）；`AesEncryptor.java:21`（实际 `@Value` 读取）；`application-prod.yml:71`（`encryption-key: ${BLOG_SECURITY_ENCRYPTION_KEY}`）
- **现象**：三处来源口径不一：①dev yml 注释说在 sys_config ②V1_21 注释说 @Value 从 yml 读 ③实际 @Value 从 Spring 属性（yml + env）读 ④`deploy/db/init-scripts/schema.sql:1073` 与 `init.sql:1119` 仍 seed 此 key（空值）。`SystemConfigInitializer` 也不补种此 key（正确，但它补种其他 crawler.* key，加深"配置都在 sys_config"的错觉）。
- **影响**：维护者改 sys_config 中的 encryption-key 不生效（V1_21 已删但 init.sql/schema.sql 双轨残留）；改 application.yml 中的 `blog.security.encryption-key`（dev）生效但与"迁移 sys_config"文档矛盾。认知负担高，易误改。
- **根因/分析**：Phase 2 迁移未完成对 encryption-key 的处理，V1_21 半修正（删 DB）但 init.sql/schema.sql 未同步，dev yml 注释未更新。
- **修复方向**：①统一文档：明确 encryption-key 是**唯一不从 sys_config 读**的特例，因其用于加密 sys_config 本身（**小**）；②init.sql/schema.sql 删除已失效的 seed（**小**，归 B15-03）；③dev yml 注释更正（**小**）。
- **关联**：B15-03（schema 三轨）、X06（配置一致性）、B07-01。

### [P3] [Arch] 配置读取双轨：`ConfigService`（内存 Map，reload 触发）与 `@Value`/`@ConfigurationProperties`（启动注入，不热更新）并存  <!-- 编号：B07-10 -->
- **定位**：`ConfigService.java:24-73`（内存 Map 模式）；`AesEncryptor.java:21`（@Value）；`CrawlerTaskClient.java:39-43`（构造时从 ConfigService 读一次，靠 reloadPool 重读）
- **现象**：crawler 配置走 ConfigService（可热更新），但 encryption-key 走 @Value（不可热更新，需重启）。两套机制并存。
- **影响**：admin 改 crawler.* 配置可热生效，改 encryption-key 必须重启（且重启后旧密文用旧 key 解不开——实际无法热轮换密钥）。这是加密密钥的天然限制，但文档未说明。
- **根因/分析**：encryption-key 不能热更新是合理的（否则需全量重加密），但应显式声明。
- **修复方向**：无需调整架构，仅需文档明确两类配置的更新语义（**小**）。
- **关联**：B07-09。

### [P4] [Arch] `ConfigAppService.refreshCache()` 是空方法体靠 `@CacheEvict` 注解生效，反直觉  <!-- 编号：B07-11 -->
- **定位**：`backend/src/main/java/com/nanmuli/blog/application/config/ConfigAppService.java:133-135`
- **现象**：`refreshCache()` 方法体为空，仅靠类上 `@CacheEvict(value = {"config", "config:admin:list"}, allEntries = true)` 注解清缓存。
- **影响**：功能正确（Spring AOP 拦截注解），但读代码者会误以为是空实现。类内方法注解比类注解清晰。
- **根因/分析**：注解写在方法上（`:133`），实际生效，但空方法体易误解。
- **修复方向**：加注释说明"靠 @CacheEvict 生效"，或方法体加 `// no-op, eviction via @CacheEvict`（**小**）。
- **关联**：无。

---

## `[Deps]` 依赖升级与版本

### 本模块依赖清单（基于声明文件，未翻依赖源码）

| 依赖 | 版本 | 声明位置 | 已知风险/可升级 | 备注 |
|---|---|---|---|---|
| JDK javax.crypto（内置） | Java 21 | `pom.xml` | 无 | AES/ECB 由 JDK provider 提供，无需外部依赖 |
| Spring Boot starter | 3.3.5 | `pom.xml` | 可升至 3.4.x | @Cacheable/@CacheEvict 注解稳定 |
| MyBatis Plus | 3.5.9 | `pom.xml` | 可升至 3.5.16+ | LambdaQueryWrapper 用法稳定 |

> 排查范围：B07 仅用 JDK 内置加密 + Spring Cache，无第三方加密库（如 Bouncy Castle/Jasypt）。未发现依赖级风险。

---

## `[Design]` 功能设计合理性

> 必填。从真实使用出发审视。

**审视结论**：

1. **场景适配**（单人博客 + 每工作日 AI 日报）：DB 化配置 + AES 加密 + crawler 热重载对单人博客是**适度偏重**的设计，但既然 crawler 是独立服务且需要 admin 在线调参（AI model、callback url），这套机制是合理的。真正的问题不是过度设计，而是**实现质量**（ECB、弱默认密钥、吞异常）。

2. **闭环完整性**：admin 改 crawler 配置的闭环是"改 Java 缓存 → 通知 Python → 重建连接池"，但 `refreshConfig` 吞异常导致 Python 侧失败时闭环断裂（B07-04）。无配置变更历史/审计日志，改错了无法回溯（只有 `default_value` 可 reset，但不知道改过什么）。

3. **可运维性**：`refreshAll` 接口返回各组件刷新结果列表，但 `refreshConfig` 吞异常导致列表里的 "Python Crawler" 永远是乐观成功。无配置变更告警、无密钥轮换工具、无加密失败告警。

### [P2] [Design] 配置变更无审计日志与历史记录，改错无法回溯  <!-- 编号：B07-12 -->
- **定位**：`ConfigAppService.update():70-81`、`set():99-131`、`resetToDefault():85-95` —— 均无审计记录，`sys_config` 表也无历史表
- **现象**：配置被改后只有 `updated_at` 时间戳变化，无"旧值→新值"、"谁改的"记录。`Config` 实体无审计字段。
- **影响**：单人维护时改错 crawler 配置导致采集失效，无法知道改前是什么值（除非记得 default）。多人或 token 泄露时无法追责。
- **建议方向**：增加 `sys_config_history` 表或审计日志（记录 key/old_value/new_value/operator/time），（**中**）。
- **关联**：B07-04（闭环）、B06（鉴权，配合审计）。

### [P4] [Design] 无加密密钥轮换机制，密钥泄露需手动重加密全表  <!-- 编号：B07-13 -->
- **定位**：`AesEncryptor.java` 无 reEncrypt 能力；`ConfigService.reload()` 无密钥变更感知
- **现象**：encryption-key 变更需重启，且重启后旧 `{AES}` 密文用新 key 解不开，无工具重加密。
- **影响**：密钥泄露后无法快速轮换，需写脚本读出所有加密配置、解密、用新 key 重加密。
- **建议方向**：提供 admin 级"重加密"工具接口（带旧 key→新 key），（**中**）。
- **关联**：B07-01、B07-02。

---

## 模块小结

### 严重度统计

| 级别 | 数量 | 条目编号 |
|---|---|---|
| P0 | 0 | — |
| P1 | 2 | B07-01、B07-06 |
| P2 | 6 | B07-02、B07-03、B07-04、B07-07、B07-09、B07-12 |
| P3 | 3 | B07-05、B07-08、B07-10 |
| P4 | 2 | B07-11、B07-13 |

### Top 风险（本模块最该先看的 ≤3 条）

1. **B07-01 弱默认密钥 `local-dev-encryption-key` 静默通过校验** —— dev/漏配场景下用源码公开弱密钥加密所有 API key，等于无加密。
2. **B07-06 admin 配置接口仅 checkLogin 不校验角色** —— token 泄露给普通用户即可篡改 crawler 配置触发 SSRF。
3. **B07-04 crawler 重载吞异常** —— Python 侧刷新失败时 admin 看到"成功"，crawler 静默失效。

### 修复优先级建议

- **立即**（P1）：
  - B07-01：移除 `@Value` 默认值或把 `local-dev-encryption-key` 加入黑名单（改动面：小）
  - B07-06：归 B06 统一加 admin 角色校验（改动面：中，跨模块）
- **计划**（P2）：
  - B07-02：AES 升级 GCM/CBC + IV（改动面：中，需数据迁移）
  - B07-03：encrypt 失败 fail-fast 不回退明文（改动面：小）
  - B07-04：refreshConfig 失败反馈给 admin（改动面：中）
  - B07-09：统一 encryption-key 文档与 schema seed（改动面：小，跨 B15/X06）
  - B07-12：配置变更审计（改动面：中）
- **择机**（P3/P4）：
  - B07-05、B07-07、B07-08、B07-10、B07-11、B07-13

### 排查盲区 / 待复核

- **B07-04**：Python 侧 `/api/v1/config/refresh` 失败后是否有 fallback 自取 sys_config 的机制？若有，则吞异常影响降低。[需查证]，归 C11 主模块。
- **B07-06**：项目当前是否真有"非 admin 角色"的登录用户？若单人博客只有 admin，实际越权风险降级。用户角色模型 [需查证]，归 B06。
- **AesEncryptor 在 dev profile 的实际取值**：未实际启动验证（命令边界禁止），基于 `application.yml:5` 默认 `profiles.active: dev` + dev yml 无 `blog.security.encryption-key` 属性 + `@Value` 默认值推断，结论可靠但未运行时确认。
