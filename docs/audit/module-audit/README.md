# Nanmuli Blog 全模块排查 · 索引页

> 本文件是 `module-audit/` 排查的总索引与最终汇总。
> 计划见 [00-audit-plan.md](./00-audit-plan.md)，报告模板见 [_template.md](./_template.md)。
> 与 `docs/audit/full-project-risk-register.md` 的关系：本页是**证据层**（42 份模块报告），risk-register 是**汇总层**（计划 §1.5）。本次审计结论已对齐回写 risk-register。

## 审计基线

| 项 | 值 |
|---|---|
| 基线分支 | `codex/digest-generation-closure` |
| 基线 commit | `6ae930098405f4d0553d96a852f3345d0f39682e` |
| 工作区状态 | 脏（ConfigRepositoryImpl / WebCollectPageMapper / crawler 多文件 / deploy-README / risk-register / release-gate 等未提交；审计期间未触碰业务代码） |
| 审计区间 | 2026-06-23 ~ 2026-06-24 |
| 审计执行 | 6 批并行 agent + 协调者去重分级，全程只读 |

---

## 1. 进度总览

**统计**：✅ **完成 42 / 42** · 累计发现 **506**（**P0: 2** · **P1: 49** · P2: ~170 · P3: ~190 · P4: ~95）

> P2/P3/P4 为各模块自报累加近似值（含若干"确认安全/正向"条目），精确数字以各报告"严重度统计"为准。

### Backend（B01–B17）

| 编号 | 模块 | 难度 | 状态 | 报告 | 发现 | P0 | P1 |
|---|---|---|---|---|---|---|---|
| B01 | 文章 Article | 🟡 | ✅ | [报告](./backend/B01-article.md) | 16 | 0 | 2 |
| B02 | 分类 Category | 🟡 | ✅ | [报告](./backend/B02-category.md) | 13 | 0 | 2 |
| B03 | 技术日志 DailyLog | 🟢 | ✅ | [报告](./backend/B03-dailylog.md) | 10 | 0 | 0 |
| B04 | 展示类 Project/Skill/FriendLink | 🟢 | ✅ | [报告](./backend/B04-showcase.md) | 9 | 0 | 0 |
| B05 | 文件 File | 🟡 | ✅ | [报告](./backend/B05-file.md) | 13 | 0 | 1 |
| B06 | 认证授权 Auth/Security | 🔴 | ✅ | [报告](./backend/B06-auth-security.md) | 14 | **1** | 3 |
| B07 | 系统配置 Config | 🟡 | ✅ | [报告](./backend/B07-config.md) | 13 | 0 | 2 |
| B08 | WebCollector 采集编排 | 🔴 | ✅ | [报告](./backend/B08-webcollector.md) | 14 | 0 | 3 |
| B09 | 内部回调与跨服务同步 | 🔴 | ✅ | [报告](./backend/B09-internal-callback.md) | 14 | **1** | 2 |
| B10 | 日报公开查询 PublicDigest | 🟢 | ✅ | [报告](./backend/B10-public-digest.md) | 12 | 0 | 0 |
| B11 | 代理管理 Proxy | 🟡 | ✅ | [报告](./backend/B11-proxy.md) | 15 | 0 | 2 |
| B12 | 看板与首页 Dashboard/Home | 🟢 | ✅ | [报告](./backend/B12-dashboard-home.md) | 10 | 0 | 0 |
| B13 | AI 骨架 AiService/NoOp | 🔴 | ✅ | [报告](./backend/B13-ai-skeleton.md) | 10 | 0 | 2 |
| B14 | 数据访问层 | 🟡 | ✅ | [报告](./backend/B14-data-access.md) | 13 | 0 | 0 |
| B15 | 数据库与迁移 | 🔴 | ✅ | [报告](./backend/B15-database-migration.md) | 14 | 0 | 6 |
| B16 | 全局基础设施 | 🟡 | ✅ | [报告](./backend/B16-global-infra.md) | 14 | 0 | 0 |
| B17 | 调度与异步 | 🟢 | ✅ | [报告](./backend/B17-scheduling-async.md) | 7 | 0 | 0 |

### Crawler-service（C01–C12）

