# Full Project Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Systematically audit and harden Nanmuli Blog so severe security, reliability, performance, and release-blocking defects are found and fixed module by module.

**Architecture:** Treat this as a sequence of independently testable gates. Each module gets inventory, threat/performance scan, minimal fixes, regression tests, and release-gate evidence before moving to the next module.

**Tech Stack:** Spring Boot 3.3 / Java 21 backend, Vue 3 / Vite frontend, FastAPI / Python crawler, PostgreSQL, Redis, Docker Compose, PowerShell release scripts.

## Global Constraints

- Do not trust stale docs; verify every claim from source, config, tests, logs, or runtime output.
- Do not add database tables unless a task explicitly proves existing tables cannot carry the requirement.
- Preserve existing public API parameters unless a severe security issue requires a breaking change.
- Use TDD for behavior changes: write failing tests, verify red, implement, verify green.
- Keep unrelated refactors out of each task; commit module-by-module.

---

### Task 1: Baseline Inventory And Risk Register

**Files:**
- Create: `docs/audit/full-project-risk-register.md`
- Read: `backend/pom.xml`, `frontend/package.json`, `crawler-service/requirements.txt`, `deploy/docker-compose.yml`

**Interfaces:**
- Produces: a risk register with `module`, `entrypoint`, `risk`, `evidence`, `priority`, `owner_task`, `status`.

- [ ] Run `git status --short` and record all dirty files as current baseline.
- [ ] Run module inventory:
  - `rg -n "@(Get|Post|Put|Delete)Mapping|@RequestMapping" backend/src/main/java`
  - `rg -n "@router\\.|app\\." crawler-service`
  - `rg -n "path:|component:|createRouter|routes" frontend/src/router frontend/src`
- [ ] Create the risk register with P0/P1/P2 buckets.
- [ ] Commit only the register after review.

### Task 2: Secret And Production Config Hardening

**Files:**
- Modify: `backend/src/main/resources/application-prod.yml`
- Modify: `backend/src/main/resources/db/migration/*`
- Modify: `deploy/db/init-scripts/schema.sql`
- Test: `backend/src/test/java/com/nanmuli/blog/infrastructure/config/**`

**Known evidence to verify first:**
- `application-prod.yml` currently contains fallback `BLOG_SECURITY_ENCRYPTION_KEY:nanmuli-blog-key`.
- `deploy/db/init-scripts/schema.sql` seeds `blog.security.encryption-key` with `nanmuli-blog-key`.

- [ ] Add failing tests proving production startup/config validation rejects default encryption keys and blank crawler callback keys.
- [ ] Remove production fallback secrets; require env values in production.
- [ ] Ensure config admin masks all password/API key values and never returns plaintext after initial seed.
- [ ] Verify: `cd backend; mvn test`.

### Task 3: Backend Authentication And Authorization Sweep

**Files:**
- Read/modify: `backend/src/main/java/com/nanmuli/blog/interfaces/rest/**`
- Read/modify: `backend/src/main/java/com/nanmuli/blog/infrastructure/config/security/**`
- Test: controller/security tests under `backend/src/test/java`

- [ ] Inventory every `/api/admin/**`, `/api/internal/**`, and public `/api/**` route.
- [ ] Add tests for unauthenticated admin access, invalid callback keys, blank callback key in prod, and public-only routes.
- [ ] Verify controllers contain no business logic and no repository direct access.
- [ ] Verify: `cd backend; mvn test`.

### Task 4: Input Validation, Upload, SSRF, And Callback Safety

**Files:**
- Backend: `FileAppService.java`, controller command DTOs, callback controllers.
- Crawler: `crawler-service/api/ssrf_guard.py`, `crawler-service/standalone/routes.py`, `crawler-service/standalone/task_executor.py`.
- Tests: backend validation tests, crawler `test_crud_endpoints.py`, `test_routes_validation.py`.

- [ ] Add malicious/limit tests for URL params, callback URL, file names, file extensions, oversized bodies, and private network URLs.
- [ ] Fix any route that accepts URL/file/path input without length, scheme, host, extension, and private-address validation.
- [ ] Ensure failed callbacks cannot mark core tasks as completed.
- [ ] Verify: crawler route tests and backend tests.

