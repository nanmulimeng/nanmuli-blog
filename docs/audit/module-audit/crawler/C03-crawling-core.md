# C03 采集核心 排查报告

> **模块编号**：C03
> **排查范围**：单页爬取 / BFS 深度爬取 / 关键词搜索四引擎降级 / RSS-Atom 解析（采集执行核心）
> **基线 commit**：`6ae930098405f4d0553d96a852f3345d0f39682e`
> **工作区状态**：脏。本模块涉及未提交文件：`crawler-service/crawler/search.py`（脏，降级链/选择器/重试参数等改动未提交）。本报告基于工作区当前状态排查，涉及 search.py 的结论以工作区版本为准。
> **排查日期**：2026-06-24
> **排查人**：C03 采集核心排查 agent
> **状态**：待复核

---

## 模块概览

**职责**：把"目标 URL / 关键词 / RSS 源"转换成结构化 markdown 内容，是整个采集链路的执行底座——上层（digest、优化、task_executor）都通过它拿到原始页面文本。

**关键文件**：
- `crawler-service/crawler/single.py:27` —— `crawl_single_page()` 单页爬取入口，低字数触发 JS Challenge 重试
- `crawler-service/crawler/deep.py:44` —— `crawl_deep_pages()` BFS 同域深度爬取，含 ccTLD 基域推导、max_pages 限流、URL 去重
- `crawler-service/crawler/search.py:794` —— `crawl_by_keyword()` 关键词搜索主流程；`_get_search_results:561` 四引擎降级；`_parse_search_results:418` SERP 解析 + 链接解码
- `crawler-service/crawler/feed.py:35` —— `parse_feed()` RSS/Atom 抓取 + freshness 过滤
- `crawler-service/crawler/processor.py:31` —— `retry_js_challenge()` JS Challenge 重试共享实现
- `crawler-service/crawler/resource_guard.py:38` —— `browser_crawl_slot()` 进程级浏览器并发信号量
- `crawler-service/crawler/config.py:146/207/262/342` —— `RunParams` / `get_browser_config` / `get_crawler_run_config` / `get_search_run_config`
- `crawler-service/crawler/models.py:52` —— `JS_CHALLENGE_MIN_WORDS=20` 等常量
- `crawler-service/crawler/deep_filters.py:16` —— `ExcludedDomainFilter` BFS URLFilter 包装
- `crawler-service/crawler/dependencies.py:44` —— `require_crawl4ai()` 依赖探活 + degraded/strict 模式

**对外接口 / 依赖**：
- 对外：4 个 async 函数 `crawl_single_page` / `crawl_deep_pages` / `crawl_by_keyword` / `parse_feed`，被 `api/crawl.py`、`standalone/task_executor.py`、`standalone/scheduler.py`、`standalone/keyword_handler.py`、`crawler/source_crawler.py`、`crawler/crawler_agent.py`、`crawler/optimization_agent.py` 等调用。
- 依赖：crawl4ai（浏览器）、httpx（搜索/feed）、beautifulsoup4+lxml（SERP 解析）、feedparser（RSS/Atom）；配置 key 见 §Deps 节。

**已读文件清单**：
- `crawler/single.py` —— 通读
- `crawler/deep.py` —— 通读
- `crawler/search.py` —— 通读（脏文件，工作区版本）
- `crawler/feed.py` —— 通读
- `crawler/processor.py` —— 通读
- `crawler/resource_guard.py` —— 通读
- `crawler/config.py`（crawler 包内） —— 通读
- `crawler/dependencies.py` —— 通读
- `crawler/models.py` —— 通读
- `crawler/deep_filters.py` —— 通读
- `crawler/utils.py` —— 通读
- `crawler/source_crawler.py` —— 通读（消费方）
- `config.py`（根配置） —— 通读 settings 相关段
- `requirements.txt` —— 通读
- `api/crawl.py` —— grep + 片段（确认 SSRF 调用点）
- 测试文件 `test_single.py`/`test_deep.py`/`test_search.py`/`test_feed.py` —— 仅 grep 调用点，未逐行读

