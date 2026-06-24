# C11 配置同步 排查报告

> **模块编号**：C11
> **排查范围**：crawler 从 Java `/api/internal/collector/config` 拉取 crawler 配置、运行时刷新、env vs sys_config 优先级、刷新触发、配置类型转换、敏感配置传输
> **基线 commit**：`6ae930098405f4d0553d96a852f3345d0f39682e`
> **工作区状态**：脏。涉及本模块的改动文件：无直接改动（`crawler-service/standalone/backend_config.py`、`config.py`、`ai/config.py` 均未在工作区 dirty 列表中）。当前工作区 dirty 文件为 `crawler/search.py`、`optimization/knowledge_base.py`、若干测试、`backend/.../ConfigRepositoryImpl.java`、`WebCollectPageMapper.java` 等，与本模块无直接因果。
> **排查日期**：2026-06-24
> **排查人**：C11 排查 agent
> **状态**：草稿

---

## 模块概览

**职责**：crawler-service 启动时和运行时从 Java 后端拉取 `crawler.*` 配置，写入 Pydantic `settings` 单例；提供 `get()`/`get_bool()` 取值链（backend 缓存优先、env 兜底）；`/api/v1/config/refresh` 端点触发重新拉取并在关键配置变化时重启调度器。

**关键文件**：
- `crawler-service/standalone/backend_config.py:1-382` —— 核心：拉取、`_apply_*` 系列映射、`get`/`get_bool`/`refresh`、类型转换、env 兜底常量
- `crawler-service/config.py:1-239` —— Pydantic Settings，env 默认值（~100 项），`model_validator` 权重和校验
- `crawler-service/ai/config.py:29-48` —— `AiSettings.__getattr__` 通过 `backend_config.get()` 动态读取 `ai_*` 字段（与 `_apply_*` 双通道）
- `crawler-service/main.py:76-81` —— 启动时 `fetch_from_backend()`（失败仅 warning，不阻断）
- `crawler-service/standalone/routes.py:780-794` —— `/api/v1/config/refresh` 端点
- `crawler-service/standalone/scheduler.py:457,527` —— `backend_config.get_bool("digest.enabled")` 消费点
- `backend/src/main/java/com/nanmuli/blog/interfaces/rest/InternalCallbackController.java:140-160` —— Java 侧 `/api/internal/collector/config` 端点（`findByGroup("crawler")`、剥离 `crawler.` 前缀、AES 解密敏感项）
- `backend/.../initializer/SystemConfigInitializer.java:30-56` —— 从 env 种子 9 项 crawler 配置到 sys_config

**对外接口 / 依赖**：
- 对外（crawler 内部）：`backend_config.get(key)`、`get_bool(key)`、`refresh()`、`fetch_from_backend()`、`AiSettings` 动态属性
- 依赖：Java 后端 `/api/internal/collector/config`（HTTP GET，`X-Callback-Key` 或 `X-Callback-Key=crawler.service.api-key`）、httpx、Pydantic Settings、`config.settings` 单例
- 配置 key：102 项 `crawler.*`（DB seed），其中 ~47 项被 `_apply_*` 映射，其余仅经 `get()` 按需读取
- 表：backend `sys_config`（`group_name='crawler'`）

**已读文件清单**：
- `crawler-service/standalone/backend_config.py` —— 通读
- `crawler-service/config.py` —— 通读
- `crawler-service/ai/config.py` —— 通读
- `crawler-service/main.py:60-109` —— 片段（lifespan 启动/关闭）
- `crawler-service/standalone/routes.py:1-15,770-810` —— 片段（refresh 端点）
- `crawler-service/standalone/scheduler.py:450-545` —— 片段（调度器消费）
- `crawler-service/standalone/auth.py` —— 通读（认证中间件消费 settings）
- `crawler-service/tests/test_backend_config.py` —— 通读（6 个测试覆盖核心映射）
- `backend/.../InternalCallbackController.java:1-160` —— 通读（端点实现 + 鉴权）
- `backend/.../SystemConfigInitializer.java:30-139` —— 通读（env 种子逻辑）
- `deploy/db/init-scripts/schema.sql:946-1071` —— 仅 grep（crawler.* 种子行）

