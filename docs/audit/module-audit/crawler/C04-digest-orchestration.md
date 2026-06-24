# C04 日报生成编排 排查报告

> **模块编号**：C04
> **排查范围**：DigestOrchestrator 4 阶段编排（Phase 0-4）、板块配置、触发与防重入、核心板块补救、global timeout、事件合并、发布门控引用
> **基线 commit**：`6ae930098405f4d0553d96a852f3345d0f39682e`
> **工作区状态**：脏（未提交改动涉及 `backend/.../ConfigRepositoryImpl.java`、`WebCollectPageMapper.java`、`crawler-service/crawler/search.py`、`optimization/knowledge_base.py`、多个 tests、`deploy/README.md`、`docs/audit/full-project-risk-register.md`、`scripts/release/release-gate.ps1`，及新增 `backend/src/test/.../webcollector/`）。**本 C04 模块核心文件（digest_orchestrator.py / digest_gen_agent.py / digest_events.py / digest_quality_gate.py）均未在未提交清单中**，结论对 HEAD 成立。
> **排查日期**：2026-06-23
> **排查人**：crawler 排查 agent（C04）
> **状态**：待复核

---

## 模块概览

**职责**：把"无脑全爬→事后优化"升级为事前规划→并行爬取→板块感知优化→AI 生成→质量评估回写 KB 的完整日报闭环，是 crawler-service 日报生成的总入口与编排核心。

**关键文件**：
- `crawler-service/crawler/digest_orchestrator.py:300` —— `DigestOrchestrator` 主类，Phase 0-4 编排（1256 行）
- `crawler-service/crawler/digest_orchestrator.py:120` —— `_calculate_digest_output_quality` 日报成品质量评分（被 publish gate 复用）
- `crawler-service/crawler/digest_gen_agent.py:56` —— `DigestGenAgent`，SectionDocument → DigestPageContent → AI 生成
- `crawler-service/crawler/digest_gen_agent.py:564` —— `_supplement_digest_coverage` 稀薄日报补充逻辑
- `crawler-service/crawler/digest_events.py:46` —— `build_digest_event_candidates` + `merge_digest_event_pages` 事件合并
- `crawler-service/standalone/digest_quality_gate.py:25` —— `evaluate_digest_publish_quality` 发布门控
- `crawler-service/standalone/task_executor.py:358-395` —— digest 任务类型入口、orchestrator 结果落库
- `crawler-service/standalone/task_executor.py:984` —— `get_digest_sections` 板块配置缓存（Java API → 本地 JSON 回退）
- `crawler-service/standalone/scheduler.py:74` —— `generate_scheduled_digest` 触发入口 + `_digest_lock` 防重入
- `crawler-service/standalone/repository.py:196` —— `get_digest_existing_non_failed` 防重复查询

**对外接口 / 依赖**：
- 对外：`DigestOrchestrator.execute()`（被 TaskExecutor 调用）、`get_plan()/get_section_documents()/get_digest_result()`（结果回传）
- 依赖：C03（CrawlerAgent/SourceAgent/搜索引擎降级）、C05（ContentOrganizer.generate_digest）、C06（CoverageEvaluator/质量评分）、C07（KnowledgeBase 弱点/趋势/源动作回写）、C09（repository/save_digest_fingerprints）、C10（scheduler 触发）、C11（settings 配置）
- 配置 key：`digest_global_timeout`(600s)、`digest_parallel_sections`(2)、`digest_search_engine`、`digest_optimization_*`、`digest_publish_core_sections`、`digest_publish_min_core_sections`、`optimization_total_budget_seconds`