| 编号 | 模块 | 难度 | 状态 | 报告 | 发现 | P0 | P1 |
|---|---|---|---|---|---|---|---|
| C01 | API 层与中间件 | 🟡 | ✅ | [报告](./crawler/C01-api-layer.md) | 16 | 0 | 2 |
| C02 | 鉴权与服务边界 | 🟡 | ✅ | [报告](./crawler/C02-auth-boundary.md) | 9 | 0 | 0 |
| C03 | 采集核心 | 🔴 | ✅ | [报告](./crawler/C03-crawling-core.md) | 14 | 0 | 1 |
| C04 | 日报生成编排 | 🔴 | ✅ | [报告](./crawler/C04-digest-orchestration.md) | 10 | 0 | 0 |
| C05 | AI 整理 | 🟡 | ✅ | [报告](./crawler/C05-ai-organizer.md) | 11 | 0 | 2 |
| C06 | 自动优化系统 | 🔴 | ✅ | [报告](./crawler/C06-optimization-system.md) | 13 | 0 | 2 |
| C07 | 知识库与强闭环 | 🔴 | ✅ | [报告](./crawler/C07-knowledge-base-closeloop.md) | 7 | 0 | 1 |
| C08 | 质量与去重 | 🟡 | ✅ | [报告](./crawler/C08-quality-dedup.md) | 13 | 0 | 1 |
| C09 | 数据层 SQLite | 🟡 | ✅ | [报告](./crawler/C09-data-layer-sqlite.md) | 11 | 0 | 0 |
| C10 | 调度器 | 🟡 | ✅ | [报告](./crawler/C10-scheduler.md) | 14 | 0 | 2 |
| C11 | 配置同步 | 🟡 | ✅ | [报告](./crawler/C11-config-sync.md) | 12 | 0 | 0 |
| C12 | 硬编码规则与维护性 | 🟡 | ✅ | [报告](./crawler/C12-hardcoded-rules.md) | 6 | 0 | 0 |

### Frontend（F01–F07）

| 编号 | 模块 | 难度 | 状态 | 报告 | 发现 | P0 | P1 |
|---|---|---|---|---|---|---|---|
| F01 | 路由与鉴权守卫 | 🟡 | ✅ | [报告](./frontend/F01-routing-auth.md) | 10 | 0 | 0 |
| F02 | 请求层 | 🟡 | ✅ | [报告](./frontend/F02-request-layer.md) | 13 | 0 | 2 |
| F03 | 编辑与渲染（md 双轨） | 🟡 | ✅ | [报告](./frontend/F03-edit-render.md) | 17 | 0 | 0 |
| F04 | 采集与日报管理页 | 🔴 | ✅ | [报告](./frontend/F04-collector-digest-admin.md) | 14 | 0 | 0 |
| F05 | 配置与代理管理页 | 🟡 | ✅ | [报告](./frontend/F05-config-proxy-admin.md) | 13 | 0 | 0 |
| F06 | 状态管理 Pinia | 🟢 | ✅ | [报告](./frontend/F06-state-management.md) | 5 | 0 | 0 |
| F07 | 构建与依赖 | 🟡 | ✅ | [报告](./frontend/F07-build-deps.md) | 13 | 0 | 2 |

### 横切全局（X01–X06）

| 编号 | 模块 | 难度 | 状态 | 报告 | 发现 | P0 | P1 |
|---|---|---|---|---|---|---|---|
| X01 | 部署架构 | 🟡 | ✅ | [报告](./crosscutting/X01-deployment.md) | 18 | 0 | 2 |
| X02 | 数据库 schema 完整性（跨子系统） | 🔴 | ✅ | [报告](./crosscutting/X02-schema-integrity.md) | 14 | 0 | 2 |
| X03 | 测试体系 | 🟡 | ✅ | [报告](./crosscutting/X03-testing.md) | 9 | 0 | 2 |
| X04 | 发布脚本与 CI | 🟡 | ✅ | [报告](./crosscutting/X04-release-scripts.md) | 11 | 0 | 2 |
| X05 | 文档一致性 | 🟢 | ✅ | [报告](./crosscutting/X05-doc-consistency.md) | 12 | 0 | 0 |
| X06 | 配置一致性 | 🟡 | ✅ | [报告](./crosscutting/X06-config-consistency.md) | 10 | 0 | 1 |

