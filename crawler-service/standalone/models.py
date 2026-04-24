"""独立模式常量和枚举"""


class TaskStatus:
    PENDING = 0
    CRAWLING = 1
    COMPLETED = 2
    FAILED = 3

    LABELS = {0: "待处理", 1: "爬取中", 2: "已完成", 3: "失败"}
    DISPLAY = {0: "PENDING", 1: "CRAWLING", 2: "COMPLETED", 3: "FAILED"}

    @classmethod
    def label(cls, status: int) -> str:
        return cls.LABELS.get(status, "未知")

    @classmethod
    def is_terminal(cls, status: int) -> bool:
        return status in (cls.COMPLETED, cls.FAILED)


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
}
