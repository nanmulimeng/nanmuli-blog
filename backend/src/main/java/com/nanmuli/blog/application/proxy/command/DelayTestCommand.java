package com.nanmuli.blog.application.proxy.command;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;

import java.util.List;

@Schema(description = "延迟测试命令")
public record DelayTestCommand(
        @NotBlank(message = "代理组名称不能为空")
        @Schema(description = "代理组名称", example = "PROXY")
        String groupName,

        @Schema(description = "要测试的节点列表，不填则测试全部")
        List<String> nodeNames
) {}
