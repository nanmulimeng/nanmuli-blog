# Crawl4AI 使用场景代码示例大全

> 基于 Crawl4AI v0.7.x+ 版本的完整代码示例集合

## 📁 文件说明

本目录包含以下文件：

| 文件名 | 说明 | 大小 |
|--------|------|------|
| `crawl4ai_examples.py` | 完整的代码示例集合（基础用法、配置、提取策略、高级功能） | ~1500行 |
| `crawl4ai_config_guide.md` | 详细的配置参数说明文档 | ~600行 |
| `crawl4ai_quick_reference.md` | 快速参考卡片（常用代码片段速查） | ~400行 |
| `crawl4ai_real_world_examples.py` | 实际应用场景示例（电商、新闻、学术、SEO等） | ~900行 |

---

## 🚀 快速开始

### 安装 Crawl4AI

```bash
# 使用 pip
pip install -U crawl4ai
crawl4ai-setup  # 安装 Playwright 浏览器

# 使用 uv (推荐)
uv pip install crawl4ai
uv run crawl4ai-setup
```

### 验证安装

```bash
crawl4ai-doctor
```

---

## 📖 内容概览

### 1. 基础使用示例 (`crawl4ai_examples.py`)

包含以下章节：

- **第一部分：基础使用示例**
  - 最简单的爬取
  - Markdown生成（带内容过滤）
  - BM25内容过滤

- **第二部分：配置示例**
  - BrowserConfig 详细配置
  - CrawlerRunConfig 详细配置
  - 缓存模式说明

- **第三部分：提取策略示例**
  - CSS选择器提取 (JsonCssExtractionStrategy)
  - XPath选择器提取 (JsonXPathExtractionStrategy)
  - LLM提取策略 (LLMExtractionStrategy)
  - DeepSeek LLM提取
  - 不同输入格式（markdown/html/fit_markdown）

- **第四部分：高级功能示例**
  - JavaScript执行（动态页面处理）
  - 截图功能
  - 会话复用（保持登录状态）
  - 代理设置
  - Hooks自定义行为

- **第五部分：深度爬取示例**
  - BFS深度爬取
  - DFS深度爬取
  - 最佳优先搜索
  - 过滤器链
  - 流式深度爬取

- **第六部分：批量爬取与调度器**
  - 基础批量爬取
  - 高级调度器（MemoryAdaptiveDispatcher/SemaphoreDispatcher）
  - 流式批量爬取

- **第七部分：实际应用场景**
  - 新闻文章爬取
  - 电商产品信息提取
  - LLM智能内容分析
  - 表格数据提取
  - RAG文档收集

### 2. 配置指南 (`crawl4ai_config_guide.md`)

详细说明：

- BrowserConfig 所有参数
- CrawlerRunConfig 所有参数
- 缓存模式详解
- 提取策略配置
- 深度爬取策略
- 调度器配置
- Markdown生成器配置
- 完整配置示例

### 3. 快速参考卡片 (`crawl4ai_quick_reference.md`)

常用代码片段速查：

- 基础爬取
- Markdown生成
- 批量爬取
- CSS/XPath提取
- LLM提取
- JavaScript执行
- 截图功能
- 会话复用
- 代理设置
- 深度爬取
- 调度器配置
- 反检测配置
- 结果对象属性

### 4. 实际应用场景 (`crawl4ai_real_world_examples.py`)

包含8个实际应用场景：

1. **电商价格监控** - 定期监控产品价格变化
2. **新闻聚合系统** - 从多个新闻源聚合内容
3. **学术论文收集** - 爬取学术论文元数据
4. **SEO分析工具** - 分析页面SEO元素
5. **竞品分析** - 分析竞争对手网站
6. **内容审核系统** - 自动审核用户内容
7. **RAG文档处理** - 为RAG系统准备文档
8. **网站监控** - 监控网站变化

---

## 💡 使用建议

### 新手入门

1. 先阅读 `crawl4ai_quick_reference.md` 了解常用代码片段
2. 运行 `crawl4ai_examples.py` 中的基础示例
3. 参考 `crawl4ai_config_guide.md` 了解配置参数

### 进阶使用

1. 深入学习 `crawl4ai_examples.py` 中的高级功能
2. 参考 `crawl4ai_real_world_examples.py` 的实际应用场景
3. 根据需求组合不同的配置和策略

### 生产环境

1. 使用调度器控制并发
2. 配置代理池避免被封
3. 启用缓存减少重复爬取
4. 使用流式处理大数据量
5. 添加错误处理和重试机制

---

## 🔧 常见问题

### Q: 如何处理动态加载的页面？

```python
run_config = CrawlerRunConfig(
    js_code="window.scrollTo(0, document.body.scrollHeight);",
    wait_for="css:.loaded-content",
    delay_before_return_html=2.0,
)
```

### Q: 如何绕过反爬机制？

```python
browser_config = BrowserConfig(
    headless=True,
    enable_stealth=True,  # 启用stealth模式
    # 或使用undetected浏览器
    browser_type="undetected",
)
```

### Q: 如何保持登录状态？

```python
# 第一次登录
await crawler.arun(url="https://example.com/login", session_id="my_session")

# 复用会话
await crawler.arun(url="https://example.com/dashboard", session_id="my_session")
```

### Q: 如何批量爬取大量URL？

```python
from crawl4ai import MemoryAdaptiveDispatcher, RateLimiter

dispatcher = MemoryAdaptiveDispatcher(
    memory_threshold_percent=70.0,
    max_session_permit=10,
    rate_limiter=RateLimiter(base_delay=(1.0, 2.0)),
)

results = await crawler.arun_many(urls, config=run_config, dispatcher=dispatcher)
```

---

## 📚 参考资源

- [Crawl4AI 官方文档](https://docs.crawl4ai.com)
- [GitHub 仓库](https://github.com/unclecode/crawl4ai)
- [官方示例代码](https://github.com/unclecode/crawl4ai/tree/main/docs/examples)

---

## 📝 更新日志

- **2025-01-XX** - 初始版本，基于 Crawl4AI v0.7.x+
  - 收集整理了基础用法、配置、提取策略、高级功能等示例
  - 添加了8个实际应用场景
  - 提供了详细的配置说明和快速参考

---

## 📄 License

本代码示例遵循 MIT License，可自由使用和修改。

---

## 🤝 贡献

欢迎提交 Issue 或 PR 来完善这些示例代码。
