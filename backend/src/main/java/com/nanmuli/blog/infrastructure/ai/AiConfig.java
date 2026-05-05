package com.nanmuli.blog.infrastructure.ai;

import com.nanmuli.blog.application.config.ConfigAppService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

/**
 * AI 动态配置（从 sys_config 表读取，支持运行时切换）
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class AiConfig {

    private final ConfigAppService configAppService;

    private static final String PREFIX = "ai.";

    public boolean isEnabled() {
        return "true".equalsIgnoreCase(getValue("enabled", "false"));
    }

    public String getProvider() {
        return getValue("provider", "dashscope");
    }

    public String getApiKey() {
        return getValue("api_key", "");
    }

    public String getBaseUrl() {
        return getValue("base_url", "https://dashscope.aliyuncs.com/compatible-mode/v1");
    }

    public String getModel() {
        return getValue("model", "qwen-turbo");
    }

    public double getTemperature() {
        try {
            return Double.parseDouble(getValue("temperature", "0.3"));
        } catch (NumberFormatException e) {
            return 0.3;
        }
    }

    public int getConnectTimeoutSeconds() {
        try {
            return Integer.parseInt(getValue("connect_timeout_seconds", "10"));
        } catch (NumberFormatException e) {
            return 10;
        }
    }

    public int getReadTimeoutSeconds() {
        try {
            return Integer.parseInt(getValue("read_timeout_seconds", "90"));
        } catch (NumberFormatException e) {
            return 90;
        }
    }

    public boolean isConfigured() {
        return isEnabled() && !getApiKey().isBlank() && !getBaseUrl().isBlank() && !getModel().isBlank();
    }

    private String getValue(String key, String defaultValue) {
        try {
            return configAppService.getByKey(PREFIX + key).getConfigValue();
        } catch (Exception e) {
            return defaultValue;
        }
    }
}
