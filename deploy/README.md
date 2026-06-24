# Nanmuli Blog 部署说明

> 当前版本：MVP Beta 试用版
> 最后复核：2026-06-18

## 部署结论

当前 Docker Compose 部署链路已具备 MVP 试用条件：

- `docker compose --env-file .env.example config` 通过。
- `docker compose --env-file .env.example build frontend` 通过。
- `scripts/release/release-gate.ps1` 可一键执行上线前审计、构建、测试、compose、env 和可选 smoke 验收。
- `scripts/release/check-deploy-env.ps1` 可校验真实 `deploy/.env` 的上线必填项。
- `scripts/release/digest-smoke.ps1` 可执行上线前真实日报 smoke。
- 真实 `.env` 已从仓库中移除，仓库仅保留 `.env.example`。
- 前端 Docker 构建使用 `frontend/package-lock.json` 和 `npm ci`，构建可复现。

## 目录结构

```text
deploy/
├── .env.example                  # 环境变量模板
├── docker-compose.yml            # Compose 编排
├── nginx.conf                    # 前端容器内 Nginx 配置
├── nginx/
│   └── conf.d/default.conf       # 可选 Nginx 站点配置
├── db/
│   ├── Dockerfile                # PostgreSQL 扩展镜像
│   ├── init-scripts/schema.sql   # 初始化 schema
│   └── README.md
└── README.md
```

## 服务拓扑

```mermaid
flowchart LR
  Browser["Browser"] --> Frontend["frontend / nginx :80"]
  Frontend --> Backend["backend :8081"]
  Backend --> Postgres["postgres :5432"]
  Backend --> Redis["redis :6379"]
  Backend --> Crawler["crawler :8500"]
  Crawler --> Backend
  Crawler --> AI["AI provider"]
```

## 快速启动

```bash
cd deploy
cp .env.example .env
# 编辑 .env，替换所有 your_*、AI_*、CORS、cookie 等配置
docker compose --env-file .env up -d --build
```

服务端口：

| 服务 | 容器名 | 宿主机端口 | 说明 |
| --- | --- | --- | --- |
| Frontend | `nanmuli-frontend` | `80` | Vue 静态资源 + API 反向代理 |
| Backend | `nanmuli-backend` | `8081` | Spring Boot API |
| Crawler | `crawler-service` | `8500` | FastAPI/Crawl4AI |
| PostgreSQL | `nanmuli-postgres` | `5433` | 映射到容器 `5432` |
| Redis | `nanmuli-redis` | `6380` | 映射到容器 `6379` |

## 必填环境变量

| 变量 | 必填 | 说明 |
| --- | --- | --- |
| `DB_PASSWORD` | 是 | PostgreSQL 密码 |
| `BLOG_SECURITY_ENCRYPTION_KEY` | 是 | 后端敏感配置加密 key，至少 16 字符 |
| `CRAWLER_API_KEY` | 是 | Backend 调用 crawler 的 key |
| `CRAWLER_CALLBACK_API_KEY` | 是 | Crawler 回调 Backend 的 key |
| `CRAWLER_SERVICE_URL` | 是 | Compose 中建议为 `http://crawler:8500` |
| `CRAWLER_CALLBACK_URL` | 是 | Compose 中建议为 `http://backend:8081/api/internal/collector/callback` |
| `CORS_ALLOWED_ORIGINS` | 是 | 前端访问域名 |
| `COOKIE_SECURE` | 是 | HTTPS 环境建议 `true` |
| `AI_ENABLED` | 视需求 | 是否启用 AI |
| `AI_API_KEY` | AI 启用时必填 | AI provider key |
| `AI_BASE_URL` | AI 启用时必填 | OpenAI-compatible endpoint |
| `AI_MODEL` | AI 启用时必填 | 试用环境使用 `deepseek-chat` |
| `DIGEST_ENABLED` | 视需求 | 是否启用定时日报 |

## 常用命令

```bash
# 查看配置展开结果
docker compose --env-file .env config

# 启动
docker compose --env-file .env up -d --build

# 查看状态
docker compose --env-file .env ps

# 查看日志
docker compose --env-file .env logs -f backend
docker compose --env-file .env logs -f crawler
docker compose --env-file .env logs -f frontend

# 重启单个服务
docker compose --env-file .env restart backend

# 停止服务
docker compose --env-file .env down

# 删除数据卷，谨慎使用
docker compose --env-file .env down -v
```

