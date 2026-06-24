# X04 发布脚本与 CI 排查报告

> **模块编号**：X04
> **排查范围**：发布闸门 / 环境校验 / 日报 smoke / 本地 smoke 启动器 / CI 缺失
> **基线 commit**：`6ae930098405f4d0553d96a852f3345d0f39682e`
> **工作区状态**：脏。涉及本模块的未提交改动：`scripts/release/release-gate.ps1`（已修改，本报告基于当前工作区版本）。其余 4 个脚本（`check-deploy-env.ps1`、`digest-smoke.ps1`、`start-local-smoke-services.ps1` 及目录下无新增）未在工作区改动。
> **排查日期**：2026-06-24
> **排查人**：X04 排查 agent
> **状态**：待复核

---

## 模块概览

**职责**：在无 CI 系统的前提下，用一组 PowerShell 脚本提供"一键上线闸门 + 环境必填项校验 + 真实日报 smoke + 本地服务拉起"的手动发布质量护栏。

**关键文件**：
- `scripts/release/release-gate.ps1:1-474`（工作区脏版本）—— 一键闸门，串联 preflight / resource snapshot / resource pressure / frontend audit / frontend build / crawler tests / backend tests / compose config / digest-smoke -SelfTest / check-deploy-env / 可选 digest smoke / 收尾 snapshot，输出 JSON + Markdown 报告
- `scripts/release/check-deploy-env.ps1:1-57` —— 校验 `deploy/.env` 的 6 个必填 key（AI_ENABLED / DIGEST_ENABLED / AI_API_KEY / CRAWLER_API_KEY / CRAWLER_CALLBACK_API_KEY / BLOG_SECURITY_ENCRYPTION_KEY），拒绝占位符，要求加密 key ≥16 字符
- `scripts/release/digest-smoke.ps1:1-396` —— 真实日报 smoke：health → config → scheduler → runtime health → 触发/取最新 → 轮询到完成/失败 → 校验 ai_title/ai_full_content/sections/core 覆盖/publishable/optimization safety；含 `-SelfTest` 离线自检
- `scripts/release/start-local-smoke-services.ps1:1-117` —— 本地拉起 backend（mvn spring-boot:run）+ crawler（uvicorn），读 deploy/.env 与 crawler/.env 注入进程环境，自动跳过已占用端口

**对外接口 / 依赖**：
- 对外：无代码接口；纯 CLI 脚本，被 `deploy/README.md`、`docs/trial-release-roadmap.md` 文档引用
- 依赖：PowerShell（Windows 专属命令：`Get-Counter`、`Get-NetTCPConnection`、`npm.cmd`、`mvn.cmd`、`venv\Scripts\python.exe`）；docker / wsl CLI（仅用于资源快照，可选）；目标服务的 HTTP 端点（`/health`、`/api/v1/digests/*`、`/api/digest/latest`）
- 配置 key：消费 `deploy/.env`（check-deploy-env）、`crawler-service/.env`（start-local-smoke）、`$env:CRAWLER_API_KEY`（digest-smoke 默认）

**已读文件清单**：
- `scripts/release/release-gate.ps1` —— 通读（474 行，工作区版本）
- `scripts/release/check-deploy-env.ps1` —— 通读（57 行）
- `scripts/release/digest-smoke.ps1` —— 通读（396 行）
- `scripts/release/start-local-smoke-services.ps1` —— 通读（117 行）
- `deploy/.env.example` —— 通读（50 行，用于覆盖度比对）
- `deploy/README.md` —— 仅 grep（release-gate / check-deploy-env / digest-smoke 引用段）
- CI 文件探测：`.github/workflows/`、`.gitlab-ci.yml`、`Jenkinsfile`、`azure-pipelines.yml`、`.circleci/config.yml` —— Glob 均无结果（确认无 CI）

**主模块归属**：
- 本模块**深查**：release-gate 检查项完整性、check-deploy-env 覆盖缺口、digest-smoke 断言、secret 脱敏、跨平台限制、无 CI 的可靠性 gap。
- **只引用**（不展开）：
  - admin 弱口令 `admin123` + check-deploy-env 未覆盖 → 主归属 `X02-05` / `B15-02`，本报告在 Design 节引用
  - COOKIE_SECURE / CORS / DB_PASSWORD 配置一致性 → 主归属 `X06`，本报告只记"check-deploy-env 未覆盖"这一发布脚本视角
  - 部署架构 / 端口暴露 / 资源限额 → 主归属 `X01`

---

## `[Bug]` 代码正确性与潜在缺陷

