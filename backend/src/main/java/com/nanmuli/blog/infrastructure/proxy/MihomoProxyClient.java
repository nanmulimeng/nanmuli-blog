package com.nanmuli.blog.infrastructure.proxy;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.*;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestTemplate;

import java.net.ConnectException;
import java.util.*;

/**
 * Mihomo (Clash Meta) REST API 客户端
 *
 * 封装 Mihomo external-controller (127.0.0.1:9090) 的 HTTP API，
 * 提供代理组查询、节点切换、延迟测试、配置管理等功能。
 */
@Slf4j
@Component
public class MihomoProxyClient {

    private final RestTemplate restTemplate;
    private final String baseUrl;
    private final String apiSecret;
    private final ObjectMapper objectMapper;

    private static final String DEFAULT_TEST_URL = "https://www.gstatic.com/generate_204";
    private static final int DEFAULT_DELAY_TIMEOUT = 5000;

    public MihomoProxyClient(
            @Value("${mihomo.api.url:http://127.0.0.1:9090}") String baseUrl,
            @Value("${mihomo.api.secret:}") String apiSecret,
            ObjectMapper objectMapper) {
        this.baseUrl = baseUrl;
        this.apiSecret = apiSecret;
        this.objectMapper = objectMapper;

        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(3000);
        factory.setReadTimeout(10000);
        this.restTemplate = new RestTemplate(factory);
    }

    // ==================== 健康检查 ====================

    public boolean healthCheck() {
        try {
            ResponseEntity<String> resp = restTemplate.getForEntity(baseUrl, String.class);
            return resp.getStatusCode().is2xxSuccessful();
        } catch (Exception e) {
            log.debug("[Mihomo] Health check failed: {}", e.getMessage());
            return false;
        }
    }

    // ==================== 代理组 & 节点 ====================

    /**
     * 获取所有代理组及其节点
     */
    public Map<String, Object> getProxies() {
        JsonNode root = get("/proxies");
        JsonNode proxiesNode = root.get("proxies");
        if (proxiesNode == null) {
            return Collections.emptyMap();
        }

        Map<String, Object> result = new LinkedHashMap<>();
        proxiesNode.fields().forEachRemaining(entry -> {
            result.put(entry.getKey(), objectMapper.convertValue(entry.getValue(), Map.class));
        });
        return result;
    }

    /**
     * 选择代理节点
     */
    public void selectProxy(String groupName, String nodeName) {
        Map<String, String> body = Map.of("name", nodeName);
        put("/proxies/" + groupName, body);
        log.info("[Mihomo] Selected proxy: {} -> {}", groupName, nodeName);
    }

    /**
     * 测试代理组内所有节点的延迟
     *
     * @param groupName 代理组名称
     * @param testUrl   测试 URL，默认 https://www.gstatic.com/generate_204
     * @param timeoutMs 超时毫秒，默认 5000
     * @return Map<节点名, 延迟毫秒>，不可达节点延迟为 0
     */
    public Map<String, Integer> testDelay(String groupName, String testUrl, int timeoutMs) {
        String url = testUrl != null ? testUrl : DEFAULT_TEST_URL;
        int timeout = timeoutMs > 0 ? timeoutMs : DEFAULT_DELAY_TIMEOUT;

        String path = String.format("/proxies/%s/delay?url=%s&timeout=%d", groupName, url, timeout);
        JsonNode root = get(path);

        Map<String, Integer> result = new LinkedHashMap<>();
        if (root.isObject()) {
            root.fields().forEachRemaining(entry -> {
                result.put(entry.getKey(), entry.getValue().asInt(0));
            });
        }
        return result;
    }

    /**
     * 测试单个节点延迟
     */
    public int testSingleDelay(String groupName, String nodeName, int timeoutMs) {
        Map<String, Integer> all = testDelay(groupName, null, timeoutMs);
        return all.getOrDefault(nodeName, 0);
    }

    // ==================== 配置管理 ====================

