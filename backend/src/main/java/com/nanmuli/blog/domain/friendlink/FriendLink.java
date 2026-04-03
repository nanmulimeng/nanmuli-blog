package com.nanmuli.blog.domain.friendlink;

import com.nanmuli.blog.shared.domain.BaseAggregateRoot;
import lombok.EqualsAndHashCode;
import lombok.Getter;
import lombok.Setter;

@Getter
@Setter
@EqualsAndHashCode(callSuper = false)
public class FriendLink extends BaseAggregateRoot<Long> {
    private static final long serialVersionUID = 1L;

    private String name;
    private String url;
    private String logo;
    private String description;
    private String email;
    private Integer sort;
    private Integer status;
}
