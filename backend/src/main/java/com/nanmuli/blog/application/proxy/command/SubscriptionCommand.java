package com.nanmuli.blog.application.proxy.command;

import io.swagger.v3.oas.annotations.media.Schema;

@Schema(description = "订阅管理命令")
public record SubscriptionCommand(
        @Schema(description = "订阅 URL", example = "https://example.com/subscription")
        String url
) {}
