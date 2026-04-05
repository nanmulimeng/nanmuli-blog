package com.nanmuli.blog.application.friendlink.command;

import jakarta.validation.constraints.NotNull;
import lombok.Data;
import lombok.EqualsAndHashCode;

/**
 * 更新友链命令
 */
@Data
@EqualsAndHashCode(callSuper = true)
public class UpdateFriendLinkCommand extends CreateFriendLinkCommand {
    private static final long serialVersionUID = 1L;

    /**
     * 友链ID
     */
    @NotNull(message = "友链ID不能为空")
    private Long id;
}
