# Web Collector - Python Crawler Service

> 独立 FastAPI + Crawl4AI 爬虫服务。
> 当前版本：`2.2.0-beta`，MVP Beta 试用版。

## 当前定位

`crawler-service` 不再只是博客系统的附属模块，而是一个可复用的内部 HTTP 服务：

- 博客后端是其中一个 client。
- 允许最多少量内部服务接入，当前按 2 个服务以内的规模设计。
- 支持 API Key 认证、任务级 callback、独立健康检查和独立 Docker 部署。

## 最近验证

最后复核日期：2026-06-03

- `python -m pytest -q --tb=short`：1266 passed，1 warning。
- 与 Java 后端联动的 config/source/fingerprint/callback 链路已接入。
- 日报生成和自动优化关键链路已达到 MVP Beta 试用要求。

## 功能能力

### 爬取能力

- 单页爬取：输入 URL，输出 Markdown、标题、元数据。
- 深度爬取：BFS 遍历同域页面，支持深度和页数上限。
- 关键词搜索：Bing/Sogou/Baidu/Google 等搜索入口，自动降级。
- RSS/Atom：解析 feed，按 freshness 过滤后逐篇爬取。
- mixed section：日报中支持 keyword/url/rss 混合来源。

### 内容处理

- 质量评估：来源可信度、内容长度、页面类型、spam 信号。
- 去重：URL 规范化、SimHash、历史 fingerprint。
- 来源效能：记录成功率、质量均值、失败原因，跳过 dead source。
- SSRF 防护：限制内网地址和危险 URL。

### AI 与日报

- OpenAI-compatible AI 调用。
- 支持 `tech_summary`、`tutorial`、`comparison`、`knowledge_report`、`daily_digest` 等整理模式。
- 支持工作日定时日报和管理端手动触发。
- 支持 `digest_section`、`digest_item` 结构化保存。
- 支持质量评分、趋势记录、弱点建议和优化记录查询。

## 服务模式

| 模式 | 说明 |
| --- | --- |
| API-only | 提供即时 crawl/organize API，不依赖博客后端 |
| Standalone | 启用任务管理、日报生成、scheduler、callback |
| Blog-integrated | 从 Java `sys_config` 拉取配置、来源、fingerprint，并回调 Java |

## API 概览

### 健康检查

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/health` | 服务健康状态 |

### 即时 API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/crawl/single` | 单页爬取 |
| POST | `/crawl/deep` | 深度爬取 |
| POST | `/crawl/search` | 关键词搜索并爬取 |
| POST | `/organize` | AI 内容整理 |
| POST | `/keyword` | 关键词搜索 + AI 整理 |

### 任务 API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/v1/tasks` | 创建异步任务 |
| GET | `/api/v1/tasks` | 分页查询任务 |
| GET | `/api/v1/tasks/{id}` | 查询任务详情 |
| DELETE | `/api/v1/tasks/{id}` | 删除任务 |
| POST | `/api/v1/tasks/{id}/retry` | 重试任务 |
| POST | `/api/v1/tasks/{id}/organize` | 重新 AI 整理 |
| GET | `/api/v1/tasks/{id}/export` | 导出 Markdown |

### 日报与优化 API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/v1/digests/trigger` | 手动触发日报 |
| GET | `/api/v1/digests` | 日报列表 |
| GET | `/api/v1/digests/latest` | 最新日报 |
| GET | `/api/v1/digests/{date}` | 按日期查询日报 |
| GET | `/api/v1/digests/task/{id}` | 按任务 ID 查询日报 |
| GET | `/api/v1/digests/config/sections` | 当前 section 配置 |
| GET | `/api/v1/optimization/config` | 优化配置 |
| GET | `/api/v1/optimization/digest-trend` | 日报质量趋势 |
| GET | `/api/v1/tasks/{id}/optimization` | 任务优化记录 |

## 认证

当 `AUTH_ENABLED=true` 时，请求需携带：

```http
X-API-Key: <your-api-key>
```

`API_KEYS` 支持逗号分隔多个 key，方便两个内部服务分别使用不同 key。

