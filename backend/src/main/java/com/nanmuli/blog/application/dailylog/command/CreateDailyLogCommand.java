package com.nanmuli.blog.application.dailylog.command;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.Data;

import java.time.LocalDate;

@Data
public class CreateDailyLogCommand {
    @NotBlank(message = "内容不能为空")
    private String content;
    private String mood;
    private String weather;
    @NotNull(message = "日期不能为空")
    private LocalDate logDate;

    private Boolean isPublic;

    private Long categoryId;
}
