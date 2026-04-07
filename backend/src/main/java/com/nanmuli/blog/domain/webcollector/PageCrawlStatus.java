package com.nanmuli.blog.domain.webcollector;

import lombok.Getter;

/**
 * 页面爬取状态枚举
 */
@Getter
public enum PageCrawlStatus {
    PENDING(0, "待爬取"),
    CRAWLING(1, "爬取中"),
    COMPLETED(2, "已完成"),
    FAILED(3, "失败");

    private final int value;
    private final String label;

    PageCrawlStatus(int value, String label) {
        this.value = value;
        this.label = label;
    }

    public static PageCrawlStatus of(int value) {
        for (PageCrawlStatus status : values()) {
            if (status.value == value) {
                return status;
            }
        }
        throw new IllegalArgumentException("Invalid page crawl status value: " + value);
    }
}
