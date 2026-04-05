package com.nanmuli.blog.application.dailylog.dto;

import com.fasterxml.jackson.annotation.JsonFormat;
import lombok.Data;

import java.io.Serializable;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;

@Data
public class DailyLogDTO implements Serializable {
    private static final long serialVersionUID = 1L;
    private Long id;
    private String content;
    private String contentHtml;
    private String mood;
    private String weather;
    private List<String> tags;
    private Integer wordCount;

    @JsonFormat(pattern = "yyyy-MM-dd")
    private LocalDate logDate;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime createTime;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime updateTime;
}
