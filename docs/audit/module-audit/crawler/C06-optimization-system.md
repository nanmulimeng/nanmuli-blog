# C06 自动优化系统 排查报告

> **模块编号**：C06
> **排查范围**：6 维评分（CoverageEvaluator）、深度/广度策略生成、疲劳追踪、深度优化循环（FeedbackLoop）、茧房突破（BreadthExpander + 跨语言翻译）
> **基线 commit**：`6ae930098405f4d0553d96a852f3345d0f39682e`
> **工作区状态**：脏。涉及本模块的未提交文件：`crawler-service/optimization/knowledge_base.py`（C07 主模块文件，C06 仅引用）、`crawler-service/tests/test_optimization.py`。C06 自身核心文件（evaluator/strategy/feedback/bubble_breaker/fatigue/utils）干净。
> **排查日期**：2026-06-24
> **排查人**：C06 排查 agent
> **状态**：草稿

---

## 模块概览

**职责**：对关键词/日报搜索结果进行 6 维覆盖度评分，基于弱点生成深度/广度补搜策略，迭代优化直到达标或预算耗尽；跨语言翻译突破信息茧房。

**关键文件**：
- `crawler-service/optimization/evaluator.py:108` —— `CoverageEvaluator`，6 维评分（angle/source_diversity/depth/temporal/perspective/language），含 AI 评估与 heuristic 回退、digest 专用 heuristic。
- `crawler-service/optimization/strategy.py:43` —— `DepthStrategyGen`（depth/angle/temporal），`:192` `BreadthStrategyGen`（source_diversity/perspective/language + source_expand），`:476` `StrategyGenerator`（向后兼容合并入口）。
- `crawler-service/optimization/fatigue.py:18` —— `FatigueTracker`，outcome-aware 维度疲劳追踪（连续 N 次无改善标记疲劳）。
- `crawler-service/optimization/feedback.py:34` —— `FeedbackLoop`，keyword 路径深度优化循环（仅 depth/angle/temporal）。
- `crawler-service/optimization/bubble_breaker.py:43` —— `BubbleBreaker`（跨语言翻译组件），`:146` `BreadthExpander`（keyword 路径广度扩展循环）。
- `crawler-service/optimization/utils.py:10` —— `save_optimization_round`，duck typing 保存轮次到 `optimization_record` 表。

**对外接口 / 依赖**：
- 对外：`CoverageEvaluator.evaluate()`、`DepthStrategyGen/BreadthStrategyGen.generate()`、`FeedbackLoop/BreadthExpander.execute()`、`BubbleBreaker.translate_keyword()`、`KnowledgeBase.get_strategy_hint()`（C07）。
- 消费方：`standalone/keyword_handler.py:117`（keyword 路径，FeedbackLoop+BreadthExpander）、`crawler/optimization_agent.py:62`（digest 路径，OptimizationAgent，板块感知）、`crawler/digest_orchestrator.py:362`（Phase 1.5 调用 OptimizationAgent）。
- 依赖：`config.settings`（optimization_*/breadth_*/bubble_*/eval_weight_*）、`ai.organizer.ContentOrganizer._call_ai`（AI 评估/翻译）、`optimization.knowledge_base.KnowledgeBase`（C07）、`crawler.utils.{detect_cjk,normalize_url,dedup_results_into,get_result_url/get_result_success}`、`crawler.search.crawl_by_keyword`、`crawler.source_crawler.{crawl_url_sources,crawl_rss_sources}`、`standalone.repository.save_optimization_round`、表 `optimization_record`（C09）。

**已读文件清单**（可追溯 + 暴露盲区）：
- `optimization/evaluator.py` —— 通读
- `optimization/strategy.py` —— 通读
- `optimization/fatigue.py` —— 通读（仅 44 行）
- `optimization/feedback.py` —— 通读
- `optimization/bubble_breaker.py` —— 通读
- `optimization/utils.py` —— 通读
- `optimization/knowledge_base.py` —— 通读（C07 主模块，本报告只引用接口）
- `standalone/keyword_handler.py` —— 通读（keyword 路径入口）
- `crawler/optimization_agent.py` —— 通读（digest 路径入口）
- `config.py:150-238` —— 片段（optimization/bubble/eval_weight 配置 + validator）
- `crawler/utils.py:1-75` —— 片段（C06 依赖的工具函数）
- `standalone/backend_config.py:126-277` —— grep（配置同步范围）
- `standalone/repository.py:696-735` —— 片段（save_optimization_round 契约）
- `crawler/digest_orchestrator.py:355-395,940-975` —— 片段（Phase 1.5 调用点）
- 测试文件：`tests/test_optimization.py`（片段）、`tests/test_optimization_integration.py`（片段）—— 未逐条核对测试覆盖

**主模块归属**（§8.6）：
- **C06 是「keyword 优化循环 vs digest 优化循环两套实现」共享对象的主模块** —— 本报告深查。
- C06 引用（不展开）：knowledge_base 强闭环 → **C07**；digest_orchestrator 编排调用 → **C04**；optimization_record 表/schema → **C09**；eval_weight_* 配置同步缺失 → **X06**；FatigueTracker 跨运行预填充的 KB 数据源 `get_recent_dimension_fatigue` → C07 实现。

