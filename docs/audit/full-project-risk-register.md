# Full Project Risk Register

> Created: 2026-06-22
> Rule: every P0/P1 item must have source evidence and a verification command before it is marked fixed.

| Module | Entrypoint | Risk | Evidence | Priority | Owner Task | Status |
| --- | --- | --- | --- | --- | --- | --- |
| Backend config | `application-prod.yml` | Production encryption key had a dangerous default fallback. Missing env could silently use a known key. | `blog.security.encryption-key: ${BLOG_SECURITY_ENCRYPTION_KEY:nanmuli-blog-key}` | P0 | Secret and production config hardening | Fixed, targeted tests passing |
| Backend DB seed | `db/init.sql`, `V1_12__unify_sys_config.sql`, deploy schema | Seed data stored `blog.security.encryption-key` as `nanmuli-blog-key`, which can mislead fresh deployments and leak weak config into DB. | `rg nanmuli-blog-key backend/src/main/resources deploy/db` | P0 | Secret and production config hardening | Fixed, grep verified |
| Backend internal API | `/api/internal/collector/**` | Callback/config endpoints intentionally bypass Sa-Token and rely on shared key. Blank-key behavior must stay blocked in prod and tested. | `InternalCallbackController.authRequired`, `configAuthRequired` | P0 | Backend auth sweep | Fixed, targeted tests passing |
| Backend config API | `/api/admin/config/**` | Sensitive values must never be returned as plaintext after initial seed; mask behavior needs regression coverage. | `ConfigAppService.toAdminDTO`, `toPublicDTO` | P0 | Secret and production config hardening | Fixed, targeted tests passing |
| Backend upload | `/api/admin/file/upload` | File size and Magic Number checks were previously swallowed by malformed comment lines; original names lacked path/control character validation. | `FileAppService.upload`, `FileAppServiceTest` | P0 | Input validation and upload safety | Fixed, targeted tests passing |
| Backend pagination | page query services/controllers | Direct service calls or missing `@Valid` can bypass REST pagination limits and request oversized pages. | `BasePageQuery`, `DailyLogAppService.listPage`, `FileController.list` | P0 | Pagination resource guard | Fixed, targeted tests passing |
| Backend article persistence | public/admin article lists and search | Article list/search queries selected large `content/content_html` fields, increasing memory, DB IO, and response serialization cost. | `ArticleRepositoryImpl.applyListProjection`, `ArticleMapper.ARTICLE_LIST_COLUMNS`, `ArticleMapperProjectionTest` | P1 | Persistence and query performance sweep | Fixed, targeted tests passing |
| Backend file maintenance | `/api/admin/file/regenerate-thumbnails` | Thumbnail backfill loaded all files into memory before filtering images. | `FileAppService.regenerateMissingThumbnails`, `FileRepository.findImagesMissingThumbnail` | P1 | Persistence and query performance sweep | Fixed, targeted tests passing |
| Backend persistence | repositories and mappers | Full-table/default-column reads and wide raw-content queries can cause memory pressure as data grows. | `ConfigRepositoryImpl.findAll` now uses an explicit wrapper; `WebCollectPageMapper` now uses explicit columns with projection tests. | P1 | Persistence and query performance sweep | Mitigated, targeted tests passing |
| Local/runtime resources | Windows + WSL2 + Docker Desktop | Docker/WSL can retain several GB of idle VM memory and leave Windows with near-zero available memory, making tests and release checks unreliable. | `release-gate resource pressure check`, `Hyper-V VM Vid Partition(*)\Physical Pages Allocated`, `.wslconfig memory=4GB` | P0 | Release gate and runtime observability | Fixed, targeted gate added |
| Crawler runtime | browser crawl paths | Browser concurrency can multiply through digest sections and freeze local machines. | `resource_guard.py`, `single.py`, `deep.py`, `search.py`; search browser fetch now uses the same process-wide slot. | P0 | Crawler resource and failure isolation | Mitigated, targeted tests passing |
| Digest pipeline | public/admin digest APIs | Failed or quality-rejected digest records must not leak to public endpoints, but admin must retain diagnostics. | `standalone/routes.py`, frontend admin digest dirty baseline | P0 | Digest product contract sweep | Mitigated, needs full regression |
| Auto optimization | crawler optimization knowledge base | Negative, low-confidence, failed, or quality-rejected digest evaluations must not poison the next generation cycle. | `KnowledgeBase` now filters `digest_final_eval` feedback through the publishable digest contract before reusing weaknesses, trend, source actions, or fatigue hints. | P0 | Digest and auto-optimization safety | Fixed, crawler full regression passing |
| Frontend rendering | article/digest markdown, search highlights, external links | Dynamic external links must reject dangerous protocols while sanitized markdown remains covered. | `frontend/src/utils/url.ts`, `rg ':href="(configStore.siteGithub|link.url|row.url|item.source_url|source.source_url|row.primary_url|page.url|task.sourceUrl|article.originalUrl)' frontend/src` | P1 | Frontend XSS sweep | Fixed, build verified |
| Release tooling | release smoke/gate scripts | Release must fail on known-danger defaults, missing keys, failed audit/build/smoke, and runtime danger state. | `scripts/release/*.ps1`, `deploy/.env.example` | P0 | Release gate and runtime observability | Mitigated, resource pressure gate added |