## 健康检查

```bash
curl http://localhost:8081/actuator/health
curl http://localhost:8500/health
curl http://localhost/api/digest/latest
```

预期：

- Backend health 返回 `UP`。
- Crawler health 返回 `healthy`。
- 公开日报接口在有日报数据时返回 `200 success`。

## 上线前日报 smoke

在仓库根目录执行：

```powershell
# 日常快速闸门：审计、前端构建、compose config、报告生成
.\scripts\release\release-gate.ps1 -Fast

# 上线完整闸门：全量测试 + 真实环境校验 + 真实日报 smoke
.\scripts\release\release-gate.ps1 -RunSmoke -TriggerDigest -ForceDigest -CrawlerApiKey <key> -TimeoutMinutes 30

# 专项诊断入口
.\scripts\release\check-deploy-env.ps1 -EnvPath deploy/.env
.\scripts\release\digest-smoke.ps1 -SelfTest
.\scripts\release\digest-smoke.ps1 -CrawlerUrl http://localhost:8500 -BackendUrl http://localhost:8081 -CrawlerApiKey <key> -Trigger -Force -TimeoutMinutes 30
```

验收标准：

- 真实 `deploy/.env` 已设置 `AI_ENABLED=true`、`DIGEST_ENABLED=true`、`AI_API_KEY`、`CRAWLER_API_KEY`、`CRAWLER_CALLBACK_API_KEY`、`BLOG_SECURITY_ENCRYPTION_KEY`。
- `BLOG_SECURITY_ENCRYPTION_KEY` 不使用默认值或占位符。
- 触发任务完成后有 `ai_title`、`ai_full_content`、结构化 `sections/items`。
- 核心板块 `hot_trend/open_source/dev_tool/tech_article/paper` 至少覆盖 3 个。
- `quality_evaluation.publishable` 不是 `false`。
- 公开 `/api/digest/latest` 能返回同一条可发布日报。
- `release-gate` 会同时生成 JSON 和 Markdown 报告，默认位于 `artifacts/release-gate/`。
- `release-gate` 会在重型步骤前检查 Windows/WSL/Docker 资源压力；如果可用内存过低、换页过高或 WSL/Docker 虚拟机仍占用过多内存，应先执行 `wsl --shutdown` 并重启 Docker Desktop。
- `digest-smoke -SelfTest` 会离线校验日报 smoke 的自动优化 safety 断言；完整 `release-gate` 已默认包含该自检。

## 上线检查清单

- [ ] 已创建真实 `deploy/.env`，且未提交到 Git。
- [ ] 数据库密码、crawler key、callback key 已替换。
- [ ] `BLOG_SECURITY_ENCRYPTION_KEY` 已替换为强随机值。
- [ ] 生产域名已写入 `CORS_ALLOWED_ORIGINS`。
- [ ] HTTPS 环境已设置 `COOKIE_SECURE=true`。
- [ ] AI key、base URL、model 已配置并可用。
- [ ] `DIGEST_ENABLED=true` 仅在确认信息源配置完成后开启。
- [ ] `.\scripts\release\release-gate.ps1 -Fast` 日常快速闸门通过。
- [ ] `.\scripts\release\release-gate.ps1 -RunSmoke -TriggerDigest -ForceDigest -CrawlerApiKey <key>` 通过。
- [ ] `.\scripts\release\check-deploy-env.ps1 -EnvPath deploy/.env` 通过。
- [ ] `.\scripts\release\digest-smoke.ps1 -SelfTest` 通过。
- [ ] `docker compose --env-file .env config` 通过。
- [ ] `docker compose --env-file .env up -d --build` 启动成功。
- [ ] Backend、Crawler、Frontend 三方健康检查通过。
- [ ] `.\scripts\release\digest-smoke.ps1 -Trigger -Force` 通过。
- [ ] 管理端可登录，日报可手动触发并能看到失败诊断。
- [ ] 公开页面可访问最新日报。

## 已知风险

- Crawler 依赖外部站点和搜索引擎，日报质量会随信息源变化波动。
- AI provider 不可用时，日报生成质量会下降或任务失败。
- 试用期建议保留人工审查，不建议直接承诺完全自动发布。
- 前端 dev/build 工具链 audit 仍有中危项，需要后续单独升级 Vite/vue-tsc。
