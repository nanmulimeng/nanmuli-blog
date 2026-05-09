package com.nanmuli.blog.infrastructure.config.security;

import cn.dev33.satoken.interceptor.SaInterceptor;
import cn.dev33.satoken.stp.StpUtil;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.HandlerInterceptor;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

import java.util.Set;

@Slf4j
@Configuration
public class SaTokenConfig implements WebMvcConfigurer {

    private static final Set<String> LOCALHOST_ADDRESSES = Set.of(
            "127.0.0.1",
            "0:0:0:0:0:0:0:1",
            "::1"
    );

    @Override
    public void addInterceptors(InterceptorRegistry registry) {
        registry.addInterceptor(new SaInterceptor(handle -> StpUtil.checkLogin()))
                .addPathPatterns("/api/admin/**")
                .excludePathPatterns("/api/auth/login", "/api/internal/**");

        registry.addInterceptor(new HandlerInterceptor() {
            @Override
            public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) throws Exception {
                String remoteAddr = request.getRemoteAddr();
                if (!LOCALHOST_ADDRESSES.contains(remoteAddr)) {
                    log.warn("[InternalEndpoint] Blocked non-localhost access from: {}, path={}", remoteAddr, request.getRequestURI());
                    response.setStatus(403);
                    response.setContentType("application/json;charset=UTF-8");
                    response.getWriter().write("{\"code\":403,\"message\":\"Access denied\",\"data\":null}");
                    return false;
                }
                return true;
            }
        }).addPathPatterns("/api/internal/**");
    }
}
