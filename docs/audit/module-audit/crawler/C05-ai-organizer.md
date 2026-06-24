# C05 AI 整理 排查报告

> **模块编号**：C05
> **排查范围**：ContentOrganizer（日报生成、板块清洗、关键词优化）、OpenAI+Anthropic 双分发、chunk 重试、清洗校验、AiSettings 配置门面
> **基线 commit**：`6ae930098405f4d0553d96a852f3345d0f39682e`
> **工作区状态**：脏（未提交改动涉及 `crawler-service/crawler/search.py`、`optimization/knowledge_base.py`、多个 test 文件；均不属于本模块 ai/organizer.py、ai/config.py、ai/utils.py，本模块三文件干净）
> **排查日期**：2026-06-24
> **排查人**：C05 排查 agent
> **状态**：完成

---

## 模块概览

**职责**：封装对 OpenAI-compatible / Anthropic messages API 的调用，把原始网页 Markdown 整理成结构化内容（单页/多页）、生成技术日报、清洗板块内容、优化/扩展搜索关键词；并对 AI 返回做 JSON 解析、字段校验、URL 去重与幻觉防护。

**关键文件**：
- `crawler-service/ai/organizer.py:1-1460` —— ContentOrganizer 主体、双分发 `_call_ai`/`_call_anthropic_ai`、`_retry_cleanup_in_chunks`、`_validate_digest`、所有 prompt、异常类
- `crawler-service/ai/config.py:1-61` —— AiSettings 门面，`__getattr__` 动态从 backend_config 读 `ai.*`，`is_configured` 兜底判断
- `crawler-service/ai/utils.py:1-73` —— `extract_json`（markdown 代码块 → raw_decode → 手工括号匹配三级回退）
- `crawler-service/config.py:104-129` —— AI 字段默认值（ai_model=qwen-plus、ai_read_timeout=90、ai_digest_max_tokens=16000 等）
- `crawler-service/standalone/backend_config.py:82-108` —— `_apply_ai_settings` 把 sys_config 的 `ai.*` 写入 settings（运行时覆盖 env/默认）

**对外接口 / 依赖**：
- 对外（被调用）：`ContentOrganizer.organize` / `organize_multiple` / `optimize_keyword` / `expand_keywords` / `generate_digest` / `clean_section_content` / `is_available`；异常类 `RateLimitError`/`TruncatedError`/`UnrecoverableError`/`InvalidOutputError`
- 调用方：`api/crawl.py:233-285`（organize/keyword 端点，有重试）、`crawler/digest_gen_agent.py:106`（generate_digest，无重试）、`crawler/crawler_agent.py:300`（clean_section_content，有超时+heuristic 回退）、`optimization/evaluator.py:296`、`optimization/bubble_breaker.py:105`（后两者直接调私有 `_call_ai`）
- 依赖：httpx（手写 HTTP，无 openai/anthropic SDK）、标准库 json/re/httpx
- 配置 key：`ai.enabled`/`ai.model`/`ai.base_url`/`ai.api_key`/`ai.max_tokens`/`ai.temperature`/`ai.read_timeout` 等（经 backend_config 从 sys_config 读）

**已读文件清单**：
- `crawler-service/ai/organizer.py` —— 通读（1460 行）
- `crawler-service/ai/config.py` —— 通读
- `crawler-service/ai/utils.py` —— 通读
- `crawler-service/config.py:90-149` —— 片段（AI 字段默认值）
- `crawler-service/standalone/backend_config.py` —— 通读（ai 配置映射 + get 优先级）
- `crawler-service/api/crawl.py:200-290` —— 片段（organize 端点重试块）
- `crawler-service/crawler/digest_gen_agent.py:100-160` —— 片段（generate_digest 调用与异常捕获）
- `crawler-service/crawler/crawler_agent.py:285-324` —— 片段（clean_section_content 调用与 heuristic 回退）
- `crawler-service/optimization/evaluator.py:280-313`、`optimization/bubble_breaker.py:90-118` —— 片段（直接调 `_call_ai`）
- `crawler-service/requirements.txt` —— 通读（确认无 openai/anthropic SDK）
- `crawler-service/.env`、`.env.example`、`deploy/.env` —— 仅 grep（AI_MODEL/AI_BASE_URL 值）

