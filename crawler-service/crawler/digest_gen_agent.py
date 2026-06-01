"""日报生成 Agent — 接收 SectionDocument 清洗文档，生成完整日报

由 DigestOrchestrator 在所有 CrawlerAgent 完成后调用。
复用 ContentOrganizer.generate_digest() 的 AI 管道，但输入从清洗文档获取
而非从 DB 原始页面。
"""

import logging
import re
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

logger = logging.getLogger(__name__)

_SOURCE_LEVEL_ORDER = {"official": 0, "high": 1, "medium": 2, "low": 3, "spam": 4}
_MIN_DIGEST_SECTIONS = 2
_MIN_DIGEST_ITEMS = 5
_MAX_DIGEST_ITEMS = 12
_OPEN_SOURCE_DOMAINS = {
    "github.com", "github.blog", "gitlab.com", "gitee.com",
    "npmjs.com", "pypi.org", "pkg.go.dev", "crates.io",
    "huggingface.co", "apache.org", "cncf.io", "openjsf.org",
    "rust-lang.org", "python.org", "nodejs.org", "deno.land",
    "bun.sh", "kubernetes.io", "docker.com", "ossinsight.io",
}


@dataclass
class DigestGenAgentResult:
    """日报生成 Agent 执行结果"""
    success: bool
    digest_content: "DigestContent | None" = None
    error: str | None = None
    tokens_used: int = 0
    duration_ms: int = 0


class DigestGenAgent:
    """日报生成 Agent：基于 SectionDocument 清洗内容生成完整日报

    与 organize_digest_and_save() 的区别：
    - 输入是 SectionDocument（已清洗），而非 DB 原始页面
    - 在 Orchestrator 内部执行，不依赖 DB 中的 page_id
    - page_id 由 TaskExecutor 后续回填
    """

    def __init__(self, config_snapshot: dict):
        self._config_snapshot = config_snapshot

    async def execute(
        self,
        section_documents: list,
        date: str,
    ) -> DigestGenAgentResult:
        if not self._precheck(section_documents):
            return DigestGenAgentResult(success=False, error="precheck failed")

        from standalone import repository as repo

        try:
            # 预加载来源可信度缓存
            try:
                from crawler.quality import SourceAuthority
                await SourceAuthority.preload_authority_cache()
            except Exception as e:
                logger.warning("[DigestGenAgent] SourceAuthority preload failed: %s", e)

            # 转换 SectionDocument → DigestPageContent
            digest_pages = self._build_digest_pages(section_documents)
            if not digest_pages:
                return DigestGenAgentResult(success=False, error="no valid pages")

            input_urls = frozenset(_collect_allowed_source_urls(digest_pages))

            # 获取最近 highlight（AI 多样性检测）
            recent_highlights = []
            try:
                recent_highlights = await repo.get_recent_highlights(count=3)
            except Exception as e:
                logger.debug("[DigestGenAgent] get_recent_highlights failed: %s", e)

            # 调用 AI 生成日报
            from ai.organizer import ContentOrganizer
            organizer = ContentOrganizer()
            try:
                content = await organizer.generate_digest(
                    digest_pages, date,
                    input_urls=input_urls,
                    recent_highlights=recent_highlights,
                )
                content = _supplement_digest_coverage(content, digest_pages)
            finally:
                await organizer.close()

            return DigestGenAgentResult(
                success=True,
                digest_content=content,
                tokens_used=content.tokens_used,
                duration_ms=content.duration_ms,
            )

        except Exception as e:
            logger.warning("[DigestGenAgent] execute failed: %s", e)
            return DigestGenAgentResult(success=False, error=str(e))

    def _precheck(self, section_documents: list) -> bool:
        if not section_documents:
            return False
        total_entries = 0
        for doc in section_documents:
            for entry in getattr(doc, "entries", []):
                content = getattr(entry, "cleaned_content", "")
                if content and len(content) >= 100:
                    total_entries += 1
        if total_entries < 3:
            logger.info("[DigestGenAgent] Precheck: only %d valid entries (>=100 chars), skipping", total_entries)
            return False
        try:
            from ai.config import ai_settings
            if not ai_settings.is_configured:
                return False
        except Exception:
            return False
        return True

    def _build_digest_pages(self, section_documents: list) -> list:
        from ai.organizer import DIGEST_CATEGORY_MAP, DigestPageContent
        from standalone.task_executor import extract_source_name, infer_category
        from standalone.organizer_helper import _extract_summary
        from crawler.quality import SourceAuthority

        pages_by_url: dict[str, DigestPageContent] = {}
        pages_without_url: list[DigestPageContent] = []
        for doc in section_documents:
            entries = getattr(doc, "entries", [])
            for entry in entries:
                content = getattr(entry, "cleaned_content", "")
                url = getattr(entry, "url", "")
                title = getattr(entry, "title", "")
                if not content or len(content) < 100:
                    continue

                source_name = extract_source_name(url)
                doc_category = getattr(doc, "section_name", "") or ""
                category = doc_category if doc_category in DIGEST_CATEGORY_MAP else infer_category(url, title)
                if category == "open_source" and not _is_open_source_digest_page(url):
                    continue

                expanded_pages = _expand_open_source_listing(
                    url=url,
                    title=title,
                    content=content,
                    category=category,
                    source_level_provider=SourceAuthority.score,
                )
                if expanded_pages:
                    for page in expanded_pages:
                        dedupe_key = _canonical_digest_url(page.url)
                        existing = pages_by_url.get(dedupe_key)
                        if existing is None or _is_better_digest_page(page, existing):
                            pages_by_url[dedupe_key] = page
                    continue

                try:
                    authority = SourceAuthority.score(url)
                    source_level = authority.get("level", "medium")
                except Exception:
                    source_level = "medium"

                summary = _extract_summary(content)

                page = DigestPageContent(
                    url=url,
                    title=title,
                    markdown=content,
                    summary=summary,
                    category=category,
                    source_name=source_name,
                    source_level=source_level,
                    page_id=None,
                )

                dedupe_key = _canonical_digest_url(url)
                if not dedupe_key:
                    pages_without_url.append(page)
                    continue

                existing = pages_by_url.get(dedupe_key)
                if existing is None or _is_better_digest_page(page, existing):
                    pages_by_url[dedupe_key] = page

        pages = list(pages_by_url.values()) + pages_without_url
        return sorted(
            pages,
            key=lambda p: (
                _SOURCE_LEVEL_ORDER.get(p.source_level, _SOURCE_LEVEL_ORDER["medium"]),
                -(len(p.markdown or "")),
            ),
        )