**已读文件清单**（可追溯 + 暴露盲区）：
- `crawler-service/crawler/digest_orchestrator.py` —— 通读（1256 行）
- `crawler-service/crawler/digest_gen_agent.py` —— 通读（718 行）
- `crawler-service/crawler/digest_events.py` —— 通读（222 行）
- `crawler-service/standalone/digest_quality_gate.py` —— 通读（95 行）
- `crawler-service/standalone/task_executor.py` —— 片段（digest 入口 330-530、板块配置 955-1190）
- `crawler-service/standalone/scheduler.py` —— 片段（generate_scheduled_digest 72-112）
- `crawler-service/standalone/repository.py` —— 片段（digest 防重查询 164-262）
- `crawler-service/config.py` —— 片段（digest 配置 130-203）
- `crawler-service/crawler/optimization_agent.py` —— 片段（预算控制 85-285）
- `crawler-service/optimization/knowledge_base.py` —— 片段（digest 评估 87-395）
- `crawler-service/optimization/evaluator.py` —— 片段（权重/overall 37-172）
- `crawler-service/.env.example` —— grep（DIGEST 配置项）
- `crawler-service/tests/test_digest_orchestrator.py` —— grep（timeout/Phase 4 覆盖情况）

**主模块归属**：**C04 是 digest_orchestrator 编排的主模块（计划 §8.6）**，深查。对 OptimizationAgent（C06/C07）、scheduler 触发（C10）、AI 生成（C05）、质量评估（C06）只引用其与本编排相关的边界行为，不展开内部实现。

---

## `[Bug]` 代码正确性与潜在缺陷

> 排查范围：digest_orchestrator.py 全文、digest_gen_agent.py 全文、digest_events.py 全文、digest_quality_gate.py 全文、task_executor.py 的 digest 分支、scheduler 触发与防重入、板块配置链路。

### [P2] [Bug] global timeout 后日报评估数据不进 KB，趋势统计偏向"顺利完成的" <!-- 编号：C04-01 -->
- **定位**：`crawler-service/crawler/digest_orchestrator.py:426-436`（Phase 4 KB 写入被 `_global_timeout_reached` 短路）；配套过滤 `crawler-service/optimization/knowledge_base.py:87-102` `_is_publishable_digest_eval_record`
- **现象**：当 Phase 1 并行爬取触发 `asyncio.TimeoutError`（line 690 置 `_global_timeout_reached=True`）后，Phase 4 显式 `logger.warning("Skipping Phase 4 KB write due to global timeout")` 并跳过 `_evaluate_digest_quality`，整条日报评估记录不会写入 `optimization_record` 表（strategy_type=`digest_final_eval`）。而 `get_digest_quality_trend`/`get_last_digest_weaknesses` 均从该表查询，并用 `_is_publishable_digest_eval_record` 过滤（要求 `task_status=COMPLETED` 且 `digest_publishable != False`）。
- **影响**：①超时日报的质量分/弱点/建议完全不入库，`_build_plan` 读到的"趋势"和"上次弱点"是经过超时事件筛选后的样本，系统性偏向顺利完成的日报，弱维度自愈闭环失效；②单人运维场景下，超时恰恰是最需要被记录诊断的故障，却被静默丢弃；③`optimization_action_outcome`（验证 source feedback 是否有效）也不会构建，KB 无法判断"上一轮 skip/deprioritize 动作是否真的改善了超时场景"。
- **根因/分析**：代码注释写明"避免不完整数据污染知识库推荐"，意图合理；但采取了"全跳过"而非"标记写入+降权"的保守策略。evaluator 对 digest 任务类型走 `_heuristic_evaluate`（纯计算，非 AI，见 evaluator.py:139-140），本身不依赖数据完整性，完全可以在超时场景下产出可用评分。已排除误判：KB 写入本身（save_digest_evaluation）不依赖爬取完整度，依赖的是评估输入；评估输入来自 `self._section_documents`，超时时已有部分 section_documents（orchestrator.py:698 日志确认"may be incomplete"）。
- **修复方向**：①超时日报也写入 KB，但在记录中加 `incomplete=True`/`global_timeout=True` 标记，趋势统计时降权或单独分组（改动面 中）；②或在 `_is_publishable_digest_eval_record` 增加超时分支，让超时记录可见但不主导趋势（改动面 中）。需要 C07 协同（KB 表结构/查询）。
- **关联**：计划 §9 已知线索（C04/C07）、C07（KB 表）、C06（evaluator）、[Design] 闭环完整性