---

## `[Bug]` 代码正确性与潜在缺陷

> 排查范围：evaluator 的 heuristic 评分与样本量校正、strategy 的策略去重与边界、feedback/bubble_breaker 的循环终止与 deadline、fatigue 的预填充、utils 的保存契约。逐文件通读 + 消费方调用链核对。

### [P2] [Bug] digest 单板块评估复用全局 section_result_counts，angle 维度被系统性高估  <!-- 编号：C06-01 -->
- **定位**：`crawler-service/crawler/optimization_agent.py:109`（ctx 初始化）、`:377-394`（`_evaluate_per_section`）、`optimization/evaluator.py:430-476`（`_heuristic_evaluate_digest`）
- **现象**：OptimizationAgent 在 `execute` 开头把全局 `section_result_counts` 写入 `ctx`（:109），后续 `_evaluate_per_section` 对每个 section 单独调 `evaluator.evaluate(keyword, sec_results, ctx)` 时，**复用同一个全局 ctx**，未按当前 section 裁剪 `section_result_counts`。而 `_heuristic_evaluate_digest` 的 angle 公式 `angle = 0.25 + 0.65 * section_ratio`（evaluator.py:440）中 `section_ratio = covered_sections / configured_sections` 用的是全局板块覆盖率，与当前被评估的单个 section 无关。
- **影响**：对单个弱板块评估时，只要全局板块覆盖率高（如 5/5 板块都有结果），该单 section 的 angle 分会被全局分数抬高（可达 0.9），导致 `_identify_weak_sections`（:432 `weakest = [d for d, s in sorted_dims[:2] if s < 0.6]`）**很难把 angle 选为弱维度**，定向重爬会偏向其他维度。结果是 angle 弱的板块得不到 angle 方向的策略补搜，优化决策与真实弱点错配。
- **根因/分析**：`_heuristic_evaluate_digest` 的 angle 语义是"日报整体板块覆盖度"，属于全局指标，被误用于单 section 评估场景。已排除"故意用全局分激励整体覆盖"的解读——因为该函数同时被全局评估（:119）和单 section 评估（:391）复用，但语义只对全局成立。
- **修复方向**：①`_evaluate_per_section` 为每个 section 构造独立 ctx，将 `section_result_counts` 收窄为 `{section.name: len(sec_results)}`（中）；②或给 evaluator 增加显式的 `scope="section"` 参数，让 angle 在 section 级用 section 内的多角度信号计算（大）。③最小改法：在 `_heuristic_evaluate_digest` 里对单 section 场景降权 angle（中，但语义不清晰，不推荐）。
- **关联**：C04（digest 编排）、次维度 [Design]、横向主题"评分与优化决策耦合"

### [P2] [Bug] FeedbackLoop 用 breadth 评估作 depth 基线，首轮 depth_base 可能虚高  <!-- 编号：C06-02 -->
- **定位**：`crawler-service/standalone/keyword_handler.py:169-184`（传 `initial_evaluation=last_breadth_eval`）、`optimization/feedback.py:88-119`
- **现象**：keyword 路径"先广后深"，`_run_optimization_loop` 把 BreadthExpander 最后一轮的 `evaluation`（一个完整 6 维 `CoverageEvaluation`）直接传给 `FeedbackLoop.execute(initial_evaluation=...)`。FeedbackLoop Round 1 不重新评估，直接用该 evaluation 算 `depth_base = depth*0.4 + angle*0.35 + temporal*0.25`（feedback.py:108）。
- **影响**：breadth 阶段的评估是在"广度补搜后、深度补搜前"的结果集上做的，此时 depth/angle/temporal 三维尚未被深度策略优化，分通常偏低。若该分恰好 ≥ `optimization_depth_target_score`(默认 0.7)，FeedbackLoop 会在 Round 1 直接 `return`（feedback.py:117-119），**跳过所有深度优化**。反之若 breadth 阶段因 source_expand 引入大量长内容把 depth 抬高，也会让 depth 循环误判达标。本质是"用广度阶段的快照决定深度阶段是否启动"，基线语义错配。
- **根因/分析**：复用 evaluation 对象是为了省一次 AI/启发式评估调用（性能优化），但牺牲了基线准确性。已排除"breadth 和 depth 共享结果集所以评估通用"的解读——breadth 阶段的目标函数是 `_breadth_score`，其优化方向不会改善 depth 三维，两者解耦。
- **修复方向**：①FeedbackLoop Round 1 始终重新评估（去掉 `initial_evaluation` 旁路或仅作日志参照）（小）；②保留旁路但加注释说明"接受基线近似"，并把 `target_score` 检查延后到 Round 2（中）。
- **关联**：C06-03（共享 deadline 加剧）、次维度 [Design]

