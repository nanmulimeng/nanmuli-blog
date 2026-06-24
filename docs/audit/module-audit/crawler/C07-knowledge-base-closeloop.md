# C07 知识库与强闭环 排查报告

> **模块编号**：C07
> **排查范围**：KnowledgeBase（策略推荐、效能统计、日报弱点反馈、跨运行疲劳、source actions 推导 + 三层安全护栏 + negative-outcome-circuit-breaker）、SourceAgent（失效源过滤、skip/deprioritize 反馈应用 + 二次 guardrail）
> **基线 commit**：`6ae930098405f4d0553d96a852f3345d0f39682e`
> **工作区状态**：**脏**。涉及本模块的未提交文件：
> - `crawler-service/optimization/knowledge_base.py`（+129 行，含 circuit-breaker、action_outcome、derive_digest_source_actions 重构，属 `codex/digest-generation-closure` 分支进行中改动）
> - `crawler-service/tests/test_knowledge_base.py`（+77 行，补 circuit-breaker / action_outcome 测试）
> - `crawler-service/crawler/source_agent.py`（本报告基线工作区状态，`git diff` 无改动）
> **排查日期**：2026-06-24
> **排查人**：crawler 排查 agent
> **状态**：待复核

---

## 模块概览

**职责**：把"日报后评估 → 下次规划"的优化反馈持久化并安全地反作用于采集规划，形成跨运行的"建议转约束"强闭环。KnowledgeBase 是闭环的数据中枢（读写 `optimization_record` 表），SourceAgent 是约束的应用端。

**关键文件**：
- `crawler-service/optimization/knowledge_base.py:105` —— `KnowledgeBase` 主类，875 行（脏基线）。策略推荐、效能统计、日报评估读写、source actions 推导、三层护栏、circuit-breaker。
- `crawler-service/optimization/knowledge_base.py:457` —— `get_digest_source_actions`：读取最近一次日报评估 + diagnostics + action_outcome，调用 `derive_digest_source_actions`。
- `crawler-service/optimization/knowledge_base.py:517` —— `derive_digest_source_actions`：纯函数推导（skip/deprioritize/boost_sections + confidence）。
- `crawler-service/optimization/knowledge_base.py:678` —— `_apply_digest_source_action_safety`：**第一层护栏**——section-skip-cap（防板块饿死）+ low-confidence 降级。
- `crawler-service/optimization/knowledge_base.py:629` —— `_apply_digest_action_outcome_safety`：**第二层护栏**——negative-outcome-circuit-breaker（上次应用反馈结果为 negative 时全面降级）。
- `crawler-service/crawler/source_agent.py:249` —— `_guard_next_run_actions`：**第三层护栏**——SourceAgent 端二次保护（low-confidence 降级 + per-section skip cap）。
- `crawler-service/crawler/digest_orchestrator.py:1068` —— `_evaluate_digest_quality`：Phase 4 日报后评估，调用 `save_digest_evaluation` 写 KB。
- `crawler-service/crawler/digest_orchestrator.py:424-436` —— Phase 4 触发点（global timeout 时跳过 KB 写入）。
- `crawler-service/crawler/digest_orchestrator.py:1014` —— `_build_optimization_action_outcome`：构造 verdict（positive/needs_review/negative）供下次 circuit-breaker 使用。
- `crawler-service/standalone/task_executor.py:371` —— 把 `optimization_action_outcome` 写入 task `ai_search_metadata.orchestrator_plan`。
- `crawler-service/standalone/repository.py:554` —— `get_digest_source_diagnostics`：source 诊断数据来源（digest_item + crawl_page）。

**对外接口 / 依赖**：
- 对外：`routes.py` 暴露 `get_digest_quality_overview`（日报质量看板）、`_build_digest_detail` 内联调用 `derive_digest_source_actions`（详情页展示）。
- 依赖：`optimization_record` 表（C09 数据层主模块）、`crawl_task`/`digest_section`/`digest_item`/`crawl_page` 表（C09）、`optimization.evaluator`（C06）、`optimization.feedback`/`bubble_breaker`（C06）、`crawler.digest_orchestrator`（C04）。

