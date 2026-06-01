"""AI 整理公共辅助模块

提取 routes.py 和 task_executor.py 的重复逻辑：
- DB pages → DTO 转换（PageContent / DigestPageContent）
- Digest 结果序列化
- 关键词上下文构建
- 统一 organize + save 入口
"""

import datetime
import json
import re
from urllib.parse import urlsplit, urlunsplit
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
    import json
    from standalone.task_executor import infer_category, extract_source_name
    from crawler.quality import SourceAuthority

    result = []
    for p in pages:
        if p.get("crawl_status") != 2 or not p.get("raw_markdown"):
            continue
        url = p.get("url", "")
        # 优先从 metadata 读取源名（信息源自定义名称），回退到域名解析
        source_name = ""
        meta_raw = p.get("page_metadata")
        if meta_raw:
            try:
                meta = json.loads(meta_raw) if isinstance(meta_raw, str) else meta_raw
                sn = meta.get("source_name", "") if isinstance(meta, dict) else ""
                source_name = sn if isinstance(sn, str) else ""
            except Exception:
                pass
        if not source_name:
            source_name = extract_source_name(url)
        result.append(DigestPageContent(
            url=url,
            title=p.get("page_title", ""),
            markdown=p.get("raw_markdown", ""),
            summary=_extract_summary(p.get("raw_markdown", "")),
            category=infer_category(url, p.get("page_title", "")),
            source_name=source_name,
            source_level=SourceAuthority.score(url).get("level", "medium"),
            page_id=p.get("id"),
        ))
    return result


def _extract_summary(markdown: str, max_chars: int = 200) -> str:
    """从 markdown 提取正文首段作为摘要（跳过标题行、元数据行）"""
    if not markdown:
        return ""
    lines = markdown.strip().splitlines()
    # 跳过标题行（# 开头）和空行，找到第一个正文段落
    content_lines: list[str] = []
    past_header = False
    for line in lines:
        stripped = line.strip()
        if not past_header:
            if stripped.startswith("#") or not stripped:
                continue
            past_header = True
        if past_header:
            if not stripped:
                break
            content_lines.append(stripped)

    text = " ".join(content_lines)
    if not text:
        return markdown.strip()[:max_chars].strip()
    if len(text) <= max_chars:
        return text
    for end_char in ("。", "！", "？", ".", "!", "?", "；", ";"):
        pos = text.rfind(end_char, max_chars // 2, max_chars)
        if pos > 0:
            return text[:pos + 1]
    return text[:max_chars].strip()


def serialize_digest_sections(result, url_to_page_id: dict | None = None) -> list[dict]:
    """将 DigestContent.sections 序列化为 dict 列表，回填 page_id"""
    _url_map = url_to_page_id or {}
    _normalized_url_map = {
        _normalize_digest_url(url): page_id
        for url, page_id in _url_map.items()
        if url
    }
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
                    "page_id": (
                        _url_map.get(item.source_url)
                        or _normalized_url_map.get(_normalize_digest_url(item.source_url))
                    ),
                }
                for item in sec.items
            ],
        }
        for sec in result.sections
    ]


def _normalize_digest_url(url: str) -> str:
    if not url:
        return ""
    try:
        parts = urlsplit(url.strip())
        return urlunsplit((
            parts.scheme.lower(),
            parts.netloc.lower(),
            parts.path.rstrip("/"),
            "",
            "",
        ))
    except Exception:
        return url.strip().lower().rstrip("/").split("#")[0].split("?")[0]


def _build_task_context(task: dict, pages: list[dict] | None = None) -> str | None:
    """构建 AI 整理的搜索上下文，引导 AI 聚焦用户意图。

    优先级：ai_search_metadata (keyword) > source_url (single/deep) > 页面标题
    """
    parts = []

    # 1. 关键词任务：从 ai_search_metadata 提取
    raw = task.get("ai_search_metadata")
    if raw:
        try:
            meta = json.loads(raw) if isinstance(raw, str) else raw
            if meta.get("originalKeyword"):
                parts.append(f"原始关键词：{meta['originalKeyword']}")
            if meta.get("optimizedKeyword") and meta["optimizedKeyword"] != meta.get("originalKeyword"):
                parts.append(f"优化关键词：{meta['optimizedKeyword']}")
            if meta.get("searchVariants"):
                parts.append(f"实际搜索词变体：{' | '.join(meta['searchVariants'])}")
        except Exception:
            pass

    # 2. single/deep 任务：从 source_url 构建来源上下文
    task_type = task.get("task_type", "")
    source_url = task.get("source_url", "")
    if not parts and source_url:
        from urllib.parse import urlparse
        try:
            parsed = urlparse(source_url)
            domain = parsed.netloc or parsed.path.split("/")[0] if parsed.path else ""
            if domain.startswith("www."):
                domain = domain[4:]
            path = parsed.path.strip("/") or ""
            if task_type == "deep":
                parts.append(f"深度爬取目标站点：{domain}")
                if path:
                    parts.append(f"起始路径：/{path}")
                parts.append("以上内容来自同一站点的多个页面，请综合分析并围绕站点主题组织内容。")
            else:
                parts.append(f"爬取来源：{domain}")
                if path:
                    parts.append(f"页面路径：/{path}")
                parts.append("请围绕以上来源页面的实际主题组织内容，避免被页面中无关的导航、广告等噪音带偏。")
        except Exception:
            pass

    # 3. 从成功页面标题中提取主题线索（补充）
    if not parts and pages:
        titles = [p.get("page_title", "") for p in pages if p.get("page_title")]
        if titles:
            parts.append(f"页面标题：{' | '.join(titles[:5])}")

    return "\n".join(parts) if parts else None