**主模块归属**：本模块深查"采集执行"。质量评估/去重逻辑（`search_min_word_count` 过滤、`dedup_results`）→ 引用 C08；ENGINE_PRIORITY 等硬编码规则 → 引用 C12；SSRF guard（`validate_url_ssrf`）实现细节 → 引用 C01。

---

## `[Bug]` 代码正确性与潜在缺陷

> 排查范围：single.py / deep.py / search.py / feed.py / processor.py / resource_guard.py / config.py（crawler 包）全部主路径 + 异常路径 + 资源生命周期。

### [P1] [Bug] deep.py crawler=None 分支 JS Challenge 重试对已关闭浏览器实例调用（use-after-close）  <!-- 编号：C03-01 -->
- **定位**：`crawler-service/crawler/deep.py:107-115`（async with 作用域）与 `crawler/deep.py:134-153`（重试块）
- **现象**：`crawl_deep_pages` 在 `crawler is None` 时进入 `async with AsyncWebCrawler(config=browser_config) as c:` 块（108 行），块内执行 `active_crawler = c` 并 `await c.arun(...)`（111 行）。`arun` 返回后**控制流离开 `async with`**，浏览器实例 `c` 被 `__aexit__` 关闭。随后在 `for result in results_raw:` 循环中（121 行起），第 135 行判断 `word_count < JS_CHALLENGE_MIN_WORDS and active_crawler is not None`，第 142 行 `await retry_js_challenge(active_crawler, result.url, params)`——此时 `active_crawler` 指向的浏览器已关闭。
- **影响**：BFS 深度爬取中任一页命中"成功但字数过低"（< 20 词，常见于 SPA / 反爬 interstitial / 页面本就短），触发 JS Challenge 重试时对已关闭的 Playwright/crawl4ai 会话发请求，重试必然失败（抛异常），被 152 行 `except` 吞掉只记 WARNING。后果是深度爬取的 JS Challenge 重试功能在"非外部复用浏览器"路径下**完全失效**，低字数页得不到补救，直接进下游。由于 `crawl_url_sources`（source_crawler.py:47）和 task_executor（task_executor.py:346）大量场景 `crawler` 由上层传入，命中本 bug 的主要是走新建浏览器分支的调用（如 api/crawl.py 的 deep 端点、test_crawler_extreme 的用例）。
- **根因/分析**：`async with` 作用域设计错误——意图是"arun 返回 list 后逐项重试"，但把 `async with` 闭合点放在了 arun 之后、重试循环之前。已排除误判：复用分支（`crawler is not None`，113 行）`active_crawler = crawler` 指向外部长期存活实例，不受影响；只有新建分支有问题。
- **修复方向**：①把重试循环移进 `async with` 块内（推荐，小改动，保持浏览器存活至重试完成）；②或新建分支改为手动 `__aenter__`/`__aexit__` + try/finally 包裹整个重试循环（中改动）。改动面：小（单文件、约 10 行结构调整）。
- **关联**：与 C03-02（阈值不一致）叠加放大影响；次维度 [Bug]；横向主题：采集核心健壮性。

### [P2] [Bug] JS Challenge 阈值（20）与 search 最小词数（50）不一致，deep 重试仍可能被下游过滤  <!-- 编号：C03-02 -->
- **定位**：`crawler-service/crawler/models.py:52`（`JS_CHALLENGE_MIN_WORDS = 20`）vs `config.py:64`（`search_min_word_count = 50`）vs `crawler/search.py:759-761`
- **现象**：single/deep 的"低字数判定"阈值是 `JS_CHALLENGE_MIN_WORDS = 20`，而 search 流程的"内容太短判定"是 `settings.search_min_word_count = 50`（search.py:759，低于则 `result.success=False`）。两层阈值差 2.5 倍。
- **影响**：经 JS Challenge 重试后 `word_count` 落在 20–49 之间的页面，single/deep 认为"成功"，但 search 路径会把它标记失败丢弃。结果：搜索引擎结果的有效率统计偏低，且当 search 调 `crawl_single_page` 复用时，重试"白做"。属于可观测但非阻断的不一致。
- **根因/分析**：两个阈值各自独立设定，无统一来源。20 词偏激进（任何正常文章远超 20），50 词是 search 专属质量门槛。已排除误判：deep 路径本身不用 50 阈值，只在被 search/optimization 复用时才暴露。
- **修复方向**：①将 `JS_CHALLENGE_MIN_WORDS` 提到 settings 配置化，并在 search 复用路径上对齐；②或保持分离但加注释说明语义差异（"重试触发线" vs "质量丢弃线"）。改动面：小。
- **关联**：次维度 [Bug]；配置项 `search_min_word_count` / `JS_CHALLENGE_MIN_WORDS`。