### [P2] [Bug] `digest_coverage_weight` 配置项被读取但从未快照，永远走默认值 0.7 <!-- 编号：C04-02 -->
- **定位**：`crawler-service/crawler/digest_orchestrator.py:1156`（读取 `plan.config_snapshot.get("digest_coverage_weight", 0.7)`）；缺失项：`crawler-service/crawler/digest_orchestrator.py:961-977` `_snapshot_config` 未包含该 key
- **现象**：Phase 4 综合分计算用 `plan.config_snapshot.get("digest_coverage_weight", 0.7)`，但 `_snapshot_config()` 返回的字典里根本没有 `digest_coverage_weight` 这个 key（见 line 963-977 的字典字面量，只有 engine/max_parallel/global_timeout 等约 14 项，无 coverage_weight）。因此该行永远返回 0.7，`coverage_weight` 实际是一个**死配置项**——即便用户在 settings 中配置也无法生效。
- **影响**：用户若想调整"覆盖度 vs 成品质量"权重（例如日报生成稳定后想更看重成品质量），配置无效，行为与预期不符。非阻断，但属于"看起来可配置实则硬编码"的隐性陷阱。
- **根因/分析**：配置项命名与快照逻辑脱节。已排除误判：全仓 grep `digest_coverage_weight` 仅命中 orchestrator.py:1156 一处，config.py 中无定义、`.env.example` 无暴露、`_snapshot_config` 未收录。结论：这是一个引用了不存在配置的 dead config，而非"默认值兜底"。
- **修复方向**：①在 `_snapshot_config` 补 `digest_coverage_weight` 并在 config.py/settings 中声明默认值（改动面 小）；②或删除该配置读取，直接硬编码 0.7 并注释说明（改动面 小）。
- **关联**：配置一致性横向主题（§2.6）、X06

### [P2] [Bug] 板块配置示例与发布门控核心板块不一致，自定义板块会导致门控永远不达标 <!-- 编号：C04-03 -->
- **定位**：板块默认 `crawler-service/config.py:135-141`（5 板块 hot_trend/open_source/dev_tool/tech_article/paper）；示例漂移 `crawler-service/.env.example:136`（注释示例为 news/articles/opensource）；门控默认 `crawler-service/config.py:201` `digest_publish_core_sections="hot_trend,open_source,dev_tool,tech_article,paper"`
- **现象**：①`config.py` 默认板块与 `digest_publish_core_sections` 默认值一致（5 板块完全匹配）；②但 `.env.example` 注释里的示例板块是 `news/articles/opensource`，与核心板块列表完全不重叠；③`get_digest_sections` 优先从 Java API 拉取（task_executor.py:1011 `/api/internal/collector/sources`），按 `contentCategory` 分组生成 section.name（task_executor.py:1126 `"name": cat`）。若用户用 Java 订阅源且 contentCategory 命名不匹配上述 5 个，`_core_section_status`（orchestrator.py:756 解析 `digest_publish_core_sections`）会判定核心板块覆盖 0。
- **影响**：①若用户启用 `.env.example` 示例板块，`evaluate_digest_publish_quality`（digest_quality_gate.py:39）的 `core_section_coverage` 门控永远失败（`min_core_sections` 默认 3，present_core 永远 0），日报永远 publishable=False，task 标记 FAILED；②Java 订阅源的 contentCategory 若不与 config 的 5 板块对齐，同样触发。用户会困惑"板块有内容但日报发不出"。
- **根因/分析**：板块配置是"软约定"（用户可任意命名），但发布门控是"硬列表"（必须精确匹配 5 个 key）。两者没有一致性校验或回退。已排除误判：`_core_section_status` 在 `core_sections` 为空时直接返回跳过（orchestrator.py:757-766），但默认值非空，所以只要用户不改 `digest_publish_core_sections` 就会触发不匹配。
- **修复方向**：①启动时校验 `digest_publish_core_sections` 与实际板块配置有交集，无交集时告警或自动放宽（改动面 中）；②`.env.example` 示例板块改为与默认 5 板块一致（改动面 小）；③文档明确板块命名契约（改动面 小）。
- **关联**：跨服务契约一致性横向主题（§2.6）、C11（配置同步）、B09（Java 订阅源 API 字段）、[Design] 闭环完整性

