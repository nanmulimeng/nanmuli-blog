package com.nanmuli.blog.domain.project;

import com.baomidou.mybatisplus.annotation.TableName;
import com.nanmuli.blog.shared.domain.BaseAggregateRoot;
import lombok.EqualsAndHashCode;
import lombok.Getter;
import lombok.Setter;

import java.time.LocalDate;

@Getter
@Setter
@EqualsAndHashCode(callSuper = false)
@TableName("project_showcase")
public class Project extends BaseAggregateRoot<Long> {
    private static final long serialVersionUID = 1L;

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
    private Integer status;
    private LocalDate startDate;
    private LocalDate endDate;
}
