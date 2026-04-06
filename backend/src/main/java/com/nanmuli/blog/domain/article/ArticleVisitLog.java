package com.nanmuli.blog.domain.article;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.io.Serializable;
import java.time.LocalDateTime;

/**
 * 文章访问日志 - 用于统计PV（访问量）
 */
@Data
@TableName("article_visit_log")
public class ArticleVisitLog implements Serializable {
    private static final long serialVersionUID = 1L;

    @TableId(type = IdType.AUTO)
    private Long id;

    private Long articleId;

    /**
     * 访客标识
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
     * 访问时间
     */
    private LocalDateTime visitTime;

    /**
     * 创建时间
     */
    private LocalDateTime createdAt;
}
