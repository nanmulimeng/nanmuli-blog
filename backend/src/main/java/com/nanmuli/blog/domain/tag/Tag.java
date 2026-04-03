package com.nanmuli.blog.domain.tag;

import com.nanmuli.blog.shared.domain.BaseAggregateRoot;
import lombok.EqualsAndHashCode;
import lombok.Getter;
import lombok.Setter;

@Getter
@Setter
@EqualsAndHashCode(callSuper = false)
public class Tag extends BaseAggregateRoot<Long> {
    private static final long serialVersionUID = 1L;

    private String name;
    private String slug;
    private String color;
    private String icon;
    private String description;
    private Integer articleCount;
    private Integer status;
}
