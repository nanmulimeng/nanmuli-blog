package com.nanmuli.blog.application.dailylog.dto;

import lombok.Data;

import java.time.LocalDate;
import java.time.LocalDateTime;

@Data
public class DailyLogDTO {
    private Long id;
    private String content;
    private String contentHtml;
    private String mood;
    private String weather;
    private String tags;
    private Integer wordCount;
    private LocalDate logDate;
    private LocalDateTime createTime;
    private LocalDateTime updateTime;
}
