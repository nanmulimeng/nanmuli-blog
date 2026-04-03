package com.nanmuli.blog.application.config;

import com.nanmuli.blog.application.config.dto.ConfigDTO;
import com.nanmuli.blog.domain.config.Config;
import com.nanmuli.blog.domain.config.ConfigRepository;
import com.nanmuli.blog.shared.exception.BusinessException;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.BeanUtils;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class ConfigAppService {

    private final ConfigRepository configRepository;

    @Transactional(readOnly = true)
    public Map<String, String> getPublicConfigs() {
        return configRepository.findAllPublic().stream()
                .collect(Collectors.toMap(Config::getConfigKey, Config::getConfigValue));
    }

    @Transactional(readOnly = true)
    public ConfigDTO getByKey(String key) {
        Config config = configRepository.findByKey(key)
                .orElseThrow(() -> new BusinessException("配置不存在"));
        return toDTO(config);
    }

    @Transactional
    public void update(String key, String value) {
        Config config = configRepository.findByKey(key)
                .orElseThrow(() -> new BusinessException("配置不存在"));
        config.setConfigValue(value);
        configRepository.save(config);
    }

    private ConfigDTO toDTO(Config config) {
        ConfigDTO dto = new ConfigDTO();
        BeanUtils.copyProperties(config, dto);
        return dto;
    }
}
