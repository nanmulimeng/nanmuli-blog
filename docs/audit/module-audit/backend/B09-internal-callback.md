# B09 内部回调与跨服务同步 排查报告

> **模块编号**：B09
> **排查范围**：Python crawler → Java 的内部回调端点（任务状态/订阅源运行状态/日报指纹/来源权威性同步）+ 双向 key 鉴权 + callback 字段契约
> **基线 commit**：`6ae930098405f4d0553d96a852f3345d0f39682e`
> **工作区状态**：脏。涉及本模块的未提交改动：`backend/src/main/java/com/nanmuli/blog/infrastructure/persistence/webcollector/WebCollectPageMapper.java`（已改），新增 `backend/src/test/java/com/nanmuli/blog/infrastructure/persistence/webcollector/`（未跟踪）。其余脏文件（`ConfigRepositoryImpl.java`、crawler `search.py`/`knowledge_base.py`、release 脚本等）不直接触及本模块主链路。排查基于当前工作区代码。
> **排查日期**：2026-06-23
> **排查人**：B09 模块排查 agent
> **状态**：草稿

---

## 模块概览

**职责**：Java 后端暴露 `/api/internal/collector/**` 端点，供 Python crawler 单向回调（任务完成通知、订阅源运行状态、日报去重指纹批量回写、来源权威性只读查询、crawler 配置引导拉取）；并用 `X-Callback-Key` 做双向 key 鉴权，配套 nginx/localhost 网络层兜底。

**关键文件**：
- `backend/src/main/java/com/nanmuli/blog/interfaces/rest/InternalCallbackController.java:33` —— 回调入口 Controller，注入 8 个 bean，6 个端点，手动 key 校验
- `backend/src/main/java/com/nanmuli/blog/infrastructure/config/security/SaTokenConfig.java:36-49` —— `/api/internal/**` 网络层兜底拦截器（localhost 或回调 key 二选一）
- `backend/src/main/java/com/nanmuli/blog/infrastructure/persistence/webcollector/DigestFingerprintMapper.java:23` —— 批量指纹写入（含 B09-01 致命缺陷）
- `backend/src/main/java/com/nanmuli/blog/infrastructure/persistence/webcollector/DigestFingerprintRepositoryImpl.java:29` —— 批量写入分片（100/批）
- `backend/src/main/java/com/nanmuli/blog/infrastructure/persistence/webcollector/SourceAuthorityMapper.java` —— 来源权威性只读 Mapper
- `backend/src/main/java/com/nanmuli/blog/domain/webcollector/DigestFingerprint.java` —— 指纹实体（simhash 为 Long）
- `backend/src/main/java/com/nanmuli/blog/application/webcollector/WebCollectorAppService.java:401` —— `handleCallback` 任务状态同步（回查 + fallback）
- `backend/src/main/java/com/nanmuli/blog/application/webcollector/WebCollectSourceAppService.java:147` —— `updateSourceRunStatus` 订阅源计数（无幂等）
- crawler 发送方：`crawler-service/standalone/task_executor.py:26`（`_fire_callback`）、`crawler-service/crawler/digest.py:68/118`（指纹保存）、`crawler-service/standalone/scheduler.py:302`（订阅源状态）、`crawler-service/crawler/quality.py:158`（权威性预热）

**对外接口 / 依赖**：
- 对外：6 个 internal 端点——`POST /callback`、`GET /sources`、`GET /config`、`POST /sources/{sourceId}/run-status`、`GET/POST /digest/fingerprints`、`GET /source-authority[/all]`
- 依赖：`configService`（`crawler.callback.api-key`、`crawler.service.api-key`）、`AesEncryptor`（解密配置）、`configRepository`、`WebCollectorAppService`、`WebCollectSourceAppService`、`Environment`（profile 判定）、PG 表 `digest_fingerprint`、`source_authority`、`web_collect_source`、`web_collect_task`

**已读文件清单**：
- `InternalCallbackController.java` —— 通读
- `SaTokenConfig.java` —— 通读
- `DigestFingerprintMapper.java` / `DigestFingerprintRepositoryImpl.java` / `SourceAuthorityMapper.java` —— 通读
- `DigestFingerprint.java` / `SourceAuthority.java` / `BaseAggregateRoot.java` —— 通读
- `WebCollectorAppService.java`（handleCallback 片段 390-490）—— 片段
- `WebCollectSourceAppService.java`（updateSourceRunStatus 片段 140-190）—— 片段
- crawler 侧 `task_executor.py`（1-120）/ `digest.py`（60-180）/ `scheduler.py`（295-330）/ `quality.py`（grep）/ `dedup.py`（166-220）—— 片段
- `InternalCallbackControllerTest.java` —— 通读
- `db/migration/V1_17` / `V1_18`、`deploy/db/init-scripts/schema.sql`、`deploy/docker-compose.yml`、`deploy/nginx/conf.d/default.conf`、`interfaces/filter/*` —— grep / 片段

