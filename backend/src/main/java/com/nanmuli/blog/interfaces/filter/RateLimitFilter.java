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

    private final ConcurrentHashMap<String, RequestCounter> counters = new ConcurrentHashMap<>();
    private ScheduledExecutorService cleaner;

    @Override
    public void init(FilterConfig filterConfig) {
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
        String key = clientIp;
        RequestCounter counter = counters.computeIfAbsent(key, k -> new RequestCounter(windowSeconds));

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
        String ip = request.getHeader("X-Forwarded-For");
        if (ip != null && !ip.isBlank() && !"unknown".equalsIgnoreCase(ip)) {
            return ip.split(",")[0].trim();
        }
        ip = request.getHeader("X-Real-IP");
        if (ip != null && !ip.isBlank() && !"unknown".equalsIgnoreCase(ip)) {
            return ip.trim();
        }
        return request.getRemoteAddr();
    }

    private void cleanup() {
        long now = System.currentTimeMillis();
        long threshold = now - TimeUnit.SECONDS.toMillis(windowSeconds);
        counters.entrySet().removeIf(entry -> {
            if (entry.getValue().isExpired(threshold)) {
                return true;
            }
            return false;
        });
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
                        count.set(0);
                        windowStart = now;
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
