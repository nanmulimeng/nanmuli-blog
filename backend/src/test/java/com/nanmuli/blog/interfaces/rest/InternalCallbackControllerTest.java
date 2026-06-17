package com.nanmuli.blog.interfaces.rest;

import com.nanmuli.blog.application.webcollector.WebCollectSourceAppService;
import com.nanmuli.blog.application.webcollector.WebCollectorAppService;
import com.nanmuli.blog.domain.config.Config;
import com.nanmuli.blog.domain.config.ConfigRepository;
import com.nanmuli.blog.infrastructure.config.ConfigService;
import com.nanmuli.blog.infrastructure.config.security.AesEncryptor;
import com.nanmuli.blog.infrastructure.persistence.webcollector.DigestFingerprintRepositoryImpl;
import com.nanmuli.blog.infrastructure.persistence.webcollector.SourceAuthorityMapper;
import com.nanmuli.blog.shared.result.Result;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.core.env.Environment;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class InternalCallbackControllerTest {

    @Mock
    private WebCollectorAppService collectorAppService;
    @Mock
    private WebCollectSourceAppService sourceAppService;
    @Mock
    private ConfigRepository configRepository;
    @Mock
    private AesEncryptor aesEncryptor;
    @Mock
    private ConfigService configService;
    @Mock
    private DigestFingerprintRepositoryImpl fingerprintRepository;
    @Mock
    private SourceAuthorityMapper sourceAuthorityMapper;
    @Mock
    private Environment environment;

    @InjectMocks
    private InternalCallbackController controller;

    @Test
    void getCrawlerConfigAllowsServiceApiKeyForBootstrap() {
        when(configService.get("crawler.callback.api-key", "")).thenReturn("callback-key");
        when(configService.get("crawler.service.api-key", "")).thenReturn("service-key");

        Config config = new Config();
        config.setConfigKey("crawler.service.api-key");
        config.setConfigValue("service-key");
        config.setIsEncrypted(false);
        when(configRepository.findByGroup("crawler")).thenReturn(List.of(config));

        Result<Map<String, String>> result = controller.getCrawlerConfig("service-key");

        assertThat(result.getCode()).isEqualTo(200);
        assertThat(result.getData()).containsEntry("service.api-key", "service-key");
    }

    @Test
    void getCrawlerConfigRejectsWrongBootstrapKey() {
        when(configService.get("crawler.callback.api-key", "")).thenReturn("callback-key");
        when(configService.get("crawler.service.api-key", "")).thenReturn("service-key");

        Result<Map<String, String>> result = controller.getCrawlerConfig("wrong-key");

        assertThat(result.getCode()).isEqualTo(403);
        verify(configRepository, never()).findByGroup("crawler");
    }
}
