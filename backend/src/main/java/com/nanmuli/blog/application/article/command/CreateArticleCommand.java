package com.nanmuli.blog.application.article.command;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.Data;

@Data
public class CreateArticleCommand {
    @NotBlank(message = "标题不能为空")
    private String title;
    private String slug;
    @NotBlank(message = "内容不能为空")
    private String content;
    private String cover;
    private Long categoryId;
    private String summary;
    private Boolean isOriginal = true;
    private String originalUrl;
    private Boolean isTop = false;
    private Integer status = 1;
}