### [P2] [Bug] keyword 路径 breadth+depth 共享单一 deadline，breadth 超时会挤压 depth 至 0 预算  <!-- 编号：C06-03 -->
- **定位**：`crawler-service/standalone/keyword_handler.py:144`（`deadline = time.monotonic() + settings.optimization_total_budget_seconds`）、`:159`（传给 BreadthExpander）、`:183`（同一 deadline 传给 FeedbackLoop）、`optimization/feedback.py:77`、`optimization/bubble_breaker.py:195`
- **现象**：`_run_optimization_loop` 只计算一次 `deadline`（基于 `optimization_total_budget_seconds`，默认 120s），BreadthExpander 和 FeedbackLoop 共用。两个循环内部都在每轮检查 `time.monotonic() > effective_deadline`（feedback.py:211、bubble_breaker.py:376）。
- **影响**：若 BreadthExpander 用掉大部分预算（如 100s），FeedbackLoop 的 `effective_deadline` 只剩 20s，首轮爬取+评估就可能超时，深度优化名存实亡。反之 breadth 阶段也会因为知道后续还有 depth 而无法放手用满预算。两个子循环实际是"抢"同一个预算池，但代码没有按比例分配（如 breadth 40% / depth 60%）。
- **根因/分析**：对比 digest 路径的 OptimizationAgent，它用 `_optimization_budget_seconds = max(90, total*0.6)`（optimization_agent.py:285）显式预留评估+重爬时间，设计更稳健。keyword 路径缺少类似的预算分割。已排除"故意让 breadth 优先"的解读——两阶段都是 `optimization_mode="both"` 的一等公民。
- **修复方向**：①按比例分割 deadline，如 breadth 用 `total*0.4`、depth 用 `total*0.6`，分别传不同 deadline（小）；②或让 BreadthExpander 接受 `max_budget_fraction` 参数内部自限（中）。
- **关联**：C06-02、次维度 [Design]

### [P3] [Bug] 跨运行疲劳预填充在默认 window=2 下是死代码，但仍触发 DB 查询  <!-- 编号：C06-04 -->
- **定位**：`crawler-service/crawler/optimization_agent.py:164-176`（预填充逻辑）、`optimization/fatigue.py:15,21`（`_DEFAULT_EXHAUST_WINDOW = 2`，`FatigueTracker()` 默认构造）
- **现象**：OptimizationAgent 用默认 `FatigueTracker()` 构造（window=2）。预填充代码 `prefill_count = max(0, self._fatigue._window - 2)`（:167）在 window=2 时 `prefill_count = 0`，内层 `for _ in range(0)` 循环从不执行。但外层仍会调 `kb.get_recent_dimension_fatigue(limit=3)`（:165，一次 DB 查询）并打印日志（:170）。
- **影响**：跨运行疲劳感知（从历史 digest 评估预填疲劳）这一能力**实际从未生效**（除非手动把 window 改成 ≥3，但无配置项暴露）。每次 OptimizationAgent 启动白白多一次 DB 查询。日志会打印"pre-filled for 'X' (0/2)"造成"功能在运行"的错觉，实际是空操作。
- **根因/分析**：`window - 2` 的设计意图是"保留 1 次机会避免维度被直接跳过"，但当 window=2 时数学上就是 0。这是 window 参数与预填充公式不匹配的逻辑漏洞，非有意设计。已排除"故意禁用"的解读——代码注释（:163）明确说"保留 1 次机会"，说明作者认为它会预填。
- **修复方向**：①把公式改为 `max(0, self._fatigue._window - 1)` 真正保留 1 次机会（小）；②或把 window 通过 settings 暴露为可配置（如 `fatigue_window=3`），让预填充有意义（中）；③若确认不需要跨运行预填，删除整段死代码 + DB 查询（小）。
- **关联**：C07（`get_recent_dimension_fatigue` 数据源）、次维度 [Arch]（死代码）

### [P3] [Bug] 年份提取正则会把内容中的 4 位数字误判为年份  <!-- 编号：C06-05 -->
- **定位**：`crawler-service/optimization/evaluator.py:192`（`_YEAR_RE = re.compile(r'(?:20)(\d{2})')`）、`:216-220`
- **现象**：正则匹配任何 "20" 开头的 4 位数字（2000-2099），然后在 `2010 <= y <= current_year+1` 范围内加入 `years_found`。但内容前 2000 字里常见的 "2024"（如 issue 编号、版本号、端口号 2024、阅读量 2024）都会被当作年份信号。
- **影响**：temporal 维度的 heuristic 评分（evaluator.py:382-390 `span = max(years) - min(years)`，跨 4 年 → 0.5）会被虚假年份扰动。例如内容里同时出现 "2018" 和 "2024"（一个是真实年份一个是 ID），span=6 会让 temporal 直接封顶 0.5，高估时效覆盖。
- **根因/分析**：纯正则无法区分年份与其他 4 位数字。已排除"影响很小"的解读——temporal 维度直接参与 overall 评分（权重 0.15）和深度子循环达标判断。
- **修复方向**：①提高提取精度，要求年份前后有月份/日期上下文（如 `2024年`、`Jan 2024`、`/2024/` 路径）（中）；②或降低 temporal 在 heuristic 中的权重，减少噪声影响（小，治标）；③用 URL 的 `/2024/` 路径段作为主信号，内容年份作辅信号（中）。
- **关联**：次维度 [Design]（评分可操纵性）

