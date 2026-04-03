package com.nanmuli.blog.domain.config;

import com.nanmuli.blog.shared.domain.BaseAggregateRoot;
import lombok.EqualsAndHashCode;
import lombok.Getter;
import lombok.Setter;

@Getter
@Setter
@EqualsAndHashCode(callSuper = false)
public class Config extends BaseAggregateRoot<Long> {
    private static final long serialVersionUID = 1L;

    private String configKey;
    private String configValue;
    private String defaultValue;
    private String description;
    private String groupName;
    private Boolean isPublic;
}
