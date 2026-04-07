#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Crawl4AI 实际应用场景示例
=======================
本文件展示 Crawl4AI 在实际项目中的应用场景

应用场景：
1. 电商价格监控
2. 新闻聚合
3. 学术论文爬取
4. 社交媒体监控
5. SEO分析
6. 竞品分析
7. 内容审核
8. 数据标注
"""

import asyncio
import json
import os
from datetime import datetime
from typing import List, Dict, Optional
from pydantic import BaseModel, Field


# =============================================================================
# 场景1：电商价格监控
# =============================================================================

class ProductPrice(BaseModel):
    """产品价格信息"""
    product_id: str = Field(..., description="产品ID")
    name: str = Field(..., description="产品名称")
    current_price: float = Field(..., description="当前价格")
    original_price: Optional[float] = Field(None, description="原价")
    currency: str = Field(default="CNY", description="货币")
    availability: str = Field(..., description="库存状态")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


async def ecommerce_price_monitor():
    """
    电商价格监控系统
    
    功能：
    - 定期爬取产品价格
    - 检测价格变化
    - 生成价格历史记录
    """
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
    from crawl4ai import JsonCssExtractionStrategy, LLMExtractionStrategy, LLMConfig
    
    # 要监控的产品列表
    products_to_monitor = [
        {"url": "https://example.com/product/1", "product_id": "P001"},
        {"url": "https://example.com/product/2", "product_id": "P002"},
    ]
    
    # CSS提取模式
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
        enable_stealth=True,  # 启用反检测
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
                    
                    # 解析价格
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
                    
                    # 检测价格变化（与历史记录比较）
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


# =============================================================================
# 场景2：新闻聚合系统
# =============================================================================

class NewsArticle(BaseModel):
    """新闻文章"""
    title: str = Field(..., description="标题")
    content: str = Field(..., description="正文内容")
    author: Optional[str] = Field(None, description="作者")
    publish_date: Optional[str] = Field(None, description="发布日期")
    source: str = Field(..., description="来源")
    url: str = Field(..., description="原文链接")
    summary: Optional[str] = Field(None, description="摘要")


async def news_aggregator():
    """
    新闻聚合系统
    
    功能：
    - 从多个新闻源爬取文章
    - 提取结构化内容
    - 生成摘要
    - 去重处理
    """
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
    from crawl4ai.content_filter_strategy import PruningContentFilter
    from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
    from crawl4ai import LLMExtractionStrategy, LLMConfig
    
    # 新闻源列表
    news_sources = [
        {"name": "TechNews", "url": "https://technews.example.com/article/1"},
        {"name": "ScienceDaily", "url": "https://sciencedaily.example.com/article/2"},
    ]
    
    # 配置优化用于新闻爬取
    browser_config = BrowserConfig(headless=True)
    
    # 用于内容提取的配置
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
    
    # 用于摘要生成的LLM配置
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
                # 第一步：爬取文章内容
                result = await crawler.arun(source["url"], config=content_config)
                
                if result.success:
                    # 第二步：使用LLM生成摘要
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


# =============================================================================
# 场景3：学术论文爬取
# =============================================================================

class ResearchPaper(BaseModel):
    """学术论文"""
    title: str = Field(..., description="论文标题")
    authors: List[str] = Field(..., description="作者列表")
    abstract: str = Field(..., description="摘要")
    keywords: List[str] = Field(..., description="关键词")
    publication_date: Optional[str] = Field(None, description="发表日期")
    doi: Optional[str] = Field(None, description="DOI")
    url: str = Field(..., description="论文链接")


async def academic_paper_collector():
    """
    学术论文收集系统
    
    功能：
    - 从学术网站爬取论文信息
    - 提取元数据（标题、作者、摘要等）
    - 结构化存储
    """
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
    from crawl4ai import LLMExtractionStrategy, LLMConfig
    
    # 论文页面URL列表
    paper_urls = [
        "https://arxiv.org/abs/2401.12345",
        "https://papers.example.com/paper/2",
    ]
    
    browser_config = BrowserConfig(headless=True)
    
    # 使用LLM提取论文信息
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


# =============================================================================
# 场景4：SEO分析工具
# =============================================================================

class SEOAnalysis(BaseModel):
    """SEO分析结果"""
    url: str = Field(..., description="分析URL")
    title: str = Field(..., description="页面标题")
    meta_description: Optional[str] = Field(None, description="Meta描述")
    headings: Dict[str, List[str]] = Field(default_factory=dict, description="标题结构")
    word_count: int = Field(0, description="字数")
    internal_links: int = Field(0, description="内部链接数")
    external_links: int = Field(0, description="外部链接数")
    images_without_alt: int = Field(0, description="无alt属性的图片数")
    has_canonical: bool = Field(False, description="是否有canonical标签")
    has_sitemap: bool = Field(False, description="是否有sitemap链接")


async def seo_analyzer():
    """
    SEO分析工具
    
    功能：
    - 分析页面SEO元素
    - 检查标题、描述、链接等
    - 生成SEO报告
    """
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
    from crawl4ai import JsonCssExtractionStrategy
    
    urls_to_analyze = [
        "https://example.com",
        "https://example.com/about",
    ]
    
    # CSS提取SEO元素
    seo_schema = {
        "baseSelector": "html",
        "fields": [
            {"name": "title", "selector": "title", "type": "text"},
            {"name": "meta_description", "selector": "meta[name='description']", "type": "attribute", "attribute": "content"},
            {"name": "canonical", "selector": "link[rel='canonical']", "type": "attribute", "attribute": "href"},
            {"name": "h1_count", "selector": "h1", "type": "text", "multiple": True},
            {"name": "h2_count", "selector": "h2", "type": "text", "multiple": True},
            {"name": "images", "selector": "img", "type": "text", "multiple": True},
            {"name": "internal_links", "selector": "a[href^='/']", "type": "text", "multiple": True},
            {"name": "external_links", "selector": "a[href^='http']", "type": "text", "multiple": True},
        ],
    }
    
    browser_config = BrowserConfig(headless=True)
    
    run_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        extraction_strategy=JsonCssExtractionStrategy(schema=seo_schema),
    )
    
    seo_reports = []
    
    async with AsyncWebCrawler(config=browser_config) as crawler:
        for url in urls_to_analyze:
            try:
                result = await crawler.arun(url, config=run_config)
                
                if result and result.extracted_content:
                    data = json.loads(result.extracted_content)
                    
                    # 统计图片alt属性
                    images_without_alt = 0
                    # 这里可以进一步分析HTML来检查alt属性
                    
                    report = SEOAnalysis(
                        url=url,
                        title=data.get("title", ""),
                        meta_description=data.get("meta_description"),
                        headings={
                            "h1": data.get("h1_count", []),
                            "h2": data.get("h2_count", []),
                        },
                        word_count=len(result.markdown.raw_markdown.split()),
                        internal_links=len(data.get("internal_links", [])),
                        external_links=len(data.get("external_links", [])),
                        images_without_alt=images_without_alt,
                        has_canonical=bool(data.get("canonical")),
                    )
                    
                    seo_reports.append(report)
                    
                    # 打印SEO报告
                    print(f"\nSEO分析: {url}")
                    print(f"标题: {report.title}")
                    print(f"Meta描述: {report.meta_description[:100] if report.meta_description else '无'}...")
                    print(f"H1数量: {len(report.headings.get('h1', []))}")
                    print(f"H2数量: {len(report.headings.get('h2', []))}")
                    print(f"内部链接: {report.internal_links}")
                    print(f"外部链接: {report.external_links}")
                    print(f"字数: {report.word_count}")
                    
            except Exception as e:
                print(f"❌ SEO分析失败 {url}: {e}")
    
    # 保存SEO报告
    with open("seo_report.json", "w", encoding="utf-8") as f:
        json.dump([r.model_dump() for r in seo_reports], f, ensure_ascii=False, indent=2)
    
    return seo_reports


# =============================================================================
# 场景5：竞品分析
# =============================================================================

class CompetitorFeature(BaseModel):
    """竞品功能"""
    name: str = Field(..., description="功能名称")
    description: str = Field(..., description="功能描述")
    pricing: Optional[str] = Field(None, description="定价信息")


class CompetitorAnalysis(BaseModel):
    """竞品分析"""
    company_name: str = Field(..., description="公司名称")
    website: str = Field(..., description="网站")
    tagline: Optional[str] = Field(None, description="标语")
    key_features: List[CompetitorFeature] = Field(default_factory=list, description="核心功能")
    pricing_tiers: List[Dict] = Field(default_factory=list, description="定价层级")
    target_audience: Optional[str] = Field(None, description="目标用户")


async def competitor_analysis():
    """
    竞品分析系统
    
    功能：
    - 分析竞争对手网站
    - 提取产品功能和定价
    - 生成竞品对比报告
    """
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
    from crawl4ai import LLMExtractionStrategy, LLMConfig
    
    competitors = [
        {"name": "Competitor A", "url": "https://competitor-a.example.com"},
        {"name": "Competitor B", "url": "https://competitor-b.example.com"},
    ]
    
    browser_config = BrowserConfig(headless=True)
    
    run_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        extraction_strategy=LLMExtractionStrategy(
            llm_config=LLMConfig(
                provider="openai/gpt-4o",
                api_token=os.getenv("OPENAI_API_KEY")
            ),
            schema=CompetitorAnalysis.model_json_schema(),
            instruction="""分析这个竞争对手网站，提取以下信息：
            1. 公司名称
            2. 标语/口号
            3. 核心功能列表（每个功能包含名称和描述）
            4. 定价信息（如果有）
            5. 目标用户群体
            尽可能详细地提取信息。""",
            extra_args={"temperature": 0.3},
        ),
    )
    
    analyses = []
    
    async with AsyncWebCrawler(config=browser_config) as crawler:
        for competitor in competitors:
            try:
                result = await crawler.arun(competitor["url"], config=run_config)
                
                if result and result.extracted_content:
                    data = json.loads(result.extracted_content)
                    analysis = CompetitorAnalysis(
                        company_name=data.get("company_name", competitor["name"]),
                        website=competitor["url"],
                        tagline=data.get("tagline"),
                        key_features=[CompetitorFeature(**f) for f in data.get("key_features", [])],
                        pricing_tiers=data.get("pricing_tiers", []),
                        target_audience=data.get("target_audience"),
                    )
                    
                    analyses.append(analysis)
                    print(f"✅ 已分析: {analysis.company_name}")
                    print(f"   核心功能: {len(analysis.key_features)} 个")
                    
            except Exception as e:
                print(f"❌ 竞品分析失败 {competitor['url']}: {e}")
    
    # 保存竞品分析
    with open("competitor_analysis.json", "w", encoding="utf-8") as f:
        json.dump([a.model_dump() for a in analyses], f, ensure_ascii=False, indent=2)
    
    return analyses


# =============================================================================
# 场景6：内容审核系统
# =============================================================================

class ContentReview(BaseModel):
    """内容审核结果"""
    url: str = Field(..., description="内容URL")
    is_appropriate: bool = Field(..., description="是否合适")
    categories: List[str] = Field(default_factory=list, description="内容分类")
    risk_level: str = Field(..., description="风险等级: low/medium/high")
    issues: List[str] = Field(default_factory=list, description="发现的问题")
    recommendation: str = Field(..., description="处理建议")


async def content_moderation():
    """
    内容审核系统
    
    功能：
    - 自动审核网页内容
    - 检测不当内容
    - 生成审核报告
    """
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
    from crawl4ai import LLMExtractionStrategy, LLMConfig
    from crawl4ai.content_filter_strategy import PruningContentFilter
    from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
    
    urls_to_review = [
        "https://user-content.example.com/post/1",
        "https://user-content.example.com/post/2",
    ]
    
    browser_config = BrowserConfig(headless=True)
    
    # 先爬取内容
    crawl_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        word_count_threshold=10,
        markdown_generator=DefaultMarkdownGenerator(
            content_filter=PruningContentFilter(threshold=0.3)
        ),
    )
    
    # 审核配置
    review_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        extraction_strategy=LLMExtractionStrategy(
            llm_config=LLMConfig(
                provider="openai/gpt-4o",
                api_token=os.getenv("OPENAI_API_KEY")
            ),
            schema=ContentReview.model_json_schema(),
            instruction="""审核以下内容，判断其是否适合公开显示：
            1. 是否包含不当内容（暴力、色情、仇恨言论等）
            2. 内容分类
            3. 风险等级（low/medium/high）
            4. 发现的具体问题
            5. 处理建议（approve/reject/review）
            请客观公正地进行审核。""",
            extra_args={"temperature": 0},
        ),
    )
    
    reviews = []
    
    async with AsyncWebCrawler(config=browser_config) as crawler:
        for url in urls_to_review:
            try:
                # 爬取内容
                crawl_result = await crawler.arun(url, config=crawl_config)
                
                if crawl_result.success:
                    # 使用LLM审核内容
                    review_result = await crawler.arun(url, config=review_config)
                    
                    if review_result and review_result.extracted_content:
                        review_data = json.loads(review_result.extracted_content)
                        review = ContentReview(
                            url=url,
                            is_appropriate=review_data.get("is_appropriate", True),
                            categories=review_data.get("categories", []),
                            risk_level=review_data.get("risk_level", "low"),
                            issues=review_data.get("issues", []),
                            recommendation=review_data.get("recommendation", "approve"),
                        )
                        
                        reviews.append(review)
                        
                        status = "✅ 通过" if review.is_appropriate else "❌ 拒绝"
                        print(f"{status} | {url}")
                        print(f"   风险等级: {review.risk_level}")
                        if review.issues:
                            print(f"   问题: {', '.join(review.issues)}")
                            
            except Exception as e:
                print(f"❌ 审核失败 {url}: {e}")
    
    # 保存审核报告
    with open("content_reviews.json", "w", encoding="utf-8") as f:
        json.dump([r.model_dump() for r in reviews], f, ensure_ascii=False, indent=2)
    
    return reviews


# =============================================================================
# 场景7：RAG文档处理
# =============================================================================

async def rag_document_processor():
    """
    RAG（检索增强生成）文档处理系统
    
    功能：
    - 批量爬取文档
    - 内容分块
    - 元数据提取
    - 为向量数据库准备数据
    """
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
    from crawl4ai import MemoryAdaptiveDispatcher, RateLimiter, CrawlerMonitor, DisplayMode
    from crawl4ai.content_filter_strategy import PruningContentFilter
    from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
    
    # 文档URL列表
    doc_urls = [
        "https://docs.crawl4ai.com/",
        "https://docs.crawl4ai.com/core/quickstart/",
        "https://docs.crawl4ai.com/core/browser-crawler-config/",
        "https://docs.crawl4ai.com/core/markdown-generation/",
    ]
    
    browser_config = BrowserConfig(headless=True)
    
    # 优化用于RAG的爬取配置
    run_config = CrawlerRunConfig(
        cache_mode=CacheMode.ENABLED,
        word_count_threshold=50,
        excluded_tags=["nav", "footer", "aside", "header", "script", "style"],
        exclude_external_links=True,
        remove_overlay_elements=True,
        wait_until="networkidle",
        markdown_generator=DefaultMarkdownGenerator(
            content_filter=PruningContentFilter(
                threshold=0.4,
                threshold_type="fixed"
            )
        ),
    )
    
    # 使用调度器进行批量处理
    dispatcher = MemoryAdaptiveDispatcher(
        memory_threshold_percent=80.0,
        max_session_permit=5,
        rate_limiter=RateLimiter(base_delay=(1.0, 2.0)),
        monitor=CrawlerMonitor(display_mode=DisplayMode.SIMPLE),
    )
    
    documents = []
    
    async with AsyncWebCrawler(config=browser_config) as crawler:
        results = await crawler.arun_many(
            urls=doc_urls,
            config=run_config,
            dispatcher=dispatcher
        )
        
        for url, result in zip(doc_urls, results):
            if result.success:
                doc = {
                    "id": url.replace("https://", "").replace("/", "_"),
                    "url": url,
                    "title": result.metadata.get("title", ""),
                    "description": result.metadata.get("description", ""),
                    "content": result.markdown.fit_markdown,
                    "word_count": len(result.markdown.fit_markdown.split()),
                    "timestamp": datetime.now().isoformat(),
                }
                
                documents.append(doc)
                print(f"✅ 已处理: {doc['title'][:50]}... ({doc['word_count']} 词)")
    
    # 保存处理后的文档
    with open("rag_documents.json", "w", encoding="utf-8") as f:
        json.dump(documents, f, ensure_ascii=False, indent=2)
    
    # 生成Markdown文件供进一步处理
    os.makedirs("rag_docs", exist_ok=True)
    for doc in documents:
        filename = f"rag_docs/{doc['id']}.md"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(f"# {doc['title']}\n\n")
            f.write(f"Source: {doc['url']}\n\n")
            f.write(doc['content'])
    
    print(f"\n共处理 {len(documents)} 个文档")
    print(f"文档已保存到 rag_docs/ 目录")
    
    return documents


# =============================================================================
# 场景8：网站监控
# =============================================================================

class WebsiteChange(BaseModel):
    """网站变更"""
    url: str = Field(..., description="监控URL")
    change_type: str = Field(..., description="变更类型: content/structure/availability")
    severity: str = Field(..., description="严重程度: low/medium/high")
    description: str = Field(..., description="变更描述")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


async def website_monitor():
    """
    网站监控系统
    
    功能：
    - 定期监控网站变化
    - 检测内容变更
    - 发送变更通知
    """
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
    import hashlib
    
    # 监控目标
    monitors = [
        {"url": "https://example.com", "name": "首页"},
        {"url": "https://example.com/pricing", "name": "定价页"},
    ]
    
    # 存储文件
    STATE_FILE = "website_monitor_state.json"
    
    # 加载之前的状态
    previous_states = {}
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            previous_states = json.load(f)
    
    browser_config = BrowserConfig(headless=True)
    
    run_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        word_count_threshold=10,
    )
    
    changes = []
    current_states = {}
    
    async with AsyncWebCrawler(config=browser_config) as crawler:
        for monitor in monitors:
            url = monitor["url"]
            
            try:
                result = await crawler.arun(url, config=run_config)
                
                if result.success:
                    # 计算内容哈希
                    content_hash = hashlib.md5(
                        result.markdown.raw_markdown.encode()
                    ).hexdigest()
                    
                    current_states[url] = {
                        "hash": content_hash,
                        "title": result.metadata.get("title", ""),
                        "timestamp": datetime.now().isoformat(),
                    }
                    
                    # 检查是否有变化
                    if url in previous_states:
                        if previous_states[url]["hash"] != content_hash:
                            change = WebsiteChange(
                                url=url,
                                change_type="content",
                                severity="medium",
                                description=f"页面内容发生变化: {monitor['name']}",
                            )
                            changes.append(change)
                            print(f"🔄 检测到变更: {monitor['name']}")
                    else:
                        print(f"📝 首次监控: {monitor['name']}")
                        
                else:
                    # 网站不可用
                    change = WebsiteChange(
                        url=url,
                        change_type="availability",
                        severity="high",
                        description=f"网站不可用: {result.error_message}",
                    )
                    changes.append(change)
                    print(f"❌ 网站不可用: {monitor['name']}")
                    
            except Exception as e:
                print(f"❌ 监控失败 {url}: {e}")
    
    # 保存当前状态
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(current_states, f, ensure_ascii=False, indent=2)
    
    # 保存变更记录
    if changes:
        with open("website_changes.json", "w", encoding="utf-8") as f:
            json.dump([c.model_dump() for c in changes], f, ensure_ascii=False, indent=2)
        print(f"\n共检测到 {len(changes)} 处变更")
    else:
        print("\n未检测到变更")
    
    return changes


# =============================================================================
# 主函数
# =============================================================================

async def main():
    """运行所有实际应用场景示例"""
    print("=" * 60)
    print("Crawl4AI 实际应用场景示例")
    print("=" * 60)
    
    # 选择要运行的场景（取消注释以运行）
    
    # print("\n1. 电商价格监控")
    # await ecommerce_price_monitor()
    
    # print("\n2. 新闻聚合系统")
    # await news_aggregator()
    
    # print("\n3. 学术论文收集")
    # await academic_paper_collector()
    
    # print("\n4. SEO分析")
    # await seo_analyzer()
    
    # print("\n5. 竞品分析")
    # await competitor_analysis()
    
    # print("\n6. 内容审核")
    # await content_moderation()
    
    # print("\n7. RAG文档处理")
    # await rag_document_processor()
    
    # print("\n8. 网站监控")
    # await website_monitor()
    
    print("\n" + "=" * 60)
    print("请取消注释main()函数中的代码来运行特定场景")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
