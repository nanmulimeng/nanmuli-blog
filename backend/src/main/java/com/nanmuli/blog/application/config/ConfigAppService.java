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

import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class ConfigAppService {

    private final ConfigRepository configRepository;
    private final AesEncryptor aesEncryptor;

    private static final String MASK_SENTINEL = "********";

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
        Config config = configRepository.findByKey(key)
                .orElseThrow(() -> new BusinessException("配置不存在"));
        // 拒绝遮罩值覆盖真实敏感数据
        if (MASK_SENTINEL.equals(value) && isSensitive(config)) {
            throw new BusinessException("不能使用脱敏值覆盖敏感配置，请修改其他字段后重试");
        }
        // 敏感值加密存储
        String storeValue = isEncrypted(config) ? aesEncryptor.encrypt(value) : value;
        config.setConfigValue(storeValue);
        configRepository.save(config);
    }

    @CacheEvict(value = {"config", "config:admin:list"}, allEntries = true)
    @Transactional
    public void set(String key, String value, String description, String groupName,
                    String inputType, Boolean isPublic) {
        Config config = configRepository.findByKey(key).orElse(null);
        if (config == null) {
            config = new Config();
            config.setConfigKey(key);
        }
        // 更新 metadata（创建和更新都执行）
        if (description != null && !description.isEmpty()) {
            config.setDescription(description);
        }
        if (groupName != null && !groupName.isEmpty()) {
            config.setGroupName(groupName);
        } else if (config.getGroupName() == null) {
            config.setGroupName("other");
        }
        if (inputType != null && !inputType.isEmpty()) {
            config.setInputType(inputType);
        } else if (config.getInputType() == null) {
            config.setInputType("text");
        }
        if (isPublic != null) {
            config.setIsPublic(isPublic);
        } else if (config.getIsPublic() == null) {
            config.setIsPublic(false);
        }
        if (MASK_SENTINEL.equals(value) && isSensitive(config)) {
            throw new BusinessException("不能使用脱敏值覆盖敏感配置");
        }
        String storeValue = isEncrypted(config) ? aesEncryptor.encrypt(value) : value;
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
        if (isSensitive(config)) {
            dto.setConfigValue(maskSensitiveValue(config.getConfigValue()));
        }
        return dto;
    }

    private ConfigDTO toAdminDTO(Config config) {
        ConfigDTO dto = new ConfigDTO();
        BeanUtils.copyProperties(config, dto);
        dto.setId(config.getId());
        if (isSensitive(config)) {
            // 解密存储值用于管理端回显
            String decrypted = aesEncryptor.decrypt(config.getConfigValue());
            dto.setConfigValue(maskSensitiveValue(decrypted));
            dto.setSensitive(true);
            dto.setIsSensitive(true);
        }
        if (isEncrypted(config)) {
            dto.setIsEncrypted(true);
        }
        return dto;
    }

    private ConfigDTO toDTO(Config config) {
        ConfigDTO dto = new ConfigDTO();
        BeanUtils.copyProperties(config, dto);
        dto.setId(config.getId());
        return dto;
    }

    private boolean isEncrypted(Config config) {
        return Boolean.TRUE.equals(config.getIsEncrypted());
    }

    private boolean isSensitive(Config config) {
        return Boolean.TRUE.equals(config.getIsSensitive());
    }

    private String maskSensitiveValue(String value) {
        if (value == null || value.isEmpty()) return value;
        return MASK_SENTINEL;
    }
}
