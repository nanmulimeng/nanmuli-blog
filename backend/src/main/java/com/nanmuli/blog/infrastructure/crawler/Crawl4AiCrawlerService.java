package com.nanmuli.blog.infrastructure.crawler;

import com.fasterxml.jackson.databind.JsonNode;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.*;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Crawl4AI HTTP 调用实现
 */
@Slf4j
@Service
public class Crawl4AiCrawlerService implements CrawlerService {

    private final RestTemplate crawlerRestTemplate;
    private final String baseUrl;

    public Crawl4AiCrawlerService(
            @Value("${crawler.service.base-url:http://localhost:8500}") String baseUrl,
            @Value("${crawler.service.timeout:180000}") int timeout) {
        this.baseUrl = baseUrl;
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(10000);
        factory.setReadTimeout(timeout);
        this.crawlerRestTemplate = new RestTemplate(factory);
        log.info("[Crawler] RestTemplate initialized: baseUrl={}, timeout={}ms", baseUrl, timeout);
    }

    @Override
    public CrawlResult crawlSingle(String url, CrawlConfig config) {
        log.info("[Crawler] Single crawl: {}", url);

        try {
            Map<String, Object> request = new HashMap<>();
            request.put("url", url);
            request.put("config", buildConfigMap(config));

            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.APPLICATION_JSON);

            HttpEntity<Map<String, Object>> entity = new HttpEntity<>(request, headers);

            ResponseEntity<JsonNode> response = crawlerRestTemplate.postForEntity(
                baseUrl + "/crawl/single",
                entity,
                JsonNode.class
            );

            return parseSingleResult(response.getBody());

        } catch (Exception e) {
            log.error("[Crawler] Single crawl failed: {}", url, e);
            CrawlResult result = new CrawlResult();
            result.setSuccess(false);
            result.setUrl(url);
            result.setErrorMessage(e.getMessage());
            return result;
        }
    }

    @Override
    public List<CrawlResult> crawlDeep(String url, int maxDepth, int maxPages, CrawlConfig config) {
        log.info("[Crawler] Deep crawl: {}, depth={}, pages={}", url, maxDepth, maxPages);

        try {
            Map<String, Object> request = new HashMap<>();
            request.put("url", url);
            request.put("max_depth", maxDepth);
            request.put("max_pages", maxPages);
            request.put("config", buildConfigMap(config));

            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.APPLICATION_JSON);

            HttpEntity<Map<String, Object>> entity = new HttpEntity<>(request, headers);

            ResponseEntity<JsonNode> response = crawlerRestTemplate.postForEntity(
                baseUrl + "/crawl/deep",
                entity,
                JsonNode.class
            );

            return parseMultiResult(response.getBody());

        } catch (Exception e) {
            log.error("[Crawler] Deep crawl failed: {}", url, e);
            List<CrawlResult> results = new ArrayList<>();
            CrawlResult result = new CrawlResult();
            result.setSuccess(false);
            result.setUrl(url);
            result.setErrorMessage(e.getMessage());
            results.add(result);
            return results;
        }
    }

    @Override
    public List<CrawlResult> crawlByKeyword(String keyword, String engine, int maxResults, CrawlConfig config) {
        log.info("[Crawler] Keyword crawl: '{}' via {}", keyword, engine);

        try {
            Map<String, Object> request = new HashMap<>();
            request.put("keyword", keyword);
            request.put("engine", engine);
            request.put("max_results", maxResults);
            request.put("config", buildConfigMap(config));

            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.APPLICATION_JSON);

            HttpEntity<Map<String, Object>> entity = new HttpEntity<>(request, headers);

            ResponseEntity<JsonNode> response = crawlerRestTemplate.postForEntity(
                baseUrl + "/crawl/search",
                entity,
                JsonNode.class
            );

            List<CrawlResult> results = parseMultiResult(response.getBody());
            results.forEach(r -> r.setKeyword(keyword));
            return results;

        } catch (Exception e) {
            log.error("[Crawler] Keyword crawl failed: '{}'", keyword, e);
            List<CrawlResult> results = new ArrayList<>();
            CrawlResult result = new CrawlResult();
            result.setSuccess(false);
            result.setUrl("keyword://" + keyword);
            result.setKeyword(keyword);
            result.setErrorMessage(e.getMessage());
            results.add(result);
            return results;
        }
    }

    @Override
    public boolean healthCheck() {
        try {
            ResponseEntity<JsonNode> response = crawlerRestTemplate.getForEntity(
                baseUrl + "/health",
                JsonNode.class
            );
            return response.getStatusCode().is2xxSuccessful();
        } catch (Exception e) {
            log.warn("[Crawler] Health check failed: {}", e.getMessage());
            return false;
        }
    }

    private Map<String, Object> buildConfigMap(CrawlConfig config) {
        if (config == null) {
            config = new CrawlConfig();
        }
        Map<String, Object> map = new HashMap<>();
        map.put("text_mode", config.isTextMode());
        map.put("light_mode", config.isLightMode());
        map.put("word_count_threshold", config.getWordCountThreshold());
        map.put("excluded_tags", config.getExcludedTags());
        map.put("wait_until", config.getWaitUntil());
        map.put("page_timeout", config.getPageTimeout());
        return map;
    }

    private CrawlResult parseSingleResult(JsonNode node) {
        CrawlResult result = new CrawlResult();
        if (node == null) return result;

        result.setSuccess(node.path("success").asBoolean(false));
        result.setUrl(node.path("url").asText());
        result.setTitle(node.path("title").asText(null));
        result.setMarkdown(node.path("markdown").asText(null));
        result.setWordCount(node.path("word_count").asInt(0));
        result.setCrawlTimeMs(node.path("crawl_time_ms").asLong(0));
        result.setErrorMessage(node.path("error_message").asText(null));

        // 解析深度（深度爬取）和搜索排名（关键词搜索）
        result.setDepth(node.path("depth").asInt(0));
        result.setSearchRank(node.path("search_rank").asInt(0));

        // Parse metadata - 保留原始类型（数值、布尔等），不全部转为字符串
        JsonNode metadataNode = node.path("metadata");
        if (metadataNode.isObject()) {
            Map<String, Object> metadata = new HashMap<>();
            metadataNode.fields().forEachRemaining(entry -> {
                JsonNode val = entry.getValue();
                if (val.isBoolean()) {
                    metadata.put(entry.getKey(), val.asBoolean());
                } else if (val.isInt()) {
                    metadata.put(entry.getKey(), val.asInt());
                } else if (val.isLong()) {
                    metadata.put(entry.getKey(), val.asLong());
                } else if (val.isDouble()) {
                    metadata.put(entry.getKey(), val.asDouble());
                } else if (val.isNull()) {
                    metadata.put(entry.getKey(), null);
                } else {
                    metadata.put(entry.getKey(), val.asText());
                }
            });
            result.setMetadata(metadata);
        }

        return result;
    }

    private List<CrawlResult> parseMultiResult(JsonNode node) {
        List<CrawlResult> results = new ArrayList<>();
        if (node == null) return results;

        JsonNode pagesNode = node.path("pages");
        if (pagesNode.isArray()) {
            for (JsonNode pageNode : pagesNode) {
                results.add(parseSingleResult(pageNode));
            }
        }

        return results;
    }
}
