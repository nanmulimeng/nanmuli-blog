# mvp-beta.2 发布检查清单

> 目标：将当前 MVP Beta 从“功能可用”推进到“可稳定试用、可定位问题、日报质量可持续提升”。
> 适用日期：2026-06-11

## 发布范围

- 博客前台与管理端基础功能。
- Web Collector 任务、信息源、配置同步和 callback。
- 技术日报手动触发、定时调度、详情展示、质量评估和自动优化闭环。
- `crawler-service` 作为最多两个内部服务复用的轻量 HTTP 服务。

## 必填环境变量

### Backend

| 变量 | 要求 |
| --- | --- |
| `DB_HOST` / `DB_PORT` / `DB_NAME` / `DB_USER` / `DB_PASSWORD` | 指向试用环境 PostgreSQL |
| `REDIS_HOST` / `REDIS_PORT` | 指向试用环境 Redis |
| `CRAWLER_SERVICE_URL` | 指向 crawler-service，例如 `http://crawler:8500` 或服务器内网地址 |
| `CRAWLER_API_KEY` | 强随机值，Backend 调用 crawler 使用 |
| `CRAWLER_CALLBACK_API_KEY` | 强随机值，crawler 回调 Backend 使用 |
| `CRAWLER_CALLBACK_URL` | crawler 可访问的 Backend callback 地址 |
| `BLOG_SECURITY_ENCRYPTION_KEY` | 强随机值，不提交仓库 |
| `CORS_ALLOWED_ORIGINS` | 包含生产域名，例如 `https://nanmu.xyz` |

### Crawler Service

| 变量 | 要求 |
| --- | --- |
| `AUTH_ENABLED` | 试用环境建议 `true` |
| `API_KEYS` | 支持逗号分隔多个 key；最多两个内部服务接入时建议每个服务独立 key |
| `JAVA_API_URL` | 博客 Backend 地址；作为独立 API-only 服务时可为空 |
| `CALLBACK_URL` | 全局 callback；任务级 `callback_url` 优先 |
| `CALLBACK_API_KEY` | 回调博客 Backend 时使用 |
| `AI_ENABLED` / `AI_API_KEY` / `AI_BASE_URL` / `AI_MODEL` | AI 能力配置 |
| `DIGEST_ENABLED` / `DIGEST_CRON` | 定时日报配置 |
| `PROXY_URL` | 仅在需要外部代理时配置 |

## 健康检查

```bash
curl http://localhost:8081/actuator/health
curl http://localhost:8500/health
curl -H "X-API-Key: <key>" http://localhost:8500/api/v1/ready
```

通过标准：

- Backend health 为 `UP`。
- Crawler health 为 `healthy`。
- Ready check 至少能区分 `db`、`scheduler`、`ai` 状态。
- 管理端日报列表能显示 scheduler、AI、最近一次 digest 执行状态。

## 测试命令

```bash
# Backend
cd backend
mvn test

# Crawler
cd ../crawler-service
python -m pytest tests -q --tb=short

# Frontend
cd ../frontend
npm run build

# Compose config
cd ../deploy
docker compose --env-file .env config
```

## 管理端手测

- 登录管理端。
- 保存系统配置，确认 crawler config refresh 不报错。
- 新增一个信息源并执行测试，确认任务详情有 diagnostics。
- 触发一次手动技术日报，确认任务状态、日报详情、质量评估、source diagnostics、next run actions 可见。
- 再触发第二轮或构造低质量 fixture，确认 skip/deprioritize/boost actions 会进入下一轮采集策略。
- 查看日报列表，确认 scheduler 运行、AI 配置、最近执行失败原因可以在页面上定位。

## 回滚方式

- 保留上一版 Backend、Frontend、crawler-service 构建产物或镜像。
- 回滚前先停止定时日报，避免回滚期间重复生成：

```bash
# Docker 部署时示例
docker compose stop crawler
docker compose stop backend frontend
```

- 回滚应用代码后重新启动三服务，再执行健康检查。
- 本版本新增字段主要为兼容性返回字段，未要求大 schema migration；如数据库 migration 已执行，禁止手工删除生产数据。

## 已知风险

- 外部搜索和网页结构变化仍可能影响采集质量，必须保留 RSS、官方博客、repo URL 等稳定来源。
- AI provider 配置错误会导致日报质量或生成失败，管理端 scheduler/diagnostics 应能定位到 `ai` 类问题。
- Callback 地址配置错误会导致 Backend 无法同步 crawler 结果，需检查 `CALLBACK_URL`、`CALLBACK_API_KEY`、网络连通性。
- 当前 crawler-service 不是公网 SaaS，多 key 仅用于少量内部服务隔离，不提供复杂多租户、配额和计费能力。
- 真实 AI E2E 受外部网络、额度和模型稳定性影响，不能替代 fixture 单元测试。
