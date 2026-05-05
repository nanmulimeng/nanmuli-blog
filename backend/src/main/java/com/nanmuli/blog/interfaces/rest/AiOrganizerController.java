package com.nanmuli.blog.interfaces.rest;

import com.nanmuli.blog.infrastructure.ai.AiConfig;
import com.nanmuli.blog.shared.result.Result;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.client.RestClient;

import java.time.Duration;
import java.util.*;

/**
 * AI 配置管理接口
 */
@Slf4j
@Tag(name = "AI 配置")
@RestController
@RequestMapping("/api/admin/ai")
@RequiredArgsConstructor
public class AiOrganizerController {

    private final AiConfig aiConfig;

    /**
     * 测试当前 AI 配置是否可用
     */
    @GetMapping("/test")
    public Result<Map<String, Object>> testConnection() {
        Map<String, Object> result = new LinkedHashMap<>();

        if (!aiConfig.isEnabled()) {
            result.put("configured", false);
            result.put("available", false);
            result.put("reason", "AI 功能未启用");
            return Result.success(result);
        }

        if (!aiConfig.isConfigured()) {
            result.put("configured", false);
            result.put("available", false);
            result.put("reason", "AI 配置不完整：请检查 API 密钥、Base URL 和模型名称");
            return Result.success(result);
        }

        result.put("configured", true);
        result.put("provider", aiConfig.getProvider());
        result.put("model", aiConfig.getModel());
        result.put("baseUrl", aiConfig.getBaseUrl());

        try {
            SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
            factory.setConnectTimeout(Duration.ofSeconds(aiConfig.getConnectTimeoutSeconds()));
            factory.setReadTimeout(Duration.ofSeconds(5));

            RestClient restClient = RestClient.builder()
                    .baseUrl(aiConfig.getBaseUrl())
                    .defaultHeader("Authorization", "Bearer " + aiConfig.getApiKey())
                    .defaultHeader("Content-Type", "application/json")
                    .requestFactory(factory)
                    .build();

            Map<String, Object> requestBody = new LinkedHashMap<>();
            requestBody.put("model", aiConfig.getModel());
            requestBody.put("temperature", aiConfig.getTemperature());
            requestBody.put("max_tokens", 5);
            requestBody.put("messages", List.of(
                    Map.of("role", "user", "content", "Hi")
            ));

            String response = restClient.post()
                    .uri("/chat/completions")
                    .body(requestBody)
                    .retrieve()
                    .body(String.class);

            result.put("available", true);
            result.put("responsePreview", response != null ? response.substring(0, Math.min(200, response.length())) : null);
            log.info("[AiTest] Connection successful, provider={}, model={}", aiConfig.getProvider(), aiConfig.getModel());

        } catch (Exception e) {
            result.put("available", false);
            result.put("reason", e.getMessage());
            log.warn("[AiTest] Connection failed, provider={}, model={}, error={}",
                    aiConfig.getProvider(), aiConfig.getModel(), e.getMessage());
        }

        return Result.success(result);
    }

    /**
     * 获取当前 AI 配置（敏感值脱敏）
     */
    @GetMapping("/config")
    public Result<Map<String, Object>> getConfig() {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("enabled", aiConfig.isEnabled());
        result.put("provider", aiConfig.getProvider());
        result.put("model", aiConfig.getModel());
        result.put("baseUrl", aiConfig.getBaseUrl());
        result.put("temperature", aiConfig.getTemperature());
        result.put("configured", aiConfig.isConfigured());

        String apiKey = aiConfig.getApiKey();
        if (apiKey != null && apiKey.length() > 8) {
            result.put("apiKeyMasked", apiKey.substring(0, 4) + "****" + apiKey.substring(apiKey.length() - 4));
        } else {
            result.put("apiKeyMasked", apiKey);
        }

        return Result.success(result);
    }
}
