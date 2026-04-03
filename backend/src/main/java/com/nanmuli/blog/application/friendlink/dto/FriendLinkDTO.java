package com.nanmuli.blog.application.friendlink.dto;

import lombok.Data;

import java.time.LocalDateTime;

@Data
public class FriendLinkDTO {
    private Long id;
    private String name;
    private String url;
    private String logo;
    private String description;
    private String email;
    private Integer sort;
    private LocalDateTime createTime;
}
