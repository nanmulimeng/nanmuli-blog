"""统一日志配置（替代 logging.basicConfig）"""

import logging
import os
from logging.handlers import RotatingFileHandler


class RequestIdFilter(logging.Filter):
    """将 context variable 中的 request_id 注入日志记录"""

    def filter(self, record):
        from api.context import request_id_var
        record.request_id = request_id_var.get("")
        return True


def setup_logging(log_level: str = "INFO", standalone: bool = False):
    """
    配置根日志器。

    - 始终输出到 stdout（人类可读格式）
    - 独立模式额外输出到 RotatingFileHandler
    - 所有 handler 注入 RequestIdFilter
    """
    level = getattr(logging, log_level.upper(), logging.INFO)
    rid_filter = RequestIdFilter()
    formatter = logging.Formatter(
        "%(asctime)s [%(request_id)s] %(name)s %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # StreamHandler (stdout)
    stream = logging.StreamHandler()
    stream.setLevel(level)
    stream.setFormatter(formatter)
    stream.addFilter(rid_filter)

    handlers = [stream]

    # 独立模式：RotatingFileHandler
    if standalone or os.environ.get("LOG_FILE"):
        log_dir = os.environ.get("LOG_DIR", "data")
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, "crawler.log")

        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=20 * 1024 * 1024,  # 20MB
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        file_handler.addFilter(rid_filter)
        handlers.append(file_handler)

    # 配置根日志器
    root = logging.getLogger()
    root.setLevel(level)
    # 清除 basicConfig 可能遗留的默认 handler
    root.handlers.clear()
    for h in handlers:
        root.addHandler(h)

    # 降低 uvicorn.access 日志级别，避免双重记录请求
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