### [P3] [Bug] strategy.generate 的 round_num 参数在三个生成器中均未使用  <!-- 编号：C06-06 -->
- **定位**：`optimization/strategy.py:58`（DepthStrategyGen.generate 签名）、`:217`（BreadthStrategyGen.generate）、`:499`（StrategyGenerator.generate）
- **现象**：三个 generate 函数都接收 `round_num: int` 参数，但函数体内从未引用该参数（已 grep 确认仅出现在签名和透传）。策略去重完全靠 `history`（已用关键词/引擎/site_scope 集合）。
- **影响**：无功能性 bug，但 `round_num` 本可用于"前 N 轮只用基础限定词、后期才用二级限定词"的渐进策略，现在该能力缺失。也是接口冗余，误导调用方以为轮次会影响策略。
- **根因/分析**：历史遗留参数，早期版本可能用过。已排除"未来扩展预留"的解读——无注释说明，且 FeedbackLoop/BreadthExpander/OptimizationAgent 都老老实实传了 round_num。
- **修复方向**：①要么移除 round_num 参数（小，但需改 3 处签名+所有调用方）；②要么真正用它实现渐进策略（中）。择机处理。
- **关联**：次维度 [Arch]（接口冗余）

---

## `[Security]` 安全漏洞

> 排查范围：C06 无 HTTP 端点、无用户输入直连、无 SQL 拼接（KB 查询在 C07 已用参数化 + LIKE 转义）。重点查 AI prompt 注入、跨语言翻译输出是否回传搜索。本项目技术栈特定重点（Sa-Token/MyBatis/Cookie/CORS/AES/SSRF/文件上传/双向 key）C06 均不直接涉及。

**未发现** C06 自身代码的安全漏洞。说明：

- C06 不直接处理用户输入，keyword 来自 crawl_task 表（C09）或 digest_plan（C04），搜索结果来自搜索引擎（C03）。
- AI prompt（evaluator.py:52-98 的 `EVALUATOR_SYSTEM_PROMPT`、bubble_breaker.py:26-40 的翻译 prompt）把搜索结果标题/内容预览拼入 user_prompt（evaluator.py:343-351），理论上恶意网页标题可构成 prompt 注入，但影响仅限于让 AI 给出错误评分/翻译——不回传到高危操作，且评分有 heuristic 兜底。属低风险，不单列条目。
- 跨语言翻译结果（bubble_breaker.py:97-118 `translate_keyword`）直接作为搜索关键词传给 `crawl_by_keyword`（C03），翻译内容由 AI 决定。若 AI 返回含特殊字符的查询，由搜索引擎层处理，C06 不做额外校验。风险传导至 C03 的 SSRF 防护（主模块 C01），本报告只引用。

---

## `[Arch]` 架构与技术债

> 排查范围：两套优化循环的重复实现、死代码、配置同步缺口、硬编码、接口语义双轨。共享对象按 §8.6 归属，C06 深查"keyword vs digest 两套循环"。

### [P1] [Arch] keyword 优化循环与 digest 优化循环是两套独立编排，逻辑重复且漂移  <!-- 编号：C06-07 -->
- **定位**：keyword 路径 `optimization/feedback.py:34`（FeedbackLoop）+ `optimization/bubble_breaker.py:146`（BreadthExpander）；digest 路径 `crawler/optimization_agent.py:62`（OptimizationAgent）
- **现象**：两条路径都调用同一组底层组件（CoverageEvaluator / DepthStrategyGen / BreadthStrategyGen / KnowledgeBase / BubbleBreaker），但**编排逻辑完全独立重写**：
  - keyword 路径：`keyword_handler._run_optimization_loop` 编排"先广后深"两个独立循环（BreadthExpander.execute → FeedbackLoop.execute），扁平结果集，无板块概念，不用 FatigueTracker。
  - digest 路径：OptimizationAgent 自己写了一套"板块映射 → 板块级评估 → 识别弱板块 → 定向重爬 → 收敛检测"循环，用 FatigueTracker，有跨运行疲劳预填充，有 section_document 更新。
  - 两者都实现"评估→策略→爬取→去重→再评估→达标/收敛/预算终止"，但终止条件、疲劳处理、结果合并方式都不同。
- **影响**：
  1. **漂移风险**：任何一边的 bug 修复/策略改进不会自动同步到另一边。例如 C06-04 的 FatigueTracker 预填充 bug 只在 digest 路径，keyword 路径根本没疲劳追踪——若未来发现某策略有害，两边要分别改。
  2. **能力不对等**：digest 路径有板块感知、疲劳追踪、跨运行预填、source_expand；keyword 路径都没有（见 C06-08）。用户用 keyword 任务时拿不到 digest 级别的优化质量。
  3. **维护成本翻倍**：两套循环各自 200+ 行编排代码，测试也分两套（test_optimization.py vs test_optimization_agent.py）。
