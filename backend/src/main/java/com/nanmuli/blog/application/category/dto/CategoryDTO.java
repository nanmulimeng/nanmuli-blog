package com.nanmuli.blog.application.category.dto;

import lombok.Data;

import java.time.LocalDateTime;
import java.util.List;

@Data
public class CategoryDTO {
    private Long id;
    private String name;
    private String slug;
    private String description;
    private String icon;
    private String color;
    private Integer sort;
    private Long parentId;
    private Integer articleCount;
    private Boolean isLeaf;
    private Integer status;
    private LocalDateTime createdAt;
    private List<CategoryDTO> children;
}
