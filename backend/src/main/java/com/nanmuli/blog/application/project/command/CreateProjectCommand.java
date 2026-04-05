package com.nanmuli.blog.application.project.command;

import jakarta.validation.constraints.*;
import lombok.Data;

import java.io.Serializable;
import java.time.LocalDate;
import java.util.List;

/**
 * 创建项目命令
 */
@Data
public class CreateProjectCommand implements Serializable {
    private static final long serialVersionUID = 1L;

    /**
     * 项目名称
     */
    @NotBlank(message = "项目名称不能为空")
    @Size(max = 100, message = "项目名称长度不能超过100字符")
    private String name;

    /**
     * 项目标识（URL别名）
     */
    @Pattern(regexp = "^[a-z0-9-]+$", message = "项目标识只能包含小写字母、数字和连字符")
    @Size(max = 100, message = "项目标识长度不能超过100字符")
    private String slug;

    /**
     * 项目描述
     */
    @Size(max = 2000, message = "项目描述长度不能超过2000字符")
    private String description;

    /**
     * 封面图URL
     */
    @Size(max = 500, message = "封面图URL长度不能超过500字符")
    private String cover;

    /**
     * 截图列表
     */
    private List<String> screenshots;

    /**
     * 技术栈
     */
    private List<String> techStack;

    /**
     * GitHub链接
     */
    @Pattern(regexp = "^(https?://.*)?$", message = "GitHub链接必须是http或https协议")
    @Size(max = 500, message = "GitHub链接长度不能超过500字符")
    private String githubUrl;

    /**
     * 演示链接
     */
    @Pattern(regexp = "^(https?://.*)?$", message = "演示链接必须是http或https协议")
    @Size(max = 500, message = "演示链接长度不能超过500字符")
    private String demoUrl;

    /**
     * 文档链接
     */
    @Pattern(regexp = "^(https?://.*)?$", message = "文档链接必须是http或https协议")
    @Size(max = 500, message = "文档链接长度不能超过500字符")
    private String docUrl;

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

    /**
     * 开始日期
     */
    private LocalDate startDate;

    /**
     * 结束日期
     */
    private LocalDate endDate;

    /**
     * 日期范围校验
     */
    @AssertTrue(message = "结束日期不能早于开始日期")
    public boolean isDateRangeValid() {
        if (startDate == null || endDate == null) {
            return true;
        }
        return !endDate.isBefore(startDate);
    }
}
