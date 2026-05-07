package com.nanmuli.blog.infrastructure.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.List;

/**
 * 每日日报板块配置属性
 */
@Data
@Component
@ConfigurationProperties(prefix = "blog.webcollector.daily-digest")
public class DailyDigestProperties {

    private boolean enabled = true;
    private List<Section> sections = new ArrayList<>();

    @Data
    public static class Section {
        private String name;
        private String displayName;
        private String keyword;
        private String timeRange = "week";
        private int maxItems = 3;
    }
}
