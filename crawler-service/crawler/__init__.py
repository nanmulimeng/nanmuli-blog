"""
Web Collector - Crawler Package

基于 Crawl4AI 的网页内容采集实现
"""

import sys

# Windows UTF-8 全局保护：Crawl4AI/Rich 输出包含 Unicode 字符（✓ ✗ 等），
# Windows 默认 GBK 编码会导致 UnicodeEncodeError 崩溃。
# 必须在任何 Crawl4AI/Rich 导入前执行此补丁。
if sys.platform == "win32":
    import os
    os.environ.setdefault("PYTHONUTF8", "1")
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    # 强制 Rich 不使用 Legacy Windows Console API（避免 GBK 编码崩溃）
    try:
        import rich.console
        _orig_console_init = rich.console.Console.__init__
        def _patched_console_init(self, *args, **kwargs):
            kwargs["legacy_windows"] = False
            kwargs["force_terminal"] = kwargs.get("force_terminal", True)
            _orig_console_init(self, *args, **kwargs)
        rich.console.Console.__init__ = _patched_console_init
    except Exception:
        pass

__version__ = "1.0.0"

from .single import crawl_single_page
from .deep import crawl_deep_pages
from .search import crawl_by_keyword
from . import filters

__all__ = [
    "crawl_single_page",
    "crawl_deep_pages",
    "crawl_by_keyword",
    "filters",
]
