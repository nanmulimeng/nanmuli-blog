package com.nanmuli.blog.application.webcollector.dto;

import lombok.Data;

import java.time.LocalDateTime;
import java.util.Map;

/**
 * 爬取页面 DTO
 */
@Data
public class CollectPageDTO {
    private String id;
    private String taskId;
    private String url;
    private String pageTitle;
    private String rawMarkdown;
    private Map<String, Object> pageMetadata;

    // 状态
    private Integer crawlStatus;
    private String crawlStatusLabel;
    private String errorMessage;

    // 统计
    private Integer crawlDuration;
    private Integer wordCount;

    // 排序
    private Integer sortOrder;
    private Integer depth;

    private LocalDateTime createdAt;
}
