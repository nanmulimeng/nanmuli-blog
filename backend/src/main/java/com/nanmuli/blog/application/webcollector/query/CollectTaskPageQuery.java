package com.nanmuli.blog.application.webcollector.query;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import lombok.Data;

/**
 * 采集任务分页查询
 */
@Data
public class CollectTaskPageQuery {

    @Min(value = 1, message = "页码不能小于1")
    private Long current = 1L;

    @Min(value = 1, message = "每页数量不能小于1")
    @Max(value = 100, message = "每页数量不能超过100")
    private Long size = 10L;

    private Integer status; // 可选，按状态筛选
    private String taskType; // 可选，按任务类型筛选
}
