package com.nanmuli.blog.infrastructure.persistence.webcollector;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.nanmuli.blog.domain.webcollector.WebCollectSource;
import com.nanmuli.blog.domain.webcollector.WebCollectSourceRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

/**
 * 订阅源仓储实现
 */
@Repository
@RequiredArgsConstructor
public class WebCollectSourceRepositoryImpl implements WebCollectSourceRepository {

    private final WebCollectSourceMapper sourceMapper;

    @Override
    public WebCollectSource save(WebCollectSource source) {
        if (source.isNew()) {
            sourceMapper.insert(source);
        } else {
            sourceMapper.updateById(source);
        }
        return source;
    }

    @Override
    public Optional<WebCollectSource> findById(Long id) {
        return Optional.ofNullable(sourceMapper.selectById(id));
    }

    @Override
    public List<WebCollectSource> findByUserId(Long userId) {
        return sourceMapper.selectByUserId(userId);
    }

    @Override
    public List<WebCollectSource> findActiveByUserId(Long userId) {
        return sourceMapper.selectActiveByUserId(userId);
    }

    @Override
    public IPage<WebCollectSource> findPage(IPage<WebCollectSource> page, Long userId) {
        return sourceMapper.selectPage(page,
            new com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper<WebCollectSource>()
                .eq(WebCollectSource::getUserId, userId)
                .eq(WebCollectSource::getIsDeleted, false)
                .orderByDesc(WebCollectSource::getCreatedAt));
    }

    @Override
    public List<WebCollectSource> findActiveScheduledSources() {
        return sourceMapper.selectActiveScheduledSources();
    }

    @Override
    public boolean existsByUserIdAndValue(Long userId, String value) {
        return sourceMapper.countByUserIdAndValue(userId, value) > 0;
    }

    @Override
    public void deleteById(Long id) {
        sourceMapper.deleteById(id);
    }

    @Override
    public long countByUserId(Long userId) {
        return sourceMapper.countByUserId(userId);
    }

    @Override
    public long countActiveByUserId(Long userId) {
        return sourceMapper.countActiveByUserId(userId);
    }
}
