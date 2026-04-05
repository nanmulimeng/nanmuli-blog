package com.nanmuli.blog.domain.article;

import com.baomidou.mybatisplus.core.metadata.IPage;

import java.util.List;
import java.util.Map;
import java.util.Optional;

public interface ArticleRepository {
    Article save(Article article);

    Optional<Article> findById(ArticleId id);

    Optional<Article> findBySlug(String slug);

    IPage<Article> findPublishedPage(IPage<Article> page);

    IPage<Article> findPublishedPage(IPage<Article> page, String sort);

    IPage<Article> findByCategoryId(Long categoryId, IPage<Article> page);

    IPage<Article> findByTagId(Long tagId, IPage<Article> page);

    IPage<Article> findAllPage(IPage<Article> page);

    List<Article> findTopArticles(int limit);

    List<Article> findLatestArticles(int limit);

    List<Article> findHotArticles(int limit);

    List<Map<String, Object>> findArchiveByYearMonth();

    Long countPublished();

    void deleteById(ArticleId id);

    void increaseViewCount(ArticleId id);

    /**
     * 统计指定分类的文章数量
     */
    Long countByCategoryId(Long categoryId);
}
