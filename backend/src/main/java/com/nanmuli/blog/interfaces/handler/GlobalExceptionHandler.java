package com.nanmuli.blog.interfaces.handler;

import cn.dev33.satoken.exception.NotLoginException;
import cn.dev33.satoken.exception.NotPermissionException;
import com.nanmuli.blog.shared.exception.BusinessException;
import com.nanmuli.blog.shared.result.Result;
import jakarta.servlet.http.HttpServletRequest;
import lombok.extern.slf4j.Slf4j;
import org.slf4j.MDC;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;

import java.util.UUID;

@Slf4j
@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(BusinessException.class)
    public Result<Void> handleBusinessException(BusinessException e) {
        return Result.error(e.getCode(), e.getMessage());
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public Result<Void> handleMethodArgumentNotValidException(MethodArgumentNotValidException e) {
        String message = e.getBindingResult().getFieldErrors().stream()
                .findFirst()
                .map(error -> error.getDefaultMessage())
                .orElse("请求参数错误");
        return Result.error(400, message);
    }

    @ExceptionHandler(NotLoginException.class)
    public Result<Void> handleNotLoginException(NotLoginException e) {
        log.warn("未登录访问: {}", e.getMessage());
        return Result.error(401, "请先登录");
    }

    @ExceptionHandler(NotPermissionException.class)
    public Result<Void> handleNotPermissionException(NotPermissionException e) {
        log.warn("无权限访问: {}", e.getMessage());
        return Result.error(403, "权限不足");
    }

    /**
     * 处理参数类型不匹配异常（如路径参数无法转换为期望类型）
     */
    @ExceptionHandler(MethodArgumentTypeMismatchException.class)
    public Result<Void> handleMethodArgumentTypeMismatchException(MethodArgumentTypeMismatchException e, HttpServletRequest request) {
        log.warn("参数类型不匹配: uri={}, param={}, value={}, error={}",
                request.getRequestURI(), e.getName(), e.getValue(), e.getMessage());
        return Result.error(400, "请求参数格式错误");
    }

    @ExceptionHandler(HttpMessageNotReadableException.class)
    public Result<Void> handleHttpMessageNotReadableException(HttpMessageNotReadableException e, HttpServletRequest request) {
        log.warn("请求体解析失败: uri={}, error={}", request.getRequestURI(), e.getMessage());
        return Result.error(400, "请求数据格式错误");
    }

    @ExceptionHandler(Exception.class)
    public Result<Void> handleException(Exception e, HttpServletRequest request) {
        String traceId = MDC.get("traceId");
        if (traceId == null) {
            traceId = UUID.randomUUID().toString().replace("-", "");
        }
        String desensitizedMessage = desensitize(e.getMessage());
        log.error("[traceId={}] 系统异常, uri={}, method={}, error={}", traceId, request.getRequestURI(), request.getMethod(), desensitizedMessage, e);
        return Result.error(500, "系统繁忙，请稍后再试");
    }

    /**
     * 敏感信息脱敏处理
     */
    private String desensitize(String message) {
        if (message == null) return null;
        // 脱敏密码
        message = message.replaceAll("(?i)(password|pwd|secret|key)=[^&\\s]*", "$1=***");
        // 脱敏Token
        message = message.replaceAll("(?i)(token|authorization)[:=][^\\s]*", "$1:***");
        return message;
    }
}
