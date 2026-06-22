package com.nanmuli.blog.shared.query;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import lombok.Data;

/**
 * 分页查询基类
 * 统一 current/size 字段及校验规则
 */
@Data
public class BasePageQuery {

    public static final long MIN_PAGE_CURRENT = 1L;
    public static final long DEFAULT_PAGE_SIZE = 10L;
    public static final long MIN_PAGE_SIZE = 1L;
    public static final long MAX_PAGE_SIZE = 100L;

    @Min(value = 1, message = "页码不能小于1")
    protected Long current = 1L;

    @Min(value = 1, message = "每页数量不能小于1")
    @Max(value = 100, message = "每页数量不能超过100")
    protected Long size = 10L;
    public Long getCurrent() {
        return normalizeCurrent(current);
    }

    public Long getSize() {
        return normalizeSize(size);
    }

    public static long normalizeCurrent(Number value) {
        if (value == null) {
            return MIN_PAGE_CURRENT;
        }
        return Math.max(MIN_PAGE_CURRENT, value.longValue());
    }

    public static long normalizeSize(Number value) {
        if (value == null) {
            return DEFAULT_PAGE_SIZE;
        }
        return Math.max(MIN_PAGE_SIZE, Math.min(value.longValue(), MAX_PAGE_SIZE));
    }
}
