# C08 质量与去重 排查报告

> **模块编号**：C08
> **排查范围**：来源可信度（SourceAuthority）、内容质量（ContentQuality 5 维）、三层去重（URL/SimHash 分桶/标题相似度）、页面分类、搜索规划/排序/反馈
> **基线 commit**：`6ae930098405f4d0553d96a852f3345d0f39682e`
> **工作区状态**：脏。涉及本模块的未提交改动：`crawler-service/crawler/search.py`（M）。其余脏文件（ConfigRepositoryImpl.java、WebCollectPageMapper.java、knowledge_base.py、tests/*、deploy/README.md、risk-register.md、release-gate.ps1）与本模块无直接关联。
> **排查日期**：2026-06-24
> **排查人**：crawler 排查 agent（C08）
> **状态**：待复核

---

## 模块概览

**职责**：为采集/日报链路提供"采集前规划 → 候选打分 → 内容质量评分 → 三层去重 → 非文章页面预过滤"的质量闸门，决定哪些 URL/内容进入 AI 整理环节。

**关键文件**：
- `crawler-service/crawler/dedup.py:160-218` —— `ContentFingerprint` SimHash 计算（**B09-02 simhash 溢出源头**）+ 三层 `DedupEngine`
- `crawler-service/crawler/dedup.py:75-157` —— 事件级软分组（`group_event_candidates` / `summarize_event_groups`）
- `crawler-service/crawler/quality.py:27-178` —— `SourceAuthority` Java API 缓存预热 + 硬编码兜底
- `crawler-service/crawler/quality.py:200-431` —— `ContentQuality` 5 维评分 + 时效性
- `crawler-service/crawler/page_classifier.py:1-388` —— SERP/listing/login/error/paywall/forum 分类
- `crawler-service/crawler/search_planner.py:1-179` —— 查询变体 + 引擎选择
- `crawler-service/crawler/search_ranker.py:1-166` —— 确定性打分（关键词重叠 + 板块域名 boost）
- `crawler-service/crawler/search_feedback.py:1-265` —— 历史诊断快照 → planner 提示

**对外接口 / 依赖**：
- 对外（被调用）：`DedupEngine`、`dedup_results`、`merge_results_into`、`ContentFingerprint`、`evaluate_content`、`filter_results`、`classify_page`、`build_search_query_plan`、`rank_search_candidates`、`build_search_feedback_snapshot`、`derive_search_feedback_hints`、`SourceAuthority.preload_authority_cache`
- 依赖（消费）：
  - Java API（`InternalCallbackController`）：`/api/internal/collector/source-authority/all`、`/digest/fingerprints`（GET/POST）
  - 配置 key：`java_api_url`、`callback_api_key`、`sources_api_timeout`、`quality_*`、`content_dedup_*`、`filter_skip_header_chars`、`filter_content_preview_length`、`digest_section_result_multiplier`、`eval_pass_threshold`、`eval_review_threshold`
  - DB 表（经 Java）：`source_authority`、`digest_fingerprint`（`simhash BIGINT` signed）
  - 模块内：`crawler.utils.normalize_url`、`crawler.utils.count_words`、`crawler.filters.is_excluded_domain`、`crawler.search.get_selector_health`、`crawler.digest_orchestrator.PlannedSection`、`crawler.source_agent.SourceCrawlPlan`

**已读文件清单**：
- `crawler-service/crawler/dedup.py` —— 通读
- `crawler-service/crawler/quality.py` —— 通读
- `crawler-service/crawler/page_classifier.py` —— 通读
- `crawler-service/crawler/search_planner.py` —— 通读
- `crawler-service/crawler/search_ranker.py` —— 通读
- `crawler-service/crawler/search_feedback.py` —— 通读
- `crawler-service/crawler/digest.py:1-130` —— 通读（simhash 持久化/回读链路）
- `crawler-service/standalone/task_executor.py:1-490` —— 通读（去重引擎接入点 + SourceAuthority 预热）
- `crawler-service/crawler/filters.py:125-165` —— 片段（`is_excluded_domain`）
- `crawler-service/standalone/backend_config.py:40-100` —— 片段（`java_api_url` 逻辑）
- `crawler-service/config.py` —— grep（质量阈值默认值）
- `backend/.../InternalCallbackController.java:188-281` —— 片段（指纹存取 + SourceAuthority 端点）
- `backend/.../DigestFingerprint.java` —— 通读（`Long simhash`）
- `backend/.../SourceAuthority.java` —— 通读
- schema 三轨 `init.sql` / `schema.sql` / `V1_17__create_digest_fingerprint.sql` —— grep（`simhash BIGINT`）
- `crawler-service/tests/test_dedup.py` —— grep（simhash 测试覆盖）
- `crawler-service/requirements.txt` —— 通读

**主模块归属**：
- **深查**：本模块是 **SimHash 产生与去重引擎** 的主模块（B09-02 simhash 溢出在 Python 端的源头确认由本报告负责）。
- **只引用**：
  - PG schema / Flyway 双轨 → 主模块 B15/X02（本报告只确认 `simhash BIGINT` 字段类型）
  - InternalCallback 端点契约 → 主模块 B09（本报告只确认字段类型不对齐）
  - 硬编码规则大表（`is_excluded_domain`、`task_executor._low_value_digest_candidate_reason`）→ 主模块 C12

---

## `[Bug]` 代码正确性与潜在缺陷

> 排查范围：dedup.py SimHash 计算/分桶/hamming、quality.py 评分维度与阈值、page_classifier 多信号累加、search_planner/ranker/feedback 数据流。逐项检查边界条件、空值、跨语言类型、缓存一致性。

### [P1] [Bug] SimHash 产生为无符号 64 位整数，写入 Java signed Long/BIGINT 时 >2^63-1 溢出   <!-- 编号：C08-01 -->
- **定位**：`crawler-service/crawler/dedup.py:182-218`（`_compute_simhash`），消费链路 `crawler-service/crawler/digest.py:68-118`（`save_digest_fingerprints` POST 到 Java），Java 端 `backend/.../InternalCallbackController.java:227`（`fp.setSimhash(m.get("simhash") instanceof Number n ? n.longValue() : null)`），落库 `backend/.../DigestFingerprint.java:22`（`private Long simhash`），schema `V1_17__create_digest_fingerprint.sql:8` / `init.sql:857` / `schema.sql:1108`（`simhash BIGINT`，PG BIGINT = signed 8 字节，范围 -2^63 ~ 2^63-1）
- **现象**：
  1. Python `_compute_simhash` 通过 `result |= (1 << i)` 对 i=0..63 置位，返回值范围是 **0 ~ 2^64-1**（无符号 64 位）。最高位（bit 63）有 50% 概率为 1，此时数值 ∈ [2^63, 2^64-1]。
  2. `digest.py:95` 把这个值原样塞进 JSON `"simhash": simhash_val`。
  3. Java 端 `n.longValue()`：当 JSON 数字 > 2^63-1 时，Jackson 先解析成 `Long` 或 `BigInteger`，再 `longValue()` 截断/解释为 signed，得到**负数**。
  4. 负数写入 PG `BIGINT`（signed）语义上合法，但语义已"反转"——Python 写出的无符号值与库里的有符号值不再是同一个数学值。
- **影响**：
  - **跨日去重失效**：`build_digest_history_engine`（`digest.py:40-43`）从 Java 回读 `simhash`，拿回的是 signed 负值；`int(simhash_val)` 得负数，传入 `add_precomputed_simhash`。`hamming_distance`（`dedup.py:254-256`）用 `hash1 ^ hash2`：当历史指纹为负、当日新算为正时，XOR 的位模式与"两个同符号原值"完全不同，**汉明距离被放大到接近 64，远超阈值 5**，跨日近重复内容无法被识别。
  - **分桶索引错位**：`_extract_bucket`（`dedup.py:386-390`）对负数做 `(hash_val >> shift) & mask`，Python 对负数 `>>` 是**算术右移**（高位补 1），导致每个桶的高位被污染，`& mask` 后虽然仍落在 0..65535，但分桶键与无符号原值不一致，**预计算的负 simhash 与当日新算的正 simhash 几乎不会落入同一桶**，候选集合退化为全量扫描兜底（`dedup.py:384`），性能与正确性双损。
  - 概率：单条指纹 bit 63 = 1 的概率 50%；一批指纹中至少一条溢出概率随数量上升。日报每次产出几十条指纹，**几乎每次都有部分指纹受影响**。
- **根因/分析**：Python `int` 无限精度，`1 << 63` 是正数 2^63；Java `long` / PG `BIGINT` 是 signed，2^63 是 `Long.MIN_VALUE`。两语言对"第 63 位"的语义解释不同，未做 mask 归一化。已排除误判：①这不是 Jackson 配置问题，`n.longValue()` 对超范围数字必然截断；②这不是 PG 问题，BIGINT 本就是 signed，是 Python 端产生值时未考虑下游 signed 约束。
- **修复方向**（不写代码，标改动面）：
  1. **产生端归一化**（首选，改动面 小）：`_compute_simhash` 返回前 `return result & ((1 << 64) - 1)` 不够（仍是 0..2^64-1），应改为把 bit 63 视为符号位转 signed：`result = result - (1 << 64) if result >= (1 << 63) else result`，使 Python 输出与 Java signed Long 语义一致。同时所有回读处 `int(simhash_val)` 自然兼容（负数在 Python XOR 中只要双方都按 signed 解释，`bin(xor).count('1')` 仍正确——Python 的 `bin(负数)` 返回带符号的 `'0b..'`？**需验证**：实际上 Python `bin(-1)` = `'-0b1'`，`count('1')` 会出错，故 `hamming_distance` 还需 `xor & ((1<<64)-1)` 再 count）。
  2. **比较端容错**（改动面 小）：`hamming_distance` 改为 `bin((hash1 ^ hash2) & ((1 << 64) - 1)).count('1')`，`_extract_bucket` 先 `hash_val &= (1 << 64) - 1`。这样无论上游是 signed 还是 unsigned 都正确。
  3. 建议 1+2 同时做，产生端归一化保证落库值数学正确，比较端容错防御历史脏数据。
- **关联**：**B09-02（本模块确认源头）**；次维度 `[Security]`（数据完整性）；横向主题"跨服务契约一致性"（§2.6）；schema 主模块 B15/X02。测试缺口：`test_dedup.py` 无 simhash > 2^63-1 用例（`C08-09`）。

### [P2] [Bug] `hamming_distance` 对负数输入返回错误结果（C08-01 的直接下游症状）   <!-- 编号：C08-02 -->
- **定位**：`crawler-service/crawler/dedup.py:254-256`
- **现象**：`bin(hash1 ^ hash2).count('1')`。当 `hash1`/`hash2` 任一为负（回读自 Java signed BIGINT），Python `bin(负数)` 返回 `'-0b...'` 形式，`count('1')` 统计的是符号位扩展后的无限个 1 的截断表示，**结果不等于真实汉明距离**。
- **影响**：跨日去重比较历史指纹（负）与当日指纹（正）时，距离值不可预测——可能虚高（误判为不重复，漏去重）也可能异常（理论上 Python `bin` 对负数的行为会让 count 偏大）。与 C08-01 叠加，跨日 SimHash 层基本失效。
- **根因/分析**：未对 XOR 结果做无符号掩码。Python 整数无限精度，与 Java/PG 的固定 64 位语义错配。
- **修复方向**：`bin((hash1 ^ hash2) & ((1 << 64) - 1)).count('1')`（改动面 小）。独立于 C08-01 修复产生端也建议加此防御。
- **关联**：C08-01；横向"跨服务契约一致性"。

### [P2] [Bug] `ContentFingerprint` 特征提取在短/纯中文文本上可能返回空，simhash 退化为 0 被跳过   <!-- 编号：C08-03 -->
- **定位**：`crawler-service/crawler/dedup.py:220-251`（`_extract_features`）、`dedup.py:192-194`（`if not features: return 0`）、`dedup.py:364`（`if hash_val == 0: return` 不入桶）
- **现象**：
  1. 中文 3-gram 要求 `len(segment) >= 3` 才切，2 字符中文片段只保留整体（`elif segment`）。英文 2-gram 要求 `len(words) >= 2`。若内容是"短英文单词 + 少量中文"且都不满足条件，`features` 可能为空，simhash 返回 0。
  2. simhash=0 在 `_add_fingerprint`（`dedup.py:364`）和 `_get_simhash_candidates`（`dedup.py:375`）被显式跳过/触发全量扫描。
- **影响**：日报场景中"一句话新闻 + 链接"类短内容（实际 ≥100 字符门槛已过滤一部分，但长摘要短正文仍可能命中）simhash=0，无法参与 Layer 2 去重，退化为仅 URL + 标题层。漏去重概率上升。
- **根因/分析**：特征提取对极短文本鲁棒性不足。`test_simhash_single_word_no_bigram_nonzero`（`test_dedup.py:59-65`）显示单词会保留自身，但那是英文；纯 2 字符中文标题无测试覆盖。`[需查证]`：实际日报内容是否频繁触发此路径（取决于 AI 整理后正文长度）。
- **修复方向**：①对空 features 回退到字符级 1-gram 或整段 hash；②simhash=0 时改为用 exact_hash 入指纹库参与精确去重（改动面 中）。
- **关联**：次维度 `[Design]`（去重召回率）。

### [P2] [Bug] `group_event_candidates` 事件分组首次匹配即 break，可能把不同事件归到一组   <!-- 编号：C08-04 -->
- **定位**：`crawler-service/crawler/dedup.py:75-110`
- **现象**：内层循环 `for group in groups`，只要 token 交集 `>= min(2, len(tokens), len(group_tokens))` 就 `matched = group; break`，取**第一个**匹配组而非最优匹配组。`event_tokens` 匹配后又用并集扩张（`dedup.py:103`），后续候选更容易匹配到这个不断膨胀的组。
- **影响**：当多个真实事件共享 2 个以上常见技术词（如 "python release" + "java release" 都含 release/openai 等被 stopwords 漏过滤的词），会被错误合并为一组，影响 `summarize_event_groups` 的 `duplicate_event_count` / `source_diversity` 诊断指标，误导 search_feedback。
- **根因/分析**：贪心首次匹配 + 单边 token 扩张。`EVENT_STOPWORDS`（`dedup.py:18-22`）列表较短，未覆盖 release/update/feature 的所有变形（已有 releases/released 但缺 releasing）。`[需查证]`：实际诊断输出是否明显偏离。
- **修复方向**：①改为取 Jaccard 最高的组；②扩张 event_tokens 时用带权重或限长，防止无限膨胀（改动面 中）。
- **关联**：次维度 `[Design]`（诊断准确性）。

### [P3] [Bug] `ContentQuality` 广告/标题党关键词正则在空列表时 `_build_combined_pattern` 返回 None，但 `findall` 已防御，评分维度静默失效   <!-- 编号：C08-05 -->
- **定位**：`crawler-service/crawler/quality.py:190-195`、`quality.py:325-329`（广告）、`quality.py:346-351`（标题党）
- **现象**：若运维把 `quality_ad_keywords` 配成空字符串，`_cached_ad_re = None`，`ad_count = 0`，`dimensions['ad_ratio'] = 25`（满分），`ad_penalty = 0`。文章无任何广告惩罚，质量分虚高。标题党维度同理。
- **影响**：配置错误（空关键词）时质量闸门静默退化为"不检测广告/标题党"，劣质内容可能通过。无日志告警。
- **根因/分析**：空列表视为"不检测"是合理默认，但缺少"配置被清空"的可观测性。
- **修复方向**：配置为空时 warn 日志一次；或在 settings 加载时校验非空（改动面 小）。
- **关联**：配置项 `quality_ad_keywords` / `quality_clickbait_keywords`。

### [P3] [Bug] `page_classifier` 各检测函数阈值固定为 5，但 `_detect_paywall` 累加无上限，单页可能远超 5 导致置信度计算 `score/8` 截顶到 0.95 失真   <!-- 编号：C08-06 -->
- **定位**：`crawler-service/crawler/page_classifier.py:149-176`（阈值 5 判定）、`page_classifier.py:367-387`（paywall 累加，注释说"最多计 3 个"但代码无此限制）
- **现象**：`_detect_paywall` 注释 `dedup.py:386` 写"截断：最多计 3 个内容信号，避免计分过高"，但**实际代码没有截断**，`for pat in _PAYWALL_CONTENT_PATTERNS` 每个 +2 无上限，11 个模式全命中 score=22+。置信度 `min(22/8, 0.95) = 0.95` 虽然被夹住，但 score 本身被 `is_non_article` 判断时只要 ≥5 就分类，paywall 误判范围比注释宣称的更宽。
- **影响**：含多个"会员/订阅/付费"关键词组合的正常文章（如讨论 SaaS 定价的 tech 文章）可能被误判为 paywall 页直接过滤。注释与代码不符是维护隐患。
- **根因/分析**：注释承诺的截断未实现。`[需查证]`：实际误判率（需跑分类测试集，本审计命令边界禁 pytest）。
- **修复方向**：实现注释承诺的 `score = min(score, 截断值)`，或删除误导注释（改动面 小）。
- **关联**：次维度 `[Design]`（分类误判率）。

### [P3] [Bug] `search_ranker.rank_search_candidates` 排序键对 dict 与对象混合判断，非 dict 项的 metadata 取值在 sort lambda 内重复求值   <!-- 编号：C08-07 -->
- **定位**：`crawler-service/crawler/search_ranker.py:158-165`
- **现象**：排序 `key=lambda pair: (-pair[0]["metadata"]["relevance_score"] if isinstance(pair[0], dict) else -pair[0].metadata.get(...), pair[1])`。每个元素每次比较都做 `isinstance` + 属性访问，且 lambda 在 Python sort 中可能被调用 O(n log n) 次。虽然 `_with_metadata` 已确保 metadata 存在，逻辑正确，但性能与可读性差。
- **影响**：候选量大时（单板块几十到上百）轻微性能损失；可读性差，后续维护易引入 bug。
- **根因/分析**：未提前计算排序键（Schwartzian transform 不彻底）。
- **修复方向**：构造 `(score, index, item)` 元组列表排序后取 item（改动面 小）。
- **关联**：次维度 `[Performance]`。

---

## `[Security]` 安全漏洞

> 排查范围：逐项覆盖 §2.2 重点。本模块不直接处理鉴权/Cookie/SQL/AES/文件上传，主要关注：跨服务 key 传输、SSRF（SourceAuthority 拉取 Java API）、配置注入（关键词正则）、信息泄露（诊断快照）。

### 未发现 P0/P1 安全漏洞

**已检查项**：
- **跨服务双向 key**（§2.2）：`SourceAuthority.preload_authority_cache`（`quality.py:155-158`）、`build_digest_history_engine`（`digest.py:28-29`）、`save_digest_fingerprints`（`digest.py:105-106`）三处调用 Java API 都带 `X-Callback-Key` header，key 来源 `settings.callback_api_key`。Java 端 `authRequired(callbackKey, false)` 校验（`InternalCallbackController.java:248,272`）。key 未在日志明文打印（`task_executor._fire_callback` 有 `maskKey` 但那是另一处）。**未发现 key 泄露**。
- **SSRF**（§2.2）：`SourceAuthority` 请求目标 URL 来自 `settings.java_api_url`（配置项，非用户输入），路径硬编码拼接，不接受用户可控 URL 参数。**不存在 SSRF**。
- **配置注入**：`quality_clickbait_keywords` 等被 `re.escape` 后拼接成正则（`quality.py:190-195`），防注入。但若关键词含特殊构造，`|`.join 后的正则在极端输入下可能 ReDoS——`[需查证]` 实际配置值均为简单中文词组，风险低。
- **信息泄露**：`search_feedback` 快照包含 query 字符串、domain 列表，均为公开技术内容，无敏感信息。

### [P3] [Security] SourceAuthority Java API 失败时静默降级，缓存为空无显式告警   <!-- 编号：C08-08 -->
- **定位**：`crawler-service/crawler/quality.py:143-178`（`preload_authority_cache`）、`quality.py:123-141`（`_query_from_cache`）
- **现象**：`preload_authority_cache` 的 `except Exception` 仅 `logger.debug`（`quality.py:178`），失败后 `_api_cache` 为空，`_query_from_cache` 走 `else` 分支 `logger.debug` 提示"preload 未调用"。实际是被调用了但失败了，日志误导。后续所有 `score()` 走硬编码兜底，**运维无法从 INFO/WARN 日志感知 Java API 持续不可用**。
- **影响**：Java 端 `source_authority` 表的运营配置（管理员手动调整的域名评分）静默失效，日报质量评分基于过期硬编码列表，运营动作无效果且无告警。
- **根因/分析**：异常吞掉仅 debug 级别；缓存空与缓存失败的日志分支混淆。
- **修复方向**：preload 失败用 `logger.warning`；区分"未调用"与"调用失败"两种缓存空状态（改动面 小）。
- **关联**：次维度 `[Design]`（可运维性）；配置项 `java_api_url`；主模块 B09（Java 端点）。

---

## `[Arch]` 架构与技术债

> 排查范围：分层、耦合、硬编码、重复实现、隐式约定。共享对象按 §8.6 归属，本节只记本模块独有或本模块视角。

### [P2] [Arch] SourceAuthority 存在双源漂移（硬编码 Python 列表 vs Java DB 表），引用 X02-06   <!-- 编号：C08-09 -->
- **定位**：`crawler-service/crawler/quality.py:38-79`（`OFFICIAL_DOMAINS` / `HIGH_QUALITY_COMMUNITIES` / `TECH_BLOGS` 硬编码，约 60 个域名）；Java 端 `source_authority` 表种子见 `init.sql:882` / `schema.sql:1133`（`INSERT INTO source_authority ...`）
- **现象**：Python 硬编码权威域名评分（95/80/60/5/50），Java DB 表有独立种子数据与运营录入。`score()` 优先查缓存（来自 Java），miss 时走 Python 硬编码。**两套列表无同步机制**：管理员在 Java 端新增域名后，若 `preload_authority_cache` 失败或缓存过期窗口内，Python 用硬编码给出与 DB 不一致的评分。
- **影响**：评分口径漂移，同域名在不同时段/不同实例评分不同，质量趋势统计不可比。属配置一致性主题（X06）的 crawler 侧表现。
- **根因/分析**：双源设计本意是"DB 优先 + 硬编码兜底"，但缺少"硬编码应作为 DB 的种子子集"的约束，两套列表各自演进。
- **修复方向**：①把 Python 硬编码列表移到 Java DB 种子，Python 端仅保留极简兜底（"未知=50"）；②或加启动期一致性校验，日志报告差异（改动面 中）。
- **关联**：**X02-06（双源漂移，本模块 crawler 侧证据）**；主模块 X06（配置一致性）；横向"配置一致性"。

### [P3] [Arch] `ContentQuality` 5 维权重隐式（25/25/25/25 + bonus/penalty），日报模式维度替换无文档   <!-- 编号：C08-10 -->
- **定位**：`crawler-service/crawler/quality.py:270-369`
- **现象**：非日报模式 5 维各 25 分（length/structure/code_density/ad_ratio），实际 `base_score = sum(dimensions.values())`（`quality.py:343`）——但 dimensions 在非日报模式下**只有 4 个 key**（length/structure/code_density/ad_ratio），"5 维"是文档说法，代码是 4 维。日报模式把 `code_density` 替换为 `source_authority`（`quality.py:332-341`），仍是 4 维求和。penalty（clickbait/ad）和 bonus（freshness）在总分外加减（`quality.py:368`）。
- **影响**：①文档与代码的"5 维"表述不一致，维护者易误解；②权重切换（日报 vs 非日报）是隐式分支，调整其一易漏改另一；③penalty 可使总分降到 0，bonus 可加到 100+，`max(0, min(100, ...))` 夹断（`quality.py:369`），极端值行为不直观。
- **根因/分析**：维度数与文档措辞漂移；权重硬编码在评分函数体内。
- **修复方向**：①文档/代码统一为"4 维 + 时效 bonus + 标题党/广告 penalty"；②权重提取为配置或常量类（改动面 小）。
- **关联**：次维度 `[Doc]`；配置项 `quality_*_weight`。

### [P3] [Arch] SimHash 测试无溢出用例，回归保护缺失（C08-01 的测试缺口）   <!-- 编号：C08-11 -->
- **定位**：`crawler-service/tests/test_dedup.py`（grep 结果：所有 simhash 测试用例文本均较短，产生的 simhash 数值未覆盖 > 2^63-1 区间）
- **现象**：`test_simhash_stability` / `test_simhash_similar_content_small_distance` 等只验证"同文本同值""相似文本距离小"，无"产生值是否落在 signed Long 范围""hamming_distance 对负数是否正确"用例。
- **影响**：C08-01 这类溢出 bug 无测试拦截，回归风险高。
- **根因/分析**：测试视角局限在 Python 进程内，未覆盖跨语言契约。
- **修复方向**：补"simhash 落在 [−2^63, 2^63-1]"断言 + "负数 hamming_distance"用例（改动面 小）。
- **关联**：C08-01/C08-02；主模块 X03（测试体系）。

---

## `[Deps]` 依赖升级与版本

### 本模块依赖清单（基于声明文件，未翻依赖源码）

| 依赖 | 版本 | 声明位置 | 已知风险/可升级 | 备注 |
|---|---|---|---|---|
| Python 标准库 `hashlib`/`re`/`difflib`/`urllib`/`json` | 内置 | — | — | simhash/分类/相似度核心，无外部依赖 |
| `httpx` | `>=0.26.0` | `crawler-service/requirements.txt:13` | 0.27+ 已发布，可平滑升 | SourceAuthority 预热、指纹存取用 |
| 无第三方 NLP/simhash 库 | — | — | — | simhash 为手写简化版（非 `simhash` 库） |

> 排查范围：本模块核心算法仅用标准库，HTTP 用 httpx。未引入 `simhash`/`datasketch`/`spacy` 等。未发现 P0–P3 依赖问题。

### 未发现 P0–P3 依赖问题

本模块是纯算法 + httpx 调用，依赖面极窄。httpx `>=0.26.0` 下限合理，无已知 CVE 影响本模块用法。`[需查证]`：httpx 0.28 对 AsyncClient 默认 timeout 行为有微调，若升级需回归 SourceAuthority 预热的 `timeout=settings.sources_api_timeout`（默认 5.0s）行为。

---

## `[Design]` 功能设计合理性

> 必填。从真实使用出发，回答 §2.5 中相关问题（至少 2 个）。本模块回答"场景适配""闭环完整性""可运维性""可操纵性"四项。

**审视结论**：

1. **场景适配**（§2.5.1）：单人技术博客 + 每工作日 AI 日报场景下，三层去重（URL/SimHash/标题）+ 事件级软分组 + 5 维质量评分 + 6 类页面分类，**功能密度匹配场景**，不算过度设计。但 SimHash 手写简化版（md5 取前 16 hex = 64 位，2-gram/3-gram 特征）在中文短内容上召回率存疑（C08-03），属"看起来能用实则边界失效"的半成品风险点。
2. **闭环完整性**（§2.5.2）：去重形成"采集 → 指纹落 Java DB → 次日回读跨日去重"闭环，**但 C08-01 溢出导致闭环在 SimHash 层断裂**，跨日近重复识别实际仅靠 URL 层兜底。search_feedback 形成"诊断快照 → planner hints → 引擎/intent 惩罚"闭环，**但 hint 时效性依赖上次日报成功落库**，若日报连续失败（C04 global timeout 不写 KB 的同类问题），hint 停滞在过期快照。
3. **可运维性**（§2.5.3）：`summarize_event_groups` / `build_search_feedback_snapshot` 提供了诊断数据，**但 SourceAuthority 降级静默（C08-08）和 SimHash 溢出（C08-01）都无显式告警**，运维只能从"跨日去重效果变差"间接感知，定位困难。缺少"去重命中率""SimHash 溢出计数"等运营指标。
4. **可操纵性/SEO 操纵**（§2.5 单点扩展）：`search_ranker` 的板块域名 boost（`SECTION_DOMAIN_BOOSTS`，`search_ranker.py:10-25`）是硬编码白名单，**不可被外部 SEO 操纵**（攻击者无法让自己进入 boost 集合）。但反向——白名单外的高质量新站点（如新兴 AI 公司博客）会被相对压低，需运营手动加表，更新滞后。

### [P4] [Design] 质量评分"5 维"实为 4 维 + 时效 bonus，文档与代码措辞需统一   <!-- 编号：C08-12 -->
- **定位**：`crawler-service/crawler/quality.py:242-266`（docstring 写 "dimensions" 含 5 key，实际代码 4 key）、模块 docstring `quality.py:1-9`
- **现象**：见 C08-10。
- **影响**：维护者认知偏差，调参时易漏维度。
- **建议方向**：统一文档为"4 维（length/structure/code_density|source_authority/ad_ratio）+ freshness bonus + clickbait/ad penalty"，或真正引入第 5 维（改动面 小）。
- **关联**：C08-10。

### [P4] [Design] 建议补"SimHash 溢出率""跨日去重命中率"运营指标   <!-- 编号：C08-13 -->
- **定位**：`crawler-service/crawler/dedup.py`（DedupEngine 无统计输出）、`crawler-service/crawler/digest.py:68-118`（save_digest_fingerprints 无溢出计数）
- **现象**：当前 DedupEngine 不暴露"本次去重命中 URL/SimHash/标题各多少""simhash 产生多少个 >2^63-1"。诊断快照（search_feedback）只覆盖搜索阶段，不覆盖去重阶段。
- **影响**：C08-01 这类问题不可观测，趋势统计偏"顺利完成的"（关联 §9 已知线索 C04/C07 同类症状）。
- **建议方向**：DedupEngine 增加 counters，日报完成后写入 task metadata 的 diagnostics（改动面 中）。
- **关联**：C08-01；§9 [Bug/P2] 日报 global timeout 后 KB 不写入（同类可观测性缺口）。

---

## 模块小结

### 严重度统计

| 级别 | 数量 | 条目编号 |
|---|---|---|
| P0 | 0 | — |
| P1 | 1 | C08-01 |
| P2 | 5 | C08-02, C08-03, C08-04, C08-09, C08-11(归 P2 测试缺口) |
| P3 | 5 | C08-05, C08-06, C08-07, C08-08, C08-10, C08-11 |
| P4 | 2 | C08-12, C08-13 |

> 注：C08-11 同时是测试缺口（P3/P2 边界），上表 P2/P3 双计，严格计数 P2=4、P3=5。

### Top 风险（本模块最该先看的 3 条）

1. **C08-01 SimHash 无符号 64 位溢出** —— **B09-02 在本模块的源头确认**。Python `_compute_simhash` 产生 [0, 2^64-1]，Java `Long`/PG `BIGINT` signed，>2^63-1 时 `longValue()` 截断为负，导致跨日 SimHash 去重 + 分桶索引双失效。修复需产生端归一化 + 比较端掩码双管齐下。改动面 小但影响面大（跨日去重核心链路）。
2. **C08-02 hamming_distance 负数错误** —— C08-01 的直接下游症状，独立修复（加 `& ((1<<64)-1)` 掩码）即可让比较端防御历史脏数据。
3. **C08-09 SourceAuthority 双源漂移** —— Python 硬编码 vs Java DB 表无同步，引用 X02-06，运营配置静默失效。

### 修复优先级建议

- **立即**（P1）：C08-01（simhash 产生端归一化 + hamming 掩码 + 分桶掩码，三处一并改），同时补 C08-11 溢出测试用例锁回归。
- **计划**（P2）：C08-02（若 C08-01 已做比较端掩码则包含）、C08-03（短文本特征回退）、C08-04（事件分组取最优匹配）、C08-09（双源一致性校验）。
- **择机**（P3/P4）：C08-05/06/07/08/10/12/13（可观测性、注释修正、权重文档统一）。

### 排查盲区 / 待复核

- **C08-03**：实际日报内容中 simhash=0 的触发频率 `[需查证]`（需跑分类测试集，命令边界禁 pytest，留给后续验证）。
- **C08-04**：`group_event_candidates` 误合并率 `[需查证]`（需对比 `summarize_event_groups` 输出与人工标注）。
- **C08-06**：paywall 误判率 `[需查证]`（注释承诺截断未实现，实际影响需测试集）。
- **C08-01 hamming 负数行为细节**：Python `bin(负数).count('1')` 的精确返回值 `[需查证]`（CPython 实现细节，本环境无法运行验证；但数学上 XOR 后掩码是确定正确的修复）。
- **未覆盖**：`crawler/search.py`（本模块工作区有改动，但 search 引擎本体属 C03 模块；本报告只看 search_planner/ranker/feedback 三件套，未深查 search.py 改动影响）。
