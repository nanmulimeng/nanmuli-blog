package com.nanmuli.blog.application.config.dto;

import com.fasterxml.jackson.databind.annotation.JsonSerialize;
import com.fasterxml.jackson.databind.ser.std.ToStringSerializer;
import lombok.Data;

import java.io.Serializable;

@Data
public class ConfigDTO implements Serializable {
    private static final long serialVersionUID = 1L;

    @JsonSerialize(using = ToStringSerializer.class)
    private Long id;
    private String configKey;
    private String configValue;
    private String defaultValue;
    private String description;
    private String groupName;
    private Boolean isPublic;
    private Boolean isEncrypted;  // AES-128 加密存储
    private Boolean isSensitive;  // 敏感配置（前端脱敏显示）
    /** @deprecated 请使用 isSensitive */
    private Boolean sensitive;
    private String inputType;     // text/textarea/switch/image/password
}
