"""日报生成 Agent — 接收 SectionDocument 清洗文档，生成完整日报

由 DigestOrchestrator 在所有 CrawlerAgent 完成后调用。
复用 ContentOrganizer.generate_digest() 的 AI 管道，但输入从清洗文档获取
而非从 DB 原始页面。
"""

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


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

            input_urls = frozenset(p.url for p in digest_pages if p.url)

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
        from ai.organizer import DigestPageContent
        from standalone.task_executor import extract_source_name, infer_category
        from standalone.organizer_helper import _extract_summary
        from crawler.quality import SourceAuthority

        pages: list[DigestPageContent] = []
        for doc in section_documents:
            entries = getattr(doc, "entries", [])
            for entry in entries:
                content = getattr(entry, "cleaned_content", "")
                url = getattr(entry, "url", "")
                title = getattr(entry, "title", "")
                if not content or len(content) < 100:
                    continue

                source_name = extract_source_name(url)
                category = infer_category(url, title)

                try:
                    authority = SourceAuthority.score(url)
                    source_level = authority.get("level", "medium")
                except Exception:
                    source_level = "medium"

                summary = _extract_summary(content)

                pages.append(DigestPageContent(
                    url=url,
                    title=title,
                    markdown=content,
                    summary=summary,
                    category=category,
                    source_name=source_name,
                    source_level=source_level,
                    page_id=None,
                ))

        return pages
