package com.nanmuli.blog.application.dailylog.dto;

import com.fasterxml.jackson.annotation.JsonFormat;
import com.fasterxml.jackson.databind.annotation.JsonSerialize;
import com.fasterxml.jackson.databind.ser.std.ToStringSerializer;
import lombok.Data;

import java.io.Serializable;
import java.time.LocalDate;
import java.time.LocalDateTime;

@Data
public class DailyLogDTO implements Serializable {
    private static final long serialVersionUID = 1L;

    @JsonSerialize(using = ToStringSerializer.class)
    private Long id;
    private String content;
    private String contentHtml;
    private String mood;
    private String weather;
    private Integer wordCount;

    @JsonFormat(pattern = "yyyy-MM-dd")
    private LocalDate logDate;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime createTime;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime updateTime;

    private Boolean isPublic;

    @JsonSerialize(using = ToStringSerializer.class)
    private Long categoryId;

    private com.nanmuli.blog.application.category.dto.CategoryDTO category;
}
