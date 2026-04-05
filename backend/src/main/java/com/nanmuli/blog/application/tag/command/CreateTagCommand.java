package com.nanmuli.blog.application.tag.command;

import jakarta.validation.constraints.*;
import lombok.Data;

import java.io.Serializable;

/**
 * 创建标签命令
 */
@Data
public class CreateTagCommand implements Serializable {
    private static final long serialVersionUID = 1L;

    /**
     * 标签名称
     */
    @NotBlank(message = "标签名称不能为空")
    @Size(max = 50, message = "标签名称长度不能超过50字符")
    private String name;

    /**
     * 标签标识（URL别名）
     */
    @Pattern(regexp = "^[a-z0-9-]+$", message = "标签标识只能包含小写字母、数字和连字符")
    @Size(max = 50, message = "标签标识长度不能超过50字符")
    private String slug;

    /**
     * 颜色（十六进制）
     */
    @Pattern(regexp = "^#[0-9A-Fa-f]{6}$", message = "颜色格式必须为十六进制，如#FF5733")
    private String color;

    /**
     * 图标
     */
    private String icon;

    /**
     * 状态：1-显示 0-隐藏
     */
    @NotNull(message = "状态不能为空")
    @Min(value = 0, message = "状态值不正确")
    @Max(value = 1, message = "状态值不正确")
    private Integer status = 1;
}