**已读文件清单**：
- `crawler-service/optimization/knowledge_base.py` —— 通读（875 行）
- `crawler-service/crawler/source_agent.py` —— 通读（457 行）
- `crawler-service/crawler/digest_orchestrator.py` —— 片段（Phase 0/4、outcome 构造、timeout 分支）
- `crawler-service/standalone/repository.py:545-611` —— `get_digest_source_diagnostics`（通读）
- `crawler-service/standalone/task_executor.py:350-400` —— outcome 持久化
- `crawler-service/standalone/db.py:112-161` —— `optimization_record` schema + 索引
- `crawler-service/standalone/routes.py:1030-1055, 1174-1179` —— KB 查询端点
- `crawler-service/standalone/scheduler.py:483-492` —— cleanup 调度
- `crawler-service/optimization/evaluator.py` —— 仅 grep（AI 降级行为）
- `crawler-service/tests/test_knowledge_base.py` —— 片段（fatigue / circuit-breaker 测试）
- `docs/audit/module-audit/backend/B09-internal-callback.md` —— 仅 grep（B09 范围确认）

**主模块归属**：本模块是 **"建议转约束"强闭环主模块**，深查。对共享对象：`optimization_record` 表 schema 引用 C09；日报编排调用链引用 C04；优化评分生成引用 C06；指纹问题引用 B09（不重复展开，只评估对闭环的污染）。

---

## 强闭环完整性结论（核心评估）

**全链路（按运行时序）**：

1. **评估写入**：`_evaluate_digest_quality`（digest_orchestrator.py:1068）计算 6 维分数 + section_fill + output_quality → `save_digest_evaluation`（knowledge_base.py:325）写入 `optimization_record`（round_num=0, strategy_type='digest_final_eval'）。✅ 写入闭环成立。
2. **outcome 记录**：`_build_optimization_action_outcome`（:1014）根据 `final_score` + `section_fill_ratio` 判定 verdict（positive/needs_review/negative），写入 task `ai_search_metadata.orchestrator_plan.optimization_action_outcome`（task_executor.py:371）。✅ 成立。
3. **下次规划读取**：`_build_plan`（digest_orchestrator.py:442）调用 `kb.get_digest_source_actions()`（knowledge_base.py:457）→ 读最近一次 publishable 评估 + diagnostics + action_outcome → `derive_digest_source_actions` 推导 → 注入 `kb_hint["next_run_actions"]`。✅ 成立。
4. **三层护栏**：KB 侧 `_apply_digest_source_action_safety`（section-skip-cap + low-confidence）→ KB 侧 `_apply_digest_action_outcome_safety`（circuit-breaker）→ SourceAgent 侧 `_guard_next_run_actions`（二次 cap）。✅ 三层都在，且测试覆盖（test_knowledge_base.py:641/699）。
5. **SourceAgent 应用**：`SourceAgent.analyze`（source_agent.py:96）用 guarded actions 过滤 URL/RSS/keyword 源（skip/deprioritize/boost）。✅ 成立。
6. **验证回灌**：下一轮 Phase 4 再次评估 → 新 outcome → 若 negative 触发 circuit-breaker。✅ 闭环回起点。

**结论：强闭环是真闭环，非空壳。** 全链路 6 个环节均有代码 + 测试覆盖，是项目最完整的自反馈链路。

**但有两个断裂风险**（详见 C07-01、C07-04）：
- **global timeout 时 Phase 4 整体跳过**（digest_orchestrator.py:427-428）：超时当轮不写 KB，趋势统计偏向"顺利完成的日报"（已知线索，§9），且**超时当轮的 outcome 也不记录**，circuit-breaker 拿不到超时场景的 negative 信号。
- **展示路径与应用路径不一致**（routes.py:1046 vs knowledge_base.py:508）：详情页 `derive_digest_source_actions` 不传 `action_outcomes`，circuit-breaker 不触发；而下次运行 `get_digest_source_actions` 会触发。用户看到的 next_run_actions 与实际应用的可能不同。

**B09 指纹问题对闭环的污染评估**：

B09-01（指纹 @Insert 漏 id）和 B09-02（simhash 溢出）都针对**后端 Java→PG 的跨日去重指纹持久化**链路，**不涉及** crawler SQLite 的 `digest_item`/`digest_section`/`crawl_page` 写入。KB 的所有数据源（评估分数、source diagnostics、action_outcome）都在 crawler SQLite 内，**不直接受 B09 污染**。

