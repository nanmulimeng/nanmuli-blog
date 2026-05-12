package com.nanmuli.blog.application.proxy.command;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;

@Schema(description = "选择代理节点命令")
public record SelectProxyCommand(
        @NotBlank(message = "代理组名称不能为空")
        @Schema(description = "代理组名称", example = "PROXY")
        String groupName,

        @NotBlank(message = "节点名称不能为空")
        @Schema(description = "节点名称", example = "🇭🇰 香港节点")
        String nodeName
) {}