**主模块归属**：本模块是**内部回调端点 + 双向 key 鉴权的主模块**（§8.6），深查。schema 定义（digest_fingerprint/source_authority 表）→ 引用 B15；SQLite vs PG 跨库一致性 → 引用 X02；`CrawlerTaskClient`（Java→Python 方向）→ 引用 B10；Sa-Token 拦截器全局配置 → 引用 B06。

---

## `[Bug]` 代码正确性与潜在缺陷

> 排查范围：`InternalCallbackController` 全部 6 端点、`DigestFingerprintRepositoryImpl`/Mapper、`WebCollectorAppService.handleCallback`、`WebCollectSourceAppService.updateSourceRunStatus`、crawler 发送方字段契约对照。

### [P0] [Bug] 批量指纹写入遗漏 id 列，必触非空约束失败 <!-- 编号：B09-01 -->
- **定位**：`backend/src/main/java/com/nanmuli/blog/infrastructure/persistence/webcollector/DigestFingerprintMapper.java:23-30`；表定义 `backend/src/main/resources/db/migration/V1_17__create_digest_fingerprint.sql:3`（`id BIGINT PRIMARY KEY` 无默认值）
- **现象**：`batchInsertIgnoreOnConflict` 的 `@Insert` SQL 列清单为 `(task_id, url_hash, url, title, simhash, digest_date, is_deleted)`，**不含 `id`**；`DigestFingerprintRepositoryImpl.saveAll`（:29-38）只构造实体后直接调该 batch insert，未对实体 `id` 赋值。`DigestFingerprint` 继承的 `BaseAggregateRoot` 用 `@TableId(type = IdType.ASSIGN_ID)`（snowflake 自动赋值），但**该注解只在 MyBatis-Plus 的 `BaseMapper.insert`/`updateById` 走拦截器时生效，对手写的 `@Insert` SQL 无效**。结果：PG 收到 `INSERT INTO digest_fingerprint(...) VALUES(NULL, ...)` → `null value in column "id" violates not-null constraint`。
- **影响**：crawler 日报生成完成后调用 `POST /api/internal/collector/digest/fingerprints` 回写指纹，每次 `saveAll` 的每个分片（100 条/批）都会抛出异常 → controller 无 try/catch 兜底（:235 直接调 `fingerprintRepository.saveAll`）→ 全量 500 → 指纹持久化**完全失效**。设计意图的"跨日去重"在 PG 侧形同虚设（crawler 侧本地 SQLite 兜底，但跨日重启后丢失，见 B09-05 影响）。
- **根因/分析**：手写 SQL 绕过 MyBatis-Plus 的 id 填充机制。已排除：①不是 ON CONFLICT 问题（url_hash+digest_date 是唯一索引，首次冲突也会因 id NULL 失败）；②不是事务问题（无 `@Transactional` 包裹，每批独立失败）。`DigestFingerprintRepositoryImpl.save`（:17-23）走的是 `fingerprintMapper.insert(fp)`，这条路径**会**触发 ASSIGN_ID，所以单条写入正常；只有批量路径坏。
- **修复方向**：①在 batch SQL 列清单加 `id` 并在 VALUES 里用 `#{fp.id}`，同时在 controller 构造实体前用 `IdWorker.getId()` 显式赋 snowflake id（改动面 中）；或 ②放弃手写 batch SQL，改用 MyBatis-Plus 原生 `saveBatch`（需校验 ON CONFLICT DO NOTHING 语义，可能需自定义 `IService`，改动面 中）；或 ③将 PG 主键改为 `BIGSERIAL`/`GENERATED ALWAYS AS IDENTITY`（涉及 schema 变更，归 B15，改动面 大，且不解决 ASSIGN_ID 与 DB 自增并存冲突）。
- **关联**：[[B15 schema 主键策略]] / 横向主题"跨服务契约" / 配置项 无

