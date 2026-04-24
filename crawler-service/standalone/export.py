"""Markdown 导出功能"""

from datetime import datetime
from fastapi.responses import PlainTextResponse
from standalone.models import TASK_TYPE_LABELS, PageStatus
from standalone import repository as repo


async def export_task_as_markdown(task_id: int) -> PlainTextResponse:
    task = await repo.get_task(task_id)
    if not task:
        raise ValueError("Task not found")

    pages = await repo.get_pages_by_task(task_id)
    success_pages = [p for p in pages if p["crawl_status"] == PageStatus.COMPLETED]

    lines = [
        f"# 爬取任务 #{task_id} - {TASK_TYPE_LABELS.get(task['task_type'], task['task_type'])}",
        "",
    ]

    if task.get("source_url"):
        lines.append(f"> URL: {task['source_url']}")
    if task.get("keyword"):
        lines.append(f"> 关键词: {task['keyword']}")
    lines.append(f"> 完成时间: {task.get('updated_at', 'N/A')}")
    lines.append(f"> 成功页面: {len(success_pages)}/{task.get('total_pages', 0)}")
    lines.append(f"> 总字数: {task.get('total_word_count', 0)}")
    lines.append("")
    lines.append("---")
    lines.append("")

    for page in success_pages:
        lines.append(f"## {page.get('page_title') or page['url']}")
        lines.append(f"> 来源: {page['url']}")
        lines.append("")
        if page.get("raw_markdown"):
            lines.append(page["raw_markdown"])
        lines.append("")
        lines.append("---")
        lines.append("")

    content = "\n".join(lines)
    filename = f"task_{task_id}_{datetime.now().strftime('%Y%m%d')}.md"

    return PlainTextResponse(
        content=content,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )
