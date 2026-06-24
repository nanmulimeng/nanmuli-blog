# X03 测试体系 排查报告

> **模块编号**：X03
> **排查范围**：backend 测试（失衡/形态）、crawler 测试（覆盖密度/形态）、frontend 测试（无单测）、测试形态与质量、关键路径缺口、测试可运行性、CI 关系、测试数据管理、覆盖率工具
> **基线 commit**：`6ae930098405f4d0553d96a852f3345d0f39682e`
> **工作区状态**：脏。涉及本模块的未提交改动：
> - `M crawler-service/tests/test_knowledge_base.py`
> - `M crawler-service/tests/test_optimization.py`
> - `M crawler-service/tests/test_search.py`
> - `?? backend/src/test/java/com/nanmuli/blog/infrastructure/persistence/webcollector/`（新增 `WebCollectPageMapperProjectionTest.java`，已计入本报告统计）
> - 其余脏文件（`ConfigRepositoryImpl.java`、`WebCollectPageMapper.java`、`crawler/search.py`、`optimization/knowledge_base.py`、`deploy/README.md`、`risk-register.md`、`release-gate.ps1`）非测试文件，不计入。
> **排查日期**：2026-06-24
> **排查人**：审计 agent（X03）
> **状态**：草稿

---

## 模块概览

**职责**：评估三子系统（backend / crawler / frontend）的测试体系是否支撑 MVP Beta 试用稳定化目标，识别覆盖缺口、形态失衡、可运行性风险。

**关键文件**：
- `backend/src/test/`（16 个测试文件，111 个 `@Test`）
- `backend/pom.xml:86-90`（测试依赖仅 `spring-boot-starter-test`）
- `crawler-service/tests/`（52 个测试文件）
- `crawler-service/tests/conftest.py:16-38`（内存 SQLite fixture）
- `crawler-service/requirements.txt:26-29`（pytest / pytest-asyncio / pytest-cov）
- `frontend/package.json:6-12`（scripts 无 `test`）

**对外接口 / 依赖**：
- 对外：无（测试为内部资产）。
- 依赖：JUnit 5 + Mockito + AssertJ（backend，经 `spring-boot-starter-test` 传递）；pytest + pytest-asyncio + pytest-cov + aiosqlite（crawler）；frontend 无测试依赖。

**已读文件清单**：
- `backend/pom.xml` —— 通读（确认测试依赖、无 surefire/jacoco 配置）
- `backend/src/test/java/com/nanmuli/blog/application/webcollector/WebCollectorAppServiceTest.java:1-120` —— 通读头部（确认 Mockito 形态）
- `backend/src/test/java/com/nanmuli/blog/infrastructure/persistence/article/ArticleMapperProjectionTest.java:1-42` —— 通读（反射注解契约测试形态）
- `crawler-service/tests/conftest.py` —— 通读（内存 SQLite fixture）
- `crawler-service/tests/test_deep.py:1-90` —— 通读头部（mock 密度形态）
- `crawler-service/tests/test_integration.py:1-70` —— 通读头部（"集成测试"实际形态）
- `crawler-service/requirements.txt` —— 通读
- `frontend/package.json` —— 通读
- `README.md:14-15,132,173,177` —— 片段（基线口径）
- 其余 backend/crawler 测试文件 —— 仅 grep 统计（`@Test` / `def test_` / `patch(` / `ASGITransport` / `class Test` 计数）

**主模块归属**：本模块深查**测试体系整体**。各业务模块报告（B06 鉴权、B08 采集、B13 AI 骨架、C04 日报、C06/C07 优化等）引用本模块条目编号说明各自测试缺口。无 CI 配置（`.github/workflows/` 不存在）归属 **X04**，本模块只引用。

---

## `[Bug]` 代码正确性与潜在缺陷

> 排查范围：测试代码自身的正确性（mock 残留、断言空转、时间敏感、flaky 风险）。**未发现测试代码本身的正确性缺陷**（测试是验证资产，bug 维度通常落在被测代码，归各业务模块）。以下为形态层面观察，归 [Arch]/[Test]。

未发现独立的 `[Bug]` 级测试代码缺陷。

---

## `[Security]` 安全漏洞