### [P3] [Bug] Phase 1 global_timeout 后未取消的优化/AI 生成阶段仍会执行，"全局超时"名不副实 <!-- 编号：C04-04 -->
- **定位**：`crawler-service/crawler/digest_orchestrator.py:685-688`（`asyncio.wait_for` 仅包裹 Phase 1 的 section_tasks）；`crawler-service/crawler/digest_orchestrator.py:362-413`（Phase 1.5 OptimizationAgent + Phase 2 DigestGenAgent 不在该超时内）；OptimizationAgent 预算 `crawler-service/crawler/optimization_agent.py:283-285`（取 `optimization_total_budget_seconds` 的 60%，最低 90s）
- **现象**：`digest_global_timeout`（默认 600s）只保护 Phase 1 的并行爬取 `asyncio.gather`。触发后只置标志位，后续 Phase 1.2（rescue，但有 `_global_timeout_reached` 守卫会跳过，见 line 812）、Phase 1.5（OptimizationAgent，有 `_should_run_optimization` 守卫会跳过，见 line 948）、Phase 2（DigestGenAgent，**无守卫**，line 389 仅 warning 后继续）、Phase 3/4 仍会执行。
- **影响**：①Phase 2 的 DigestGenAgent 调用 AI（`generate_digest`）在超时后仍执行，真实墙钟时间 = 600s + AI 生成时间（数十秒到数分钟），运维若按 600s 设告警/超时阈值会误判；②注释（line 388 "超时后仍允许生成日报"）说明这是有意设计，但命名 `digest_global_timeout` 与"全局"语义不符，易误导。
- **根因/分析**：注释表明"不完整数据生成的日报比没有好"是有意决策（line 388），合理。问题在于命名与文档未澄清真实边界。已排除误判：Phase 1.2/1.5 有守卫，Phase 2 无守卫但有意为之。
- **修复方向**：①重命名为 `digest_phase1_crawl_timeout` 或文档明确"仅 Phase 1"边界（改动面 小）；②若要真正全局，给 Phase 2 AI 生成也加超时包装（改动面 中，需评估 AI 调用可中断性）。
- **关联**：[Design] 可运维性、C05（AI 生成超时）

### [P3] [Bug] `_get_weights` 被 import 但未使用，dead import <!-- 编号：C04-05 -->
- **定位**：`crawler-service/crawler/digest_orchestrator.py:1070`（`from optimization.evaluator import CoverageEvaluator, _get_weights`）
- **现象**：导入了 `_get_weights`，但 `_evaluate_digest_quality` 全文（line 1068-1195）未调用它。权重计算已封装在 `CoverageEvaluator.evaluate` 内部（evaluator.py:149）。
- **影响**：无害，但属于死代码，可能误导后续维护者以为权重在此处手动覆盖。
- **根因/分析**：重构遗留。CoverageEvaluator 内部自取权重，编排层无需关心。
- **修复方向**：移除该 import（改动面 小）。
- **关联**：无

### [P3] [Bug] `_build_optimization_action_outcome` 的 target_score 兜底值 0.75 与发布门控 0.65 不一致 <!-- 编号：C04-06 -->
- **定位**：`crawler-service/crawler/digest_orchestrator.py:1031`（`target_score = 0.75` 硬编码兜底）；实际配置 `crawler-service/config.py:200`（`digest_optimization_target_score = 0.65`）
- **现象**：`_build_optimization_action_outcome` 读取 `plan.config_snapshot.get("digest_optimization_target_score", ...)`，正常路径取 settings 值 0.65；但 `except` 分支兜底硬编码 0.75（line 1039-1040）。verdict 判定（positive/needs_review/negative）依赖该值。
- **影响**：仅在配置读取异常（极低概率）时触发，verdict 阈值偏移 0.1，可能导致 source feedback 动作被误判为 positive/negative。非阻断。
- **根因/分析**：兜底值应与 config 默认一致。已排除误判：try 块内正常取值路径正确，仅 except 兜底偏差。
- **修复方向**：兜底改为 0.65（与 config 默认对齐）（改动面 小）。
- **关联**：配置一致性横向主题（§2.6）

