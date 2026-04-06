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

    /**
     * 根据多个分类ID查询文章（用于父分类筛选，包含所有子分类）
     */
    IPage<Article> findByCategoryIds(List<Long> categoryIds, IPage<Article> page, String sort);

    IPage<Article> findAllPage(IPage<Article> page);

    List<Article> findTopArticles(int limit);

    List<Article> findLatestArticles(int limit);

    List<Article> findHotArticles(int limit);

    List<Map<String, Object>> findArchiveByYearMonth();

    Long countPublished();

    Long countAll();

    Long sumViewCount();

    void deleteById(ArticleId id);

    void increaseViewCount(ArticleId id);

    /**
     * 统计指定分类的文章数量
     */
    Long countByCategoryId(Long categoryId);

    /**
     * 检查slug是否存在
     */
    boolean existsBySlug(String slug);

    /**
     * 检查slug是否被其他文章使用（排除指定ID）
     */
    boolean existsBySlugAndIdNot(String slug, Long id);
}
