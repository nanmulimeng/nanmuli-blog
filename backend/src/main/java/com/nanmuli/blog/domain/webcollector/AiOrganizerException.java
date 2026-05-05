package com.nanmuli.blog.domain.webcollector;

/**
 * AI 内容整理异常层次
 *
 * 位于领域层，应用层和基础设施层均可引用，
 * 避免应用层依赖基础设施层具体实现类。
 */
public final class AiOrganizerException {

    private AiOrganizerException() {}

    /** AI 输出被 token 限制截断，重试无意义 */
    public static class TruncatedException extends RuntimeException {
        public TruncatedException(String message) { super(message); }
    }

    /** API 客户端错误（401/403/400），重试无法恢复 */
    public static class UnrecoverableException extends RuntimeException {
        public UnrecoverableException(String message) { super(message); }
    }

    /** API 限速（429），需更长退避 */
    public static class RateLimitException extends RuntimeException {
        public RateLimitException(String message) { super(message); }
    }
}