### [P4] [Bug] pre_generated 路径与 organize_with_ai 回退路径的双重质量门控阈值相同但 stage 标记不同 <!-- 编号：C04-07 -->
- **定位**：`crawler-service/standalone/digest_post_processor.py:62`（pre_generated 路径，stage=`pre_generated`）；`crawler-service/standalone/organizer_helper.py:306`（fallback 路径，stage 待确认）
- **现象**：当 orchestrator 预生成日报存在但被门控拒绝（publishable=False）时，task_executor.py:464 会 fallback 到 `organize_with_ai`，后者**重新**调用 AI 生成并再次过门控。两次门控用同一 threshold（`digest_optimization_target_score` 0.65），但输入不同（pre_generated 用 section_documents，fallback 用 DB pages）。
- **影响**：fallback 成功率取决于 AI 是否能从相同原始数据产出更优结果，存在概率性浪费 token 的风险。非 bug，但属于设计上的重复评估。
- **根因/分析**：pre_generated 拒绝通常意味着源数据覆盖不足（core_section_coverage 失败），fallback 重新生成大概率仍失败。但 fallback 路径输入是 raw pages（含低质量过滤后剩余），与 section_documents（已清洗）不同，理论上有差异。
- **修复方向**：①门控失败时根据失败原因决定是否 fallback（如仅 score 低可 fallback，core_section 失败直接放弃）（改动面 中）；②保持现状但记录 fallback 成功率到 KB 供分析（改动面 小）。
- **关联**：[Design] 闭环完整性、C05

---

## `[Security]` 安全漏洞

> 排查范围：板块配置拉取（Java API 回调 key）、事件合并 URL 处理、JSON 解析、AI 生成输入。本模块无直接用户输入入口（触发由内部 scheduler/routes 负责，鉴权见 C02/C10）。

未发现本模块特有的安全漏洞。本模块的安全边界依赖上游：①`_fetch_digest_sections` 调 Java API 时携带 `X-Callback-Key`（task_executor.py:1008-1009），跨服务双向 key 强度/比较方式归属 B09/X06；②板块 keyword/url 最终被 C03 搜索引擎/爬虫消费，SSRF/注入风险归属 C01/C03；③事件合并与 canonical URL 处理（digest_orchestrator.py:41-64、digest_gen_agent.py:239-263）为纯字符串操作，无外部调用，无注入面。

---

## `[Arch]` 架构与技术债

> 排查范围：编排分层、配置快照机制、与 C05/C06/C07 的耦合边界、可测试性。

### [P3] [Arch] digest_orchestrator.py 1256 行混合编排+评分+补救+评估多职责 <!-- 编号：C04-08 -->
- **定位**：`crawler-service/crawler/digest_orchestrator.py`（全文）
- **现象**：单文件承载：①Phase 0-4 编排（execute/_build_plan/_dispatch/_rescue/_evaluate）；②日报成品质量评分 `_calculate_digest_output_quality`（176 行，line 120-296）；③URL canonical 化工具函数（line 33-83）；④优化动作汇总 `_build_optimization_action_outcome`（line 1014-1066）；⑤配置快照 `_snapshot_config`。其中 `_calculate_digest_output_quality` 被 publish gate（digest_quality_gate.py:26）跨模块复用。
- **影响**：单文件过大，修改任一职责需通读全文定位，可维护性下降。`_calculate_digest_output_quality` 作为共享评分逻辑放在 orchestrator 文件内，被 digest_quality_gate 反向 import，形成隐式依赖。
- **根因/分析**：编排与评分逻辑随日报能力迭代逐步堆积。评分逻辑更适合放 quality 模块（C06/C08）。
- **修复方向**：①将 `_calculate_digest_output_quality` 及 URL 工具函数抽到独立模块（如 `crawler/digest_quality.py`）（改动面 中）；②publish gate 改为从新模块 import（改动面 小）。
- **关联**：C06、C08

