package com.nanmuli.blog.application.config;

import com.nanmuli.blog.domain.config.Config;
import com.nanmuli.blog.domain.config.ConfigRepository;
import com.nanmuli.blog.infrastructure.config.security.AesEncryptor;
import com.nanmuli.blog.shared.exception.BusinessException;
import org.junit.jupiter.api.Test;

import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentCaptor.forClass;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class ConfigAppServiceTest {

    @Test
    void resetToDefault_existingConfig_usesDefaultValue() {
        ConfigRepository repository = mock(ConfigRepository.class);
        AesEncryptor encryptor = new AesEncryptor("test-encryption-key");
        ConfigAppService service = new ConfigAppService(repository, encryptor);
        Config config = new Config();
        config.setConfigKey("crawler.digest.sections");
        config.setConfigValue("old-value");
        config.setDefaultValue("recommended-value");

        when(repository.findByKey("crawler.digest.sections")).thenReturn(Optional.of(config));

        service.resetToDefault("crawler.digest.sections");

        var captor = forClass(Config.class);
        verify(repository).save(captor.capture());
        assertThat(captor.getValue().getConfigValue()).isEqualTo("recommended-value");
    }

    @Test
    void resetToDefault_encryptedConfig_encryptsDefaultValue() {
        ConfigRepository repository = mock(ConfigRepository.class);
        AesEncryptor encryptor = new AesEncryptor("test-encryption-key");
        ConfigAppService service = new ConfigAppService(repository, encryptor);
        Config config = new Config();
        config.setConfigKey("crawler.service.api-key");
        config.setConfigValue("old-encrypted-value");
        config.setDefaultValue("plain-default");
        config.setIsEncrypted(true);

        when(repository.findByKey("crawler.service.api-key")).thenReturn(Optional.of(config));

        service.resetToDefault("crawler.service.api-key");

        var captor = forClass(Config.class);
        verify(repository).save(captor.capture());
        assertThat(captor.getValue().getConfigValue()).isNotEqualTo("plain-default");
        assertThat(encryptor.decrypt(captor.getValue().getConfigValue())).isEqualTo("plain-default");
    }

    @Test
    void resetToDefault_missingConfig_throwsBusinessException() {
        ConfigRepository repository = mock(ConfigRepository.class);
        ConfigAppService service = new ConfigAppService(repository, new AesEncryptor("test-encryption-key"));
        when(repository.findByKey("missing.key")).thenReturn(Optional.empty());

        assertThatThrownBy(() -> service.resetToDefault("missing.key"))
                .isInstanceOf(BusinessException.class);
    }
}
