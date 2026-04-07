package com.nanmuli.blog.domain.webcollector;

import lombok.Getter;

/**
 * 采集任务状态枚举
 */
@Getter
public enum CollectTaskStatus {
    PENDING(0, "待处理", "排队中..."),
    CRAWLING(1, "爬取中", "正在爬取网页..."),
    PROCESSING(2, "整理中", "AI 正在整理内容..."),
    COMPLETED(3, "已完成", "查看结果"),
    FAILED(4, "失败", "失败（显示原因）");

    private final int value;
    private final String label;
    private final String displayText;

    CollectTaskStatus(int value, String label, String displayText) {
        this.value = value;
        this.label = label;
        this.displayText = displayText;
    }

    public static CollectTaskStatus of(int value) {
        for (CollectTaskStatus status : values()) {
            if (status.value == value) {
                return status;
            }
        }
        throw new IllegalArgumentException("Invalid status value: " + value);
    }

    public boolean isTerminal() {
        return this == COMPLETED || this == FAILED;
    }
}