### [P4] [Arch] Phase 1.2 rescue 与 Phase 1.5 optimization 功能边界重叠 <!-- 编号：C04-09 -->
- **定位**：`crawler-service/crawler/digest_orchestrator.py:807`（`_rescue_starved_core_sections`）；`crawler-service/crawler/digest_orchestrator.py:946`（`_should_run_optimization` → OptimizationAgent）
- **现象**：Phase 1.2 对核心板块做"扩时间窗口+fallback keyword"的补救爬取（orchestrator.py:842-898，time_range day→week→month→year）；Phase 1.5 的 OptimizationAgent 做"板块级弱维度识别+定向重爬"（optimization_agent.py:134-148）。两者都是"识别不足→重爬补充"，但触发条件、策略、预算不同：rescue 只看核心板块 result_count，optimization 看 6 维覆盖分；rescue 无独立预算（受 Phase 1 剩余时间），optimization 有独立 90s+ 预算。
- **影响**：逻辑分层清晰但概念重叠，新人理解成本高；极端场景下可能对同一板块先 rescue 再 optimize，重复消耗。
- **根因/分析**：rescue 是"保证核心板块有内容"的兜底，optimization 是"提升覆盖质量"的增强，目标不同但手段相似。当前 rescue 优先执行且 optimization 检查 `qualified >= min_sections`，有一定去重，但未显式排除已 rescue 的板块。
- **修复方向**：①optimization 阶段跳过已 rescue 成功的板块（改动面 小）；②或合并为统一的"不足→补充"管线（改动面 大，需评估）。
- **关联**：C06（OptimizationAgent）

---

## `[Deps]` 依赖升级与版本

### 本模块依赖清单（基于声明文件，未翻依赖源码）

| 依赖 | 版本 | 声明位置 | 已知风险/可升级 | 备注 |
|---|---|---|---|---|
| Python 标准库 asyncio | 内置 | - | 无 | Phase 1 并发/gather/timeout |
| httpx | 见 requirements | `crawler-service/requirements.txt` | 见 C01/C11 | 仅 `_fetch_digest_sections` 调 Java API 用（task_executor.py:1006） |
| dataclasses | 内置 | - | 无 | PlannedSection/DigestCrawlPlan 等 |

> 排查范围：本模块为纯编排层，第三方依赖极少（httpx 仅板块配置拉取，归属 C11）。无独立依赖风险。

---

## `[Design]` 功能设计合理性

> 从单人维护的技术博客 + 每工作日 AI 日报场景出发，审视编排闭环。

**审视结论**：

1. **闭环完整性**：日报闭环在"正常路径"下完整（规划→爬取→优化→生成→评估→KB 回写→下次规划参考），但**超时路径下闭环断裂**（C04-01：评估数据不回写）。这导致 KB 的趋势统计系统性遗漏最需要诊断的故障样本，弱维度自愈在超时场景失效。单人运维下，超时往往是源质量/网络问题的信号，丢掉这些数据等于让优化系统"只学顺利的"。这是当前设计最大的闭环缺口。

2. **可运维性/缺失功能**：①编排过程中的中间状态（plan_log/search_diagnostics/section_documents）已持久化到 task metadata（task_executor.py:362-395），单人运维可追溯，这点设计良好；②但 global timeout 触发后，Phase 4 被跳过只在日志 warning，无 task metadata 标记，运维从外部难以判断"这次日报是否走了超时降级路径"（C04-04 的命名问题加剧了这一点）；③缺少"人工剔除/合并日报条目"的入口（AI 生成后不可编辑，只能 force 重生成），属于闭环中缺失的人工干预环。

