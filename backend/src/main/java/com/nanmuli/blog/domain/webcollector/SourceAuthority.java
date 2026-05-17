package com.nanmuli.blog.domain.webcollector;

import com.baomidou.mybatisplus.annotation.TableName;
import com.nanmuli.blog.shared.domain.BaseAggregateRoot;
import lombok.EqualsAndHashCode;
import lombok.Getter;
import lombok.Setter;

@Getter
@Setter
@EqualsAndHashCode(callSuper = false)
@TableName("source_authority")
public class SourceAuthority extends BaseAggregateRoot<Long> {
    private static final long serialVersionUID = 1L;

    private String domain;
    private Integer score;
    private String level;
    private Boolean isActive;
}