- **根因/分析**：这是 §9 已知线索 "[Arch/P2] keyword 优化循环 vs digest 优化循环两套实现" 的细化，本报告深查后**上调为 P1**——因为漂移已实际发生（FatigueTracker 只在一边、source_expand 在 keyword 路径是死代码见 C06-08、deadline 分配策略不同见 C06-03），不是"未来可能漂移"而是"已经漂移"。OptimizationAgent 注释（:62-67）明确说"编排自己的板块感知循环，而非使用 BreadthExpander/FeedbackLoop"，证明是有意分叉。
- **修复方向**：①提取公共"优化循环引擎"抽象（接受评估器、策略生成器、终止策略、结果合并器为依赖），keyword 和 digest 各自注入不同配置（大，核心链路改动，需补两套测试）；②短期：把 keyword 路径也接入 FatigueTracker 和 source_expand（中，缩小能力差）；③最小：统一两边的 deadline 分配、收敛阈值、失败重试策略（中）。需先评估单人博客场景下两条路径是否都真在用——若 keyword 任务实际很少触发优化，可考虑废弃 keyword 路径只保留 digest（大，但消除重复）。
- **关联**：C06-08、C06-03、§9 已知线索、横向主题"重复实现"

### [P2] [Arch] source_expand 策略链在 keyword 路径完全是死代码  <!-- 编号：C06-08 -->
- **定位**：`optimization/strategy.py:388-473`（`_pick_expand_section`/`_strategy_source_expand`/`_generate_overrides`）、`optimization/bubble_breaker.py:188`（`source_crawl_fn` 参数）、`standalone/keyword_handler.py:147-160`（BreadthExpander.execute 调用未传 sections）
- **现象**：`BreadthStrategyGen.generate` 只有在 `sections` 参数非空时才会走 `source_expand` 分支（strategy.py:241 `if sections and weakest == "source_diversity"`）。但 keyword 路径调用链 `keyword_handler._run_optimization_loop → BreadthExpander.execute → breadth_gen.generate(sections=sections)` 中，`BreadthExpander.execute` 的 `sections` 参数默认 None（bubble_breaker.py:187），而 keyword_handler 调用时**没传 sections**（keyword_handler.py:153-160）。FeedbackLoop 调用 depth_gen.generate 更是根本不带 sections 参数（feedback.py 不含 "sections" 字样，已 grep 确认）。
- **影响**：strategy.py 中 `_pick_expand_section`、`_strategy_source_expand`、`_generate_overrides` 共约 85 行代码（含 effectiveness 评分、skip_source_ids 生成等逻辑）**在 keyword 路径从不执行**，只在 digest 路径（OptimizationAgent:499 传 `section_dicts`）生效。这 85 行是 source_expand 策略的核心，却在一条主路径上是死的——阅读 keyword 路径代码时会被误导以为 source_expand 可用。
- **根因/分析**：source_expand 依赖板块（PlannedSection）概念，而 keyword 任务是扁平搜索无板块，所以 keyword 路径无法提供 sections。这是 C06-07 两套循环分叉的具体体现。已排除"keyword 路径未来会接 sections"的解读——keyword_handler 无任何构造 sections 的代码。
- **修复方向**：①若 keyword 路径确实不需要 source_expand，在 BreadthStrategyGen.generate 入口加断言/日志说明"sections 为空时跳过 source_expand"，并考虑把 source_expand 相关方法移到 digest 专用模块（中）；②随 C06-07 统一循环时一并处理（大）。
- **关联**：C06-07、次维度 [Arch]（死代码）

### [P2] [Arch] eval_weight_* 6 维评估权重未纳入 backend_config 同步，Python 端独有  <!-- 编号：C06-09 -->
- **定位**：`optimization/evaluator.py:37-47`（`_get_weights` 读 settings.eval_weight_*）、`config.py:90-95`（6 个权重默认值）、`standalone/backend_config.py:166-198`（`_apply_optimization_settings`/`_apply_bubble_settings` 同步范围）
- **现象**：`optimization.enabled/mode/max_rounds/breadth_max_rounds/total_budget/min_improvement/depth_target/breadth_target` 和 `bubble.enabled` 都能从 Java 后端 sys_config 同步（backend_config.py:168-195），但 **6 个 `eval_weight_*`（angle/source/depth/temporal/perspective/language）和 `optimization_depth_weight_*`/`optimization_breadth_weight_*` 子循环权重均未同步**，只能在 Python `.env` 改。
- **影响**：管理员想调整"angle 维度权重从 0.25 降到 0.20"必须改 crawler 的 `.env` 并重启，不能像其他优化参数那样通过后端管理页热更新。三处 env（主模块 X06）之外又多一处配置漂移点。validator（config.py:227-234）保证 6 权重和为 1.0，但改了 env 后 backend 无感知。
- **根因/分析**：eval_weight_* 是评分公式权重，敏感度低于开关类配置，当初未纳入同步可能是有意。但与"optimization 子循环权重也未同步"一致，属于配置同步不完整。
- **修复方向**：①把 eval_weight_* 和子循环权重加入 `_apply_optimization_settings` 同步范围（中，需 Java 后端 sys_config 补 key + 前端配置页，跨服务）；②或明确文档化"这些权重仅 Python 端 .env 可调，不在管理端暴露"（小）。配置一致性主模块 X06 统一处理。
- **关联**：X06（配置一致性主模块）、横向主题"配置一致性"