### [P1] [Bug] simhash 无符号 64 位写入 signed BIGINT，超 2^63-1 时溢出截断 <!-- 编号：B09-02 -->
- **定位**：crawler 生成方 `crawler-service/crawler/dedup.py:214-218`（`result |= (1 << i)`，64 位全空间）；Java 接收方 `InternalCallbackController.java:227`（`m.get("simhash") instanceof Number n ? n.longValue() : null`）；表列 `V1_17__create_digest_fingerprint.sql:8`（`simhash BIGINT`，signed）
- **现象**：Python `simhash` 是 0 ~ 2^64-1 的无符号整数；Java `Long.longValue()` 对 >2^63-1 的值会**回绕成负数**（如 2^63 → -9223372036854775808）；PG `BIGINT` 同样是 signed，写入会得到负值。
- **影响**：约一半指纹的 simhash 在 Java 侧被解释为负数，**与 crawler 本地 SQLite 侧的解释不一致**。后果：跨日去重时 Java 回传给 crawler 的指纹（`GET /digest/fingerprints`）simhash 值符号翻转，Hamming 距离计算错误 → 跨日相似内容重复进日报，去重失效（这正是 B09 模块的核心价值点）。crawler 本地内存去重正常（同进程同解释），只有跨日跨库链路被破坏。
- **根因/分析**：跨语言无符号整数契约缺失。已排除：不是 JSON 序列化精度问题（httpx/JSON 对 <2^53 之外的整数仍以 number 传输，Jackson `ObjectMapper` 反序列化为 `Object`→`Number`，再 `longValue()` 时已是 signed 解释）。Python 的 `add_precomputed_simhash(url, ..., simhash=int)`（`dedup.py:286-293`）原样接收 Java 回传的负值，内部按 Python 任意精度计算，符号位差异会改变 Hamming 距离。
- **修复方向**：①在 Java `saveDigestFingerprints` 写入前与 crawler 约定 simhash 按 `& ((1<<64)-1)` 无符号解释，统一为字符串/BigDecimal 传输（改动面 中）；或 ②将 PG 列改 `NUMERIC(20,0)`（schema 变更，归 B15，改动面 大）；或 ③最简：crawler 侧发送前 `simhash = simhash & 0xFFFFFFFFFFFFFFFF`，Java 侧存储也按无符号回绕后再算距离（需两侧对称，改动面 中）。[需查证] crawler 侧 Hamming 距离是否对负 simhash 容错（`dedup.py` 的 `hamming_distance` 实现未读全）。
- **关联**：横向主题"跨服务契约" / [[X02 跨库一致性]] / 次维度 [Security]（语义而非安全）

### [P2] [Bug] `updateSourceRunStatus` 无幂等，重复回调致计数虚高 <!-- 编号：B09-03 -->
- **定位**：`backend/src/main/java/com/nanmuli/blog/application/webcollector/WebCollectSourceAppService.java:147-189`；crawler 发送方 `standalone/scheduler.py:302`（fire-and-forget）
- **现象**：每次回调无条件 `runCount + 1`（:156）、`successCount/failCount + 1`（:159/:169）、用 `0.7*prev + 0.3*score` 滑动平均刷新 `avgQualityScore`（:165）。没有运行批次 id、没有 `lastRunAt` 幂等窗口、没有去重键。
- **影响**：crawler 侧 HTTP 超时重试（`callback_timeout` 内 httpx 自身重试，或 scheduler 任务级重试）或重复触达（一次源被多个调度实例回调）会导致同一源运行被计多次，`successCount`/`avgQualityScore` 偏离真实；管理端看板数据失真，长期累积影响优化系统的疲劳判断（C06 引用此值）。
- **根因/分析**：fire-and-forget 模式下 callback 至少一次（at-least-once）语义，但接收侧按精确一次（exactly-once）累加。已排除：乐观锁重试（:179）只防并发覆盖丢失，不防重复回调。
- **修复方向**：①接收侧引入 `lastRunAt` 时间窗幂等（如 30s 内同 sourceId+status 视作重复，仅刷新不计数，改动面 小-中）；或 ②callback payload 加 `run_batch_id`，Java 侧用唯一索引去重（需 schema 改动，归 B15，改动面 大）。
- **关联**：[[C06 优化系统读 source 计数]] / 配置项 无

