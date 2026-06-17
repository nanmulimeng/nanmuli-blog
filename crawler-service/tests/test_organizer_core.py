"""AI Organizer 核心逻辑测试：JSON 解析、截断、验证、分类映射"""

import pytest
from ai.organizer import (
    _truncate_at_paragraph_boundary, _normalize,
    _normalize_list, _normalize_category, _extract_message_content,
    ContentOrganizer, OrganizedContent, DigestContent, DigestPageContent,
    CATEGORY_ALIASES, ALLOWED_CATEGORIES, DIGEST_CATEGORY_MAP,
    DIGEST_SYSTEM_PROMPT, InvalidOutputError, digest_relevance_score,
)
from ai.utils import extract_json as _extract_json
from ai.config import AiSettings


# ============== _extract_json ==============

class TestExtractJson:
    def test_plain_json(self):
        raw = '{"title": "hello", "count": 42}'
        assert _extract_json(raw) == raw

    def test_json_in_code_block(self):
        raw = '```json\n{"title": "hello"}\n```'
        result = _extract_json(raw)
        assert '"title"' in result and result.strip().startswith("{")

    def test_json_in_plain_code_block(self):
        raw = '```\n{"title": "hello"}\n```'
        result = _extract_json(raw)
        assert '"title"' in result

    def test_json_with_surrounding_text(self):
        raw = 'Here is the result:\n{"title": "hello", "tags": ["a"]}\nDone.'
        result = _extract_json(raw)
        assert result == '{"title": "hello", "tags": ["a"]}'

    def test_nested_json(self):
        raw = '{"outer": {"inner": "value"}, "list": [1, 2]}'
        assert _extract_json(raw) == raw

    def test_json_with_escaped_quotes(self):
        raw = r'{"title": "He said \"hello\"", "x": 1}'
        result = _extract_json(raw)
        import json
        parsed = json.loads(result)
        assert parsed["title"] == 'He said "hello"'

    def test_no_json_raises(self):
        with pytest.raises(ValueError, match="No JSON found"):
            _extract_json("no json here")

    def test_unbalanced_json_raises(self):
        with pytest.raises(ValueError, match="No balanced JSON"):
            _extract_json('{"title": "incomplete"')

    def test_json_with_braces_in_strings(self):
        raw = '{"title": "use {curly} braces", "x": 1}'
        result = _extract_json(raw)
        assert "curly" in result


# ============== _truncate_at_paragraph_boundary ==============

class TestTruncate:
    def test_short_text_unchanged(self):
        text = "short text"
        assert _truncate_at_paragraph_boundary(text, 100) == text

    def test_truncate_at_paragraph(self):
        text = "A" * 50 + "\n\n" + "B" * 50 + "\n\n" + "C" * 200
        result = _truncate_at_paragraph_boundary(text, 120)
        assert result.endswith("[...内容过长已截断]")
        assert "AAA" in result
        assert "CCC" not in result

    def test_truncate_at_newline_fallback(self):
        text = "A" * 90 + "\n" + "B" * 90
        result = _truncate_at_paragraph_boundary(text, 100)
        assert result.endswith("[...内容过长已截断]")

    def test_truncate_hard_cut(self):
        text = "A" * 200
        result = _truncate_at_paragraph_boundary(text, 100)
        assert len(result) < 200
        assert result.endswith("[...内容过长已截断]")


# ============== _normalize ==============

class TestNormalize:
    def test_strip(self):
        assert _normalize("  hello  ") == "hello"

    def test_none(self):
        assert _normalize(None) == ""

    def test_int(self):
        assert _normalize(42) == "42"

    def test_empty(self):
        assert _normalize("") == ""


# ============== _normalize_list ==============

