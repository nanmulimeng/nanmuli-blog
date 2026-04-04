package com.nanmuli.blog.shared.domain;

import lombok.EqualsAndHashCode;
import lombok.Getter;
import lombok.Setter;

import java.io.Serializable;
import java.time.LocalDateTime;

/**
 * 领域实体抽象基类（纯净版，无框架依赖）
 * 用于真正的领域建模，不依赖任何持久化框架
 */
@Getter
@Setter
@EqualsAndHashCode
public abstract class AbstractDomainEntity<ID extends Serializable> implements Serializable {
    private static final long serialVersionUID = 1L;

    protected ID id;
    protected LocalDateTime createdAt;
    protected LocalDateTime updatedAt;
    protected Boolean isDeleted;

    /**
     * 判断是否为新建实体
     */
    public boolean isNew() {
        return id == null;
    }

    /**
     * 标记为已删除（软删除）
     */
    public void markDeleted() {
        this.isDeleted = true;
    }

    /**
     * 获取实体标识（用于日志、事件等）
     */
    public abstract String getEntityName();
}