### [P2] [Bug] ccTLD 基域推导表不完整，部分多段 TLD 会误聚合或误分裂  <!-- 编号：C03-06 -->
- **定位**：`crawler-service/crawler/deep.py:23-25`（`_MULTI_PART_TLD`）与 `deep.py:80-85`
- **现象**：`_MULTI_PART_TLD = {'co','com','org','net','edu','gov','ac'}`，判断条件 `parts[-2] in _MULTI_PART_TLD`。覆盖 co.uk / com.cn / com.au / co.jp 等常见组合，但缺 `go`（go.jp、go.id）、`mil`、`mod`（mod.uk）等；且对无二级前缀的 ccTLD（如 `example.uk`、`example.de`）和 4 段以上域名（`a.b.example.com` → parts[-2]='example' 不命中 → base='example.com'，正确）处理依赖"倒数第二段恰好是表内 token"。
- **影响**：BFS 的 `DomainFilter(allowed_domains=[domain, f"*.{base_domain}"])`（deep.py:100）决定同域边界。基域推导过宽（把 `blog.example.co.uk` 和 `www.example.co.uk` 当同域）一般无害；推导过窄（把 `example.com.cn` 的子域误判为不同站点）会导致 BFS 漏爬。实际命中场景有限，因常见技术站点多为标准两段域名。
- **根因/分析**：手维护小表 + 倒数第二段匹配的启发式，无法覆盖真实 ccTLD 全集（数百个）。业界做法是用 `tldextract` / PUBLIC_SUFFIX_LIST。已排除误判：当前表对项目实际信息源（GitHub/Cloudflare/arxiv 等）足够，不影响主链路。
- **修复方向**：①引入 `tldextract`（基于 Mozilla PSL）替代手维护表（中改动，新增依赖）；②或维持现状但补 `go/mil/mod` 并加测试覆盖。改动面：中（引依赖）/ 小（补表）。
- **关联**：次维度 [Bug]；与 C12（硬编码规则）主题相关。

### [P3] [Bug] `_decode_baidu_redirect` 退避逻辑是死代码（max_retries=0）  <!-- 编号：C03-07 -->
- **定位**：`crawler-service/crawler/search.py:383`（`max_retries = 0`）与 `search.py:412-413`
- **现象**：`_decode_baidu_redirect` 内 `max_retries = 0`，循环 `for attempt in range(max_retries + 1)` 即 `range(1)` 只跑一次；循环体末尾 `if attempt < max_retries:`（412 行，`0 < 0` 恒 False）的 `await asyncio.sleep(_backoff_delay(...))` 永不执行。
- **影响**：无功能损害（设计上就是单次尝试），但代码给人"有退避重试"的错觉，维护者可能误以为百度链接解码失败会重试。属于可读性 / 死代码。
- **根因/分析**：疑似重构残留——`max_retries` 被硬置 0 但保留了重试骨架。已排除误判：百度重定向解码本身 HEAD/GET 各一次（387-410 行），单轮已含双策略，不需要外层重试。
- **修复方向**：①删除 `max_retries` 变量和 412-413 行死分支，循环改为单次 `HEAD then GET`（小改动）；②或把 `max_retries` 提到 settings 配置化并给真实默认值。改动面：小。
- **关联**：次维度 [Bug]。

