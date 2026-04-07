# Crawl4AI 完整使用文档

> **文档版本**: v1.0  
> **适用版本**: Crawl4AI v0.8.x  
> **更新日期**: 2025年4月  
> **GitHub Stars**: 63.5k+ ⭐

---

## 📋 目录

1. [概述](#一概述)
2. [核心功能](#二核心功能)
3. [安装与配置](#三安装与配置)
4. [快速入门](#四快速入门)
5. [基础使用](#五基础使用)
6. [高级功能](#六高级功能)
7. [提取策略](#七提取策略)
8. [实际应用场景](#八实际应用场景)
9. [常见问题排查](#九常见问题排查)
10. [学习资源](#十学习资源)

---

## 一、概述

### 1.1 什么是 Crawl4AI

**Crawl4AI** 是一个开源的、专为大型语言模型（LLM）优化的异步网页爬虫和抓取工具。它旨在简化网络爬虫和数据提取流程，使其适用于AI应用、RAG（检索增强生成）管道和数据管道。

### 1.2 核心定位

| 特性 | 说明 |
|------|------|
| 🤖 **LLM-First Design** | 专为RAG管道和LLM应用设计 |
| 🚀 **AI原生架构** | 将AI能力嵌入爬取-解析-反爬的每个环节 |
| ⚡ **性能优先** | 异步架构提供6倍于传统爬虫的性能提升 |
| 🆓 **完全开源** | Apache 2.0许可证，无需API密钥即可使用核心功能 |

### 1.3 与同类工具对比

| 特性 | Crawl4AI | Scrapy | Playwright | Firecrawl |
|------|----------|--------|------------|-----------|
| LLM原生支持 | ✅ 内置 | ❌ 需集成 | ❌ 需集成 | ✅ 内置 |
| Markdown输出 | ✅ 原生 | ❌ 需处理 | ❌ 需处理 | ✅ 原生 |
| 动态页面 | ✅ Playwright | ⚠️ 需集成 | ✅ 原生 | ✅ 原生 |
| 开源免费 | ✅ 完全 | ✅ 完全 | ✅ 完全 | ⚠️ 有限 |
| 学习成本 | 低 | 高 | 中等 | 低 |

---

## 二、核心功能

### 2.1 Markdown生成与内容处理

| 功能 | 描述 | 适用场景 |
|------|------|----------|
| **Clean Markdown** | 生成干净、结构化的Markdown格式 | 通用内容提取 |
| **Fit Markdown** | 基于启发式算法过滤噪声内容 | RAG管道输入 |
| **Citation Support** | 自动转换页面链接为编号引用列表 | 学术引用场景 |
| **BM25算法过滤** | 使用BM25算法提取核心信息 | 信息检索优化 |

### 2.2 结构化数据提取策略

| 策略类型 | 类名 | 特点 | 性能 |
|----------|------|------|------|
| **LLM驱动提取** | `LLMExtractionStrategy` | 支持自然语言指令，语义理解强 | 较慢，需API调用 |
| **CSS选择器提取** | `JsonCssExtractionStrategy` | 基于CSS选择器，精确快速 | 极快 |
| **XPath提取** | `JsonXPathExtractionStrategy` | 支持复杂层级导航 | 极快 |
| **正则表达式提取** | `RegexExtractionStrategy` | 模式匹配，适合标准数据 | 最快 |
| **余弦相似度聚类** | `CosineStrategy` | 语义聚类，无需规则 | 中等 |

### 2.3 浏览器控制与管理

| 功能 | 描述 | 配置参数 |
|------|------|----------|
| **隐身模式** | 修改浏览器指纹避免检测 | `enable_stealth=True` |
| **Undetected Browser** | 高级反检测适配器 | `UndetectedAdapter` |
| **用户浏览器** | 使用自有浏览器实例 | `use_managed_browser=True` |
| **远程CDP控制** | 连接Chrome DevTools Protocol | `cdp_url="ws://..."` |
| **浏览器Profile** | 持久化认证状态和Cookie | `browser_profiler` |

### 2.4 深度爬取策略

| 策略 | 特点 | 最佳场景 |
|------|------|----------|
| **BFS** | 先广后深，全面覆盖 | 网站索引、快速扫描 |
| **DFS** | 先深后广，深入探索 | 分类目录、嵌套结构 |
| **Best-First** | 基于评分优先 | 目标导向爬取 |

---

## 三、安装与配置

### 3.1 环境要求

| 项目 | 要求 |
|------|------|
| Python版本 | **3.10或更高版本** |
| 操作系统 | Linux、macOS、Windows |
| 内存 | 至少4GB RAM（推荐8GB+） |

### 3.2 基础安装（推荐）

```bash
# 1. 安装核心包
pip install -U crawl4ai

# 2. 运行安装后设置（安装浏览器依赖）
crawl4ai-setup

# 3. 验证安装状态
crawl4ai-doctor
```

### 3.3 预发布版本安装

```bash
pip install crawl4ai --pre
crawl4ai-setup
crawl4ai-doctor
```

### 3.4 手动安装Playwright浏览器

```bash
# 方法1：安装所有浏览器
playwright install

# 方法2：仅安装Chromium（推荐）
python -m playwright install chromium

# 方法3：带系统依赖的安装（Linux）
python -m playwright install --with-deps chromium
```

### 3.5 高级功能安装（可选）

```bash
# 安装PyTorch功能（文本聚类、语义分块）
pip install crawl4ai[torch]

# 安装Transformers功能（Hugging Face摘要/生成）
pip install crawl4ai[transformer]

# 安装所有功能
pip install crawl4ai[all]
```

### 3.6 Docker部署

```bash
# 拉取官方镜像
docker pull unclecode/crawl4ai:latest

# 运行容器
docker run -d \
  -p 11235:11235 \
  --name crawl4ai \
  --shm-size=3g \
  unclecode/crawl4ai:latest
```

### 3.7 不同操作系统注意事项

**Linux (Ubuntu/Debian)**
```bash
sudo apt-get update
sudo apt-get install -y libnss3 libnspr4 libasound2 \
    libatk1.0-0 libatk-bridge2.0-0 libgomp1
```

**macOS (M1/M2芯片)**
```bash
# 如遇onnxruntime问题
conda install -c conda-forge onnxruntime
```

---

## 四、快速入门

### 4.1 第一个爬虫程序

```python
import asyncio
from crawl4ai import AsyncWebCrawler

async def first_crawl():
    """你的第一个智能爬取程序"""
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(
            url="https://www.nbcnews.com/business",
        )
        print(f"成功爬取页面，内容长度：{len(result.markdown.raw_markdown)}")
        print(result.markdown.raw_markdown[:500])  # 打印前500个字符

if __name__ == "__main__":
    asyncio.run(first_crawl())
```

### 4.2 使用配置类

```python
import asyncio
from crawl4ai import AsyncWebCrawler
from crawl4ai.async_configs import BrowserConfig, CrawlerRunConfig, CacheMode

async def main():
    # 浏览器配置
    browser_config = BrowserConfig(
        headless=True,  # 无头模式
        verbose=True    # 详细日志
    )
    
    # 爬取运行配置
    run_config = CrawlerRunConfig(
        word_count_threshold=10,  # 最小词数阈值
        cache_mode=CacheMode.ENABLED  # 启用缓存
    )
    
    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun(
            url="https://example.com",
            config=run_config
        )
        print(result.markdown.fit_markdown)  # 打印最相关的内容

if __name__ == "__main__":
    asyncio.run(main())
```

### 4.3 命令行工具使用

```bash
# 基础爬取（输出Markdown）
crwl https://www.nbcnews.com/business -o markdown

# 深度爬取（BFS策略，最多10页）
crwl https://docs.crawl4ai.com --deep-crawl bfs --max-pages 10

# 使用LLM提取特定信息
crwl https://www.example.com/products -q "Extract all product prices"

# 输出JSON格式
crwl https://example.com -o json

# 保存到文件
crwl https://example.com -o markdown > output.md
```

---

## 五、基础使用

### 5.1 处理爬取结果

```python
import asyncio
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig

async def main():
    browser_config = BrowserConfig()
    run_config = CrawlerRunConfig()
    
    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun(
            url="https://example.com",
            config=run_config
        )
        
        # 访问不同格式的内容
        print(result.html)                    # 原始HTML
        print(result.cleaned_html)            # 清理后的HTML
        print(result.markdown.raw_markdown)   # 原始Markdown
        print(result.markdown.fit_markdown)   # 最相关内容的Markdown
        
        # 检查状态
        print(result.success)      # 是否成功
        print(result.status_code)  # HTTP状态码
        
        # 访问媒体资源
        print(result.media)  # 图片、视频、音频
        print(result.links)  # 内部和外部链接

if __name__ == "__main__":
    asyncio.run(main())
```

### 5.2 Markdown生成与内容过滤

```python
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

async def main():
    run_config = CrawlerRunConfig(
        markdown_generator=DefaultMarkdownGenerator(
            content_filter=PruningContentFilter(
                threshold=0.48, 
                threshold_type="fixed"
            ),
            options={"ignore_links": True}
        )
    )
    
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(
            url="https://docs.micronaut.io/4.9.9/guide/",
            config=run_config
        )
        print(result.markdown.fit_markdown)

if __name__ == "__main__":
    asyncio.run(main())
```

### 5.3 BM25内容过滤

```python
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.content_filter_strategy import BM25ContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

async def main():
    browser_config = BrowserConfig(headless=True)
    
    run_config = CrawlerRunConfig(
        cache_mode=CacheMode.ENABLED,
        markdown_generator=DefaultMarkdownGenerator(
            content_filter=BM25ContentFilter(
                user_query="Crawl4AI configuration browser settings",
                bm25_threshold=1.0
            )
        ),
    )
    
    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun(
            url="https://docs.crawl4ai.com",
            config=run_config
        )
        print(result.markdown.fit_markdown)

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 六、高级功能

### 6.1 BrowserConfig 详细配置

```python
from crawl4ai import BrowserConfig
from pathlib import Path
import os

def create_browser_config():
    """创建详细的浏览器配置"""
    # 用户数据目录（用于持久化会话）
    user_data_dir = os.path.join(Path.home(), ".crawl4ai", "browser_profile")
    os.makedirs(user_data_dir, exist_ok=True)
    
    browser_config = BrowserConfig(
        # 基本设置
        headless=True,                    # 无头模式
        browser_type="chromium",          # 浏览器类型: chromium/firefox/webkit/undetected
        verbose=True,                     # 详细日志
        
        # 视口设置
        viewport_width=1920,              # 视口宽度
        viewport_height=1080,             # 视口高度
        
        # JavaScript设置
        java_script_enabled=True,         # 启用JavaScript
        
        # 反检测设置
        enable_stealth=True,              # 启用stealth模式（隐藏自动化特征）
        
        # 代理设置
        proxy_config={
            "server": "http://proxy.example.com:8080",
            "username": "user",
            "password": "pass"
        },
        
        # 持久化设置
        user_data_dir=user_data_dir,      # 用户数据目录
        use_persistent_context=True,      # 使用持久化上下文
        
        # 性能优化
        text_mode=True,                   # 文本模式（不加载图片）
        light_mode=True,                  # 轻量模式（禁用非必要任务）
        
        # 额外参数
        extra_args=[
            "--disable-blink-features=AutomationControlled",
            "--disable-web-security",
            "--no-sandbox",
            "--disable-setuid-sandbox"
        ],
    )
    
    return browser_config
```

### 6.2 CrawlerRunConfig 详细配置

```python
from crawl4ai import CrawlerRunConfig, CacheMode

def create_crawler_run_config():
    """创建详细的爬虫运行配置"""
    run_config = CrawlerRunConfig(
        # 内容处理设置
        word_count_threshold=10,          # 字数阈值（低于此值的文本块被忽略）
        excluded_tags=["nav", "footer", "aside", "header"],  # 排除的HTML标签
        exclude_external_links=True,      # 排除外部链接
        remove_overlay_elements=True,     # 移除弹窗等覆盖元素
        
        # 页面导航设置
        wait_until="networkidle",         # 等待条件: load/domcontentloaded/networkidle
        page_timeout=30000,               # 页面加载超时（毫秒）
        delay_before_return_html=2.0,     # 返回HTML前的额外延迟
        
        # 等待元素
        wait_for="css:.content-loaded",   # 等待特定CSS选择器出现
        
        # 缓存设置
        cache_mode=CacheMode.ENABLED,     # 缓存模式
        
        # 截图设置
        screenshot=True,                  # 启用截图
        screenshot_options={
            "full_page": True,            # 全页截图
            "type": "png",                # 图片格式
            "quality": 90                 # 图片质量（JPEG）
        },
        
        # 礼貌爬取
        check_robots_txt=True,            # 检查robots.txt
        mean_delay=1.5,                   # 平均延迟（秒）
        max_range=1.0,                    # 最大随机延迟浮动
        
        # 并发控制
        semaphore_count=3,                # 并发数
    )
    
    return run_config
```

### 6.3 缓存模式说明

```python
from crawl4ai import CacheMode, CrawlerRunConfig

# ENABLED: 启用缓存（默认）- 如果缓存存在则读取，否则写入
config1 = CrawlerRunConfig(cache_mode=CacheMode.ENABLED)

# BYPASS: 绕过缓存 - 总是重新爬取，不读取也不写入缓存
config2 = CrawlerRunConfig(cache_mode=CacheMode.BYPASS)

# READ_ONLY: 只读模式 - 只读取缓存，不写入新缓存
config3 = CrawlerRunConfig(cache_mode=CacheMode.READ_ONLY)

# WRITE_ONLY: 只写模式 - 总是重新爬取并写入缓存，不读取缓存
config4 = CrawlerRunConfig(cache_mode=CacheMode.WRITE_ONLY)
```

### 6.4 页面交互（JavaScript执行）

```python
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig

async def main():
    run_config = CrawlerRunConfig(
        js_code="""
            // 滚动到页面底部
            window.scrollTo(0, document.body.scrollHeight);
            
            // 点击"加载更多"按钮
            document.querySelector('.load-more').click();
        """,
        wait_for="div.loaded-content",  # 等待特定元素出现
        timeout=60000  # 超时时间60秒
    )
    
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(
            url="https://example.com/dynamic",
            config=run_config
        )
        print(result.markdown.raw_markdown)

if __name__ == "__main__":
    asyncio.run(main())
```

### 6.5 代理和认证

```python
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig

async def main():
    browser_config = BrowserConfig(
        proxy="http://user:pass@proxy:8080"
    )
    
    run_config = CrawlerRunConfig(
        hooks={
            "on_page_context_created": """
                await page.context.add_cookies([
                    {"name": "session", "value": "your-session", "domain": ".example.com"}
                ]);
            """
        }
    )
    
    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun(
            url="https://example.com/protected",
            config=run_config
        )
        print(result.markdown.raw_markdown)

if __name__ == "__main__":
    asyncio.run(main())
```

### 6.6 深度爬取

```python
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
from crawl4ai.deep_crawling import BFSDeepCrawlStrategy

async def main():
    run_config = CrawlerRunConfig(
        deep_crawl_strategy=BFSDeepCrawlStrategy(
            max_pages=10,
            max_depth=2
        )
    )
    
    async with AsyncWebCrawler() as crawler:
        results = await crawler.arun(
            url="https://docs.crawl4ai.com",
            config=run_config
        )
        for result in results:
            print(f"URL: {result.url}")
            print(f"Content length: {len(result.markdown.raw_markdown)}")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 七、提取策略

### 7.1 CSS选择器提取

```python
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy

schema = {
    "name": "Product",
    "baseSelector": "div.product",
    "fields": [
        {"name": "title", "selector": "h2", "type": "text"},
        {"name": "price", "selector": ".price", "type": "text"},
        {"name": "image", "selector": "img", "type": "attribute", "attribute": "src"}
    ]
}

async def main():
    run_config = CrawlerRunConfig(
        extraction_strategy=JsonCssExtractionStrategy(schema)
    )
    
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(
            url="https://example.com/products",
            config=run_config
        )
        print(result.extracted_content)

if __name__ == "__main__":
    asyncio.run(main())
```

### 7.2 LLM提取

```python
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
from crawl4ai.extraction_strategy import LLMExtractionStrategy

async def main():
    run_config = CrawlerRunConfig(
        extraction_strategy=LLMExtractionStrategy(
            provider="openai/gpt-4o",
            api_token="your-api-key",
            instruction="Extract all product names and prices as a JSON list"
        )
    )
    
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(
            url="https://example.com/products",
            config=run_config
        )
        print(result.extracted_content)

if __name__ == "__main__":
    asyncio.run(main())
```

### 7.3 使用Pydantic Schema的LLM提取

```python
from pydantic import BaseModel, Field
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
from crawl4ai.extraction_strategy import LLMExtractionStrategy

class Product(BaseModel):
    name: str = Field(..., description="产品名称")
    price: float = Field(..., description="产品价格")
    description: str = Field(..., description="产品描述")

async def main():
    run_config = CrawlerRunConfig(
        extraction_strategy=LLMExtractionStrategy(
            provider="openai/gpt-4o",
            api_token="your-api-key",
            schema=Product.model_json_schema(),
            instruction="从页面中提取所有产品信息"
        )
    )
    
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(
            url="https://example.com/products",
            config=run_config
        )
        print(result.extracted_content)

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 八、实际应用场景

### 8.1 电商价格监控

```python
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
import json

class ProductPrice(BaseModel):
    product_id: str = Field(..., description="产品ID")
    name: str = Field(..., description="产品名称")
    current_price: float = Field(..., description="当前价格")
    original_price: Optional[float] = Field(None, description="原价")
    currency: str = Field(default="CNY", description="货币")
    availability: str = Field(..., description="库存状态")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())

async def ecommerce_price_monitor():
    """电商价格监控系统"""
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
    from crawl4ai import JsonCssExtractionStrategy
    
    products_to_monitor = [
        {"url": "https://example.com/product/1", "product_id": "P001"},
        {"url": "https://example.com/product/2", "product_id": "P002"},
    ]
    
    price_schema = {
        "baseSelector": ".product-detail",
        "fields": [
            {"name": "name", "selector": "h1.product-name", "type": "text"},
            {"name": "current_price", "selector": ".current-price", "type": "text"},
            {"name": "original_price", "selector": ".original-price", "type": "text"},
            {"name": "availability", "selector": ".stock-status", "type": "text"},
        ],
    }
    
    browser_config = BrowserConfig(
        headless=True,
        enable_stealth=True,
    )
    
    run_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        extraction_strategy=JsonCssExtractionStrategy(schema=price_schema),
        wait_for="css:.product-detail",
    )
    
    price_history = []
    
    async with AsyncWebCrawler(config=browser_config) as crawler:
        for product in products_to_monitor:
            try:
                result = await crawler.arun(product["url"], config=run_config)
                
                if result and result.extracted_content:
                    data = json.loads(result.extracted_content)
                    
                    current_price = float(data.get("current_price", "0").replace("¥", "").replace(",", ""))
                    original_price_str = data.get("original_price", "")
                    original_price = float(original_price_str.replace("¥", "").replace(",", "")) if original_price_str else None
                    
                    price_info = ProductPrice(
                        product_id=product["product_id"],
                        name=data.get("name", ""),
                        current_price=current_price,
                        original_price=original_price,
                        availability=data.get("availability", "unknown"),
                    )
                    
                    price_history.append(price_info)
                    
                    print(f"产品: {price_info.name}")
                    print(f"当前价格: ¥{price_info.current_price}")
                    if original_price:
                        discount = (original_price - current_price) / original_price * 100
                        print(f"折扣: {discount:.1f}%")
                    print("-" * 50)
                    
            except Exception as e:
                print(f"监控产品 {product['product_id']} 时出错: {e}")
    
    # 保存价格历史
    with open("price_history.json", "w", encoding="utf-8") as f:
        json.dump([p.model_dump() for p in price_history], f, ensure_ascii=False, indent=2)
    
    return price_history
```

### 8.2 新闻聚合系统

```python
from pydantic import BaseModel, Field
from typing import Optional, List
import json
import os

class NewsArticle(BaseModel):
    title: str = Field(..., description="标题")
    content: str = Field(..., description="正文内容")
    author: Optional[str] = Field(None, description="作者")
    publish_date: Optional[str] = Field(None, description="发布日期")
    source: str = Field(..., description="来源")
    url: str = Field(..., description="原文链接")
    summary: Optional[str] = Field(None, description="摘要")

async def news_aggregator():
    """新闻聚合系统"""
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
    from crawl4ai.content_filter_strategy import PruningContentFilter
    from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
    from crawl4ai import LLMExtractionStrategy, LLMConfig
    
    news_sources = [
        {"name": "TechNews", "url": "https://technews.example.com/article/1"},
        {"name": "ScienceDaily", "url": "https://sciencedaily.example.com/article/2"},
    ]
    
    browser_config = BrowserConfig(headless=True)
    
    content_config = CrawlerRunConfig(
        cache_mode=CacheMode.ENABLED,
        word_count_threshold=50,
        excluded_tags=["nav", "footer", "aside", "header", "script", "style"],
        remove_overlay_elements=True,
        wait_until="networkidle",
        markdown_generator=DefaultMarkdownGenerator(
            content_filter=PruningContentFilter(threshold=0.4)
        ),
    )
    
    summary_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        extraction_strategy=LLMExtractionStrategy(
            llm_config=LLMConfig(
                provider="openai/gpt-4o-mini",
                api_token=os.getenv("OPENAI_API_KEY")
            ),
            instruction="""请为这篇文章生成一个简洁的摘要（100字以内），并提取以下信息：
            1. 作者
            2. 发布日期（ISO格式）
            返回JSON格式：{"summary": "...", "author": "...", "publish_date": "..."}""",
            extra_args={"temperature": 0.3},
        ),
    )
    
    articles = []
    
    async with AsyncWebCrawler(config=browser_config) as crawler:
        for source in news_sources:
            try:
                result = await crawler.arun(source["url"], config=content_config)
                
                if result.success:
                    summary_result = await crawler.arun(source["url"], config=summary_config)
                    
                    summary_data = {}
                    if summary_result.extracted_content:
                        try:
                            summary_data = json.loads(summary_result.extracted_content)
                        except:
                            pass
                    
                    article = NewsArticle(
                        title=result.metadata.get("title", ""),
                        content=result.markdown.fit_markdown,
                        author=summary_data.get("author"),
                        publish_date=summary_data.get("publish_date"),
                        source=source["name"],
                        url=source["url"],
                        summary=summary_data.get("summary"),
                    )
                    
                    articles.append(article)
                    print(f"✅ 已获取: {article.title[:50]}...")
                    
            except Exception as e:
                print(f"❌ 获取新闻失败 {source['url']}: {e}")
    
    # 保存聚合结果
    with open("news_articles.json", "w", encoding="utf-8") as f:
        json.dump([a.model_dump() for a in articles], f, ensure_ascii=False, indent=2)
    
    return articles
```

### 8.3 学术论文收集

```python
from pydantic import BaseModel, Field
from typing import List, Optional
import json
import os

class ResearchPaper(BaseModel):
    title: str = Field(..., description="论文标题")
    authors: List[str] = Field(..., description="作者列表")
    abstract: str = Field(..., description="摘要")
    keywords: List[str] = Field(..., description="关键词")
    publication_date: Optional[str] = Field(None, description="发表日期")
    doi: Optional[str] = Field(None, description="DOI")
    url: str = Field(..., description="论文链接")

async def academic_paper_collector():
    """学术论文收集系统"""
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
    from crawl4ai import LLMExtractionStrategy, LLMConfig
    
    paper_urls = [
        "https://arxiv.org/abs/2401.12345",
        "https://papers.example.com/paper/2",
    ]
    
    browser_config = BrowserConfig(headless=True)
    
    run_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        extraction_strategy=LLMExtractionStrategy(
            llm_config=LLMConfig(
                provider="openai/gpt-4o",
                api_token=os.getenv("OPENAI_API_KEY")
            ),
            schema=ResearchPaper.model_json_schema(),
            instruction="""从页面中提取学术论文的完整信息：
            1. 论文标题
            2. 作者列表（数组格式）
            3. 摘要
            4. 关键词（数组格式）
            5. 发表日期（ISO格式）
            6. DOI（如果有）
            确保提取所有可用信息，不要遗漏任何作者。""",
            extra_args={"temperature": 0},
        ),
    )
    
    papers = []
    
    async with AsyncWebCrawler(config=browser_config) as crawler:
        for url in paper_urls:
            try:
                result = await crawler.arun(url, config=run_config)
                
                if result and result.extracted_content:
                    paper_data = json.loads(result.extracted_content)
                    paper = ResearchPaper(
                        title=paper_data.get("title", ""),
                        authors=paper_data.get("authors", []),
                        abstract=paper_data.get("abstract", ""),
                        keywords=paper_data.get("keywords", []),
                        publication_date=paper_data.get("publication_date"),
                        doi=paper_data.get("doi"),
                        url=url,
                    )
                    
                    papers.append(paper)
                    print(f"✅ 已收集: {paper.title[:60]}...")
                    print(f"   作者: {', '.join(paper.authors[:3])}")
                    
            except Exception as e:
                print(f"❌ 收集论文失败 {url}: {e}")
    
    # 保存论文库
    with open("paper_collection.json", "w", encoding="utf-8") as f:
        json.dump([p.model_dump() for p in papers], f, ensure_ascii=False, indent=2)
    
    return papers
```

---

## 九、常见问题排查

### 9.1 安装问题

| 问题 | 症状 | 解决方案 |
|------|------|----------|
| Playwright浏览器未找到 | `Executable doesn't exist` | `playwright install` |
| Linux系统库缺失 | `error while loading shared libraries` | `sudo apt-get install libnss3 libnspr4` |
| Mac M1安装失败 | onnxruntime wheel构建失败 | `conda install -c conda-forge onnxruntime` |

### 9.2 运行时问题

| 问题 | 症状 | 解决方案 |
|------|------|----------|
| 异步上下文错误 | `'NoneType' has no attribute` | 确保使用 `async with` |
| 页面加载超时 | 动态内容未完全加载 | 增加 `timeout` 参数 |
| 被反爬拦截 | 检测为机器人 | 启用 `enable_stealth=True` |

### 9.3 调试技巧

```python
# 启用详细日志
from crawl4ai import AsyncWebCrawler

async with AsyncWebCrawler(log_level="DEBUG") as crawler:
    result = await crawler.arun(url)
    
# 临时禁用headless查看浏览器行为
browser_config = BrowserConfig(headless=False, verbose=True)
```

---

## 十、学习资源

### 10.1 官方资源

| 资源类型 | 链接 | 说明 |
|----------|------|------|
| 🏠 **GitHub仓库** | https://github.com/unclecode/crawl4ai | 源代码、Issues、PR |
| 📖 **官方文档** | https://docs.crawl4ai.com | 完整文档和API参考 |
| 🌐 **官方网站** | https://crawl4ai.com | 项目主页 |
| 💬 **Discord社区** | https://discord.gg/jP8KfhDhyN | 社区讨论和支持 |

### 10.2 第三方教程

| 标题 | 链接 | 语言 |
|------|------|------|
| Crawl4AI终极指南 | https://blog.csdn.net/gitblog_00544/article/details/155374845 | 中文 |
| Crawl4AI Docker部署指南 | https://developer.volcengine.com/articles/7585503512579342363 | 中文 |
| 使用Crawl4AI和DeepSeek构建AI爬虫 | https://www.bright.cn/blog/web-data/crawl4ai-and-deepseek-web-scraping | 中文 |

---

## 附录：完整代码示例文件

所有代码示例已保存到以下文件：

| 文件路径 | 说明 | 行数 |
|---------|------|------|
| `/mnt/okcomputer/output/crawl4ai_examples.py` | 完整代码示例集合 | 300+ |
| `/mnt/okcomputer/output/crawl4ai_real_world_examples.py` | 实际应用场景示例 | 400+ |
| `/mnt/okcomputer/output/crawl4ai_config_guide.md` | 详细配置参数说明 | 600+ |
| `/mnt/okcomputer/output/crawl4ai_quick_reference.md` | 快速参考卡片 | 400+ |

---

> 💡 **提示**：本文档会持续更新，建议收藏官方文档获取最新信息。

> ⭐ 如果Crawl4AI对你有帮助，请在GitHub上给项目点个Star支持开发者！
