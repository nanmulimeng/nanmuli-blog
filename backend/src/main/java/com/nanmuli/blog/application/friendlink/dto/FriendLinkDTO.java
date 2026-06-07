package com.nanmuli.blog.application.friendlink.dto;

import com.fasterxml.jackson.annotation.JsonFormat;
import com.fasterxml.jackson.databind.annotation.JsonSerialize;
import com.fasterxml.jackson.databind.ser.std.ToStringSerializer;
import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import lombok.Data;

import java.io.Serializable;
import java.time.LocalDateTime;

@Data
public class FriendLinkDTO implements Serializable {
    private static final long serialVersionUID = 1L;

    @JsonSerialize(using = ToStringSerializer.class)
    private Long id;

    @NotBlank(message = "网站名称不能为空")
    @Size(max = 50, message = "网站名称长度不能超过50字符")
    private String name;

    @NotBlank(message = "网站链接不能为空")
    @Pattern(regexp = "^https?://.*$", message = "网站链接必须是http或https协议")
    @Size(max = 500, message = "网站链接长度不能超过500字符")
    private String url;

    @Size(max = 500, message = "Logo链接长度不能超过500字符")
    private String logo;

    @Size(max = 200, message = "网站描述长度不能超过200字符")
    private String description;

    @Email(message = "邮箱格式不正确")
    @Size(max = 100, message = "邮箱长度不能超过100字符")
    private String email;

    private Integer sort;

    @NotNull(message = "状态不能为空")
    @Min(value = 0, message = "状态值不正确")
    @Max(value = 1, message = "状态值不正确")
    private Integer status;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime createTime;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime updateTime;
}