---

## 2. 🔴 P0 阻断级发现（上线前必须处理）

| 编号 | 维度 | 标题 | 模块 | 备注 |
|---|---|---|---|---|
| **B06-04** | Security | **`deploy/.env` 真实密钥在 git 历史泄漏**（5 类凭据，commit `4523b7f`/`247afe4`） | B06 | 必须轮换全部密钥 + 清理历史；归 X06 执行 |
| **B09-01** | Bug | 批量指纹 `@Insert` SQL 漏 `id` 列，跨日去重持久化恒失败 | B09 | 日报"跨日去重"核心能力生产失效 |

---

## 3. Top 高优发现（P1，按主题去重聚合）

> 共 49 条 P1，去重后约 **25 个独立问题**。同因多视角条目合并，主编号在前。

### 3.1 安全与密钥（最高优先）

| 主编号 | 标题 | 关联 |
|---|---|---|
| B06-04 | git 历史密钥泄漏（P0） | X06 执行清理 |
| B15-02 | admin 默认弱口令 `admin123` 三处 seed | X02-05；check-deploy-env 未覆盖（X04-05） |
| B07-01 | AES 弱默认密钥 `local-dev-encryption-key` 通过校验 | B07-02 ECB 无 IV、B07-03 失败回退明文 |
| X01-07 | postgres/redis/backend/crawler 端口全公网发布 | X01-08 redis 无密码可伪造 admin token（P2 但严重） |
| B11-06 | 代理订阅 URL 无 SSRF 校验 | B11-01 订阅刷新 provider 名硬编码致功能必失败 |
| C01-04 | SSRF 不覆盖重定向/BFS 子链接 | C01-05 /health 泄漏内部状态 |

### 3.2 鉴权机制

| 主编号 | 标题 | 关联 |
|---|---|---|
| B06-05 | 鉴权纯靠 URL 前缀，role 是死字段（假 RBAC） | B06-11 role 大小写三轨不一（潜伏地雷，当前不影响） |
| B06-06 | sys_login_log 死表，无登录失败锁定/审计 | 弱口令+无锁定+宽松限流=真实爆破窗口 |
| B07-06 | `/api/admin/config/**` 仅 checkLogin 不校验角色 | B12-03 dashboard 同问题 |

### 3.3 schema 与配置（根因 B15-04）

| 主编号 | 标题 | 关联 |
|---|---|---|
| B15-04 | **Flyway 完全未集成**（一切 schema 漂移根因） | 连带消解 B15-05/06/07/08/09/10、B15-12 Deps、B15-14 Design |
| B15-05 | schema 三轨漂移致 fresh deploy 缺列缺索引 | 缺 `python_task_id` 列、`idx_task_python_id` 索引、`ai_generation` 表 |
| B15-06 | config seed 三轨漂移（V1_21 删的 64 项仍 seed） | X06-02/08、C04-02/03 |
| X06-01 | **AI_MODEL `deepseek-v4-pro` 疑似无效** → 日报硬失败无兜底 | C05 已确认传播链路；CLAUDE.md"日报可试用"在此 model 下不成立 |

### 3.4 日报/采集闭环

| 主编号 | 标题 | 关联 |
|---|---|---|
| B09-01 | 指纹持久化恒失败（P0） | C08-01 simhash 溢出（dedup.py 产生无符号64位→Java 负值→回读错误） |
| C03-01 | deep.py crawler=None 分支 use-after-close | C03-02 JS challenge 阈值不一致 |
| C05-01 | generate_digest 无重试无降级 | C05-10 digest 失败无兜底 |
| C04-01 | global timeout 后日报评估不进 KB | C07-06 circuit-breaker 失明；趋势统计偏向"顺利完成的" |
| C10-12 | 日报 cron 无 misfire 补偿 | C10-01 日报全流程无 APScheduler 超时 |

### 3.5 优化系统

