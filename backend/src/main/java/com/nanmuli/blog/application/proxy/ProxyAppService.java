package com.nanmuli.blog.application.proxy;

import com.nanmuli.blog.application.config.ConfigAppService;
import com.nanmuli.blog.application.config.dto.ConfigDTO;
import com.nanmuli.blog.application.proxy.dto.NodeDelayDTO;
import com.nanmuli.blog.application.proxy.dto.ProxyGroupDTO;
import com.nanmuli.blog.application.proxy.dto.ProxyNodeDTO;
import com.nanmuli.blog.application.proxy.dto.ProxyStatusDTO;
import com.nanmuli.blog.infrastructure.config.ConfigService;
import com.nanmuli.blog.infrastructure.proxy.MihomoProxyClient;
import com.nanmuli.blog.infrastructure.proxy.MihomoUnreachableException;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.*;

@Slf4j
@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class ProxyAppService {

    private final ConfigAppService configAppService;
    private final ConfigService configService;
    private final MihomoProxyClient mihomoProxyClient;

    // ==================== 代理状态 ====================

    public ProxyStatusDTO getStatus() {
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

        return new ProxyStatusDTO(
                enabled,
                proxyUrl != null ? proxyUrl : "",
                mihomoReachable,
                latencyMs,
                message,
                subUrl
        );
    }

    // ==================== 代理组管理 ====================

    public List<ProxyGroupDTO> getGroups() {
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

        return groups;
    }

    public void selectNode(String groupName, String nodeName) {
        mihomoProxyClient.selectProxy(groupName, nodeName);
    }

    // ==================== 延迟测试 ====================

    public List<NodeDelayDTO> testDelay(String groupName, List<String> nodeNames) {
        Map<String, Integer> delays = mihomoProxyClient.testDelay(groupName, null, 3000);

        List<NodeDelayDTO> results = new ArrayList<>();
        if (nodeNames != null && !nodeNames.isEmpty()) {
            for (String nodeName : nodeNames) {
                int delay = delays.getOrDefault(nodeName, 0);
                results.add(new NodeDelayDTO(nodeName, delay, delay > 0));
            }
        } else {
            for (Map.Entry<String, Integer> entry : delays.entrySet()) {
                boolean reachable = entry.getValue() > 0;
                results.add(new NodeDelayDTO(entry.getKey(), entry.getValue(), reachable));
            }
        }

        return results;
    }

    // ==================== 订阅管理 ====================

    public String getSubscriptionUrl() {
        ConfigDTO dto = configAppService.getByKey("crawler.proxy.subscription_url");
        return dto != null ? dto.getConfigValue() : "";
    }

    @Transactional
    public void updateSubscription(String url) {
        String targetUrl = url != null ? url.trim() : "";
        if (!targetUrl.isBlank()) {
            validateSubscriptionUrl(targetUrl); // B11-06 SSRF 防护
        }
        configAppService.update("crawler.proxy.subscription_url", targetUrl);
        configService.reload();

        if (!targetUrl.isBlank()) {
            try {
                mihomoProxyClient.updateProviderUrl("default", targetUrl);
            } catch (MihomoUnreachableException e) {
                log.warn("[Proxy] Mihomo unreachable, subscription URL saved to DB only");
            }
        }
    }

    /**
     * 校验订阅 URL，防止 SSRF（B11-06）。
     * 仅允许 http/https，且 host 不得为本地/内网字面地址。
     * 注意：基于字面 host 校验，无法防御 DNS rebinding（与 crawler ssrf_guard 同口径）。
     */
    private void validateSubscriptionUrl(String url) {
        java.net.URI uri;
        try {
            uri = java.net.URI.create(url);
        } catch (IllegalArgumentException e) {
            throw new IllegalArgumentException("无效的订阅 URL");
        }
        String scheme = uri.getScheme();
        if (!"http".equalsIgnoreCase(scheme) && !"https".equalsIgnoreCase(scheme)) {
            throw new IllegalArgumentException("订阅 URL 必须是 http 或 https 协议");
        }
        String host = uri.getHost();
        if (host == null || host.isBlank()) {
            throw new IllegalArgumentException("订阅 URL 缺少 host");
        }
        String lower = host.toLowerCase();
        if ("localhost".equals(lower) || lower.endsWith(".localhost")
                || "127.0.0.1".equals(lower) || "::1".equals(lower)
                || lower.startsWith("10.") || lower.startsWith("192.168.")
                || lower.startsWith("169.254.")
                || (lower.startsWith("172.") && isPrivate172(lower))) {
            throw new IllegalArgumentException("订阅 URL 不得指向本地/内网地址");
        }
    }

    private boolean isPrivate172(String host) {
        try {
            int octet = Integer.parseInt(host.split("\\.")[1]);
            return octet >= 16 && octet <= 31;
        } catch (NumberFormatException | ArrayIndexOutOfBoundsException e) {
            return false;
        }
    }

    public void refreshSubscription() {
        boolean ok = mihomoProxyClient.refreshProviderSafe("default");
        if (!ok) {
            throw new MihomoUnreachableException("订阅刷新失败，Mihomo 服务不可达");
        }
    }
}
