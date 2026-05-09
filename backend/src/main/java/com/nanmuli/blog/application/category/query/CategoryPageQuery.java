package com.nanmuli.blog.application.category.query;

import com.nanmuli.blog.shared.query.BasePageQuery;
import lombok.Data;
import lombok.EqualsAndHashCode;

/**
 * 分类分页查询参数
 */
@Data
@EqualsAndHashCode(callSuper = false)
public class CategoryPageQuery extends BasePageQuery {

    /**
     * 父分类ID（查询指定父分类下的子分类）
     */
    private Long parentId;

    /**
     * 类型筛选：true-叶子分类 false-父分类 null-全部
     */
    private Boolean isLeaf;

    /**
     * 状态筛选：1-启用 0-禁用 null-全部
     */
    private Integer status;

    /**
     * 关键词搜索（匹配名称或slug）
     */
    private String keyword;

    /**
     * 排序字段：sort-排序号 createTime-创建时间 updateTime-更新时间
     */
    private String sortField = "sort";

    /**
     * 排序方式：asc-升序 desc-降序
     */
    private String sortOrder = "asc";
}