def _canonical_digest_url(url: str) -> str:
    if not url:
        return ""
    try:
        parsed = urlsplit(url.strip())
    except Exception:
        return url.strip().rstrip("/")
    if not parsed.scheme or not parsed.netloc:
        return url.strip().rstrip("/")

    path = parsed.path.rstrip("/") or "/"
    return urlunsplit((
        parsed.scheme.lower(),
        parsed.netloc.lower(),
        path,
        parsed.query,
        "",
    ))


def _collect_allowed_source_urls(pages: list) -> set[str]:
    """Collect page URLs plus URLs explicitly present in cleaned content.

    Search result pages and RSS pages often contain canonical article links in
    their markdown. Allowing those links prevents the final sourceUrl guard from
    dropping legitimate article URLs copied from the input text.
    """
    urls: set[str] = set()
    for page in pages:
        for raw in (getattr(page, "url", ""),):
            cleaned = _clean_source_url(raw)
            if cleaned:
                urls.add(cleaned)
        for field in ("markdown", "summary"):
            text = getattr(page, field, "") or ""
            for raw in re.findall(r"https?://[^\s)\]}>\"']+", text):
                cleaned = _clean_source_url(raw)
                if cleaned:
                    urls.add(cleaned)
    return urls


def _clean_source_url(url: str) -> str:
    if not url:
        return ""
    return url.strip().rstrip(".,;:!?，。；：！？")


