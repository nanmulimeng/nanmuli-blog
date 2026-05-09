package com.nanmuli.blog.infrastructure.persistence.article;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.nanmuli.blog.domain.article.ArticleViewRecord;
import com.nanmuli.blog.domain.article.ArticleViewRecordRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Repository;

import java.util.Collection;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

@Repository
@RequiredArgsConstructor
public class ArticleViewRecordRepositoryImpl implements ArticleViewRecordRepository {

    private final ArticleViewRecordMapper articleViewRecordMapper;

    @Override
    public ArticleViewRecord save(ArticleViewRecord record) {
        if (record.isNew()) {
            articleViewRecordMapper.insert(record);
        } else {
            articleViewRecordMapper.updateById(record);
        }
        return record;
    }

    @Override
    public Optional<ArticleViewRecord> findByArticleIdAndVisitorId(Long articleId, String visitorId) {
        LambdaQueryWrapper<ArticleViewRecord> wrapper = Wrappers.lambdaQuery();
        wrapper.eq(ArticleViewRecord::getArticleId, articleId)
               .eq(ArticleViewRecord::getVisitorId, visitorId)
               .eq(ArticleViewRecord::getIsDeleted, false);
        return Optional.ofNullable(articleViewRecordMapper.selectOne(wrapper));
    }

    @Override
    public Long countUniqueVisitorsByArticleId(Long articleId) {
        LambdaQueryWrapper<ArticleViewRecord> wrapper = Wrappers.lambdaQuery();
        wrapper.eq(ArticleViewRecord::getArticleId, articleId)
               .eq(ArticleViewRecord::getIsDeleted, false);
        return articleViewRecordMapper.selectCount(wrapper);
    }

    @Override
    public Map<Long, Long> countUniqueVisitorsByArticleIds(Collection<Long> articleIds) {
        if (articleIds == null || articleIds.isEmpty()) {
            return Collections.emptyMap();
        }
        List<Map<String, Object>> rows = articleViewRecordMapper.countByArticleIds(articleIds);
        Map<Long, Long> result = new HashMap<>();
        for (Map<String, Object> row : rows) {
            Long articleId = ((Number) row.get("article_id")).longValue();
            Long count = ((Number) row.get("cnt")).longValue();
            result.put(articleId, count);
        }
        return result;
    }

    @Override
    public Long countTotalUniqueVisitors() {
        return articleViewRecordMapper.countTotalUniqueVisitors();
    }
}