async def organize_content_and_save(
    task_id: int, task: dict, pages: list[dict], organizer,
    max_tokens_override: int | None = None
):
    """非日报：AI 整理 + 持久化"""
    page_contents = build_page_contents(pages)
    if not page_contents:
        raise ValueError("没有成功的页面可整理")

    template = task.get("ai_template", "tech_summary")
    keyword_context = _build_task_context(task, pages)

    if len(page_contents) == 1:
        result = await organizer.organize(
            page_contents[0].markdown, template, keyword_context,
            max_tokens_override=max_tokens_override,
        )
    else:
        result = await organizer.organize_multiple(
            page_contents, template, keyword_context=keyword_context,
            max_tokens_override=max_tokens_override,
        )

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
    task_id: int, task: dict, pages: list[dict], organizer,
    max_tokens_override: int | None = None
):
    """日报：AI 整理 + 持久化"""
    digest_pages = build_digest_pages(pages)
    if not digest_pages:
        raise ValueError("没有成功的页面可整理")

    date = task.get("digest_date") or task.get("keyword") or datetime.date.today().isoformat()
    input_urls = frozenset(_collect_digest_allowed_urls(digest_pages))

    # 获取最近 highlight 用于 AI 多样性检测
    recent_highlights = await repo.get_recent_highlights(count=3)

    result = await organizer.generate_digest(
        digest_pages, date, input_urls=input_urls, recent_highlights=recent_highlights,
        max_tokens_override=max_tokens_override
    )

    # highlight 重复检测：与最近几期对比，高相似度时从 sections 中选取替代
    if recent_highlights and result.highlight:
        if _is_highlight_duplicate(result.highlight, recent_highlights):
            _replace_duplicate_highlight(result, recent_highlights)

    # 构建 URL → page_id 映射，供序列化时回填
    url_to_page_id = {p.url: p.page_id for p in digest_pages if p.url and p.page_id is not None}
    sections_data = serialize_digest_sections(result, url_to_page_id=url_to_page_id)

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


def _collect_digest_allowed_urls(digest_pages: list[DigestPageContent]) -> set[str]:
    urls: set[str] = set()
    for page in digest_pages:
        for raw in (getattr(page, "url", ""),):
            cleaned = _clean_digest_source_url(raw)
            if cleaned:
                urls.add(cleaned)
        for field in ("markdown", "summary"):
            text = getattr(page, field, "") or ""
            for raw in re.findall(r"https?://[^\s)\]}>\"']+", text):
                cleaned = _clean_digest_source_url(raw)
                if cleaned:
                    urls.add(cleaned)
    return urls


def _clean_digest_source_url(url: str) -> str:
    if not url:
        return ""
    return url.strip().rstrip(".,;:!?，。；：！？")


def _is_highlight_duplicate(new_highlight: str, recent_highlights: list[str], threshold: float = 0.7) -> bool:
    """检测 highlight 与最近几期是否高度重复（基于 bigram 级 Jaccard 相似度）"""
    if not new_highlight or not recent_highlights:
        return False
    def _bigrams(s: str) -> set[str]:
        return {s[i:i+2] for i in range(len(s) - 1)} if len(s) >= 2 else {s}
    new_bg = _bigrams(new_highlight)
    for old in recent_highlights:
        if not old:
            continue
        old_bg = _bigrams(old)
        intersection = len(new_bg & old_bg)
        union = len(new_bg | old_bg)
        if union > 0 and intersection / union > threshold:
            return True
    return False


def _replace_duplicate_highlight(result, recent_highlights: list[str]):
    """从 sections items 中选取一个与 recent_highlights 不重复的 oneLiner 替换 highlight"""
    candidates = []
    for sec in result.sections:
        for item in sec.items:
            if item.one_liner and not _is_highlight_duplicate(item.one_liner, recent_highlights):
                candidates.append(item.one_liner)
    if candidates:
        result.highlight = candidates[0]