### [P3] [Bug] handleCallback 的 payloadStatus 缺省 -1 与 crawler 始终发 status 不对称 <!-- 编号：B09-04 -->
- **定位**：`InternalCallbackController.java:113-118`（status 缺失时 `payloadStatus = -1`）；crawler 发送方 `task_executor.py:38`（`payload = {"python_task_id": task_id, "status": status}` 始终带 status）
- **现象**：controller 允许 status 缺失并继续 `handleCallback(pythonTaskId, -1)`；`WebCollectorAppService.handleCallback`（:416-422）仅在 `payloadStatus >= 0` 时用作 fallback。
- **影响**：当前 crawler 始终发 status，无害；但若未来发送方字段名变更（如改成 `task_status`）或省略，会静默走 `syncFromPythonSilent` 失败路径且 fallback 不触发，任务卡在非终态。
- **根因/分析**：契约松散。已排除：不是 bug，是健壮性缺口。
- **修复方向**：要么 status 缺失时直接 400（与 `python_task_id` 缺失的 :108-110 一致），要么显式记录 -1 语义（改动面 小）。
- **关联**：横向主题"跨服务契约"

### [P4] [Bug] 单条 save 与批量 save 路径分裂，两条 id 处理逻辑不一致 <!-- 编号：B09-05 -->
- **定位**：`DigestFingerprintRepositoryImpl.java:17-23`（单条 `save` 用 `isNew` 分支，走 `BaseMapper.insert` 触发 ASSIGN_ID）vs `:29-38`（批量走手写 `@Insert` 不触发，见 B09-01）
- **现象**：同一仓储两条写入路径，id 处理一个生效一个失效。
- **影响**：单条路径目前无人调用（controller 只用 `saveAll`），但代码分裂易致后续维护误改；且批量失败的根因与单条路径差异隐蔽，难以排查。
- **根因/分析**：历史遗留，原 `insertIgnoreOnConflict` 单条版本（:14-17）与批量版本字段清单同步漂移，都漏了 id。
- **修复方向**：合并为统一路径，或删除未用的单条 `insertIgnoreOnConflict`（改动面 小，需 grep 确认无引用）。
- **关联**：[[B09-01]]

---

## `[Security]` 安全漏洞

> 排查范围：双向 key 鉴权强度/比较方式/默认值/泄漏；internal 端点网络层暴露；SSRF/来源校验。逐项覆盖 §2.2 技术栈重点之"跨服务双向 key"。

### [P1] [Security] internal 端点经 nginx `/api/` 反代 + backend 8081 端口公网发布，localhost 兜底形同虚设 <!-- 编号：B09-06 -->
- **定位**：`deploy/nginx/conf.d/default.conf:37-45`（`location /api/ { proxy_pass http://backend:8081; }`）；`deploy/docker-compose.yml:77-78`（`backend` 发布 `ports: - "8081:8081"`）；兜底拦截器 `SaTokenConfig.java:39-49`（`request.getRemoteAddr()` 不在 `LOCALHOST_ADDRESSES` 才校验 key）
- **现象**：①nginx 把 `/api/internal/**` 一视同仁反代到 backend，**没有 location 级白名单阻断**；②backend 容器 8081 端口直接 `ports` 发布到宿主机，外部可绕过 nginx 直连 `host:8081/api/internal/**`；③Spring 的 `request.getRemoteAddr()` 返回的是 TCP 直连对端 IP——经 nginx 反代时是 nginx 容器 IP（如 `172.x.x.x`），直连 8081 时是外部攻击者 IP，**两种情况都不在 `{127.0.0.1, ::1}`** → 拦截器永远走 key 校验分支。也就是说 localhost 兜底**在生产拓扑下几乎从不生效**，安全完全压在单一 `X-Callback-Key` 上。
- **影响**：一旦 `crawler.callback.api-key` 泄漏或为弱值/默认值，internal 端点（含 `/config` 明文返回所有 crawler 配置含解密后的 api-key、`/source-authority/all` 全量来源、`/callback` 可伪造任务状态）即被外部完全接管。且因 backend 端口发布，nginx 层的任何加固都失效。
- **根因/分析**：①localhost 校验对反代场景语义错误，应判 `X-Forwarded-For` 首跳或独立 internal network；②端口不应发布。已排除：不是 nginx 配置漏写 internal location（nginx 层即使加了，8081 直连仍绕过）。
- **修复方向**：①backend 容器去掉 `ports: 8081`，仅暴露给同网络的 nginx/crawler（compose `expose` 替代 `ports`，改动面 中）；②nginx 层加 `location /api/internal/ { deny all; }` 或限定 `allow crawler_network;`（改动面 中）；③拦截器改判 `X-Forwarded-For` 首跳 IP + 配置内网 CIDR 白名单，而非裸 `getRemoteAddr`（改动面 中，需与 ①配合）。三项组合。
- **关联**：[[B06 SaToken 拦截器配置主模块]] / [[X01 部署网络]] / 横向主题"鉴权机制一致性"