| 主编号 | 标题 | 关联 |
|---|---|---|
| C06-07 | keyword vs digest 两套优化循环已实际漂移 | C06-08 source_expand 死代码；§9 已知线索细化为 P1 |
| C06-11 | digest 强制 heuristic 评分，放弃 AI 评估 | C06-13 优化系统默认全关 |

### 3.6 AI 空壳链路

| 主编号 | 标题 | 关联 |
|---|---|---|
| B13-02 | Java AI 端口/表/事件全建但全 NoOp | git 历史证实"迁移残留"（commit `0374b1b`）非预留 |
| B13-08 | [Design] 建议清理 Java AI 骨架 | X02-07 article_vector 零 Repository、B15-11 ai_generation 死表、X05-08 文档夸大 |

### 3.7 前端

| 主编号 | 标题 | 关联 |
|---|---|---|
| F02-01 | 重试不区分 HTTP 方法，POST/PUT/DELETE 5xx 自动重试 | 写操作重复执行（triggerDigest/refreshConfigs） |
| F02-02 | 多文件并发上传 FormData 序列化致 key 相同 | 后发 abort 先发，多图上传确定性失败 |
| F07-06 | vue-tsc 1.8 严重落后 vue 3.5，类型门禁失效 | F07-07 persistedstate v3 EOL、F07-04 splitVendor 阻塞 vite 6 |

### 3.8 部署/测试/发布

| 主编号 | 标题 | 关联 |
|---|---|---|
| X01-01 | prod 上传/日志路径三处不一致，上传文件丢失 | X01-02 nginx 限流死代码 |
| X03-02 | backend 全 Mockito 单测零集成 | Sa-Token/MyBatis/真实 PG 从未在 CI 跑 |
| X03-03 | backend 覆盖失衡，webcollector 占 69% | Auth/User/领域层 0；frontend 0 单测 |
| X04-06 | 完全无 CI，所有门禁靠手动 PowerShell | X04-10 手动闸门可靠性；release-gate.ps1 自身处于脏未提交状态 |

---

## 4. 横向主题（跨模块聚合，计划 §2.6）

### 4.1 日报生成闭环完整性（最核心业务链路，断裂点多）
- **跨日去重失效**：B09-01（指纹 P0）+ C08-01（simhash 溢出）→ 跨日去重实际仅靠 URL 兜底
- **AI 生成脆性**：X06-01（model 无效）+ C05-01（无降级）→ 当天日报可能硬失败
- **评估数据缺失**：C04-01（global timeout 不写 KB）+ C07-06（circuit-breaker 失明）→ 趋势统计偏向
- **调度缺口**：C10-12（misfire 无补偿，重启错过 8:00 当天日报丢失）+ C10-01（无端到端超时）
- **采集执行**：C03-01（deep use-after-close）
- **结论**：日报"看起来能用实则多处在空转/半断裂"，CLAUDE.md 声称的"MVP Beta 可试用"在多个前置条件（model 有效、指纹修复、misfire 补偿）未满足时不成立

### 4.2 schema 漂移（根因 B15-04 Flyway 未集成）
- 三轨差异 22 项对象 diff：B15-05
- 文档撒谎：X05-02/X05-03（Flyway 自称在用）
- config seed 漂移：B15-06/07、X06-02
- 双库（SQLite vs PG）不一致 7 类：X02

### 4.3 配置一致性（主 X06）
- AI_MODEL 无效（X06-01 + C05 确认）
- env vs sys_config 冷热生效不对称（C11-01/11）：改 env 冷生效、改 sys_config 需手动 refresh，无文档
- check-deploy-env 覆盖缺口（X04-05）：DB_PASSWORD/COOKIE_SECURE/CORS/REDIS 密码/admin 密码均未校验

### 4.4 鉴权与密钥安全（多处一致问题）
- 假 RBAC + URL 前缀鉴权（B06-05）
- 多处 admin 越权（B07-06、B12-03）
- key 校验非恒定时间（B06-07、B09-07、C02-01）
- AES 弱默认密钥 + ECB（B07-01/02/03）
- 端口公网 + redis 无密码（X01-07/08）

