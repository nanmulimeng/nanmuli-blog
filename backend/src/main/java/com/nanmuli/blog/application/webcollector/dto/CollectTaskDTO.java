package com.nanmuli.blog.application.webcollector.dto;

import com.fasterxml.jackson.annotation.JsonFormat;
import lombok.Data;

import java.time.LocalDateTime;
import java.util.List;

/**
 * 采集任务详情 DTO
 */
@Data
public class CollectTaskDTO {
    private String id;
    private String taskType;
    private String taskTypeLabel;
    private String sourceUrl;
    private String keyword;
    private String searchEngine;
    private String triggerType;

    // AI 整理结果
    private String aiTitle;
    private String aiSummary;
    private List<String> aiKeyPoints;
    private List<String> aiTags;
    private String aiCategory;
    private String aiFullContent;

    // 状态
    private Integer status;
    private String statusLabel;
    private String statusDisplay;
    private String errorMessage;

    // 配置
    private String crawlMode;
    private String aiTemplate;
    private Integer maxDepth;
    private Integer maxPages;
    private String timeRange;

    // 进度
    private Integer totalPages;
    private Integer completedPages;
    private Integer progressPercent; // 计算字段

    // 统计
    private Integer crawlDuration;
    private Integer aiDuration;
    private Integer tokensUsed;
    private Integer totalWordCount;

    // 关联
    private String articleId;
    private String dailyLogId;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime createdAt;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime updatedAt;
}
