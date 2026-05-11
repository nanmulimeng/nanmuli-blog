package com.nanmuli.blog.application.config;

import cn.dev33.satoken.stp.StpUtil;
import com.nanmuli.blog.application.config.dto.ConfigDTO;
import com.nanmuli.blog.domain.config.Config;
import com.nanmuli.blog.domain.config.ConfigRepository;
import com.nanmuli.blog.infrastructure.config.security.AesEncryptor;
import com.nanmuli.blog.shared.exception.BusinessException;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.BeanUtils;
import org.springframework.cache.annotation.CacheEvict;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.Arrays;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class ConfigAppService {

    private final ConfigRepository configRepository;
    private final AesEncryptor aesEncryptor;

    private static final String MASK_SENTINEL = "********";
    private static final List<String> SENSITIVE_KEYWORDS = Arrays.asList(
            "key", "secret", "password", "token", "credential", "private", "apikey"
    );

    @Transactional(readOnly = true)
    public Map<String, String> getPublicConfigs() {
        return configRepository.findAllPublic().stream()
                .collect(Collectors.toMap(Config::getConfigKey, Config::getConfigValue));
    }

    @Transactional(readOnly = true)
    public List<ConfigDTO> getPublicConfigsForList() {
        return configRepository.findAllPublic().stream()
                .map(this::toPublicDTO)
                .collect(Collectors.toList());
    }

    @Cacheable(value = "config:admin:list")
    @Transactional(readOnly = true)
    public List<ConfigDTO> getAllConfigsForAdmin() {
        if (!StpUtil.isLogin()) {
            throw new BusinessException(401, "未登录，请先登录");
        }
        return configRepository.findAll().stream()
                .map(this::toAdminDTO)
                .collect(Collectors.toList());
    }

    @Cacheable(value = "config", key = "#key")
    @Transactional(readOnly = true)
    public ConfigDTO getByKey(String key) {
        Config config = configRepository.findByKey(key)
                .orElseThrow(() -> new BusinessException("配置不存在"));
        return toDTO(config);
    }

    @CacheEvict(value = {"config", "config:admin:list"}, allEntries = true)
    @Transactional
    public void update(String key, String value) {
        // 拒绝遮罩值覆盖真实敏感数据
        if (MASK_SENTINEL.equals(value) && isSensitiveConfig(key)) {
            throw new BusinessException("不能使用脱敏值覆盖敏感配置，请修改其他字段后重试");
        }
        Config config = configRepository.findByKey(key)
                .orElseThrow(() -> new BusinessException("配置不存在"));
        // 敏感值加密存储
        String storeValue = isSensitiveConfig(key) ? aesEncryptor.encrypt(value) : value;
        config.setConfigValue(storeValue);
        configRepository.save(config);
    }

    @CacheEvict(value = {"config", "config:admin:list"}, allEntries = true)
    public void refreshCache() {
    }

    private ConfigDTO toPublicDTO(Config config) {
        ConfigDTO dto = new ConfigDTO();
        BeanUtils.copyProperties(config, dto);
        dto.setId(config.getId());
        if (isSensitiveConfig(config.getConfigKey())) {
            dto.setConfigValue(maskSensitiveValue(config.getConfigValue()));
        }
        return dto;
    }

    private ConfigDTO toAdminDTO(Config config) {
        ConfigDTO dto = new ConfigDTO();
        BeanUtils.copyProperties(config, dto);
        dto.setId(config.getId());
        if (isSensitiveConfig(config.getConfigKey())) {
            // 解密存储值用于管理端回显
            String decrypted = aesEncryptor.decrypt(config.getConfigValue());
            dto.setConfigValue(maskSensitiveValue(decrypted));
            dto.setSensitive(true);
        }
        return dto;
    }

    private ConfigDTO toDTO(Config config) {
        ConfigDTO dto = new ConfigDTO();
        BeanUtils.copyProperties(config, dto);
        dto.setId(config.getId());
        return dto;
    }

    private boolean isSensitiveConfig(String configKey) {
        if (configKey == null) return false;
        String lowerKey = configKey.toLowerCase();
        return SENSITIVE_KEYWORDS.stream().anyMatch(lowerKey::contains);
    }

    private String maskSensitiveValue(String value) {
        if (value == null || value.isEmpty()) return value;
        return MASK_SENTINEL;
    }
}
