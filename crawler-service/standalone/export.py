"""Markdown 导出功能"""

import json
from datetime import datetime
from fastapi import HTTPException
from fastapi.responses import PlainTextResponse
from standalone.models import TASK_TYPE_LABELS, PageStatus
from standalone import repository as repo


async def export_task_as_markdown(task_id: int) -> PlainTextResponse:
    task = await repo.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

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

    # AI 整理结果（非日报任务，或日报无 sections 时的 fallback）
    is_digest = task.get("task_type") == "digest"
    sections = await repo.get_digest_sections(task_id) if is_digest else []

    if not is_digest or not sections:
        ai_content = task.get("ai_full_content")
        if ai_content:
            if task.get("ai_title"):
                lines.append(f"## AI 整理: {task['ai_title']}")
            else:
                lines.append("## AI 整理结果")
            lines.append("")
            if task.get("ai_summary"):
                lines.append(f"> 摘要: {task['ai_summary']}")
            if task.get("ai_tags"):
                try:
                    tags = json.loads(task["ai_tags"]) if isinstance(task["ai_tags"], str) else task["ai_tags"]
                    lines.append(f"> 标签: {', '.join(tags)}")
                except Exception:
                    pass
            lines.append("")
            lines.append(ai_content)
            lines.append("")
            lines.append("---")
            lines.append("")

    # 日报结构化 sections
    if is_digest and sections:
            if task.get("digest_highlight"):
                lines.append(f"## 今日亮点")
                lines.append("")
                lines.append(task["digest_highlight"])
                lines.append("")
                lines.append("---")
                lines.append("")

            for sec in sections:
                emoji = sec.get("emoji", "")
                cat_name = sec.get("category_name", sec.get("category", ""))
                lines.append(f"## {emoji} {cat_name}")
                lines.append("")
                for item in sec.get("items", []):
                    title = item.get("title", "")
                    one_liner = item.get("one_liner", "")
                    source_url = item.get("source_url", "")
                    source_name = item.get("source_name", "")
                    if title:
                        link = f"[{title}]({source_url})" if source_url else title
                        lines.append(f"- **{link}**")
                        if one_liner:
                            lines.append(f"  {one_liner}")
                        if source_name:
                            lines.append(f"  — {source_name}")
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
