"""板块清洗文档数据模型

CrawlerAgent 爬取完成后，对每个板块生成一份清洗文档。
AI 轻量去噪或 heuristic 回退，不改变原文语义。
"""

from dataclasses import dataclass, field


@dataclass
class SourceEntry:
    """清洗后的单个来源条目"""
    url: str = ""
    title: str = ""
    cleaned_content: str = ""
    source_type: str = ""       # "keyword" / "url" / "rss"
    word_count: int = 0


@dataclass
class SectionDocument:
    """单个板块的清洗文档

    是对原始 CrawlResult 列表的补充，不替换它们。
    Orchestrator 在后续阶段（覆盖率评估、摘要生成）中使用。
    """
    section_name: str = ""
    source_count: int = 0       # 爬取总数（清洗前）
    cleaned_count: int = 0      # 有效条目数（清洗后）
    total_word_count: int = 0
    entries: list[SourceEntry] = field(default_factory=list)
    merged_content: str = ""    # 所有条目内容用 --- 分隔拼接
    cleanup_method: str = ""    # "ai" / "heuristic" / "none"
    cleanup_tokens_used: int = 0
    cleanup_duration_ms: int = 0