**主模块归属**：本模块深查 AI 调用链。配置 `ai.*` 经 backend_config 读取的一致性问题 → 引用 **X06**（主模块）；日报编排（digest_gen_agent 调用、超时、补救）→ 引用 **C04**；evaluator/bubble_breaker 重复调 `_call_ai` 的优化循环 → 引用 **C06**。

---

## X06-01 关联结论（AI_MODEL 实际使用与失效后果）

**结论：本模块是 AI 调用的实际执行点，X06-01 的 `deepseek-v4-pro` 无效 model 会在此处导致日报/AI 整理调用失败，确认成立。**

证据链：

1. **model 实际取值**（`organizer.py:1010`、`1069`）：`"model": self._settings.ai_model`，`ai_model` 由 `AiSettings.__getattr__`（`config.py:36-48`）经 `backend_config.get("ai.model")` 读取，而 `backend_config.get`（`backend_config.py:330-338`）优先返回 `_config_cache["ai.model"]`（即 sys_config 的 config_value）。sys_config 种子 `crawler.ai.model` 的 config_value = `deepseek-v4-pro`（`init.sql:993`、`schema.sql:956`、`V1_12:91`）。env 实测 `crawler-service/.env:4` 和 `deploy/.env:12` 也是 `deepseek-v4-pro`。**所有可达路径（backend 可达读 sys_config、backend 不可达读 env）都得到 `deepseek-v4-pro`**，仅 `.env.example` 模板是 `qwen-plus`（误导）。

2. **model 无效 → 调用失败路径**：`deepseek-v4-pro` 非 DeepSeek 官方 model（官方仅 `deepseek-chat`/`deepseek-reasoner`，X06-01 已 `[需查证]` 标注，WebSearch 佐证）。DeepSeek 端点收到未知 model → 返回 `400 Bad Request` → `_call_openai_ai`（`organizer.py:1031-1032`）命中 `400 <= status < 500` 分支 → `raise UnrecoverableError(...)`。

3. **失败后果**：
   - **日报生成**：`generate_digest`（`organizer.py:695-709`）**无任何重试**，`UnrecoverableError` 直接抛出 → `digest_gen_agent.py:123 except Exception` 捕获 → 返回 `success=False` → 日报不产出（整条日报链路失败）。
   - **单页/多页整理**：`api/crawl.py:230-248` 有 `for attempt in range(max_retries+1)`，但 `except OrganizerError: raise`（`:247-248`）会让 `UnrecoverableError`（其子类）**立即重抛不重试** → 端点返回 500。
   - **板块清洗**：`crawler_agent.py:321` 捕获后回退 heuristic（有降级，影响较小）。
   - **关键词优化/扩展**：`organize.py:639/690` 自身 `except Exception` 吞掉返回原值（有降级）。

4. **失效影响范围**：日报生成是**硬失败无降级**（digest_gen_agent 不回退 heuristic），这是最严重后果。CLAUDE.md 声称"日报生成系统 MVP Beta 可试用"，但若 model 名无效，每工作日定时任务都会失败。归 **X06-01 P1**（本模块补充"失败如何传播"的细节，model 名有效性判定与修复归 X06）。

---

## `[Bug]` 代码正确性与潜在缺陷

> 排查范围：organizer.py 全部公共方法、双分发、重试、校验、去重、解析；config.py 门面；utils.py JSON 提取。

### [P1] [Bug] `generate_digest` 无重试且无降级，AI 调用任何瞬时/可恢复错误都导致整条日报失败 <!-- 编号：C05-01 -->
- **定位**：`crawler-service/ai/organizer.py:695-709`（generate_digest）；对比 `api/crawl.py:226-248`（organize 有 RateLimit 重试）
- **现象**：`generate_digest` 只做一次 `_call_ai`，遇到 `RateLimitError`（429）、网络抖动（`httpx.HTTPError`，会被 `_call_ai` 透传为 `RuntimeError` 或 httpx 原生异常）、`TruncatedError`（finish_reason=length）都直接抛出。`digest_gen_agent.py:123` 的 `except Exception` 捕获后返回 `success=False`，无重试、无回退。
- **影响**：日报是每工作日定时的核心产出。DeepSeek 等 OpenAI-compatible 端点在高峰期频繁返回 429；一次 429 或一次网络抖动就导致当天**无日报**。`api/crawl.py` 的 organize 路径有 `RateLimitError` 重试（sleep `ai_rate_limit_backoff_ms`），但 digest 路径完全没复用这套逻辑，行为不一致。
- **根因/分析**：`generate_digest` 与 `organize` 的重试逻辑分散在调用方（crawl.py）而非 organizer 内部，digest 调用方（digest_gen_agent）没复制重试逻辑。已排除误判：`_retry_cleanup_in_chunks` 只用于 section cleanup 的"空结果重试"，与 digest 无关。
- **修复方向**：①在 organizer 内部统一封装重试（RateLimitError 退避重试 N 次），所有公共方法复用；或②digest_gen_agent 调用处补 RateLimitError 退避重试。（改动面 中）
- **关联**：[[X06-01]]（model 无效会触发 UnrecoverableError，但本条针对的是可恢复错误也不重试的设计缺陷）/ 次维度 `[Arch]` 重复实现 / 横向主题"日报可靠性"