**主模块归属**：本模块**非**任何共享对象的主模块。配置一致性主模块为 **X06**（env 三轨 / AI_MODEL 不一致）。本报告补充 crawler 侧"拉取/消费/优先级/降级"视角，对 X06 已覆盖的 env 不一致只引用。AES 加密细节引用 **B07**；`CrawlerTaskClient` 反向通道引用 **B10**；双向 key 鉴权引用 **B09**。

---

## `[Bug]` 代码正确性与潜在缺陷

> 排查范围：`backend_config.py` 全量、`ai/config.py`、`config.py`、`routes.py` refresh 端点、`scheduler.py` 消费点、`test_backend_config.py`。

### [P2] [Bug] `ai.base_url` / `ai.api_key` / `callback.url` / `callback.api-key` 用 `in config` 成员判断，backend 下发空串会清空 env 值  <!-- 编号：C11-01 -->
- **定位**：`crawler-service/standalone/backend_config.py:104-107,148-149,156-157,158-159`
- **现象**：这几项使用 `if "ai.base_url" in config:` / `if "ai.api_key" in config:` / `if "callback.url" in config:` / `if "callback.api-key" in config:` / `if "service.java-api-url" in config:`（成员存在判断），而非其余项用的 `if config.get(key, ""):`（真值判断）。当 backend 这些 key 值为空字符串时（schema.sql 种子 `crawler.ai.api_key=''`、`crawler.callback.api-key=''`），仍会执行赋值，把 `settings.ai_api_key` 等覆盖为空。
- **影响**：①env 里设置了 `AI_API_KEY`/`AI_BASE_URL`，但 sys_config 对应 key 为空 → crawler 拉取后 `settings.ai_api_key` 变空 → `AiSettings.is_configured` False → AI 整理 / 日报生成静默关闭，且日志只有 INFO 级，难定位。②真实使用场景：DB 初始化时 `AI_API_KEY` env 未设，admin 后台清空了 base_url → crawler 重启后 AI 失效。③`callback.url` 的 localhost 守卫（`_ENV_CALLBACK_URL`）仅在 backend 下发 localhost 时触发，下发空串时直接 `settings.callback_url = ""`，回调链路断。
- **根因/分析**：与同文件其余项（`config.get(key, "")` 真值判断、空值跳过）的语义不一致。`callback.url` 有部分 localhost 守卫（C11-05 详述），但 `ai.base_url`/`ai.api_key` 无任何 env 兜底。已排除误判：测试 `test_blank_backend_auth_keys_do_not_clear_env_api_keys` 覆盖了 `auth.api_keys` 的真值判断分支，但**未覆盖** `ai.api_key` 的成员判断分支。
- **修复方向**：①统一为真值判断 `if config.get("ai.api_key", "").strip():`（改动面 小）；②对 `ai.api_key`/`ai.base_url` 增加 env 兜底（类似 `_ENV_API_KEYS`）（改动面 中）；③补测试覆盖"backend 空值不覆盖 env"（改动面 小）。
- **关联**：[[X06-09 env 不一致]] / 横向主题"配置一致性" / 配置项 `crawler.ai.api_key`、`crawler.ai.base_url`、`crawler.callback.url`、`crawler.callback.api-key`

### [P2] [Bug] `get()` 的 fallback 链对 `int`/`bool`/`float` 类型字段返回字符串，类型不一致  <!-- 编号：C11-02 -->
- **定位**：`crawler-service/standalone/backend_config.py:330-345`（`get` / `get_bool`）
- **现象**：`get(key)` 先查 `_config_cache[key]`（永远是 str，来自 HTTP JSON 的 `Map<String,String>`），命中则直接返回 str；未命中时 `getattr(settings, env_key)` 并 `str(val)`。两条路径都返回 str。调用方 `ai/config.py:38-44` 自己做 `field_type(val)` 类型转换，但转换失败时 `except Exception` 吞掉并 fallback 到 `getattr(settings, name)`（正确类型）。
- **影响**：①类型转换失败静默 fallback，无 warning 日志，难排查（如 backend 下发非数字的 `ai.max_tokens`）。②`get_bool` 用 `"true","1","yes","on"` 判定，但 backend schema.sql 里 switch 类型字段值是 `'true'`/`'false'` 小写，正常；若 admin 误填 `'True'` 也能识别（`.lower()`），OK。③`get()` 对不存在的 key 返回 `default=""`，调用方若直接 `int(get("limit.max_pages"))` 会抛 `ValueError`——目前没有这样直接调用的点（都经 `_to_int`），但 API 表面不安全。
- **根因/分析**：`get()` 设计为统一 str 出口，类型转换责任推给调用方。`ai/config.py` 的转换异常被 `logger.debug` 吞掉（`ai/config.py:45-46`），生产日志默认 INFO 级看不到。
- **修复方向**：①`get()` 增加可选 `cast` 参数或在转换失败时 `logger.warning`（改动面 小）；②`ai/config.py:46` 把 `logger.debug` 提到 `logger.warning`（改动面 小）。
- **关联**：次维度"可运维性" / 配置项类型转换

