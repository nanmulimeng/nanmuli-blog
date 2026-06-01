package com.nanmuli.blog.application.article.dto;

import com.fasterxml.jackson.databind.annotation.JsonSerialize;
import com.fasterxml.jackson.databind.ser.std.ToStringSerializer;
import lombok.Data;

import java.io.Serializable;
import java.util.List;

/**
 * 文章归档 DTO
 */
@Data
public class ArticleArchiveDTO implements Serializable {
    private static final long serialVersionUID = 1L;

    private String year;
    private String month;
    private Long count;
    private List<ArticleSimpleDTO> articles;

    @Data
    public static class ArticleSimpleDTO implements Serializable {
        private static final long serialVersionUID = 1L;

        @JsonSerialize(using = ToStringSerializer.class)
        private Long id;
        private String title;
        private String slug;
        private String publishTime;
    }
}