### Task 5: Persistence And Query Performance Sweep

**Files:**
- Backend mappers/repositories under `backend/src/main/java/com/nanmuli/blog/infrastructure/persistence/**`.
- Crawler repository: `crawler-service/standalone/repository.py`.

**Known evidence to verify first:**
- `ConfigRepositoryImpl.java` uses `selectList(null)`.
- Several backend/crawler queries use `SELECT *`.

- [ ] Inventory all `SELECT *`, `selectList(null)`, unbounded list queries, and OFFSET-heavy pagination.
- [ ] Add tests for max page size, empty filters, and high page indexes.
- [ ] Replace unbounded full-table reads with explicit columns, limits, or cached admin-only paths.
- [ ] Verify: backend `mvn test`; crawler repository/API tests.

### Task 6: Crawler Resource And Failure Isolation

**Files:**
- `crawler-service/crawler/**`
- `crawler-service/standalone/scheduler.py`
- `crawler-service/standalone/task_executor.py`
- `deploy/docker-compose.yml`

- [ ] Keep the global browser crawl limiter and add runtime diagnostics for active/queued browser slots.
- [ ] Add tests that digest cannot multiply browser concurrency by section count.
- [ ] Add smoke script reporting for crawler memory, task count, and browser slot pressure.
- [ ] Verify: `test_resource_guard.py`, `test_search.py`, `test_digest_orchestrator.py`, smoke self-test.

### Task 7: Digest Product Contract And Quality Gate Sweep

**Files:**
- `crawler-service/crawler/digest_orchestrator.py`
- `crawler-service/crawler/digest_gen_agent.py`
- `crawler-service/standalone/digest_post_processor.py`
- `crawler-service/standalone/routes.py`
- `frontend/src/views/admin/digest/**`

- [ ] Re-test all failure states: AI missing, invalid output, quality reject, save failure, timeout, source starvation.
- [ ] Ensure public digest endpoints only expose publishable records.
- [ ] Ensure admin task detail always shows raw crawl data, quality gate reason, search diagnostics, event diagnostics, and optimization outcome.
- [ ] Verify: digest API, quality gate, orchestrator, task executor, frontend build.

### Task 8: Frontend XSS, Route, And State Robustness

**Files:**
- `frontend/src/views/**`
- `frontend/src/utils/markdown.ts`
- `frontend/src/utils/sanitize.ts`
- `frontend/src/api/**`

- [ ] Inventory all `v-html`, `innerHTML`, external links, route params, and file/download interactions.
- [ ] Add tests or build-time checks for sanitizer usage around markdown/article/digest rendering.
- [ ] Ensure every admin page has loading, empty, error, and disabled states for failing APIs.
- [ ] Verify: `cd frontend; npm run build`; browser smoke for article detail, digest detail, admin digest list.

### Task 9: Release Gate And Runtime Observability

**Files:**
- `scripts/release/release-gate.ps1`
- `scripts/release/digest-smoke.ps1`
- `scripts/release/start-local-smoke-services.ps1`
- `deploy/.env.example`

- [ ] Make release gate fail on known-danger defaults, missing API keys, failed audit, failed compose config, failed smoke.
- [ ] Add a resource snapshot step before and after smoke: top processes, docker stats, WSL status.
- [ ] Generate JSON/Markdown reports under `artifacts/release-gate/`.
- [ ] Verify: `scripts/release/release-gate.ps1 -Fast`; full gate with smoke before deployment.

### Task 10: Final End-To-End Regression And Cutover Checklist

**Files:**
- Create: `docs/audit/full-project-hardening-report.md`

- [ ] Run crawler full tests: `crawler-service\.venv\Scripts\python.exe -m pytest crawler-service\tests -q --tb=short`.
- [ ] Run backend tests: `cd backend; mvn test`.
- [ ] Run frontend build and audit: `cd frontend; npm run build`; `npm audit --omit=dev --registry=https://registry.npmjs.org`.
- [ ] Run compose config: `cd deploy; docker compose --env-file .env.example config`.
- [ ] Run real local/pre-prod digest smoke with real keys.
- [ ] Write final report listing fixed P0/P1 risks, remaining accepted risks, rollback command, and next release gate command.