### [P3] [Arch] strategy_detail 列语义双轨：digest 存 JSON 数组，其他存纯文本  <!-- 编号：C06-10 -->
- **定位**：`optimization/utils.py:36`（`save_optimization_round` 传 `r.strategy.reason` 纯文本）、`optimization/knowledge_base.py:358`（`save_digest_evaluation` 传 `_json.dumps(section_scores or [])` JSON 数组）
- **现象**：`optimization_record.strategy_detail` 列在两种写入路径下语义不同：普通优化轮次（utils.save_optimization_round）存策略的 `reason` 字段（纯文本，如"时效性覆盖仅 30%，扩展时间范围 week → month"）；digest 最终评估（knowledge_base.save_digest_evaluation）存 `section_scores` 的 JSON 数组字符串。
- **影响**：后续读取该列的代码（如 knowledge_base.py:388 `d["strategy_detail"] = _parse_json_list(...)`）必须同时处理纯文本和 JSON 两种情况，`_parse_json_list` 对纯文本返回 `[]`（knowledge_base.py:33-34 解析失败返回空列表），导致普通轮次的 strategy_detail 信息在 digest 趋势视图里丢失。语义混淆增加维护成本。
- **根因/分析**：save_digest_evaluation 复用了 optimization_record 表但塞了不同语义的数据。已排除"故意复用列"的解读——若故意应有列名区分或注释说明。
- **修复方向**：①save_digest_evaluation 改用专门列（如 section_scores_json）或专门表（大，schema 变更）；②或统一 strategy_detail 始终存 JSON（普通轮次存 `{"reason": "..."}`）（中，需迁移历史数据）；③最小：在 knowledge_base 读取处对纯文本 strategy_detail 做兼容标注（小，治标）。C09（表主模块）和 C07（save_digest_evaluation 主模块）协同。
- **关联**：C07、C09、横向主题"schema 漂移"

---

## `[Deps]` 依赖升级与版本

### 本模块依赖清单（基于声明文件，未翻依赖源码）

| 依赖 | 版本 | 声明位置 | 已知风险/可升级 | 备注 |
|---|---|---|---|---|
| crawl4ai | ~=0.8.6 | `crawler-service/requirements.txt:8` | 0.8 系列较新，约束 `~=0.8.6` 允许 0.8.x 补丁升级 | C06 仅间接依赖（通过 crawler.search/source_crawler），不直接 import |
| pydantic-settings | >=2.1.0 | `crawler-service/requirements.txt:20` | 无已知风险 | C06 通过 config.settings 用 |
| aiosqlite | >=0.19.0 | `crawler-service/requirements.txt:34` | 无已知风险 | C06 通过 KnowledgeBase/save_optimization_round 间接用 |

> 排查范围：C06 是纯 Python 模块，无直接第三方依赖（只用标准库 + 项目内 ai/crawler/standalone 模块）。上表列出间接相关依赖。无 C06 自身代码引入的过时/CVE 依赖。

**未发现** C06 模块级别的依赖风险。Python 版本要求（3.10+，requirements.txt:3）支撑 C06 使用的 `dict[str, list]`、`X | None` 等语法，无版本冲突。

---

## `[Design]` 功能设计合理性

> 必填。从单人维护技术博客 + 每工作日 AI 日报场景出发，回答 §2.5 相关问题。

**审视结论**：

1. **场景适配（过度设计 vs 简陋）**：C06 的 6 维评分 + 深度/广度双循环 + 跨语言翻译 + 疲劳追踪 + 知识库推荐，对"单人技术博客 + 每工作日日报"场景**明显过度设计**。这套系统本质是一个迷你搜索质量优化引擎，但真实场景是：单人维护、每天一篇日报、关键词任务偶发。6 维评分中 perspective（观点对立）和 language（跨语言）维度对技术日报价值有限——技术信息很少有"正反方辩论"，且翻译准确性无校验（C06 无条目，见下方 Design 条目）。更关键的是 **`optimization_enabled` 和 `digest_optimization_enabled` 默认都是 False**（config.py:154,197），说明作者也清楚默认不该开——这本身就是"过度设计但默认关闭"的信号。
2. **闭环完整性**：优化循环自身是闭环的（评估→策略→爬取→再评估），但**缺少人工干预入口**——优化记录写入 optimization_record 表后，管理员无法在管理端剔除某条"优化进来的低质结果"、无法手动标记某策略为有害（只能靠 FatigueTracker 自动学）、无法回滚某次优化轮次。知识库的 source_actions（C07）部分弥补，但 C06 侧的 strategy 层无人工覆盖接口。
3. **评分与优化决策耦合（关键审视）**：C06 的核心假设是"更高覆盖度分 → 更好的采集/日报"，但这个假设**未被验证**。heuristic 评分（digest 模式强制走 heuristic，evaluator.py:139）基于域名数、内容长度、年份跨度等浅层信号，可被"多爬几个低质域名"操纵（source_diversity 靠域名数、depth 靠内容长度）。优化循环会朝"提高分数"的方向补搜，但提高的是分数不是真实质量——可能出现"分数达标但日报质量没变甚至变差"的情况。无 A/B 对比或人工抽检机制来校准"分数与质量的相关性"。
4. **MVP 假设检验**：README/CLAUDE.md 声称"自动优化系统 MVP Beta"，但默认关闭、两套实现漂移（C06-07）、digest 模式强制 heuristic 不用 AI（evaluator.py:139，即使 AI 可用）、疲劳预填充是死代码（C06-04）——这些意味着**真实跑起来后优化效果存疑**。属"看起来能用实则多处在空转"的半成品状态。

