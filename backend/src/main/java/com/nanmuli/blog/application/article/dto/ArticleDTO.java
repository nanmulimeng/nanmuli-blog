package com.nanmuli.blog.application.article.dto;

import com.nanmuli.blog.application.category.dto.CategoryDTO;
import com.nanmuli.blog.application.tag.dto.TagDTO;
import lombok.Data;

import java.time.LocalDateTime;
import java.util.List;

@Data
public class ArticleDTO {
    private Long id;
    private String title;
    private String slug;
    private String content;
    private String contentHtml;
    private String summary;
    private String cover;
    private CategoryDTO category;
    private List<TagDTO> tags;
    private Integer viewCount;
    private Integer likeCount;
    private Integer wordCount;
    private Integer readingTime;
    private Integer status;
    private Boolean isTop;
    private Boolean isOriginal;
    private String originalUrl;
    private LocalDateTime publishTime;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
