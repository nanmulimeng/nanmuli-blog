package com.nanmuli.blog.infrastructure.crawler;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import java.lang.reflect.Method;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

class Crawl4AiCrawlerServiceTest {

    private final ObjectMapper objectMapper = new ObjectMapper();

    @Test
    void parseSingleResultShouldPreserveNestedMetadataStructure() throws Exception {
        Crawl4AiCrawlerService service = new Crawl4AiCrawlerService("http://localhost:8500", 1000);
        JsonNode node = objectMapper.readTree("""
                {
                  "success": true,
                  "url": "https://example.com",
                  "title": "Example",
                  "metadata": {
                    "search_engine": "bing",
                    "quality_eval": {
                      "verdict": "review",
                      "scores": {
                        "source": 80,
                        "content": 70
                      },
                      "flags": ["fresh", "official"]
                    }
                  }
                }
                """);

        Method method = Crawl4AiCrawlerService.class.getDeclaredMethod("parseSingleResult", JsonNode.class);
        method.setAccessible(true);

        CrawlResult result = (CrawlResult) method.invoke(service, node);

        assertNotNull(result.getMetadata());
        assertEquals("bing", result.getMetadata().get("search_engine"));

        Object qualityEval = result.getMetadata().get("quality_eval");
        assertInstanceOf(Map.class, qualityEval);

        Map<?, ?> qualityMap = (Map<?, ?>) qualityEval;
        assertEquals("review", qualityMap.get("verdict"));
        assertInstanceOf(Map.class, qualityMap.get("scores"));
        assertInstanceOf(List.class, qualityMap.get("flags"));
    }
}
