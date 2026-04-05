package com.nanmuli.blog.application.article.command;

import jakarta.validation.constraints.*;
import lombok.Data;

import java.io.Serializable;

/**
 * 创建文章命令
 */
@Data
public class CreateArticleCommand implements Serializable {
    private static final long serialVersionUID = 1L;

    /**
     * 标题
     */
    @NotBlank(message = "标题不能为空")
    @Size(max = 200, message = "标题长度不能超过200个字符")
    private String title;

    /**
     * URL别名（用于SEO）
     */
    @Pattern(regexp = "^[a-z0-9-]*$", message = "别名只能包含小写字母、数字和连字符")
    @Size(max = 200, message = "别名长度不能超过200个字符")
    private String slug;

    /**
     * 内容（Markdown格式）
     */
    @NotBlank(message = "内容不能为空")
    @Size(max = 50000, message = "内容长度不能超过50000个字符")
    private String content;

    /**
     * 封面图URL
     */
    @Size(max = 500, message = "封面图URL长度不能超过500个字符")
    private String cover;

    /**
     * 分类ID（必须是叶子分类）
     */
    private Long categoryId;

    /**
     * 摘要（为空时自动生成）
     */
    @Size(max = 500, message = "摘要长度不能超过500个字符")
    private String summary;

    /**
     * 是否原创
     */
    @NotNull(message = "是否原创不能为空")
    private Boolean isOriginal = true;

    /**
     * 原文链接（转载时填写）
     */
    @Size(max = 500, message = "原文链接长度不能超过500个字符")
    private String originalUrl;

    /**
     * 是否置顶
     */
    @NotNull(message = "置顶状态不能为空")
    private Boolean isTop = false;

    /**
     * 状态：1-已发布 2-草稿
     */
    @NotNull(message = "状态不能为空")
    @Min(value = 1, message = "状态值不正确")
    @Max(value = 2, message = "状态值不正确")
    private Integer status = 1;
}