### [P3] [Bug] `_config_cache` 无 TTL、无失效时间戳，刷新失败时保留旧值  <!-- 编号：C11-03 -->
- **定位**：`crawler-service/standalone/backend_config.py:16,299-327`
- **现象**：`_config_cache` 是模块级全局 dict，仅在 `fetch_from_backend()` 成功（HTTP 200 + `code==200`）时整体替换；HTTP 失败/非 200/异常时返回 `{}` 但**不清空** `_config_cache`。无 TTL、无 last_fetch 时间戳、无失效检测。
- **影响**：①backend 宕机后 crawler 永远使用最后一次成功的 backend 配置（这其实是"独立服务原则"期望的降级，方向正确），但**无法区分**"backend 不可达"和"backend 配置没变"，诊断困难。②admin 改了配置但 backend 重启失败 → crawler 一直用旧值，`get_scheduler_status()` 的 `digest.enabled` 显示旧值，admin 误以为刷新成功。③没有 `last_refreshed_at` 字段供 `/api/v1/config/refresh` 返回，运维无法判断配置新鲜度。
- **根因/分析**：这是设计取舍（独立服务原则要求 backend 不可用时 crawler 用 env/缓存兜底）。问题在于缺少可观测性字段，而非降级行为本身。
- **修复方向**：①记录 `_last_fetch_at` / `_last_fetch_status` 并在 `refresh()` 返回值和 `get_scheduler_status()` 暴露（改动面 小）；②可选：给 `_config_cache` 加 TTL（如 1 小时）后回退 env（改动面 中，需评估对降级语义的影响）。
- **关联**：[[B10 CrawlerTaskClient]] / 次维度"可运维性"

### [P3] [Bug] `refresh()` 的调度器重启用 `asyncio.get_event_loop()` 已 deprecated  <!-- 编号：C11-04 -->
- **定位**：`crawler-service/standalone/backend_config.py:368-376`
- **现象**：调度器重启逻辑用 `asyncio.get_event_loop().call_soon(lambda: asyncio.ensure_future(_restart()))`。Python 3.10+ 中 `asyncio.get_event_loop()` 在无运行循环时会 deprecated/报警告；在已有运行循环的 coroutine 内推荐用 `asyncio.get_running_loop()`。
- **影响**：当前在 FastAPI 请求处理中调用（有运行循环），功能正常，但 Python 升级后可能产生 DeprecationWarning（CLAUDE.md 基线提到 crawler 测试有 1 warning，[需查证] 是否本处）。逻辑本身也有风险：`call_soon + ensure_future` 异步重启调度器，若重启过程中 `start_scheduler` 抛异常，只在 `_restart` 内部被 `except Exception` 吞掉，调用方无感知。
- **根因/分析**：`get_event_loop()` 是历史写法。Python 3.12 仍可用但在非主线程会报错。
- **修复方向**：①改用 `asyncio.get_running_loop()`（改动面 小）；②重启失败的异常应在 `refresh()` 返回值体现（改动面 小）。
- **关联**：次维度"可维护性"