### [P2] [Bug] `_retry_cleanup_in_chunks` 的 chunk_size 逻辑反直觉：条目越少分片越小 <!-- 编号：C05-02 -->
- **定位**：`crawler-service/ai/organizer.py:756` —— `chunk_size = 2 if len(entries) <= 8 else 3`
- **现象**：当 entries ≤ 8 时每片 2 条（最多 4 次调用），> 8 时每片 3 条。直觉上"内容多才需要更小分片避免超长"，但这里反过来——条目少反而分得更细。
- **影响**：当一次性清洗 3-8 个来源返回空触发 chunk 重试时，会拆成多次 2 条的调用，增加 AI 调用次数和 token 成本（每次调用都带 system prompt + 重复的 prompt 框架），且每片仍可能因同样原因返回空。属于次要的效率/鲁棒性问题，不阻断功能（最坏 fallback 到空 cleaned、crawler_agent heuristic 回退）。
- **根因/分析**：推测原意是"少条目时单条内容可能很长，所以分细点"，但 `_build_cleanup_prompt` 已有 `ai_section_cleanup_per_max_chars=6000` 单来源上限和 `total_budget=24000` 总预算做截断，chunk_size 与内容长度无直接关系。逻辑写反或意图不清。已排除"刻意设计"：无注释说明，且 8→3、9→3 的跳变无依据。
- **修复方向**：统一 chunk_size（如固定 3），或基于内容总长度动态决定。（改动面 小）
- **关联**：次维度 `[Design]` 可维护性

### [P2] [Bug] `_validate_digest` 的跨板块 URL 去重用 None 标记 + 下标回写，跨 section 时依赖下标本轮不变，存在脆弱性 <!-- 编号：C05-03 -->
- **定位**：`crawler-service/ai/organizer.py:1242-1300`
- **现象**：去重逻辑遍历 sections，用 `items_to_keep[prev_ii] = None`（同 section）或 `c.sections[prev_si].items[prev_ii] = None`（跨 section）标记被淘汰项，最后 `[it for it in sec.items if it is not None]` 清理。`seen_urls`/`seen_titles` 存的是 `(si, len(items_to_keep))`，即"加入时的下标"。
- **影响**：逻辑在当前数据流下能正确工作（已通读验证），但有两个脆弱点：①`len(items_to_keep)` 作为下标假设"加入后 items_to_keep 不被插入新元素直到本轮结束"——成立，但隐式；②同 section 内用 `items_to_keep[prev_ii]=None`、跨 section 用 `c.sections[prev_si].items[prev_ii]=None` 两种不同容器混用，阅读成本高，后续修改易引入 bug。当前无功能性 bug，定为可维护性 P2。
- **根因/分析**：为支持"新条目更完整则替换旧胜者"的语义，用 None 哨兵避免在遍历中增删。设计可工作但非最简。
- **修复方向**：改为两阶段——先收集所有 (section_idx, item_idx, item) 三元组打分排序，再重建 sections；或用显式 `to_drop: set`。（改动面 中）
- **关联**：次维度 `[Arch]` 可读性

