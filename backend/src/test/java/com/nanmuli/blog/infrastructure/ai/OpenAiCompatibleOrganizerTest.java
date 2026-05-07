package com.nanmuli.blog.infrastructure.ai;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.nanmuli.blog.application.config.ConfigAppService;
import com.nanmuli.blog.domain.webcollector.AiContentOrganizer;
import com.nanmuli.blog.domain.webcollector.AiOrganizerException;
import com.nanmuli.blog.domain.webcollector.AiTemplate;
import com.nanmuli.blog.domain.webcollector.ContentCategory;
import org.junit.jupiter.api.Test;

import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.mock;

class OpenAiCompatibleOrganizerTest {

    private final OpenAiCompatibleOrganizer organizer = new OpenAiCompatibleOrganizer(
            new AiConfig(mock(ConfigAppService.class)),
            new ObjectMapper()
    );

    @Test
    void buildSinglePagePromptShouldIncludeKeywordContext() throws Exception {
        Method method = OpenAiCompatibleOrganizer.class.getDeclaredMethod(
                "buildSinglePagePrompt", String.class, AiTemplate.class, String.class);
        method.setAccessible(true);

        String prompt = (String) method.invoke(
                organizer,
                "# Docker Guide",
                AiTemplate.TECH_SUMMARY,
                "originalKeyword=docker\noptimizedKeyword=docker container\nsearchVariants=docker container | docker tutorial"
        );

        assertTrue(prompt.contains("docker container"));
        assertTrue(prompt.contains("docker tutorial"));
    }

    @Test
    void buildMultiPagePromptShouldIncludeKeywordContext() throws Exception {
        Method method = OpenAiCompatibleOrganizer.class.getDeclaredMethod(
                "buildMultiPagePrompt", List.class, AiTemplate.class, String.class);
        method.setAccessible(true);

        AiContentOrganizer.PageContent page = new AiContentOrganizer.PageContent();
        page.title = "Spring Boot Guide";
        page.url = "https://example.com/spring";
        page.markdown = "Spring Boot content";

        String prompt = (String) method.invoke(
                organizer,
                List.of(page),
                AiTemplate.TECH_SUMMARY,
                "originalKeyword=spring boot\nsearchVariants=spring boot | spring boot tutorial"
        );

        assertTrue(prompt.contains("spring boot tutorial"));
        assertTrue(prompt.contains("Spring Boot Guide"));
    }

    @Test
    void parseDigestContentShouldCoerceNonStringFieldsSafely() throws Exception {
        Method method = OpenAiCompatibleOrganizer.class.getDeclaredMethod("parseDigestContent", String.class);
        method.setAccessible(true);

        String response = """
                {
                  "title": 20260507,
                  "summary": {"value":"digest summary is long enough"},
                  "highlight": ["top"],
                  "tags": ["ai", 42],
                  "fullContent": {"markdown":"This digest full content is definitely long enough."},
                  "sections": [
                    {
                      "category": "open_source",
                      "categoryName": {"name":"Open Source"},
                      "emoji": ["star"],
                      "items": [
                        {
                          "title": 7,
                          "oneLiner": {"text":"one line"},
                          "sourceUrl": 88,
                          "sourceName": ["github.com"]
                        }
                      ]
                    }
                  ]
                }
                """;

        AiContentOrganizer.DigestContent digest =
                (AiContentOrganizer.DigestContent) method.invoke(organizer, response);

        assertEquals("20260507", digest.title);
        assertEquals("{value=digest summary is long enough}", digest.summary);
        assertEquals("[top]", digest.highlight);
        assertEquals(List.of("ai", "42"), digest.tags);
        assertEquals("{markdown=This digest full content is definitely long enough.}", digest.fullContent);
        assertEquals("open_source", digest.sections.getFirst().category);
        assertEquals("{name=Open Source}", digest.sections.getFirst().categoryName);
        assertEquals("[star]", digest.sections.getFirst().emoji);
        assertEquals("7", digest.sections.getFirst().items.getFirst().title);
        assertEquals("{text=one line}", digest.sections.getFirst().items.getFirst().oneLiner);
        assertEquals("88", digest.sections.getFirst().items.getFirst().sourceUrl);
        assertEquals("[github.com]", digest.sections.getFirst().items.getFirst().sourceName);
    }

    @Test
    void parseOrganizedContentShouldNormalizeMetadataAndAliases() throws Exception {
        Method method = OpenAiCompatibleOrganizer.class.getDeclaredMethod("parseOrganizedContent", String.class);
        method.setAccessible(true);

        String response = """
                {
                  "title": "  Spring Guide  ",
                  "summary": "  This summary is definitely long enough.  ",
                  "keyPoints": [" point 1 ", "", "point 1", "point 2"],
                  "tags": [" java ", "", "java", "spring"],
                  "category": "backend",
                  "fullContent": "  This full content is definitely long enough for validation.  "
                }
                """;

        AiContentOrganizer.OrganizedContent content =
                (AiContentOrganizer.OrganizedContent) method.invoke(organizer, response);

        assertEquals("Spring Guide", content.title);
        assertEquals("This summary is definitely long enough.", content.summary);
        assertEquals(List.of("point 1", "point 2"), content.keyPoints);
        assertEquals(List.of("java", "spring"), content.tags);
        assertEquals("后端开发", content.category);
        assertEquals("This full content is definitely long enough for validation.", content.fullContent);
    }