### [P2] [Security] 回调 key 校验用 `String.equals`，非常数时间比较 <!-- 编号：B09-07 -->
- **定位**：`InternalCallbackController.java:67`（`return !expectedKey.equals(callbackKey);`）、`:77`、`:82`；`SaTokenConfig.java:55`（`expectedKey.equals(requestKey)`）
- **现象**：双向 key 校验三处均用 `String.equals`，非常数时间（提前短路）。
- **影响**：理论上的定时攻击（timing attack）面，可逐字节推断 key。在 internal 端点 + 单人维护 + 网络层应已隔离的场景下，实际可利用性低；但与 AES、Sa-Token 自身的密钥处理风格不一致，属安全卫生项。
- **根因/分析**：未用 `MessageDigest.isEqual` 或等价常数时间比较。已排除：这不是高危——key 长度通常 ≥32 字符，定时差异在 JVM JIT/网络抖动量级之下，难以稳定测量。
- **修复方向**：统一改 `MessageDigest.isEqual(expectedKey.getBytes(UTF_8), callbackKey.getBytes(UTF_8))`，并把三处校验抽到 `AesEncryptor`/`KeyValidator` 工具类（改动面 小）。
- **关联**：横向主题"鉴权机制一致性" / [[B07 AES 主模块]]

### [P2] [Security] `/config` 端点明文回吐所有 crawler 配置（含解密后的 service api-key） <!-- 编号：B09-08 -->
- **定位**：`InternalCallbackController.java:140-160`（`getCrawlerConfig`，对 `isEncrypted=true` 的项调 `aesEncryptor.decrypt(val)` 后明文返回）；`configAuthRequired`（:75-95）允许 `crawler.service.api-key` 或 `crawler.callback.api-key` 任一命中
- **现象**：该端点把 `crawler` 配置组**全量解密**后以明文 Map 返回，含 `crawler.service.api-key`（Java→Python 方向的 key）。鉴权放宽为"任一 key 命中"（其他端点只认 callback key）。
- **影响**：持有 callback key 的调用方（按设计只有 crawler）即可读走 service api-key，导致双向 key 事实上退化为单向；结合 B09-06（端点公网可达），一旦 callback key 泄漏，service key 也即泄漏。crawler 客户端本不需要 service api-key（它持有的是被 Java 校验的 key，不是它去校验 Java 的），回吐该字段属过度披露。
- **根因/分析**：bootstrap 便利性压倒最小披露原则。已排除：不是解密本身错（crawler 需要配置值），是回吐范围未做白名单。
- **修复方向**：①`getCrawlerConfig` 返回前过滤掉 `*.api-key`、`*.api_key` 等 key 字段（改动面 小）；或 ②对敏感 key 返回占位符 `<encrypted>`，crawler 侧只读非敏感项（改动面 中，需 crawler 配合）。
- **关联**：[[B07 AES 加密主模块]] / 横向主题"鉴权机制一致性"

### [P3] [Security] 回调 key 为空时生产 profile 下"全阻断"，但日志告警仅一次且用 volatile 标志 <!-- 编号：B09-09 -->
- **定位**：`InternalCallbackController.java:44`（`private volatile boolean apiKeyBlankWarned`）、`:60-64`
- **现象**：key 为空且非 bootstrap profile 时所有 internal 端点返回 403，首次 `log.error` 后 `apiKeyBlankWarned=true` 不再告警。
- **影响**：故障可观测性弱——运维若未及时抓首条日志，后续所有回调静默 403，crawler 重试 3 次后放弃，任务状态不同步、指纹不落库，但 backend 日志看似平静。`volatile` 只保证可见性不保证原子，多线程首次告警可能重复一次（无害）。
- **根因/分析**：告警抑制过度。已排除：阻断行为本身是安全的（fail-closed）。
- **修复方向**：改为按 N 分钟窗口周期性告警，或接入健康检查/指标暴露"key 为空"状态（改动面 小-中）。
- **关联**：配置项 `crawler.callback.api-key` / [[X06 配置一致性]]

