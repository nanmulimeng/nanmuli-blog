# C12 硬编码规则与维护性 排查报告

> **模块编号**：C12
> **排查范围**：crawler-service 中硬编码域名表/友好名/分类表、搜索引擎降级链、低价值内容过滤规则、跨库一致性窗口（维护性视角）、整体可维护性与配置化/版本化缺失
> **基线 commit**：`6ae930098405f4d0553d96a852f3345d0f39682e`
> **工作区状态**：脏。涉及本模块的未提交改动：`crawler-service/crawler/search.py`（+5/-2，新增 `browser_crawl_slot` 资源守卫，**未触及 `ENGINE_PRIORITY` 等硬编码规则**，属 C03 范围）。`crawler-service/standalone/task_executor.py` **干净**（所有硬编码段均为已提交状态）。
> **排查日期**：2026-06-24
> **排查人**：C12 审计 agent
> **状态**：待复核

---

## 模块概览

**职责**：维护 crawler-service 中"域名→友好名/分类"映射、日报候选低价值过滤规则、搜索引擎降级链顺序等**静态业务规则**，以及评估这些规则的配置化、版本化、跨库一致性等可维护性属性。本模块不实现具体采集/过滤逻辑（那是 C03/C08），只审视"规则作为数据"的维护成本。

**关键文件**：
- `crawler-service/standalone/task_executor.py:667-723` —— `_FRIENDLY_SOURCE_NAMES` 域名→友好名表（~75 条）
- `crawler-service/standalone/task_executor.py:749-841` —— `_SOURCE_CATEGORY_MAP` 域名→分类表（~75 条）
- `crawler-service/standalone/task_executor.py:844-873` —— `_PATH_CATEGORY_RULES` + `_TITLE_PATTERNS` 正则分类规则
- `crawler-service/standalone/task_executor.py:919-958` —— `_DIGEST_KEYWORD_EXPANSIONS` + `_DIGEST_CATEGORY_FALLBACK_KEYWORDS` 关键词扩展表
- `crawler-service/standalone/task_executor.py:116-239` —— `_low_value_digest_candidate_reason` 低价值过滤函数（~124 行 ad-hoc 规则）
- `crawler-service/crawler/search.py:82-117` —— `SEARCH_ENGINES` 选择器表 + `ENGINE_PRIORITY` 降级链
- `crawler-service/crawler/quality.py:27-178` —— `SourceAuthority` 硬编码兜底域名表（OFFICIAL/HIGH/TECH 三档，~50 条）+ Java API 缓存
- `crawler-service/crawler/filters.py:13-127` —— `EXCLUDED_DOMAINS`/`EXCLUDED_DOMAIN_SUFFIXES`/`DOMAIN_PATH_EXCLUSIONS`/`EXCLUDED_KEYWORDS` 黑名单
- `crawler-service/crawler/page_classifier.py:28-35` —— `_SERP_ROOT_DOMAINS` 搜索引擎根域表
- `crawler-service/optimization/strategy.py:17` —— `ENGINE_PRIORITY` **第二份**定义（与 search.py 重复）

**对外接口 / 依赖**：
- 对外（被消费）：`extract_source_name()`、`infer_category()`（task_executor.py）→ 被 `digest_gen_agent.py:149`、`organizer_helper.py:35` 调用；`SourceAuthority.score()`（quality.py）→ 被 quality 评分链调用；`is_excluded_domain()`（filters.py）→ 被 search.py/quality.py 共享
- 依赖：PG `source_authority` 表（通过 Java API `/api/internal/collector/source-authority/all` 拉取，quality.py:163）、`settings.java_api_url`/`settings.callback_api_key`

**已读文件清单**：
- `crawler-service/standalone/task_executor.py` —— 通读硬编码段（行 100-280、660-999）
- `crawler-service/crawler/search.py` —— 通读 ENGINE_PRIORITY 段（行 75-155、800-890）
- `crawler-service/crawler/quality.py` —— 通读 SourceAuthority 类（行 25-178）
- `crawler-service/crawler/filters.py` —— 通读全文件（行 1-135）
- `crawler-service/crawler/page_classifier.py` —— 片段（行 26-45）
- `crawler-service/optimization/strategy.py` —— grep ENGINE_PRIORITY（行 17、303）
- `backend/src/main/resources/db/migration/V1_18__create_source_authority.sql` —— 通读（34 条种子）
- `docs/audit/module-audit/crosscutting/X02-schema-integrity.md` —— grep source_authority/C12 相关段（确认归属，不重复）

