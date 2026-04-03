package com.nanmuli.blog.application.config.dto;

import lombok.Data;

@Data
public class ConfigDTO {
    private String configKey;
    private String configValue;
    private String description;
    private String groupName;
}
