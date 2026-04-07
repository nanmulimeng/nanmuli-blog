# Web Collector - Python Crawler Service

基于 **Crawl4AI** 的异步网页内容采集服务，为 Nanmuli Blog 的 Web Collector 模块提供后端支持。

## 功能特性

- **单页爬取** (`/crawl/single`) - 爬取单个 URL 并返回 Markdown
- **深度爬取** (`/crawl/deep`) - BFS 遍历同域名多页面
- **关键词搜索** (`/crawl/search`) - 搜索引擎关键词查找并爬取结果
- **元数据提取** - 自动提取标题、描述、发布时间、作者等
- **针对 2G 服务器优化** - text_mode + light_mode 减少内存占用

## 技术栈

| 组件 | 版本 | 说明 |
|------|------|------|
| Python | 3.10+ | 运行时 |
| Crawl4AI | >=0.8.0 | 异步网页爬取框架 |
| FastAPI | >=0.109.0 | Web 框架 |
| Uvicorn | >=0.27.0 | ASGI 服务器 |
| BeautifulSoup4 | >=4.12.0 | HTML 解析 |

## 安装部署

### 方式一：Docker 部署（推荐）

#### 1. 使用 Docker Compose（与主项目一起部署）

```bash
# 在项目根目录执行
docker-compose up -d crawler

# 查看日志
docker-compose logs -f crawler
```

#### 2. 单独构建爬虫服务镜像

```bash
cd crawler-service

# 构建镜像
docker build -t nanmuli-crawler:latest .

# 运行容器
docker run -d \
  --name nanmuli-crawler \
  -p 8500:8500 \
  -e PORT=8500 \
  -e MAX_PAGES_DEFAULT=10 \
  -e LOG_LEVEL=INFO \
  --restart unless-stopped \
  nanmuli-crawler:latest
```

### 方式二：本地部署

#### 1. 创建虚拟环境

```bash
cd crawler-service
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate
```

#### 2. 安装依赖

```bash
pip install -r requirements.txt
```

#### 3. 安装 Playwright 浏览器（Crawl4AI 依赖）

```bash
crawl4ai-setup
# 或手动安装
playwright install chromium
```

验证安装：
```bash
crawl4ai-doctor
```

#### 4. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件根据需要调整配置
```

#### 5. 启动服务

开发模式（热重载）：
```bash
uvicorn main:app --host 0.0.0.0 --port 8500 --reload
```

生产模式：
```bash
uvicorn main:app --host 0.0.0.0 --port 8500 --workers 1
```

> **注意**：由于 Playwright 浏览器实例限制，建议使用单进程模式（`--workers 1`）

## API 文档

启动后访问自动生成的 API 文档：
- Swagger UI: http://localhost:8500/docs
- ReDoc: http://localhost:8500/redoc

### 端点列表

| 方法 | 端点 | 描述 |
|------|------|------|
| GET | `/health` | 健康检查 |
| POST | `/crawl/single` | 单页爬取 |
| POST | `/crawl/deep` | BFS 深度爬取 |
| POST | `/crawl/search` | 关键词搜索爬取 |

### 请求示例

#### 单页爬取

```bash
curl -X POST "http://localhost:8500/crawl/single" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://docs.crawl4ai.com",
    "config": {
      "text_mode": true,
      "light_mode": true,
      "page_timeout": 30000
    }
  }'
```

#### 深度爬取

```bash
curl -X POST "http://localhost:8500/crawl/deep" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://docs.crawl4ai.com",
    "max_depth": 2,
    "max_pages": 10,
    "config": {
      "text_mode": true,
      "light_mode": true
    }
  }'
```

#### 关键词搜索

```bash
curl -X POST "http://localhost:8500/crawl/search" \
  -H "Content-Type: application/json" \
  -d '{
    "keyword": "Spring AI RAG 实战",
    "engine": "bing",
    "max_results": 10
  }'
```

### 响应格式

#### 单页爬取响应

```json
{
  "success": true,
  "url": "https://docs.crawl4ai.com",
  "title": "Crawl4AI Documentation",
  "markdown": "# Crawl4AI Documentation\n\n...",
  "metadata": {
    "url": "https://docs.crawl4ai.com",
    "title": "Crawl4AI Documentation",
    "description": "...",
    "published_at": "2024-01-15T08:00:00",
    "language": "en"
  },
  "word_count": 15234,
  "crawl_time_ms": 5400
}
```

#### 多页爬取响应

```json
{
  "success": true,
  "pages": [
    {
      "success": true,
      "url": "https://docs.crawl4ai.com",
      "title": "Crawl4AI Documentation",
      "markdown": "...",
      "word_count": 15234,
      "crawl_time_ms": 5400
    }
  ],
  "total_pages": 5,
  "total_crawl_time_ms": 25000,
  "keyword": "Spring AI"
}
```

## 性能优化（2G 服务器）

服务默认配置针对低内存服务器优化：

- `text_mode=True` - 不加载图片，节省内存和带宽
- `light_mode=True` - 轻量模式，减少浏览器资源占用
- `max_pages <= 20` - 限制单次爬取页面数
- `workers=1` - 单进程避免浏览器实例冲突

如需更高性能，可调整 `.env` 中的配置或传入自定义 `config` 参数。

## 故障排查

### Crawl4AI 安装失败

```bash
# 确保系统依赖已安装（Ubuntu/Debian）
sudo apt-get install -y libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libasound2

# 重新安装
pip install --force-reinstall crawl4ai
playwright install chromium
```

### 内存不足

如出现内存错误，请确保：
1. `text_mode=True` 和 `light_mode=True`
2. 减少 `max_pages` 和 `max_depth`
3. 确保没有其他 Playwright 实例在运行

### 搜索引擎返回空结果

搜索引擎可能有反爬机制，建议：
1. 减少请求频率（每次搜索间增加延迟）
2. 尝试切换搜索引擎（`engine: "duckduckgo"`）
3. 检查关键词是否有效

## 与 Java 后端集成

Java 后端通过 REST API 调用此服务，配置示例：

```yaml
# application-dev.yml
crawler:
  service:
    base-url: http://localhost:8500
    timeout: 60000  # 60秒超时
```

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0.0 | 2026-04-07 | 初始版本，支持 single/deep/search 三种模式 |