> 排查范围：测试是否硬编码真实密钥/token、是否绕过安全检查、是否泄露敏感配置。逐项覆盖 §2.2 技术栈重点在测试侧的体现。未命中则写"未发现"。

### [P级别待定/低] [Security] 测试 fixture 硬编码 API Key 与默认口令的扩散风险 <!-- 编号：X03-01 -->

> **[需查证]**：本条目基于 `grep` 命中分布推断，未逐文件审计每个硬编码字符串的语义。

- **定位**：`crawler-service/tests/`（多个测试文件硬编码 `"test-api-key"` 等占位 key）；backend `ProductionConfigHardeningTest.java`（验证默认口令不被带入生产的契约测试）。
- **现象**：crawler 测试中存在大量字面量 API Key（如 `"test-api-key"`），backend 有一份 `ProductionConfigHardeningTest` 反向校验默认弱口令不进生产。
- **影响**：占位 key 本身非真实密钥，泄露风险低；但若开发者后续将真实 key 写入测试常量（无 `.env` 隔离机制），会随仓库扩散。backend 的 hardening 测试是正向防御，风险点在 crawler 侧无同类"默认值不得进生产"的契约测试。
- **根因/分析**：crawler 测试体系无 fixture 隔离规范，key 直接字面量内联；backend 有 `ProductionConfigHardeningTest` 但 crawler 无对应。
- **修复方向**：①crawler 测试统一从 fixture 取 key（不内联字面量）；②crawler 补"默认 API_KEY 不得为空/弱值"的契约测试。改动面：中。
- **关联**：关联 B06（鉴权）、X06（配置一致性）、§2.6 跨服务双向 key 主题。

---

## `[Arch]` 架构与技术债

> 排查范围：测试形态失衡、分层覆盖断层、mock 策略与真实行为验证的偏离、可测试性设计。本模块为该维度主战场。

### [P1] [Arch] backend 全 Mockito 单测、零集成测试，Sa-Token/MyBatis/真实 PG 从未在 CI 跑过 <!-- 编号：X03-02 -->

- **定位**：
  - `backend/src/test/`（16 文件，全 `@ExtendWith(MockitoExtension.class)`，grep `@SpringBootTest|@DataJpaTest|@WebMvcTest|Testcontainers|@ExtendWith\(SpringExtension` **0 命中**）
  - `backend/pom.xml:86-90`（仅 `spring-boot-starter-test`，无 `testcontainers`/`spring-boot-testcontainers`）
  - `backend/src/test/java/com/nanmuli/blog/application/webcollector/WebCollectorAppServiceTest.java:54-94`（`@ExtendWith(MockitoExtension.class)` + `mockStatic(TransactionSynchronizationManager)`）
- **现象**：全部 111 个 `@Test` 是纯 Mockito 单测；连事务 `afterCommit` 回调都用 `mockStatic` 屏蔽；MyBatis SQL、Sa-Token 拦截器、真实 PostgreSQL（含 pgvector、逻辑删除、乐观锁）**从未在自动化测试中执行**。
- **影响**：MVP Beta 试用稳定化的核心风险——①MyBatis 的 `${}` vs `#{}`、`QueryWrapper.apply()` 拼接、分页+逻辑删除组合的 SQL 错误只能靠线上暴露；②Sa-Token 路由拦截器规则（B06 已记"纯靠 URL 前缀"）漏配 admin 路径无测试兜底；③Flyway/schema 三轨漂移（B15/X02）导致的缺列运行时错误无集成层捕获；④乐观锁 `@Version`、`@TableLogic` 是否生效零验证。
- **根因/分析**：测试体系从单测起步，未建立集成测试基座（无 Testcontainers 依赖、无 `@SpringBootTest` 习惯）。这不是单点疏忽，是测试策略层面的形态选择——单测密度高给人"覆盖充分"错觉，但关键路径（DB/鉴权/事务）实际无保护。
- **修复方向**：①引入 `testcontainers-postgresql` + `@SpringBootTest` 建立 smoke 集成测试基座（覆盖启动、关键 Mapper、鉴权拦截器）；②优先补 B06（鉴权）、B08（采集状态机）、B15（schema 一致性）的集成测试；③CI（X04）中分离 `unit` / `integration` 两个 job。改动面：大（跨测试基座搭建 + CI）。
- **关联**：§2.6 横向主题（鉴权一致性、schema 漂移）；B06/B08/B13/B15 各模块测试缺口引用本条；X04（CI）。

