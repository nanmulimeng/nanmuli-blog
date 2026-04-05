package com.nanmuli.blog.domain.category;

import com.nanmuli.blog.shared.domain.BaseAggregateRoot;
import lombok.EqualsAndHashCode;
import lombok.Getter;
import lombok.Setter;

@Getter
@Setter
@EqualsAndHashCode(callSuper = false)
public class Category extends BaseAggregateRoot<Long> {
    private static final long serialVersionUID = 1L;

    private String name;
    private String slug;
    private String description;
    private String icon;
    private String color;
    private Integer sort;
    private Long parentId;
    private Integer articleCount;
    private Integer status;
    private Boolean isLeaf;

    /**
     * 是否为叶子节点（可关联文章）
     */
    public boolean isLeaf() {
        return isLeaf != null && isLeaf;
    }

    /**
     * 是否可关联文章
     */
    public boolean canAssociateArticle() {
        return isLeaf();
    }

    /**
     * 设置为叶子节点（原标签概念）
     */
    public void markAsLeaf() {
        this.isLeaf = true;
    }

    /**
     * 设置为父分类（容器节点，不可直接关联文章）
     */
    public void markAsParent() {
        this.isLeaf = false;
    }
}