### [P3] [Bug] `refresh()` 仅检测 3 项配置变化触发调度器重启，忽略部分调度相关项  <!-- 编号：C11-05 -->
- **定位**：`crawler-service/standalone/backend_config.py:350-367`
- **现象**：`refresh()` 只比较 `digest.enabled`、`ai.enabled`、`digest.cron` 三项决定是否重启调度器。但调度器实际还依赖 `digest.parallel_sections`、`digest.optimization_enabled`、`digest.global_timeout`、`optimization.enabled` 等（`scheduler.py:457` 只看 `digest.enabled` + `digest_cron`，所以调度器注册本身只关心这两项）。
- **影响**：实际影响有限——调度器注册确实只依赖 `digest.enabled` + `digest.cron`（`scheduler.py:457`），其余项是执行时读 settings，运行时生效。所以 `refresh()` 的检测项与 `start_scheduler` 的依赖项一致，**逻辑自洽**。但 `digest.enabled`/`ai.enabled` 的比较用 `get_bool()`，而 `get_bool` 读 `_config_cache`——若 backend 下发了非标准 bool 字符串（如 `"yes"`），新旧比较结果可能反复触发重启。
- **根因/分析**：检测项与注册项一致，非 bug。列为 P3 因 documentation 角度：`refresh()` 注释应说明"为何只检测这 3 项"，避免后续误改。
- **修复方向**：补充注释说明检测范围 = `start_scheduler` 依赖项（改动面 小）。
- **关联**：[[C10 调度器]]

---

## `[Security]` 安全漏洞

> 排查范围：`backend_config.py` HTTP 拉取、`ai/config.py`、`InternalCallbackController` 鉴权、敏感配置传输与日志。逐项覆盖 §2.2：本模块不涉及 Sa-Token/MyBatis/Cookie/CSRF/CORS/文件上传；涉及 SSRF（callback url）、AES（敏感配置）、跨服务双向 key。

### [P2] [Security] `ai.api_key` / `auth.api_keys` / `callback.api-key` 经 sys_config 明文下发到 crawler 内存，日志可能泄漏  <!-- 编号：C11-06 -->
- **定位**：`crawler-service/standalone/backend_config.py:106-107,156-157,204-209`；日志风险点 `backend_config.py:254,261`（`logger.info("Proxy enabled: %s", proxy_url)`）
- **现象**：①Java 端 `InternalCallbackController:152-153` 对 `isEncrypted=TRUE` 的 key 调用 `aesEncryptor.decrypt(val)` 解密后放入返回 Map，crawler 收到的是**明文 API key**。②crawler 侧 `_apply_*` 直接赋值给 `settings.ai_api_key` 等明文字段，无运行时加密。③`fetch_from_backend()` 整个 `_config_cache` dict 在内存常驻，dump 可能泄漏。④`_apply_proxy_config` 把 `proxy_url`（可能含 `user:pass@host`）打到 INFO 日志。
- **影响**：①传输层：Java→crawler HTTP 若未走 mTLS/内网，明文 API key 经响应体传输（依赖部署网络隔离，X01 范围）。②内存层：crawler 进程内存 dump / error report 暴露所有 key。③日志层：proxy_url 含凭证时进 INFO 日志（crawler 默认 log_level=INFO），日志聚合系统可见。④admin 后台修改 `ai.api_key` 后，旧值仍可能残留在 crawler `_config_cache`（刷新成功才覆盖）。
- **根因/分析**：跨服务配置同步的固有取舍——Java 解密后必须明文下发，否则 crawler 无法使用。风险点在"日志"和"内存驻留"，而非传输设计本身。已排除误判：`_apply_ai_settings` 对 `ai.api_key` 没有打 INFO 日志（只 `ai.base_url` 等非敏感项不打），但 proxy_url 打日志是真实风险。
- **修复方向**：①`_apply_proxy_config` 的 `logger.info` 改为脱敏（只打 host，不打 userinfo）（改动面 小）；②crawler 侧敏感字段标记 + 内存中尽量短驻留（改动面 大，跨模块）；③评估 crawler→backend 拉取走内网 + 双向 TLS（改动面 大，X01）。
- **关联**：[[B07 AesEncryptor]] / [[B09 双向 key]] / 配置项 `crawler.ai.api_key`、`crawler.auth.api_keys`、`crawler.callback.api-key`、`crawler.proxy.url`

