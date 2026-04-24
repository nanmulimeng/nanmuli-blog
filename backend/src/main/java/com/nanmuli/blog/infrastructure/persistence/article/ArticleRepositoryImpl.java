package com.nanmuli.blog.infrastructure.persistence.article;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.nanmuli.blog.domain.article.Article;
import com.nanmuli.blog.domain.article.ArticleId;
import com.nanmuli.blog.domain.article.ArticleRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Repository;

import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

@Repository
@RequiredArgsConstructor
public class ArticleRepositoryImpl implements ArticleRepository {

    private final ArticleMapper articleMapper;

    @Override
    public Article save(Article article) {
        if (article.isNew()) {
            articleMapper.insert(article);
        } else {
            articleMapper.updateById(article);
        }
        return article;
    }

    @Override
    public Optional<Article> findById(ArticleId id) {
        // MyBatis Plus 全局逻辑删除配置已自动过滤 is_deleted = false
        return Optional.ofNullable(articleMapper.selectById(id.getValue()));
    }

    @Override
    public Optional<Article> findBySlug(String slug) {
        LambdaQueryWrapper<Article> wrapper = Wrappers.lambdaQuery();
        wrapper.eq(Article::getSlug, slug)
               .eq(Article::getIsDeleted, false);
        return Optional.ofNullable(articleMapper.selectOne(wrapper));
    }

    @Override
    public boolean existsBySlug(String slug) {
        LambdaQueryWrapper<Article> wrapper = Wrappers.lambdaQuery();
        wrapper.eq(Article::getSlug, slug)
               .eq(Article::getIsDeleted, false);
        return articleMapper.selectCount(wrapper) > 0;
    }

    @Override
    public boolean existsBySlugAndIdNot(String slug, Long id) {
        LambdaQueryWrapper<Article> wrapper = Wrappers.lambdaQuery();
        wrapper.eq(Article::getSlug, slug)
               .ne(Article::getId, id)
               .eq(Article::getIsDeleted, false);
        return articleMapper.selectCount(wrapper) > 0;
    }

    @Override
    public IPage<Article> findPublishedPage(IPage<Article> page) {
        return findPublishedPage(page, null);
    }

    @Override
    public IPage<Article> findPublishedPage(IPage<Article> page, String sort) {
        LambdaQueryWrapper<Article> wrapper = Wrappers.lambdaQuery();
        wrapper.eq(Article::getStatus, 1)
               .eq(Article::getIsDeleted, false);

        // 根据排序参数设置排序方式
        if ("oldest".equals(sort)) {
            wrapper.orderByDesc(Article::getIsTop)
                   .orderByAsc(Article::getPublishTime);
        } else if ("popular".equals(sort)) {
            wrapper.orderByDesc(Article::getIsTop)
                   .orderByDesc(Article::getViewCount);
        } else {
            // 默认：最新发布
            wrapper.orderByDesc(Article::getIsTop)
                    .orderByDesc(Article::getPublishTime);
        }

        return articleMapper.selectPage(page, wrapper);
    }

    @Override
    public IPage<Article> findByCategoryId(Long categoryId, IPage<Article> page) {
        LambdaQueryWrapper<Article> wrapper = Wrappers.lambdaQuery();
        wrapper.eq(Article::getCategoryId, categoryId)
                .eq(Article::getStatus, 1)
                .eq(Article::getIsDeleted, false)
                .orderByDesc(Article::getPublishTime);
        return articleMapper.selectPage(page, wrapper);
    }

    @Override
    public IPage<Article> findByCategoryIds(List<Long> categoryIds, IPage<Article> page, String sort) {
        LambdaQueryWrapper<Article> wrapper = Wrappers.lambdaQuery();
        wrapper.in(Article::getCategoryId, categoryIds)
                .eq(Article::getStatus, 1)
                .eq(Article::getIsDeleted, false);

        // 根据排序参数设置排序方式
        if ("oldest".equals(sort)) {
            wrapper.orderByDesc(Article::getIsTop)
                   .orderByAsc(Article::getPublishTime);
        } else if ("popular".equals(sort)) {
            wrapper.orderByDesc(Article::getIsTop)
                   .orderByDesc(Article::getViewCount);
        } else {
            // 默认：最新发布
            wrapper.orderByDesc(Article::getIsTop)
                    .orderByDesc(Article::getPublishTime);
        }

        return articleMapper.selectPage(page, wrapper);
    }

    @Override
    public List<Article> findTopArticles(int limit) {
        LambdaQueryWrapper<Article> wrapper = Wrappers.lambdaQuery();
        wrapper.eq(Article::getStatus, 1)
                .eq(Article::getIsDeleted, false)
                .orderByDesc(Article::getIsTop)
                .orderByDesc(Article::getViewCount)
                .last("LIMIT " + limit);
        return articleMapper.selectList(wrapper);
    }

    @Override
    public void deleteById(ArticleId id) {
        articleMapper.deleteById(id.getValue());
    }

    @Override
    public void increaseViewCount(ArticleId id) {
        articleMapper.increaseViewCount(id.getValue());
    }

    @Override
    public Long countByCategoryId(Long categoryId) {
        LambdaQueryWrapper<Article> wrapper = Wrappers.lambdaQuery();
        wrapper.eq(Article::getCategoryId, categoryId)
               .eq(Article::getStatus, 1)
               .eq(Article::getIsDeleted, false);
        return articleMapper.selectCount(wrapper);
    }

