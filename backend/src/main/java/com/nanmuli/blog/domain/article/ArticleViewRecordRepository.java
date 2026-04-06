package com.nanmuli.blog.domain.article;

import java.util.Optional;

public interface ArticleViewRecordRepository {

    /**
     * 保存阅读记录
     */
    ArticleViewRecord save(ArticleViewRecord record);

    /**
     * 根据文章ID和访客ID查找记录
     */
    Optional<ArticleViewRecord> findByArticleIdAndVisitorId(Long articleId, String visitorId);

    /**
     * 统计文章的独立访客数
     */
    Long countUniqueVisitorsByArticleId(Long articleId);

    /**
     * 统计所有文章的总独立访客数（去重）
     */
    Long countTotalUniqueVisitors();
}
