package com.nanmuli.blog.application.tag.dto;

import lombok.Data;

import java.time.LocalDateTime;

@Data
public class TagDTO {
    private Long id;
    private String name;
    private String slug;
    private String color;
    private String icon;
    private Integer articleCount;
    private LocalDateTime createdAt;
}