**间接污染路径**：B09 导致跨日去重失效 → 日报可能出现与前一日重复的内容 → `_evaluate_digest_quality` 对"看似新鲜实则重复"的日报评分 → 评估分数失真（可能虚高，因为内容看起来充实；或 source_diversity 维度受影响）。这是**数据质量层面的间接污染**，不是代码缺陷。严重度：当前 MVP 阶段可接受（单日内去重仍由 crawler 本地内存保证，跨日重复概率受内容源更新频率制约），但应在 B09 修复后回归验证 KB 趋势数据的可信度。

---

## `[Bug]` 代码正确性与潜在缺陷

> 排查范围：KnowledgeBase 全部方法、SourceAgent.analyze 及 guardrail、derive/safety 静态方法、fingerprint 对 KB 的间接影响。

### [P3] [Bug] get_recent_dimension_fatigue 的"持续下降"判定逻辑不严谨 <!-- 编号：C07-01 -->
- **定位**：`crawler-service/optimization/knowledge_base.py:849`
- **现象**：`declining = all(scores[i] <= scores[-1] for i in range(len(scores) - 1))`。注释写"最早到最近持续下降或不变"，但实际判定的是"所有分数都不超过 `scores[-1]`（最早一次）"。`scores` 按 created_at DESC，最近在前，`scores[-1]` 是最早。
- **影响**：对**单调下降**序列（如 [0.3, 0.5, 0.7] 最近→最早）判定正确；但对**波动下降**（如 [0.4, 0.3, 0.5]，整体趋势下降但中间反弹）也会因为 `0.4<=0.5 and 0.3<=0.5` 为 True 而误判为 fatigue。方向偏宽松——更容易触发弱维度 boost，对"防饿死"是安全的，但语义不严谨。
- **根因/分析**：正确的"单调不增"（最近→最早）应是 `all(scores[i] <= scores[i+1] for i in range(len(scores)-1))`。当前写法把"最大值在最早"等同于"单调下降"，两者不等价。已排除误判：测试 `test_recent_dimension_fatigue_uses_actual_dimension_columns`（test_knowledge_base.py:293）用纯单调序列覆盖，未暴露波动场景。
- **修复方向**：改为相邻元素比较 `scores[i] <= scores[i+1]`，并补波动下降的负向测试用例。（改动面：小）
- **关联**：[[C06]] 疲劳检测归 C06 主模块，此处只记 KB 视角；次维度 `[Arch]`（语义与注释不符）。

---

## `[Security]` 安全漏洞

> 排查范围：KB 所有 SQL 拼接点、LIKE 通配符、参数化、task 元数据解析。技术栈重点（§2.2）本模块不涉及 Sa-Token/Cookie/AES/SSRF/文件上传/双向 key（纯 Python 内部模块）。

### [P3] [Security] LIKE 查询通配符已转义，参数化完整，无注入风险 <!-- 编号：C07-02 -->
- **定位**：`crawler-service/optimization/knowledge_base.py:11-20, 126-127, 244-245`
- **现象**：`_escape_like` 用 `!` 作 ESCAPE 字符转义 `%`/`_`/`!`，所有 LIKE 子句带 `ESCAPE '!'`，参数均通过 `?` 占位符绑定。`get_strategy_hint` / `get_similar_keyword_strategies` 有 token 数量上限（3 / 5）防 OR 子句 DoS。
- **影响**：无注入风险。`get_similar_keyword_strategies` 另有 `len(keyword) > 200` 截断（:233）。
- **根因/分析**：实现正确。唯一可改进点：`get_strategy_hint`（:122）只取 `tokens = keyword.split()[:3]` 但未对单 token 长度截断，超长 token 会进入 LIKE 参数（SQLite 对绑定参数长度无硬限，影响有限）。
- **修复方向**：可选——对单 token 加长度上限（如 100 字符）。（改动面：小）
- **关联**：无需调整，记录为已验证安全。

---

## `[Arch]` 架构与技术债

> 排查范围：KB 类职责边界、round_num=0 隐式约定、confidence 三档语义、三层护栏冗余度、KB 查询索引。共享对象按 §8.6：optimization_record schema 引用 C09。

