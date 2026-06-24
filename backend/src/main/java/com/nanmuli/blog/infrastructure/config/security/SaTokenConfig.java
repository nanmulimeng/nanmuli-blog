package com.nanmuli.blog.infrastructure.config.security;

import cn.dev33.satoken.interceptor.SaInterceptor;
import cn.dev33.satoken.stp.StpUtil;
import com.nanmuli.blog.infrastructure.config.ConfigService;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.HandlerInterceptor;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

import java.util.Set;

@Slf4j
@Configuration
@RequiredArgsConstructor
public class SaTokenConfig implements WebMvcConfigurer {

    private final ConfigService configService;

    private static final Set<String> LOCALHOST_ADDRESSES = Set.of(
            "127.0.0.1",
            "0:0:0:0:0:0:0:1",
            "::1"
    );

    @Override
    public void addInterceptors(InterceptorRegistry registry) {
        // B06-05: 当前仅校验登录（单 admin 场景，sys_user 均为 admin）。
        // 未来引入多角色时，需在 login 时存角色（StpUtil.getSession().set("role", user.getRole())），
        // 并在此处或 @SaCheckRole 注解追加角色校验，同时统一 role 种子值大小写（B06-11）。
        registry.addInterceptor(new SaInterceptor(handle -> StpUtil.checkLogin()))
                .addPathPatterns("/api/admin/**")
                .excludePathPatterns("/api/auth/login", "/api/internal/**");

        registry.addInterceptor(new HandlerInterceptor() {
            @Override
            public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) throws Exception {
                String remoteAddr = request.getRemoteAddr();
                if (!LOCALHOST_ADDRESSES.contains(remoteAddr) && !hasValidCallbackKey(request)) {
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

    private boolean hasValidCallbackKey(HttpServletRequest request) {
        String expectedKey = configService.get("crawler.callback.api-key", "");
        String requestKey = request.getHeader("X-Callback-Key");
        return expectedKey != null && !expectedKey.isBlank() && expectedKey.equals(requestKey);
    }
}
