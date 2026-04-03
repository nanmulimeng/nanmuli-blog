package com.nanmuli.blog.domain.article;

import com.nanmuli.blog.shared.domain.BaseAggregateRoot;
import lombok.EqualsAndHashCode;
import lombok.Getter;
import lombok.Setter;

import java.time.LocalDateTime;

@Getter
@Setter
@EqualsAndHashCode(callSuper = false)
public class Article extends BaseAggregateRoot<Long> {
    private static final long serialVersionUID = 1L;

    private String title;
    private String slug;
    private String content;
    private String contentHtml;
    private String summary;
    private String cover;
    private Long categoryId;
    private Long userId;
    private Integer viewCount;
    private Integer likeCount;
    private Integer wordCount;
    private Integer readingTime;
    private Integer status;
    private Boolean isTop;
    private Boolean isOriginal;
    private String originalUrl;
    private LocalDateTime publishTime;

    public ArticleId articleId() {
        return new ArticleId(this.id);
    }

    public ArticleStatus articleStatus() {
        return ArticleStatus.of(this.status);
    }

    public void publish() {
        this.status = ArticleStatus.PUBLISHED.getCode();
        this.publishTime = LocalDateTime.now();
    }

    public void draft() {
        this.status = ArticleStatus.DRAFT.getCode();
    }

    public void recycle() {
        this.status = ArticleStatus.RECYCLED.getCode();
    }

    public boolean isPublished() {
        return status != null && status == ArticleStatus.PUBLISHED.getCode();
    }

    public void calculateWordCount() {
        if (this.content != null) {
            this.wordCount = this.content.replaceAll("\\s+", "").length();
            this.readingTime = Math.max(1, this.wordCount / 300);
        }
    }
}