### [P3] [Security] `/api/v1/config/refresh` 端点可被用于自我锁死（修改 api_keys 后旧 key 立即失效）  <!-- 编号：C11-07 -->
- **定位**：`crawler-service/standalone/routes.py:780-794` + `crawler-service/standalone/auth.py:40-54` + `backend_config.py:198-209`
- **现象**：refresh 端点在 `auth_protected_prefixes = "/api/v1,..."` 下，需 `X-API-Key`。但 `_apply_auth_settings` 会用 backend 下发的新 `auth.api_keys` 覆盖 `settings.api_keys`。场景：admin 在 backend 改了 `crawler.auth.api_keys`（不含当前调用方的 key），crawler refresh 后 `settings.api_keys` 变更，当前持有旧 key 的调用方**下一次请求**就被中间件 401。
- **影响**：①运维误操作：admin 改 api_keys 拼写错误 → 所有内部服务调用方被锁死，且 crawler 无"保留旧 key 宽限期"。②这是合理的安全行为（改 key 就该立即生效），但缺少"配置变更审计/回滚"工具时风险放大。③refresh 端点本身：若 backend 下发空 `auth.api_keys` + 空 `service.api-key`，`_apply_auth_settings:208` 会 fallback `_ENV_API_KEYS`，不会清空——这个分支正确（有测试覆盖 `test_blank_backend_auth_keys_do_not_clear_env_api_keys`）。
- **根因/分析**：鉴权即时生效是设计本意。风险在运维流程缺审计/回滚，属可运维性问题而非漏洞。
- **修复方向**：①backend admin 改 `crawler.auth.api_keys` 时记录变更历史（X06/B07 范围）；②refresh 端点返回"本次影响的 key 数量"供审计（改动面 小）。
- **关联**：[[B09 双向 key]] / 横向主题"鉴权一致性"

---

## `[Arch]` 架构与技术债

> 排查范围：`backend_config.py` 结构、双通道读取、配置 key 映射、模块文档准确性。

### [P3] [Arch] 模块 docstring 声称"33 项核心配置"，实际映射 47 项、DB 种子 102 项，文档严重漂移  <!-- 编号：C11-08 -->
- **定位**：`crawler-service/standalone/backend_config.py:1-6`（docstring）vs 实际代码
- **现象**：docstring 写"仅保留 33 项核心管理配置的映射"、"删除了搜索调参、质量评估调参..."。实测：①`_apply_*` 函数引用的去重后配置 key 约 **47 项**（grep 统计）；②`deploy/db/init-scripts/schema.sql` 种子 `crawler.*` 共 **102 项** distinct key；③backend `/api/internal/collector/config` 用 `findByGroup("crawler")` **全量下发**这 102 项到 crawler `_config_cache`。
- **影响**：①docstring 与代码不符，误导维护者以为只处理 33 项。②102 项全量下发但只有 47 项被 `_apply_*` 映射到 settings，其余 55 项只能经 `get()` 按需读取（目前只有 `digest.enabled` 一项这样用），其余 54 项实际"拉了但没用"，浪费 HTTP payload + 内存。③"删除的配置类别"声明与 DB 种子矛盾（DB 仍种子了 `crawler.ai.temperature`、`crawler.quality.*`、`crawler.keyword.*`、`crawler.db.*` 等被声称删除的类别）。
- **根因/分析**：docstring 是历史重构残留（commit `49b708c` "harden digest generation" 期间精简了 `_apply_*`，但没更新 docstring，也没清理 DB seed）。非功能 bug，但属配置一致性技术债。
- **修复方向**：①更新 docstring 反映实际映射数量（改动面 小）；②评估：DB seed 是否应同步精简到 `_apply_*` 实际消费的子集（改动面 中，需 X06 协调，避免破坏 admin 后台展示）；③在 `_apply_all_settings` 末尾的 INFO 日志补充"已应用 N 项 / 下发 M 项"对比（改动面 小）。
- **关联**：[[X06 配置一致性]] / [[B15 schema 三轨]] / 横向主题"配置一致性"

