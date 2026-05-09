package com.nanmuli.blog.infrastructure.crawler;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.*;
import org.springframework.http.client.HttpComponentsClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;

import jakarta.annotation.PreDestroy;
import java.io.IOException;
import java.util.*;

import org.apache.hc.client5.http.config.RequestConfig;
import org.apache.hc.client5.http.impl.classic.CloseableHttpClient;
import org.apache.hc.client5.http.impl.classic.HttpClients;
import org.apache.hc.client5.http.impl.io.PoolingHttpClientConnectionManager;
import org.apache.hc.core5.util.Timeout;

/**
 * Python 爬虫服务任务 API 客户端
 *
 * 封装 /api/v1/tasks/* 端点调用，替代原来逐个调用 /crawl/* 的编排模式。
 * 使用连接池复用 TCP 连接，避免高并发场景下端口耗尽。
 */
@Slf4j
@Component
public class CrawlerTaskClient {

    private final RestTemplate restTemplate;
    private final CloseableHttpClient httpClient;
    private final String baseUrl;
    private final String apiKey;
    private final ObjectMapper objectMapper;

    public CrawlerTaskClient(
            @Value("${crawler.service.base-url:http://localhost:8500}") String baseUrl,
            @Value("${crawler.service.api-key:}") String apiKey,
            @Value("${crawler.service.connect-timeout:10000}") int connectTimeout,
            @Value("${crawler.service.read-timeout:30000}") int readTimeout,
            @Value("${crawler.http.pool.max-total:20}") int maxTotal,
            @Value("${crawler.http.pool.max-per-route:10}") int maxPerRoute,
            ObjectMapper objectMapper) {
        this.baseUrl = baseUrl;
        this.apiKey = apiKey;
        this.objectMapper = objectMapper;

        PoolingHttpClientConnectionManager cm = new PoolingHttpClientConnectionManager();
        cm.setMaxTotal(maxTotal);
        cm.setDefaultMaxPerRoute(maxPerRoute);

        this.httpClient = HttpClients.custom()
                .setConnectionManager(cm)
                .setDefaultRequestConfig(RequestConfig.custom()
                        .setConnectTimeout(Timeout.ofMilliseconds(connectTimeout))
                        .setResponseTimeout(Timeout.ofMilliseconds(readTimeout))
                        .build())
                .build();

        HttpComponentsClientHttpRequestFactory factory = new HttpComponentsClientHttpRequestFactory(httpClient);
        this.restTemplate = new RestTemplate(factory);
        log.info("[CrawlerTaskClient] initialized: baseUrl={}, connectTimeout={}ms, readTimeout={}ms",
                baseUrl, connectTimeout, readTimeout);
    }

    @PreDestroy
    public void close() throws IOException {
        if (httpClient != null) {
            httpClient.close();
            log.info("[CrawlerTaskClient] closed");
        }
    }

    /**
     * 创建异步任务（Python 负责爬取 + AI 整理）
     *
     * @return Python 侧任务 ID
     */
    public int createTask(String taskType, String url, String keyword,
                          String searchEngine, Integer maxDepth, Integer maxPages,
                          String aiTemplate, String timeRange) {
        Map<String, Object> body = new HashMap<>();
        body.put("task_type", taskType);
        if (url != null) body.put("url", url);
        if (keyword != null) body.put("keyword", keyword);
        if (searchEngine != null) body.put("search_engine", searchEngine);
        if (maxDepth != null) body.put("max_depth", maxDepth);
        if (maxPages != null) body.put("max_pages", maxPages);
        if (aiTemplate != null) body.put("ai_template", aiTemplate);
        if (timeRange != null) body.put("time_range", timeRange);

        JsonNode resp = post("/api/v1/tasks", body);
        int pythonTaskId = resp.path("id").asInt();
        if (pythonTaskId <= 0) {
            throw new RuntimeException("Python 返回无效任务 ID: " + resp);
        }
        log.info("[CrawlerTaskClient] created Python task: id={}, type={}", pythonTaskId, taskType);
        return pythonTaskId;
    }