**主模块归属**：本模块是"硬编码规则可维护性"的主模块，深查。对以下共享对象**只引用**：
- 跨库一致性（SQLite ↔ PG）→ **X02**（已记 X02-06/X02-13）
- 降级链**实现逻辑**（四引擎降级、超时、回退阈值）→ **C03**（本模块只看顺序硬编码与重复定义）
- source_authority 表 schema/种子合理性 → **X02**（X02-06）

---

## `[Bug]` 代码正确性与潜在缺陷

> 排查范围：硬编码规则的逻辑正确性（域名匹配边界、正则误杀、降级链顺序一致性）。重点检查 `_low_value_digest_candidate_reason` 的误杀边界、`ENGINE_PRIORITY` 两处定义一致性、`extract_source_name` 后缀匹配安全性。未发现 P0/P1 级 Bug，记录 1 个 P2 边界问题。

### [P2] [Bug] `ENGINE_PRIORITY` 两处独立硬编码，降级链顺序变更存在漂移风险  <!-- 编号：C12-01 -->
- **定位**：`crawler-service/crawler/search.py:117` 与 `crawler-service/optimization/strategy.py:17`
- **现象**：两处均字面量定义 `ENGINE_PRIORITY = ["bing", "baidu", "sogou", "google"]`，**不是 import 复用**（grep 确认 strategy.py 未从 search.py 导入，各自独立声明）。search.py:815 用它构造降级队列，strategy.py:303 用它选择下一个引擎。
- **影响**：若未来调整降级顺序（如把 google 提前、或新增引擎），需同步改两处且无一致性校验。两处不一致会导致：采集降级链（search.py）按 A 顺序、优化策略推荐的下一引擎（strategy.py）按 B 顺序，产生行为矛盾。
- **根因/分析**：strategy.py 早期可能为避免循环导入而复制了常量。已排除误判：当前两处值确实相同，但这是"碰巧一致"而非"机制保证一致"。
- **修复方向**：①将 `ENGINE_PRIORITY` 抽到独立模块（如 `crawler/engine_config.py`），两处 import；②或 strategy.py 从 search.py 导入（需确认无循环依赖）。改动面：小（单常量提取 + 2 处 import 修改 + 测试）。
- **关联**：次维度 [Arch]；降级链实现细节见 C03；横向主题：跨模块常量一致性。

---

## `[Security]` 安全漏洞

> 排查范围：硬编码规则本身不涉及鉴权/注入/SSRF。仅检查 `SourceAuthority.preload_authority_cache` 的 HTTP 拉取是否引入风险（callback_api_key 泄漏、响应信任）。逐项覆盖计划 §2.2 中与本模块相关项（双向 key 归 B09、SSRF 归 C01）。未发现本模块独有的安全问题。

未发现。`SourceAuthority.preload_authority_cache`（quality.py:144-178）的 HTTP 调用、`X-Callback-Key` 头处理、超时配置均归 B09（双向 key）与 C01（HTTP 客户端）模块，本模块只记：硬编码兜底数据本身不构成安全漏洞，兜底失败时（API 不可用）退化为硬编码评分，属可用性问题而非安全问题。

---

## `[Arch]` 架构与技术债

> 排查范围：硬编码域名表的多处重复定义、配置化缺失、版本化/审计缺失、与 PG 表的双源漂移。这是本模块的核心维度。注意：source_authority 双源 schema/种子问题归 X02（X02-06），本模块只记 Python 侧独有的硬编码技术债。