class TestNormalizeList:
    def test_dedup_and_limit(self):
        result = _normalize_list(["a", "b", "a", "c", "b"], max_items=3)
        assert result == ["a", "b", "c"]

    def test_empty_strings_filtered(self):
        result = _normalize_list(["a", "", "  ", "b"], max_items=10)
        assert result == ["a", "b"]

    def test_not_list_returns_empty(self):
        assert _normalize_list("not a list", max_items=10) == []

    def test_max_items(self):
        items = [f"item{i}" for i in range(20)]
        result = _normalize_list(items, max_items=5)
        assert len(result) == 5


# ============== _normalize_category ==============

class TestNormalizeCategory:
    def test_alias_mapping(self):
        assert _normalize_category("backend") == "后端开发"
        assert _normalize_category("ai") == "AI与机器学习"
        assert _normalize_category("other") == "其他"

    def test_case_insensitive(self):
        assert _normalize_category("Backend") == "后端开发"
        assert _normalize_category("BACKEND") == "后端开发"

    def test_valid_category_unchanged(self):
        assert _normalize_category("后端开发") == "后端开发"

    def test_empty_returns_empty(self):
        assert _normalize_category("") == ""


class TestDigestRelevanceScore:
    def _page(self, title, url, markdown=""):
        return DigestPageContent(
            category="tech_article",
            url=url,
            title=title,
            summary=title,
            markdown=markdown or title,
            source_name="test",
            source_level="medium",
        )

    def test_penalizes_real_low_value_digest_samples(self):
        bad_pages = [
            self._page(
                "Security Jobs in Penang - June 2026 | Jobstreet",
                "https://my.jobstreet.com/security-jobs/in-Penang",
            ),
            self._page(
                "Security+ (Plus) Certification | CompTIA",
                "https://www.comptia.org/en-us/certifications/security/",
            ),
            self._page(
                "What is Software? Definition, Examples, & Types Explained",
                "https://www.simplilearn.com/tutorials/programming-tutorial/what-is-software",
            ),
            self._page(
                "Download software for Windows",
                "https://en.softonic.com/windows",
            ),
        ]

        assert all(digest_relevance_score(page) <= 0 for page in bad_pages)

    def test_keeps_specific_engineering_article_positive(self):
        page = self._page(
            "GitHub Copilot coding agent updates",
            "https://github.blog/changelog/2026-06-01-copilot-coding-agent-updates/",
            "GitHub Copilot coding agent now supports software engineering workflows.",
        )

        assert digest_relevance_score(page) > 0

    def test_unknown_falls_back_to_default(self):
        assert _normalize_category("quantum") == "其他"

    def test_all_aliases(self):
        for alias, expected in CATEGORY_ALIASES.items():
            result = _normalize_category(alias)
            assert result == expected, f"alias '{alias}' -> '{result}', expected '{expected}'"


# ============== _extract_message_content ==============

class TestExtractMessageContent:
    def test_string(self):
        assert _extract_message_content("hello") == "hello"

    def test_array_of_dicts(self):
        content = [
            {"type": "text", "text": "first"},
            {"type": "output_text", "text": "second"},
        ]
        assert _extract_message_content(content) == "first\nsecond"

    def test_none(self):
        assert _extract_message_content(None) == ""

    def test_mixed(self):
        content = [None, "raw", {"type": "text", "text": "dict"}]
        assert _extract_message_content(content) == "raw\ndict"


# ============== ContentOrganizer parsing ==============

