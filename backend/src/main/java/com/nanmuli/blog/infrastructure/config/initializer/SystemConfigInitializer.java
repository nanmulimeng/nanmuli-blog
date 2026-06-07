package com.nanmuli.blog.infrastructure.config.initializer;

import com.nanmuli.blog.domain.config.Config;
import com.nanmuli.blog.domain.config.ConfigRepository;
import com.nanmuli.blog.infrastructure.crawler.CrawlerTaskClient;
import com.nanmuli.blog.infrastructure.config.ConfigService;
import com.nanmuli.blog.infrastructure.config.security.AesEncryptor;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.core.annotation.Order;
import org.springframework.core.env.Environment;
import org.springframework.stereotype.Component;

@Slf4j
@Component
@RequiredArgsConstructor
@Order(20)
public class SystemConfigInitializer implements ApplicationRunner {

    private static final String CRAWLER_DEPENDENCY_MODE = "crawler.dependency_mode";

    private final ConfigRepository configRepository;
    private final ConfigService configService;
    private final AesEncryptor aesEncryptor;
    private final Environment environment;
    private final CrawlerTaskClient crawlerTaskClient;

    @Override
    public void run(ApplicationArguments args) {
        boolean changed = false;
        changed |= ensureCrawlerDependencyMode();
        changed |= seedFromEnvironment("crawler.service.base-url", "CRAWLER_SERVICE_URL",
                "Python crawler service base URL", "text", false, false);
        changed |= seedFromEnvironment("crawler.service.api-key", "CRAWLER_API_KEY",
                "Python crawler API key", "password", true, true);
        changed |= seedFromEnvironment("crawler.callback.api-key", "CRAWLER_CALLBACK_API_KEY",
                "Crawler callback API key", "password", true, true);
        changed |= seedFromEnvironment("crawler.callback.url", "CRAWLER_CALLBACK_URL",
                "Crawler callback URL", "text", false, false);
        if (changed) {
            configService.reload();
            crawlerTaskClient.reloadPool();
        }
    }

    private boolean ensureCrawlerDependencyMode() {
        try {
            if (configRepository.findByKey(CRAWLER_DEPENDENCY_MODE).isPresent()) {
                return false;
            }
            Config config = new Config();
            config.setConfigKey(CRAWLER_DEPENDENCY_MODE);
            config.setConfigValue("degraded");
            config.setDefaultValue("degraded");
            config.setDescription("Crawler dependency mode: degraded keeps service available when external crawler dependencies fail; strict fails startup.");
            config.setGroupName("crawler");
            config.setIsPublic(false);
            config.setInputType("text");
            config.setIsEncrypted(false);
            config.setIsSensitive(false);
            configRepository.save(config);
            log.info("[ConfigInit] Added missing config: {}", CRAWLER_DEPENDENCY_MODE);
            return true;
        } catch (Exception e) {
            log.warn("[ConfigInit] Failed to ensure {}: {}", CRAWLER_DEPENDENCY_MODE, e.getMessage());
            return false;
        }
    }

    private boolean seedFromEnvironment(String configKey, String envKey, String description,
                                        String inputType, boolean encrypted, boolean sensitive) {
        String envValue = environment.getProperty(envKey, "");
        if (envValue == null || envValue.isBlank()) {
            return false;
        }

        try {
            Config config = configRepository.findByKey(configKey).orElseGet(() -> {
                Config created = new Config();
                created.setConfigKey(configKey);
                created.setDefaultValue("");
                created.setDescription(description);
                created.setGroupName("crawler");
                created.setInputType(inputType);
                created.setIsPublic(false);
                created.setIsEncrypted(encrypted);
                created.setIsSensitive(sensitive);
                return created;
            });

            String currentValue = config.getConfigValue();
            if (currentValue != null && !currentValue.isBlank()) {
                return false;
            }

            if (config.getDescription() == null || config.getDescription().isBlank()) {
                config.setDescription(description);
            }
            if (config.getGroupName() == null || config.getGroupName().isBlank()) {
                config.setGroupName("crawler");
            }
            if (config.getInputType() == null || config.getInputType().isBlank()) {
                config.setInputType(inputType);
            }
            if (config.getIsPublic() == null) {
                config.setIsPublic(false);
            }
            if (config.getIsEncrypted() == null) {
                config.setIsEncrypted(encrypted);
            }
            if (config.getIsSensitive() == null) {
                config.setIsSensitive(sensitive);
            }

            String valueToStore = Boolean.TRUE.equals(config.getIsEncrypted())
                    ? aesEncryptor.encrypt(envValue)
                    : envValue;
            config.setConfigValue(valueToStore);
            configRepository.save(config);
            log.info("[ConfigInit] Seeded {} from environment {}", configKey, envKey);
            return true;
        } catch (Exception e) {
            log.warn("[ConfigInit] Failed to seed {} from {}: {}", configKey, envKey, e.getMessage());
            return false;
        }
    }
}
