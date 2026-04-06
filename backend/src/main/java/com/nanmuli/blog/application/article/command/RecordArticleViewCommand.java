package com.nanmuli.blog.application.article.command;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.Data;

@Data
public class RecordArticleViewCommand {
    @NotNull(message = "文章ID不能为空")
    private Long articleId;

    @NotBlank(message = "访客ID不能为空")
    private String visitorId;
}