### [P1] [Design] digest 模式强制走 heuristic 评分，放弃 AI 评估能力，评分可信度存疑  <!-- 编号：C06-11 -->
- **定位**：`optimization/evaluator.py:139`（`if ctx.get("task_type") == "digest": ai_eval = self._heuristic_evaluate(meta, ctx)`）
- **现象**：CoverageEvaluator.evaluate 中，只要 ctx 的 `task_type == "digest"`，**无条件走 heuristic**（`_heuristic_evaluate_digest`），即使 AI organizer 可用也不调用 `_ai_evaluate`。keyword 模式才会用 AI（:141 `elif self.is_available`）。
- **影响**：digest 是每天最重要的产物（每工作日 AI 日报），其优化决策反而依赖最粗糙的 heuristic 评分（基于域名数、内容长度、板块覆盖率）。AI 本可以判断"这批结果是否真覆盖了趋势/开源/工程多个角度"，却被禁用。导致 OptimizationAgent 的板块级弱维度识别、收敛判断都建立在浅层信号上（叠加 C06-01 的 angle 高估，偏差更大）。优化循环可能在"低质结果上反复折腾"却拿不到真实质量反馈。
- **根因/分析**：推测是性能/成本考量（digest 结果集大，AI 评估慢且费 token），或早期 heuristic 够用后来没改回来。但 digest 正是 AI 价值最高的场景（需要语义判断板块覆盖），禁用 AI 与系统设计目标矛盾。已排除"AI 不可用才回退"的解读——代码是 `if digest: heuristic` 而非 `if not ai_available: heuristic`，无条件分支。
- **建议方向**：①增加配置项 `digest_eval_use_ai: bool = False`，允许在 AI 端点稳定时打开 AI 评估（小，加配置 + 分支）；②或对 digest 全局评估用 AI、板块级用 heuristic（混合，平衡成本，中）；③至少加注释说明"为何 digest 强制 heuristic"（小）。需 [需查证] 当初是否有 benchmark 显示 AI 评估对 digest 无增益。
- **关联**：C06-01、§2.5 问题 4（MVP 假设）、横向主题"AI 空壳链路"（B13）、横向主题"评分与优化决策耦合"

### [P2] [Design] 跨语言翻译准确性无校验，错误翻译直接进入搜索  <!-- 编号：C06-12 -->
- **定位**：`optimization/bubble_breaker.py:97-118`（`translate_keyword`）、`:111-115`（仅校验目标语言字符存在）
- **现象**：`translate_keyword` 调 AI 翻译关键词，唯一校验是 `re.search(r"[a-zA-Z]{2,}", translated)`（中→英）或 `re.search(r"[一-鿿]", translated)`（英→中），即"翻译结果包含目标语言字符就接受"。无术语正确性校验、无回译校验、无长度限制。
- **影响**：AI 若把"Spring Boot"误译为"春靴"（字符校验通过，含中文），或把技术术语翻错（如"Kubernetes"→"库伯网"），错误关键词直接传给 `crawl_by_keyword` 搜索，污染结果集。虽然单次 cross_language 策略每循环最多触发一次（strategy.py:376-378 收敛保护），但一次坏翻译就会拉低整轮质量。对技术场景尤其危险——技术术语本就不该翻译，但 prompt（bubble_breaker.py:30）说"保留技术专有名词"只是软约束，AI 不一定遵守。
- **根因/分析**：跨语言翻译是"突破茧房"的好想法，但缺乏质量护栏。已排除"影响有限"的解读——`bubble_cross_language` 默认 True（config.py:176），一旦 optimization 开启就会触发。
- **建议方向**：①对含已知技术术语（维护一个术语白名单）的关键词跳过翻译（中）；②加回译校验：翻译后再翻回原语言，相似度低于阈值则丢弃（中，多一次 AI 调用）；③降低 cross_language 优先级，仅在 language 维度极低（如 <0.2）时才触发（小）。
- **关联**：§2.5 问题 1（场景适配）、次维度 [Design]