### [P3] [Bug] `_parse_cleanup_response` 解析失败返回空列表，与"AI 返回合法但无内容"无法区分 <!-- 编号：C05-04 -->
- **定位**：`crawler-service/ai/organizer.py:800-817`
- **现象**：JSON 解析失败（`except (json.JSONDecodeError, ValueError): return []`）和非 list 类型（`if not isinstance(raw, list): return []`）都静默返回空 list。调用方 `clean_section_content:735` 仅凭 `if not cleaned and len(entries) > 1` 触发 chunk 重试，无法区分"AI 输出格式错"vs"AI 正确返回空数组"。
- **影响**：AI 偶发返回非 JSON（如包裹在多余文本里）时，`extract_json` 已有三级回退（utils.py）能兜底大部分，但若仍失败则静默吞掉错误信息，排障困难。`extract_json` 失败会 raise ValueError，这里 catch 后丢失原始错误。
- **根因/分析**：刻意吞异常以走 chunk 重试流程。但应至少 log warning 保留原始响应片段。
- **修复方向**：`except` 分支补 `logger.warning("[CleanupParse] %s", response[:200])`。（改动面 小）
- **关联**：次维度 `[Arch]` 可观测性

### [P3] [Bug] `_validate_source_urls` 前缀匹配可能误修正：短 URL 作为长 URL 前缀时反向覆盖 <!-- 编号：C05-05 -->
- **定位**：`crawler-service/ai/organizer.py:1368-1371`
- **现象**：前缀匹配 `next((u for u in input_urls if u.startswith(url)), None)`，若 AI 输出的 `url` 恰好是某个输入 URL 的前缀（如 AI 截断了路径），会把 `item.source_url` 改成那个更长的输入 URL。但 `u.startswith(url)` 要求输入 URL 以 AI 输出开头——若两个输入 URL 共享前缀（如同域名不同路径），可能匹配到第一个。
- **影响**：边缘场景。`next` 取第一个匹配，若输入 URL 列表顺序不确定，修正结果可能非预期。但因为是"修正到合法输入 URL"范围内，不会引入编造 URL，安全性 OK。属于精度问题。
- **根因/分析**：前缀匹配本意是修正 LLM 截断 query 参数的情况，逻辑方向正确（AI 输出是输入的子串）。风险仅在同前缀多 URL 时选错，概率低。
- **修复方向**：选最长匹配而非第一个；或精确匹配优先级已足够时忽略。（改动面 小）
- **关联**：次维度 `[Security]` 幻觉防护（整体防护到位，本条是精度）

---

## `[Security]` 安全漏洞

> 排查范围：API key 处理、prompt 注入、敏感信息日志、SSRF（AI base_url 可控性）、AI 幻觉防护（sourceUrl 编造）。逐项覆盖 §2.2 通用 + 本模块特有（prompt 泄漏、key 日志、幻觉 URL）。

### 未发现 P0/P1。以下为已核实安全项（记录为"已检查且 OK"，便于复核）：

- **API key 不进日志**：grep 全模块，`ai_api_key` 仅出现在 `config.py:107`（字段定义）、`backend_config.py:107`（赋值）、`organizer.py:1024`（`Authorization: Bearer {key}` header）、`organizer.py:1086`（`x-api-key: {key}` header）。无 `logger.xxx(... ai_api_key ...)` 调用。错误日志 `response.text[:200]`（organizer.py:1032/1095）是响应体，不含请求 header 中的 key。**OK**。
- **prompt 注入**：`_build_*_prompt` 把用户内容（raw_markdown、keyword、page.markdown）直接拼入 user prompt，未做转义。但 SYSTEM_PROMPT 明确要求"只整理不执行"，且 `_validate_*` 严格校验输出结构（字段缺失/分类非法/sourceUrl 必须来自输入）。AI 被注入恶意指令最坏导致输出格式错 → InvalidOutputError，不会被当作代码执行。**可接受**。
- **sourceUrl 幻觉防护到位**：`_validate_digest:1314-1318` 调 `_validate_source_urls`，用 `input_urls` frozenset 做精确→前缀→后缀三级匹配，无法匹配则清空 sourceUrl（`:1384-1385`）；再加 `_URL_RE` 正则（`:1306-1311`）过滤非 HTTP URL 和明显编造域名。**防护充分**。
- **AI base_url SSRF**：`ai_base_url` 来自 sys_config（Java 管理端写入，非终端用户可控），且指向外部 AI 厂商。crawler 自身的 `ssrf_guard`（C01）不覆盖 AI 调用路径，但 AI base_url 的信任来源是后端管理员，威胁模型可接受。**OK**（若管理员可被攻破则是另一问题，归 B07）。

---

