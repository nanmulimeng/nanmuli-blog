"""AI 整理公共辅助模块

提取 routes.py 和 task_executor.py 的重复逻辑：
- DB pages → DTO 转换（PageContent / DigestPageContent）
- Digest 结果序列化
- 关键词上下文构建
- 统一 organize + save 入口
"""

import datetime
import json
from ai.organizer import PageContent, DigestPageContent
from standalone import repository as repo


def build_page_contents(pages: list[dict]) -> list[PageContent]:
    """从 DB 页面记录构建 PageContent 列表"""
    return [
        PageContent(
            url=p.get("url", ""),
            title=p.get("page_title", ""),
            markdown=p.get("raw_markdown", ""),
            word_count=p.get("word_count", 0),
        )
        for p in pages
        if p.get("crawl_status") == 2 and p.get("raw_markdown")
    ]


def build_digest_pages(pages: list[dict]) -> list[DigestPageContent]:
    """从 DB 页面记录构建 DigestPageContent 列表"""
    from standalone.task_executor import infer_category, extract_source_name

    return [
        DigestPageContent(
            url=p.get("url", ""),
            title=p.get("page_title", ""),
            markdown=p.get("raw_markdown", ""),
            category=infer_category(p.get("url", ""), p.get("page_title", "")),
            source_name=extract_source_name(p.get("url", "")),
        )
        for p in pages
        if p.get("crawl_status") == 2 and p.get("raw_markdown")
    ]


def serialize_digest_sections(result) -> list[dict]:
    """将 DigestContent.sections 序列化为 dict 列表"""
    return [
        {
            "category": sec.category,
            "category_name": sec.category_name,
            "emoji": sec.emoji,
            "items": [
                {
                    "title": item.title,
                    "one_liner": item.one_liner,
                    "source_url": item.source_url,
                    "source_name": item.source_name,
                }
                for item in sec.items
            ],
        }
        for sec in result.sections
    ]


def _build_keyword_context(task: dict) -> str | None:
    """从 ai_search_metadata 提取关键词上下文（用于 AI 整理）"""
    raw = task.get("ai_search_metadata")
    if not raw:
        return None
    try:
        meta = json.loads(raw) if isinstance(raw, str) else raw
        parts = []
        if meta.get("originalKeyword"):
            parts.append(f"原始关键词：{meta['originalKeyword']}")
        if meta.get("optimizedKeyword") and meta["optimizedKeyword"] != meta.get("originalKeyword"):
            parts.append(f"优化关键词：{meta['optimizedKeyword']}")
        if meta.get("searchVariants"):
            parts.append(f"实际搜索词变体：{' | '.join(meta['searchVariants'])}")
        return "\n".join(parts) if parts else None
    except Exception:
        return None


async def organize_content_and_save(
    task_id: int, task: dict, pages: list[dict], organizer
):
    """非日报：AI 整理 + 持久化"""
    page_contents = build_page_contents(pages)
    if not page_contents:
        raise ValueError("没有成功的页面可整理")

    template = task.get("ai_template", "tech_summary")
    keyword_context = _build_keyword_context(task)

    if len(page_contents) == 1:
        result = await organizer.organize(page_contents[0].markdown, template, keyword_context)
    else:
        result = await organizer.organize_multiple(page_contents, template)

    await repo.save_ai_results(
        task_id,
        ai_title=result.title,
        ai_summary=result.summary,
        ai_key_points=result.key_points,
        ai_tags=result.tags,
        ai_category=result.category,
        ai_full_content=result.full_content,
        ai_duration=result.duration_ms,
        ai_tokens_used=result.tokens_used,
    )
    return result


async def organize_digest_and_save(
    task_id: int, task: dict, pages: list[dict], organizer
):
    """日报：AI 整理 + 持久化"""
    digest_pages = build_digest_pages(pages)
    if not digest_pages:
        raise ValueError("没有成功的页面可整理")

    date = task.get("keyword") or datetime.date.today().isoformat()
    result = await organizer.generate_digest(digest_pages, date)
    sections_data = serialize_digest_sections(result)

    await repo.save_digest_results(
        task_id,
        ai_title=result.title,
        ai_summary=result.summary,
        ai_tags=result.tags,
        ai_full_content=result.full_content,
        ai_duration=result.duration_ms,
        ai_tokens_used=result.tokens_used,
        digest_date=date,
        highlight=result.highlight,
        sections=sections_data,
    )
    return result