class TestParseOrganizedContent:
    def setup_method(self):
        settings = AiSettings(ai_enabled=False, ai_api_key="")
        self.organizer = ContentOrganizer(settings=settings)

    def test_valid_content(self):
        response = """{
            "title": "Spring Boot Guide",
            "summary": "This summary is definitely long enough for validation purposes.",
            "keyPoints": ["point 1", "point 2"],
            "tags": ["java", "spring"],
            "category": "后端开发",
            "fullContent": "This full content is definitely long enough for validation."
        }"""
        result = self.organizer._parse_organized_content(response)
        assert result.title == "Spring Boot Guide"
        assert result.tags == ["java", "spring"]
        assert result.category == "后端开发"

    def test_alias_category_mapped(self):
        response = """{
            "title": "React Guide",
            "summary": "This summary is definitely long enough for validation.",
            "keyPoints": ["point 1"],
            "tags": ["react"],
            "category": "frontend",
            "fullContent": "This full content is definitely long enough for validation."
        }"""
        result = self.organizer._parse_organized_content(response)
        assert result.category == "前端开发"

    def test_dedup_key_points(self):
        response = """{
            "title": "Title",
            "summary": "This summary is definitely long enough for validation.",
            "keyPoints": ["alpha point", "beta point", "alpha point", "gamma point"],
            "tags": ["tag"],
            "category": "其他",
            "fullContent": "This full content is definitely long enough for validation."
        }"""
        result = self.organizer._parse_organized_content(response)
        assert result.key_points == ["alpha point", "beta point", "gamma point"]

    def test_empty_title_rejected(self):
        response = """{
            "title": "",
            "summary": "valid summary text for testing",
            "keyPoints": ["valid point text"],
            "tags": ["tag"],
            "category": "其他",
            "fullContent": "valid content for testing purposes"
        }"""
        with pytest.raises(InvalidOutputError, match="Missing title"):
            self.organizer._parse_organized_content(response)

    def test_short_summary_rejected(self):
        response = """{
            "title": "Title",
            "summary": "short",
            "keyPoints": ["valid point text"],
            "tags": ["tag"],
            "category": "其他",
            "fullContent": "valid content long enough for testing"
        }"""
        with pytest.raises(InvalidOutputError, match="Summary too short"):
            self.organizer._parse_organized_content(response)

    def test_no_tags_rejected(self):
        response = """{
            "title": "Title",
            "summary": "This summary is definitely long enough.",
            "keyPoints": ["valid point text"],
            "tags": [],
            "category": "其他",
            "fullContent": "This full content is definitely long enough."
        }"""
        with pytest.raises(InvalidOutputError, match="Missing tags"):
            self.organizer._parse_organized_content(response)

    def test_invalid_category_falls_back(self):
        response = """{
            "title": "Title",
            "summary": "This summary is definitely long enough.",
            "keyPoints": ["valid point text"],
            "tags": ["tag"],
            "category": "invalid_category",
            "fullContent": "This full content is definitely long enough."
        }"""
        result = self.organizer._parse_organized_content(response)
        assert result.category == "其他"

    def test_strips_whitespace(self):
        response = """{
            "title": "  Title  ",
            "summary": "  This summary is long enough.  ",
            "keyPoints": [" point 1 ", "point 2"],
            "tags": [" java ", "spring"],
            "category": "后端开发",
            "fullContent": "  This full content is long enough.  "
        }"""
        result = self.organizer._parse_organized_content(response)
        assert result.title == "Title"
        assert result.key_points == ["point 1", "point 2"]


