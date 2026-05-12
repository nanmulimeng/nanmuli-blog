package com.nanmuli.blog.interfaces.rest;

import com.nanmuli.blog.application.config.ConfigAppService;
import com.nanmuli.blog.application.config.dto.ConfigDTO;
import com.nanmuli.blog.application.proxy.command.DelayTestCommand;
import com.nanmuli.blog.application.proxy.command.SelectProxyCommand;
import com.nanmuli.blog.application.proxy.command.SubscriptionCommand;
import com.nanmuli.blog.application.proxy.dto.NodeDelayDTO;
import com.nanmuli.blog.application.proxy.dto.ProxyGroupDTO;
import com.nanmuli.blog.application.proxy.dto.ProxyNodeDTO;
import com.nanmuli.blog.application.proxy.dto.ProxyStatusDTO;
import com.nanmuli.blog.infrastructure.proxy.MihomoProxyClient;
import com.nanmuli.blog.infrastructure.proxy.MihomoUnreachableException;
import com.nanmuli.blog.shared.result.Result;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;

import java.util.*;

@Slf4j
@Tag(name = "代理管理")
@RestController
@RequestMapping("/api/admin/proxy")
@RequiredArgsConstructor
public class ProxyController {

    private final ConfigAppService configAppService;
    private final MihomoProxyClient mihomoProxyClient;

    // ==================== 代理状态 ====================

    @Operation(summary = "获取代理状态")
    @GetMapping("/status")
    public Result<ProxyStatusDTO> status() {
        ConfigDTO enabledDTO = configAppService.getByKey("crawler.proxy.enabled");
        ConfigDTO urlDTO = configAppService.getByKey("crawler.proxy.url");
        ConfigDTO subDTO = configAppService.getByKey("crawler.proxy.subscription_url");

        boolean enabled = "true".equals(enabledDTO.getConfigValue());
        String proxyUrl = urlDTO.getConfigValue();
        String subUrl = subDTO != null ? subDTO.getConfigValue() : "";

        boolean mihomoReachable = false;
        Long latencyMs = null;
        String message = null;

        if (enabled && proxyUrl != null && !proxyUrl.isBlank()) {
            long start = System.currentTimeMillis();
            mihomoReachable = mihomoProxyClient.healthCheck();
            latencyMs = System.currentTimeMillis() - start;
            if (!mihomoReachable) {
                message = "Mihomo 代理服务不可达，请检查 Mihomo 是否已启动";
            }
        } else {
            if (!enabled) {
                message = "代理未启用";
            } else {
                message = "代理地址未配置";
            }
        }

        return Result.success(new ProxyStatusDTO(
                enabled,
                proxyUrl != null ? proxyUrl : "",
                mihomoReachable,
                latencyMs,
                message,
                subUrl != null ? subUrl : ""
        ));
    }

    // ==================== 代理组管理 ====================

    @Operation(summary = "获取所有代理组")
    @GetMapping("/groups")
    public Result<List<ProxyGroupDTO>> groups() {
        Map<String, Object> proxies = mihomoProxyClient.getProxies();

        List<ProxyGroupDTO> groups = new ArrayList<>();
        for (Map.Entry<String, Object> entry : proxies.entrySet()) {
            if (!(entry.getValue() instanceof Map<?, ?> proxy)) {
                continue;
            }

            Object typeObj = proxy.get("type");
            String type = typeObj != null ? String.valueOf(typeObj) : "";
            Object nowObj = proxy.get("now");
            String now = nowObj != null ? String.valueOf(nowObj) : "";

            @SuppressWarnings("unchecked")
            List<String> allNodes = (List<String>) proxy.get("all");

            List<ProxyNodeDTO> nodes = new ArrayList<>();
            if (allNodes != null) {
                for (String nodeName : allNodes) {
                    Integer delay = null;
                    Object historyObj = proxy.get("history");
                    if (historyObj instanceof List<?> historyList) {
                        for (Object h : historyList) {
                            if (h instanceof Map<?, ?> hm) {
                                Object hmNow = hm.get("now");
                                if (nodeName.equals(hmNow != null ? String.valueOf(hmNow) : "")) {
                                    Object delayObj = hm.get("delay");
                                    if (delayObj instanceof Number) {
                                        delay = ((Number) delayObj).intValue();
                                    }
                                    break;
                                }
                            }
                        }
                    }
                    nodes.add(new ProxyNodeDTO(nodeName, "", delay));
                }
            }

            groups.add(new ProxyGroupDTO(entry.getKey(), type, now, nodes));
        }

        return Result.success(groups);
    }

    @Operation(summary = "选择代理节点")
    @PutMapping("/groups/{name}")
    public Result<Void> selectNode(@PathVariable String name,
                                   @Valid @RequestBody SelectProxyCommand command) {
        mihomoProxyClient.selectProxy(command.groupName(), command.nodeName());
        return Result.success();
    }

    // ==================== 延迟测试 ====================

    @Operation(summary = "批量测试节点延迟")
    @PostMapping("/nodes/delay-test")
    public Result<List<NodeDelayDTO>> testDelay(@Valid @RequestBody DelayTestCommand command) {
        Map<String, Integer> delays = mihomoProxyClient.testDelay(
                command.groupName(), null, 3000);

        List<NodeDelayDTO> results = new ArrayList<>();
        if (command.nodeNames() != null && !command.nodeNames().isEmpty()) {
            for (String nodeName : command.nodeNames()) {
                int delay = delays.getOrDefault(nodeName, 0);
                results.add(new NodeDelayDTO(nodeName, delay, delay > 0));
            }
        } else {
            for (Map.Entry<String, Integer> entry : delays.entrySet()) {
                boolean reachable = entry.getValue() > 0;
                results.add(new NodeDelayDTO(entry.getKey(), entry.getValue(), reachable));
            }
        }

        return Result.success(results);
    }

    // ==================== 订阅管理 ====================

    @Operation(summary = "获取订阅 URL")
    @GetMapping("/subscription")
    public Result<String> getSubscription() {
        ConfigDTO dto = configAppService.getByKey("crawler.proxy.subscription_url");
        return Result.success(dto != null ? dto.getConfigValue() : "");
    }

    @Operation(summary = "更新订阅 URL")
    @PutMapping("/subscription")
    public Result<Void> updateSubscription(@Valid @RequestBody SubscriptionCommand command) {
        String url = command.url() != null ? command.url() : "";
        configAppService.update("crawler.proxy.subscription_url", url);

        if (!url.isBlank()) {
            // 尝试推送到 Mihomo
            try {
                mihomoProxyClient.updateProviderUrl("default", url);
            } catch (MihomoUnreachableException e) {
                log.warn("[Proxy] Mihomo unreachable, subscription URL saved to DB only");
            }
        }

        return Result.success();
    }

    @Operation(summary = "刷新订阅（触发 Mihomo 重新拉取）")
    @PostMapping("/subscription/refresh")
    public Result<Void> refreshSubscription() {
        boolean ok = mihomoProxyClient.refreshProviderSafe("default");
        if (!ok) {
            return Result.error(503, "订阅刷新失败，Mihomo 服务不可达");
        }
        return Result.success();
    }

    // ==================== 全局异常处理（Mihomo 不可达） ====================

    @ExceptionHandler(MihomoUnreachableException.class)
    public Result<Void> handleMihomoUnreachable(MihomoUnreachableException e) {
        return Result.error(e.getCode(), e.getMessage());
    }
}