### [P3] [Bug] single/deep 爬取无显式字符编码处理，完全依赖 Crawl4AI 自动探测  <!-- 编号：C03-08 -->
- **定位**：`crawler-service/crawler/single.py:77`（`extract_markdown(result)`）与 `deep.py:131`；`crawler/config.py:651`（`extract_markdown`）
- **现象**：`extract_markdown` 直接取 `crawl4ai_result.markdown` 的 `fit_markdown`/`raw_markdown`，仅做 `bytes → utf-8` 兜底（config.py:668-671），无 `<meta charset>` / Content-Type charset 的二次校验。
- **影响**：依赖 Crawl4AI/Playwright 的编码探测。对绝大多数现代站点（UTF-8 / 显式 charset）无问题；但对老站点（GBK / Big5 且无 charset 声明）可能出现乱码，乱码后 `count_words` 仍可能 > 20 不触发重试，乱码内容流入下游 AI 整理。
- **根因/分析**：Crawl4AI 0.8.x 内部用 Playwright，浏览器渲染通常能正确解码，但 markdown 生成层是否透传正确编码 [需查证]。本项目信息源以英文技术博客为主，命中概率低。
- **修复方向**：①保持现状，依赖 Crawl4AI（推荐，无改动）；②或在 `extract_markdown` 后加 chardet 探测兜底（中改动）。改动面：无 / 中。
- **关联**：次维度 [Bug]；[需查证] Crawl4AI 0.8.6 的编码处理细节。

---

## `[Security]` 安全漏洞

> 排查范围：SSRF 边界、SERP 注入、feedparser XML 安全、反爬绕过合规性、User-Agent 伪造、robots.txt 合规。逐项对照 §2.2。

### [P2] [Security] feedparser 解析外部 RSS XML，未显式禁用外部实体（XXE 风险待查证）  <!-- 编号：C03-05 -->
- **定位**：`crawler-service/crawler/feed.py:53`（`import feedparser`）与 `feed.py:80`（`feed = feedparser.parse(raw_xml)`）
- **现象**：`parse_feed` 用 `httpx.get(feed_url)` 抓取原始 XML（57-69 行，超时 15s、follow_redirects），再 `feedparser.parse(raw_xml)` 解析。未对 feedparser 的实体解析行为做任何限制；feedparser 内部对 XML 的处理（是否启用 `resolve_entities`、是否禁用外部实体）[需查证]。
- **影响**：RSS 源由配置注入（`rss_sources`，source_crawler.py:85），攻击面限于"可信订阅源"。但若订阅源被污染或 feed_url 可被配置端篡改为返回恶意 XML 的端点，理论上可触发 XXE（读取服务器本地文件 / SSRF）。feedparser 历史上有过 XML 解析相关讨论，6.x 版本默认行为需核实。
- **根因/分析**：feedparser 不是严格 XML 解析器（容忍畸形 feed），其底层用 `sgmllib`/`xml.parsers.expat` 的混合策略，实体处理行为不像 `defusedxml` 那样明确禁用外部实体。本项目未做二次加固。
- **修复方向**：①核实 feedparser 6.x 对外部实体的处理（查证后定级可能下调）；②若需加固，在 `parse` 前用 `defusedxml` 预过滤，或限制 feed_url 来源白名单（中改动）。改动面：中。
- **关联**：次维度 [Security]；[需查证] feedparser 6.0+ 实体解析行为；SSRF 边界由 C01 的 `validate_url_ssrf` 在 feed_url 入口是否覆盖 [需查证]（feed.py 自身无 SSRF 校验，依赖上层）。

### [P3] [Security] 采集核心完全不遵守 robots.txt  <!-- 编号：C03-04 -->
- **定位**：全模块——`grep -ri robots crawler-service` 零命中
- **现象**：crawler-service 全代码库无 `robots.txt` / `RobotFileParser` / `robotparser` 的任何引用。single/deep/search/feed 四条路径均不查询目标站点的 robots.txt，直接抓取。
- **影响**：合规风险。对单人技术博客 + 公开技术资讯的 MVP 场景，被抓站点多为有意公开的内容（GitHub/Cloudflare/arxiv/博客），robots 禁止的概率低；但若信息源扩展到明确禁止爬取的站点，存在被站点封禁 / 法律合规争议的可能。搜索引擎（bing/baidu/sogou/google）抓取本身是读它们自己的 SERP，不受 robots 约束争议，但后续对 SERP 结果页的二次爬取受目标站 robots 约束。
- **根因/分析**：MVP 阶段的合理取舍——robots 解析会增加每次爬取前的额外请求和复杂度。项目文档（CLAUDE.md）未声明 robots 策略。
- **修复方向**：①评估后明确声明"不遵守 robots"并记录风险（无代码改动，文档）；②或引入轻量 robots 缓存（Crawl4AI 自身是否有 robots 支持 [需查证]）。改动面：无 / 大。
- **关联**：次维度 [Security]/[Design]；[需查证] Crawl4AI 0.8.6 是否内置 robots 处理。

