# Crawl4AI 快速参考卡片

> 常用代码片段速查手册

---

## 基础爬取

### 最简单的爬取
```python
from crawl4ai import AsyncWebCrawler

async with AsyncWebCrawler() as crawler:
    result = await crawler.arun("https://example.com")
    print(result.markdown.raw_markdown)
```

### 带配置的爬取
```python
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode

browser_config = BrowserConfig(headless=True)
run_config = CrawlerRunConfig(cache_mode=CacheMode.BYPASS)

async with AsyncWebCrawler(config=browser_config) as crawler:
    result = await crawler.arun("https://example.com", config=run_config)
```

---

## Markdown生成

### 基础Markdown生成
```python
from crawl4ai import CrawlerRunConfig
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

run_config = CrawlerRunConfig(
    markdown_generator=DefaultMarkdownGenerator()
)
```

### 带内容过滤的Markdown
```python
from crawl4ai import CrawlerRunConfig
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

run_config = CrawlerRunConfig(
    markdown_generator=DefaultMarkdownGenerator(
        content_filter=PruningContentFilter(threshold=0.48)
    )
)
```

---

## 批量爬取

### 基础批量爬取
```python
urls = ["https://example.com/page1", "https://example.com/page2"]

async with AsyncWebCrawler() as crawler:
    results = await crawler.arun_many(urls)
    for result in results:
        print(f"{result.url}: {len(result.markdown.raw_markdown)}")
```

### 带配置的批量爬取
```python
from crawl4ai import CrawlerRunConfig, CacheMode

urls = ["https://example.com/page1", "https://example.com/page2"]
run_config = CrawlerRunConfig(cache_mode=CacheMode.ENABLED)

async with AsyncWebCrawler() as crawler:
    results = await crawler.arun_many(urls, config=run_config)
```

### 流式批量爬取
```python
run_config = CrawlerRunConfig(stream=True)

async with AsyncWebCrawler() as crawler:
    async for result in await crawler.arun_many(urls, config=run_config):
        print(f"{result.url}: {result.success}")
```

---

## CSS选择器提取

### 基础CSS提取
```python
from crawl4ai import JsonCssExtractionStrategy, CrawlerRunConfig

schema = {
    "baseSelector": ".product",
    "fields": [
        {"name": "title", "selector": "h2", "type": "text"},
        {"name": "price", "selector": ".price", "type": "text"},
        {"name": "link", "selector": "a", "type": "attribute", "attribute": "href"},
    ],
}

run_config = CrawlerRunConfig(
    extraction_strategy=JsonCssExtractionStrategy(schema=schema)
)
```

### 提取属性值
```python
{"name": "image", "selector": "img", "type": "attribute", "attribute": "src"}
```

### 检查元素存在
```python
{"name": "in_stock", "selector": ".stock", "type": "exists"}
```

### 提取多个元素
```python
{"name": "tags", "selector": ".tag", "type": "text", "multiple": True}
```

---

## LLM提取

### 基础LLM提取
```python
from crawl4ai import LLMExtractionStrategy, LLMConfig, CrawlerRunConfig
from pydantic import BaseModel, Field

class Product(BaseModel):
    name: str = Field(..., description="产品名称")
    price: str = Field(..., description="产品价格")

run_config = CrawlerRunConfig(
    extraction_strategy=LLMExtractionStrategy(
        llm_config=LLMConfig(provider="openai/gpt-4o", api_token="YOUR_KEY"),
        schema=Product.model_json_schema(),
        instruction="提取产品信息",
    )
)
```

### DeepSeek LLM提取
```python
LLMConfig(provider="deepseek/deepseek-chat", api_token="YOUR_KEY")
```

### Ollama本地模型
```python
LLMConfig(provider="ollama/llama3", api_token="no-token")
```

---

## JavaScript执行

### 执行JavaScript
```python
js_code = """
(async () => {
    document.querySelector('.load-more').click();
    await new Promise(r => setTimeout(r, 1000));
    window.scrollTo(0, document.body.scrollHeight);
})();
"""

run_config = CrawlerRunConfig(
    js_code=js_code,
    wait_for="css:.loaded",
)
```

---

## 截图功能

### 基础截图
```python
run_config = CrawlerRunConfig(
    screenshot=True,
    screenshot_options={"full_page": True, "type": "png"}
)

# 保存截图
import base64
with open("screenshot.png", "wb") as f:
    f.write(base64.b64decode(result.screenshot))
```

---

## 会话复用

### 保持登录状态
```python
# 登录
await crawler.arun(
    url="https://example.com/login",
    config=CrawlerRunConfig(js_code=login_js),
    session_id="my_session"
)

# 复用会话
await crawler.arun(
    url="https://example.com/dashboard",
    session_id="my_session"
)
```

---

## 代理设置

