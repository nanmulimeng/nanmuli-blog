# 爬虫工具层重构计划与当前结论

> 原始计划日期：2026-05-24
> 当前更新：2026-06-03
> 状态：作为后续重构参考保留

## 背景

早期 crawler 内部存在一些跨模块耦合问题：

- URL/RSS 通用采集逻辑曾与 digest 流程耦合较深。
- 关键词采集、Agent 层、Orchestrator 层存在重复去重风险。
- fingerprint 参数需要统一，避免不同阶段 SimHash 口径不同。
- CrawlerAgent 中存在临时兼容桥接逻辑。

当前 MVP Beta 已优先保证主链路可用，后续重构应保持小步推进，不影响日报上线试用。

## 当前优先级判断

| 项目 | 当前优先级 | 说明 |
| --- | --- | --- |
| 主链路稳定 | P0 | 日报、自动优化、部署优先 |
| 来源质量提升 | P1 | 直接影响日报质量 |
| 工具层重构 | P2 | 有价值，但不应阻断 MVP |
| 深度抽象/框架化 | P3 | 当前服务量小，不急 |

## 建议重构方向

### 1. 抽离 source crawler

目标：将 URL/RSS/keyword 采集能力从 digest 特定流程中抽离，形成稳定工具层。

建议模块：

```text
crawler-service/crawler/
├── source_crawler.py      # url/rss/source list 采集
├── search.py              # keyword/search
├── single.py              # 单页基础能力
├── deep.py                # 深度基础能力
├── dedup.py               # 去重
└── dependencies.py        # 外部依赖降级策略
```

### 2. 统一去重入口

目标：避免同一批结果被多个层级重复去重，导致结果被过度过滤。

原则：

- 工具层只做必要基础去重。
- Orchestrator 负责跨 section 和历史去重。
- 自动优化补采结果进入统一 merge 管线。
- fingerprint 参数从 settings 读取，避免硬编码。

### 3. 保持兼容入口

重构时允许保留薄委托函数，避免一次性破坏旧调用方。

示例：

```python
async def _crawl_url_sources(...):
    return await crawl_url_sources(...)
```

### 4. 加强测试

重构必须覆盖：

- 单页、深度、关键词、RSS。
- digest 任务完整生成。
- 自动优化补采。
- 去重结果数量稳定。
- 旧入口兼容。

## 验收标准

- `python -m pytest -q --tb=short` 通过。
- `rg "_crawl_url_sources|_crawl_rss_sources|crawl_url_sources|crawl_rss_sources"` 调用关系清晰。
- digest 任务仍可生成。
- 自动优化记录仍可写入。
- 外部 task API 不发生破坏性变化。

## 当前建议

在 MVP Beta 试用期间，只有当工具层耦合直接导致日报质量或服务不可用时，才进行重构。否则优先完成：

1. 来源质量优化。
2. 自动优化强反馈。
3. 独立服务接入文档和错误码。
4. 运维观测。
