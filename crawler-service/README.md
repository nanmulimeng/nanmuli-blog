# Web Collector - Python Crawler Service

基于 **Crawl4AI** 的异步网页内容采集服务，支持双模式部署。

## 功能特性

### 爬取引擎
- **单页爬取** — 爬取单个 URL，提取 Markdown + 元数据
- **深度爬取** — BFS 遍历同域名多页面，支持深度和数量限制
- **关键词搜索** — 4 搜索引擎（Bing/Sogou/Baidu/Google）自动轮换 + 降级 + 反爬检测

### 内容处理
- **质量评估** — 来源可信度（5 级）+ 内容质量（5 维度）+ 标题党检测
- **三级去重** — URL 精确 + SimHash 内容指纹 + 标题相似度
- **元数据提取** — OpenGraph / Twitter Card / JSON-LD / 发布时间
- **域名过滤** — 60+ 黑名单域名 + 负向关键词

### AI 内容整理（需配置 AI API）
- **5 种模板** — tech_summary / tutorial / comparison / knowledge_report / daily_digest
- **关键词优化/扩展** — AI 优化搜索关键词并生成变体
- **日报生成** — 定时调度（默认工作日 8:00）+ 多板块 + 跨日去重

### 独立模式（STANDALONE=true）
- SQLite 任务管理（创建/查询/重试/删除/导出）
- API Key 认证 + SSRF 防护
- APScheduler 定时日报调度
- 5 态任务状态机（PENDING → CRAWLING → PROCESSING → COMPLETED / FAILED）

## 技术栈

| 组件 | 版本 | 说明 |
|------|------|------|
| Python | 3.10+ | 运行时 |
| Crawl4AI | ~=0.8.6 | 无头 Chromium 异步爬虫 |
| FastAPI | >=0.109.0 | Web 框架 |
| httpx | >=0.26.0 | 异步 HTTP 客户端 |
| Pydantic Settings | >=2.1.0 | 配置管理 |
| APScheduler | >=3.10.0 | 定时调度（独立模式） |

## 双模式部署

### 纯 API 模式（默认）

作为微服务被 Java 后端调用，仅暴露爬取端点：

| 方法 | 端点 | 描述 |
|------|------|------|
| GET | `/health` | 健康检查（含组件状态） |
| POST | `/crawl/single` | 单页爬取 |
| POST | `/crawl/deep` | BFS 深度爬取 |
| POST | `/crawl/search` | 关键词搜索爬取 |
| POST | `/organize` | AI 内容整理 |
| POST | `/keyword` | 关键词搜索 + AI 整理（一站式） |

### 独立模式（STANDALONE=true）

完整任务管理系统，额外暴露 `/api/v1/*` 端点：

| 方法 | 端点 | 描述 |
|------|------|------|
| POST | `/api/v1/tasks` | 创建任务（异步爬取 + AI 整理） |
| GET | `/api/v1/tasks` | 任务列表（分页） |
| GET | `/api/v1/tasks/{id}` | 任务详情 |
| DELETE | `/api/v1/tasks/{id}` | 删除任务 |
| POST | `/api/v1/tasks/{id}/retry` | 重试失败任务 |
| POST | `/api/v1/tasks/{id}/organize` | 重新 AI 整理 |
| GET | `/api/v1/tasks/{id}/export` | 导出为 Markdown |
| GET | `/api/v1/digests` | 日报列表 |
| GET | `/api/v1/digests/latest` | 最新日报 |
| POST | `/api/v1/digests/trigger` | 手动触发日报 |
| GET | `/api/v1/stats` | 统计信息 |

## 安装部署

### Docker（推荐）

```bash
cd crawler-service
docker build -t nanmuli-crawler:latest .

# 纯 API 模式
docker run -d -p 8500:8500 nanmuli-crawler:latest

# 独立模式
docker run -d -p 8500:8500 \
  -e STANDALONE=true \
  -e AI_ENABLED=true \
  -e AI_API_KEY=sk-xxx \
  -e DIGEST_ENABLED=true \
  nanmuli-crawler:latest
```

### 本地部署

```bash
cd crawler-service
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
crawl4ai-setup
cp .env.example .env  # 编辑配置
uvicorn main:app --host 0.0.0.0 --port 8500 --reload
```

## 配置说明

所有配置通过 `.env` 文件或环境变量，完整列表见 `.env.example`。

关键配置：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `STANDALONE` | false | 启用独立模式 |
| `AI_ENABLED` | false | 启用 AI 内容整理 |
| `AI_BASE_URL` | DashScope | OpenAI 兼容 API 地址 |
| `DIGEST_ENABLED` | false | 启用定时日报 |
| `DIGEST_CRON` | `0 8 * * 1-5` | 工作日早 8 点 |
| `PROXY_URL` | 空 | HTTP/SOCKS5 代理 |

## 与 Java 后端集成

```yaml
# application-prod.yml
crawler:
  service:
    base-url: ${CRAWLER_SERVICE_URL:http://localhost:8500}
    api-key: ${CRAWLER_API_KEY:}
    connect-timeout: ${CRAWLER_CONNECT_TIMEOUT:10000}
    read-timeout: ${CRAWLER_READ_TIMEOUT:30000}
```

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 2.0.0 | 2026-05-08 | 独立模式 + AI 整理 + 日报 + 质量评估 + 三级去重 + 连接池化 |
| 1.0.0 | 2026-04-07 | 初始版本，single/deep/search 三种模式 |