> 排查范围：四个脚本的逻辑、边界、异常处理、超时、轮询、资源释放。静态阅读，未执行。

### [P2] [Bug] `Invoke-Step` 超时强杀 Job 后子进程未回收，重型步骤泄漏  <!-- 编号：X04-01 -->
- **定位**：`scripts/release/release-gate.ps1:89-116`（`Start-Job` + `Wait-Job -Timeout` + `Stop-Job`/`Remove-Job -Force`）
- **现象**：`Invoke-Step` 用 `Start-Job` 跑外部进程（`mvn test`、`npm run build`、`pytest`、`docker compose config`）。超时分支（第 108-116 行）只 `Stop-Job`/`Remove-Job` PowerShell Job 对象本身，但 Job 内 `& $file` 启动的原生进程（mvn/java/node）**不保证被级联终止**——PowerShell Job 超时清理的是 job runspace，原生子进程可能继续占用 JVM/Node 内存直到自身结束。
- **影响**：在 release-gate 设计要防的"资源压力"场景里，超时本身最易发生在资源紧张时（mvn 慢、build 卡），此时残留 JVM/Node 进程叠加下一次 release-gate 的资源检查，可触发后续步骤假性 FAIL（available memory 不足）。讽刺点：超时清理路径反而制造了资源泄漏。
- **根因/分析**：`Start-Job` 起的是独立 runspace，原生子进程父进程是该 runspace 的 PowerShell，`Stop-Job` 不传播到原生子进程。已排除"Wait-Job 能正常回收"——正常完成分支（第 122 行 `Remove-Job`）同样不杀残留子进程，只是正常完成时子进程已自然退出故不显形。这是 PowerShell Job 模型通病，非脚本逻辑写错，但在长跑重型步骤场景下被放大。
- **修复方向**：①改用 `Start-Process -PassThru` + `WaitForExit(timeout)` + 超时 `$proc.Kill()`（含子进程树，PowerShell 7 的 `$proc.Kill($true)` 杀整个树）；②或超时分支显式按进程名清理残留 `java`/`node`/`python` 进程（粗糙，风险误杀）。改动面：中（核心执行函数重写，需重测所有步骤）。
- **关联**：次维度 `[Arch]` 可运维性；与 `X01` 资源压力主题呼应

### [P3] [Bug] `check-deploy-env.ps1` 占位符正则过窄，绕过校验风险  <!-- 编号：X04-02 -->
- **定位**：`scripts/release/check-deploy-env.ps1:36`（`if ($Env[$Key] -match "^(your_|sk-your-|nanmuli-blog-key$)")`）
- **现象**：占位符黑名单只匹配 3 个前缀：`your_`、`sk-your-`、`nanmuli-blog-key`。但 `deploy/.env.example` 实际用到的占位符值包括 `your_secure_database_password`、`your_16_plus_char_encryption_key`、`your_shared_crawler_api_key`、`your_shared_callback_key`（都以 `your_` 开头，能命中），而 `AI_API_KEY=`（空值，由 `Assert-Configured` 第 33 行空白检查兜底，OK）。
- **影响**：若用户填入 `changeme`、`test123`、`placeholder`、`xxx` 等非 `your_` 前缀的占位词，check-deploy-env 会 PASS 但实际未配置真实值。单人口子项目风险较低（自己填的能记住），但作为"上线闸门"兜底不够。
- **根因/分析**：黑名单是 deny-list 思路，天然有绕过面。已排除"空值绕过"——第 33 行 `IsNullOrWhiteSpace` 已挡空字符串。残余风险是"非空但弱"的值。
- **修复方向**：①对密钥类 key 增加最小长度断言（如 `AI_API_KEY`、`CRAWLER_API_KEY` ≥ 16 字符，对齐 `BLOG_SECURITY_ENCRYPTION_KEY` 的 16 字符门槛）；②扩展占位符黑名单（`changeme`/`placeholder`/`test`/`xxx`）；③改为 allow-list 思路（拒绝任何与 .env.example 默认值相等的值）。改动面：小。
- **关联**：次维度 `[Security]` 密钥强度；横向主题配置一致性（主归属 X06）

