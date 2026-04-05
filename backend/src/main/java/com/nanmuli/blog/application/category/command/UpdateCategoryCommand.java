package com.nanmuli.blog.application.category.command;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import lombok.Data;

import java.io.Serializable;

/**
 * 更新分类命令
 */
@Data
public class UpdateCategoryCommand implements Serializable {
    private static final long serialVersionUID = 1L;

    /**
     * 分类ID（从路径参数传入，不需要在请求体中）
     */
    private Long id;

    /**
     * 父分类ID（null表示根分类）
     */
    private Long parentId;

    /**
     * 分类名称
     */
    @NotBlank(message = "分类名称不能为空")
    @Size(max = 50, message = "分类名称不能超过50个字符")
    private String name;

    /**
     * URL别名
     */
    @NotBlank(message = "分类标识不能为空")
    @Size(max = 50, message = "分类标识不能超过50个字符")
    @Pattern(regexp = "^[a-z0-9-]+$", message = "分类标识只能包含小写字母、数字和连字符")
    private String slug;

    /**
     * 描述
     */
    @Size(max = 200, message = "描述不能超过200个字符")
    private String description;

    /**
     * 图标（Element Plus图标名称或其他）
     */
    @Size(max = 50, message = "图标名称不能超过50个字符")
    private String icon;

    /**
     * 颜色
     */
    @Pattern(regexp = "^#[0-9A-Fa-f]{6}$", message = "颜色格式必须为十六进制，如#FF6B6B")
    private String color = "#409EFF";  // 默认蓝色

    /**
     * 排序号
     */
    @NotNull(message = "排序号不能为空")
    private Integer sort;

    /**
     * 是否为叶子节点（true-可关联文章，false-父分类容器）
     */
    @NotNull(message = "分类类型不能为空")
    private Boolean isLeaf;

    /**
     * 状态：1-启用 0-禁用
     */
    @NotNull(message = "状态不能为空")
    private Integer status;
}