### [P4] [Design] 优化系统默认全关，"MVP Beta"宣称与默认状态不符  <!-- 编号：C06-13 -->
- **定位**：`config.py:154`（`optimization_enabled: bool = False`）、`:174`（`bubble_breaker_enabled: bool = False`）、`:197`（`digest_optimization_enabled: bool = False`）
- **现象**：C06 相关的三个总开关默认全 False。要启用 digest 优化需同时开 `optimization_enabled=True` + `optimization_mode` 含 "digest" + `digest_optimization_enabled=True` 三层。CLAUDE.md 称"自动优化系统 MVP Beta 可试用"，但默认配置下系统完全不运行。
- **影响**：新部署的用户若不细读配置，会以为优化系统已工作（日志无任何优化记录也不会报错），实际是关闭的。三层开关的叠加条件（digest_orchestrator.py:951-953）也容易配错——开了前两个忘了第三个，优化不生效且无明显提示。
- **建议方向**：①要么把 `digest_optimization_enabled` 默认改 True（让 optimization_enabled 一开就生效，小，但需评估默认开启的性能影响）；②要么在管理端/启动日志显式提示"优化系统当前关闭，需开 N 个开关"（小）；③维持现状但在 README 明确"默认关闭，需手动启用"（小，文档）。倾向于②或③，因为优化系统效果未验证（见 C06-11），默认开启有风险。
- **关联**：§2.5 问题 4（MVP 假设）、X05（文档一致性）

---

## 模块小结

### 严重度统计

| 级别 | 数量 | 条目编号 |
|---|---|---|
| P0 | 0 | — |
| P1 | 2 | C06-07, C06-11 |
| P2 | 5 | C06-01, C06-02, C06-03, C06-08, C06-09, C06-12 |
| P3 | 4 | C06-04, C06-05, C06-06, C06-10 |
| P4 | 1 | C06-13 |

> 注：C06-12 定为 P2（Design 类，影响采集质量），统计时归入 P2。上表 P2 实际 6 条（含 C06-12），P3 实际 4 条。

### Top 风险（本模块最该先看的 ≤3 条）

1. **C06-07 keyword vs digest 两套优化循环漂移** —— 已实际漂移（FatigueTracker/source_expand/死代码分布不均），不是潜在风险而是现状，任何策略改进都要改两处，维护成本翻倍且易漏。
2. **C06-11 digest 强制 heuristic 放弃 AI 评估** —— 每天最重要的日报产物反而用最粗糙的评分驱动优化决策，评分与真实质量脱节，优化可能空转。
3. **C06-01 digest 单板块评估复用全局 section_counts 致 angle 高估** —— 直接导致弱板块识别偏差，定向重爬打错维度，是当前 digest 优化效果存疑的具体技术原因之一。

### 修复优先级建议

- **立即**（P0/P1）：
  - C06-07：决定是统一两套循环还是废弃 keyword 路径（需先评估 keyword 任务优化是否真在用），这是架构级决策，影响后续所有 C06 修复方向。
  - C06-11：至少补注释说明 digest 强制 heuristic 的原因，并评估开启 AI 评估的可行性。
- **计划**（P2）：
  - C06-01：修 `_evaluate_per_section` 的 ctx 收窄（直接影响 digest 优化质量）。
  - C06-02 + C06-03：一起修 keyword 路径的基线错配和 deadline 分割（相互关联）。
  - C06-08：随 C06-07 处理 source_expand 死代码。
  - C06-09：eval_weight 纳入配置同步（跨服务，协同 X06）。
  - C06-12：跨语言翻译加护栏。
- **择机**（P3/P4）：
  - C06-04：跨运行疲劳预填充死代码（修公式或删除）。
  - C06-05：年份提取精度。
  - C06-06：round_num 冗余参数。
  - C06-10：strategy_detail 语义双轨（协同 C07/C09）。
  - C06-13：默认开关与文档对齐。

### 排查盲区 / 待复核

- **C06-11 [需查证]**：digest 强制走 heuristic（evaluator.py:139）当初是否有 benchmark 显示 AI 评估对 digest 无增益或成本过高？需查 git history 或问作者。若 AI 评估对 digest 确有增益，应视为 P1 设计缺陷。
- **C06-07 [需查证]**：keyword 任务的优化（optimization_mode 含 "keyword"）在实际部署中是否真的被触发过？若 keyword 任务优化从未实际运行，C06-02/C06-03/C06-08 的优先级可下调。需查 optimization_record 表中 task_type != "digest" 的记录数（C09 侧查询）。
- **测试覆盖盲区**：本次未逐条核对 `tests/test_optimization.py`、`test_optimization_agent.py`、`test_optimization_integration.py`、`test_bubble_breaker.py`、`test_strategy_language.py`、`test_learning_loop.py` 对上述 bug 的覆盖情况。C06-01（单 section ctx）、C06-04（预填充死代码）、C06-11（digest heuristic 强制）是否有测试覆盖，需 X03 测试体系排查确认。
- **C06-12 [需查证]**：跨语言翻译在真实运行中的错误率无统计，需查 optimization_record 中 strategy_type="cross_language" 的轮次效果（score_delta 分布）。
- **性能盲区**：optimization_total_budget_seconds=120s 在真实搜索引擎响应下能跑几轮未实测，C06-03 的 deadline 挤压严重程度需运行时观测。