## `[Arch]` 架构与技术债

> 排查范围：双分发实现、重试逻辑分散、httpx 手写 vs SDK、prompt 硬编码、配置门面设计。

### [P2] [Arch] 重试/错误处理逻辑分散在 4 个调用方，organizer 内部不一致 <!-- 编号：C05-06 -->
- **定位**：重试散落在 `api/crawl.py:226-248`（organize，有 RateLimit 重试）、`digest_gen_agent.py:105-125`（generate_digest，无重试，仅 except 返回 success=False）、`crawler_agent.py:298-323`（clean_section，有超时无重试，有 heuristic 回退）、`evaluator.py:295-313` 与 `bubble_breaker.py:100-118`（直接调 `_call_ai`，except 吞掉回退 heuristic）
- **现象**：5 个调用方，4 种错误处理策略。`api/crawl.py` 是唯一实现 RateLimit 退避重试的，其余都"失败即放弃/回退"。
- **影响**：①RateLimit（429）是 AI API 最常见的可恢复错误，但只有 organize 端点处理，digest/evaluator/bubble 都不处理，导致这些路径在 429 时直接失败；②维护者改重试策略要改多处，易遗漏（C05-01 即 digest 遗漏的后果）。
- **根因/分析**：organizer 把 `_call_ai` 设计为"裸调用、异常上抛"，把重试责任推给调用方，但调用方实现参差不齐。应在 organizer 内提供"带重试的调用"作为默认。
- **修复方向**：在 `_call_ai` 内统一封装可恢复错误（RateLimit/网络错误）的退避重试（受 `ai_max_retries` 控制），UnrecoverableError/InvalidOutputError 不重试直接抛。所有公共方法自动获益。（改动面 中）
- **关联**：[[C05-01]] / 横向主题"日报可靠性" / 次维度 `[Bug]`

### [P3] [Arch] 不使用 openai/anthropic SDK，用 httpx 手写 HTTP，需自行维护错误码/重试/兼容 <!-- 编号：C05-07 -->
- **定位**：`crawler-service/requirements.txt`（无 openai、anthropic 依赖）；`organizer.py:1008-1117` 手写 `/chat/completions` 和 `/v1/messages` 调用
- **现象**：项目用 httpx 直接 POST，自行处理状态码（429/4xx/5xx）、响应解析（choices[0].message.content vs Anthropic 的 content list）、finish_reason 映射（`length`→TruncatedError，Anthropic 的 `max_tokens`→TruncatedError）。requirements 里只有 httpx，没有官方 SDK。
- **影响**：①好处是零额外依赖、可控；②坏处是要自行跟进 OpenAI/Anthropic API 变更（如新的错误码、streaming、tool_use），错误处理比官方 SDK 简陋（如没处理 `content_filter` finish_reason、没处理 Anthropic 的 `stop_sequence`）。
- **根因/分析**：MVP 阶段刻意轻量。对当前"纯文本 chat completions"场景够用，但扩展（function calling、streaming）需引入 SDK 或继续手写。
- **修复方向**：维持现状（MVP 合理），或在未来需要 streaming/tool_use 时引入官方 SDK。（改动面 中，非必要不改）
- **关联**：`[Design]` 场景适配（见下）

### [P3] [Arch] 大量常量/prompt 硬编码在 organizer.py 单文件（1460 行），混业务逻辑与文案 <!-- 编号：C05-08 -->
- **定位**：`organizer.py:19-156`（去重常量、分类映射、别名）、`:256-472`（5 段大段 prompt）、`:168-254`（`digest_relevance_score` 的正负向词条硬编码）
- **现象**：SYSTEM_PROMPT、OUTPUT_SCHEMA、FEW_SHOT_EXAMPLE、SECTION_CLEANUP_SYSTEM_PROMPT、DIGEST_SYSTEM_PROMPT（最长，含完整示例日报）全部内联在 organizer.py。`digest_relevance_score` 的 `positive_terms`/`negative_terms`（约 50 个词条 + 权重）也硬编码。
- **影响**：调整 prompt 措辞或过滤词条需改这个 1460 行的核心文件，易误伤解析逻辑。prompt 与代码混合，阅读成本高。
- **根因/分析**：从 Java 迁移时原样保留（注释 `organizer.py:3` 说明）。MVP 可接受，但后续运营调优 prompt 会频繁碰核心文件。
- **修复方向**：把 prompt 抽到 `ai/prompts/` 独立文件（.txt 或 .py 常量模块），`digest_relevance_score` 词条抽配置。（改动面 中，非阻断）
- **关联**：`[Design]` 可运维性 / 次维度重复实现（词条表与 task_executor 的硬编码并列，归 C12）