### 基础代理
```python
browser_config = BrowserConfig(
    proxy_config={
        "server": "http://proxy.example.com:8080",
        "username": "user",
        "password": "pass"
    }
)
```

### 代理URL
```python
browser_config = BrowserConfig(
    proxy_config="http://user:pass@proxy.example.com:8080"
)
```

---

## 深度爬取

### BFS深度爬取
```python
from crawl4ai.deep_crawling import BFSDeepCrawlStrategy

run_config = CrawlerRunConfig(
    deep_crawl_strategy=BFSDeepCrawlStrategy(
        max_depth=2,
        include_external=False
    )
)

results = await crawler.arun("https://example.com", config=run_config)
```

### 带过滤器的深度爬取
```python
from crawl4ai.deep_crawling.filters import FilterChain, URLPatternFilter

run_config = CrawlerRunConfig(
    deep_crawl_strategy=BFSDeepCrawlStrategy(
        max_depth=2,
        filter_chain=FilterChain([URLPatternFilter(patterns=["*api*"])])
    )
)
```

---

## 调度器

### 内存自适应调度器
```python
from crawl4ai import MemoryAdaptiveDispatcher, RateLimiter, CrawlerMonitor, DisplayMode

dispatcher = MemoryAdaptiveDispatcher(
    memory_threshold_percent=70.0,
    max_session_permit=10,
    rate_limiter=RateLimiter(base_delay=(1.0, 2.0)),
    monitor=CrawlerMonitor(display_mode=DisplayMode.DETAILED),
)

results = await crawler.arun_many(urls, config=run_config, dispatcher=dispatcher)
```

---

## 反检测配置

### Stealth模式
```python
browser_config = BrowserConfig(
    headless=True,
    enable_stealth=True,
)
```

### Undetected浏览器
```python
browser_config = BrowserConfig(
    browser_type="undetected",
    headless=True,
)
```

---

## 常用配置参数

### BrowserConfig常用参数
```python
BrowserConfig(
    headless=True,              # 无头模式
    browser_type="chromium",    # 浏览器类型
    viewport_width=1920,        # 视口宽度
    viewport_height=1080,       # 视口高度
    enable_stealth=True,        # 反检测
    java_script_enabled=True,   # 启用JS
    text_mode=True,             # 文本模式
)
```

### CrawlerRunConfig常用参数
```python
CrawlerRunConfig(
    cache_mode=CacheMode.ENABLED,   # 缓存模式
    word_count_threshold=10,        # 字数阈值
    wait_until="networkidle",       # 等待条件
    page_timeout=30000,             # 超时时间
    mean_delay=1.5,                 # 平均延迟
    screenshot=True,                # 截图
)
```

---

## 缓存模式

| 模式 | 说明 |
|------|------|
| `CacheMode.ENABLED` | 启用缓存（默认） |
| `CacheMode.BYPASS` | 绕过缓存 |
| `CacheMode.READ_ONLY` | 只读模式 |
| `CacheMode.WRITE_ONLY` | 只写模式 |

---

## 等待条件

| 条件 | 说明 |
|------|------|
| `"load"` | 等待load事件 |
| `"domcontentloaded"` | 等待DOMContentLoaded事件 |
| `"networkidle"` | 等待网络空闲 |

---

## 提取字段类型

| 类型 | 说明 |
|------|------|
| `"text"` | 提取文本内容 |
| `"attribute"` | 提取属性值 |
| `"exists"` | 检查元素是否存在 |
| `"html"` | 提取HTML内容 |

---

## 常用导入

```python
# 核心类
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode

# 提取策略
from crawl4ai import JsonCssExtractionStrategy, JsonXPathExtractionStrategy
from crawl4ai import LLMExtractionStrategy, LLMConfig

# 内容过滤
from crawl4ai.content_filter_strategy import PruningContentFilter, BM25ContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

# 深度爬取
from crawl4ai.deep_crawling import BFSDeepCrawlStrategy, DFSDeepCrawlStrategy, BestFirstCrawlingStrategy
from crawl4ai.deep_crawling.filters import FilterChain, URLPatternFilter, DomainFilter
from crawl4ai.deep_crawling.scorers import KeywordRelevanceScorer

# 调度器
from crawl4ai import MemoryAdaptiveDispatcher, SemaphoreDispatcher, RateLimiter, CrawlerMonitor, DisplayMode
```

---

## 结果对象属性

```python
result.url                      # 爬取的URL
result.html                     # 原始HTML
result.markdown.raw_markdown    # 原始Markdown
result.markdown.fit_markdown    # 过滤后的Markdown
result.metadata                 # 元数据（标题、描述等）
result.links                    # 链接（internal/external）
result.screenshot               # 截图（Base64）
result.extracted_content        # 提取的内容（JSON字符串）
result.success                  # 是否成功
result.error_message            # 错误信息
```