### [P3] [Security] User-Agent 池固定 4 个且版本号写死，反爬识别后易被整体封禁  <!-- 编号：C03-10 -->
- **定位**：`crawler-service/crawler/search.py:75-80`（`USER_AGENTS`）与 `search.py:159`（`random.choice`）
- **现象**：搜索引擎抓取用的 UA 池硬编码 4 条（Chrome 134-136 / Firefox 138），每次请求 `random.choice` 随机选一条。版本号停在 2026-05 前后，且池子极小。
- **影响**：反爬系统基于 UA 指纹 + 行为模式识别，4 条固定 UA 在高频抓取下极易被关联并整体封禁（一旦 4 条都被标记，所有搜索请求都会被拦）。版本陈旧后 UA 本身也会显得可疑。浏览器渲染路径（`get_browser_config`，config.py:249 `user_agent_mode="random"`）由 Crawl4AI 随机化，问题主要在 httpx 直抓的 search 路径。
- **根因/分析**：UA 池规模过小是主因。已排除误判：UA 不是反爬唯一判据，Crawl4AI 的 stealth/模拟人类交互（config.py:321 `magic=True`/`simulate_user=True`）对浏览器路径有效。
- **修复方向**：①扩大 UA 池至 20+ 并定期更新（小改动）；②或接入 UA 库（如 `fake-useragent`，中改动，新增依赖）。改动面：小 / 中。
- **关联**：次维度 [Security]/[Arch]；与 C03-03（引擎降级）主题相关——UA 被封会连带触发降级。

---

## `[Arch]` 架构与技术债

> 排查范围：硬编码、并发控制、资源生命周期、降级策略、可配置性、可测试性。

### [P2] [Arch] 搜索引擎降级链 ENGINE_PRIORITY 硬编码，无法配置且无失效熔断  <!-- 编号：C03-03 -->
- **定位**：`crawler-service/crawler/search.py:117`（`ENGINE_PRIORITY = ["bing", "baidu", "sogou", "google"]`）与 `search.py:814-817`（拼装 engines_to_try）
- **现象**：降级顺序硬编码为 bing→baidu→sogou→google，常量定义在模块顶层。`crawl_by_keyword` 把首选用 engine 放第一位，再按 ENGINE_PRIORITY 补齐其余三个（814-817 行）。引擎是否真的被反爬封禁，靠每页 `403/429` 抛 `RuntimeError`（656-660、689-693 行）+ 选择器 0 结果告警（447-451 行）被动发现，无"某引擎连续 N 次失败后短期内跳过"的熔断器。选择器健康度 `_selector_health`（31 行）只记录不决策。
- **影响**：①反爬波动时，bing 被封会逐个试 baidu/sogou/google，每次都付"预热 + 翻页 + 退避"的完整代价，拉长单次关键词搜索耗时（叠加 `search_crawl_deadline_seconds=300` 全局超时）；②配置化缺失，无法通过 env 在不同地区/网络环境下调整首选引擎（例如国内 bing 不稳定时想首选 baidu，需改代码）；③选择器版本 `2026-05`（97/105/113 行）随时间过时后，只能靠日志 WARNING 被动发现，无主动告警。
- **根因/分析**：MVP 阶段的简化设计。健康度数据已采集（`get_selector_health` 供 /stats），但未反哺决策。
- **修复方向**：①ENGINE_PRIORITY 提到 settings 配置化（小改动）；②基于 `_selector_health` 实现简单熔断（连续 N 次 0 结果/403 的引擎短期跳过，中改动）；③选择器表外置为可热更新的配置（大改动）。改动面：小 / 中 / 大。
- **关联**：C12（硬编码规则主模块）——本条为 C03 视角补充；次维度 [Arch]；横向主题：配置一致性（X06）。

