package com.nanmuli.blog.application.category.dto;

import lombok.Data;

import java.time.LocalDateTime;

@Data
public class CategoryDTO {
    private Long id;
    private String name;
    private String slug;
    private String description;
    private String icon;
    private String color;
    private Integer sort;
    private Integer articleCount;
    private LocalDateTime createTime;
}