class TestParseDigestContent:
    def setup_method(self):
        settings = AiSettings(ai_enabled=False, ai_api_key="")
        self.organizer = ContentOrganizer(settings=settings)

    def test_valid_digest(self):
        response = """{
            "title": "Daily Digest 2026-05-07",
            "summary": "This digest summary is definitely long enough for validation.",
            "highlight": "Big news today",
            "tags": ["ai", "cloud"],
            "fullContent": "This full digest content is definitely long enough for validation. It covers multiple topics including AI breakthroughs, cloud computing trends, open source updates, and deep technical analysis for developers who want to stay current with industry developments.",
            "sections": [
                {
                    "category": "hot_trend",
                    "categoryName": "Hot Trend",
                    "emoji": "🔥",
                    "items": [
                        {
                            "title": "AI Breakthrough",
                            "oneLiner": "New model released",
                            "sourceUrl": "https://example.com",
                            "sourceName": "example.com"
                        }
                    ]
                }
            ]
        }"""
        result = self.organizer._parse_digest_content(response)
        assert result.title == "Daily Digest 2026-05-07"
        assert len(result.sections) == 1
        assert result.sections[0].category == "hot_trend"
        assert result.sections[0].items[0].title == "AI Breakthrough"
        assert result.highlight == "Big news today"

    def test_legacy_digest_category_aliases_are_normalized(self):
        response = """{
            "title": "Daily Digest 2026-05-07",
            "summary": "This digest summary is definitely long enough for validation.",
            "highlight": "Big news today",
            "tags": ["ai", "cloud"],
            "fullContent": "This full digest content is definitely long enough for validation. It covers AI infrastructure updates, open source project changes, and developer-facing technical articles with enough detail to pass validation.",
            "sections": [
                {
                    "category": "news",
                    "categoryName": "News",
                    "emoji": "n",
                    "items": [
                        {
                            "title": "AI infrastructure update",
                            "oneLiner": "A vendor expanded AI capacity",
                            "sourceUrl": "https://example.com/news",
                            "sourceName": "example.com"
                        }
                    ]
                },
                {
                    "category": "articles",
                    "categoryName": "Articles",
                    "emoji": "a",
                    "items": [
                        {
                            "title": "Engineering deep dive",
                            "oneLiner": "A technical article explains tradeoffs",
                            "sourceUrl": "https://example.com/article",
                            "sourceName": "example.com"
                        }
                    ]
                },
                {
                    "category": "opensource",
                    "categoryName": "Open Source",
                    "emoji": "o",
                    "items": [
                        {
                            "title": "Open source release",
                            "oneLiner": "A repository shipped a new release",
                            "sourceUrl": "https://github.com/example/repo",
                            "sourceName": "GitHub"
                        }
                    ]
                }
            ]
        }"""

        result = self.organizer._parse_digest_content(response)

        assert [section.category for section in result.sections] == [
            "hot_trend",
            "tech_article",
            "open_source",
        ]

    def test_empty_summary_rejected(self):
        response = """{
            "title": "Digest",
            "summary": "short",
            "highlight": "",
            "tags": [],
            "fullContent": "",
            "sections": []
        }"""
        with pytest.raises(InvalidOutputError):
            self.organizer._parse_digest_content(response)

    def test_no_valid_items_rejected(self):
        response = """{
            "title": "Digest",
            "summary": "This summary is definitely long enough to pass the minimum validation threshold.",
            "highlight": "h",
            "tags": ["ai"],
            "fullContent": "This full content is definitely long enough to pass the minimum validation threshold for digest content length checks. It includes comprehensive coverage of all major technology developments, open source project updates, cloud infrastructure changes, and developer tool improvements that occurred during the reporting period.",
            "sections": [
                {
                    "category": "unknown",
                    "categoryName": "Unknown",
                    "emoji": "x",
                    "items": [
                        {"title": "", "oneLiner": "", "sourceUrl": "", "sourceName": ""}
                    ]
                }
            ]
        }"""
        with pytest.raises(InvalidOutputError, match="missing valid items"):
            self.organizer._parse_digest_content(response)

    def test_incomplete_digest_items_are_dropped(self):
        response = """{
            "title": "Daily Digest 2026-05-07",
            "summary": "This digest summary is definitely long enough for validation.",
            "highlight": "Big news today",
            "tags": ["ai", "cloud"],
            "fullContent": "This full digest content is definitely long enough for validation. It covers multiple topics including AI breakthroughs, cloud computing trends, open source updates, and deep technical analysis for developers.",
            "sections": [
                {
                    "category": "hot_trend",
                    "categoryName": "Hot Trend",
                    "emoji": "🔥",
                    "items": [
                        {
                            "title": "AI Breakthrough",
                            "oneLiner": "New model released",
                            "sourceUrl": "https://example.com/valid",
                            "sourceName": "example.com"
                        },
                        {
                            "title": "Missing source",
                            "oneLiner": "This should not be saved",
                            "sourceUrl": "",
                            "sourceName": ""
                        }
                    ]
                }
            ]
        }"""

        result = self.organizer._parse_digest_content(response)

        assert len(result.sections[0].items) == 1
        assert result.sections[0].items[0].title == "AI Breakthrough"

    def test_unmatched_input_url_items_are_dropped(self):
        response = """{
            "title": "Daily Digest 2026-05-07",
            "summary": "This digest summary is definitely long enough for validation.",
            "highlight": "Big news today",
            "tags": ["ai", "cloud"],
            "fullContent": "This full digest content is definitely long enough for validation. It covers multiple topics including AI breakthroughs, cloud computing trends, open source updates, and deep technical analysis for developers.",
            "sections": [
                {
                    "category": "hot_trend",
                    "categoryName": "Hot Trend",
                    "emoji": "🔥",
                    "items": [
                        {
                            "title": "Valid item",
                            "oneLiner": "New model released",
                            "sourceUrl": "https://example.com/valid",
                            "sourceName": "example.com"
                        },
                        {
                            "title": "Fabricated item",
                            "oneLiner": "This URL was not in the inputs",
                            "sourceUrl": "https://fake.example.com/post",
                            "sourceName": "fake.example.com"
                        }
                    ]
                }
            ]
        }"""

        result = self.organizer._parse_digest_content(
            response,
            input_urls=frozenset({"https://example.com/valid"}),
        )

        assert [item.source_url for item in result.sections[0].items] == ["https://example.com/valid"]


