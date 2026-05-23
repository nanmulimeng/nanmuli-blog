package com.nanmuli.blog.application.webcollector.dto;

import com.fasterxml.jackson.databind.annotation.JsonSerialize;
import com.fasterxml.jackson.databind.ser.std.ToStringSerializer;
import lombok.Data;

import java.time.LocalDateTime;

@Data
public class SourceDTO {
    @JsonSerialize(using = ToStringSerializer.class)
    private Long id;
    private String name;
    private String type;
    private String value;
    private String contentCategory;
    private String crawlMode;
    private Integer maxDepth;
    private Integer maxPages;
    private String cssSelector;
    private String aiTemplate;
    private String scheduleCron;
    private Integer freshnessHours;
    private Boolean isActive;
    private LocalDateTime lastRunAt;
    private String lastRunStatus;
    private Integer runCount;
    private Integer successCount;
    private Integer failCount;
    private Double avgQualityScore;
    private Integer lastResultCount;
    private String lastError;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