### [P3] [Bug] `digest-smoke.ps1` 轮询间隔固定 10s × TimeoutMinutes，对慢网/AI 慢响应诊断粒度粗  <!-- 编号：X04-03 -->
- **定位**：`scripts/release/digest-smoke.ps1:358-368`（`$deadline = (Get-Date).AddMinutes($TimeoutMinutes); do { Start-Sleep -Seconds 10 ... } while`）
- **现象**：触发日报后每 10s 轮询 `/api/v1/digests/task/{id}`，直到 status=Completed(3)/Failed(4) 或到 `$TimeoutMinutes` 截止。默认 30min 内每 10s 一次，期间只在状态变化时打印一行。
- **影响**：超时后只能抛 `"did not complete within X minutes"`，无中途进度（卡在哪一阶段、哪个板块、AI 调用次数）。`Print-Diagnostics`（第 144 行）只在 `FailedStatus=4` 分支调用，超时分支（task 仍 running）拿不到诊断信息，需人工再请求一次。对"上线前 smoke 卡住"的排查体验不佳。
- **根因/分析**：轮询设计本身正确（拉取状态机），问题是诊断输出仅绑定"失败"分支，超时分支漏了。已排除"超时即失败应能复用 Print-Diagnostics"——超时时 `$digest` 仍是最后一次轮询结果（status≠4），含 quality_evaluation/orchestrator_plan 字段，`Print-Diagnostics` 能打印，只是没被调用。
- **修复方向**：①超时分支调用 `Print-Diagnostics $digest` 后再抛错（一行改动）；②轮询日志增加 `current_section`/`pages_crawled` 进度字段（需后端 task 接口提供，跨服务改动）。改动面：小（仅 ①）/ 中（②涉及 crawler 接口）。
- **关联**：次维度 `[Design]` 可运维性；与 `C04` 日报编排诊断字段呼应

---

## `[Security]` 安全漏洞

> 排查范围：secret 脱敏、密钥校验、密文泄漏、占位符绕过、报告输出安全。逐项覆盖 §2.2 技术栈重点（本模块不直接处理 Sa-Token / MyBatis / AES / SSRF / 文件上传，重点在 secret 脱敏与密钥校验）。

### [P3] [Security] `Redact-SecretText` 脱敏正则可被多行/无换行格式绕过  <!-- 编号：X04-04 -->
- **定位**：`scripts/release/release-gate.ps1:46-65`（`Redact-SecretText`）
- **现象**：脱敏靠两条正则：①按行匹配 `^\s*$name\s*[:=]\s*.+$`（覆盖 `KEY=value` / `KEY: value` 两种行格式，多行 `?m` 模式）；②`sk-[A-Za-z0-9_-]{12,}` 匹配 OpenAI 风格 key。被脱敏的 key 名单含 AI_API_KEY / CRAWLER_API_KEY / CRAWLER_CALLBACK_API_KEY / CALLBACK_API_KEY / API_KEYS / BLOG_SECURITY_ENCRYPTION_KEY / DB_PASSWORD（第 51-59 行）。
- **影响**：①若外部命令输出把 secret 拼在非行首（如 `config: AI_API_KEY=sk-xxxxx inline`），行正则仍能命中（`?im` 的 `^` 配合 `\s*` 容忍前导空白，但"前缀有其他文本"如 `[INFO] AI_API_KEY=sk-x` 因 `^` 锚定行首，`\s*` 不匹配 `[INFO] ` → **漏脱敏**）；②`sk-` 正则要求 ≥12 位字符，若某 AI provider 用更短的 key 前缀（如 `sk-` + 8 位）则不命中；③JSON 输出里 secret 若以 `"ai_api_key":"sk-x"` 形式（key 名小写、带引号、无 `=`/`:` 后空白），行正则的 `[:=]` 不匹配引号包裹 → 漏脱敏。
- **根因/分析**：脱敏靠"行首 + key 名 + 分隔符"模式匹配，对结构化输出（JSON/日志前缀）覆盖不全。已排除"Add-Result 已对 output 和 error 都脱敏"——第 68-69 行确实两路都过 `Redact-SecretText`，但脱敏函数本身的覆盖面有缝。`mvn test` 日志一般不含明文 key，但 crawler `pytest` 若打印 config 对象、或 `docker compose config` 渲染出 env 值时，明文可能进入报告。
- **修复方向**：①增加对 JSON 值的脱敏（`"$name"\s*:\s*"[^"]*"` → `"$name":"***"`）；②对已知 provider key 前缀（`sk-`、`claude-`、`AIza`）独立正则脱敏，不限长度；③测试用例覆盖 JSON / 日志前缀 / 内联三种格式（参考 digest-smoke 的 SelfTest 思路）。改动面：小-中。
- **关联**：次维度 `[Bug]`；横向主题配置一致性