# ============== Prompt builders ==============

class TestPromptBuilders:
    def setup_method(self):
        settings = AiSettings(ai_enabled=False, ai_api_key="")
        self.organizer = ContentOrganizer(settings=settings)

    def test_single_page_prompt_contains_content(self):
        prompt = self.organizer._build_single_page_prompt(
            "# Hello World\nThis is content.", "tech_summary", None
        )
        assert "Hello World" in prompt
        assert "OUTPUT_SCHEMA" not in prompt  # shouldn't be literal
        assert "title" in prompt  # schema mentions title

    def test_single_page_prompt_with_keyword_context(self):
        prompt = self.organizer._build_single_page_prompt(
            "content", "tech_summary", "原始关键词：docker\n优化关键词：docker 容器"
        )
        assert "docker" in prompt
        assert "搜索上下文" in prompt

    def test_multi_page_prompt_budget(self):
        from ai.organizer import PageContent
        pages = [
            PageContent(url=f"http://a{i}.com", title=f"Page {i}",
                        markdown="X" * 30000, word_count=30000)
            for i in range(5)
        ]
        prompt = self.organizer._build_multi_page_prompt(pages, "tech_summary", None)
        assert "来源 1" in prompt
        assert "来源 5" in prompt

    def test_digest_prompt_sorted_by_category(self):
        from ai.organizer import DigestPageContent
        pages = [
            DigestPageContent(url="http://a.com", title="Z", markdown="Z", category="open_source"),
            DigestPageContent(url="http://b.com", title="A", markdown="A", category="hot_trend"),
        ]
        prompt = self.organizer._build_digest_prompt(pages, "2026-05-07")
        assert prompt.index("hot_trend") < prompt.index("open_source")

    def test_digest_prompt_sorted_by_title_within_category(self):
        from ai.organizer import DigestPageContent
        pages = [
            DigestPageContent(url="http://z.com", title="Zulu", markdown="Z", category="open_source"),
            DigestPageContent(url="http://a.com", title="Alpha", markdown="A", category="open_source"),
        ]
        prompt = self.organizer._build_digest_prompt(pages, "2026-05-07")
        # 同分类内的条目按 source_level + content length 排序，非按 title 字母序
        # 验证两个条目都出现在 prompt 中
        assert "Alpha" in prompt
        assert "Zulu" in prompt

    def test_digest_prompt_exposes_all_source_levels(self):
        from ai.organizer import DigestPageContent
        pages = [
            DigestPageContent(
                url="http://low.example.com/post",
                title="Low confidence",
                markdown="Low confidence content",
                category="tech_article",
                source_name="low.example.com",
                source_level="low",
            )
        ]

        prompt = self.organizer._build_digest_prompt(pages, "2026-05-07")

        assert "来源可信度: low" in prompt

    def test_digest_prompt_warns_against_multi_item_listing_sources(self):
        from ai.organizer import DigestPageContent
        pages = [
            DigestPageContent(
                url="https://techcrunch.com/",
                title="TechCrunch",
                markdown="Homepage listing content with several headlines",
                category="hot_trend",
                source_name="TechCrunch",
                source_level="high",
            )
        ]

        prompt = self.organizer._build_digest_prompt(pages, "2026-05-07")

        assert "Listing-page rule" in prompt
        assert "at most one item" in prompt

    def test_digest_prompt_orders_same_source_level_by_relevance(self):
        pages = [
            DigestPageContent(
                url="https://techcrunch.com/game",
                title="Grand Theft Auto cheat service gets hacked",
                markdown="gaming account breach " * 400,
                category="hot_trend",
                source_level="high",
            ),
            DigestPageContent(
                url="https://techcrunch.com/ai-security",
                title="Meta AI support chatbot account recovery security incident",
                markdown="AI support chatbot account recovery security incident developer risk " * 80,
                category="hot_trend",
                source_level="high",
            ),
            DigestPageContent(
                url="https://techcrunch.com/space",
                title="SpaceX may issue equity in future transactions",
                markdown="space finance launch vehicle investor update " * 300,
                category="hot_trend",
                source_level="high",
            ),
        ]

        prompt = self.organizer._build_digest_prompt(pages, "2026-05-07")

        assert prompt.index("Meta AI support chatbot") < prompt.index("Grand Theft Auto")
        assert prompt.index("Meta AI support chatbot") < prompt.index("SpaceX may issue equity")

    def test_digest_system_prompt_contains_quality_guardrails(self):
        assert "事实边界" in DIGEST_SYSTEM_PROMPT
        assert "没有来源支撑" in DIGEST_SYSTEM_PROMPT
        assert "低可信" in DIGEST_SYSTEM_PROMPT
        assert "可执行影响" in DIGEST_SYSTEM_PROMPT


    def test_digest_system_prompt_contains_category_quality_contract(self):
        assert "Category Quality Contract" in DIGEST_SYSTEM_PROMPT
        assert "hot_trend: prefer new releases" in DIGEST_SYSTEM_PROMPT
        assert "open_source: require repository" in DIGEST_SYSTEM_PROMPT
        assert "tech_article: require concrete engineering takeaway" in DIGEST_SYSTEM_PROMPT
        assert "dev_tool: require install/use case" in DIGEST_SYSTEM_PROMPT
        assert "paper: require finding and practitioner impact" in DIGEST_SYSTEM_PROMPT


