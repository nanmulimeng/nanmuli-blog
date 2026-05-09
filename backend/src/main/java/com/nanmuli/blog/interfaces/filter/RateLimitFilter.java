package com.nanmuli.blog.interfaces.filter;

import jakarta.servlet.*;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * IP-based rate limit filter for public API endpoints.
 * Default: 60 requests per minute per IP for /api/ paths (excluding /api/admin/ and /api/internal/).
 */
@Slf4j
@Component
@Order(Ordered.HIGHEST_PRECEDENCE + 1)
public class RateLimitFilter implements Filter {

    @Value("${rate-limit.max-requests:60}")
    private int maxRequestsPerMinute;

    @Value("${rate-limit.window-seconds:60}")
    private int windowSeconds;

    @Value("${rate-limit.trusted-proxies:}")
    private String trustedProxies;

    @Value("${rate-limit.max-tracked-ips:10000}")
    private int maxTrackedIps;

    private Set<String> trustedProxySet = Set.of();
    private final ConcurrentHashMap<String, RequestCounter> counters = new ConcurrentHashMap<>();
    private ScheduledExecutorService cleaner;

    @Override
    public void init(FilterConfig filterConfig) {
        if (trustedProxies != null && !trustedProxies.isBlank()) {
            trustedProxySet = Set.of(trustedProxies.split(","));
        }
        cleaner = Executors.newSingleThreadScheduledExecutor(r -> {
            Thread t = new Thread(r, "rate-limit-cleaner");
            t.setDaemon(true);
            return t;
        });
        cleaner.scheduleAtFixedRate(this::cleanup, windowSeconds, windowSeconds, TimeUnit.SECONDS);
    }

    @Override
    public void doFilter(ServletRequest request, ServletResponse response, FilterChain chain) throws IOException, ServletException {
        HttpServletRequest httpRequest = (HttpServletRequest) request;
        String path = httpRequest.getRequestURI();

        if (!shouldRateLimit(path)) {
            chain.doFilter(request, response);
            return;
        }

        String clientIp = resolveClientIp(httpRequest);

        if (counters.size() >= maxTrackedIps && !counters.containsKey(clientIp)) {
            log.warn("[RateLimit] Tracked IP limit reached ({}), forcing cleanup", maxTrackedIps);
            cleanup();
        }

        RequestCounter counter = counters.computeIfAbsent(clientIp, k -> new RequestCounter(windowSeconds));

        if (counter.incrementAndGet() > maxRequestsPerMinute) {
            log.warn("[RateLimit] IP {} exceeded {} requests/{}s on {}", clientIp, maxRequestsPerMinute, windowSeconds, path);
            HttpServletResponse httpResponse = (HttpServletResponse) response;
            httpResponse.setStatus(429);
            httpResponse.setContentType("application/json;charset=UTF-8");
            httpResponse.getWriter().write("{\"code\":429,\"message\":\"Too Many Requests\",\"data\":null}");
            return;
        }

        chain.doFilter(request, response);
    }

    private boolean shouldRateLimit(String path) {
        if (path == null || !path.startsWith("/api/")) {
            return false;
        }
        return !path.startsWith("/api/admin/") && !path.startsWith("/api/internal/");
    }

    private String resolveClientIp(HttpServletRequest request) {
        String remoteAddr = request.getRemoteAddr();

        // 仅在受信任代理后时才读取 X-Forwarded-For
        if (!trustedProxySet.isEmpty() && trustedProxySet.contains(remoteAddr)) {
            String xff = request.getHeader("X-Forwarded-For");
            if (xff != null && !xff.isBlank() && !"unknown".equalsIgnoreCase(xff)) {
                return xff.split(",")[0].trim();
            }
            String realIp = request.getHeader("X-Real-IP");
            if (realIp != null && !realIp.isBlank() && !"unknown".equalsIgnoreCase(realIp)) {
                return realIp.trim();
            }
        }

        return remoteAddr;
    }

    private void cleanup() {
        long now = System.currentTimeMillis();
        long threshold = now - TimeUnit.SECONDS.toMillis(windowSeconds);
        counters.entrySet().removeIf(entry -> entry.getValue().isExpired(threshold));
    }

    @Override
    public void destroy() {
        if (cleaner != null) {
            cleaner.shutdownNow();
        }
        counters.clear();
    }

    private static class RequestCounter {
        private final AtomicInteger count = new AtomicInteger(0);
        private volatile long windowStart = System.currentTimeMillis();
        private final long windowMillis;

        RequestCounter(int windowSeconds) {
            this.windowMillis = TimeUnit.SECONDS.toMillis(windowSeconds);
        }

        int incrementAndGet() {
            long now = System.currentTimeMillis();
            if (now - windowStart > windowMillis) {
                synchronized (this) {
                    if (now - windowStart > windowMillis) {
                        windowStart = now;
                        count.set(0);
                    }
                }
            }
            return count.incrementAndGet();
        }

        boolean isExpired(long threshold) {
            return windowStart < threshold;
        }
    }
}