## 创建任务示例

```bash
curl -X POST http://localhost:8500/api/v1/tasks \
  -H "Content-Type: application/json" \
  -H "X-API-Key: sk-your-client-key" \
  -d '{
    "task_type": "single",
    "url": "https://example.com/article",
    "ai_template": "tech_summary",
    "callback_url": "https://client.example.com/crawler/callback",
    "callback_headers": {
      "X-Client-Token": "client-callback-secret"
    }
  }'
```

任务完成或失败后会向 callback 发送：

```json
{
  "python_task_id": 123,
  "status": 3
}
```

`status` 使用 5 态任务机：

| 值 | 状态 |
| --- | --- |
| 0 | PENDING |
| 1 | CRAWLING |
| 2 | PROCESSING |
| 3 | COMPLETED |
| 4 | FAILED |

## 与博客后端集成

博客后端通过以下能力与 crawler-service 集成：

- `CRAWLER_SERVICE_URL`：Backend 调用 crawler API。
- `CRAWLER_API_KEY`：Backend 调用 crawler 时携带。
- `CRAWLER_CALLBACK_URL`：crawler 完成任务后回调 Backend。
- `CRAWLER_CALLBACK_API_KEY`：crawler 回调 Backend 时携带。
- Java `sys_config`：集中下发 `crawler.*`、AI、digest、optimization 配置。

内部端点由 Backend 提供，crawler 按需调用：

- `/api/internal/collector/config`
- `/api/internal/collector/sources`
- `/api/internal/collector/digest/fingerprints`
- `/api/internal/collector/source-authority`
- `/api/internal/collector/callback`

## 本地启动

```bash
cd crawler-service
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt
crawl4ai-setup
uvicorn main:app --host 0.0.0.0 --port 8500 --reload
```

## Docker 启动

```bash
cd crawler-service
docker build -t nanmuli-crawler:latest .
docker run -d -p 8500:8500 \
  -e AUTH_ENABLED=true \
  -e API_KEYS=sk-your-client-key \
  -e AI_ENABLED=true \
  -e AI_API_KEY=sk-xxx \
  -e DIGEST_ENABLED=true \
  -v crawler_data:/app/data \
  nanmuli-crawler:latest
```

## 配置重点

| 环境变量 | 说明 |
| --- | --- |
| `AUTH_ENABLED` | 是否启用 API key 认证 |
| `API_KEYS` | 允许访问的 API key，逗号分隔 |
| `AI_ENABLED` | 是否启用 AI |
| `AI_BASE_URL` | OpenAI-compatible endpoint |
| `AI_MODEL` | AI model，试用环境使用 `deepseek-v4-pro` |
| `AI_API_KEY` | AI key |
| `DIGEST_ENABLED` | 是否启用定时日报 |
| `DIGEST_CRON` | 默认 `0 8 * * 1-5` |
| `JAVA_API_URL` | Java 后端地址，非空时启用配置/来源拉取 |
| `CALLBACK_URL` | 全局 callback，任务级 callback 优先 |
| `CALLBACK_API_KEY` | 回调 Java 后端时使用 |
| `PROXY_URL` | HTTP/SOCKS proxy |

## 当前已知风险

- 外部站点结构变化会影响爬取质量。
- 搜索引擎可能触发反爬，需通过来源配置和 RSS 降低波动。
- 自动优化已经能记录弱点，但强策略反馈仍需要后续增强。
- 当前不是 SaaS 多租户服务，不建议暴露到公网给不受控用户调用。

## 版本历史

| 版本 | 日期 | 说明 |
| --- | --- | --- |
| 2.2.0-beta | 2026-06-03 | MVP Beta 上线复核，补充独立服务接入、配置联动、生产审计和部署说明 |
| 2.1.0-beta | 2026-06-01 | 日报 MVP Beta，接入真实 AI、质量趋势、自动优化和管理端链路 |
| 2.0.0 | 2026-05-08 | Standalone 任务管理、AI 整理、日报、质量评估、三层去重 |
| 1.0.0 | 2026-04-07 | single/deep/search 初始版本 |