def _is_open_source_digest_page(url: str) -> bool:
    """Keep open_source focused on repositories and official project sources."""
    if not url:
        return False
    try:
        parsed = urlsplit(url.strip())
    except Exception:
        return False

    domain = parsed.netloc.lower()
    if domain.startswith("www."):
        domain = domain[4:]

    if domain == "github.com":
        parts = [p for p in parsed.path.split("/") if p]
        if parts[:1] == ["trending"]:
            return True
        return len(parts) >= 2 and parts[0] not in {"features", "topics", "marketplace"}

    return domain in _OPEN_SOURCE_DOMAINS


def _expand_open_source_listing(
    *,
    url: str,
    title: str,
    content: str,
    category: str,
    source_level_provider,
) -> list:
    """Split high-signal listing pages into source-specific project pages."""
    if category != "open_source" or not _is_github_trending_url(url):
        return []

    from ai.organizer import DigestPageContent

    pages = []
    link_matches = list(re.finditer(
        r"^##\s+\[\s*([^/\]\n]+?)\s*/\s*([^\]\n]+?)\]\((https://github\.com/[^)\s]+)\)",
        content,
        flags=re.MULTILINE,
    ))
    matches = [
        {
            "start": match.start(),
            "owner": re.sub(r"\s+", "", match.group(1)).strip(),
            "repo": re.sub(r"\s+", "", match.group(2)).strip(),
            "url": match.group(3).strip(),
        }
        for match in link_matches
    ]

    if not matches:
        matches = [
            {
                "start": match.start(),
                "owner": match.group(1).strip(),
                "repo": match.group(2).strip(),
                "url": f"https://github.com/{match.group(1).strip()}/{match.group(2).strip()}",
            }
            for match in re.finditer(
                r"^\*\*\s*([A-Za-z0-9_.-]+)\s*/\s*([A-Za-z0-9_.-]+)\s*\*\*(?:\s*\([^)]*\))?\s*:",
                content,
                flags=re.MULTILINE,
            )
        ]

    if not matches:
        return []

    for idx, match in enumerate(matches[:12]):
        owner = match["owner"]
        repo = match["repo"]
        repo_url = match["url"]
        next_start = matches[idx + 1]["start"] if idx + 1 < len(matches) else len(content)
        entry_markdown = content[match["start"]:next_start].strip()
        if len(entry_markdown) < 80:
            continue
        try:
            authority = source_level_provider(repo_url)
            source_level = authority.get("level", "medium")
        except Exception:
            source_level = "medium"
        pages.append(DigestPageContent(
            url=repo_url,
            title=f"{owner}/{repo}",
            markdown=entry_markdown,
            summary=_first_non_heading_line(entry_markdown),
            category="open_source",
            source_name="GitHub Trending",
            source_level=source_level,
            page_id=None,
        ))
    if pages:
        logger.info(
            "[DigestGenAgent] Expanded GitHub Trending listing into %d repo pages",
            len(pages),
        )
    return pages


def _is_github_trending_url(url: str) -> bool:
    if not url:
        return False
    try:
        parsed = urlsplit(url.strip())
    except Exception:
        return False
    domain = parsed.netloc.lower()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain == "github.com" and parsed.path.rstrip("/") == "/trending"


def _first_non_heading_line(markdown: str, max_chars: int = 220) -> str:
    for line in (markdown or "").splitlines()[1:]:
        text = line.strip()
        if not text or text.startswith("[") or text.startswith("!"):
            continue
        if len(text) > max_chars:
            return text[:max_chars].strip()
        return text
    return (markdown or "").strip()[:max_chars].strip()


def _is_better_digest_page(candidate, current) -> bool:
    candidate_rank = _SOURCE_LEVEL_ORDER.get(candidate.source_level, _SOURCE_LEVEL_ORDER["medium"])
    current_rank = _SOURCE_LEVEL_ORDER.get(current.source_level, _SOURCE_LEVEL_ORDER["medium"])
    if candidate_rank != current_rank:
        return candidate_rank < current_rank
    return len(candidate.markdown or "") > len(current.markdown or "")