### [P1] [Arch] backend 测试覆盖严重失衡，webcollector 独占 68/111（61%），Auth/UserAppService/领域层 0 覆盖 <!-- 编号：X03-03 -->

- **定位**：
  - `backend/src/test/java/com/nanmuli/blog/application/webcollector/WebCollectorAppServiceTest.java`（**68 个 `@Test`**）
  - `backend/src/test/java/com/nanmuli/blog/application/webcollector/WebCollectSourceAppServiceTest.java`（2）
  - `backend/src/test/java/com/nanmuli/blog/interfaces/rest/WebCollectorControllerTest.java`（7）
  - 即 webcollector 域合计 **77/111 ≈ 69%**
  - `glob backend/src/test/**/*{Auth,User,SaToken,Digest,Optimization,Proxy,Dashboard,Home,Scheduler,Category,DailyLog,FriendLink}*Test.java` → **0 命中**
- **现象**：webcollector 一家独占近 7 成测试；鉴权（AuthController/UserAppService/SaTokenConfig/Filter）、配置（ConfigAppService 仅 5）、日报、调度、首页聚合、分类树、技术日志、友链/项目/技能的领域层与 AppService **零或近零覆盖**。
- **影响**：MVP 试用最关键的"登录能用、配置改了生效、日报定时触发"链路无单测保护。鉴权 0 覆盖叠加 X03-02 的零集成测试 = 鉴权正确性纯靠人工验证；这与 CLAUDE.md "MVP Beta 试用稳定化"目标直接冲突。
- **根因/分析**：测试随开发热点累积（webcollector 是近期活跃模块，见 git log `codex/digest-generation-closure` 分支），缺乏按模块/风险的测试覆盖规划。`FileAppServiceTest`(6)、`ConfigAppServiceTest`(5)、`InternalCallbackControllerTest`(5) 是仅有的非 webcollector 业务测试。
- **修复方向**：①按"风险×复杂度"排补测优先级：Auth/UserAppService（P0 补）、ConfigAppService（加强）、调度对账、Dashboard 聚合并行；②领域层（聚合根不变量、状态机流转）补纯单测（不依赖 Spring，成本低）；③建立覆盖矩阵文档避免再次失衡。改动面：中（持续补，非一次性）。
- **关联**：§2.5 闭环完整性；B06/B01/B02/B03/B04/B07/B17 各模块测试缺口均引用本条。

### [P2] [Arch] crawler 测试"集成"名不副实，真实 Crawl4AI/AI/搜索引擎/callback HTTP 从未联调 <!-- 编号：X03-04 -->

- **定位**：
  - `crawler-service/tests/test_integration.py:1-70`（文件名"集成"，但 `Mock 爬虫和 AI，用内存 SQLite`，见 docstring 第 3 行）
  - `crawler-service/tests/test_deep.py:83-88`（`patch("crawler.deep.AsyncWebCrawler")` + `BFSDeepCrawlStrategy` + `DomainFilter` + `FilterChain` 全 mock）
  - `crawler-service/tests/test_crawler_extreme.py:549,575,610,637,662`（`patch("crawler.deep.AsyncWebCrawler")` 多处）
  - `crawler-service/tests/test_dependency_mode.py:43`（`pytest.raises(RuntimeError, match="Crawl4AI is unavailable")` —— 测的是降级，不是真实 Crawl4AI）
  - `grep Crawl4AI|arun\(` 命中均为 mock 上下文
