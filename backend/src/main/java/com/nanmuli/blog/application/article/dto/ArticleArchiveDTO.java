package com.nanmuli.blog.application.article.dto;

import lombok.Data;

import java.util.List;

/**
 * 文章归档 DTO
 */
@Data
public class ArticleArchiveDTO {
    private String year;
    private String month;
    private Long count;
    private List<ArticleSimpleDTO> articles;

    @Data
    public static class ArticleSimpleDTO {
        private Long id;
        private String title;
        private String slug;
        private String publishTime;
    }
}