---

## `[Deps]` 依赖升级与版本

### 本模块依赖清单（基于 `crawler-service/requirements.txt`，未翻依赖源码）

| 依赖 | 版本 | 声明位置 | 已知风险/可升级 | 备注 |
|---|---|---|---|---|
| httpx | `>=0.26.0` | requirements.txt:13 | 无固定上限，可至 0.28+ | 本模块用 `httpx.AsyncClient`/`httpx.Timeout`，API 稳定 |
| 无 openai SDK | — | — | — | **手写 HTTP 调用 OpenAI-compatible 端点**，见 C05-07 |
| 无 anthropic SDK | — | — | — | **手写 HTTP 调用 Anthropic messages API**，见 C05-07 |
| pydantic-settings | `>=2.1.0` | requirements.txt:17 | — | `config.py` Settings 基类，本模块经 AiSettings 间接用 |

> 排查范围：仅本模块直接相关的 httpx +（缺失的）openai/anthropic SDK。crawl4ai/fastapi 等非本模块职责。未命中 CVE 级风险（httpx 0.26+ 无已知高危 CVE）。

### [P4] [Deps] 未声明 openai/anthropic 官方 SDK，长期维护需评估 <!-- 编号：C05-09 -->
- **定位**：`requirements.txt`（缺 openai、anthropic）
- **现象**：见 C05-07。当前用 httpx 手写。
- **影响**：见 C05-07。非 bug，是技术选型记录。
- **根因/分析**：MVP 轻量决策。
- **修复方向**：若后续接入 streaming/function-calling，评估引入 `openai`（1.x）和 `anthropic` SDK。（改动面 大，非必要）
- **关联**：[[C05-07]]

---

## `[Design]` 功能设计合理性

**审视结论**：

1. **场景适配（§2.5-1）**：单人维护的技术博客 + 每工作日 AI 日报场景下，organizer 的功能边界（整理/清洗/生成/关键词优化）划分合理，prompt 质量高（有质量护栏、Category Quality Contract、防幻觉 sourceUrl 校验）。双分发（OpenAI vs Anthropic）覆盖主流厂商，用 base_url 后缀 `/anthropic` 切换是轻量且够用的设计。**未过度设计**。
2. **闭环完整性（§2.5-2）**：AI 调用的"失败→重试→降级"闭环不完整——digest 路径失败无降级（C05-01），日报整条不产出；clean_section 有 heuristic 回退（好）；keyword 有原值返回（好）。**digest 路径缺人工干预入口**（失败后无"用上一次成功日报"或"用 heuristic 拼凑兜底日报"的降级，整条死）。
3. **可运维性（§2.5-3）**：日志覆盖较好（每次调用记 title/duration/tokens、budget 耗尽 warning、URL 去重 info），但**无成本控制闭环**——token 计数只记录不汇总，超预算（`ai_digest_total_budget`）只在 prompt 构建时截断输入，没有"单日/单月 token 上限"的熔断；RateLimit 退避参数 `ai_rate_limit_backoff_ms=10000` 写死默认且只 organize 路径用。排障时可看日志，但无法主动控制成本。
4. **MVP 假设检验（§2.5-4）**：CLAUDE.md 声称"日报生成 MVP Beta 可试用"，但结合 X06-01（model 名无效）+ C05-01（digest 无重试无降级），**真实跑起来日报大概率失败且无优雅退化**，与"可试用"存在落差（落差主因是 X06-01 的 model，本模块的 C05-01 放大了影响）。

