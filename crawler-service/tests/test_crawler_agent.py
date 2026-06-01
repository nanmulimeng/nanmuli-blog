"""CrawlerAgent 板块清洗文档测试

覆盖：
- SectionDocument / SourceEntry 数据模型
- CrawlerAgentResult.section_document 字段
- _heuristic_cleanup 正则过滤
- _build_section_document AI 优先 + heuristic 降级
- Orchestrator 收集 section_documents
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass

from crawler.section_document import SectionDocument, SourceEntry
from crawler.crawler_agent import CrawlerAgent, CrawlerAgentResult
from crawler.digest_orchestrator import DigestOrchestrator, PlannedSection, DigestCrawlPlan
from crawler.source_agent import SourceCrawlPlan


# ============== 数据模型测试 ==============

class TestSectionDocument:
    def test_defaults(self):
        doc = SectionDocument()
        assert doc.section_name == ""
        assert doc.source_count == 0
        assert doc.cleaned_count == 0
        assert doc.entries == []
        assert doc.merged_content == ""
        assert doc.cleanup_method == ""
        assert doc.cleanup_tokens_used == 0
        assert doc.cleanup_duration_ms == 0

    def test_source_entry(self):
        entry = SourceEntry(
            url="https://example.com",
            title="Test",
            cleaned_content="cleaned content",
            source_type="keyword",
            word_count=2,
        )
        assert entry.url == "https://example.com"
        assert entry.word_count == 2


class TestCrawlerAgentResult:
    def test_default_section_document_is_none(self):
        result = CrawlerAgentResult(section_name="test", success=True)
        assert result.section_document is None
        assert result.results == []
        assert result.fallback_used is False

    def test_section_document_field(self):
        doc = SectionDocument(section_name="test", source_count=5)
        result = CrawlerAgentResult(
            section_name="test", success=True, section_document=doc
        )
        assert result.section_document is not None
        assert result.section_document.source_count == 5


# ============== Heuristic 清洗测试 ==============

class TestHeuristicCleanup:
    def _make_result(self, url, title, markdown):
        """构造类 CrawlResult 对象"""
        obj = MagicMock()
        obj.url = url
        obj.title = title
        obj.markdown = markdown
        return obj

    def test_filters_short_content(self):
        results = [self._make_result("https://a.com", "Short", "hi")]
        entries = CrawlerAgent._heuristic_cleanup(results)
        assert len(entries) == 0

    def test_keeps_valid_content(self):
        content = "A" * 200
        results = [self._make_result("https://a.com", "Valid", content)]
        entries = CrawlerAgent._heuristic_cleanup(results)
        assert len(entries) == 1
        assert entries[0].url == "https://a.com"
        assert entries[0].title == "Valid"
        assert len(entries[0].cleaned_content) >= 100

    def test_filters_dict_results(self):
        results = [{"url": "https://a.com", "title": "Dict", "markdown": "B" * 200}]
        entries = CrawlerAgent._heuristic_cleanup(results)
        assert len(entries) == 1

    def test_skips_empty_content(self):
        results = [self._make_result("https://a.com", "Empty", "")]
        entries = CrawlerAgent._heuristic_cleanup(results)
        assert len(entries) == 0


# ============== _build_section_document 测试 ==============

class TestBuildSectionDocument:
    def _make_agent(self) -> CrawlerAgent:
        section = PlannedSection(
            name="test_section",
            source_type="keyword",
            keywords=["test"],
        )
        plan = SourceCrawlPlan(
            section_name="test_section",
            active_keywords=["test"],
            active_url_sources=[],
            active_rss_sources=[],
            skipped_source_ids=[],
            recommended_engine="sogou",
            adjusted_max_items=5,
        )
        config = MagicMock()
        snap = {}
        agent = CrawlerAgent(section, plan, config, snap)
        return agent

    def _make_result(self, url, title, markdown):
        obj = MagicMock()
        obj.url = url
        obj.title = title
        obj.markdown = markdown
        return obj

    @pytest.mark.asyncio
    async def test_no_content_returns_none_method(self):
        agent = self._make_agent()
        results = [self._make_result("https://a.com", "Empty", "")]
        doc = await agent._build_section_document(results)
        assert doc.cleanup_method == "none"
        assert doc.cleaned_count == 0

    @pytest.mark.asyncio
    async def test_heuristic_fallback_when_ai_disabled(self):
        agent = self._make_agent()
        content = "Valid content " * 20
        results = [self._make_result("https://a.com", "Test", content)]
        with patch.object(agent, "_should_use_ai", return_value=False):
            doc = await agent._build_section_document(results)
        assert doc.cleanup_method == "heuristic"
        assert doc.cleaned_count == 1
        assert doc.section_name == "test_section"
        assert doc.source_count == 1

    @pytest.mark.asyncio
    async def test_ai_cleanup_success(self):
        agent = self._make_agent()
        content = "Valid content " * 20
        results = [self._make_result("https://a.com", "Test", content)]

        cleaned = [{"url": "https://a.com", "cleaned_content": "cleaned " * 30}]

        with patch.object(agent, "_should_use_ai", return_value=True), \
             patch("ai.organizer.ContentOrganizer") as MockOrganizer:
            mock_org = MagicMock()
            mock_org.clean_section_content = AsyncMock(return_value=(cleaned, 100, 500))
            mock_org.close = AsyncMock()
            MockOrganizer.return_value = mock_org

            doc = await agent._build_section_document(results)

        assert doc.cleanup_method == "ai"
        assert doc.cleanup_tokens_used == 100
        assert doc.cleanup_duration_ms == 500
        assert doc.cleaned_count == 1

    @pytest.mark.asyncio
    async def test_ai_failure_falls_back_to_heuristic(self):
        agent = self._make_agent()
        content = "Valid content " * 20
        results = [self._make_result("https://a.com", "Test", content)]

        with patch.object(agent, "_should_use_ai", return_value=True), \
             patch("ai.organizer.ContentOrganizer") as MockOrganizer:
            mock_org = MagicMock()
            mock_org.clean_section_content = AsyncMock(side_effect=Exception("AI error"))
            mock_org.close = AsyncMock()
            MockOrganizer.return_value = mock_org

            doc = await agent._build_section_document(results)

        assert doc.cleanup_method == "heuristic"
        assert doc.cleaned_count >= 1

    @pytest.mark.asyncio
    async def test_open_source_section_filters_non_project_pages_before_cleanup(self):
        section = PlannedSection(name="open_source", source_type="keyword")
        plan = SourceCrawlPlan(section_name="open_source")
        agent = CrawlerAgent(section, plan, MagicMock(), {})
        results = [
            self._make_result(
                "https://blog.csdn.net/example/article/details/1",
                "GitHub tutorial",
                "tutorial content " * 20,
            ),
            self._make_result(
                "https://github.com/example/repo",
                "example/repo",
                "repo content " * 20,
            ),
        ]

        with patch.object(agent, "_should_use_ai", return_value=False):
            doc = await agent._build_section_document(results)

        assert doc.cleanup_method == "heuristic"
        assert len(doc.entries) == 1
        assert doc.entries[0].url == "https://github.com/example/repo"


# ============== finalize_document 测试 ==============

class TestFinalizeDocument:
    def test_aggregates_fields(self):
        agent = MagicMock(spec=CrawlerAgent)
        doc = SectionDocument(
            section_name="test",
            entries=[
                SourceEntry(cleaned_content="aaa", word_count=3),
                SourceEntry(cleaned_content="bbb", word_count=3),
            ],
        )
        CrawlerAgent._finalize_document(agent, doc)
        assert doc.cleaned_count == 2
        assert doc.total_word_count == 6
        assert "aaa" in doc.merged_content
        assert "bbb" in doc.merged_content
        assert "---" in doc.merged_content


# ============== Orchestrator 收集文档测试 ==============

class TestOrchestratorSectionDocuments:
    def test_init_empty_documents(self):
        orch = DigestOrchestrator()
        assert orch.get_section_documents() == []

    def test_get_section_documents_returns_list(self):
        orch = DigestOrchestrator()
        doc = SectionDocument(section_name="test", source_count=3)
        orch._section_documents.append(doc)
        docs = orch.get_section_documents()
        assert len(docs) == 1
        assert docs[0].section_name == "test"


# ============== _should_use_ai 测试 ==============

class TestShouldUseAI:
    def test_returns_false_when_ai_not_configured(self):
        section = PlannedSection(name="test", source_type="keyword")
        plan = SourceCrawlPlan(
            section_name="test", active_keywords=[], active_url_sources=[], active_rss_sources=[],
            skipped_source_ids=[], recommended_engine="sogou", adjusted_max_items=5,
        )
        agent = CrawlerAgent(section, plan, MagicMock(), {})

        with patch("ai.config.ai_settings") as mock_ai:
            mock_ai.is_configured = False
            assert agent._should_use_ai() is False

    def test_returns_true_when_ai_configured(self):
        section = PlannedSection(name="test", source_type="keyword")
        plan = SourceCrawlPlan(
            section_name="test", active_keywords=[], active_url_sources=[], active_rss_sources=[],
            skipped_source_ids=[], recommended_engine="sogou", adjusted_max_items=5,
        )
        agent = CrawlerAgent(section, plan, MagicMock(), {})

        with patch("ai.config.ai_settings") as mock_ai:
            mock_ai.is_configured = True
            assert agent._should_use_ai() is True