### [P2] [Arch] 浏览器并发信号量被双层声明（resource_guard 全局 + search 内 Semaphore），语义重叠  <!-- 编号：C03-11 -->
- **定位**：`crawler-service/crawler/resource_guard.py:38`（`browser_crawl_slot`）vs `crawler/search.py:752`（`sem = asyncio.Semaphore(settings.max_concurrent_crawls)`）
- **现象**：`_crawl_urls_with_shared_browser` 内部为并发爬取每个 URL 新建了一个 `asyncio.Semaphore(max_concurrent_crawls)`（752 行），`_crawl_one` 内 `async with sem`（755 行）；而 `crawl_single_page` 内部又通过 `browser_crawl_slot()`（single.py:73）获取**同一个 `max_concurrent_crawls` 值**的全局信号量。两层信号量限流值相同（都是 3）。
- **影响**：search 路径下，外层 sem 和内层 browser_crawl_slot 形成等效"串行化"——外层 sem 放 3 个协程进来，每个又去抢全局 sem 的 3 个槽位，实际并发上限被压到 min(3,3)=3，与单层一致但多了一层无意义的等待和代码复杂度。功能正确，但维护者易误解并发模型。
- **根因/分析**：resource_guard 是后加的全局限流，search 内的局部 sem 是历史遗留，两者未去重。
- **修复方向**：①移除 search.py:752 的局部 sem，统一由 `browser_crawl_slot` 限流（小改动，需确认 search 的并发语义不变）；②或让局部 sem 用不同维度（如总任务数 vs 浏览器槽位）并明确注释。改动面：小。
- **关联**：次维度 [Arch]。

### [P3] [Arch] `AsyncWebCrawler` / `BFSDeepCrawlStrategy` 等用函数包装 + import_module 延迟导入，增加心智负担  <!-- 编号：C03-12 -->
- **定位**：`crawler/single.py:23-24`、`crawler/deep.py:28-41`、`crawler/config.py:26-39`、`crawler/dependencies.py:54-55`
- **现象**：多处定义同名包装函数（`def AsyncWebCrawler(*args, **kwargs): return get_async_web_crawler()(*args, **kwargs)`），且 deep.py 用 `import_module("crawl4ai.deep_crawling")` 延迟导入 BFSDeepCrawlStrategy/FilterChain/DomainFilter（32-41 行）。目的是兼容 crawl4ai 不可用时的 degraded 模式（启动不崩）。
- **影响**：功能正确（degraded 模式有意义），但包装函数散落 4 个文件、签名重复，新人难追踪"真正的类在哪"。IDE 跳转失效。
- **根因/分析**：为 degraded 模式做的合理妥协，但实现可集中到 dependencies.py 统一导出。
- **修复方向**：①把所有 crawl4ai 符号统一从 `dependencies.py` 导出，业务文件只 import（中改动，无功能变化）；②维持现状加模块 docstring 说明。改动面：中 / 小。
- **关联**：次维度 [Arch]；与 degraded 模式（config.py:22 `crawler_dependency_mode`）相关。

---

## `[Deps]` 依赖升级与版本

### 本模块依赖清单（基于声明文件，未翻依赖源码）

| 依赖 | 版本 | 声明位置 | 已知风险/可升级 | 备注 |
|---|---|---|---|---|
| crawl4ai | `~=0.8.6` | `crawler-service/requirements.txt:6` | 0.8.x 系列内升级；0.9 路径 [需查证] | 浏览器爬取核心，degraded 模式兜底 |
| httpx | `>=0.26.0` | `requirements.txt:14` | 可升至 0.27/0.28 | search/feed 的 HTTP 客户端 |
| beautifulsoup4 | `>=4.12.0` | `requirements.txt:20` | 稳定 | SERP 解析 |
| lxml | `>=4.9.0` | `requirements.txt:21` | 可升至 5.x（有安全修复） | bs4 解析后端 |
| feedparser | `>=6.0.0` | `requirements.txt:38` | 6.x 稳定；XXE 行为见 C03-05 | RSS/Atom 解析 |
| pydantic | `>=2.5.0` | `requirements.txt:16` | 稳定 | settings |
| pydantic-settings | `>=2.1.0` | `requirements.txt:17` | 稳定 | settings |