### [P2] [Arch] 五套域名表分散在四个文件，无统一数据源，维护成本高  <!-- 编号：C12-02 -->
- **定位**：
  - `task_executor.py:667-723` `_FRIENDLY_SOURCE_NAMES`（~75 条，域名→显示名）
  - `task_executor.py:749-841` `_SOURCE_CATEGORY_MAP`（~75 条，域名→分类）
  - `quality.py:38-79` `OFFICIAL_DOMAINS`/`HIGH_QUALITY_COMMUNITIES`/`TECH_BLOGS`（~50 条，域名→评分档）
  - `filters.py:13-66` `EXCLUDED_DOMAINS`/`EXCLUDED_DOMAIN_SUFFIXES`（~45 条，域名→黑名单）
  - `page_classifier.py:28-35` `_SERP_ROOT_DOMAINS`（~11 条，搜索引擎根域）
- **现象**：同一域名（如 `github.com`、`medium.com`、`stackoverflow.com`、`csdn.net`）在多张表中分别出现，语义不同（显示名/分类/评分/黑名单/SERP），但**无任何交叉校验或单一数据源**。新增一个官方域名需考虑是否要同步加入 `_FRIENDLY_SOURCE_NAMES`（否则显示原始域名）、`_SOURCE_CATEGORY_MAP`（否则分类靠标题正则兜底）、`quality.OFFICIAL_DOMAINS`（否则评分偏低）、PG `source_authority`（否则 API 路径取不到）。
- **影响**：单人维护场景下，规则演进需在 4-5 个文件间跳转，极易遗漏某张表导致行为不一致。例如：某域名在 `_SOURCE_CATEGORY_MAP` 是 `tech_article` 但在 `quality.OFFICIAL_DOMAINS` 漏配，会得到"分类正确但可信度被低估"的矛盾结果。
- **根因/分析**：各表历史地随功能增量添加（filters.py 最早做黑名单 → quality.py 加评分 → task_executor.py 加显示名/分类），无人做全局归并。`filters.py:5` 注释声称"单一数据源消除维护两份列表的漂移风险"，但实际只统一了 search.py 和 quality.py 的黑名单，并未覆盖后续新增的友好名/分类表。
- **修复方向**：①建立"域名主数据"单一事实源（推荐 PG 表 `domain_metadata(domain, friendly_name, category, authority_score, is_excluded, serp_root)`），各处读取；②或至少在 Python 侧抽取 `domain_registry.py` 统一持有所有域名→属性映射，现有各表改为查询接口。改动面：大（跨文件重构 + 数据迁移 + 测试）。
- **关联**：次维度 [Design]（C12-05）；X02-06（source_authority 双源）；横向主题：配置一致性。

### [P2] [Arch] 低价值过滤规则与 filters.py 黑名单功能重叠，规则边界模糊  <!-- 编号：C12-03 -->
- **定位**：`task_executor.py:116-239` `_low_value_digest_candidate_reason`（~124 行）vs `filters.py:13-127`（`EXCLUDED_DOMAINS` 等）
- **现象**：`_low_value_digest_candidate_reason` 针对 digest 候选池实现了第二套低价值过滤：csdn gitblog（行 225-226）、百度知道（行 146-147、157-158）、招聘页（行 173-182）、认证页（行 184-190）、下载站（行 192-198）、基础定义页（行 200-215）、硬件新闻（行 228-237）。其中 `softonic.com`（行 193）同时在 `filters.py:48` 的 `EXCLUDED_DOMAINS` 中——**同一域名被两套规则各自过滤一次**。`techpowerup.com`（行 228）的硬件新闻规则与 filters.py 无交集，属纯 ad-hoc。
- **影响**：①规则边界模糊——开发者不知道某域名该进 `filters.py`（全局黑名单，影响所有采集）还是 `_low_value_digest_candidate_reason`（仅影响日报候选池），文档未界定；②`softonic.com` 这类双过滤域名，若未来想"放行用于普通采集但日报仍排除"，需在两处分别调整；③`_low_value_digest_candidate_reason` 函数注释（行 117-119）说"普通采集仍允许用户抓取词典、问答"，但实际 `zhidao.baidu.com`（行 146）只在此函数排除、filters.py 未排除，符合注释；而 `softonic.com` 在两处都排除，**违反注释承诺**（普通采集也会被 filters.py 排除）。
- **根因/分析**：filters.py 是"全局硬黑名单"，`_low_value_digest_candidate_reason` 是"日报软过滤"，本应分层清晰，但因历史增量导致部分域名（softonic）两边都加。无机制防止重复添加。
- **修复方向**：①明确分层契约并文档化（filters.py = 任何场景都排除；_low_value = 仅日报候选池排除）；②对 softonic 这类两边都有的，按语义归位（softonic 是下载站，应留 filters.py，从 _low_value 移除）；③加一条测试断言"两套规则的交集为空"作为回归护栏。改动面：中（规则梳理 + 契约文档 + 交叉校验测试）。
- **关联**：次维度 [Bug]；C12-02（域名表统一）。