# ============== Constants ==============

class TestConstants:
    def test_allowed_categories_are_superset_of_aliases(self):
        for alias_target in CATEGORY_ALIASES.values():
            assert alias_target in ALLOWED_CATEGORIES, f"Alias target '{alias_target}' not in ALLOWED_CATEGORIES"

    def test_digest_category_map_keys(self):
        expected = {"hot_trend", "open_source", "tech_article", "dev_tool", "creative", "paper"}
        assert set(DIGEST_CATEGORY_MAP.keys()) == expected

    def test_digest_category_map_values_are_tuples(self):
        for key, val in DIGEST_CATEGORY_MAP.items():
            assert isinstance(val, tuple) and len(val) == 2, f"{key}: {val}"


# ============== ContentOrganizer availability ==============

class TestAvailability:
    def test_not_available_when_disabled(self):
        settings = AiSettings(ai_enabled=False, ai_api_key="")
        org = ContentOrganizer(settings=settings)
        assert org.is_available is False

    def test_not_available_when_no_key(self):
        settings = AiSettings(ai_enabled=True, ai_api_key="")
        org = ContentOrganizer(settings=settings)
        assert org.is_available is False

    def test_available_when_configured(self):
        settings = AiSettings(ai_enabled=True, ai_api_key="sk-test", ai_model="test")
        org = ContentOrganizer(settings=settings)
        assert org.is_available is True
