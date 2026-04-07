package com.nanmuli.blog.application.webcollector.dto;

import com.fasterxml.jackson.annotation.JsonFormat;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 采集任务列表 DTO（不含大文本字段）
 */
@Data
public class CollectTaskListDTO {
    private String id;
    private String taskType;
    private String taskTypeLabel;
    private String sourceUrl;
    private String keyword;

    // AI 结果摘要（列表显示用）
    private String aiTitle;
    private String aiSummary;

    // 状态
    private Integer status;
    private String statusLabel;
    private String statusDisplay;

    // 进度
    private Integer totalPages;
    private Integer completedPages;
    private Integer progressPercent;

    // 统计
    private Integer totalWordCount;
    private Integer tokensUsed;

    // 关联
    private String articleId;
    private String dailyLogId;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime createdAt;
}