### [P3] [Security] check-deploy-env 不校验 DB_PASSWORD / COOKIE_SECURE / CORS / REDIS 密码（覆盖缺口）  <!-- 编号：X04-05 -->
- **定位**：`scripts/release/check-deploy-env.ps1:7-14`（`$RequiredKeys` 6 项）；对照 `deploy/.env.example:4,6,23-24,49`
- **现象**：`RequiredKeys` 仅 6 项（AI_ENABLED / DIGEST_ENABLED / AI_API_KEY / CRAWLER_API_KEY / CRAWLER_CALLBACK_API_KEY / BLOG_SECURITY_ENCRYPTION_KEY）。但 `deploy/.env.example` 含 `DB_PASSWORD`（第 4 行，默认 `your_secure_database_password`）、`COOKIE_SECURE=false`（第 6 行，**生产应为 true**）、`CORS_ALLOWED_ORIGINS`（第 49 行）、`REDIS_MEM_LIMIT`（第 23 行，无 REDIS_PASSWORD 项——说明 Redis 默认无密码）。这 4 项在 check-deploy-env 完全不校验。
- **影响**：
  - **DB_PASSWORD**：用户忘填或保留 `your_secure_database_password` → compose 启动时 postgres 用默认/空密码，公网 PG（X01-05 已记端口暴露）直接暴露。
  - **COOKIE_SECURE=false** 进生产 → Sa-Token Cookie 不带 Secure 标志，HTTP 中间人可窃取 admin token（主归属 X06 / B06，本报告只记"check-deploy-env 不拦"）。
  - **CORS_ALLOWED_ORIGINS** 若保留示例域名 `https://nanmu.xyz` → 上线到其他域名时 CORS 反射错误，或若用户改成 `*` + allowCredentials 则 XSS 提权面（主归属 X06 / B16）。
  - **REDIS 无密码**：.env.example 无 REDIS_PASSWORD 项，compose 若暴露 6379 → 未授权访问（X01 视角）。
- **根因/分析**：check-deploy-env 的 RequiredKeys 是"日报链路能跑通"的最小集（AI/digest/key/加密），而非"生产安全就绪"全集。这是设计取舍而非 bug，但 deploy/README 第 70 行把 `DB_PASSWORD` 标为"必填"，脚本却没校验 → 文档与脚本不一致。已排除"这些配置主归属 X06"——X06 负责配置一致性本身，本条只记"发布闸门未覆盖"这一可执行 gap。
- **修复方向**：①RequiredKeys 增加 `DB_PASSWORD`、`COOKIE_SECURE`、`CORS_ALLOWED_ORIGINS`；②对 `COOKIE_SECURE` 增加断言"生产必须为 true"（或增加 `-Production` 开关强制）；③对 `DB_PASSWORD` 增加最小长度/非占位符断言；④Redis 密码项先在 .env.example 补齐再纳入校验（依赖 X01/X06）。改动面：小（脚本单文件）。
- **关联**：[[X02-05]]（admin 密码同属 check-deploy-env 覆盖缺口）/ [[X06-config-consistency]]（COOKIE_SECURE/CORS/DB_PASSWORD 主归属）/ [[X01-deployment]]（端口暴露）/ 横向主题配置一致性

---

## `[Arch]` 架构与技术债

> 排查范围：脚本组织、可维护性、无 CI、跨平台、与既有审计文档的关系。注意共享对象按 §8.6 归属。

### [P1] [Arch] 完全无 CI，所有发布质量门禁靠手动 PowerShell，PR 无自动验证  <!-- 编号：X04-06 -->
- **定位**：CI 文件探测——`.github/workflows/`（Glob 无结果）、`.gitlab-ci.yml` / `Jenkinsfile` / `azure-pipelines.yml` / `.circleci/config.yml`（均不存在）。门禁逻辑全在 `scripts/release/release-gate.ps1`，靠 `deploy/README.md:129-139` 的手动命令引导执行。
- **现象**：项目无任何 CI 配置。`release-gate.ps1` 提供了一键闸门（audit/build/test/compose/smoke），但**必须人工在 Windows 机器上手动跑**。PR 合并、push 到 master、tag 发布均无自动触发的构建/测试/lint。
- **影响**：
  - **易遗忘**：单人维护，"赶进度直接合 PR"是真实场景，release-gate 形同虚设。审计基线显示工作区常有未提交改动（当前 release-gate.ps1 本身就是脏的），说明开发流不总是"先过闸门再提交"。
  - **漂移无防线**：§9 已记的 schema 三轨漂移、AI_MODEL 三处不一致、admin 弱口令等，若有 CI 跑测试 + 配置一致性检查可早暴露，现在全靠人工 release-gate。
  - **复现性差**：release-gate 报告只生成在本地 `artifacts/release-gate/`，无 CI artifacts 留痕，事后无法追溯"上次发布是否真的过了闸门"。
  - **跨平台封锁**：闸门是 PowerShell + Windows 命令（见 X04-08），未来若要加 CI，需先把脚本去 Windows 化或用 GitHub Actions 的 windows-latest runner。
