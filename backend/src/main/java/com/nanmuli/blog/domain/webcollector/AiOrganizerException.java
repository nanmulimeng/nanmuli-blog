package com.nanmuli.blog.domain.webcollector;

/**
 * AI 内容整理异常层次。
 */
public final class AiOrganizerException {

    private AiOrganizerException() {
    }

    /** AI 输出被 token 限制截断，重试通常无意义。 */
    public static class TruncatedException extends RuntimeException {
        public TruncatedException(String message) {
            super(message);
        }
    }

    /** API 客户端错误或配置错误，重试通常无法恢复。 */
    public static class UnrecoverableException extends RuntimeException {
        public UnrecoverableException(String message) {
            super(message);
        }
    }

    /** API 限流，需要更长退避。 */
    public static class RateLimitException extends RuntimeException {
        public RateLimitException(String message) {
            super(message);
        }
    }

    /** AI 输出格式合法但业务无效，例如正文为空或日报没有有效条目。 */
    public static class InvalidOutputException extends RuntimeException {
        public InvalidOutputException(String message) {
            super(message);
        }
    }
}
