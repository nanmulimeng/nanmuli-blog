package com.nanmuli.blog.domain.skill;

import com.nanmuli.blog.shared.domain.BaseAggregateRoot;
import lombok.EqualsAndHashCode;
import lombok.Getter;
import lombok.Setter;

@Getter
@Setter
@EqualsAndHashCode(callSuper = false)
public class Skill extends BaseAggregateRoot<Long> {
    private static final long serialVersionUID = 1L;

    private String name;
    private String category;
    private Integer proficiency;
    private String icon;
    private String color;
    private String description;
    private Integer sort;
    private Integer status;
}