- **根因/分析**：MVP 阶段单人 Windows 开发，手动闸门"够用"。但随着审计本身（42 模块）暴露的问题积累，没有 CI 意味着每个修复都要靠人工记得跑闸门验证，回归风险高。已排除"项目用 Codex/AI agent 自动提交"——agent 提交也不触发任何验证。这是 §9 已知线索 `[Arch/P2] 无 CI` 的本模块视角细化，升级为 P1（因为 release-gate.ps1 自身在工作区是脏的，证明"手动闸门"在实践中未被严格执行）。
- **修复方向**：①最小 CI：GitHub Actions 一个 workflow，触发 push/PR，跑 backend `mvn test` + crawler `pytest` + frontend `npm run build` + `docker compose config`（用 ubuntu-latest，需脚本去 Windows 化或加 bash 等价版）；②进阶：把 check-deploy-env 和 release-gate 的核心检查（不含 smoke）拆成跨平台脚本，CI 复用；③短期兜底：加 husky/git hook 在 commit 前强制跑 `release-gate -Fast`。改动面：中-大（CI 搭建 + 脚本跨平台化）。
- **关联**：§9 已知线索"无 CI"；次维度 `[Design]` 可运维性；横向主题配置/schema 一致性（CI 是这些主题的自动防线）

### [P2] [Arch] release-gate.ps1 单文件 474 行，职责耦合  <!-- 编号：X04-07 -->
- **定位**：`scripts/release/release-gate.ps1:1-474`（整体）
- **现象**：单文件混合 6 类职责：①secret 脱敏（46-65）；②Job 执行器（80-137）；③资源快照/压力检查（149-302，150+ 行，最重）；④preflight（304-337）；⑤Markdown 报告生成（339-373）；⑥主流程编排（375-473）。资源检查逻辑（Windows 计数器解析、WSL 内存、docker stats）占了文件 1/3。
- **影响**：可维护性差——改压力检查阈值（如 `$MinAvailableMemoryMB`）要在 170 行的 `Get-WindowsResourcePressureText` 里翻；新增一个发布步骤要在主流程（375-436）插一段 `if/else`，易漏 Skip 开关处理。工作区当前 dirty 状态（release-gate.ps1 已改）说明这文件在被反复编辑，单文件放大冲突面。
- **根因/分析**：脚本演进的产物，从简单编排逐步加了资源检查/报告/secret 脱敏。没有按职责拆模块（如 `ReleaseStep.psm1`、`ResourcePressure.psm1`、`Report.psm1`）。已排除"PowerShell 拆模块复杂"——PS 支持 `.psm1` 模块和 dot-sourcing，拆分可行。
- **修复方向**：①按职责拆 3-4 个 `.psm1`（resource / report / steps / main）；②主文件只保留参数解析和编排；③压力检查独立成可单独调用的诊断脚本。改动面：中（重构，行为不变需重测）。
- **关联**：次维度 `[Design]` 可运维性

### [P2] [Arch] 脚本强绑 Windows，Linux/Mac 部署无等价闸门  <!-- 编号：X04-08 -->
- **定位**：`scripts/release/release-gate.ps1:153,196,239,307-321,380-405`；`scripts/release/start-local-smoke-services.ps1:41,95,107`
- **现象**：Windows 专属点密集：
  - `Get-Counter`（release-gate:153,196）—— Windows 性能监视器，Linux/macOS 无此 cmdlet
  - `Get-NetTCPConnection`（start-local-smoke:41）—— Windows 网络命令
  - `npm.cmd` / `mvn.cmd`（release-gate:307-312,380,386,399；start-local-smoke:95）—— `.cmd` 后缀在 Linux 不存在（应为 `npm`/`mvn`）
  - `crawler-service\.venv\Scripts\python.exe`（release-gate:317,392；start-local-smoke:107）—— Linux venv 路径是 `.venv/bin/python`
  - `wsl` / Hyper-V 计数器（release-gate:196,276-285）—— Linux 原生无 WSL
  - 资源压力检查有 `$IsWindows` 守卫（第 239 行跳过），但其他步骤无守卫，Linux 跑会在 preflight 找不到 `npm.cmd` 直接 FAIL
