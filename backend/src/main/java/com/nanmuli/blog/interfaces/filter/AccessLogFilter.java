package com.nanmuli.blog.interfaces.filter;

import jakarta.servlet.*;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.extern.slf4j.Slf4j;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;

import java.io.IOException;

@Slf4j
@Component
@Order(Ordered.HIGHEST_PRECEDENCE + 2)
public class AccessLogFilter implements Filter {

    private static final String HEALTH_PATH = "/health";

    @Override
    public void doFilter(ServletRequest request, ServletResponse response, FilterChain chain)
            throws IOException, ServletException {
        HttpServletRequest httpRequest = (HttpServletRequest) request;
        HttpServletResponse httpResponse = (HttpServletResponse) response;

        String path = httpRequest.getRequestURI();
        boolean skipLog = path.equals(HEALTH_PATH);

        long start = System.nanoTime();
        try {
            chain.doFilter(request, response);
        } finally {
            if (!skipLog) {
                long durationMs = (System.nanoTime() - start) / 1_000_000;
                int status = httpResponse.getStatus();
                String method = httpRequest.getMethod();

                if (status >= 500) {
                    log.warn("[AccessLog] method={} path={} status={} duration={}ms",
                            method, path, status, durationMs);
                } else if (status >= 400) {
                    log.info("[AccessLog] method={} path={} status={} duration={}ms",
                            method, path, status, durationMs);
                } else {
                    log.debug("[AccessLog] method={} path={} status={} duration={}ms",
                            method, path, status, durationMs);
                }
            }
        }
    }
}
