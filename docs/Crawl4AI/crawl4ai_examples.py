#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Crawl4AI 使用场景代码示例大全
=============================
本文件收集整理了 Crawl4AI 的各种使用场景代码示例，包括：
1. 基础使用示例（简单爬取、Markdown生成）
2. 配置示例（BrowserConfig、CrawlerRunConfig详细配置）
3. 提取策略示例（CSS/XPath提取、LLM提取）
4. 高级功能示例（动态页面、会话管理、代理、深度爬取）
5. 实际应用场景示例

作者: AI Assistant
版本: 基于 Crawl4AI v0.7.x+
"""

import asyncio
import json
import os
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

# =============================================================================
# 第一部分：基础使用示例
# =============================================================================

"""
1.1 最简单的爬取示例
--------------------
使用 AsyncWebCrawler 进行最基本的网页爬取
"""


async def basic_crawl_example():
    """最基础的爬取示例"""
    from crawl4ai import AsyncWebCrawler
    
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun("https://example.com")
        print(f"URL: {result.url}")
        print(f"标题: {result.metadata.get('title', 'N/A')}")
        print(f"Markdown长度: {len(result.markdown.raw_markdown)}")
        return result


"""
1.2 Markdown生成示例
--------------------
使用 DefaultMarkdownGenerator 和 PruningContentFilter 生成高质量的 Markdown
"""


async def markdown_generation_example():
    """Markdown生成示例 - 使用内容过滤"""
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
    from crawl4ai.content_filter_strategy import PruningContentFilter
    from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
    
    browser_config = BrowserConfig(headless=True, verbose=True)
    
    run_config = CrawlerRunConfig(
        cache_mode=CacheMode.ENABLED,
        markdown_generator=DefaultMarkdownGenerator(
            content_filter=PruningContentFilter(
                threshold=0.48,           # 过滤阈值
                threshold_type="fixed",   # 阈值类型
                min_word_threshold=0      # 最小词数阈值
            )
        ),
    )
    
    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun(
            url="https://docs.crawl4ai.com",
            config=run_config
        )
        print(f"原始Markdown长度: {len(result.markdown.raw_markdown)}")
        print(f"精简Markdown长度: {len(result.markdown.fit_markdown)}")
        return result


"""
1.3 BM25内容过滤示例
--------------------
使用 BM25 算法根据用户查询进行内容过滤
"""


async def bm25_filter_example():
    """BM25内容过滤示例"""
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
    from crawl4ai.content_filter_strategy import BM25ContentFilter
    from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
    
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
        print(f"过滤后内容长度: {len(result.markdown.fit_markdown)}")
        return result


# =============================================================================
# 第二部分：配置示例
# =============================================================================

"""
2.1 BrowserConfig 详细配置
--------------------------
浏览器级别的配置，控制浏览器的行为
"""


def create_browser_config():
    """创建详细的浏览器配置"""
    from crawl4ai import BrowserConfig
    from pathlib import Path
    
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
        
        # CDP连接（连接已有Chrome）
        # cdp_url="http://localhost:9222",
        # use_managed_browser=True,
    )
    
    return browser_config


"""
2.2 CrawlerRunConfig 详细配置
-----------------------------
爬虫运行时的配置，控制爬取行为
"""


def create_crawler_run_config():
    """创建详细的爬虫运行配置"""
    from crawl4ai import CrawlerRunConfig, CacheMode
    
    run_config = CrawlerRunConfig(
        # 内容处理设置
        word_count_threshold=10,          # 字数阈值（低于此值的文本块被忽略）
        excluded_tags=["nav", "footer", "aside", "header"],  # 排除的HTML标签
        exclude_external_links=True,      # 排除外部链接
        exclude_all_images=False,         # 是否排除所有图片
        remove_overlay_elements=True,     # 移除弹窗等覆盖元素
        remove_forms=True,                # 移除表单元素
        process_iframes=True,             # 处理iframe
        
        # 页面导航设置
        wait_until="networkidle",         # 等待条件: load/domcontentloaded/networkidle
        page_timeout=30000,               # 页面加载超时（毫秒）
        delay_before_return_html=2.0,     # 返回HTML前的额外延迟
        
        # 等待元素
        wait_for="css:.content-loaded",   # 等待特定CSS选择器出现
        # wait_for="js:() => document.readyState === 'complete'",
        
        # 缓存设置
        cache_mode=CacheMode.ENABLED,     # 缓存模式: ENABLED/BYPASS/READ_ONLY/WRITE_ONLY
        
        # 截图设置
        screenshot=True,                  # 启用截图
        screenshot_options={
            "full_page": True,            # 全页截图
            "type": "png",                # 图片格式
            "quality": 90                 # 图片质量（JPEG）
        },
        
        # 内容选择
        css_selector="article .content",  # 只提取匹配选择器的内容
        target_elements=["article", "main"],  # 目标元素选择器
        
        # 礼貌爬取
        check_robots_txt=True,            # 检查robots.txt
        mean_delay=1.5,                   # 平均延迟（秒）
        max_range=1.0,                    # 最大随机延迟浮动
        
        # 并发控制
        semaphore_count=3,                # 并发数
        
        # 其他
        prettiify=True,                   # 美化HTML输出
    )
    
    return run_config


"""
2.3 缓存模式说明
--------------
CacheMode 的四种模式
"""


def cache_mode_examples():
    """缓存模式示例"""
    from crawl4ai import CacheMode, CrawlerRunConfig
    
    # ENABLED: 启用缓存（默认）- 如果缓存存在则读取，否则写入
    config1 = CrawlerRunConfig(cache_mode=CacheMode.ENABLED)
    
    # BYPASS: 绕过缓存 - 总是重新爬取，不读取也不写入缓存
    config2 = CrawlerRunConfig(cache_mode=CacheMode.BYPASS)
    
    # READ_ONLY: 只读模式 - 只读取缓存，不写入新缓存
    config3 = CrawlerRunConfig(cache_mode=CacheMode.READ_ONLY)
    
    # WRITE_ONLY: 只写模式 - 总是重新爬取并写入缓存，不读取缓存
    config4 = CrawlerRunConfig(cache_mode=CacheMode.WRITE_ONLY)
    
    return config1, config2, config3, config4


# =============================================================================
# 第三部分：提取策略示例
# =============================================================================

"""
3.1 CSS选择器提取 (JsonCssExtractionStrategy)
--------------------------------------------
使用CSS选择器从网页中提取结构化数据
"""


async def css_extraction_example():
    """CSS选择器提取示例 - 提取Amazon产品信息"""
    from crawl4ai import AsyncWebCrawler, CacheMode, JsonCssExtractionStrategy
    from crawl4ai.async_configs import BrowserConfig, CrawlerRunConfig
    
    # 定义提取模式（Schema）
    schema = {
        "name": "Amazon Product Search Results",
        "baseSelector": "[data-component-type='s-search-result']",  # 基础选择器
        "fields": [
            {
                "name": "asin",
                "selector": "",
                "type": "attribute",
                "attribute": "data-asin",
            },
            {
                "name": "title",
                "selector": "h2 a span",
                "type": "text"
            },
            {
                "name": "url",
                "selector": "h2 a",
                "type": "attribute",
                "attribute": "href",
            },
            {
                "name": "image",
                "selector": ".s-image",
                "type": "attribute",
                "attribute": "src",
            },
            {
                "name": "rating",
                "selector": ".a-icon-star-small .a-icon-alt",
                "type": "text",
            },
            {
                "name": "price",
                "selector": ".a-price .a-offscreen",
                "type": "text",
            },
            {
                "name": "sponsored",
                "selector": ".puis-sponsored-label-text",
                "type": "exists",  # 检查元素是否存在
            },
            {
                "name": "delivery_info",
                "selector": "[data-cy='delivery-recipe'] .a-color-base",
                "type": "text",
                "multiple": True,  # 提取多个匹配元素
            },
        ],
    }
    
    browser_config = BrowserConfig(headless=True)
    
    crawler_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        extraction_strategy=JsonCssExtractionStrategy(schema=schema),
    )
    
    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun(
            url="https://www.amazon.com/s?k=laptop",
            config=crawler_config
        )
        
        if result and result.extracted_content:
            products = json.loads(result.extracted_content)
            for product in products[:3]:
                print(f"产品: {product.get('title')}")
                print(f"价格: {product.get('price')}")
                print(f"评分: {product.get('rating')}")
                print("-" * 50)
            return products
        return []


"""
3.2 XPath选择器提取 (JsonXPathExtractionStrategy)
------------------------------------------------
使用XPath选择器从网页中提取结构化数据
"""


async def xpath_extraction_example():
    """XPath选择器提取示例"""
    from crawl4ai import AsyncWebCrawler, CacheMode, JsonXPathExtractionStrategy
    from crawl4ai.async_configs import BrowserConfig, CrawlerRunConfig
    
    # 定义XPath提取模式
    schema = {
        "baseSelector": "//div[@class='product']",
        "fields": [
            {
                "name": "title",
                "selector": ".//h1[@class='product-title']/text()",
                "type": "text",
            },
            {
                "name": "price",
                "selector": ".//span[@class='price']/text()",
                "type": "text",
            },
            {
                "name": "description",
                "selector": ".//div[@class='description']/text()",
                "type": "text",
            },
            {
                "name": "image_url",
                "selector": ".//img[@class='product-image']/@src",
                "type": "text",
            },
        ],
    }
    
    browser_config = BrowserConfig(headless=True)
    
    crawler_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        extraction_strategy=JsonXPathExtractionStrategy(schema=schema),
    )
    
    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun(
            url="https://example.com/products",
            config=crawler_config
        )
        
        if result and result.extracted_content:
            data = json.loads(result.extracted_content)
            print(f"提取到 {len(data)} 条数据")
            return data
        return []


"""
3.3 LLM提取策略 (LLMExtractionStrategy)
---------------------------------------
使用大语言模型智能提取网页内容
"""


# 定义Pydantic模型用于结构化提取
class ProductInfo(BaseModel):
    """产品信息模型"""
    name: str = Field(..., description="产品名称")
    price: str = Field(..., description="产品价格")
    description: str = Field(..., description="产品描述")
    rating: Optional[str] = Field(None, description="产品评分")


class OpenAIModelFee(BaseModel):
    """OpenAI模型费用信息"""
    model_name: str = Field(..., description="模型名称，如GPT-4o")
    input_fee: str = Field(..., description="输入token单价")
    output_fee: str = Field(..., description="输出token单价")


async def llm_extraction_example():
    """LLM提取示例 - 提取OpenAI定价信息"""
    from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, LLMConfig, BrowserConfig, CacheMode
    from crawl4ai.extraction_strategy import LLMExtractionStrategy
    
    browser_config = BrowserConfig(headless=True)
    
    crawler_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        word_count_threshold=1,
        page_timeout=80000,
        extraction_strategy=LLMExtractionStrategy(
            llm_config=LLMConfig(
                provider="openai/gpt-4o",  # LLM提供商
                api_token=os.getenv("OPENAI_API_KEY")
            ),
            schema=OpenAIModelFee.model_json_schema(),  # Pydantic模型schema
            extraction_type="schema",  # 提取类型
            instruction="""从爬取的内容中提取所有提到的模型名称及其输入输出token费用。
            不要遗漏内容中的任何模型。""",
            extra_args={
                "temperature": 0,      # 零温度确保结果一致性
                "top_p": 0.9,
                "max_tokens": 2000
            },
        ),
    )
    
    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun(
            url="https://openai.com/api/pricing/",
            config=crawler_config
        )
        
        if result and result.extracted_content:
            fees = json.loads(result.extracted_content)
            print(f"提取到 {len(fees)} 个模型定价信息")
            for fee in fees[:3]:
                print(f"模型: {fee.get('model_name')}")
                print(f"输入费用: {fee.get('input_fee')}")
                print(f"输出费用: {fee.get('output_fee')}")
                print("-" * 50)
            return fees
        return []


"""
3.4 使用DeepSeek进行LLM提取
---------------------------
使用DeepSeek模型进行结构化数据提取
"""


async def deepseek_llm_extraction_example():
    """使用DeepSeek进行LLM提取"""
    from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, LLMConfig, BrowserConfig, CacheMode
    from crawl4ai.extraction_strategy import LLMExtractionStrategy
    
    browser_config = BrowserConfig(headless=True)
    
    crawler_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        word_count_threshold=1,
        extraction_strategy=LLMExtractionStrategy(
            llm_config=LLMConfig(
                provider="deepseek/deepseek-chat",  # DeepSeek模型
                api_token=os.getenv("DEEPSEEK_API_KEY")
            ),
            schema=ProductInfo.model_json_schema(),
            instruction="提取页面上的产品信息，包括名称、价格、描述和评分",
            extra_args={"temperature": 0},
        ),
    )
    
    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun(
            url="https://example.com/product",
            config=crawler_config
        )
        
        if result and result.extracted_content:
            products = json.loads(result.extracted_content)
            return products
        return []


"""
3.5 LLM提取的不同输入格式
--------------------------
支持 markdown/html/fit_markdown 三种输入格式
"""


async def llm_input_format_examples():
    """LLM提取的不同输入格式示例"""
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode, LLMConfig
    from crawl4ai.extraction_strategy import LLMExtractionStrategy
    from crawl4ai.content_filter_strategy import PruningContentFilter
    from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
    
    browser_config = BrowserConfig(headless=True)
    
    # 1. 使用Markdown输入（默认）
    markdown_strategy = LLMExtractionStrategy(
        llm_config=LLMConfig(
            provider="openai/gpt-4o-mini",
            api_token=os.getenv("OPENAI_API_KEY")
        ),
        instruction="提取产品信息包括名称、价格和描述",
    )
    
    # 2. 使用HTML输入
    html_strategy = LLMExtractionStrategy(
        input_format="html",  # 指定输入格式为HTML
        llm_config=LLMConfig(
            provider="openai/gpt-4o-mini",
            api_token=os.getenv("OPENAI_API_KEY")
        ),
        instruction="从HTML中提取产品信息包括结构化数据",
    )
    
    # 3. 使用Fit Markdown输入（过滤后的Markdown）
    fit_markdown_strategy = LLMExtractionStrategy(
        input_format="fit_markdown",  # 指定输入格式为过滤后的Markdown
        llm_config=LLMConfig(
            provider="openai/gpt-4o-mini",
            api_token=os.getenv("OPENAI_API_KEY")
        ),
        instruction="从清理后的Markdown中提取产品信息",
    )
    
    # 配置使用fit_markdown的爬虫
    run_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        extraction_strategy=fit_markdown_strategy,
        markdown_generator=DefaultMarkdownGenerator(
            content_filter=PruningContentFilter()
        ),
    )
    
    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun(
            url="https://example.com/product",
            config=run_config
        )
        return result


# =============================================================================
# 第四部分：高级功能示例
# =============================================================================

"""
4.1 JavaScript执行（动态页面处理）
----------------------------------
执行自定义JavaScript代码处理动态页面
"""


async def javascript_execution_example():
    """JavaScript执行示例 - 点击按钮加载更多内容"""
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
    
    # 定义要执行的JavaScript代码
    js_code = """
    (async () => {
        // 点击所有"加载更多"按钮
        const loadMoreButtons = document.querySelectorAll('.load-more-btn');
        for (let btn of loadMoreButtons) {
            btn.click();
            await new Promise(r => setTimeout(r, 1000));  // 等待1秒
        }
        
        // 滚动到页面底部
        window.scrollTo(0, document.body.scrollHeight);
        await new Promise(r => setTimeout(r, 2000));  // 等待2秒加载内容
        
        // 返回页面信息
        return {
            scrollHeight: document.body.scrollHeight,
            loadedItems: document.querySelectorAll('.item').length
        };
    })();
    """
    
    # 同步JavaScript代码
    js_code_sync = """
        document.querySelector('#twotabsearchtextbox').value = 'laptop';
        document.querySelector('#nav-search-submit-button').click();
    """
    
    browser_config = BrowserConfig(headless=True)
    
    run_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        js_code=js_code,  # 执行JavaScript
        wait_for="css:.loaded-item",  # 等待加载完成的元素
        process_iframes=True,  # 处理iframe
    )
    
    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun(
            url="https://example.com/dynamic-page",
            config=run_config
        )
        print(f"页面内容长度: {len(result.markdown.raw_markdown)}")
        return result


"""
4.2 截图功能
------------
捕获网页截图
"""


async def screenshot_example():
    """截图示例"""
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
    import base64
    
    browser_config = BrowserConfig(headless=True)
    
    run_config = CrawlerRunConfig(
        screenshot=True,  # 启用截图
        screenshot_options={
            "full_page": True,    # 全页截图
            "type": "png",        # 图片格式: png/jpeg
            "quality": 90,        # 图片质量(0-100，仅JPEG)
            "omit_background": False,  # 是否透明背景
        },
    )
    
    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun(
            url="https://example.com",
            config=run_config
        )
        
        if result.screenshot:
            # 保存截图到文件
            screenshot_path = "screenshot.png"
            with open(screenshot_path, "wb") as f:
                f.write(base64.b64decode(result.screenshot))
            print(f"截图已保存到: {screenshot_path}")
        
        return result


"""
4.3 会话复用（保持登录状态）
----------------------------
使用session_id复用浏览器会话，保持登录状态
"""


async def session_reuse_example():
    """会话复用示例"""
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
    
    browser_config = BrowserConfig(headless=True)
    
    async with AsyncWebCrawler(config=browser_config) as crawler:
        # 第一步：登录（使用session_id）
        login_js = """
            document.querySelector('#username').value = 'your_username';
            document.querySelector('#password').value = 'your_password';
            document.querySelector('#login-btn').click();
        """
        
        login_config = CrawlerRunConfig(
            js_code=login_js,
            wait_for="css:.dashboard",  # 等待登录后的页面元素
        )
        
        login_result = await crawler.arun(
            url="https://example.com/login",
            config=login_config,
            session_id="my_session"  # 指定会话ID
        )
        
        print(f"登录成功: {login_result.success}")
        
        # 第二步：访问需要登录的页面（复用同一个session_id）
        dashboard_config = CrawlerRunConfig()
        
        dashboard_result = await crawler.arun(
            url="https://example.com/dashboard",
            config=dashboard_config,
            session_id="my_session"  # 复用相同的会话
        )
        
        print(f"Dashboard内容长度: {len(dashboard_result.markdown.raw_markdown)}")
        return dashboard_result


"""
4.4 代理设置
------------
配置代理服务器
"""


async def proxy_example():
    """代理设置示例"""
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
    
    # 方式1：在BrowserConfig中配置代理
    browser_config = BrowserConfig(
        headless=True,
        proxy_config={
            "server": "http://proxy.example.com:8080",
            "username": "proxy_user",
            "password": "proxy_pass"
        }
    )
    
    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun("https://example.com")
        return result


async def proxy_rotation_example():
    """代理轮换示例"""
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
    import random
    
    # 代理池
    proxies = [
        {"server": "http://proxy1.example.com:8080", "username": "user1", "password": "pass1"},
        {"server": "http://proxy2.example.com:8080", "username": "user2", "password": "pass2"},
        {"server": "http://proxy3.example.com:8080", "username": "user3", "password": "pass3"},
    ]
    
    urls = ["https://example.com/page1", "https://example.com/page2", "https://example.com/page3"]
    
    results = []
    for url in urls:
        # 随机选择代理
        proxy = random.choice(proxies)
        
        browser_config = BrowserConfig(
            headless=True,
            proxy_config=proxy
        )
        
        async with AsyncWebCrawler(config=browser_config) as crawler:
            result = await crawler.arun(url)
            results.append(result)
    
    return results


"""
4.5 Hooks自定义行为
-------------------
使用Hooks在爬虫的不同阶段执行自定义代码
"""


async def hooks_example():
    """Hooks示例"""
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
    from playwright.async_api import Page, BrowserContext
    
    browser_config = BrowserConfig(headless=True)
    
    run_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
    )
    
    crawler = AsyncWebCrawler(config=browser_config)
    
    # 定义Hook函数
    
    async def on_browser_created(browser, context: BrowserContext, **kwargs):
        """浏览器创建后调用"""
        print("[HOOK] 浏览器已创建")
        return browser
    
    async def on_page_context_created(page: Page, context: BrowserContext, **kwargs):
        """页面上下文创建后调用"""
        print("[HOOK] 页面上下文已创建")
        # 添加Cookie
        await context.add_cookies([
            {
                "name": "session_id",
                "value": "example_session",
                "domain": ".example.com",
                "path": "/",
            }
        ])
        # 设置视口大小
        await page.set_viewport_size({"width": 1080, "height": 800})
        return page
    
    async def before_goto(page: Page, context: BrowserContext, url: str, **kwargs):
        """导航前调用"""
        print(f"[HOOK] 即将访问: {url}")
        # 添加自定义请求头
        await page.set_extra_http_headers({"Custom-Header": "my-value"})
        return page
    
    async def after_goto(page: Page, context: BrowserContext, url: str, response: dict, **kwargs):
        """导航后调用"""
        print(f"[HOOK] 成功加载: {url}")
        # 等待特定元素
        try:
            await page.wait_for_selector(".content", timeout=1000)
            print("[HOOK] 内容元素已找到")
        except:
            print("[HOOK] 内容元素未找到")
        return page
    
    async def before_retrieve_html(page: Page, context: BrowserContext, **kwargs):
        """获取HTML前调用"""
        print("[HOOK] 即将获取HTML内容")
        # 滚动到页面底部触发懒加载
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
        return page
    
    # 设置Hooks
    crawler.crawler_strategy.set_hook("on_browser_created", on_browser_created)
    crawler.crawler_strategy.set_hook("on_page_context_created", on_page_context_created)
    crawler.crawler_strategy.set_hook("before_goto", before_goto)
    crawler.crawler_strategy.set_hook("after_goto", after_goto)
    crawler.crawler_strategy.set_hook("before_retrieve_html", before_retrieve_html)
    
    await crawler.start()
    
    result = await crawler.arun("https://example.com", config=run_config)
    print(f"爬取完成: {result.url}")
    
    await crawler.close()
    return result


# =============================================================================
# 第五部分：深度爬取示例
# =============================================================================

"""
5.1 基础深度爬取（BFS）
----------------------
使用广度优先搜索进行深度爬取
"""


async def basic_deep_crawl_example():
    """基础深度爬取示例 - BFS"""
    from crawl4ai import CrawlerRunConfig, AsyncWebCrawler, CacheMode
    from crawl4ai.content_scraping_strategy import LXMLWebScrapingStrategy
    from crawl4ai.deep_crawling import BFSDeepCrawlStrategy
    
    # 配置BFS深度爬取
    # max_depth=2: 初始页面(depth 0) + 2层深度
    # include_external=False: 只爬取同一域名下的页面
    config = CrawlerRunConfig(
        deep_crawl_strategy=BFSDeepCrawlStrategy(
            max_depth=2,
            include_external=False
        ),
        scraping_strategy=LXMLWebScrapingStrategy(),
        verbose=True,
    )
    
    async with AsyncWebCrawler() as crawler:
        results = await crawler.arun(
            url="https://docs.crawl4ai.com",
            config=config
        )
        
        # 按深度分组显示结果
        pages_by_depth = {}
        for result in results:
            depth = result.metadata.get("depth", 0)
            if depth not in pages_by_depth:
                pages_by_depth[depth] = []
            pages_by_depth[depth].append(result.url)
        
        print(f"共爬取 {len(results)} 个页面")
        for depth, urls in sorted(pages_by_depth.items()):
            print(f"深度 {depth}: {len(urls)} 个页面")
            for url in urls[:3]:
                print(f"  → {url}")
        
        return results


"""
5.2 深度优先搜索（DFS）
----------------------
使用深度优先搜索进行深度爬取
"""


async def dfs_deep_crawl_example():
    """DFS深度爬取示例"""
    from crawl4ai import CrawlerRunConfig, AsyncWebCrawler, CacheMode
    from crawl4ai.content_scraping_strategy import LXMLWebScrapingStrategy
    from crawl4ai.deep_crawling import DFSDeepCrawlStrategy
    
    config = CrawlerRunConfig(
        deep_crawl_strategy=DFSDeepCrawlStrategy(
            max_depth=3,
            include_external=False,
            max_pages=20  # 最多爬取20个页面
        ),
        scraping_strategy=LXMLWebScrapingStrategy(),
        verbose=True,
    )
    
    async with AsyncWebCrawler() as crawler:
        results = await crawler.arun(
            url="https://docs.crawl4ai.com",
            config=config
        )
        
        print(f"DFS共爬取 {len(results)} 个页面")
        return results


"""
5.3 最佳优先搜索（Best-First）
------------------------------
使用评分器优先爬取最相关的页面
"""


async def best_first_crawl_example():
    """最佳优先搜索示例"""
    from crawl4ai import CrawlerRunConfig, AsyncWebCrawler, CacheMode
    from crawl4ai.content_scraping_strategy import LXMLWebScrapingStrategy
    from crawl4ai.deep_crawling import BestFirstCrawlingStrategy
    from crawl4ai.deep_crawling.scorers import KeywordRelevanceScorer
    
    # 创建关键词相关性评分器
    keyword_scorer = KeywordRelevanceScorer(
        keywords=["crawl", "browser", "configuration", "async", "javascript"],
        weight=1.0
    )
    
    config = CrawlerRunConfig(
        deep_crawl_strategy=BestFirstCrawlingStrategy(
            max_depth=2,
            include_external=False,
            url_scorer=keyword_scorer,  # 使用评分器
            max_pages=10
        ),
        scraping_strategy=LXMLWebScrapingStrategy(),
        verbose=True,
    )
    
    async with AsyncWebCrawler() as crawler:
        results = await crawler.arun(
            url="https://docs.crawl4ai.com",
            config=config
        )
        
        print(f"最佳优先搜索共爬取 {len(results)} 个页面")
        for result in results:
            score = result.metadata.get("score", 0)
            print(f"评分: {score:.2f} | {result.url}")
        
        return results


"""
5.4 使用过滤器
--------------
使用过滤器筛选要爬取的页面
"""


async def filter_chain_example():
    """过滤器链示例"""
    from crawl4ai import CrawlerRunConfig, AsyncWebCrawler, CacheMode
    from crawl4ai.content_scraping_strategy import LXMLWebScrapingStrategy
    from crawl4ai.deep_crawling import BFSDeepCrawlStrategy
    from crawl4ai.deep_crawling.filters import (
        FilterChain,
        URLPatternFilter,
        DomainFilter,
        ContentTypeFilter,
        SEOFilter,
        ContentRelevanceFilter,
    )
    
    # 创建过滤器链
    filter_chain = FilterChain([
        # 域名过滤器
        DomainFilter(
            allowed_domains=["docs.crawl4ai.com"],
            blocked_domains=["old.docs.crawl4ai.com"]
        ),
        # URL模式过滤器
        URLPatternFilter(patterns=["*core*", "*advanced*", "*api*"]),
        # 内容类型过滤器
        ContentTypeFilter(allowed_types=["text/html"]),
    ])
    
    config = CrawlerRunConfig(
        deep_crawl_strategy=BFSDeepCrawlStrategy(
            max_depth=2,
            include_external=False,
            filter_chain=filter_chain
        ),
        scraping_strategy=LXMLWebScrapingStrategy(),
        verbose=True,
    )
    
    async with AsyncWebCrawler() as crawler:
        results = await crawler.arun(
            url="https://docs.crawl4ai.com",
            config=config
        )
        
        print(f"过滤后爬取 {len(results)} 个页面")
        return results


"""
5.5 流式深度爬取
----------------
使用流式处理实时获取爬取结果
"""


async def streaming_deep_crawl_example():
    """流式深度爬取示例"""
    from crawl4ai import CrawlerRunConfig, AsyncWebCrawler
    from crawl4ai.content_scraping_strategy import LXMLWebScrapingStrategy
    from crawl4ai.deep_crawling import BFSDeepCrawlStrategy
    
    config = CrawlerRunConfig(
        deep_crawl_strategy=BFSDeepCrawlStrategy(
            max_depth=2,
            include_external=False
        ),
        scraping_strategy=LXMLWebScrapingStrategy(),
        stream=True,  # 启用流式处理
        verbose=True,
    )
    
    async with AsyncWebCrawler() as crawler:
        results = []
        # 使用async for实时处理结果
        async for result in await crawler.arun(
            url="https://docs.crawl4ai.com",
            config=config
        ):
            results.append(result)
            depth = result.metadata.get("depth", 0)
            print(f"[实时] 深度 {depth}: {result.url}")
        
        print(f"流式爬取完成，共 {len(results)} 个页面")
        return results


# =============================================================================
# 第六部分：批量爬取与调度器
# =============================================================================

"""
6.1 基础批量爬取
----------------
使用arun_many批量爬取多个URL
"""


async def basic_batch_crawl_example():
    """基础批量爬取示例"""
    from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode
    
    urls = [
        "https://example.com",
        "https://www.python.org",
        "https://news.ycombinator.com",
    ]
    
    run_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        verbose=True
    )
    
    async with AsyncWebCrawler() as crawler:
        results = await crawler.arun_many(
            urls=urls,
            config=run_config
        )
        
        for url, result in zip(urls, results):
            status = "✅ 成功" if result.success else "❌ 失败"
            print(f"{status} | {url} | 内容长度: {len(result.markdown.raw_markdown)}")
        
        return results


"""
6.2 使用调度器进行高级批量爬取
------------------------------
使用MemoryAdaptiveDispatcher和SemaphoreDispatcher进行高级调度
"""


async def advanced_dispatcher_example():
    """高级调度器示例"""
    from crawl4ai import (
        AsyncWebCrawler,
        BrowserConfig,
        CrawlerRunConfig,
        MemoryAdaptiveDispatcher,
        SemaphoreDispatcher,
        RateLimiter,
        CrawlerMonitor,
        DisplayMode,
        CacheMode,
    )
    from crawl4ai.content_scraping_strategy import LXMLWebScrapingStrategy
    
    urls = [f"https://example.com/page{i}" for i in range(1, 20)]
    
    browser_config = BrowserConfig(headless=True, verbose=False)
    run_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        scraping_strategy=LXMLWebScrapingStrategy()
    )
    
    # 方式1：内存自适应调度器
    async def memory_adaptive_crawl():
        async with AsyncWebCrawler(config=browser_config) as crawler:
            dispatcher = MemoryAdaptiveDispatcher(
                memory_threshold_percent=70.0,  # 内存阈值
                max_session_permit=10,          # 最大会话数
                monitor=CrawlerMonitor(
                    max_visible_rows=15,
                    display_mode=DisplayMode.DETAILED
                ),
            )
            
            results = await crawler.arun_many(
                urls=urls,
                config=run_config,
                dispatcher=dispatcher
            )
            return results
    
    # 方式2：带速率限制的内存自适应调度器
    async def memory_adaptive_with_rate_limit():
        async with AsyncWebCrawler(config=browser_config) as crawler:
            dispatcher = MemoryAdaptiveDispatcher(
                memory_threshold_percent=95.0,
                max_session_permit=10,
                rate_limiter=RateLimiter(
                    base_delay=(1.0, 2.0),  # 基础延迟范围
                    max_delay=30.0,          # 最大延迟
                    max_retries=2            # 最大重试次数
                ),
                monitor=CrawlerMonitor(
                    max_visible_rows=15,
                    display_mode=DisplayMode.DETAILED
                ),
            )
            
            results = await crawler.arun_many(
                urls=urls,
                config=run_config,
                dispatcher=dispatcher
            )
            return results
    
    # 方式3：信号量调度器
    async def semaphore_crawl():
        async with AsyncWebCrawler(config=browser_config) as crawler:
            dispatcher = SemaphoreDispatcher(
                semaphore_count=5,  # 并发数
                monitor=CrawlerMonitor(
                    max_visible_rows=15,
                    display_mode=DisplayMode.DETAILED
                ),
            )
            
            results = await crawler.arun_many(
                urls=urls,
                config=run_config,
                dispatcher=dispatcher
            )
            return results
    
    # 执行批量爬取
    results = await memory_adaptive_crawl()
    print(f"批量爬取完成，共 {len(results)} 个结果")
    return results


"""
6.3 流式批量爬取
----------------
使用流式处理批量爬取结果
"""


async def streaming_batch_crawl_example():
    """流式批量爬取示例"""
    from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode
    
    urls = [f"https://example.com/page{i}" for i in range(1, 10)]
    
    run_config = CrawlerRunConfig(
        stream=True,  # 启用流式处理
        cache_mode=CacheMode.BYPASS,
    )
    
    async with AsyncWebCrawler() as crawler:
        count = 0
        async for result in await crawler.arun_many(
            urls=urls,
            config=run_config
        ):
            count += 1
            if result.success:
                print(f"✅ [{count}] {result.url}: {len(result.markdown.raw_markdown)} 字符")
            else:
                print(f"❌ [{count}] {result.url}: {result.error_message}")
        
        print(f"流式处理完成，共 {count} 个结果")


# =============================================================================
# 第七部分：实际应用场景示例
# =============================================================================

"""
7.1 新闻文章爬取
----------------
爬取新闻网站的文章内容
"""


async def news_crawl_example():
    """新闻文章爬取示例"""
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
    
    # 新闻文章URL列表
    article_urls = [
        "https://news.example.com/tech/article1",
        "https://news.example.com/tech/article2",
        "https://news.example.com/business/article3",
    ]
    
    # 浏览器配置
    browser_config = BrowserConfig(
        headless=True,
        viewport_width=1920,
        viewport_height=1080,
    )
    
    # 新闻爬取配置
    news_config = CrawlerRunConfig(
        # 内容处理
        css_selector="article .content",  # 只提取文章正文
        excluded_tags=["script", "style", "nav", "footer", "aside", "header"],
        excluded_selector=".ad-container, .recommendation, .comment-section",
        word_count_threshold=20,  # 忽略少于20个词的文本块
        remove_forms=True,
        prettiify=True,
        
        # 页面导航
        wait_until="networkidle",
        page_timeout=30000,
        check_robots_txt=True,
        
        # 缓存
        cache_mode=CacheMode.ENABLED,
        
        # 链接处理
        exclude_external_links=True,
        exclude_all_images=False,
        
        # 礼貌爬取
        mean_delay=1.5,
        max_range=1.0,
        semaphore_count=3,
    )
    
    async with AsyncWebCrawler(config=browser_config) as crawler:
        results = await crawler.arun_many(
            urls=article_urls,
            config=news_config
        )
        
        articles = []
        for url, result in zip(article_urls, results):
            if result.success:
                articles.append({
                    'url': url,
                    'title': result.metadata.get('title', 'N/A'),
                    'content': result.markdown.raw_markdown,
                    'word_count': len(result.markdown.raw_markdown.split()),
                })
                print(f"✅ 成功: {result.metadata.get('title', 'N/A')[:50]}...")
        
        print(f"\n共爬取 {len(articles)} 篇文章")
        return articles


"""
7.2 电商产品信息提取
--------------------
提取电商网站的产品信息
"""


async def ecommerce_extraction_example():
    """电商产品信息提取示例"""
    from crawl4ai import AsyncWebCrawler, CacheMode, JsonCssExtractionStrategy
    from crawl4ai.async_configs import BrowserConfig, CrawlerRunConfig
    
    # 定义产品信息提取模式
    product_schema = {
        "name": "Product Details",
        "baseSelector": ".product-detail",
        "fields": [
            {"name": "name", "selector": "h1.product-name", "type": "text"},
            {"name": "price", "selector": ".price-current", "type": "text"},
            {"name": "original_price", "selector": ".price-original", "type": "text"},
            {"name": "discount", "selector": ".discount-badge", "type": "text"},
            {"name": "rating", "selector": ".rating-value", "type": "text"},
            {"name": "review_count", "selector": ".review-count", "type": "text"},
            {"name": "description", "selector": ".product-description", "type": "text"},
            {"name": "availability", "selector": ".stock-status", "type": "text"},
            {
                "name": "images",
                "selector": ".product-image img",
                "type": "attribute",
                "attribute": "src",
                "multiple": True
            },
            {
                "name": "specifications",
                "selector": ".spec-table tr",
                "type": "text",
                "multiple": True
            },
        ],
    }
    
    browser_config = BrowserConfig(headless=True)
    
    crawler_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        extraction_strategy=JsonCssExtractionStrategy(schema=product_schema),
        wait_for="css:.product-detail",  # 等待产品详情加载
    )
    
    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun(
            url="https://example.com/product/123",
            config=crawler_config
        )
        
        if result and result.extracted_content:
            product = json.loads(result.extracted_content)
            print(f"产品名称: {product.get('name')}")
            print(f"当前价格: {product.get('price')}")
            print(f"原价: {product.get('original_price')}")
            print(f"评分: {product.get('rating')} ({product.get('review_count')} 评论)")
            return product
        return {}


"""
7.3 使用LLM进行智能内容分析
---------------------------
使用LLM对网页内容进行智能分析
"""


async def llm_content_analysis_example():
    """LLM智能内容分析示例"""
    from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, LLMConfig, BrowserConfig, CacheMode
    from crawl4ai.extraction_strategy import LLMExtractionStrategy
    
    # 定义分析结果模型
    class ContentAnalysis(BaseModel):
        summary: str = Field(..., description="文章摘要")
        key_points: List[str] = Field(..., description="关键要点列表")
        sentiment: str = Field(..., description="情感倾向: positive/negative/neutral")
        topics: List[str] = Field(..., description="文章主题标签")
        reading_time: int = Field(..., description="预计阅读时间（分钟）")
    
    browser_config = BrowserConfig(headless=True)
    
    crawler_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        extraction_strategy=LLMExtractionStrategy(
            llm_config=LLMConfig(
                provider="openai/gpt-4o",
                api_token=os.getenv("OPENAI_API_KEY")
            ),
            schema=ContentAnalysis.model_json_schema(),
            instruction="""分析这篇文章并提供：
            1. 一段简洁的摘要
            2. 5-7个关键要点
            3. 情感倾向（positive/negative/neutral）
            4. 相关主题标签
            5. 预计阅读时间（分钟）""",
            extra_args={"temperature": 0.3},
        ),
    )
    
    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun(
            url="https://example.com/article",
            config=crawler_config
        )
        
        if result and result.extracted_content:
            analysis = json.loads(result.extracted_content)
            print("文章分析结果:")
            print(f"摘要: {analysis.get('summary')}")
            print(f"情感: {analysis.get('sentiment')}")
            print(f"主题: {', '.join(analysis.get('topics', []))}")
            print(f"预计阅读时间: {analysis.get('reading_time')} 分钟")
            return analysis
        return {}


"""
7.4 表格数据提取
----------------
提取网页中的表格数据
"""


async def table_extraction_example():
    """表格数据提取示例"""
    from crawl4ai import AsyncWebCrawler, LLMConfig, CrawlerRunConfig, BrowserConfig, CacheMode
    from crawl4ai.extraction_strategy import LLMExtractionStrategy
    
    browser_config = BrowserConfig(headless=True)
    
    # 使用LLM提取表格数据
    crawler_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        extraction_strategy=LLMExtractionStrategy(
            llm_config=LLMConfig(
                provider="openai/gpt-4o",
                api_token=os.getenv("OPENAI_API_KEY")
            ),
            instruction="""提取页面中的所有表格数据，返回JSON格式：
            {
                "tables": [
                    {
                        "title": "表格标题",
                        "headers": ["列1", "列2", ...],
                        "rows": [["数据1", "数据2", ...], ...]
                    }
                ]
            }""",
            extra_args={"temperature": 0},
        ),
    )
    
    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun(
            url="https://example.com/data-table",
            config=crawler_config
        )
        
        if result and result.extracted_content:
            tables = json.loads(result.extracted_content)
            print(f"提取到 {len(tables.get('tables', []))} 个表格")
            return tables
        return {}


"""
7.5 RAG系统文档收集
-------------------
为RAG系统收集和处理文档
"""


async def rag_document_collection_example():
    """RAG文档收集示例"""
    from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode
    from crawl4ai.content_filter_strategy import PruningContentFilter
    from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
    
    # 文档URL列表
    doc_urls = [
        "https://docs.example.com/intro",
        "https://docs.example.com/installation",
        "https://docs.example.com/configuration",
        "https://docs.example.com/api",
    ]
    
    # 配置优化用于RAG的Markdown生成
    run_config = CrawlerRunConfig(
        cache_mode=CacheMode.ENABLED,
        word_count_threshold=50,  # 过滤短文本
        exclude_external_links=True,
        remove_overlay_elements=True,
        markdown_generator=DefaultMarkdownGenerator(
            content_filter=PruningContentFilter(
                threshold=0.4,
                threshold_type="fixed"
            )
        ),
    )
    
    async with AsyncWebCrawler() as crawler:
        results = await crawler.arun_many(
            urls=doc_urls,
            config=run_config
        )
        
        documents = []
        for url, result in zip(doc_urls, results):
            if result.success:
                doc = {
                    'url': url,
                    'title': result.metadata.get('title', ''),
                    'content': result.markdown.fit_markdown,  # 使用过滤后的内容
                    'raw_content': result.markdown.raw_markdown,
                    'links': result.links,
                }
                documents.append(doc)
                print(f"✅ 已处理: {doc['title']}")
        
        # 保存到文件
        for doc in documents:
            filename = f"docs/{doc['title'].replace(' ', '_')}.md"
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(doc['content'])
        
        print(f"\n共收集 {len(documents)} 个文档")
        return documents


# =============================================================================
# 主函数：运行所有示例
# =============================================================================

async def main():
    """主函数 - 运行示例"""
    print("=" * 60)
    print("Crawl4AI 使用场景代码示例")
    print("=" * 60)
    
    # 运行基础示例
    print("\n1. 基础爬取示例")
    print("-" * 40)
    # await basic_crawl_example()
    
    # 运行Markdown生成示例
    print("\n2. Markdown生成示例")
    print("-" * 40)
    # await markdown_generation_example()
    
    print("\n" + "=" * 60)
    print("示例运行完成！")
    print("=" * 60)
    print("\n提示: 取消注释main()函数中的await语句来运行特定示例")


if __name__ == "__main__":
    asyncio.run(main())
