package com.nanmuli.blog.domain.article;

import java.util.Collection;
import java.util.Map;
import java.util.Optional;

public interface ArticleViewRecordRepository {

    ArticleViewRecord save(ArticleViewRecord record);

    Optional<ArticleViewRecord> findByArticleIdAndVisitorId(Long articleId, String visitorId);

    Long countUniqueVisitorsByArticleId(Long articleId);

    /**
     * 批量统计多篇文章的独立访客数，避免 N+1 查询
     *
     * @return articleId -> count 的映射，不存在于 map 中的 articleId 表示 count=0
     */
    Map<Long, Long> countUniqueVisitorsByArticleIds(Collection<Long> articleIds);

    Long countTotalUniqueVisitors();
}