### [P3] [Arch] 硬编码规则无版本号、无 changelog、无变更审计  <!-- 编号：C12-04 -->
- **定位**：全模块所有硬编码段（task_executor.py:667-958、search.py:82-117、quality.py:38-79、filters.py:13-127）
- **现象**：grep `RULES_VERSION|rules_version|filter_version|FILTER_VERSION|category_version` 全仓零命中。所有规则无版本字段、无变更日志、无上线时间戳。`SEARCH_ENGINES` 每个引擎有 `selector_version: "2026-05"`（search.py:89/97/105/113），但这只是选择器 CSS 规则的版本标记，不覆盖域名表/分类表/降级链顺序。
- **影响**：①规则调整无审计，回滚时只能靠 git blame 定位"哪次提交改了哪条规则"，但无法在运行时识别"当前生效的是哪一版规则"；②日报质量回归时，无法快速判断"是规则变了还是数据变了"；③若未来支持 Java 后端下发规则，缺少版本号做兼容判断。
- **根因/分析**：规则演进初期未建立版本治理。对于单人 MVP 项目，git 历史勉强够用，但随着规则增长（当前仅 `_low_value` 就 124 行），无版本会越来越痛。
- **修复方向**：①为每套规则加 `VERSION = "YYYY-MM-DD"` 或语义版本常量，记录到日报 metadata；②重大规则变更在 task metadata 留 rule_version 字段，便于质量回归归因。改动面：小（加常量 + 记录点）。
- **关联**：次维度 [Design]（可运维性）。

---

## `[Deps]` 依赖升级与版本

### 本模块依赖清单（基于声明文件，未翻依赖源码）

本模块是"规则数据"模块，不直接引入第三方库。规则消费涉及的标准库：`re`、`urllib.parse`、`httpx`（quality.py 拉取 API）。无本模块独有的依赖声明。

| 依赖 | 版本 | 声明位置 | 已知风险/可升级 | 备注 |
|---|---|---|---|---|
| httpx | （见 requirements.txt，归 C01） | `crawler-service/requirements.txt` | 归 C01 | 仅 `SourceAuthority.preload_authority_cache` 使用 |

> 排查范围：本模块无独有依赖。未发现。

---

## `[Design]` 功能设计合理性

> 从单人维护的技术博客 + 每工作日 AI 日报场景出发，审视硬编码规则的设计合理性。回答计划 §2.5 中的 4 个相关问题。

**审视结论**：

1. **场景适配（§2.5-1）**：单人维护场景下，当前规模的硬编码（域名表合计约 250 条、低价值过滤 124 行）处于"勉强可控但逼近阈值"的区间。`filters.py` 早期"单一数据源"设计是好的，但后续增量（友好名/分类/评分表）破坏了这一原则。判断：**不是过度设计，而是"欠统一"**——规则该有的都有，只是散落。

2. **可运维性（§2.5-3）**：硬编码规则的最大运维痛点是**变更需改代码 + 重启服务**。单人博主发现"CSDN 某子域质量太差想临时降分"或"新冒出的 AI 工具站想加入官方名单"，必须改 Python 源码、提交、重启 crawler。而 `source_authority` 表已经具备"Java 管理端改 DB → crawler 缓存刷新"的能力（quality.py:144），说明项目已有动态化基建，但只用于评分，未扩展到友好名/分类/低价值过滤。判断：**配置化方向明确，基建已存在一半，缺的是把更多规则接入这个通道**。

3. **缺失功能（§2.5-5）**：无规则的"试运行/灰度"机制。修改 `_low_value_digest_candidate_reason` 后，只能等下一次日报任务跑完看效果，无法对历史候选池回放验证新规则是否会误杀。这对"调整过滤规则"这一高频运维操作很不友好。

