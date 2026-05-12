package com.nanmuli.blog.application.proxy.dto;

import io.swagger.v3.oas.annotations.media.Schema;

@Schema(description = "代理状态")
public record ProxyStatusDTO(
        @Schema(description = "是否启用") boolean enabled,
        @Schema(description = "代理地址") String url,
        @Schema(description = "Mihomo 是否可达") boolean mihomoReachable,
        @Schema(description = "代理连通延迟(ms)") Long latencyMs,
        @Schema(description = "状态消息") String message,
        @Schema(description = "订阅地址") String subscriptionUrl
) {}
