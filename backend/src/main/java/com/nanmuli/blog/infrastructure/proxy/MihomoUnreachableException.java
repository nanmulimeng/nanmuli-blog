package com.nanmuli.blog.infrastructure.proxy;

import com.nanmuli.blog.shared.exception.BusinessException;

/**
 * Mihomo API 不可达异常
 */
public class MihomoUnreachableException extends BusinessException {

    public MihomoUnreachableException() {
        super(503, "Mihomo 代理服务不可达，请检查 Mihomo 是否已启动");
    }

    public MihomoUnreachableException(String message) {
        super(503, message);
    }
}