### 4.5 半成品/死代码/空转（Design 维度集中浮现）
- article_draft 死表、ArticleCreatedEvent 死事件（B01-10/11）
- 文件模块整体无业务消费方（B05-09，孤岛图床）
- tags 假能力（B03-01，schema 有列代码零实现）
- Project screenshots UI 断链、FriendLink 审核状态不可达（B04-08/05）
- Java AI 骨架迁移残留（B13）
- sys_login_log 死表（B06-06）
- keyword 优化循环死代码（C06-08）、优化系统默认全关（C06-13）
- 代理订阅刷新必失败（B11-01）
- 过度设计：优化系统（C06）、文件模块多存储（B05）、代理管理嵌入博客（B11-14）、前端 abort 机制（F02-12）

### 4.6 可运维性 / 可观测性短板（多模块 Design 共识）
- 异常吞掉无告警：B14-02、B17-01、B07-04（crawler 重载假成功）
- 故障不可感知：X02（指纹/SourceAuthority 同步失败仅 warning）、C11-03（配置缓存无 TTL 无可观测）
- traceId 不回传响应：B16-13
- 无连续失败告警/手动触发：B17-06、C10
- 超时日报无人工干预标记：C04-10
- 配置/日报变更无审计历史：B07-12、B15

### 4.7 跨服务契约一致性
- crawler callback ↔ backend 字段：X02-01/02/04、B09-12（裸 Map 无 DTO）
- crawler ↔ backend 配置 key：X06-08/09、C11
- 前端 ↔ 后端：B08-12（updateTaskFromPython 弱类型 Map）、F04-02（triggerDigest 硬编码契约）、F04-10（snake/camel 混用）

---

## 5. 待复核清单（`[需查证]` 高优，全量见各报告）

| 编号 | 待查问题 | 潜在升级 | 归属/方法 |
|---|---|---|---|
| B06-04 | git 历史全部 commit 的 .env 内容全量确认 | 清理前必做 | `git log -p -- deploy/.env` |
| X06-01 | `deepseek-v4-pro` 是否 DeepSeek 官方有效 model | 若无效→日报硬失败（已强佐证） | 真实 API 验证 |
| B15-01 | PG 内联 UNIQUE 默认约束名是否恒为 `article_slug_key` | 若否→409 退化为 500 | 真实 PG 实例 |
| X02-11 | admin role 大小写敏感？ | 当前不影响（全库零读取），潜伏地雷 | B06 已确认零读取 |
| C08-01 | Python `bin(负数).count('1')` 精确行为 | 影响 simhash 比较修复 | CPython 实现细节 |
| C03-05 | feedparser 6.x 是否解析外部实体（XXE） | 若是→XXE | feedparser 文档 |
| C01-04 | Crawl4AI 是否提供落地 URL hook 供二次 SSRF 校验 | 网络层防护 | 依赖文档 |
| X01-09 | ankane/pgvector 仓库当前可用性（已归档） | 镜像拉取失败 | docker pull |
| B05 | md5 去重在逻辑删除下的预期语义 | 影响修复 | 产品决策 |

---

## 6. 修复排期建议（按严重度批次）

| 批次 | 优先级 | 代表条目 | 说明 |
|---|---|---|---|
| **第 0 批·上线阻断** | P0 | B06-04（密钥轮换+历史清理）、B09-01（指纹 @Insert 补 id） | 上线前必须 |
| **第 1 批·安全加固** | P1 安全 | B15-02（admin 密码）、B07-01/02（AES）、X01-07/08（端口/redis 密码）、B11-06（SSRF）、B06-05（鉴权注解） | 可利用/爆破窗口 |
| **第 2 批·根因架构** | P1 Arch | B15-04（接入 Flyway 或放弃承诺，连带消解 6 条）、B13（清理 Java AI 骨架）、C06-07（统一优化循环） | 根因修复，连带消解多条 |
| **第 3 批·日报闭环** | P1 业务 | X06-01（AI_MODEL）、C05-01（digest 降级）、C04-01+C07-06（timeout 写 KB）、C10-12（misfire 补偿）、C03-01（deep）、C08-01（simhash） | 日报"可试用"成立的前提 |
| **第 4 批·前端/构建** | P1 | F02-01/02（写操作重试/上传）、F07-06（vue-tsc） | 写操作安全+类型门禁 |
| **第 5 批·质量基建** | P1 | X04-06（加最小 CI）、X03-02/03（testcontainers 集成基座+补 Auth/Config 测试） | 把门禁从纪律变机制 |
| **第 6 批·技术债/漂移** | P2 | schema 三轨对齐、文档基线校准（X05）、配置一致性（X06）、check-deploy-env 补全（X04-05） | 计划修复 |
| **第 7 批·优化** | P3/P4 | 死代码清理、大文件拆分、可观测性、半成品决策 | 择机 |

