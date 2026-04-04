package com.nanmuli.blog.infrastructure.persistence.article;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.nanmuli.blog.domain.article.ArticleTag;
import com.nanmuli.blog.domain.article.ArticleTagRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Repository;
import org.springframework.util.CollectionUtils;

import java.time.LocalDateTime;
import java.util.List;

/**
 * 文章-标签关联仓储实现
 */
@Repository
@RequiredArgsConstructor
public class ArticleTagRepositoryImpl implements ArticleTagRepository {

    private final ArticleTagMapper articleTagMapper;

    @Override
    public void save(Long articleId, Long tagId) {
        ArticleTag articleTag = new ArticleTag();
        articleTag.setArticleId(articleId);
        articleTag.setTagId(tagId);
        articleTag.setCreatedAt(LocalDateTime.now());
        articleTagMapper.insert(articleTag);
    }

    @Override
    public void saveBatch(Long articleId, List<Long> tagIds) {
        if (CollectionUtils.isEmpty(tagIds)) {
            return;
        }
        for (Long tagId : tagIds) {
            save(articleId, tagId);
        }
    }

    @Override
    public void deleteByArticleId(Long articleId) {
        LambdaQueryWrapper<ArticleTag> wrapper = Wrappers.lambdaQuery();
        wrapper.eq(ArticleTag::getArticleId, articleId);
        articleTagMapper.delete(wrapper);
    }

    @Override
    public List<Long> findTagIdsByArticleId(Long articleId) {
        return articleTagMapper.selectTagIdsByArticleId(articleId);
    }

    @Override
    public List<Long> findArticleIdsByTagId(Long tagId) {
        return articleTagMapper.selectArticleIdsByTagId(tagId);
    }
}
