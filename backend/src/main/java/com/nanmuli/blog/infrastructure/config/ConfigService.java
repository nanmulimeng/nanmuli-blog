package com.nanmuli.blog.infrastructure.config;

import com.nanmuli.blog.domain.config.Config;
import com.nanmuli.blog.domain.config.ConfigRepository;
import com.nanmuli.blog.infrastructure.config.security.AesEncryptor;
import jakarta.annotation.PostConstruct;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 统一配置读取服务
 *
 * 启动时从 sys_config 表加载所有配置到内存 Map，
 * 提供 get/getInt/getBool 方法替代 @Value 注入。
 * 支持运行时刷新（/api/admin/config/refresh 触发 reload）。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class ConfigService {

    private final ConfigRepository configRepository;
    private final AesEncryptor aesEncryptor;

    private volatile Map<String, String> cache = new ConcurrentHashMap<>();

    @PostConstruct
    public void init() {
        reload();
    }

    /** 全量重新加载（从 DB 读取所有配置，解密加密值） */
    public synchronized void reload() {
        Map<String, String> temp = new ConcurrentHashMap<>();
        for (Config config : configRepository.findAll()) {
            String value = config.getConfigValue() != null ? config.getConfigValue() : "";
            if (Boolean.TRUE.equals(config.getIsEncrypted())) {
                value = aesEncryptor.decrypt(value);
            }
            temp.put(config.getConfigKey(), value);
        }
        this.cache = temp;
        log.info("[ConfigService] Loaded {} configs from DB", cache.size());
    }

    public String get(String key) {
        return cache.getOrDefault(key, "");
    }

    public String get(String key, String defaultValue) {
        return cache.getOrDefault(key, defaultValue);
    }

    public int getInt(String key, int defaultValue) {
        String val = cache.get(key);
        if (val == null || val.isEmpty()) return defaultValue;
        try {
            return Integer.parseInt(val);
        } catch (NumberFormatException e) {
            return defaultValue;
        }
    }

    public boolean getBool(String key, boolean defaultValue) {
        String val = cache.get(key);
        if (val == null || val.isEmpty()) return defaultValue;
        return "true".equalsIgnoreCase(val) || "1".equals(val);
    }
}