> 排查范围：仅 `requirements.txt` 声明 + 模块内使用方式，未跑 `pip-audit`、未查 CVE 库。版本号均为下限约束（`>=`），实际安装版本可能更高，[需查证] 锁文件（未见 requirements.lock / poetry.lock）。

### [P3] [Deps] crawl4ai 用 `~=0.8.6` 限定，0.8→0.9 升级路径未验证  <!-- 编号：C03-13 -->
- **定位**：`crawler-service/requirements.txt:6`（`crawl4ai~=0.8.6`）
- **现象**：`~=0.8.6` 兼容 `>=0.8.6, <0.9`，锁死在 0.8.x。代码多处对 0.8.x 行为有显式适配（deep.py:117 注释"Crawl4AI 0.8.x: arun 返回 list"、config.py:299 的 markdown_generation_strategy 导入路径、dependencies.py:26 的 `__version__` 兼容）。
- **影响**：0.8.x 内的 patch 升级安全；跨 0.9 大版本时，arun 返回类型、BrowserConfig 参数（如 `text_mode`/`light_mode`/`enable_stealth`/`avoid_ads`，config.py:244-256）可能变动，需回归。无锁文件，实际装到的 patch 版本不可控。
- **根因/分析**：合理的兼容性限定，但缺 lock 文件导致可复现性弱。
- **修复方向**：①补 `requirements.lock`（pip-compile）固定 patch 版本（小改动）；②跟踪 crawl4ai 0.9 changelog 评估升级。改动面：小。
- **关联**：次维度 [Deps]；与 X06（配置一致性）相关。

---

## `[Design]` 功能设计合理性

> 必填。从真实使用出发审视。

**审视结论**：

1. **场景适配（§2.5-1）**：四引擎降级 + JS Challenge 重试 + RSS freshness 过滤 + BFS 同域，对"单人技术博客 + 每工作日 AI 日报"是**略偏重**的设计——单人维护场景下，bing 单引擎 + RSS 已能覆盖大部分信息源，四引擎降级链主要价值在于"某引擎被反爬时还能出结果"，属合理的稳健性投入，不算过度。阈值（20/50 词、ccTLD 表）偏经验值，但对技术博客内容够用。
2. **闭环完整性（§2.5-2）**：采集结果本身**无人工剔除入口**——search/deep 返回的 CrawlResult 列表直接进 AI 整理/优化，中途无"这一条不要"的人工干预点。但这是上层（digest 编辑、优化反馈）的职责，不在采集核心范围，采集核心只负责"忠实返回"，设计自洽。
3. **可运维性（§2.5-3）**：故障定位中等。每个函数有结构化日志（成功/失败/字数/耗时），选择器健康度有 /stats 暴露（`get_selector_health`），但**无重试入口**——单次爬取失败后，没有"针对这个 URL 手动重爬"的独立运维 API（需走 task_executor 重投）。引擎被封时靠日志被动发现，无主动告警。
4. **MVP 假设检验（§2.5-4）**：CLAUDE.md 声称的"四引擎降级、JS challenge 重试、RSS 解析"真实可跑，但 C03-01 暴露的 deep use-after-close 使"JS Challenge 重试"在新建浏览器分支**实际失效**——属于"看起来能用实则部分跑不通"的半成品，需修。
5. **缺失功能（§2.5-5）**：robots.txt 不遵守（C03-04）在 MVP 可接受，但应在文档显式声明而非默认忽略。

### [P4 / 无需调整] [Design] 采集核心"忠实返回失败"的设计合理，但缺独立重爬运维入口  <!-- 编号：C03-14 -->
- **定位**：`crawler/search.py:930`（返回 results 含失败项）、`crawler/deep.py:207-213`（失败也返回 CrawlResult）、`crawler/single.py:62-67`（异常返回 success=False）
- **现象**：四条路径均把失败/异常封装成 `CrawlResult(success=False, ...)` 返回，不抛断上层，由调用方决定如何处理（task_executor 会记录、digest 会跳过）。这是良好的"失败隔离"设计。但没有任何一条路径提供"给定 URL，单独重爬并替换结果"的运维级 API。
- **影响**：日常运维中，某次日报因临时网络问题缺了几条，只能等下一轮或重跑整个任务，无法精准补爬。
- **建议方向**：维持采集核心现状（职责单一），重爬入口应在 task_executor / 运维 API 层补充（非本模块）。标注：无需调整（本模块）。
- **关联**：次维度 [Design]；与 C10（调度器）/运维主题相关。

