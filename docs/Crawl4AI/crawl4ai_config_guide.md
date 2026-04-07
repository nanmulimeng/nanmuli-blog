# Crawl4AI 配置指南

> 基于 Crawl4AI v0.7.x+ 版本的详细配置说明

## 目录

1. [BrowserConfig 配置](#1-browserconfig-配置)
2. [CrawlerRunConfig 配置](#2-crawlerrunconfig-配置)
3. [缓存模式](#3-缓存模式)
4. [提取策略](#4-提取策略)
5. [深度爬取策略](#5-深度爬取策略)
6. [调度器配置](#6-调度器配置)

---

## 1. BrowserConfig 配置

`BrowserConfig` 用于配置浏览器级别的设置，在创建 `AsyncWebCrawler` 实例时传入。

### 1.1 基本配置参数

```python
from crawl4ai import BrowserConfig

browser_config = BrowserConfig(
    # 基本设置
    headless=True,                    # 无头模式（默认True）
    browser_type="chromium",          # 浏览器类型
    verbose=True,                     # 详细日志输出
    
    # 视口设置
    viewport_width=1920,              # 视口宽度
    viewport_height=1080,             # 视口高度
    
    # JavaScript设置
    java_script_enabled=True,         # 启用JavaScript（默认True）
)
```

### 1.2 浏览器类型

| 类型 | 说明 | 适用场景 |
|------|------|----------|
| `chromium` | Chrome/Chromium（默认） | 大多数场景 |
| `firefox` | Firefox浏览器 | 需要Firefox特定功能 |
| `webkit` | Safari浏览器 | 测试Safari兼容性 |
| `undetected` | 反检测Chrome | 反爬严格的网站 |

### 1.3 反检测配置

```python
browser_config = BrowserConfig(
    headless=True,
    enable_stealth=True,              # 启用stealth模式
    # 或使用undetected浏览器
    browser_type="undetected",
    extra_args=[
        "--disable-blink-features=AutomationControlled",
        "--disable-web-security",
        "--no-sandbox",
        "--disable-setuid-sandbox",
    ],
)
```

### 1.4 代理配置

```python
# 方式1：使用proxy_config字典
browser_config = BrowserConfig(
    proxy_config={
        "server": "http://proxy.example.com:8080",
        "username": "proxy_user",
        "password": "proxy_pass"
    }
)

# 方式2：使用代理URL字符串
browser_config = BrowserConfig(
    proxy_config="http://user:pass@proxy.example.com:8080"
)
```

### 1.5 持久化会话配置

```python
from pathlib import Path
import os

# 创建用户数据目录
user_data_dir = os.path.join(Path.home(), ".crawl4ai", "browser_profile")
os.makedirs(user_data_dir, exist_ok=True)

browser_config = BrowserConfig(
    user_data_dir=user_data_dir,      # 用户数据目录
    use_persistent_context=True,      # 使用持久化上下文
)
```

### 1.6 CDP连接（连接已有Chrome）

```python
# 1. 首先启动Chrome并开启远程调试
# chrome --remote-debugging-port=9222

# 2. 配置Crawl4AI连接
browser_config = BrowserConfig(
    cdp_url="http://localhost:9222",
    use_managed_browser=True,
    headless=False,  # 通常本地Chrome是headful
)
```

### 1.7 性能优化配置

```python
browser_config = BrowserConfig(
    text_mode=True,                   # 文本模式（不加载图片）
    light_mode=True,                  # 轻量模式（禁用非必要任务）
)
```

---

## 2. CrawlerRunConfig 配置

`CrawlerRunConfig` 用于配置爬虫运行时的行为，在调用 `arun()` 或 `arun_many()` 时传入。

### 2.1 内容处理参数

```python
from crawl4ai import CrawlerRunConfig

run_config = CrawlerRunConfig(
    # 内容过滤
    word_count_threshold=10,          # 字数阈值（低于此值的文本块被忽略）
    excluded_tags=["nav", "footer", "aside", "header"],  # 排除的HTML标签
    excluded_selector=".ad, .sidebar",  # 排除的CSS选择器
    
    # 链接和图片处理
    exclude_external_links=True,      # 排除外部链接
    exclude_all_images=False,         # 是否排除所有图片
    exclude_social_media_links=True,  # 排除社交媒体链接
    
    # 元素移除
    remove_overlay_elements=True,     # 移除弹窗等覆盖元素
    remove_forms=True,                # 移除表单元素
    process_iframes=True,             # 处理iframe内容
)
```

### 2.2 页面导航参数

```python
run_config = CrawlerRunConfig(
    # 等待条件
    wait_until="networkidle",         # 等待条件
    # 可选值: "load" | "domcontentloaded" | "networkidle"
    
    # 超时设置
    page_timeout=30000,               # 页面加载超时（毫秒）
    
    # 额外延迟
    delay_before_return_html=2.0,     # 返回HTML前的额外延迟（秒）
    
    # 等待元素
    wait_for="css:.content-loaded",   # 等待特定CSS选择器出现
    # wait_for="js:() => document.readyState === 'complete'",
)
```

### 2.3 截图参数

```python
run_config = CrawlerRunConfig(
    screenshot=True,                  # 启用截图
    screenshot_options={
        "full_page": True,            # 全页截图
        "type": "png",                # 图片格式: png | jpeg
        "quality": 90,                # 图片质量（0-100，仅JPEG）
        "omit_background": False,     # 是否透明背景
    },
)
```

### 2.4 内容选择参数

```python
run_config = CrawlerRunConfig(
    # CSS选择器过滤
    css_selector="article .content",  # 只提取匹配选择器的内容
    target_elements=["article", "main"],  # 目标元素选择器列表
)
```

### 2.5 礼貌爬取参数

```python
run_config = CrawlerRunConfig(
    check_robots_txt=True,            # 检查robots.txt
    mean_delay=1.5,                   # 平均延迟（秒）
    max_range=1.0,                    # 最大随机延迟浮动
    semaphore_count=3,                # 并发数
)
```

### 2.6 JavaScript执行

```python
js_code = """
(async () => {
    // 点击按钮
    document.querySelector('.load-more').click();
    await new Promise(r => setTimeout(r, 1000));
    
    // 滚动页面
    window.scrollTo(0, document.body.scrollHeight);
    await new Promise(r => setTimeout(r, 2000));
})();
"""

run_config = CrawlerRunConfig(
    js_code=js_code,                  # 执行JavaScript
    wait_for="css:.loaded-content",   # 等待加载完成的元素
)
```

---

## 3. 缓存模式

```python
from crawl4ai import CacheMode, CrawlerRunConfig

# ENABLED: 启用缓存（默认）
# - 如果缓存存在则读取
# - 如果缓存不存在则写入
config1 = CrawlerRunConfig(cache_mode=CacheMode.ENABLED)

# BYPASS: 绕过缓存
# - 总是重新爬取
# - 不读取也不写入缓存
config2 = CrawlerRunConfig(cache_mode=CacheMode.BYPASS)

# READ_ONLY: 只读模式
# - 只读取缓存
# - 不写入新缓存
config3 = CrawlerRunConfig(cache_mode=CacheMode.READ_ONLY)

# WRITE_ONLY: 只写模式
# - 总是重新爬取
# - 写入缓存但不读取
config4 = CrawlerRunConfig(cache_mode=CacheMode.WRITE_ONLY)
```

---

## 4. 提取策略

### 4.1 CSS选择器提取 (JsonCssExtractionStrategy)

```python
from crawl4ai import JsonCssExtractionStrategy

schema = {
    "name": "Product Info",           # 提取模式名称
    "baseSelector": ".product-item",  # 基础选择器（重复元素）
    "fields": [
        {
            "name": "title",
            "selector": "h2.title",
            "type": "text"              # 提取文本
        },
        {
            "name": "price",
            "selector": ".price",
            "type": "text"
        },
        {
            "name": "link",
            "selector": "a",
            "type": "attribute",        # 提取属性
            "attribute": "href"
        },
        {
            "name": "image",
            "selector": "img",
            "type": "attribute",
            "attribute": "src"
        },
        {
            "name": "in_stock",
            "selector": ".stock-badge",
            "type": "exists"            # 检查元素是否存在
        },
        {
            "name": "tags",
            "selector": ".tag",
            "type": "text",
            "multiple": True            # 提取多个匹配元素
        },
    ],
}

strategy = JsonCssExtractionStrategy(schema=schema)
```

### 4.2 XPath选择器提取 (JsonXPathExtractionStrategy)

```python
from crawl4ai import JsonXPathExtractionStrategy

schema = {
    "baseSelector": "//div[@class='product']",
    "fields": [
        {
            "name": "title",
            "selector": ".//h1/text()",   # XPath表达式
            "type": "text"
        },
    ],
}

strategy = JsonXPathExtractionStrategy(schema=schema)
```

### 4.3 LLM提取策略 (LLMExtractionStrategy)

```python
from crawl4ai import LLMExtractionStrategy, LLMConfig
from pydantic import BaseModel, Field

# 定义数据模型
class Product(BaseModel):
    name: str = Field(..., description="产品名称")
    price: str = Field(..., description="产品价格")
    description: str = Field(..., description="产品描述")

strategy = LLMExtractionStrategy(
    llm_config=LLMConfig(
        provider="openai/gpt-4o",      # LLM提供商
        api_token="your-api-key"
    ),
    schema=Product.model_json_schema(), # Pydantic模型schema
    extraction_type="schema",           # 提取类型
    instruction="提取产品信息",          # 提取指令
    input_format="markdown",            # 输入格式: markdown/html/fit_markdown
    extra_args={
        "temperature": 0,               # 温度参数
        "max_tokens": 2000,
    },
)
```

#### 支持的LLM提供商

| 提供商 | 格式 | 示例 |
|--------|------|------|
| OpenAI | `openai/model-name` | `openai/gpt-4o` |
| DeepSeek | `deepseek/model-name` | `deepseek/deepseek-chat` |
| Ollama | `ollama/model-name` | `ollama/llama3` |
| Groq | `groq/model-name` | `groq/llama-3.1-70b` |
| Anthropic | `anthropic/model-name` | `anthropic/claude-3-sonnet` |

---

## 5. 深度爬取策略

### 5.1 BFS深度爬取 (BFSDeepCrawlStrategy)

```python
from crawl4ai.deep_crawling import BFSDeepCrawlStrategy

strategy = BFSDeepCrawlStrategy(
    max_depth=2,                      # 最大深度
    include_external=False,           # 是否包含外部链接
    max_pages=50,                     # 最大页面数
    url_scorer=None,                  # URL评分器（可选）
    filter_chain=None,                # 过滤器链（可选）
)
```

### 5.2 DFS深度爬取 (DFSDeepCrawlStrategy)

```python
from crawl4ai.deep_crawling import DFSDeepCrawlStrategy

strategy = DFSDeepCrawlStrategy(
    max_depth=3,
    include_external=False,
    max_pages=20,
    url_scorer=None,
    score_threshold=0.5,              # 评分阈值
)
```

### 5.3 最佳优先爬取 (BestFirstCrawlingStrategy)

```python
from crawl4ai.deep_crawling import BestFirstCrawlingStrategy
from crawl4ai.deep_crawling.scorers import KeywordRelevanceScorer

# 创建评分器
scorer = KeywordRelevanceScorer(
    keywords=["crawl", "browser", "api"],
    weight=1.0
)

strategy = BestFirstCrawlingStrategy(
    max_depth=2,
    include_external=False,
    url_scorer=scorer,                # 使用评分器
    max_pages=10,
)
```

### 5.4 过滤器链

```python
from crawl4ai.deep_crawling.filters import (
    FilterChain,
    URLPatternFilter,
    DomainFilter,
    ContentTypeFilter,
    SEOFilter,
    ContentRelevanceFilter,
)

filter_chain = FilterChain([
    # 域名过滤器
    DomainFilter(
        allowed_domains=["docs.crawl4ai.com"],
        blocked_domains=["old.docs.crawl4ai.com"]
    ),
    # URL模式过滤器
    URLPatternFilter(patterns=["*api*", "*core*"]),
    # 内容类型过滤器
    ContentTypeFilter(allowed_types=["text/html"]),
    # SEO过滤器
    SEOFilter(threshold=0.5, keywords=["crawl", "scrape"]),
    # 内容相关性过滤器
    ContentRelevanceFilter(
        query="web crawling tutorial",
        threshold=0.7
    ),
])
```

---

## 6. 调度器配置

### 6.1 内存自适应调度器 (MemoryAdaptiveDispatcher)

```python
from crawl4ai import MemoryAdaptiveDispatcher, RateLimiter, CrawlerMonitor, DisplayMode

dispatcher = MemoryAdaptiveDispatcher(
    memory_threshold_percent=70.0,    # 内存使用阈值（%）
    max_session_permit=10,            # 最大会话数
    rate_limiter=RateLimiter(
        base_delay=(1.0, 2.0),        # 基础延迟范围（秒）
        max_delay=30.0,               # 最大延迟
        max_retries=2,                # 最大重试次数
    ),
    monitor=CrawlerMonitor(
        max_visible_rows=15,          # 监控显示行数
        display_mode=DisplayMode.DETAILED,  # 显示模式
    ),
)
```

### 6.2 信号量调度器 (SemaphoreDispatcher)

```python
from crawl4ai import SemaphoreDispatcher, RateLimiter, CrawlerMonitor, DisplayMode

dispatcher = SemaphoreDispatcher(
    semaphore_count=5,                # 并发数
    rate_limiter=RateLimiter(
        base_delay=(1.0, 2.0),
        max_delay=30.0,
        max_retries=2,
    ),
    monitor=CrawlerMonitor(
        max_visible_rows=15,
        display_mode=DisplayMode.DETAILED,
    ),
)
```

### 6.3 显示模式

| 模式 | 说明 |
|------|------|
| `DisplayMode.SIMPLE` | 简单显示 |
| `DisplayMode.DETAILED` | 详细显示 |
| `DisplayMode.NO_DISPLAY` | 不显示 |

---

## 7. Markdown生成器配置

### 7.1 PruningContentFilter

```python
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

filter_strategy = PruningContentFilter(
    threshold=0.48,                   # 过滤阈值
    threshold_type="fixed",           # 阈值类型: fixed/dynamic
    min_word_threshold=0,             # 最小词数
)

markdown_generator = DefaultMarkdownGenerator(
    content_filter=filter_strategy
)
```

### 7.2 BM25ContentFilter

```python
from crawl4ai.content_filter_strategy import BM25ContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

filter_strategy = BM25ContentFilter(
    user_query="web scraping tutorial",  # 用户查询
    bm25_threshold=1.0,                  # BM25阈值
)

markdown_generator = DefaultMarkdownGenerator(
    content_filter=filter_strategy
)
```

---

## 8. 完整配置示例

```python
from crawl4ai import (
    AsyncWebCrawler,
    BrowserConfig,
    CrawlerRunConfig,
    CacheMode,
    MemoryAdaptiveDispatcher,
    RateLimiter,
)
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

# 浏览器配置
browser_config = BrowserConfig(
    headless=True,
    browser_type="chromium",
    viewport_width=1920,
    viewport_height=1080,
    enable_stealth=True,
    java_script_enabled=True,
)

# 运行配置
run_config = CrawlerRunConfig(
    cache_mode=CacheMode.ENABLED,
    word_count_threshold=10,
    excluded_tags=["nav", "footer", "aside"],
    remove_overlay_elements=True,
    wait_until="networkidle",
    page_timeout=30000,
    mean_delay=1.5,
    markdown_generator=DefaultMarkdownGenerator(
        content_filter=PruningContentFilter(threshold=0.48)
    ),
)

# 调度器配置
dispatcher = MemoryAdaptiveDispatcher(
    memory_threshold_percent=70.0,
    max_session_permit=10,
    rate_limiter=RateLimiter(base_delay=(1.0, 2.0)),
)

# 使用配置
async with AsyncWebCrawler(config=browser_config) as crawler:
    results = await crawler.arun_many(
        urls=url_list,
        config=run_config,
        dispatcher=dispatcher,
    )
```

---

## 参考链接

- [官方文档](https://docs.crawl4ai.com)
- [GitHub仓库](https://github.com/unclecode/crawl4ai)
- [示例代码](https://github.com/unclecode/crawl4ai/tree/main/docs/examples)