    /**
     * 获取任务详情（包含 AI 结果）
     */
    public Optional<Map<String, Object>> getTask(int pythonTaskId) {
        try {
            JsonNode resp = get("/api/v1/tasks/" + pythonTaskId);
            return Optional.of(toMap(resp));
        } catch (Exception e) {
            log.warn("[CrawlerTaskClient] getTask failed for pythonTaskId={}: {}", pythonTaskId, e.getMessage());
            return Optional.empty();
        }
    }

    /**
     * 列表查询任务
     */
    public Map<String, Object> listTasks(int page, int size, Integer status, String taskType) {
        StringBuilder sb = new StringBuilder("/api/v1/tasks?page=" + page + "&size=" + size);
        if (status != null) sb.append("&status=").append(status);
        if (taskType != null) sb.append("&task_type=").append(taskType);
        JsonNode resp = get(sb.toString());
        return toMap(resp);
    }

    /**
     * 删除任务
     */
    public void deleteTask(int pythonTaskId) {
        try {
            exchange("/api/v1/tasks/" + pythonTaskId, HttpMethod.DELETE, null);
            log.info("[CrawlerTaskClient] deleted Python task: id={}", pythonTaskId);
        } catch (Exception e) {
            log.warn("[CrawlerTaskClient] deleteTask failed for pythonTaskId={}: {}", pythonTaskId, e.getMessage());
        }
    }

    /**
     * 重试任务
     */
    public void retryTask(int pythonTaskId) {
        post("/api/v1/tasks/" + pythonTaskId + "/retry", null);
        log.info("[CrawlerTaskClient] retried Python task: id={}", pythonTaskId);
    }

    /**
     * 获取任务页面列表
     */
    public Optional<Map<String, Object>> getTaskPages(int pythonTaskId) {
        try {
            JsonNode resp = get("/api/v1/tasks/" + pythonTaskId + "/pages");
            return Optional.of(toMap(resp));
        } catch (Exception e) {
            log.warn("[CrawlerTaskClient] getTaskPages failed for pythonTaskId={}: {}", pythonTaskId, e.getMessage());
            return Optional.empty();
        }
    }

    /**
     * 健康检查
     */
    public boolean healthCheck() {
        try {
            get("/health");
            return true;
        } catch (Exception e) {
            return false;
        }
    }

    // ============== HTTP Helpers ==============

    /**
     * Digest 代理 GET — 返回原始 Map 给 Controller
     */
    public Map<String, Object> proxyGet(String path) {
        JsonNode resp = get(path);
        return toMap(resp);
    }

    /**
     * Digest 代理 POST — 返回原始 Map 给 Controller
     */
    public Map<String, Object> proxyPost(String path) {
        JsonNode resp = post(path, null);
        return toMap(resp);
    }

    private JsonNode get(String path) {
        ResponseEntity<JsonNode> resp = restTemplate.exchange(
                baseUrl + path, HttpMethod.GET, new HttpEntity<>(authHeaders()), JsonNode.class);
        JsonNode body = resp.getBody();
        if (body == null) throw new RuntimeException("Empty response from Python service: GET " + path);
        return body;
    }

    private JsonNode post(String path, Map<String, Object> body) {
        HttpEntity<Map<String, Object>> entity = new HttpEntity<>(body, authHeaders());
        ResponseEntity<JsonNode> resp = restTemplate.exchange(
                baseUrl + path, HttpMethod.POST, entity, JsonNode.class);
        JsonNode respBody = resp.getBody();
        if (respBody == null) throw new RuntimeException("Empty response from Python service: POST " + path);
        return respBody;
    }

    private void exchange(String path, HttpMethod method, Map<String, Object> body) {
        HttpEntity<Map<String, Object>> entity = new HttpEntity<>(body, authHeaders());
        restTemplate.exchange(baseUrl + path, method, entity, Object.class);
    }

    private HttpHeaders authHeaders() {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        if (apiKey != null && !apiKey.isBlank()) {
            headers.set("X-API-Key", apiKey);
        }
        return headers;
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> toMap(JsonNode node) {
        if (node == null) return Collections.emptyMap();
        return objectMapper.convertValue(node, Map.class);
    }
}