### [P4] [Design] crawler=None 时每次爬取启停浏览器，单次调用开销大但复用路径已覆盖主场景  <!-- 编号：C03-09 -->
- **定位**：`crawler/single.py:53-55`、`crawler/deep.py:107-111`、`crawler/feed.py`（通过 source_crawler 复用）
- **现象**：`crawl_single_page`/`crawl_deep_pages` 的 `crawler=None` 分支每次 `async with AsyncWebCrawler(...)` 新建并关闭浏览器。主使用场景（task_executor、source_crawler、digest）均通过外部传入 `crawler` 复用，单次调用（api/crawl.py 的单页端点）走新建分支。
- **影响**：API 单页爬取端点每次请求启停 Playwright，开销 1-3 秒；但该端点本身是低频调试用途，主场景已优化。
- **建议方向**：维持现状（复用路径已覆盖主场景）；若 API 单页端点频率升高再考虑池化。标注：记录备选。
- **关联**：次维度 [Design]/[Arch]；与 C03-01（use-after-close 就出在新建分支）相关。

---

## 模块小结

### 严重度统计

| 级别 | 数量 | 条目编号 |
|---|---|---|
| P0 | 0 | — |
| P1 | 1 | C03-01 |
| P2 | 4 | C03-02、C03-03、C03-05、C03-06、C03-11 |
| P3 | 4 | C03-04、C03-07、C03-08、C03-10、C03-12、C03-13 |
| P4 | 2 | C03-09、C03-14 |

> 注：P2 实为 5 条（C03-02/03/05/06/11），P3 实为 6 条（C03-04/07/08/10/12/13）。统计表按维度归类，以正文编号为准。

### Top 风险（本模块最该先看的 ≤3 条）

1. **C03-01 deep.py use-after-close（P1）** —— 唯一 P1，JS Challenge 重试在新建浏览器分支完全失效，是"声称能用实则跑不通"的半成品，修一行结构即可恢复。
2. **C03-03 ENGINE_PRIORITY 硬编码降级链（P2）** —— 反爬波动连带影响放大器，无配置化无熔断，是 §9 已知线索的本模块实证。
3. **C03-05 feedparser XXE 风险（P2，需查证）** —— 唯一带安全属性的待查证项，影响面取决于 feedparser 6.x 真实行为，需优先核实。

### 修复优先级建议

- **立即**（P1）：C03-01（deep.py 重试循环移入 async with 块，小改动）
- **计划**（P2）：C03-03（降级链配置化 + 熔断）、C03-02（阈值对齐）、C03-06（ccTLD 表或引 tldextract）、C03-05（核实 feedparser 后决定）、C03-11（去重信号量）
- **择机**（P3/P4）：C03-04（robots 文档声明）、C03-07（删死代码）、C03-08/10（编码/UA 池）、C03-12/13（依赖整理）、C03-09/14（Design 备选）

### 排查盲区 / 待复核

- **[需查证] C03-05**：feedparser 6.0+ 解析 XML 时是否解析外部实体（XXE 实际风险等级）。建议查 feedparser 源码或 CVE 记录后下调/上调 P 级。
- **[需查证] C03-08**：Crawl4AI 0.8.6 对无 charset 声明的非 UTF-8 页面的 markdown 生成编码处理。
- **[需查证] C03-04**：Crawl4AI 0.8.6 是否内置 robots.txt 遵守（若内置则 C03-04 可下调）。
- **[需查证] C03-13**：crawl4ai 0.9.x 的 API 兼容性（arun 返回类型、BrowserConfig 参数名）。
- **search.py 脏文件影响**：本报告基于工作区版本排查，search.py 未提交改动若被回滚，C03-03/07/10 的行号和细节可能漂移；复核前先 `git diff crawler-service/crawler/search.py` 确认。
- **测试覆盖未深读**：test_single/test_deep/test_search/test_feed 仅 grep 调用点，未逐行核对是否覆盖 use-after-close 场景（C03-01 是否有测试暴露 [需查证]）。