---

## 模块审计对齐（2026-06-24 · 新增发现 · 待处理）

> 来源：[module-audit/README.md](./module-audit/README.md)（42 模块地毯式只读排查，506 条发现，2 P0 / 49 P1）
> 本节为本次独立审计**新发现**的 P0/P1，Status=Open，证据详见对应模块报告。
> 与上方既有 Fixed 条目可能存在视角重叠的项，需交叉确认是"回归"还是"不同视角"，再决定处置。

### P0 阻断（上线前必须）

| 编号 | 模块 | 风险 | 证据 | 状态 |
| --- | --- | --- | --- | --- |
| B06-04 | Backend auth | `deploy/.env` 真实密钥在 git 历史泄漏（5 类凭据，commit `4523b7f`/`247afe4`） | `git log -p -- deploy/.env`；module-audit/backend/B06 §B06-04 | Open |
| B09-01 | Backend internal callback | 批量指纹 `@Insert` SQL 漏 `id` 列，跨日去重持久化恒失败 | `DigestFingerprintMapper` 批量 insert；module-audit/backend/B09 §B09-01 | Open |

### P1 高优（去重后约 25 个独立问题，完整清单见 module-audit/README.md §3）

| 主编号 | 主题 | 证据 |
| --- | --- | --- |
| B15-04 | Flyway 完全未集成（schema 漂移根因，连带消解 6 条 P1） | module-audit/backend/B15 |
| B15-02 | admin 默认弱口令 `admin123` 三处 seed | module-audit/backend/B15 §B15-02 |
| B07-01/02 | AES 弱默认密钥 `local-dev-encryption-key` + ECB 无 IV | module-audit/backend/B07 |
| X01-07/08 | 端口全公网发布 + redis 无密码可伪造 admin token | module-audit/crosscutting/X01 |
| X06-01 | AI_MODEL `deepseek-v4-pro` 疑似无效 → 日报硬失败无兜底 | module-audit/crosscutting/X06 + crawler/C05 |
| B13 | Java AI 骨架迁移残留（commit `0374b1b`），建议清理 | module-audit/backend/B13 |
| B06-05 | 假 RBAC（鉴权纯靠 URL 前缀，role 死字段） | module-audit/backend/B06 |
| C08-01 | simhash 溢出（跨日去重二度失效） | module-audit/crawler/C08 §C08-01 |
| C04-01 / C07-06 | 日报 global timeout 后评估不进 KB，circuit-breaker 失明 | module-audit/crawler/C04、C07 |
| C10-12 / C10-01 | 日报 cron 无 misfire 补偿 + 无端到端超时 | module-audit/crawler/C10 |
| C06-07 | keyword vs digest 两套优化循环已实际漂移 | module-audit/crawler/C06 §C06-07 |
| F02-01 / F02-02 | 前端写操作 5xx 重试重复执行 / 多图上传 abort 确定性失败 | module-audit/frontend/F02 |
| F07-06 / F07-07 | vue-tsc 1.8 vs vue 3.5 类型门禁失效 + persistedstate v3 EOL | module-audit/frontend/F07 |
| X01-01 | prod 上传/日志路径三处不一致，上传文件丢失 | module-audit/crosscutting/X01 §X01-01 |
| B11-01 / B11-06 | 代理订阅刷新必失败 + 订阅 URL SSRF | module-audit/backend/B11 |
| X03-02 / X03-03 | backend 全 mock 零集成 + 覆盖失衡（webcollector 占 69%） | module-audit/crosscutting/X03 |
| X04-06 / X04-10 | 完全无 CI + 手动闸门可靠性 | module-audit/crosscutting/X04 |

### 与既有 Fixed 条目的交叉确认项

- **B07-01 vs 第 8 行**（encryption-key 默认 fallback Fixed）：用户已修 `application-prod.yml` 的 `${...:nanmuli-blog-key}` fallback，但本次发现 `AesEncryptor` 仍接受 `local-dev-encryption-key` 默认值通过弱密钥校验——可能是**不同层面**的残留，需确认。
- **B06-05 vs 第 10 行**（internal API 共享 key Fixed）：internal 端点的 key 校验已加固，但 admin 接口（`/api/admin/**`）的**角色校验缺失**（假 RBAC）是新增视角。
- **X06-01**：既有 risk-register 无对应条目，是本次新发现（AI_MODEL 无效）。

完整修复排期见 [module-audit/README.md](./module-audit/README.md) §6（7 个批次，从上线阻断→安全加固→根因架构→日报闭环→前端→质量基建→技术债）。