- **现象**：crawler 测试体系是"**真 SQLite schema + Mock 一切外部**"形态。`test_deep.py` 用 157 个 `patch(` 把 Crawl4AI 的 `AsyncWebCrawler`、`BFSDeepCrawlStrategy`、`FilterChain`、`DomainFilter` 全部替换——**测的是 BFS 编排逻辑，不是 Crawl4AI 的真实 JS 渲染/反爬/超时行为**。AI provider、搜索引擎抓取、backend callback（`X-Callback-Key`）同理全 mock。
- **影响**：①真实采集成功率、反爬绕过能力、Crawl4AI 升级兼容性（Crawl4AI 0.8.x 仍在快速迭代）**零自动化验证**，只能上线后人工发现；②AI provider 响应格式漂移（JSON 结构、字段缺失）无测试捕获；③跨服务 callback 契约（B09/C01 横向主题）只有单侧 mock，无双向联调。
- **根因/分析**：真实联调需起 Crawl4AI 浏览器进程 + AI API key + 网络，成本高、有 flaky 风险。当前策略用 mock 换确定性，代价是**外部依赖行为变更时无预警**。这是 mock 策略的固有取舍，但缺少"少量冒烟级真实集成测试"作为兜底。
- **修复方向**：①新增 `tests/e2e/` 或 `tests/smoke/` 目录，标记 `@pytest.mark.e2e`，CI 中可选运行，覆盖：单个真实 URL 采集、AI provider 一次真实调用（用 test key）、callback 本地回路；②Crawl4AI 升级时手动跑 e2e 回归。改动面：中。
- **关联**：C03（采集核心）、C05（AI 整理）、B09/C01（callback 契约）、§2.6 跨服务契约。

### [P2] [Arch] crawler 覆盖密度极高但形态单一，unittest/pytest 双风格混用 <!-- 编号：X03-05 -->

- **定位**：
  - `crawler-service/tests/test_search.py`（**唯一用 `unittest.TestCase` 风格**，87 个 `def test_`，6 个 `class Test...(unittest.TestCase)`，见 `test_search.py:46,92,151,179,223,245`）
  - 其余 51 个测试文件为 pytest 函数风格
  - `grep "def test_"` 总命中 900；`grep "def test_|class Test"` 总命中 1635（差异来自 `class Test` 内的方法计数与匹配口径）
- **现象**：crawler 有 52 个测试文件、约 1300+ 测试函数（数量级与 README "1366 passed" 吻合，函数级精确数需 pytest 实际收集，**[需查证]** 精确数），密度远高于 backend；但 `test_search.py` 独用 unittest 风格，与其余文件不一致，增加维护心智。
- **影响**：风格不统一是可维护性问题（P3 级单独看），但叠加 X03-04（全 mock）后，"高密度覆盖"给人虚假安全感——大量测试验证的是 mock 行为而非真实采集逻辑。`test_search.py` 的 unittest 风格在 pytest 收集下能跑（兼容），但 fixture 注入、`pytest.mark` 等特性不可用。
- **根因/分析**：`test_search.py` 可能是早期遗留，后续新测试统一用 pytest 风格但未回填。
- **修复方向**：①低优先级将 `test_search.py` 迁移到 pytest 风格（保持断言不变）；②更重要：审计 mock 密度最高文件（`test_deep.py` 157 patch、`test_digest_orchestrator.py` 79 patch）确认是否"为 mock 而 mock"（mock 循环而非验证行为）。改动面：中。
- **关联**：X03-04（mock 策略）。

### [P3] [Arch] backend 测试代码反射契约化趋势初显，但无 DB 真跑 <!-- 编号：X03-06 -->

- **定位**：
  - `backend/src/test/java/com/nanmuli/blog/infrastructure/persistence/article/ArticleMapperProjectionTest.java:16-40`（反射读 `@Select` 注解，断言 SQL 不含 `SELECT *`）
  - `backend/src/test/java/com/nanmuli/blog/infrastructure/persistence/webcollector/WebCollectPageMapperProjectionTest.java`（新增，同类形态，2 个 `@Test`）
  - `backend/src/test/java/com/nanmuli/blog/shared/query/BasePageQueryTest.java`（2 个 `@Test`）
- **现象**：出现"静态契约测试"形态——用反射读注解/常量验证 SQL 不含 `SELECT *`、投影不含大字段。这比纯 Mockito 更接近"验证真实代码结构"，但仍**不连 DB**。
- **影响**：能捕获 `SELECT *` 投影泄漏（B14 关注点）和 `ARTICLE_LIST_COLUMNS` 常量被误改，但无法发现 SQL 语法错误、字段名拼写、运行时类型映射。属于有益补充，非集成测试替代品。
- **根因/分析**：合理的轻量契约测试，方向正确，但不应被误读为"持久层已覆盖"。
- **修复方向**：维持现状，明确标注此类测试的边界（不替代集成测试）。改动面：无。
- **关联**：B14（数据访问层）。