### [P1] [Design] digest 生成失败无任何降级/兜底，与"日报 MVP Beta 可试用"的声明存在落差 <!-- 编号：C05-10 -->
- **定位**：`digest_gen_agent.py:105-125`（调用 generate_digest 失败即返回 success=False）+ `organizer.py:695-709`（generate_digest 无重试）
- **现象**：见审视结论 2/4。digest_gen_agent 捕获 generate_digest 异常后直接失败，无"用 heuristic 拼凑最低限度日报"或"复用昨日日报"的兜底。
- **影响**：model 无效（X06-01）或 AI 端点不可达时，当天无日报且无任何产出，运营无法向用户交代。
- **建议方向**：补 digest 的 heuristic 兜底（从 cleaned 文档按规则提取标题+URL 拼最小日报），或失败时保留半成品供人工编辑。（改动面 大，涉及 C04）
- **关联**：[[X06-01]] / [[C05-01]] / 计划 §9 已知线索"日报 global timeout 后 KB 不写入"（C04/C07）

### [P4] [Design] 无 token 成本熔断/汇总，长期运营不可控 <!-- 编号：C05-11 -->
- **定位**：`organizer.py:582/599/706/734`（记录 tokens_used 但不汇总不熔断）；`config.py:128` `ai_digest_total_budget` 仅截断输入
- **现象**：每次调用记 `tokens_used` 返回给调用方，但无累计/阈值/熔断。
- **影响**：单人维护场景下，AI 费用可能因优化循环（evaluator/bubble 反复调）失控。
- **建议方向**：记录备选；MVP 可接受，未来接 token 计数 + 日预算熔断。（改动面 中）
- **关联**：[[C06]] 优化循环

---

## 模块小结

### 严重度统计

| 级别 | 数量 | 条目编号 |
|---|---|---|
| P0 | 0 | — |
| P1 | 2 | C05-01、C05-10 |
| P2 | 4 | C05-02、C05-03、C05-06、（C05-10 部分属 Design P1）|
| P3 | 4 | C05-04、C05-05、C05-07、C05-08 |
| P4 | 2 | C05-09、C05-11 |

> 注：C05-10 归 P1（Design 视角的严重度，与 C05-01 同一现象的不同维度）。

### Top 风险（本模块最该先看的 ≤3 条）

1. **C05-01 / C05-10 generate_digest 无重试无降级** —— 配合 X06-01 的无效 model，直接导致每工作日定时日报失败且无产出，是"日报 MVP 可试用"声明的最大威胁。
2. **C05-06 重试逻辑分散** —— 5 个调用方 4 种策略，digest/evaluator/bubble 都不处理 RateLimit，是 C05-01 的根因。
3. **C05-08 prompt/词条硬编码在 1460 行核心文件** —— 后续运营调优 prompt 频繁碰核心解析逻辑，可维护性隐患。

### 修复优先级建议

- **立即**（P1）：C05-01 + C05-10（给 generate_digest 补 RateLimit 退避重试 + heuristic 兜底）—— 但前置依赖 X06-01 修好 model 名，否则重试也救不回 400 UnrecoverableError。
- **计划**（P2）：C05-06（重试逻辑下沉到 organizer）、C05-02（chunk_size 修正）、C05-03（去重逻辑重构）。
- **择机**（P3/P4）：C05-04/C05-05（精度与日志）、C05-07/C05-09（SDK 引入评估）、C05-08（prompt 抽离）、C05-11（成本熔断）。

### 排查盲区 / 待复核

- **`deepseek-v4-pro` 实际 API 行为 `[需查证]`**：本模块确认了"若无效则走 400→UnrecoverableError→digest 失败"的代码路径，但 model 名是否真无效需真实 API 验证（归 X06-01，受 §1.3 外网禁令未执行）。
- **DeepSeek 端点 `/chat/completions` vs `/v1/chat/completions` `[需查证]`**：`.env` 的 `AI_BASE_URL=https://api.deepseek.com`（无 /v1），sys_config 是 `https://api.deepseek.com/v1`（有 /v1），organizer 拼成 `{base_url}/chat/completions`。DeepSeek 官方文档用 `/chat/completions`（/v1 可选），但 env 与 sys_config 的 base_url 不一致是另一配置漂移点，归 X06。
- **py_compile 未完成**：受 Bash 工具超时限制，未对 organizer.py 跑语法检查；已通读全文未发现语法问题，[需查证] 可在解除工具限制后补 `python -m py_compile`。
- **Anthropic 路径未实测**：`_call_anthropic_ai` 的 base_url 判断（`/anthropic` 后缀）与 DeepSeek/qwen 默认配置不匹配（两者都不以 `/anthropic` 结尾），实际部署是否有人用 Anthropic 分发未确认，`tests/test_ai_extreme.py:146` 有 mock 测试但无真实端点验证。