### [P2] [Arch] 展示路径跳过 circuit-breaker，与实际应用路径产生"看到的不是应用的" <!-- 编号：C07-03 -->
- **定位**：`crawler-service/standalone/routes.py:1046`（`_build_digest_detail` 调用 `derive_digest_source_actions`）vs `crawler-service/optimization/knowledge_base.py:508`（`get_digest_source_actions` 调用 `derive_digest_source_actions`）
- **现象**：详情页展示用 `derive_digest_source_actions(diagnostics, weaknesses, suggestions, digest_date, created_at)`——**不传 `action_outcomes`**；而下次规划用 `get_digest_source_actions` 内部会加载 action_outcomes 并触发 `_apply_digest_action_outcome_safety`（circuit-breaker）。
- **影响**：当上次日报的 optimization_action_outcome.verdict == "negative" 时，详情页展示的 next_run_actions 仍带 skip 动作（circuit-breaker 未触发），但下次实际运行时这些 skip 会被降级为 deprioritize、confidence 降为 low。用户/运维在看板上看到的"下次会 skip 这些源"与实际行为不符，误导排障。
- **根因/分析**：`_build_digest_detail` 是同步构造详情的辅助函数，action_outcome 需额外读 task.ai_search_metadata，调用方未传入。非 bug，是展示层与执行层的语义割裂。已排除误判：`derive_digest_source_actions` 签名上 action_outcomes 是可选参数（:525），展示路径不传是"刻意简化"但带来了不一致。
- **修复方向**：①详情页也加载 action_outcome（从 task.ai_search_metadata 解析）传入 derive；或 ②在 derive 返回里标记"展示模式 vs 应用模式"，详情页显式标注"以下动作尚未应用 circuit-breaker"。（改动面：中）
- **关联**：[[C04]] 展示层归编排；横向主题：跨服务契约一致性（前端看板字段 vs 后端实际行为）。

### [P3] [Arch] KB 日报评估查询缺 (strategy_type, created_at) 复合索引 <!-- 编号：C07-04 -->
- **定位**：`crawler-service/standalone/db.py:136-139`（现有索引：task / delta / engine / keyword）vs `crawler-service/optimization/knowledge_base.py:294, 367, 461, 819`（所有日报评估查询都按 `strategy_type='digest_final_eval' ORDER BY created_at DESC`）
- **现象**：KB 的 4 个核心趋势/弱点查询（get_last_digest_weaknesses / get_digest_quality_trend / get_digest_source_actions / get_recent_dimension_fatigue）全部过滤 `strategy_type` 并按 `created_at` 排序，但无对应复合索引，需全表扫描 + 排序。
- **影响**：当前 MVP 数据量小（每天 1 条 digest_final_eval），无感。长期运行（数百条记录混合 keyword 优化记录）后查询成本上升，尤其 `get_digest_quality_overview` 在看板被频繁调用（routes.py:910, 1179）。
- **根因/分析**：索引按 keyword 优化场景设计（engine/delta/keyword），日报评估场景的索引缺失。属设计时遗漏（日报评估是后加的 Phase 4 闭环）。
- **修复方向**：在 `_MIGRATIONS` 加 `CREATE INDEX IF NOT EXISTS idx_opt_record_strategy_created ON optimization_record(strategy_type, created_at DESC)`。（改动面：小，schema 引用 C09）
- **关联**：[[C09]] SQLite schema 主模块。

### [P4] [Arch] round_num=0 作为 digest_final_eval 的隐式约定，缺少文档与防御 <!-- 编号：C07-05 -->
- **定位**：`crawler-service/optimization/knowledge_base.py:347`（save_digest_evaluation 写 round_num=0）；`:134, 200, 219, 252`（策略推荐查询 `WHERE round_num > 1` 过滤掉 round_num=0）
- **现象**：日报评估记录用 `round_num=0` 与 keyword 优化轮次（round_num>1）隔离，策略推荐查询用 `round_num > 1` 排除它们。语义靠两处隐式约定耦合。
- **影响**：当前正确工作（测试 test_knowledge_base.py:393/661 验证 round_num=0 写入，策略查询测试覆盖 >1 过滤）。但约定是隐式的：若有人新增一个用 round_num=0 但 strategy_type 不是 digest_final_eval 的记录，会被策略查询静默忽略；反之若有人把 digest_final_eval 的 round_num 改非 0，会污染策略推荐。
- **根因/分析**：`strategy_type` 字段已是显式区分维度，`round_num=0` 是冗余的辅助标记。设计上可接受，属可维护性观察项。
- **修复方向**：①在 save_digest_evaluation 加注释说明 round_num=0 的语义约定；或 ②策略推荐查询改为显式 `WHERE strategy_type != 'digest_final_eval'`，不依赖 round_num。（改动面：小）
- **关联**：次维度 `[Design]`。

