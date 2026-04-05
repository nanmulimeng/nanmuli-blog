package com.nanmuli.blog.application.article.dto;

import com.nanmuli.blog.application.category.dto.CategoryDTO;
import com.fasterxml.jackson.annotation.JsonFormat;
import com.fasterxml.jackson.databind.annotation.JsonSerialize;
import com.fasterxml.jackson.databind.ser.std.ToStringSerializer;
import lombok.Data;

import java.io.Serializable;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;

@Data
public class ArticleDTO implements Serializable {
    private static final long serialVersionUID = 1L;

    @JsonSerialize(using = ToStringSerializer.class)
    private Long id;
    private String title;
    private String slug;
    private String content;
    private String contentHtml;
    private String summary;
    private String cover;
    private CategoryDTO category;
    private List<CategoryDTO> categoryPath;  // 分类层级路径
    private List<String> tags;  // 简化为字符串列表（SEO关键词用途）
    private Integer viewCount;
    private Integer likeCount;
    private Integer wordCount;
    private Integer readingTime;
    private Integer status;
    private Boolean isTop;
    private Boolean isOriginal;
    private String originalUrl;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime publishTime;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime createTime;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime updateTime;
}
