package com.nanmuli.blog.shared.domain;

import java.io.Serializable;
import java.time.LocalDateTime;
import java.util.UUID;

/**
 * 领域事件标记接口
 * 所有领域事件必须实现此接口
 */
public interface DomainEvent extends Serializable {

    /**
     * 获取事件ID
     */
    default String getEventId() {
        return UUID.randomUUID().toString();
    }

    /**
     * 获取事件发生时间
     */
    default LocalDateTime getOccurredOn() {
        return LocalDateTime.now();
    }

    /**
     * 获取事件类型
     */
    String getEventType();

    /**
     * 获取聚合根ID
     */
    String getAggregateId();
}