    @Override
    public Map<Long, Integer> countByCategoryIds(List<Long> categoryIds) {
        if (categoryIds == null || categoryIds.isEmpty()) {
            return Map.of();
        }

        // 批量查询文章数（使用IN语句，避免N+1问题）
        List<Map<String, Object>> results = articleMapper.selectCategoryArticleCounts(categoryIds);

        Map<Long, Integer> countMap = new HashMap<>();
        // 初始化为0
        for (Long id : categoryIds) {
            countMap.put(id, 0);
        }
        // 填充实际计数
        for (Map<String, Object> result : results) {
            Long categoryId = ((Number) result.get("category_id")).longValue();
            Integer count = ((Number) result.get("count")).intValue();
            countMap.put(categoryId, count);
        }

        return countMap;
    }

    @Override
    public List<Article> findLatestArticles(int limit) {
        LambdaQueryWrapper<Article> wrapper = Wrappers.lambdaQuery();
        wrapper.eq(Article::getStatus, 1)
                .eq(Article::getIsDeleted, false)
                .orderByDesc(Article::getPublishTime)
                .last("LIMIT " + limit);
        return articleMapper.selectList(wrapper);
    }

    @Override
    public List<Article> findHotArticles(int limit) {
        LambdaQueryWrapper<Article> wrapper = Wrappers.lambdaQuery();
        wrapper.eq(Article::getStatus, 1)
                .eq(Article::getIsDeleted, false)
                .orderByDesc(Article::getViewCount)
                .orderByDesc(Article::getPublishTime)
                .last("LIMIT " + limit);
        return articleMapper.selectList(wrapper);
    }

    @Override
    public List<Map<String, Object>> findArchiveByYearMonth() {
        return articleMapper.selectArchiveByYearMonth();
    }

    @Override
    public Long countPublished() {
        LambdaQueryWrapper<Article> wrapper = Wrappers.lambdaQuery();
        wrapper.eq(Article::getStatus, 1)
               .eq(Article::getIsDeleted, false);
        return articleMapper.selectCount(wrapper);
    }

    @Override
    public Long countAll() {
        LambdaQueryWrapper<Article> wrapper = Wrappers.lambdaQuery();
        wrapper.eq(Article::getIsDeleted, false);
        return articleMapper.selectCount(wrapper);
    }

    @Override
    public IPage<Article> findPublishedByKeyword(String keyword, List<Long> categoryIds, IPage<Article> page, String sort) {
        // TODO: 优化建议 - 当前使用LIKE '%keyword%'全表扫描，大数据量时性能差
        // 方案1: 添加PostgreSQL全文搜索（推荐）
        //   - 添加tsvector列 + GIN索引
        //   - 使用 plainto_tsquery('chinese', keyword) 查询
        // 方案2: 使用Elasticsearch（复杂查询场景）
        // 方案3: 限制搜索范围（仅搜索标题+摘要，不搜索content大字段）

        // SQL通配符转义，防止意外匹配或全表扫描
        String escapedKeyword = escapeLikeKeyword(keyword);

        LambdaQueryWrapper<Article> wrapper = Wrappers.lambdaQuery();
        wrapper.eq(Article::getStatus, 1)
               .eq(Article::getIsDeleted, false)
               .and(kw -> {
                   // 优先搜索标题（有索引）
                   kw.like(Article::getTitle, escapedKeyword)
                     .or()
                     .like(Article::getSummary, escapedKeyword);
                   // 如果有关键词匹配的分类，也加入搜索条件
                   if (categoryIds != null && !categoryIds.isEmpty()) {
                       kw.or().in(Article::getCategoryId, categoryIds);
                   }
               });

        // 根据排序参数设置排序方式
        if ("oldest".equals(sort)) {
            wrapper.orderByDesc(Article::getIsTop)
                   .orderByAsc(Article::getPublishTime);
        } else if ("popular".equals(sort)) {
            wrapper.orderByDesc(Article::getIsTop)
                   .orderByDesc(Article::getViewCount);
        } else {
            // 默认：最新发布
            wrapper.orderByDesc(Article::getIsTop)
                    .orderByDesc(Article::getPublishTime);
        }

        return articleMapper.selectPage(page, wrapper);
    }

    @Override
    public Long sumViewCount() {
        return articleMapper.sumViewCount();
    }

    @Override
    public IPage<Article> findAllPage(IPage<Article> page) {
        LambdaQueryWrapper<Article> wrapper = Wrappers.lambdaQuery();
        wrapper.eq(Article::getIsDeleted, false)
               .orderByDesc(Article::getCreatedAt);
        return articleMapper.selectPage(page, wrapper);
    }

    /**
     * SQL通配符转义，防止LIKE查询时意外匹配或全表扫描
     * 转义 % _ \ 等特殊字符
     */
    private String escapeLikeKeyword(String keyword) {
        if (keyword == null) {
            return null;
        }
        return keyword.replace("\\", "\\\\")
                      .replace("%", "\\%")
                      .replace("_", "\\_");
    }

    @Override
    public IPage<Article> findAllByKeyword(String keyword, List<Long> categoryIds, IPage<Article> page) {
        String escapedKeyword = escapeLikeKeyword(keyword);
        LambdaQueryWrapper<Article> wrapper = Wrappers.lambdaQuery();
        wrapper.eq(Article::getIsDeleted, false)
               .and(kw -> {
                   kw.like(Article::getTitle, escapedKeyword)
                     .or()
                     .like(Article::getContent, escapedKeyword)
                     .or()
                     .like(Article::getSummary, escapedKeyword);
                   if (categoryIds != null && !categoryIds.isEmpty()) {
                       kw.or().in(Article::getCategoryId, categoryIds);
                   }
               })
               .orderByDesc(Article::getCreatedAt);
        return articleMapper.selectPage(page, wrapper);
    }
}
