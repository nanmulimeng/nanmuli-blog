package com.nanmuli.blog.infrastructure.persistence.article;

import com.nanmuli.blog.domain.article.ArticleVisitLog;
import com.nanmuli.blog.domain.article.ArticleVisitLogRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Repository;

import java.util.Collection;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Repository
@RequiredArgsConstructor
public class ArticleVisitLogRepositoryImpl implements ArticleVisitLogRepository {

    private final ArticleVisitLogMapper articleVisitLogMapper;

    @Override
    public ArticleVisitLog save(ArticleVisitLog log) {
        articleVisitLogMapper.insert(log);
        return log;
    }

    @Override
    public Long countByArticleId(Long articleId) {
        return articleVisitLogMapper.countByArticleId(articleId);
    }

    @Override
    public Long countTodayByArticleId(Long articleId) {
        return articleVisitLogMapper.countTodayByArticleId(articleId);
    }

    @Override
    public Long countTotalVisits() {
        return articleVisitLogMapper.countTotalVisits();
    }

    @Override
    public Long countTodayVisits() {
        return articleVisitLogMapper.countTodayVisits();
    }

    @Override
    public Map<Long, Long> countByArticleIds(Collection<Long> articleIds) {
        if (articleIds == null || articleIds.isEmpty()) {
            return Map.of();
        }
        List<Map<String, Object>> rows = articleVisitLogMapper.countByArticleIds(articleIds);
        Map<Long, Long> result = new HashMap<>();
        for (Long id : articleIds) {
            result.put(id, 0L);
        }
        for (Map<String, Object> row : rows) {
            Long articleId = ((Number) row.get("article_id")).longValue();
            Long count = ((Number) row.get("count")).longValue();
            result.put(articleId, count);
        }
        return result;
    }
}