---

## `[Deps]` 依赖升级与版本

### 本模块依赖清单（基于声明文件，未翻依赖源码）

| 依赖 | 版本 | 声明位置 | 已知风险/可升级 | 备注 |
|---|---|---|---|---|
| spring-boot-starter-test | 继承自 SB 3.3.5 | `backend/pom.xml:86-90` | 含 JUnit 5 + Mockito + AssertJ | 未显式声明 Mockito/JUnit5 版本 |
| testcontainers（postgresql） | **未声明** | `backend/pom.xml`（缺失） | 需新增 | 集成测试基座缺失（见 X03-02） |
| jacoco-maven-plugin | **未声明** | `backend/pom.xml`（缺失） | 需新增 | backend 无覆盖率工具 |
| pytest | `>=7.4.0` | `crawler-service/requirements.txt:27` | 可升至 8.x | |
| pytest-asyncio | `>=0.23.0` | `crawler-service/requirements.txt:28` | | |
| pytest-cov | `>=4.1.0` | `crawler-service/requirements.txt:29` | **声明但无配置文件** | 见 X03-07 |
| aiosqlite | `>=0.19.0` | `crawler-service/requirements.txt:32` | | conftest 内存 DB 用 |
| vitest/jest/playwright | **未声明** | `frontend/package.json`（缺失） | 需新增 | frontend 无测试框架 |

> 排查范围：仅测试相关依赖。未发现因依赖版本导致的测试阻断风险。主要缺口是**依赖缺失**（testcontainers、jacoco、frontend 测试框架），归 [Arch] 条目。

---

## `[Design]` 功能设计合理性

> 本节从测试体系是否支撑 MVP 稳定化目标出发审视。

**审视结论**：

1. **场景适配（§2.5-1）**：单人维护的技术博客 + 每工作日 AI 日报场景下，当前测试体系**形态与目标错配**。backend 111 个单测看似充足，但全部 mock 掉 DB/鉴权/事务，而 MVP 试用最怕的恰恰是"登录失败、配置改了不生效、日报定时没触发、schema 缺列报错"——这些都不是 Mockito 单测能捕获的。crawler 反过来，密度极高（1300+ 函数）但全 mock 外部依赖，真实采集/AI 行为零验证。**测试投入与风险分布不匹配**。
2. **闭环完整性（§2.5-2）**：测试体系自身**不形成完整闭环**——无覆盖率阈值门禁（X03-07）、无 CI 自动跑（关联 X04）、无集成/e2e 兜底（X03-02/04）。测试只能手动跑（`mvn test` / `pytest`），新提交不会自动触发验证，回归靠开发者自觉。
3. **可运维性（§2.5-3）**：故障时测试无法帮助定位"是代码 bug 还是环境/schema/外部依赖问题"，因为后者从未被测试覆盖。README 基线漂移（X03-08）进一步削弱测试作为"可信基线"的运维价值。

### [P4] [Design] frontend 零测试，关键页面与状态管理无保护 <!-- 编号：X03-09 -->

- **定位**：`frontend/package.json:6-12`（`scripts` 仅 `dev/build/preview/lint/format`，无 `test`）；`frontend/package.json:27-51`（`devDependencies` 无 vitest/jest/playwright/cypress）；`frontend/` 下无 `tests/`、`__tests__/`、`*.spec.ts`、`*.test.ts`（glob 确认）。
- **现象**：frontend 完全无单测/E2E。lint 和 `vue-tsc` 类型检查是仅有的自动化质量门。
- **影响**：MVP 试用中前端是用户直接接触面——登录守卫（F01）、请求层 401 重试（F02）、md 双轨渲染与 XSS（F03）、采集/日报管理页轮询（F04）、配置双向刷新（F05）均无测试。类型检查能挡语法/类型错，挡不了逻辑回归（如守卫边界、markdown 净化绕过、轮询竞态）。
- **建议方向**：①引入 vitest（与 vite 同构，成本最低）+ `@vue/test-utils`，先补 F01 守卫、F02 请求层、F03 markdown 净化的纯逻辑单测；②E2E（playwright）作为可选后续。改动面：中（框架引入 + 首批用例）。
- **关联**：F01/F02/F03/F04/F05 各前端模块；§2.5 闭环完整性。

