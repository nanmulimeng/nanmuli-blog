package com.nanmuli.blog.application.proxy.dto;

import io.swagger.v3.oas.annotations.media.Schema;

@Schema(description = "代理节点")
public record ProxyNodeDTO(
        @Schema(description = "节点名称") String name,
        @Schema(description = "节点类型") String type,
        @Schema(description = "延迟(ms)，null=未测试") Integer delay
) {}
