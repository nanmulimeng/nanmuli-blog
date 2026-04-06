package com.nanmuli.blog.domain.article;

import com.baomidou.mybatisplus.annotation.TableName;
import com.nanmuli.blog.shared.domain.BaseAggregateRoot;
import lombok.EqualsAndHashCode;
import lombok.Getter;
import lombok.Setter;

import java.time.LocalDateTime;

/**
 * 文章阅读记录 - 用于统计独立访客(UV)
 */
@Getter
@Setter
@EqualsAndHashCode(callSuper = false)
@TableName("article_view_record")
public class ArticleViewRecord extends BaseAggregateRoot<Long> {
    private static final long serialVersionUID = 1L;

    private Long articleId;

    /**
     * 访客标识（前端生成的唯一ID，存储在localStorage中）
     */
    private String visitorId;

    /**
     * IP地址
     */
    private String ipAddress;

    /**
     * 用户代理字符串
     */
    private String userAgent;

    /**
     * 首次访问时间
     */
    private LocalDateTime firstViewTime;

    /**
     * 最后访问时间
     */
    private LocalDateTime lastViewTime;

    /**
     * 访问次数（该访客多次访问同一文章）
     */
    private Integer viewCount;
}
