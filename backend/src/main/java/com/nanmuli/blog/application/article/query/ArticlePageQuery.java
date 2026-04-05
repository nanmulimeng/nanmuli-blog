package com.nanmuli.blog.application.article.query;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import lombok.Data;

@Data
public class ArticlePageQuery {

    @Min(value = 1, message = "页码不能小于1")
    private Long current = 1L;

    @Min(value = 1, message = "每页数量不能小于1")
    @Max(value = 100, message = "每页数量不能超过100")
    private Long size = 10L;

    private Long categoryId;
    private Long tagId;
    private Integer status;
    private String keyword;
    private String sort;
}