### [P3] [Security] callback 与 `/config` 无来源标识校验（无 crawler 身份/无 IP 白名单） <!-- 编号：B09-10 -->
- **定位**：`InternalCallbackController.java` 全部端点仅校验 `X-Callback-Key`；crawler 发送方 `task_executor.py:42-43`、`digest.py:105-106`、`scheduler.py:313-314` 只发 `X-Callback-Key`，不发 `X-Client-Id`（contrast：Java→Python 方向的 `CrawlerTaskClient` 有 `X-Client-Id`，见 B10）
- **现象**：Python→Java 方向没有 `X-Client-Id` 类的调用方标识，任何持有 callback key 的来源都被视作合法 crawler。
- **影响**：若未来有第二个内部服务接入（CLAUDE.md 提到"允许最多两个内部服务调用"），无法区分来源；审计/限流/故障隔离缺少身份维度。当前单人单服务场景影响低。
- **根因/分析**：双向契约不对称。已排除：不是 bug，是契约设计缺口。
- **修复方向**：引入 `X-Client-Id` 或 mTLS/服务账号，backend 侧按 client 限流与审计（改动面 中，跨服务）。
- **关联**：[[B10 CrawlerTaskClient]] / 横向主题"跨服务契约"

---

## `[Arch]` 架构与技术债

> 排查范围：InternalCallbackController 职责/分层、注入 bean 数量、DTO/Map 传递、领域层 MyBatis 注解泄漏。

### [P2] [Arch] InternalCallbackController 注入 8 bean、手写鉴权+DTO 构造+MyBatis Wrapper，是 mini facade 非 Controller <!-- 编号：B09-11 -->
- **定位**：`InternalCallbackController.java:35-42`（注入 `WebCollectorAppService`、`WebCollectSourceAppService`、`ConfigRepository`、`AesEncryptor`、`ConfigService`、`DigestFingerprintRepositoryImpl`、`SourceAuthorityMapper`、`Environment`）
- **现象**：Controller 同时承担：①手写 key 鉴权（`authRequired`/`configAuthRequired` 50-95）；②`/config` 端点直接调 `configRepository.findByGroup` + `aesEncryptor.decrypt` 做 service 层应做的聚合（:148-156）；③`/digest/fingerprints` POST 端点用裸 `Map<String,Object>` 手搓 `DigestFingerprint` 实体（:218-233）；④`/source-authority` 端点直接 new `LambdaQueryWrapper` 调 `SourceAuthorityMapper`（:252-280）——**Controller 直接调 Mapper，跳过 RepositoryImpl 和领域层**，且 `SourceAuthorityMapper` 是 infrastructure 层对象被 interfaces 层直接注入，分层穿透。
- **影响**：①DDD 分层违反（interfaces → infrastructure 直接依赖，绕过 application/domain）；②鉴权逻辑散落在 Controller（:50-95）而非 Filter/Interceptor，与 `SaTokenConfig` 的拦截器形成**两套并行鉴权**（拦截器校验一次、Controller 再校验一次），易漂移；③8 bean 注入远超 Controller 应有职责，单测需 mock 全部（`InternalCallbackControllerTest` 已验证，:30-45）；④`DigestFingerprintRepositoryImpl` 与 `SourceAuthorityMapper` 的查询逻辑本应在各自 RepositoryImpl/领域服务。
- **根因/分析**：历史增量——每个回调端点就近在 Controller 写实现，未抽 `InternalCallbackAppService`。已排除：不是性能问题，是可维护性。
- **修复方向**：①抽 `InternalCallbackAppService` 承载 `/config` 聚合、指纹构造、权威性查询，Controller 只做参数绑定+鉴权委托（改动面 中）；②鉴权抽成独立 `CallbackKeyFilter` 或复用 `SaTokenConfig` 拦截器（与 B06-02 鉴权一致性协同，改动面 中）；③`source-authority` 查询下沉到 `SourceAuthorityRepositoryImpl`（需新建，改动面 中）。
- **关联**：[[B06 鉴权一致性]] / 次维度 [Bug]（分层穿透）