---

## `[Deps]` 依赖升级与版本

### 本模块依赖清单（基于声明文件，未翻依赖源码）

| 依赖 | 版本 | 声明位置 | 已知风险/可升级 | 备注 |
|---|---|---|---|---|
| aiosqlite | （runtime） | `crawler-service/requirements.txt` | 本模块仅用 `get_db()` 上下文管理器 + `db.execute`，无直接版本敏感 API | 引用 C09 数据层主模块 |
| Python 标准库 `json` / `logging` | — | — | — | 无第三方依赖 |

> 排查范围：本模块是纯 Python 标准库 + aiosqlite，无独立第三方依赖。版本风险归 C09（aiosqlite 主模块）。未命中 `[Deps]` 维度发现。

---

## `[Design]` 功能设计合理性

> 从真实使用（单人维护技术博客 + 每工作日 AI 日报）出发，回答 §2.5 相关问题。

**审视结论**：

1. **场景适配（§2.5-1）**：强闭环设计**超前但合理**。三层护栏 + circuit-breaker + confidence 三档，对"单人维护、无人工复核日报质量"的场景是恰当的——反馈系统在无人监督下必须偏保守，否则一次坏评估会饿死整个板块。护栏冗余度（KB 侧 cap + SourceAgent 侧 cap）看似重复，实则是"防御性编程"——任何一层被绕过都有兜底，符合"自动系统在 MVP 阶段宁可少做不可做错"的原则。
2. **闭环完整性（§2.5-2）**：**真闭环**（见上方"强闭环完整性结论"），6 个环节代码 + 测试齐全，是项目最完整的自反馈链路。但**缺人工干预入口**：KB 没有"管理员手动覆盖某条 source action"的接口，当反馈系统误判时（如某优质源被错误 skip），只能等 circuit-breaker 自然恢复或手动改 DB。单人维护场景下这是可接受的（直接改库），但应文档化。
3. **MVP 假设检验（§2.5-4）**：**"建议转约束"实际跑得通**——derive → safety → SourceAgent 应用 → outcome 回灌全链路有集成测试（test_optimization_integration.py / test_learning_loop.py）。唯一"看起来能用实则打折"的点是 **global timeout 时整条 Phase 4 跳过**（digest_orchestrator.py:427），超时场景的反馈数据缺失，趋势统计有偏（已知线索 §9）。
4. **可运维性（§2.5-3）**：KB 查询都走 routes.py 暴露（quality_overview / trend），运维可观测。但**缺"为什么这个源被 skip"的逆向追踪**——`safety.downgraded` 记录了降级动作，`sources[source_key].reason` 记录了原始判定，但没有端到端的"某源在 N 次运行中的 action 演变"视图，排障时需手工拼。

### [P1] [Design] global timeout 时 Phase 4 整体跳过，超时场景无 outcome 触发 circuit-breaker <!-- 编号：C07-06 -->
- **定位**：`crawler-service/crawler/digest_orchestrator.py:427-428`
- **现象**：`if self._global_timeout_reached: logger.warning("Skipping Phase 4 KB write...")`——超时时既不写 `save_digest_evaluation`，也不构造 `optimization_action_outcome`。
- **影响**：两个后果——①趋势统计偏向"顺利完成的日报"（已知线索 §9，C04 主模块）；②**更严重**：超时往往意味着 section_fill_ratio 很低、本应产生 negative verdict 触发 circuit-breaker，但 outcome 不记录导致 circuit-breaker 永远拿不到"超时→反馈无效"的信号。即：反馈系统在最需要自我修正的场景（超时饿死）下失明。
- **根因/分析**：设计意图是"不完整数据不污染 KB 推荐"（注释 :425），合理；但把"评估写入"和"outcome 记录"一起跳过过于激进——outcome 可以独立记录（标记为 timeout 场景），让 circuit-breaker 学习。已排除误判：`_build_optimization_action_outcome` 接受 `final_score` / `section_fill_ratio` 参数，超时时可传入已知的不完整值。
- **修复方向**：超时时仍构造 outcome（verdict=negative，标记 timeout=True）写入 task metadata，但不写 save_digest_evaluation（保持趋势数据洁净）。让 circuit-breaker 能学习超时场景。（改动面：中）
- **关联**：[[C04-NN]] 编排主模块；[[B09-01]] 指纹问题的对照（B09 也是"non-critical 静默失败"模式）。