3. **单点与扩展**：`digest_parallel_sections=2` + `digest_global_timeout=600s` 对单人 5 板块场景合理；但板块配置从 Java API 拉取后按 contentCategory 分组（task_executor.py:1049），若 contentCategory 数量增长（如细分到 10+ 板块），max_parallel=2 会让 Phase 1 串行化严重，600s 预算可能不够。当前 5 板块/2 并发 = 最多 3 轮，每轮约 200s，边界紧凑。

### [P4] [Design] 超时日报缺乏人工干预入口与可观测标记 <!-- 编号：C04-10 -->
- **定位**：`crawler-service/crawler/digest_orchestrator.py:389-390`（超时仅 warning）；task metadata 未记录 timeout 标志
- **现象**：超时日报生成后，外部（前端/routes.py）无法从 task metadata 判断本次日报是否经历了 global timeout 降级。运维只能翻日志。
- **影响**：单人运维定位"为什么今天日报内容偏少"时，需 ssh 看日志，效率低。
- **建议方向**：在 orchestrator_plan metadata 中增加 `global_timeout_reached`/`incomplete` 标志位，前端日报详情可展示降级提示（改动面 中）。
- **关联**：[Bug] C04-01、C04-04、[Design] 可运维性

---

## 模块小结

### 严重度统计

| 级别 | 数量 | 条目编号 |
|---|---|---|
| P0 | 0 | — |
| P1 | 0 | — |
| P2 | 3 | C04-01, C04-02, C04-03 |
| P3 | 4 | C04-04, C04-05, C04-06, C04-08 |
| P4 | 3 | C04-07, C04-09, C04-10 |

### Top 风险（本模块最该先看的 ≤3 条）

1. **C04-01 global timeout 后日报评估数据不进 KB** —— 闭环断裂，趋势统计偏差，弱维度自愈在超时场景失效，是计划 §9 已知线索的确认与定级（P2）。
2. **C04-03 板块配置与发布门控核心板块不一致** —— 用户自定义板块（尤其用 Java 订阅源）会导致门控永远失败，日报发不出，体验断层。
3. **C04-02 digest_coverage_weight 死配置项** —— 引用了不存在的配置，永远走默认值，"可配置"是假象。

### 修复优先级建议

- **立即**（P0/P1）：无。
- **计划**（P2）：
  - C04-01：超时日报也写入 KB 并标记降权（需 C07 协同表结构）
  - C04-02：`_snapshot_config` 补 `digest_coverage_weight` 或删除死读取
  - C04-03：板块配置与核心板块一致性校验 + `.env.example` 示例对齐
- **择机**（P3/P4）：
  - C04-04：澄清 global_timeout 边界（重命名或文档）
  - C04-05/C04-06：清理 dead import 与兜底值对齐
  - C04-08：拆分 orchestrator 大文件
  - C04-10：超时标记持久化（可观测性）

### 排查盲区 / 待复核

- **[需查证]** C04-07：`organize_with_ai` fallback 路径的 stage 标记值（organizer_helper.py:306 附近），未完整读取该函数，仅确认 threshold 相同。若 stage 不同，诊断价值有差异。
- **[需查证]** C04-09：Phase 1.2 rescue 与 Phase 1.5 optimization 是否会重复处理同一板块，未深入 OptimizationAgent 内部的板块排除逻辑（optimization_agent.py 后续行），需 C06 排查时交叉确认。
- **测试盲区**：`test_digest_orchestrator.py` 无 `_global_timeout_reached=True` 时跳过 Phase 4 的专门测试（grep 确认无 timeout/skip 相关用例），C04-01 的修复需补该场景测试。

---

**已知线索复核结论**（计划 §9 `[Bug/P2] 日报 global timeout 后 KB 不写入`）：**确认成立**，定级 **P2**（见 C04-01）。判定依据：global timeout 触发后 Phase 4 被 `_global_timeout_reached` 短路（orchestrator.py:427-428），save_digest_evaluation 不执行，optimization_record 表无该日报记录，趋势统计经 `_is_publishable_digest_eval_record` 过滤后系统性遗漏超时样本。修复需 C04（编排层标记写入）+ C07（KB 表/查询降权）协同。
