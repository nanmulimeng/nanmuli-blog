package com.nanmuli.blog.domain.category;

import com.nanmuli.blog.shared.domain.BaseAggregateRoot;
import lombok.EqualsAndHashCode;
import lombok.Getter;
import lombok.Setter;

@Getter
@Setter
@EqualsAndHashCode(callSuper = false)
public class Category extends BaseAggregateRoot<Long> {
    private static final long serialVersionUID = 1L;

    private String name;
    private String slug;
    private String description;
    private String icon;
    private String color;
    private Integer sort;
    private Long parentId;
    private Integer articleCount;
    private Integer status;
}