### [P4] [Design] confidence="medium" 阈值偏低（diagnostics>=2），medium skip 仅靠 section-skip-cap 兜底 <!-- 编号：C07-07 -->
- **定位**：`crawler-service/optimization/knowledge_base.py:598`（`confidence = "medium" if len(diagnostics) >= 2 else "low"`）；`:691`（low-confidence 才触发全量降级）
- **现象**：只要 ≥2 条 source diagnostics 就判 medium，medium 的 skip 动作在 KB 侧不做 low-confidence 全量降级（只做 section-skip-cap），在 SourceAgent 侧也不做 low-confidence 降级（source_agent.py:256 只处理 "low"）。
- **影响**：2 条 diagnostics 中若 1 条被判 skip（verdict=filter 或 score<0.4），该 skip 会直接生效。对单人博客场景，单次日报每个板块的 source 本就不多，2 条样本不足以构成"统计可靠的 skip 判定"，偏激进。但 section-skip-cap（max_skip = source_count//2）兜底，单源场景 max_skip=0，不会饿死。
- **根因/分析**：保守与激进的权衡。diagnostics>=2 是"至少有对照样本"的最低门槛，配合 section-skip-cap 实际不会饿死板块。属可接受的设计选择，记录为观察项。
- **建议方向**：可选——把 medium 阈值提到 3，或对 medium 也做"单源 skip 需连续 2 次评估确认"的加强。（改动面：中）
- **关联**：次维度 `[Arch]`。

---

## 模块小结

### 严重度统计

| 级别 | 数量 | 条目编号 |
|---|---|---|
| P0 | 0 | — |
| P1 | 1 | C07-06 |
| P2 | 1 | C07-03 |
| P3 | 3 | C07-01, C07-02, C07-04 |
| P4 | 2 | C07-05, C07-07 |

### Top 风险（本模块最该先看的 ≤3 条）

1. **C07-06 global timeout 跳过 Phase 4 致 circuit-breaker 失明** —— 反馈系统在最需要自我修正的超时饿死场景下拿不到 negative 信号，强闭环的"自我纠错"能力打折。
2. **C07-03 展示路径跳过 circuit-breaker** —— 看板展示的 next_run_actions 与实际应用的不一致，排障误导。
3. **C07-04 KB 趋势查询缺复合索引** —— 长期运行后看板查询成本上升（当前无感）。

### 修复优先级建议

- **立即**（P0/P1）：C07-06（超时场景 outcome 补录，让 circuit-breaker 学习超时）。
- **计划**（P2）：C07-03（详情页展示与应用路径统一 circuit-breaker）。
- **择机**（P3/P4）：C07-01（fatigue 判定逻辑严谨化）、C07-04（补复合索引，随 C09 schema 维护一起做）、C07-05（round_num 约定文档化）、C07-07（confidence 阈值观察）。

### 排查盲区 / 待复核

- **[需查证]** C07-06 修复方向（超时仍写 outcome）是否与 C04 编排模块的设计意图冲突——需 C04 报告确认 Phase 4 跳过的完整语义。
- **[需查证]** B09 指纹问题修复后，KB 趋势数据（source_diversity 维度）是否需回归验证——依赖 B09-01/B09-02 先修复。
- **未深入**：`optimization.feedback` / `bubble_breaker`（C06 主模块）与 KB 的交互细节，本轮只确认调用方向，未逐行核对反馈写入对 KB 趋势的二次影响。
- **未运行**：未跑 pytest（命令边界 §1.3 禁止），所有测试断言引用基于代码阅读 + 测试文件 grep，未实际验证通过。
