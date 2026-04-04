package com.nanmuli.blog.domain.article.event;

import com.nanmuli.blog.shared.domain.DomainEvent;
import lombok.Getter;

import java.time.LocalDateTime;

/**
 * 文章发布领域事件
 */
@Getter
public class ArticlePublishedEvent implements DomainEvent {

    private static final long serialVersionUID = 1L;

    private final String eventId;
    private final LocalDateTime occurredOn;
    private final Long articleId;
    private final String title;
    private final String slug;
    private final String content;
    private final Long categoryId;

    public ArticlePublishedEvent(Long articleId, String title, String slug, String content, Long categoryId) {
        this.eventId = java.util.UUID.randomUUID().toString();
        this.occurredOn = LocalDateTime.now();
        this.articleId = articleId;
        this.title = title;
        this.slug = slug;
        this.content = content;
        this.categoryId = categoryId;
    }

    @Override
    public String getEventType() {
        return "ARTICLE_PUBLISHED";
    }

    @Override
    public String getAggregateId() {
        return articleId.toString();
    }
}
