package com.nanmuli.blog.application.config;

import cn.dev33.satoken.stp.StpUtil;
import com.nanmuli.blog.application.config.dto.ConfigDTO;
import com.nanmuli.blog.domain.config.Config;
import com.nanmuli.blog.domain.config.ConfigRepository;
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

    // 敏感配置关键词列表
    private static final List<String> SENSITIVE_KEYWORDS = Arrays.asList(
            "key", "secret", "password", "token", "credential", "private", "apikey"
    );

    /**
     * 获取公开配置（仅返回isPublic=true的配置，敏感值脱敏）
     */
    @Transactional(readOnly = true)
    public List<ConfigDTO> getPublicConfigsForList() {
        return configRepository.findAllPublic().stream()
                .map(this::toPublicDTO)
                .collect(Collectors.toList());
    }

    /**
     * 获取所有配置（需管理员权限，敏感值脱敏显示）
     */
    @Transactional(readOnly = true)
    public List<ConfigDTO> getAllConfigsForAdmin() {
        // 校验管理员权限
        if (!StpUtil.isLogin()) {
            throw new BusinessException(401, "未登录，请先登录");
        }

        return configRepository.findAll().stream()
                .map(this::toAdminDTO)
                .collect(Collectors.toList());
    }

    @Transactional(readOnly = true)
    public Map<String, String> getPublicConfigs() {
        return configRepository.findAllPublic().stream()
                .collect(Collectors.toMap(Config::getConfigKey, Config::getConfigValue));
    }

    @Cacheable(value = "config", key = "#key")
    @Transactional(readOnly = true)
    public ConfigDTO getByKey(String key) {
        Config config = configRepository.findByKey(key)
                .orElseThrow(() -> new BusinessException("配置不存在"));
        return toDTO(config);
    }

    @CacheEvict(value = "config", key = "#key")
    @Transactional
    public void update(String key, String value) {
        Config config = configRepository.findByKey(key)
                .orElseThrow(() -> new BusinessException("配置不存在"));
        config.setConfigValue(value);
        configRepository.save(config);
    }

    @CacheEvict(value = "config", allEntries = true)
    public void refreshCache() {
        // 清除所有配置缓存
    }

    /**
     * 转换为公开DTO（敏感值脱敏）
     */
    private ConfigDTO toPublicDTO(Config config) {
        ConfigDTO dto = new ConfigDTO();
        BeanUtils.copyProperties(config, dto);
        dto.setId(config.getId());

        // 敏感配置值脱敏
        if (isSensitiveConfig(config.getConfigKey())) {
            dto.setConfigValue(maskSensitiveValue(config.getConfigValue()));
            dto.setDefaultValue(maskSensitiveValue(config.getDefaultValue()));
        }

        return dto;
    }

    /**
     * 转换为管理员DTO（敏感值脱敏显示，但标记为可查看）
     */
    private ConfigDTO toAdminDTO(Config config) {
        ConfigDTO dto = new ConfigDTO();
        BeanUtils.copyProperties(config, dto);
        dto.setId(config.getId());

        // 敏感配置值脱敏显示
        if (isSensitiveConfig(config.getConfigKey())) {
            dto.setConfigValue(maskSensitiveValue(config.getConfigValue()));
            dto.setDefaultValue(maskSensitiveValue(config.getDefaultValue()));
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

    /**
     * 检测是否为敏感配置
     */
    private boolean isSensitiveConfig(String configKey) {
        if (configKey == null) {
            return false;
        }
        String lowerKey = configKey.toLowerCase();
        return SENSITIVE_KEYWORDS.stream().anyMatch(lowerKey::contains);
    }

    /**
     * 敏感值脱敏处理
     */
    private String maskSensitiveValue(String value) {
        if (value == null || value.isEmpty()) {
            return value;
        }
        return "********";
    }
}
