package com.nanmuli.blog.application.project.command;

import jakarta.validation.constraints.NotNull;
import lombok.Data;
import lombok.EqualsAndHashCode;

/**
 * 更新项目命令
 */
@Data
@EqualsAndHashCode(callSuper = true)
public class UpdateProjectCommand extends CreateProjectCommand {
    private static final long serialVersionUID = 1L;

    /**
     * 项目ID
     */
    @NotNull(message = "项目ID不能为空")
    private Long id;
}
