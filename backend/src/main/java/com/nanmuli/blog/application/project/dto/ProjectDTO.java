package com.nanmuli.blog.application.project.dto;

import lombok.Data;

import java.time.LocalDate;
import java.time.LocalDateTime;

@Data
public class ProjectDTO {
    private Long id;
    private String name;
    private String slug;
    private String description;
    private String cover;
    private String screenshots;
    private String techStack;
    private String githubUrl;
    private String demoUrl;
    private String docUrl;
    private Integer sort;
    private LocalDate startDate;
    private LocalDate endDate;
    private LocalDateTime createTime;
}