    @Test
    void parseOrganizedContentShouldRejectSemanticallyEmptyPayload() throws Exception {
        Method method = OpenAiCompatibleOrganizer.class.getDeclaredMethod("parseOrganizedContent", String.class);
        method.setAccessible(true);

        String response = """
                {
                  "title": "",
                  "summary": "short",
                  "keyPoints": [],
                  "tags": [],
                  "category": "other",
                  "fullContent": ""
                }
                """;

        InvocationTargetException ex = assertThrows(InvocationTargetException.class,
                () -> method.invoke(organizer, response));
        assertTrue(ex.getCause() instanceof AiOrganizerException.InvalidOutputException);
    }

    @Test
    void parseOrganizedContentShouldRejectInvalidCategoryAndEmptyMetadata() throws Exception {
        Method method = OpenAiCompatibleOrganizer.class.getDeclaredMethod("parseOrganizedContent", String.class);
        method.setAccessible(true);

        String response = """
                {
                  "title": "Valid title",
                  "summary": "This summary is definitely long enough.",
                  "keyPoints": ["", "   "],
                  "tags": ["tag"],
                  "category": "unknown",
                  "fullContent": "This full content is definitely long enough for validation."
                }
                """;

        InvocationTargetException ex = assertThrows(InvocationTargetException.class,
                () -> method.invoke(organizer, response));
        assertTrue(ex.getCause() instanceof AiOrganizerException.InvalidOutputException);
    }

    @Test
    void parseDigestContentShouldRejectSemanticallyEmptyPayload() throws Exception {
        Method method = OpenAiCompatibleOrganizer.class.getDeclaredMethod("parseDigestContent", String.class);
        method.setAccessible(true);

        String response = """
                {
                  "title": "Daily Digest",
                  "summary": "too short",
                  "highlight": "",
                  "tags": [],
                  "fullContent": "",
                  "sections": []
                }
                """;

        InvocationTargetException ex = assertThrows(InvocationTargetException.class,
                () -> method.invoke(organizer, response));
        assertTrue(ex.getCause() instanceof AiOrganizerException.InvalidOutputException);
    }

    @Test
    void parseDigestContentShouldRejectInvalidSectionCategory() throws Exception {
        Method method = OpenAiCompatibleOrganizer.class.getDeclaredMethod("parseDigestContent", String.class);
        method.setAccessible(true);

        String response = """
                {
                  "title": "Daily Digest",
                  "summary": "This summary is definitely long enough.",
                  "highlight": "Highlight",
                  "tags": ["ai"],
                  "fullContent": "This full content is definitely long enough for validation.",
                  "sections": [
                    {
                      "category": "unknown_category",
                      "categoryName": "Unknown",
                      "emoji": "x",
                      "items": [
                        {
                          "title": "Item title",
                          "oneLiner": "One liner",
                          "sourceUrl": "https://example.com",
                          "sourceName": "example.com"
                        }
                      ]
                    }
                  ]
                }
                """;

        InvocationTargetException ex = assertThrows(InvocationTargetException.class,
                () -> method.invoke(organizer, response));
        assertTrue(ex.getCause() instanceof AiOrganizerException.InvalidOutputException);
    }

    @Test
    void buildDigestPromptShouldBeDeterministicByCategoryAndTitle() throws Exception {
        Method method = OpenAiCompatibleOrganizer.class.getDeclaredMethod("buildDigestPrompt", List.class, String.class);
        method.setAccessible(true);

        AiContentOrganizer.DigestPageContent zulu = new AiContentOrganizer.DigestPageContent();
        zulu.category = ContentCategory.OPEN_SOURCE;
        zulu.title = "Zulu";
        zulu.url = "https://example.com/zulu";
        zulu.markdown = "Zulu content";

        AiContentOrganizer.DigestPageContent alpha = new AiContentOrganizer.DigestPageContent();
        alpha.category = ContentCategory.OPEN_SOURCE;
        alpha.title = "Alpha";
        alpha.url = "https://example.com/alpha";
        alpha.markdown = "Alpha content";

        AiContentOrganizer.DigestPageContent trend = new AiContentOrganizer.DigestPageContent();
        trend.category = ContentCategory.HOT_TREND;
        trend.title = "Trend";
        trend.url = "https://example.com/trend";
        trend.markdown = "Trend content";

        String prompt = (String) method.invoke(organizer, List.of(zulu, trend, alpha), "2026-05-07");

        assertTrue(prompt.indexOf("hot_trend") < prompt.indexOf("open_source"));
        assertTrue(prompt.indexOf("Alpha") < prompt.indexOf("Zulu"));
    }

    @Test
    void extractMessageContentShouldSupportArrayPayload() throws Exception {
        Method method = OpenAiCompatibleOrganizer.class.getDeclaredMethod("extractMessageContent", Object.class);
        method.setAccessible(true);

        String content = (String) method.invoke(organizer, List.of(
                Map.of("type", "text", "text", "first"),
                Map.of("type", "output_text", "text", "second")
        ));

        assertEquals("first\nsecond", content);
    }
}
