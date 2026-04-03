package com.nanmuli.blog.application.user.dto;

import lombok.Data;

import java.time.LocalDateTime;

@Data
public class UserDTO {
    private Long id;
    private String username;
    private String nickname;
    private String avatar;
    private String email;
    private String phone;
    private String role;
    private Integer status;
    private String loginIp;
    private LocalDateTime loginTime;
    private LocalDateTime createTime;
}
