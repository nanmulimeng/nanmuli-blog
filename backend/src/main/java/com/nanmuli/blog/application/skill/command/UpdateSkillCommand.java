package com.nanmuli.blog.application.skill.command;

import jakarta.validation.constraints.*;
import lombok.Data;
import lombok.EqualsAndHashCode;

/**
 * 更新技能命令
 */
@Data
@EqualsAndHashCode(callSuper = true)
public class UpdateSkillCommand extends CreateSkillCommand {
    private static final long serialVersionUID = 1L;

    /**
     * 技能ID
     */
    @NotNull(message = "技能ID不能为空")
    private Long id;
}
