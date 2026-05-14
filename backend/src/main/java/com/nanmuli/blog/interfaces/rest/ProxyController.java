package com.nanmuli.blog.interfaces.rest;

import com.nanmuli.blog.application.proxy.ProxyAppService;
import com.nanmuli.blog.application.proxy.command.DelayTestCommand;
import com.nanmuli.blog.application.proxy.command.SelectProxyCommand;
import com.nanmuli.blog.application.proxy.command.SubscriptionCommand;
import com.nanmuli.blog.application.proxy.dto.NodeDelayDTO;
import com.nanmuli.blog.application.proxy.dto.ProxyGroupDTO;
import com.nanmuli.blog.application.proxy.dto.ProxyStatusDTO;
import com.nanmuli.blog.infrastructure.proxy.MihomoUnreachableException;
import com.nanmuli.blog.shared.result.Result;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@Tag(name = "代理管理")
@RestController
@RequestMapping("/api/admin/proxy")
@RequiredArgsConstructor
public class ProxyController {

    private final ProxyAppService proxyAppService;

    // ==================== 代理状态 ====================

    @Operation(summary = "获取代理状态")
    @GetMapping("/status")
    public Result<ProxyStatusDTO> status() {
        return Result.success(proxyAppService.getStatus());
    }

    // ==================== 代理组管理 ====================

    @Operation(summary = "获取所有代理组")
    @GetMapping("/groups")
    public Result<List<ProxyGroupDTO>> groups() {
        return Result.success(proxyAppService.getGroups());
    }

    @Operation(summary = "选择代理节点")
    @PutMapping("/groups/{name}")
    public Result<Void> selectNode(@PathVariable String name,
                                   @Valid @RequestBody SelectProxyCommand command) {
        proxyAppService.selectNode(command.groupName(), command.nodeName());
        return Result.success();
    }

    // ==================== 延迟测试 ====================

    @Operation(summary = "批量测试节点延迟")
    @PostMapping("/nodes/delay-test")
    public Result<List<NodeDelayDTO>> testDelay(@Valid @RequestBody DelayTestCommand command) {
        return Result.success(proxyAppService.testDelay(command.groupName(), command.nodeNames()));
    }

    // ==================== 订阅管理 ====================

    @Operation(summary = "获取订阅 URL")
    @GetMapping("/subscription")
    public Result<String> getSubscription() {
        return Result.success(proxyAppService.getSubscriptionUrl());
    }

    @Operation(summary = "更新订阅 URL")
    @PutMapping("/subscription")
    public Result<Void> updateSubscription(@Valid @RequestBody SubscriptionCommand command) {
        proxyAppService.updateSubscription(command.url());
        return Result.success();
    }

    @Operation(summary = "刷新订阅（触发 Mihomo 重新拉取）")
    @PostMapping("/subscription/refresh")
    public Result<Void> refreshSubscription() {
        proxyAppService.refreshSubscription();
        return Result.success();
    }

    // ==================== 全局异常处理（Mihomo 不可达） ====================

    @ExceptionHandler(MihomoUnreachableException.class)
    public Result<Void> handleMihomoUnreachable(MihomoUnreachableException e) {
        return Result.error(e.getCode(), e.getMessage());
    }
}