def _supplement_digest_coverage(content, pages: list):
    """Add source-backed items when the model returns a valid but thin digest."""
    if not pages or not isinstance(getattr(content, "sections", None), list):
        return content

    usable_pages = [
        p for p in pages
        if getattr(p, "url", "") and getattr(p, "title", "") and (
            getattr(p, "summary", "") or getattr(p, "markdown", "")
        )
    ]
    if not usable_pages:
        return content

    categories = []
    for page in usable_pages:
        cat = getattr(page, "category", "") or "tech_article"
        if cat not in categories:
            categories.append(cat)

    current_items = [
        item
        for section in content.sections
        for item in getattr(section, "items", [])
    ]
    current_urls = {
        getattr(item, "source_url", "")
        for item in current_items
        if getattr(item, "source_url", "")
    }
    current_categories = {
        getattr(section, "category", "")
        for section in content.sections
        if getattr(section, "items", [])
    }
    missing_categories = [cat for cat in categories if cat not in current_categories]
    current_count = len(current_items)
    target_sections = min(len(categories), _MIN_DIGEST_SECTIONS)
    target_items = min(len(usable_pages), _MIN_DIGEST_ITEMS)

    if not missing_categories and len(content.sections) >= target_sections and current_count >= target_items:
        return content

    from ai.organizer import DIGEST_CATEGORY_MAP, DigestItem, DigestSection

    section_by_category = {
        getattr(section, "category", ""): section
        for section in content.sections
    }

    added_items = []

    def ensure_section(category: str):
        section = section_by_category.get(category)
        if section is not None:
            return section
        cat_info = DIGEST_CATEGORY_MAP.get(category, DIGEST_CATEGORY_MAP.get("tech_article", ("技术文章", "📖")))
        section = DigestSection(category=category, category_name=cat_info[0], emoji=cat_info[1])
        content.sections.append(section)
        section_by_category[category] = section
        return section

    def add_page(page) -> bool:
        nonlocal current_count
        if current_count >= min(len(usable_pages), _MAX_DIGEST_ITEMS):
            return False
        url = getattr(page, "url", "")
        if not url or url in current_urls:
            return False
        section = ensure_section(getattr(page, "category", "") or "tech_article")
        item = DigestItem(
            title=_fallback_title(page),
            one_liner=_fallback_one_liner(page),
            source_url=url,
            source_name=_fallback_source_name(page),
        )
        section.items.append(item)
        current_urls.add(url)
        current_count += 1
        added_items.append((section, item))
        return True

    for category in categories:
        section = ensure_section(category)
        if not getattr(section, "items", []):
            for page in usable_pages:
                if (getattr(page, "category", "") or "tech_article") == category and add_page(page):
                    break

    for page in usable_pages:
        if current_count >= target_items:
            break
        add_page(page)

    if added_items:
        logger.info(
            "[DigestGenAgent] Supplemented thin digest with %d source-backed items",
            len(added_items),
        )
        _append_supplement_to_full_content(content, added_items)
        if not getattr(content, "highlight", ""):
            content.highlight = added_items[0][1].one_liner

    content.sections = [section for section in content.sections if getattr(section, "items", [])]
    return content


def _fallback_title(page) -> str:
    title = (getattr(page, "title", "") or "").strip()
    return _truncate_text(title, 80) or "Untitled"


def _fallback_one_liner(page) -> str:
    text = (getattr(page, "summary", "") or getattr(page, "markdown", "") or "").strip()
    text = re.sub(r"\s+", " ", text)
    return _truncate_text(text, 180) or _fallback_title(page)


def _fallback_source_name(page) -> str:
    source_name = (getattr(page, "source_name", "") or "").strip()
    if source_name:
        return source_name
    url = getattr(page, "url", "") or ""
    try:
        return urlsplit(url).netloc or url
    except Exception:
        return url


def _truncate_text(text: str, max_len: int) -> str:
    text = (text or "").strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def _append_supplement_to_full_content(content, added_items: list[tuple]):
    lines = ["", "## 补充覆盖"]
    last_category = None
    for section, item in added_items:
        category_name = getattr(section, "category_name", "") or getattr(section, "category", "")
        if category_name != last_category:
            lines.append(f"### {category_name}")
            last_category = category_name
        lines.append(f"- [{item.title}]({item.source_url})：{item.one_liner}")
    supplement = "\n".join(lines)
    content.full_content = ((getattr(content, "full_content", "") or "").rstrip() + "\n" + supplement).strip()
