package com.nanmuli.blog.infrastructure.persistence.article;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.nanmuli.blog.domain.article.Article;
import com.nanmuli.blog.domain.article.ArticleId;
import com.nanmuli.blog.domain.article.ArticleRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Repository;

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
        return Optional.ofNullable(articleMapper.selectById(id.getValue()));
    }

    @Override
    public Optional<Article> findBySlug(String slug) {
        LambdaQueryWrapper<Article> wrapper = Wrappers.lambdaQuery();
        wrapper.eq(Article::getSlug, slug);
        return Optional.ofNullable(articleMapper.selectOne(wrapper));
    }

    @Override
    public IPage<Article> findPublishedPage(IPage<Article> page) {
        return findPublishedPage(page, null);
    }

    @Override
    public IPage<Article> findPublishedPage(IPage<Article> page, String sort) {
        LambdaQueryWrapper<Article> wrapper = Wrappers.lambdaQuery();
        wrapper.eq(Article::getStatus, 1);

        // 根据排序参数设置排序方式
        if ("oldest".equals(sort)) {
            wrapper.orderByAsc(Article::getPublishTime);
        } else if ("popular".equals(sort)) {
            wrapper.orderByDesc(Article::getViewCount);
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
                .orderByDesc(Article::getPublishTime);
        return articleMapper.selectPage(page, wrapper);
    }

    @Override
    public List<Article> findTopArticles(int limit) {
        LambdaQueryWrapper<Article> wrapper = Wrappers.lambdaQuery();
        wrapper.eq(Article::getStatus, 1)
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
    public List<Article> findLatestArticles(int limit) {
        LambdaQueryWrapper<Article> wrapper = Wrappers.lambdaQuery();
        wrapper.eq(Article::getStatus, 1)
                .orderByDesc(Article::getPublishTime)
                .last("LIMIT " + limit);
        return articleMapper.selectList(wrapper);
    }

    @Override
    public List<Article> findHotArticles(int limit) {
        LambdaQueryWrapper<Article> wrapper = Wrappers.lambdaQuery();
        wrapper.eq(Article::getStatus, 1)
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
        wrapper.eq(Article::getStatus, 1);
        return articleMapper.selectCount(wrapper);
    }

    @Override
    public IPage<Article> findByTagId(Long tagId, IPage<Article> page) {
        return articleMapper.selectByTagId(page, tagId);
    }

    @Override
    public IPage<Article> findAllPage(IPage<Article> page) {
        LambdaQueryWrapper<Article> wrapper = Wrappers.lambdaQuery();
        wrapper.orderByDesc(Article::getCreatedAt);
        return articleMapper.selectPage(page, wrapper);
    }
}
