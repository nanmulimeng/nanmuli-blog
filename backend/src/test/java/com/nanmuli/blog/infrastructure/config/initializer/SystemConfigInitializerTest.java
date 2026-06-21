package com.nanmuli.blog.infrastructure.config.initializer;

import com.nanmuli.blog.domain.config.Config;
import com.nanmuli.blog.domain.config.ConfigRepository;
import com.nanmuli.blog.infrastructure.crawler.CrawlerTaskClient;
import com.nanmuli.blog.infrastructure.config.ConfigService;
import com.nanmuli.blog.infrastructure.config.security.AesEncryptor;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.mock.env.MockEnvironment;

import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

class SystemConfigInitializerTest {

    @Test
    void seedsBlankCrawlerSecretsFromEnvironmentAndReloadsConfigCache() {
        ConfigRepository repository = mock(ConfigRepository.class);
        ConfigService configService = mock(ConfigService.class);
        CrawlerTaskClient crawlerTaskClient = mock(CrawlerTaskClient.class);
        AesEncryptor aesEncryptor = new AesEncryptor("test-encryption-key");
        MockEnvironment environment = new MockEnvironment()
                .withProperty("CRAWLER_API_KEY", "crawler-secret")
                .withProperty("CRAWLER_CALLBACK_API_KEY", "callback-secret")
                .withProperty("CRAWLER_SERVICE_URL", "http://crawler:8500")
                .withProperty("CRAWLER_CALLBACK_URL", "http://backend:8081/api/internal/collector/callback")
                .withProperty("AI_ENABLED", "true")
                .withProperty("AI_API_KEY", "ai-secret")
                .withProperty("AI_BASE_URL", "https://api.deepseek.com")
                .withProperty("AI_MODEL", "deepseek-v4-pro")
                .withProperty("DIGEST_ENABLED", "true");

        when(repository.findByKey(any())).thenReturn(Optional.empty());

        SystemConfigInitializer initializer =
                new SystemConfigInitializer(repository, configService, aesEncryptor, environment, crawlerTaskClient);
        initializer.run(null);

        ArgumentCaptor<Config> captor = ArgumentCaptor.forClass(Config.class);
        verify(repository, atLeastOnce()).save(captor.capture());
        assertThat(captor.getAllValues())
                .extracting(Config::getConfigKey)
                .contains(
                        "crawler.service.api-key",
                        "crawler.callback.api-key",
                        "crawler.ai.enabled",
                        "crawler.ai.api_key",
                        "crawler.ai.base_url",
                        "crawler.ai.model",
                        "crawler.digest.enabled"
                );
        Config aiKey = captor.getAllValues().stream()
                .filter(config -> "crawler.ai.api_key".equals(config.getConfigKey()))
                .findFirst()
                .orElseThrow();
        assertThat(aiKey.getConfigValue()).isNotEqualTo("ai-secret");
        assertThat(aiKey.getIsEncrypted()).isTrue();
        assertThat(aiKey.getIsSensitive()).isTrue();
        verify(configService).reload();
        verify(crawlerTaskClient).reloadPool();
    }

    @Test
    void doesNotOverrideExistingAdminConfigValue() {
        Config existing = new Config();
        existing.setConfigKey("crawler.service.api-key");
        existing.setConfigValue("already-set");
        existing.setIsEncrypted(true);
        existing.setIsSensitive(true);

        ConfigRepository repository = mock(ConfigRepository.class);
        ConfigService configService = mock(ConfigService.class);
        CrawlerTaskClient crawlerTaskClient = mock(CrawlerTaskClient.class);
        AesEncryptor aesEncryptor = new AesEncryptor("test-encryption-key");
        MockEnvironment environment = new MockEnvironment()
                .withProperty("CRAWLER_API_KEY", "env-secret");

        when(repository.findByKey("crawler.dependency_mode")).thenReturn(Optional.of(new Config()));
        when(repository.findByKey("crawler.service.base-url")).thenReturn(Optional.of(blankConfig("crawler.service.base-url")));
        when(repository.findByKey("crawler.service.api-key")).thenReturn(Optional.of(existing));
        when(repository.findByKey("crawler.callback.api-key")).thenReturn(Optional.of(blankConfig("crawler.callback.api-key")));
        when(repository.findByKey("crawler.callback.url")).thenReturn(Optional.of(blankConfig("crawler.callback.url")));

        SystemConfigInitializer initializer =
                new SystemConfigInitializer(repository, configService, aesEncryptor, environment, crawlerTaskClient);
        initializer.run(null);

        assertThat(existing.getConfigValue()).isEqualTo("already-set");
        verify(repository, never()).save(existing);
        verify(crawlerTaskClient, never()).reloadPool();
    }

    private static Config blankConfig(String key) {
        Config config = new Config();
        config.setConfigKey(key);
        config.setConfigValue("");
        return config;
    }
}
