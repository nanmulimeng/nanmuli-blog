package com.nanmuli.blog.application.article.command;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.Data;

import java.util.List;

@Data
public class UpdateArticleCommand {
    @NotNull(message = "文章ID不能为空")
    private Long articleId;
    @NotBlank(message = "标题不能为空")
    private String title;
    private String slug;
    @NotBlank(message = "内容不能为空")
    private String content;
    private String cover;
    private Long categoryId;
    private List<Long> tagIds;
    private String summary;
    private Boolean isOriginal;
    private String originalUrl;
    private Boolean isTop;
}
