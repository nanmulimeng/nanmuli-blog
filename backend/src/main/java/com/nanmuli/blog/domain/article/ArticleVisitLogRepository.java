package com.nanmuli.blog.domain.article;

import java.time.LocalDate;

public interface ArticleVisitLogRepository {

    /**
     * 保存访问日志
     */
    ArticleVisitLog save(ArticleVisitLog log);

    /**
     * 统计文章的总访问量（PV）
     */
    Long countByArticleId(Long articleId);

    /**
     * 统计文章今日访问量
     */
    Long countTodayByArticleId(Long articleId);

    /**
     * 统计所有文章的总访问量（PV）
     */
    Long countTotalVisits();

    /**
     * 统计所有文章今日访问量
     */
    Long countTodayVisits();
}
