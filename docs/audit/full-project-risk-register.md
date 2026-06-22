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
| Backend persistence | repositories and mappers | Full table reads and wide queries can cause memory pressure as data grows. | `ConfigRepositoryImpl.selectList(null)`, crawler `SELECT *` queries | P1 | Persistence and query performance sweep | Open |
| Crawler runtime | browser crawl paths | Browser concurrency can multiply through digest sections and freeze local machines. | `resource_guard.py`, `single.py`, `deep.py` dirty baseline | P0 | Crawler resource and failure isolation | Mitigated, needs full regression |
| Digest pipeline | public/admin digest APIs | Failed or quality-rejected digest records must not leak to public endpoints, but admin must retain diagnostics. | `standalone/routes.py`, frontend admin digest dirty baseline | P0 | Digest product contract sweep | Mitigated, needs full regression |
| Auto optimization | crawler optimization knowledge base | Negative or low-confidence optimization decisions must not poison the next generation cycle. | `optimization/knowledge_base.py` dirty baseline | P0 | Digest and auto-optimization safety | Mitigated, needs full regression |
| Frontend rendering | article/digest markdown, search highlights | `v-html` and `innerHTML` sinks need sanitizer and external URL validation coverage. | `rg v-html frontend/src`, `ArticleContent.vue`, digest detail views | P1 | Frontend XSS sweep | Open |
| Release tooling | release smoke/gate scripts | Release must fail on known-danger defaults, missing keys, failed audit/build/smoke, and runtime danger state. | `scripts/release/*.ps1`, `deploy/.env.example` | P0 | Release gate and runtime observability | In progress, resource snapshots added |