### [P3] [Arch] 回调 payload 用裸 `Map<String,Object>` 传递，无 DTO/契约文档 <!-- 编号：B09-12 -->
- **定位**：`InternalCallbackController.java:100`（`@RequestBody Map<String, Object> payload`）、`:169`、`:212`（`@RequestBody List<Map<String, Object>>`）；crawler 发送方 `task_executor.py:38`、`digest.py:90-97`
- **现象**：所有 internal 端点用 `Map<String,Object>` 接收，字段名靠字符串（`python_task_id`、`urlHash`、`qualityScore`），类型靠 `instanceof Number` 运行时判（:108/:114/:182/:183/:220/:227）。无 DTO 类、无 OpenAPI 文档、字段命名 snake_case 与 camelCase 混用（callback 用 snake_case `python_task_id`，指纹用 camelCase `urlHash/digestDate`）。
- **影响**：跨服务字段契约无静态保障，重命名字段（如 B09-04 的 status）编译期不报错；crawler/Java 两侧命名风格不一致（B09-12 暴露的是已存在的不一致），新增字段时易漏改对侧。
- **根因/分析**：internal 端点未纳入与公开 API 同等契约管理。已排除：不是 bug，是技术债。
- **修复方向**：①为每个回调定义 DTO（`CallbackPayload`、`DigestFingerprintPayload`），字段加 `@JsonProperty` 明确命名（改动面 中）；②用 OpenAPI/Springdoc 标注 internal tag（knife4j 已在依赖，改动面 小）。
- **关联**：横向主题"跨服务契约" / [[C01 crawler callback 字段契约]]

### [P3] [Arch] `SourceAuthorityMapper` 无 RepositoryImpl，Controller 直接穿透 <!-- 编号：B09-13 -->
- **定位**：`SourceAuthorityMapper.java`（仅 `extends BaseMapper`，无自定义方法）；`InternalCallbackController.java:252-280`（Controller 内 new `LambdaQueryWrapper`）
- **现象**：其余 webcollector 实体（WebCollectTask/Source/Page、DigestFingerprint）都有 RepositoryImpl，唯独 SourceAuthority 没有，查询逻辑落在 Controller。
- **影响**：分层不一致；若未来需要在别处复用"查活跃权威性"逻辑，无法复用，会复制粘贴。
- **根因/分析**：当前只有 internal 端点用，未抽。
- **修复方向**：新建 `SourceAuthorityRepositoryImpl` 提供 `findActiveByDomain`/`findAllActive`，Controller 改调（改动面 小）。
- **关联**：[[B09-11]] / [[B14 数据访问层]]

---

## `[Deps]` 依赖升级与版本

### 本模块依赖清单（基于声明文件，未翻依赖源码）

| 依赖 | 版本 | 声明位置 | 已知风险/可升级 | 备注 |
|---|---|---|---|---|
| MyBatis Plus | 3.5.9 | `backend/pom.xml` | 可升至 3.5.12+ | 本模块用 `BaseMapper.insert`/`@Insert`/`LambdaQueryWrapper`；`IdType.ASSIGN_ID` 在手写 SQL 下不生效是 B09-01 根因 |
| Spring Web | 6.1.x（随 Boot 3.3.5） | `backend/pom.xml` | Boot 3.3→3.4/4.x | `@RequestMapping`/`@RequestBody` 标准用法，无版本风险 |
| Sa-Token | 1.44.0 | `backend/pom.xml` | 可升至 1.46+ | 本模块仅借道 `SaInterceptor` 排除 `/api/internal/**`（SaTokenConfig:34），无直接调用 `StpUtil` |
| httpx（crawler 侧） | [需查证] | `crawler-service/requirements.txt` | — | crawler 发送方依赖，非本模块 Java 侧 |

> 排查范围：`backend/pom.xml` 中本模块用到的库（MyBatis Plus / Spring Web / Sa-Token）+ crawler 发送方 httpx。未深入依赖源码（§1.3.1）。**未发现**版本 CVE 或废弃 API 命中。

---

## `[Design]` 功能设计合理性

**审视结论**：

1. **闭环完整性**：跨日去重闭环**不完整**——指纹写入因 B09-01 恒失败、simhash 符号因 B09-02 失真，crawler 重启后从 Java 侧恢复的跨日历史要么为空、要么语义错乱，导致"跨日持久化去重"这个核心承诺在生产环境实际不成立。这是"看起来能用实则跑不通"的半成品（§2.5 第 4 问），且因 crawler 本地 SQLite 兜底，单日内不易察觉。
2. **可运维性**：回调失败处理在 crawler 侧有 3 次重试 + 4xx/5xx 区分（`task_executor.py:46-70`），但 backend 侧**无任何幂等/对账机制**（B09-03 计数虚高、B09-04 状态 fallback 粗糙），故障时无法快速定位是 backend 拒绝还是 crawler 未发；key 为空告警仅一次（B09-09），运维盲区大。
3. **场景适配**：单人维护 + 每工作日 AI 日报场景下，internal 端点的"localhost 兜底 + 单 key"设计在**理想内网拓扑**下够用且不过度；但 B09-06 揭示的实际部署（nginx 反代 + 8081 端口公网发布）使该设计前提落空，从"够用"退化为"单 key 一旦泄漏即全面失守"。这是设计与部署错配，不是过度设计。