    /**
     * 获取完整 Mihomo 配置
     */
    public Map<String, Object> getConfigs() {
        JsonNode root = get("/configs");
        return objectMapper.convertValue(root, Map.class);
    }

    /**
     * 更新 Mihomo 配置（用于热更新 proxy-providers 订阅）
     */
    public void updateConfigs(Map<String, Object> patch) {
        put("/configs", patch);
        log.info("[Mihomo] Config updated with keys: {}", patch.keySet());
    }

    /**
     * 更新 proxy-provider 的订阅 URL
     *
     * @param providerName    provider 名称（如 "default"）
     * @param subscriptionUrl 新的订阅 URL
     */
    public void updateProviderUrl(String providerName, String subscriptionUrl) {
        Map<String, Object> patch = Map.of(
                "proxy-providers",
                Map.of(providerName, Map.of("url", subscriptionUrl))
        );
        updateConfigs(patch);
    }

    /**
     * 刷新指定 proxy-provider（触发重新拉取订阅）
     */
    public void refreshProvider(String providerName) {
        put("/providers/proxy/" + providerName, Map.of());
        log.info("[Mihomo] Refreshed proxy provider: {}", providerName);
    }

    /**
     * 健康检查并触发更新 proxy-provider
     */
    public boolean refreshProviderSafe(String providerName) {
        try {
            refreshProvider(providerName);
            return true;
        } catch (Exception e) {
            log.warn("[Mihomo] Failed to refresh provider {}: {}", providerName, e.getMessage());
            return false;
        }
    }

    // ==================== 内部 HTTP 方法 ====================

    private JsonNode get(String path) {
        try {
            HttpHeaders headers = new HttpHeaders();
            if (apiSecret != null && !apiSecret.isEmpty()) {
                headers.set("Authorization", "Bearer " + apiSecret);
            }
            HttpEntity<Void> entity = new HttpEntity<>(headers);
            ResponseEntity<JsonNode> resp = restTemplate.exchange(
                    baseUrl + path, HttpMethod.GET, entity, JsonNode.class);
            return resp.getBody();
        } catch (RestClientException e) {
            if (isConnectRefused(e)) {
                throw new MihomoUnreachableException();
            }
            log.error("[Mihomo] GET {} failed: {}", path, e.getMessage());
            throw new MihomoUnreachableException("Mihomo API 请求失败: " + e.getMessage());
        }
    }

    private void put(String path, Object body) {
        try {
            String json = objectMapper.writeValueAsString(body);
            java.net.URL url = java.net.URI.create(baseUrl + path).toURL();
            java.net.HttpURLConnection conn = (java.net.HttpURLConnection) url.openConnection();
            conn.setRequestMethod("PUT");
            conn.setRequestProperty("Content-Type", "application/json");
            conn.setRequestProperty("Connection", "close");
            conn.setDoOutput(true);
            conn.setConnectTimeout(3000);
            conn.setReadTimeout(10000);
            if (apiSecret != null && !apiSecret.isEmpty()) {
                conn.setRequestProperty("Authorization", "Bearer " + apiSecret);
            }
            try (var os = conn.getOutputStream()) {
                os.write(json.getBytes(java.nio.charset.StandardCharsets.UTF_8));
                os.flush();
            }
            int code = conn.getResponseCode();
            if (code >= 400) {
                log.warn("[Mihomo] PUT {} returned {}", path, code);
            }
            conn.disconnect();
        } catch (java.net.ConnectException e) {
            throw new MihomoUnreachableException();
        } catch (Exception e) {
            log.error("[Mihomo] PUT {} failed: {}", path, e.getMessage());
            throw new MihomoUnreachableException("Mihomo API 请求失败: " + e.getMessage());
        }
    }

    private boolean isConnectRefused(Throwable e) {
        Throwable cause = e;
        while (cause != null) {
            if (cause instanceof ConnectException) {
                return true;
            }
            cause = cause.getCause();
        }
        return false;
    }
}