4. **单点与扩展（§2.5-7）**：当前规则全部 Python 硬编码，Java 后端无法干预。若未来第二个内部服务接入并希望用不同的分类规则（如某服务只关心 paper 分类），Python 侧规则无法按调用方（`X-Client-Id`）差异化。MVP 阶段可接受，但这是扩展硬阻塞点之一。

### [P2] [Design] 硬编码规则无可运营入口，变更需改代码重启，与 source_authority 动态化能力不对齐  <!-- 编号：C12-05 -->
- **定位**：`task_executor.py:667-958`（友好名/分类/关键词扩展）、`filters.py:13-127`（黑名单）、`search.py:117`（降级链）—— 均无配置化入口；对比 `quality.py:144-178`（source_authority 已支持 API 拉取）
- **现象**：`source_authority` 评分已实现"PG 表 → Java API → crawler 内存缓存（TTL 1h）"的动态化链路，单人博主可在 DB 改分数后 1 小时内生效（或重启立即生效）。但友好名、分类、低价值过滤、降级链顺序、关键词扩展等规则**仍纯硬编码**，无任何运行时配置入口。
- **影响**：①规则演进成本高——改一条分类规则要走"改代码→提交→重启"全流程，与 source_authority 的"改 DB 即生效"体验割裂；②规则变更无法灰度——无法对部分日报任务试用新规则；③违背 CLAUDE.md 声称的"配置 DB 化、可运营"方向（README 与 X02-13 都指出 source_authority 应可运营，同理其他规则也应可运营）。
- **建议方向**：分阶段配置化——①短期：把变更频率最高的"低价值过滤域名清单"外置为 JSON/YAML（crawler 启动加载，支持热重载）；②中期：扩展 source_authority 表或新增 `domain_metadata` 表，承载友好名/分类，复用现有 Java API 下发通道；③长期：降级链顺序、关键词扩展等也纳入 DB 管理。降级链顺序因影响采集核心链路（C03），配置化需更谨慎，建议最后做。改动面：中→大（分阶段）。
- **关联**：C12-02（域名表统一）、C12-04（版本化）；X02-13（source_authority 管理端入口）；横向主题：配置一致性。

### [P4] [Design] 无规则回归测试机制，过滤规则调整无法对历史数据回放验证  <!-- 编号：C12-06 -->
- **定位**：`task_executor.py:116-239` `_low_value_digest_candidate_reason`；测试仅见 `test_integration.py:208-220` 对 `extract_source_name`/`infer_category` 的少量断言，无对 `_low_value_digest_candidate_reason` 的直接单元测试（grep 该函数名在 tests/ 下零命中调用方测试）
- **现象**：`_low_value_digest_candidate_reason` 有 124 行 ad-hoc 规则、覆盖十余种站点场景，但无独立单元测试文件，仅通过 digest 集成测试间接覆盖。调整任一规则（如放宽 csdn gitblog 过滤）后，无法快速验证"历史候选池中被误杀/漏杀的变化"。
- **影响**：过滤规则调整是高频运维操作，但每次调整都依赖完整日报集成测试跑一遍才能确认效果，反馈周期长、成本高。误杀风险（如某优质 csdn 教程被 generic tutorial 规则误杀，行 217-223）难以提前发现。
- **建议方向**：①为 `_low_value_digest_candidate_reason` 补独立单元测试（构造典型 URL × 期望理由的表驱动测试）；②建立"规则回归语料库"——保存历史 digest 候选样本，规则变更后对语料回放比对差异。改动面：中（测试基建 + 语料沉淀）。
- **关联**：C12-03（规则边界）；X03（测试体系）。

---

## 模块小结

### 严重度统计

| 级别 | 数量 | 条目编号 |
|---|---|---|
| P0 | 0 | — |
| P1 | 0 | — |
| P2 | 4 | C12-01、C12-02、C12-03、C12-05 |
| P3 | 1 | C12-04 |
| P4 | 1 | C12-06 |

### 硬编码规则规模统计