### [P4] [Design] 回调链路缺少对账/补偿入口 <!-- 编号：B09-14 -->
- **定位**：整个 internal callback 链路
- **现象**：crawler fire-and-forget 发回调，backend 收到即改状态；无"任务长时间未回调"的对账任务、无"指纹写入失败"的重试队列、无管理端手动触发指纹回写的入口。
- **影响**：任一环节失败（网络、backend 重启、B09-01 必失败）数据静默丢失，需人工查日志才能发现。
- **建议方向**：补充 backend 侧定时对账（扫超时未回调的任务回查 crawler API，归 B17 调度），与 C04/C07 的补救任务协同（改动面 中）。
- **关联**：[[C04 日报编排]] / [[B17 调度]] / §2.5 第 3 问

---

## 模块小结

### 严重度统计

| 级别 | 数量 | 条目编号 |
|---|---|---|
| P0 | 1 | B09-01 |
| P1 | 3 | B09-02, B09-06, B09-08（B09-08 归为 P2 见上表，此处订正）|
| P2 | 4 | B09-03, B09-07, B09-08, B09-11 |
| P3 | 4 | B09-04, B09-09, B09-10, B09-12, B09-13 |
| P4 | 2 | B09-05, B09-14 |

> 订正：B09-08 定为 P2（敏感配置过度披露，但需先有 key 泄漏/端点可达才可利用）。正确统计：**P0=1，P1=2（B09-02, B09-06），P2=4（B09-03, B09-07, B09-08, B09-11），P3=5（B09-04, B09-09, B09-10, B09-12, B09-13），P4=2（B09-05, B09-14）**。

### Top 风险（本模块最该先看的 ≤3 条）

1. **B09-01 批量指纹写入必触非空约束失败** —— `/digest/fingerprints` 端点恒 500，跨日去重持久化链路在生产环境完全失效，是"看起来能用实则跑不通"的典型。
2. **B09-06 internal 端点经 nginx 反代 + 8081 端口公网发布，localhost 兜底失效** —— 安全完全压在单一 key 上，部署拓扑与设计前提错配，结合 B09-08 配置回吐可致双向 key 双双泄漏。
3. **B09-02 simhash 无符号 64 位写入 signed BIGINT 溢出** —— 约一半指纹语义错乱，跨日去重准确率受损（本地去重正常掩盖了问题）。

### 修复优先级建议

- **立即**（P0/P1）：B09-01（批量指纹 id 列缺失，单点必修）；B09-02（simhash 契约对称化）；B09-06（backend 端口下线 + nginx internal location 收敛）。
- **计划**（P2）：B09-03（updateSourceRunStatus 幂等窗口）；B09-07（key 校验常数时间）；B09-08（`/config` 过滤敏感字段）；B09-11（抽 InternalCallbackAppService）。
- **择机**（P3/P4）：B09-04/B09-09/B09-10/B09-12/B09-13（契约 DTO 化、告警周期化、来源标识、分层下沉）；B09-05/B09-14（路径合并、对账入口）。

### 排查盲区 / 待复核

- **[需查证]** B09-02：crawler 侧 `hamming_distance` 对负 simhash 是否容错（`crawler-service/crawler/dedup.py` 的 `hamming_distance` 实现未读全，影响修复方向选择）。
- **[需查证]** B09-06：生产 Docker 网络下 `request.getRemoteAddr()` 实际返回值（nginx 容器 IP 还是宿主桥接 IP），需运维确认；若 backend 配了 `server.forward-headers-strategy` 则 `getRemoteAddr` 行为再变。
- **[需查证]** B09-01：是否已有运行环境用 `IdType.AUTO` + DB 序列覆盖（当前 `BaseAggregateRoot` 固定 ASSIGN_ID，但若有 MyBatis-Plus 全局配置覆盖需确认 `application.yml`）。
- crawler 侧 `requirements.txt` 的 httpx 版本未读（属 C 模块范围，本模块仅引用）。