- **影响**：项目 `deploy/docker-compose.yml` 本身是跨平台的（Linux 部署完全可行），但发布闸门只能在 Windows 跑。若未来部署到 Linux 服务器（云主机常见）或在 macOS 开发，无等价闸门，回到 X04-06 的"无自动验证"困境。
- **根因/分析**：脚本为作者本地 Windows + WSL + Docker Desktop 环境定制（risk-register 已记"Windows + WSL2 + Docker Desktop"环境约束）。资源压力检查（内存/WSL）是对该环境内存泄漏痛点的针对性防御，合理但不可移植。已排除"PowerShell Core 跨平台"——pwsh 装在 Linux 能跑 .ps1，但 `Get-Counter`/`Get-NetTCPConnection`/`.cmd` 这些是命令/cmdlet 限制，非 PS 版本问题。
- **修复方向**：①命令名去 `.cmd` 后缀（PowerShell 会自己解析 PATH，`npm` 比 `npm.cmd` 更可移植）；②venv 路径按 `$IsWindows` 分支选 `Scripts/python.exe` 或 `bin/python`；③资源压力检查加 Linux 等价（`free -m`、`/proc/meminfo`、`ps`）；④start-local-smoke 的 `Get-NetTCPConnection` 换 `Test-NetConnection` 或 `Get-NetTCPConnection` 的 Linux 等价。改动面：中。
- **关联**：[[X04-06]]（无 CI 加剧跨平台问题——CI 若用 ubuntu runner 也跑不了当前脚本）；[[X01-deployment]]（部署架构主归属）

---

## `[Deps]` 依赖升级与版本

### 本模块依赖清单（基于声明文件，未翻依赖源码）

| 依赖 | 版本 | 声明位置 | 已知风险/可升级 | 备注 |
|---|---|---|---|---|
| PowerShell | 未在项目声明（系统依赖） | 无 `#Requires` 声明 | 用了 `$IsWindows` 自动变量 → 需 PS 6+（PowerShell Core）；`Get-Counter` 在 PS 7 仍可用 | 脚本未声明最低版本，Windows PowerShell 5.1 跑会因 `$IsWindows` 不存在而行为异常 `[需查证]` |
| docker CLI | 未声明 | `release-gate.ps1:213,269,313` 调用 `docker stats`/`docker compose config` | 可选（缺则跳过相关检查） | 用 `Test-CommandAvailable` 守卫，缺 docker 不阻断（除 compose config 步骤） |
| wsl CLI | 未声明 | `release-gate.ps1:276-285` 调用 `wsl --status` | 仅 Windows，可选 | 有 `Test-CommandAvailable` 守卫 |
| npm / mvn / python | 由其他模块声明 | 脚本通过 `Test-CommandAvailable` 探测 | 见 X03 / B / C 各模块 | 脚本不强约束版本 |

> 排查范围：脚本调用的外部命令。无 npm/mvn/python 版本硬约束（仅 preflight 探测存在性）。

### [P3] [Deps] PowerShell 最低版本未声明，Windows PowerShell 5.1 兼容性存疑  <!-- 编号：X04-09 -->
- **定位**：`scripts/release/release-gate.ps1`（无 `#Requires -Version` 声明）；关键自动变量 `$IsWindows`（第 239 行）、`$PSVersionTable.PSEdition`（第 239 行）
- **现象**：脚本用了 `$IsWindows`（PowerShell 6+ 自动变量，Windows PowerShell 5.1 中**不存在**，值为 `$null`，`-not $null` = `$true`，逻辑会误判为 Windows 走计数器分支，但 5.1 在 Windows 上跑 `Get-Counter` 反而正常——巧合可用）。但 `$PSVersionTable.PSEdition`（5.1 = `Desktop`，6+ = `Core`）的判断逻辑在 5.1 下 `-and "Desktop"` 仍为真分支，逻辑成立。`Start-Job` 在 5.1/7 行为一致。
- **影响**：Windows PowerShell 5.1（Windows 10 自带）能否跑通未验证。`Get-Counter`、`Start-Job`、`Invoke-RestMethod` 在 5.1 都存在，理论可用，但 `[System.Collections.Generic.List[object]]`（第 29 行）等泛型在 5.1 支持但语法更脆。无法静态断言，标 `[需查证]`。
- **根因/分析**：脚本未声明 `#Requires -Version 7`，也未在 README 说明需 PowerShell 7。`deploy/README.md` 未提 PowerShell 版本要求。
- **修复方向**：①文件头加 `#requires -Version 7.0`；②README 说明需安装 PowerShell 7（pwsh）；③或在 5.1 上实测一轮补兼容。改动面：小。
- **关联**：次维度 `[Arch]` 跨平台

