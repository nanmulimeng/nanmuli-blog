package com.nanmuli.blog.application.article.query;

import lombok.Data;

@Data
public class ArticlePageQuery {
    private Integer current = 1;
    private Integer size = 10;
    private Long categoryId;
    private Integer status;
    private String keyword;
}