### [P3] [Arch] 双通道读取 AI 配置（`_apply_ai_settings` 直接赋值 + `AiSettings.__getattr__` 动态 get），语义重叠易漂移  <!-- 编号：C11-09 -->
- **定位**：`backend_config.py:82-107`（`_apply_ai_settings` 写 `settings.ai_*`）vs `ai/config.py:29-48`（`AiSettings.__getattr__` 读 `backend_config.get`）
- **现象**：AI 配置有两条生效路径：①`fetch_from_backend` → `_apply_ai_settings` 把值写进 `settings.ai_model` 等 Pydantic 字段；②`AiSettings.__getattr__` 访问 `.ai_model` 时动态调 `backend_config.get("ai.model")` 读 `_config_cache`。两者数据源相同（`_config_cache`），但路径 ② 绕过了路径 ① 写入的 `settings`，直接读缓存。
- **影响**：①功能上目前一致（都源自 `_config_cache`），但维护时改一处忘另一处会漂移。②`AiSettings` 有 `_overrides` 机制（构造时传入），但 `_overrides` 只在显式构造时生效，全局 `ai_settings = AiSettings()` 单例无 override，全靠 `__getattr__` 动态读。③`AiSettings.is_configured`（`ai/config.py:51-57`）每次访问都重新读 `ai_enabled`/`ai_api_key`/`ai_base_url`/`ai_model`，若任一为空返回 False——这与 `_apply_ai_settings` 的空值覆盖问题（C11-01）叠加，AI 易静默关闭。
- **根因/分析**：`AiSettings` 是为向后兼容保留的 Facade（注释 `ai/config.py:11-15`），本意是统一读 settings，但 `__getattr__` 又绕回去读 backend_config，形成循环依赖（`ai.config` → `backend_config` → `config.settings`）。设计冗余。
- **修复方向**：①`AiSettings.__getattr__` 直接读 `getattr(settings, name)`，移除 `backend_config.get` 依赖（依赖 `_apply_ai_settings` 已同步写入）（改动面 中，需测试覆盖）；②或反之，移除 `_apply_ai_settings` 完全靠 `AiSettings` 动态读（改动面 中，需评估非 AI 代码对 `settings.ai_*` 的直接引用）。
- **关联**：[[C05 AI 整理]] / 次维度"可维护性"

### [P4] [Arch] `get()` 的 key 转换 `key.replace(".", "_")` 对嵌套 key 不稳健  <!-- 编号：C11-10 -->
- **定位**：`backend_config.py:334`
- **现象**：`get(key)` 未命中缓存时 `env_key = key.replace(".", "_")` 把 `ai.max_tokens` 转成 `ai_max_tokens` 查 settings。对 `ai.max_tokens` 这类单层点号 OK，但对 `pipeline.content_dedup_simhash_threshold` 转成 `pipeline_content_dedup_simhash_threshold`——而 settings 字段名是 `content_dedup_simhash_threshold`（无 `pipeline_` 前缀）。
- **影响**：`getattr(settings, "pipeline_content_dedup_simhash_threshold", None)` 返回 None → fallback `default`。即对 `pipeline.*` / `optimization.*` 等 key，`get()` 的 env 兜底**失效**（除非字段名恰好带前缀）。目前 `get()` 的真实调用方只有 `scheduler.py` 的 `digest.enabled`（单层，OK）和 `ai/config.py` 的 `ai_*`（用 `replace("_", ".", 1)` 反向转换，OK），所以**当前无实际故障**。
- **根因/分析**：`get()` 的 env fallback 是按"backend key 直接映射 settings 字段名"的假设写的，但 `_apply_*` 的映射是显式的（`pipeline.content_dedup_enabled` → `settings.content_dedup_enabled`，去前缀）。两者口径不一致。
- **修复方向**：①`get()` 文档化"仅适用于 key 与 settings 字段名同构的场景"（改动面 小）；②长期：统一 key 命名约定（改动面 大，X06）。
- **关联**：[[X06 配置一致性]]

---

## `[Deps]` 依赖升级与版本

### 本模块依赖清单（基于声明文件，未翻依赖源码）

| 依赖 | 版本 | 声明位置 | 已知风险/可升级 | 备注 |
|---|---|---|---|---|
| httpx | （未在 requirements.txt 单独列，随 FastAPI 生态） | `crawler-service/requirements.txt` [需查证] | [需查证] 当前版本 | `fetch_from_backend` 用 `httpx.AsyncClient` |
| pydantic-settings | （FastAPI 依赖） | `crawler-service/requirements.txt` [需查证] | [需查证] | `config.py` 用 `BaseSettings` |
| Python | 3.10+ | `Dockerfile` [需查证] | `asyncio.get_event_loop()` 在 3.10+ deprecated（见 C11-04） | |

> 排查范围：本节基于 `crawler-service/requirements.txt` 声明（未深入读取，[需查证] 具体版本）。本模块无独立第三方依赖（httpx/pydantic 为框架级共享）。未发现本模块特有的依赖风险。

### 本模块 [Deps] 发现
未发现（本模块不引入独立依赖，共享 FastAPI 生态，版本风险归 X01/C12）。