---

## `[Design]` 功能设计合理性

> 必填。从真实使用出发，回答 §2.5 相关问题（≥2）。本节重点：手动闸门 vs CI 的可靠性、PowerShell 单平台限制、check-deploy-env 覆盖缺口（Design 视角，非 Security 视角——Security 已在 X04-05 记）。

**审视结论**：

1. **场景适配（§2.5-1）**：单人 Windows 维护的技术博客 + 每工作日 AI 日报场景下，这套 PowerShell 闸门**设计取向合理但已到瓶颈**。release-gate 把"审计/构建/测试/compose/smoke/资源压力"串成一键，对单人减少认知负担是正向的；digest-smoke 的 `-SelfTest` 离线自检设计聪明（不依赖服务就能验证断言逻辑）。但"必须手动在 Windows 跑"这一前提，在审计基线显示 release-gate.ps1 自身处于脏未提交状态时，证明手动执行纪律在松动——设计假设（人会记得跑闸门）与现实（赶进度跳过）已出现裂缝。

2. **闭环完整性（§2.5-2）**：发布闭环**在"触发"这一环是完整的**，但**在"强制执行"这一环断裂**。release-gate 有完整的 preflight→执行→报告→exit code 链，exit 1 能阻断下游脚本；但项目无 CI 无 git hook，"是否真的跑了 release-gate"全靠自觉。deploy/README 的上线检查清单（第 154-172 行）很详尽（含"已修改默认 admin 密码""生产域名已写入 CORS"等），但**清单是 markdown，不是可执行检查**——check-deploy-env 只覆盖清单的 6 项，其余十几项（admin 密码、DB_PASSWORD、COOKIE_SECURE、CORS、域名、AI 可用性等）靠人眼对照。这是 check-deploy-env 覆盖缺口（X04-05）的设计层根因。

3. **可运维性（§2.5-3）**：故障定位能力**中等**。release-gate 的 JSON+Markdown 双报告、超时/失败原因记录、资源快照（前后两次）、secret 脱敏都是亮点，事后能复盘。但 `Invoke-Step` 超时分支不调 `Print-Diagnostics`（X04-03）、Job 超时子进程泄漏（X04-01）、报告存本地无归档（无 CI），削弱了可追溯性。单文件 474 行（X04-07）也增加维护期故障定位成本。

### [P1] [Design] 发布质量门禁缺自动执行机制，手动闸门可靠性不足  <!-- 编号：X04-10 -->
- **定位**：`deploy/README.md:129-172`（手动命令 + 上线清单）；无 CI / 无 git hook（见 X04-06）
- **现象**：发布质量保障完全依赖开发者在发布前手动执行 4 条命令（release-gate -Fast / release-gate -RunSmoke / check-deploy-env / digest-smoke -SelfTest），并对照 13 项 markdown 清单逐条打勾。无任何自动触发（push/PR/tag）或强制门禁（git hook、分支保护）。
- **影响**：单人项目最大风险是"流程靠记忆"，而非技术缺陷。当前审计发现的 P1 问题（admin 弱口令 X02-05、AI 空壳 B13、schema 漂移 B15）能在有 CI 的项目里早暴露，这里全靠人工 release-gate 兜底，而 release-gate.ps1 在工作区是脏的（说明最近在改但未必跑过完整闸门）。这套设计在 MVP 阶段合理，但作为"试用版上线"的发布保障已不够。
- **建议方向**：①优先加最小 CI（见 X04-06 修复方向），把"必须跑闸门"从纪律变成机制；②短期加 pre-commit hook 跑 `release-gate -Fast`；③把 deploy/README 的 markdown 清单转为 check-deploy-env 的可执行断言（至少覆盖 DB_PASSWORD/COOKIE_SECURE/CORS/admin 密码）。标改动面：中。
- **关联**：[[X04-05]] [[X04-06]]；§9 已知线索"无 CI"