---

## 7. 批次执行记录

| 批次 | 模块 | 状态 | 发现 | P0/P1 | 备注 |
|---|---|---|---|---|---|
| 批 1 基础设施底座 | B14 B15 B16 B17 X02 X05 X06 | ✅ | 84 | 0/9 | B15 确认 Flyway 未集成根因；B15/X02 质量已抽查达标 |
| 批 2 Backend 业务上 | B01 B02 B03 B04 B05 B12 | ✅ | 71 | 0/5 | 首轮 4 个 agent API 中断已重试；半成品/死代码集中浮现 |
| 批 3 Backend 业务下+集成 | B06 B07 B08 B09 B10 B11 B13 | ✅ | 92 | **2**/14 | **2 个 P0**：B06-04 git 密钥泄漏、B09-01 指纹失效；B13 定性 Java AI 迁移残留 |
| 批 4 Crawler 核心 | C01 C02 C03 C04 C05 | ✅ | 60 | 0/5 | C05 确认 X06-01（deepseek-v4-pro 无效→日报硬失败） |
| 批 5 Crawler 智能优化 | C06-C12 | ✅ | 76 | 0/6 | C06/C11 首轮 429 限流已重试；C08 确认 simhash 溢出；C07 强闭环非空壳 |
| 批 6 Frontend+部署发布 | F01-F07 X01 X03 X04 | ✅ | 123 | 0/10 | F07 vue-tsc 失效；X01 端口公网+redis 无密码；X03 测试失衡量化；X04 无 CI |

---

## 8. 核心判断（审计总结）

1. **项目主链路"看起来完整，实则多处在空转/半断裂"**。最典型的三条：日报跨日去重（B09-01 P0 + C08-01）、日报 AI 生成（X06-01 无效 model + C05-01 无降级）、Java AI 骨架（B13 迁移残留）。README/CLAUDE.md 声称的"MVP Beta 可试用"在多个前置条件未修复时不完全成立。

2. **最大的根因是 schema 管理机制（B15-04 Flyway 未集成）**。一条根因连带 6 条 P1（三轨漂移、config seed 漂移、缺列缺索引）。修复这一根因性价比最高。

3. **安全问题不是设计缺失而是实现/部署疏漏**：密钥进 git 历史（B06-04 P0）、弱默认密钥+ECB（B07）、端口全公网+redis 无密码（X01）、admin 弱口令（B15-02）、假 RBAC（B06-05）。修复成本普遍不大（多为配置/单文件），但必须在上线前完成。

4. **测试体系与 CI 是质量基建的双重缺口**：backend 111 个单测全 mock（X03-02）、无任何 CI（X04-06）。MVP 最怕的"登录失败/配置不生效/schema 缺列/日报不触发"恰好看不住。加最小 CI + testcontainers 集成基座是把"门禁"从纪律变机制的关键。

5. **Design 维度集中暴露"过度设计 + 未完成的半成品"并存**：优化系统（C06）、文件多存储（B05）、代理管理（B11）过度设计；同时 article_draft/ArticleCreatedEvent/tags/Java AI/sys_login_box 等死代码/空壳堆积。建议做一次"去半成品"清理，让代码与"真实在跑"一致。

6. **正向确认（避免误报）**：XSS 防护有效（F03，后端 Jsoup + 前端 DOMPurify 双重净化）、SQL 全参数化无注入（B14/B06）、对账调度器不误杀任务（B17）、强闭环是真闭环非空壳（C07）、dist 未提交仓库（F07 澄清）、RateLimitFilter 已规避 XFF 伪造（B06）。
