package com.nanmuli.blog.application.skill.dto;

import lombok.Data;

import java.time.LocalDateTime;

@Data
public class SkillDTO {
    private Long id;
    private String name;
    private String category;
    private Integer proficiency;
    private String icon;
    private String color;
    private String description;
    private Integer sort;
    private LocalDateTime createdAt;
}
