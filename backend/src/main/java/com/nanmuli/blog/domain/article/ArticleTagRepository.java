package com.nanmuli.blog.domain.article;

import java.util.List;

/**
 * 文章-标签关联仓储接口
 */
public interface ArticleTagRepository {

    /**
     * 保存关联
     */
    void save(Long articleId, Long tagId);

    /**
     * 批量保存关联
     */
    void saveBatch(Long articleId, List<Long> tagIds);

    /**
     * 根据文章ID删除所有关联
     */
    void deleteByArticleId(Long articleId);

    /**
     * 根据文章ID查询标签ID列表
     */
    List<Long> findTagIdsByArticleId(Long articleId);

    /**
     * 根据标签ID查询文章ID列表
     */
    List<Long> findArticleIdsByTagId(Long tagId);
}
