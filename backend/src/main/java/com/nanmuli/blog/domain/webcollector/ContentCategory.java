package com.nanmuli.blog.domain.webcollector;

import lombok.Getter;

/**
 * 内容分类枚举（用于日报和订阅源）
 */
@Getter
public enum ContentCategory {
    HOT_TREND("hot_trend", "热点动态", "🔥"),
    OPEN_SOURCE("open_source", "开源项目", "🌟"),
    TECH_ARTICLE("tech_article", "技术文章", "📖"),
    DEV_TOOL("dev_tool", "开发工具", "🔧"),
    CREATIVE("creative", "创意发现", "💡");

    private final String code;
    private final String label;
    private final String emoji;

    ContentCategory(String code, String label, String emoji) {
        this.code = code;
        this.label = label;
        this.emoji = emoji;
    }

    public static ContentCategory of(String code) {
        for (ContentCategory category : values()) {
            if (category.code.equalsIgnoreCase(code)) {
                return category;
            }
        }
        return null;
    }
}
