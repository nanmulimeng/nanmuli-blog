package com.nanmuli.blog.domain.article;

import com.baomidou.mybatisplus.core.metadata.IPage;

import java.util.List;
import java.util.Optional;

public interface ArticleRepository {
    Article save(Article article);

    Optional<Article> findById(ArticleId id);

    Optional<Article> findBySlug(String slug);

    IPage<Article> findPublishedPage(IPage<Article> page);

    IPage<Article> findByCategoryId(Long categoryId, IPage<Article> page);

    List<Article> findTopArticles(int limit);

    void deleteById(ArticleId id);

    void increaseViewCount(ArticleId id);
}
