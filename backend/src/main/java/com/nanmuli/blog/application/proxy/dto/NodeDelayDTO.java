package com.nanmuli.blog.application.proxy.dto;

import io.swagger.v3.oas.annotations.media.Schema;

@Schema(description = "节点延迟测试结果")
public record NodeDelayDTO(
        @Schema(description = "节点名称") String nodeName,
        @Schema(description = "延迟(ms)，0=不可达") int delay,
        @Schema(description = "是否可达") boolean reachable
) {}
