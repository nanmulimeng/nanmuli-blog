package com.nanmuli.blog.application.tag.command;

import jakarta.validation.constraints.NotNull;
import lombok.Data;
import lombok.EqualsAndHashCode;

/**
 * 更新标签命令
 */
@Data
@EqualsAndHashCode(callSuper = true)
public class UpdateTagCommand extends CreateTagCommand {
    private static final long serialVersionUID = 1L;

    /**
     * 标签ID
     */
    @NotNull(message = "标签ID不能为空")
    private Long id;
}
