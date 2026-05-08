"""独立模式常量和枚举（5态，与 Java CollectTaskStatus 对齐）"""


class TaskStatus:
    PENDING = 0
    CRAWLING = 1
    PROCESSING = 2
    COMPLETED = 3
    FAILED = 4

    LABELS = {
        0: "待处理",
        1: "爬取中",
        2: "AI整理中",
        3: "已完成",
        4: "失败",
    }

    @classmethod
    def label(cls, status: int) -> str:
        return cls.LABELS.get(status, "未知")

    @classmethod
    def is_terminal(cls, status: int) -> bool:
        return status in (cls.COMPLETED, cls.FAILED)

    @classmethod
    def is_active(cls, status: int) -> bool:
        return status in (cls.PENDING, cls.CRAWLING, cls.PROCESSING)


class PageStatus:
    PENDING = 0
    CRAWLING = 1
    COMPLETED = 2
    FAILED = 3

    LABELS = {0: "待爬取", 1: "爬取中", 2: "已完成", 3: "失败"}


TASK_TYPE_LABELS = {
    "single": "单页爬取",
    "deep": "深度爬取",
    "keyword": "关键词搜索",
    "digest": "技术日报",
}

AI_TEMPLATE_LABELS = {
    "tech_summary": "技术摘要",
    "tutorial": "教程提炼",
    "comparison": "对比分析",
    "knowledge_report": "知识报告",
    "daily_digest": "技术日报",
}
