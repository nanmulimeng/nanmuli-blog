"""
共享数据模型

供 single / deep / search 模块共同引用的 CrawlResult 和 JS Challenge 常量。
"""

from typing import Optional


class CrawlResult:
    """爬取结果数据类"""
    def __init__(
        self,
        success: bool,
        url: str,
        title: Optional[str] = None,
        markdown: Optional[str] = None,
        metadata: Optional[dict] = None,
        word_count: int = 0,
        crawl_time_ms: int = 0,
        error_message: Optional[str] = None,
        depth: int = 0,
        search_rank: int = 0,
    ):
        self.success = success
        self.url = url
        self.title = title
        self.markdown = markdown
        self.metadata = metadata or {}
        self.word_count = word_count
        self.crawl_time_ms = crawl_time_ms
        self.error_message = error_message
        self.depth = depth
        self.search_rank = search_rank

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "url": self.url,
            "title": self.title,
            "markdown": self.markdown,
            "metadata": self.metadata,
            "word_count": self.word_count,
            "crawl_time_ms": self.crawl_time_ms,
            "error_message": self.error_message,
            "depth": self.depth,
            "search_rank": self.search_rank,
        }


# JS Challenge 检测阈值：成功但字数低于此值视为可能被拦截
JS_CHALLENGE_MIN_WORDS = 20

# JS Challenge 重试参数：等待正文元素出现 + 额外延迟
JS_CHALLENGE_WAIT_FOR = "article, main, .post-content, .entry-content, .content, #content, .article"
JS_CHALLENGE_DELAY = 3.0
