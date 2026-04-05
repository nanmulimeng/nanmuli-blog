package com.nanmuli.blog.application.config.dto;

import lombok.Data;

@Data
public class ConfigDTO {
    private Long id;
    private String configKey;
    private String configValue;
    private String defaultValue;
    private String description;
    private String groupName;
    private Boolean isPublic;
    private Boolean sensitive; // 是否为敏感配置
}
