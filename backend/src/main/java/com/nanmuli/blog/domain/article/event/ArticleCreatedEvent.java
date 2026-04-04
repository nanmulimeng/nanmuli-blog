package com.nanmuli.blog.domain.article.event;

import com.nanmuli.blog.shared.domain.DomainEvent;
import lombok.Getter;

import java.time.LocalDateTime;

/**
 * 文章创建领域事件
 */
@Getter
public class ArticleCreatedEvent implements DomainEvent {

    private static final long serialVersionUID = 1L;

    private final String eventId;
    private final LocalDateTime occurredOn;
    private final Long articleId;
    private final String title;

    public ArticleCreatedEvent(Long articleId, String title) {
        this.eventId = java.util.UUID.randomUUID().toString();
        this.occurredOn = LocalDateTime.now();
        this.articleId = articleId;
        this.title = title;
    }

    @Override
    public String getEventType() {
        return "ARTICLE_CREATED";
    }

    @Override
    public String getAggregateId() {
        return articleId.toString();
    }
}
