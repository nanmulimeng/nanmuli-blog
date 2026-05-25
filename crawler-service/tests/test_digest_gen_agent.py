"""DigestGenAgent 日报生成 Agent 测试

覆盖：
- DigestGenAgentResult 数据模型
- DigestGenAgent._precheck()
- DigestGenAgent._build_digest_pages()
- DigestGenAgent.execute() 成功/失败/降级
- Orchestrator Phase 1.5 集成
- TaskExecutor _save_pre_generated_digest + 回退
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass, field

from crawler.digest_gen_agent import DigestGenAgent, DigestGenAgentResult
from crawler.section_document import SectionDocument, SourceEntry
from crawler.digest_orchestrator import DigestOrchestrator


# ============== 数据模型测试 ==============

class TestDigestGenAgentResult:
    def test_defaults(self):
        result = DigestGenAgentResult(success=False)
        assert result.digest_content is None
        assert result.error is None
        assert result.tokens_used == 0
        assert result.duration_ms == 0

    def test_success_with_content(self):
        mock_content = MagicMock()
        result = DigestGenAgentResult(
            success=True, digest_content=mock_content,
            tokens_used=500, duration_ms=3000,
        )
        assert result.success is True
        assert result.digest_content is mock_content
        assert result.tokens_used == 500


# ============== _precheck 测试 ==============

class TestPrecheck:
    def _make_agent(self) -> DigestGenAgent:
        return DigestGenAgent(config_snapshot={})

    def test_empty_documents(self):
        agent = self._make_agent()
        assert agent._precheck([]) is False

    def test_few_entries(self):
        agent = self._make_agent()
        doc = SectionDocument(entries=[
            SourceEntry(url="https://a.com", title="A", cleaned_content="x" * 200),
        ])
        with patch("ai.config.ai_settings") as mock_ai:
            mock_ai.is_configured = True
            assert agent._precheck([doc]) is False

    def test_enough_entries(self):
        agent = self._make_agent()
        doc = SectionDocument(entries=[
            SourceEntry(url=f"https://a{i}.com", title=f"T{i}", cleaned_content="x" * 200)
            for i in range(5)
        ])
        with patch("ai.config.ai_settings") as mock_ai:
            mock_ai.is_configured = True
            assert agent._precheck([doc]) is True

    def test_ai_not_configured(self):
        agent = self._make_agent()
        doc = SectionDocument(entries=[
            SourceEntry(url=f"https://a{i}.com", title=f"T{i}", cleaned_content="x" * 200)
            for i in range(5)
        ])
        with patch("ai.config.ai_settings") as mock_ai:
            mock_ai.is_configured = False
            assert agent._precheck([doc]) is False


# ============== _build_digest_pages 测试 ==============

class TestBuildDigestPages:
    def _make_agent(self) -> DigestGenAgent:
        return DigestGenAgent(config_snapshot={})

    def _make_section_doc(self, n_entries=3) -> SectionDocument:
        entries = [
            SourceEntry(
                url=f"https://github.com/test/repo{i}",
                title=f"Test Article {i}",
                cleaned_content="# Title\n\nSome content " * 20,
                source_type="keyword",
                word_count=100,
            )
            for i in range(n_entries)
        ]
        return SectionDocument(
            section_name="tech_article",
            source_count=5,
            entries=entries,
        )

    @patch("crawler.quality.SourceAuthority")
    @patch("standalone.organizer_helper._extract_summary", return_value="summary text")
    def test_converts_entries_to_pages(self, mock_summary, mock_auth):
        mock_auth.score.return_value = {"level": "high"}
        agent = self._make_agent()
        doc = self._make_section_doc(3)
        pages = agent._build_digest_pages([doc])

        assert len(pages) == 3
        assert pages[0].url == "https://github.com/test/repo0"
        assert pages[0].title == "Test Article 0"
        assert pages[0].category == "open_source"
        assert pages[0].source_level == "high"
        assert pages[0].page_id is None
        assert len(pages[0].markdown) >= 100

    @patch("crawler.quality.SourceAuthority")
    @patch("standalone.organizer_helper._extract_summary", return_value="")
    def test_skips_short_content(self, mock_summary, mock_auth):
        mock_auth.score.return_value = {"level": "medium"}
        agent = self._make_agent()
        doc = SectionDocument(entries=[
            SourceEntry(url="https://a.com", title="Short", cleaned_content="hi"),
            SourceEntry(url="https://b.com", title="Valid", cleaned_content="x" * 200),
        ])
        pages = agent._build_digest_pages([doc])
        assert len(pages) == 1
        assert pages[0].title == "Valid"

    @patch("crawler.quality.SourceAuthority")
    @patch("standalone.organizer_helper._extract_summary", return_value="sum")
    def test_multiple_documents(self, mock_summary, mock_auth):
        mock_auth.score.return_value = {"level": "medium"}
        agent = self._make_agent()
        doc1 = self._make_section_doc(2)
        doc2 = self._make_section_doc(2)
        pages = agent._build_digest_pages([doc1, doc2])
        assert len(pages) == 4


# ============== execute 测试 ==============

class TestDigestGenAgentExecute:
    def _make_agent(self) -> DigestGenAgent:
        return DigestGenAgent(config_snapshot={})

    def _make_docs(self, n=5) -> list:
        entries = [
            SourceEntry(
                url=f"https://example.com/{i}",
                title=f"Test {i}",
                cleaned_content="Valid content " * 20,
            )
            for i in range(n)
        ]
        return [SectionDocument(section_name="test", entries=entries)]

    @pytest.mark.asyncio
    async def test_precheck_fails_returns_false(self):
        agent = self._make_agent()
        result = await agent.execute([], "2026-05-24")
        assert result.success is False
        assert "precheck" in result.error

    @pytest.mark.asyncio
    async def test_ai_success(self):
        agent = self._make_agent()
        docs = self._make_docs(5)
        mock_digest = MagicMock()
        mock_digest.tokens_used = 1000
        mock_digest.duration_ms = 5000

        with patch.object(agent, "_precheck", return_value=True), \
             patch("crawler.quality.SourceAuthority") as mock_sa, \
             patch("standalone.repository") as mock_repo, \
             patch("ai.organizer.ContentOrganizer") as mock_org_cls:
            mock_sa.preload_authority_cache = AsyncMock()
            mock_repo.get_recent_highlights = AsyncMock(return_value=[])
            mock_org = MagicMock()
            mock_org.generate_digest = AsyncMock(return_value=mock_digest)
            mock_org.close = AsyncMock()
            mock_org_cls.return_value = mock_org

            result = await agent.execute(docs, "2026-05-24")

        assert result.success is True
        assert result.digest_content is mock_digest
        assert result.tokens_used == 1000
        assert result.duration_ms == 5000

    @pytest.mark.asyncio
    async def test_ai_failure_returns_error(self):
        agent = self._make_agent()
        docs = self._make_docs(5)

        with patch.object(agent, "_precheck", return_value=True), \
             patch("crawler.quality.SourceAuthority") as mock_sa, \
             patch("standalone.repository") as mock_repo, \
             patch("ai.organizer.ContentOrganizer") as mock_org_cls:
            mock_sa.preload_authority_cache = AsyncMock()
            mock_repo.get_recent_highlights = AsyncMock(return_value=[])
            mock_org = MagicMock()
            mock_org.generate_digest = AsyncMock(side_effect=Exception("AI error"))
            mock_org.close = AsyncMock()
            mock_org_cls.return_value = mock_org

            result = await agent.execute(docs, "2026-05-24")

        assert result.success is False
        assert "AI error" in result.error

    @pytest.mark.asyncio
    async def test_no_valid_pages_after_build(self):
        agent = self._make_agent()
        docs = [SectionDocument(section_name="empty", entries=[])]

        with patch.object(agent, "_precheck", return_value=True):
            result = await agent.execute(docs, "2026-05-24")

        assert result.success is False
        assert "no valid pages" in result.error


# ============== Orchestrator 集成测试 ==============

class TestOrchestratorDigestGen:
    def test_init_digest_result_none(self):
        orch = DigestOrchestrator()
        assert orch.get_digest_result() is None

    def test_get_digest_result_returns_value(self):
        orch = DigestOrchestrator()
        mock_result = DigestGenAgentResult(success=True)
        orch._digest_result = mock_result
        assert orch.get_digest_result().success is True


# ============== TaskExecutor _save_pre_generated_digest 测试 ==============

class TestSavePreGeneratedDigest:
    def _make_executor(self):
        from standalone.task_executor import TaskExecutor
        return TaskExecutor(max_concurrent=1)

    @pytest.mark.asyncio
    async def test_save_success(self):
        executor = self._make_executor()

        mock_digest = MagicMock()
        mock_digest.title = "技术日报 | 2026-05-24"
        mock_digest.summary = "summary"
        mock_digest.tags = ["AI"]
        mock_digest.full_content = "# Daily"
        mock_digest.duration_ms = 5000
        mock_digest.tokens_used = 1000
        mock_digest.highlight = "highlight text"
        mock_digest.sections = []

        pre_gen = DigestGenAgentResult(
            success=True, digest_content=mock_digest,
        )

        with patch("standalone.task_executor.repo") as mock_repo, \
             patch("standalone.organizer_helper.serialize_digest_sections", return_value=[]), \
             patch("standalone.organizer_helper._is_highlight_duplicate", return_value=False):
            mock_repo.get_pages_by_task = AsyncMock(return_value=[])
            mock_repo.get_recent_highlights = AsyncMock(return_value=[])
            mock_repo.save_digest_results = AsyncMock()

            result = await executor._save_pre_generated_digest(
                task_id=1,
                task={"digest_date": "2026-05-24"},
                pre_generated=pre_gen,
            )

        assert result is True
        mock_repo.save_digest_results.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_failure_returns_false(self):
        executor = self._make_executor()

        mock_digest = MagicMock()
        mock_digest.highlight = "hl"
        mock_digest.sections = []
        pre_gen = DigestGenAgentResult(success=True, digest_content=mock_digest)

        with patch("standalone.task_executor.repo") as mock_repo, \
             patch("standalone.organizer_helper.serialize_digest_sections", return_value=[]), \
             patch("standalone.organizer_helper._is_highlight_duplicate", return_value=False):
            mock_repo.get_pages_by_task = AsyncMock(return_value=[])
            mock_repo.get_recent_highlights = AsyncMock(return_value=[])
            mock_repo.save_digest_results = AsyncMock(side_effect=Exception("DB error"))

            result = await executor._save_pre_generated_digest(
                task_id=1,
                task={"digest_date": "2026-05-24"},
                pre_generated=pre_gen,
            )

        assert result is False