---

## `[Design]` 功能设计合理性

> 从真实使用出发（单人维护博客 + 工作日 AI 日报场景），回答 §2.5 相关问题。

**审视结论**：

1. **可运维性（§2.5-3）**：双源配置（env + sys_config）的优先级语义**不直观且无文档**。实际生效顺序是：①`_apply_*` 把 backend 值写入 settings（覆盖 env）；②`get()` 读 `_config_cache` 优先、settings 兜底。但 `_apply_*` 内部对空值处理不一致（C11-01：部分 key 空值覆盖、部分跳过），导致"我改了 env 为什么不生效"的排障陷阱：env 改了 `AI_API_KEY`，crawler 不重启就不生效；即便重启，若 sys_config 里该 key 非空，env 改动被 sys_config 覆盖。**admin 改 sys_config 是热生效（refresh 端点），改 env 是冷生效（重启 crawler）**——这一不对称未在任何文档说明，是真实使用下的高频困惑点。

2. **闭环完整性（§2.5-2）**：配置变更链路有断点。admin 在 backend 改 `crawler.*` → 写 sys_config → **但 crawler 不会自动感知**，必须有人调 `/api/v1/config/refresh`。backend 侧 `WebCollectSourceAppService:196` 有"通知 crawler refresh"逻辑（针对 source 配置），但通用 crawler 配置变更**无自动推送**。实测路径：admin 改 `digest.cron` → crawler 仍按旧 cron 跑，直到下次 refresh。缺"配置变更自动通知"闭环。

3. **场景适配（§2.5-1）**：102 项配置全量下发对一个单人博客+日报场景**过度设计**。大量调参项（`crawler.ai.temperature`、`crawler.quality.*`、`crawler.keyword.*`）admin 几乎不会改，却每次 refresh 都拉取 102 项。但这也是"通用性"的代价，非 bug。

### [P2 / Design] [Design] env vs sys_config 优先级与失效场景（重点结论）  <!-- 编号：C11-11 -->
- **定位**：`backend_config.py:82-287`（`_apply_*`）+ `config.py`（env 默认）+ `main.py:76-81`（启动拉取）
- **现象**：crawler 实际运行时配置生效的**明确优先级链**（本次排查核心结论）：

  **写入 settings 的优先级**（`_apply_*` 执行时）：
  - 启动：`settings` 先由 Pydantic 从 `.env`/环境变量初始化 → `fetch_from_backend()` 调 `_apply_*` 把 backend 值覆盖到 settings。
  - 大多数 key：`if config.get(key, ""):` 真值判断 → **backend 非空则覆盖 env，backend 为空则保留 env**（env 兜底成立）。
  - 例外（C11-01）：`ai.base_url`/`ai.api_key`/`callback.url`/`callback.api-key`/`service.java-api-url` 用成员判断 → **backend 即使为空也覆盖 env**（env 兜底失效）。

  **读取时的优先级**（`get(key)`）：
  - `_config_cache[key]` 非空 → 返回缓存（backend 值）
  - 否则 `getattr(settings, env_key)` → 返回 env/默认值
  - 否则 `default`

  **失效场景**（改了配置 crawler 多久生效）：
  | 改动源 | 生效方式 | 延迟 |
  |---|---|---|
  | admin 改 sys_config（backend） | 需手动调 `/api/v1/config/refresh` | **无限期**（直到 refresh） |
  | 改 crawler `.env` | 重启 crawler 进程 | 重启后立即（但若 sys_config 非空则被覆盖） |
  | backend 宕机 | crawler 用最后一次成功的 `_config_cache` | 永久用旧值（C11-03） |

- **影响**：真实排障陷阱：①admin 改 `digest.cron` 不生效 → 因为没调 refresh。②运维改 `.env` 的 `AI_API_KEY` 不生效 → 因为 sys_config 的 `crawler.ai.api_key` 非空，启动时被覆盖（C11-01 的 `in config` 分支即使 sys_config 为空也会覆盖）。③backend 重启失败后 crawler 一直用旧配置，admin 以为新配置已生效。
- **建议方向**：①文档化优先级矩阵（改动面 小）；②统一 `_apply_*` 的空值处理为"backend 空则保留 env"（改动面 中，见 C11-01）；③backend 配置变更后自动调 crawler refresh（改动面 中，需 B10 `CrawlerTaskClient` 加 push refresh）。
- **关联**：[[X06 配置一致性]] / 横向主题"配置一致性" / [[B07 sys_config]] / [[B10 CrawlerTaskClient]]