### [P4] [Design] check-deploy-env 设计为"日报链路最小集"而非"生产就绪全集"，存在定位偏差  <!-- 编号：X04-11 -->
- **定位**：`scripts/release/check-deploy-env.ps1:7-14`；对照 `deploy/README.md:67-76`（必填变量表含 DB_PASSWORD 等 7 项）
- **现象**：脚本名是 `check-deploy-env`（部署环境检查），但 `RequiredKeys` 实际是"日报能跑通"的最小集（AI/digest/key/加密 6 项）。`deploy/README.md` 第 68-76 行的"必填变量表"列了 7 项（含 DB_PASSWORD），脚本只校验 6 项，名字与实质不符。
- **影响**：开发者看到 `check-deploy-env.ps1 通过` 会以为"部署环境就绪"，实际只代表"日报链路的 key 配了"。这是 X04-05 覆盖缺口的设计层体现——脚本命名暗示了比实际更宽的保证。
- **建议方向**：①重命名为 `check-digest-release-env.ps1`（名实相符）；②或扩展校验项让名字成立（见 X04-05）。倾向 ②，因为改名会破坏 deploy/README 已有的命令引用。标改动面：小。
- **关联**：[[X04-05]]；次维度 `[Arch]` 命名语义

---

## 模块小结

### 严重度统计

| 级别 | 数量 | 条目编号 |
|---|---|---|
| P0 | 0 | — |
| P1 | 2 | X04-06, X04-10 |
| P2 | 4 | X04-01, X04-05, X04-07, X04-08 |
| P3 | 4 | X04-02, X04-03, X04-04, X04-09 |
| P4 | 1 | X04-11 |

### Top 风险（本模块最该先看的 ≤3 条）

1. **X04-06 / X04-10 无 CI + 手动闸门可靠性不足** —— 所有发布质量门禁靠手动 PowerShell，工作区 release-gate.ps1 本身脏未提交证明执行纪律松动；X04-05 的覆盖缺口（DB_PASSWORD/COOKIE_SECURE/CORS/admin 密码未校验）使"闸门通过≠生产就绪"。这是本模块核心 gap，建议优先加最小 CI + 扩展 check-deploy-env。
2. **X04-05 check-deploy-env 安全覆盖缺口** —— 6 项必填不含 DB_PASSWORD/COOKIE_SECURE/CORS/REDIS 密码/admin 密码，与 deploy/README 必填表不一致，易产生"闸门通过即安全"的错觉。关联 X02-05（admin）、X06（配置一致性）。
3. **X04-08 脚本强绑 Windows** —— release-gate 在 Linux/macOS 跑不通（npm.cmd/mvn.cmd/venv\Scripts\python.exe/Get-Counter），与 docker-compose 跨平台部署矛盾，且阻塞未来用 ubuntu CI runner。

### 修复优先级建议

- **立即**（P1）：
  - X04-06：搭最小 CI（GitHub Actions：mvn test + pytest + npm build + compose config），这是其他 P1 修复（admin 密码、schema 漂移）的自动防线
  - X04-10：把 deploy/README markdown 清单转为 check-deploy-env 可执行断言（与 X04-05 合并修复），或加 pre-commit hook
- **计划**（P2）：
  - X04-05：check-deploy-env 增加 DB_PASSWORD / COOKIE_SECURE / CORS / admin 密码校验（安全视角，配合 X06）
  - X04-01：`Invoke-Step` 超时分支改用 `Start-Process -PassThru` + `Kill($true)` 杀进程树
  - X04-07：release-gate 按职责拆 `.psm1`
  - X04-08：脚本去 Windows 化（命令名/venv 路径/资源检查 Linux 等价）
- **择机**（P3/P4）：
  - X04-02：占位符黑名单扩展 + 密钥最小长度断言
  - X04-03：digest-smoke 超时分支补 `Print-Diagnostics`
  - X04-04：Redact-SecretText 补 JSON/日志前缀格式覆盖
  - X04-09：声明 `#requires -Version 7.0` + README 说明
  - X04-11：check-deploy-env 名实对齐（扩展校验优于改名）

### 排查盲区 / 待复核

- `[需查证]` **X04-09**：Windows PowerShell 5.1 实跑兼容性未验证（静态分析推测理论可用但泛型语法/`$IsWindows` 行为存疑）。建议在 Win10 自带 5.1 实测一轮。
- `[需查证]` **X04-01**：`Stop-Job -Force` 是否级联杀原生子进程，依赖 PowerShell 版本与 Job 实现细节。PS 7.x 下 `[diagnostics.process]::Kill()` 行为需实测确认泄漏。
- **未执行**：四个脚本均未实际运行（§1.3 命令边界禁止 powershell 执行），所有结论基于静态阅读 + 正则/逻辑推演。release-gate.ps1 处于工作区脏状态，若后续再改，编号 X04-01/06/07/08 的行号与职责描述需复核。
- **跨模块待补**：check-deploy-env 的 REDIS_PASSWORD 校验依赖 X01/X06 先在 .env.example 补齐该项（当前 .env.example 无 REDIS_PASSWORD 项）。
