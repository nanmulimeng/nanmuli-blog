package com.nanmuli.blog.application.article.dto;

import lombok.Data;

import java.io.Serializable;

@Data
public class ArticleStatsDTO implements Serializable {
    private static final long serialVersionUID = 1L;
    private Long articleId;
    private String slug;
    private String title;

    /**
     * 总访问量（PV）
     */
    private Long visitCount;

    /**
     * 独立访客数（UV）
     */
    private Long visitorCount;

    /**
     * 今日访问量
     */
    private Long todayCount;
}
