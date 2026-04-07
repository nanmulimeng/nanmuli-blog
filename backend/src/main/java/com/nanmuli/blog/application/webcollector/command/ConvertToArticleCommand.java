package com.nanmuli.blog.application.webcollector.command;

import jakarta.validation.constraints.Size;
import lombok.Data;

/**
 * 采集任务转为文章命令
 */
@Data
public class ConvertToArticleCommand {

    @Size(max = 200, message = "标题长度不能超过 200")
    private String title; // 不传则使用 aiTitle

    private Long categoryId;
}
