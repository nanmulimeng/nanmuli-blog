package com.nanmuli.blog.application.article.query;

import com.nanmuli.blog.shared.query.BasePageQuery;
import jakarta.validation.constraints.Size;
import lombok.Data;
import lombok.EqualsAndHashCode;

@Data
@EqualsAndHashCode(callSuper = false)
public class ArticlePageQuery extends BasePageQuery {

    private Long categoryId;
    private Integer status;

    @Size(max = 100, message = "搜索关键词不能超过100个字符")
    private String keyword;

    private String sort;
}
