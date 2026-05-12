package com.nanmuli.blog.application.proxy.dto;

import io.swagger.v3.oas.annotations.media.Schema;

import java.util.List;

@Schema(description = "代理组")
public record ProxyGroupDTO(
        @Schema(description = "组名称") String name,
        @Schema(description = "组类型: Selector/URLTest/Fallback/LoadBalance") String type,
        @Schema(description = "当前选中节点") String now,
        @Schema(description = "节点列表") List<ProxyNodeDTO> nodes
) {}
