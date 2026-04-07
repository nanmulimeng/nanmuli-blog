package com.nanmuli.blog.domain.webcollector;

import lombok.Getter;

/**
 * 采集任务类型枚举
 */
@Getter
public enum CollectTaskType {
    SINGLE("single", "单页爬取"),
    DEEP("deep", "深度爬取"),
    KEYWORD("keyword", "关键词搜索"),
    DIGEST("digest", "每日日报");

    private final String code;
    private final String label;

    CollectTaskType(String code, String label) {
        this.code = code;
        this.label = label;
    }

    public static CollectTaskType of(String code) {
        for (CollectTaskType type : values()) {
            if (type.code.equalsIgnoreCase(code)) {
                return type;
            }
        }
        throw new IllegalArgumentException("Invalid task type: " + code);
    }
}
