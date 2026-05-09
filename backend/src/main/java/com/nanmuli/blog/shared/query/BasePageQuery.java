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

    @Min(value = 1, message = "页码不能小于1")
    protected Long current = 1L;

    @Min(value = 1, message = "每页数量不能小于1")
    @Max(value = 100, message = "每页数量不能超过100")
    protected Long size = 10L;
}
