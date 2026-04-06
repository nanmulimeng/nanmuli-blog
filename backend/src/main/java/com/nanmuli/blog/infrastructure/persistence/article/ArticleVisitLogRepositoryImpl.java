package com.nanmuli.blog.infrastructure.persistence.article;

import com.nanmuli.blog.domain.article.ArticleVisitLog;
import com.nanmuli.blog.domain.article.ArticleVisitLogRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Repository;

import java.time.LocalDate;

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
}
