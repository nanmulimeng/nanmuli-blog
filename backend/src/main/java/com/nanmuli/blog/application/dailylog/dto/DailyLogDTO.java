package com.nanmuli.blog.application.dailylog.dto;

import com.fasterxml.jackson.annotation.JsonFormat;
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

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime createTime;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime updateTime;
}
