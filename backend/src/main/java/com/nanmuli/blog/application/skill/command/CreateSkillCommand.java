package com.nanmuli.blog.application.skill.command;

import jakarta.validation.constraints.*;
import lombok.Data;

import java.io.Serializable;

/**
 * 创建技能命令
 */
@Data
public class CreateSkillCommand implements Serializable {
    private static final long serialVersionUID = 1L;

    /**
     * 技能名称
     */
    @NotBlank(message = "技能名称不能为空")
    @Size(max = 50, message = "技能名称长度不能超过50字符")
    private String name;

    /**
     * 技能分类
     */
    @NotBlank(message = "技能分类不能为空")
    private String category;

    /**
     * 熟练度（1-5）
     */
    @NotNull(message = "熟练度不能为空")
    @Min(value = 1, message = "熟练度最小值为1")
    @Max(value = 5, message = "熟练度最大值为5")
    private Integer proficiency;

    /**
     * 图标
     */
    private String icon;

    /**
     * 颜色（十六进制）
     */
    @Pattern(regexp = "^#[0-9A-Fa-f]{6}$", message = "颜色格式必须为十六进制，如#FF5733")
    private String color;

    /**
     * 描述
     */
    @Size(max = 500, message = "描述长度不能超过500字符")
    private String description;

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
