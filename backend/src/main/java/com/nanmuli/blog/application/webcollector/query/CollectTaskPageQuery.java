package com.nanmuli.blog.application.webcollector.query;

import com.nanmuli.blog.shared.query.BasePageQuery;
import lombok.Data;
import lombok.EqualsAndHashCode;

/**
 * 采集任务分页查询
 */
@Data
@EqualsAndHashCode(callSuper = false)
public class CollectTaskPageQuery extends BasePageQuery {

    private Integer status; // 可选，按状态筛选
    private String taskType; // 可选，按任务类型筛选
    private String keyword; // 可选，按URL或搜索关键词模糊搜索
}
