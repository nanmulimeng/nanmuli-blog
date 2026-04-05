package com.nanmuli.blog.application.config.dto;

import com.fasterxml.jackson.databind.annotation.JsonSerialize;
import com.fasterxml.jackson.databind.ser.std.ToStringSerializer;
import lombok.Data;

@Data
public class ConfigDTO {

    @JsonSerialize(using = ToStringSerializer.class)
    private Long id;
    private String configKey;
    private String configValue;
    private String defaultValue;
    private String description;
    private String groupName;
    private Boolean isPublic;
    private Boolean sensitive; // 是否为敏感配置
}