| 规则集 | 文件:行 | 条目数/行数 | 配置化 | 版本化 |
|---|---|---|---|---|
| `_FRIENDLY_SOURCE_NAMES`（域名→友好名） | task_executor.py:667-723 | ~75 条 | 否（纯字面量） | 否 |
| `_SOURCE_CATEGORY_MAP`（域名→分类） | task_executor.py:749-841 | ~75 条 | 否 | 否 |
| `_PATH_CATEGORY_RULES` + `_TITLE_PATTERNS`（正则分类） | task_executor.py:844-873 | 5+7 条正则 | 否 | 否 |
| `_DIGEST_KEYWORD_EXPANSIONS` + fallback（关键词扩展） | task_executor.py:919-958 | 6 组 + 6 档 | 否 | 否 |
| `_low_value_digest_candidate_reason`（低价值过滤） | task_executor.py:116-239 | ~124 行/十余种场景 | 否 | 否 |
| `OFFICIAL/HIGH/TECH` 域名（评分兜底） | quality.py:38-79 | ~50 条 | 半（API 兜底） | 否 |
| `EXCLUDED_DOMAINS` + 后缀 + 路径（黑名单） | filters.py:13-92 | ~45 条 + 22 路径对 | 否 | 否 |
| `SEARCH_ENGINES` 选择器表 | search.py:82-115 | 4 引擎 | 否 | 选择器有 `selector_version` |
| `ENGINE_PRIORITY`（降级链） | search.py:117 + strategy.py:17（**重复**） | 4 引擎顺序 | 否 | 否 |
| `_SERP_ROOT_DOMAINS` | page_classifier.py:28-35 | ~11 条 | 否 | 否 |

**合计**：约 5 个文件、10 套规则集、~400+ 行硬编码规则，全部无版本化、仅 source_authority 评分部分配置化。

### Top 风险（本模块最该先看的 ≤3 条）

1. **C12-02 五套域名表分散无统一数据源** —— 维护成本根源，新增/调整域名需在 4-5 个文件跳转，单人维护下最易遗漏。
2. **C12-05 硬编码规则无可运营入口** —— 与 source_authority 已有的动态化能力割裂，规则变更需改代码重启，违背项目"配置 DB 化"方向。
3. **C12-03 低价值过滤与 filters.py 黑名单重叠** —— softonic.com 双过滤违反 `_low_value` 函数注释承诺，规则边界契约缺失。

### 修复优先级建议

- **立即**（P0/P1）：无。本模块无阻断或高危问题。
- **计划**（P2）：
  - C12-02 域名表统一（建议结合 X02-13 的 source_authority 管理端一起做，建立 `domain_metadata` 主数据表）
  - C12-05 规则配置化（分阶段，先外置 JSON，再接 DB）
  - C12-03 低价值过滤与黑名单分层契约梳理
  - C12-01 ENGINE_PRIORITY 抽取为共享常量（独立小改动，可先做）
- **择机**（P3/P4）：
  - C12-04 规则版本化（配合配置化一起推进）
  - C12-06 规则回归测试语料库

### 排查盲区 / 待复核

- **[需查证]** `quality.py` 的 `OFFICIAL_DOMAINS`/`HIGH_QUALITY_COMMUNITIES`/`TECH_BLOGS` 与 PG `source_authority` 种子的完整差异集（哪些域名只在 Python、哪些只在 PG）未逐一比对——X02-06 已部分记录，但完整 diff 需脚本化核对（本轮只读约束下未执行）。
- **[需查证]** `_DIGEST_KEYWORD_EXPANSIONS`（task_executor.py:919-949）的 6 组扩展关键词是否与 Java 侧 `digest_section` 表的配置存在语义重叠或冲突，未交叉核对（需读 Java 订阅源相关代码，超出本模块范围）。
- **[需查证]** `ENGINE_PRIORITY` 抽取为共享常量后是否会在 `strategy.py` ↔ `search.py` 间引入循环导入——需运行时验证（本轮约束下未跑）。
- 排查未覆盖 `optimization/feedback.py`、`optimization/bubble_breaker.py` 中可能存在的第二套规则硬编码（归 C06/C07），本模块只确认了 strategy.py 的 ENGINE_PRIORITY 重复。
