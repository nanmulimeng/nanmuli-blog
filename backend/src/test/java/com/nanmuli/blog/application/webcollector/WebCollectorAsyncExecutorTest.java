package com.nanmuli.blog.application.webcollector;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.nanmuli.blog.domain.webcollector.WebCollectPageRepository;
import com.nanmuli.blog.domain.webcollector.WebCollectTaskRepository;
import com.nanmuli.blog.infrastructure.crawler.CrawlerService;
import org.junit.jupiter.api.Test;

import java.lang.reflect.Method;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.mock;

class WebCollectorAsyncExecutorTest {

    private final WebCollectorAsyncExecutor executor = new WebCollectorAsyncExecutor(
            mock(WebCollectTaskRepository.class),
            mock(WebCollectPageRepository.class),
            mock(CrawlerService.class),
            new ObjectMapper()
    );

    @Test
    void buildKeywordAiContextShouldContainOriginalOptimizedAndVariants() throws Exception {
        Method method = WebCollectorAsyncExecutor.class.getDeclaredMethod(
                "buildKeywordAiContext", String.class, String.class, List.class);
        method.setAccessible(true);

        String context = (String) method.invoke(
                executor,
                "docker",
                "docker 容器",
                List.of("docker 容器", "docker tutorial", "docker 容器")
        );

        assertTrue(context.contains("原始关键词：docker"));
        assertTrue(context.contains("优化关键词：docker 容器"));
        assertTrue(context.contains("实际搜索词变体：docker 容器 | docker tutorial"));
    }

    @Test
    void buildKeywordAiContextShouldFallbackToOriginalKeywordWhenVariantsMissing() throws Exception {
        Method method = WebCollectorAsyncExecutor.class.getDeclaredMethod(
                "buildKeywordAiContext", String.class, String.class, List.class);
        method.setAccessible(true);

        String context = (String) method.invoke(executor, "redis", "redis", null);

        assertEquals("原始关键词：redis\n实际搜索词变体：redis", context);
    }

    @Test
    void buildKeywordAiMetadataShouldProduceStructuredJson() throws Exception {
        ObjectMapper objectMapper = new ObjectMapper();
        WebCollectorAsyncExecutor exec = new WebCollectorAsyncExecutor(
                mock(WebCollectTaskRepository.class),
                mock(WebCollectPageRepository.class),
                mock(CrawlerService.class),
                objectMapper
        );

        Method method = WebCollectorAsyncExecutor.class.getDeclaredMethod(
                "buildKeywordAiMetadata", String.class, String.class, List.class);
        method.setAccessible(true);

        String metadataJson = (String) method.invoke(
                exec,
                "docker",
                "docker 容器",
                List.of("docker 容器", "docker tutorial", "docker tutorial")
        );

        @SuppressWarnings("unchecked")
        Map<String, Object> metadata = objectMapper.readValue(metadataJson, Map.class);

        assertEquals("docker", metadata.get("originalKeyword"));
        assertEquals("docker 容器", metadata.get("optimizedKeyword"));
        assertEquals(List.of("docker 容器", "docker tutorial"), metadata.get("searchVariants"));
    }
}