### [P3] [Design] README 测试基线口径漂移，削弱可信度 <!-- 编号：X03-08 -->

- **定位**：`README.md:14`（"Backend ... `mvn test`：88 passed"）、`README.md:15`（"Crawler Service ... 1366 passed"）。
- **现象**：实际 backend `@Test` 计数 **111**（grep `@Test` 命中），README 写 **88**；crawler 函数统计约 1300+ 级别（精确数 [需查证]），README 写 **1366**。CLAUDE.md 另写"75 tests passed"（backend），三处口径（75/88/111）互不一致。
- **影响**：README 作为"最近验证基线"（CLAUDE.md 明确要求记录），数字漂移让审计/接力者无法判断"测试是否真的在跑、是否真的全绿"。`webcollector` 测试新增（68 个）和 `WebCollectPageMapperProjectionTest` 新增（2 个）显然未回写 README。
- **建议方向**：①README/CLAUDE.md 基线数字统一为当前实测（111 / 约 1300+）；②在 X04 CI 落地后，基线由 CI 自动回写而非手维护。改动面：小。
- **关联**：X04（CI）、X05（文档一致性）。

---

## 模块小结

### 严重度统计

| 级别 | 数量 | 条目编号 |
|---|---|---|
| P0 | 0 | — |
| P1 | 2 | X03-02（零集成）、X03-03（覆盖失衡） |
| P2 | 2 | X03-04（crawler mock 化集成）、X03-05（风格/密度） |
| P3 | 2 | X03-06（契约测试边界）、X03-08（README 基线漂移） |
| P4 | 1 | X03-09（frontend 零测试） |
| [需查证] | 2 | X03-01（fixture 硬编码 key 语义）、X03-05（crawler 精确函数数） |

> 注：X03-01 安全条目因未逐文件审计每个硬编码字符串，定级待复核；倾向 P2-P3。

### Top 风险（本模块最该先看的 ≤3 条）

1. **X03-02 backend 零集成测试** —— MVP 试用核心风险，Sa-Token/MyBatis/PG 从未在自动化测试中跑过，schema 漂移和鉴权漏配只能线上暴露。
2. **X03-03 backend 覆盖失衡（webcollector 69%，Auth/User 0）** —— 鉴权零覆盖叠加零集成，登录链路无任何自动化保护。
3. **X03-04 crawler 全 mock 集成** —— 真实采集成功率/AI 格式漂移/Crawl4AI 升级兼容性零验证。

### 修复优先级建议

- **立即**（P1）：引入 testcontainers + `@SpringBootTest` 搭 backend 集成测试基座（X03-02）；按风险补 Auth/UserAppService 单测 + 集成（X03-03）。
- **计划**（P2）：crawler 补 `@pytest.mark.e2e` 冒烟级真实联调（X03-04）；审计 mock 密度极端文件确认非"mock 循环"（X03-05）。
- **择机**（P3/P4）：README 基线口径对齐（X03-08）；frontend 引入 vitest 补守卫/请求层/净化单测（X03-09）；crawler 测试 key fixture 化（X03-01）。

### 排查盲区 / 待复核

- **[需查证]** crawler 测试精确函数数：本报告基于 `grep "def test_"`(900) 与 `grep "def test_|class Test"`(1635) 统计，与 README "1366" 的精确对齐需实际 `pytest --collect-only`（命令边界 §1.3 禁止，未执行）。函数数量级结论（1300+）成立。
- **[需查证]** X03-01：crawler 测试中硬编码 `"test-api-key"` 等字面量是否含真实 key 片段，未逐文件审计。
- **未执行**：backend `mvn test` / crawler `pytest` 实际通过率（命令边界禁止），报告基线"111 @Test / 约 1300+ 函数"为静态计数，是否全绿、有无 flaky 需 X04 CI 落地后验证。
- **未深查**：单测内部是否存在"断言空转"（`assertThat(mock).isNotNull()` 类无意义断言）——抽样 WebCollectorAppServiceTest/ArticleMapperProjectionTest 未发现，但 111 个测试未逐一审计。
