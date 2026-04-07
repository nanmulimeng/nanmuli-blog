package com.nanmuli.blog.application.webcollector.command;

import jakarta.validation.constraints.Size;
import lombok.Data;

import java.time.LocalDate;

/**
 * 采集任务转为技术日志命令
 */
@Data
public class ConvertToDailyLogCommand {

    @Size(max = 50, message = "心情长度不能超过 50")
    private String mood;

    @Size(max = 50, message = "天气长度不能超过 50")
    private String weather;

    private LocalDate logDate; // 不传则使用当天

    private Boolean isPublic = false;

    private Long categoryId;
}