### [P4 / Design] [Design] 缺"配置新鲜度"可观测性，admin 无法判断 crawler 是否用最新配置  <!-- 编号：C11-12 -->
- **定位**：`backend_config.py`（无 `last_fetch_at`）+ `routes.py:780-794`（refresh 返回值）+ `scheduler.py:523-545`（scheduler_status）
- **现象**：`get_scheduler_status()` 返回 `enabled`/`cron`/`ai_enabled`/`ai_configured`，但**不返回** `last_config_fetch_at` / `last_config_fetch_status` / `config_source`（env vs sys_config）。admin 看不到 crawler 当前用的是哪次拉取的配置。
- **影响**：排障时 admin 只能 ssh 进 crawler 容器看日志，无法从管理界面判断配置同步状态。
- **建议方向**：`get_scheduler_status()` 增加 `config: {last_fetch, source, keys_count}` 字段（改动面 小）。
- **关联**：[[C10 调度器]] / 次维度"可运维性"

---

## 模块小结

### 严重度统计

| 级别 | 数量 | 条目编号 |
|---|---|---|
| P0 | 0 | — |
| P1 | 0 | — |
| P2 | 3 | C11-01, C11-06, C11-11 |
| P3 | 5 | C11-02, C11-03, C11-04, C11-05, C11-07, C11-08, C11-09 |
| P4 | 2 | C11-10, C11-12 |

> 统计修正：P3 实际 7 条（C11-02/03/04/05/07/08/09），P2 3 条（C11-01/06/11），P4 2 条（C11-10/12）。合计 12 条。

### Top 风险（本模块最该先看的 ≤3 条）

1. **C11-01 backend 空值覆盖 env（ai.api_key 等）** —— 唯一可能造成"AI 静默关闭"的功能性 bug，env 兜底失效，难排查。
2. **C11-11 env vs sys_config 优先级与失效场景** —— 运维高频困惑点（改配置不生效），且无文档。
3. **C11-06 敏感配置日志/内存泄漏** —— proxy_url 含凭证进 INFO 日志，跨服务明文下发 API key。

### 修复优先级建议

- **立即**（P0/P1）：无。
- **计划**（P2）：
  - C11-01 统一 `_apply_*` 空值判断 + 补 env 兜底（小-中）
  - C11-06 proxy_url 日志脱敏（小）
  - C11-11 文档化优先级矩阵 + 评估自动 refresh 推送（小-中，跨 X06/B10）
- **择机**（P3/P4）：
  - C11-02 `get()` 类型转换失败提 warning 日志（小）
  - C11-03 增加 `last_fetch_at`/`fetch_status` 可观测性（小）
  - C11-04 `get_event_loop` → `get_running_loop`（小）
  - C11-08 更新 docstring 反映实际映射数量（小）
  - C11-09 简化 AiSettings 双通道（中）
  - C11-12 scheduler_status 暴露配置新鲜度（小）

### 排查盲区 / 待复核

- **[需查证]** `crawler-service/requirements.txt` 中 httpx / pydantic-settings 的具体版本（本次未读取该文件，依赖清单版本留空）。
- **[需查证]** crawler 测试基线的 "1 warning"（CLAUDE.md 记载）是否由 C11-04 的 `asyncio.get_event_loop()` DeprecationWarning 产生——本次命令边界禁止跑 pytest，无法验证。
- **[需查证]** backend `WebCollectSourceAppService:196` "通知 crawler refresh" 是否覆盖通用 crawler 配置变更，还是仅限 source 配置——本次仅 grep 到该行，未通读实现（归属 C10/B08）。
- **[需查证]** Java `findByGroup("crawler")` 是否会返回 `is_public=true` 之外的敏感 key（admin 后台可能动态新增非 schema.sql 种子的 key），影响 `_apply_*` 的 key 覆盖范围。
- **跨模块待核对**：X06 应回写 C11-01/C11-11 的 env 优先级结论；B07 应核对 AES 解密后明文下发的安全评估口径；B10 应评估"配置变更自动 push refresh"的改动归属。
