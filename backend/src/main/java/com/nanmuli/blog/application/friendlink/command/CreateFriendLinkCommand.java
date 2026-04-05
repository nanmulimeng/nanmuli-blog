package com.nanmuli.blog.application.friendlink.command;

import jakarta.validation.constraints.*;
import lombok.Data;

import java.io.Serializable;

/**
 * 创建友链命令
 */
@Data
public class CreateFriendLinkCommand implements Serializable {
    private static final long serialVersionUID = 1L;

    /**
     * 网站名称
     */
    @NotBlank(message = "网站名称不能为空")
    @Size(max = 50, message = "网站名称长度不能超过50字符")
    private String name;

    /**
     * 网站链接
     */
    @NotBlank(message = "网站链接不能为空")
    @Pattern(regexp = "^https?://.*$", message = "网站链接必须是http或https协议")
    @Size(max = 500, message = "网站链接长度不能超过500字符")
    private String url;

    /**
     * 网站Logo
     */
    @Size(max = 500, message = "Logo链接长度不能超过500字符")
    private String logo;

    /**
     * 网站描述
     */
    @Size(max = 200, message = "网站描述长度不能超过200字符")
    private String description;

    /**
     * 联系邮箱
     */
    @Email(message = "邮箱格式不正确")
    @Size(max = 100, message = "邮箱长度不能超过100字符")
    private String email;

    /**
     * 排序
     */
    private Integer sort;

    /**
     * 状态：1-显示 0-隐藏
     */
    @NotNull(message = "状态不能为空")
    @Min(value = 0, message = "状态值不正确")
    @Max(value = 1, message = "状态值不正确")
    private Integer status = 1;
}
