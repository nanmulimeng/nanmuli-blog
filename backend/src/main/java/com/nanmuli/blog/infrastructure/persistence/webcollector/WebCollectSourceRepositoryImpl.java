package com.nanmuli.blog.infrastructure.persistence.webcollector;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.nanmuli.blog.domain.webcollector.WebCollectSource;
import com.nanmuli.blog.domain.webcollector.WebCollectSourceRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

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
        LambdaQueryWrapper<WebCollectSource> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(WebCollectSource::getUserId, userId)
               .eq(WebCollectSource::getIsDeleted, false)
               .orderByDesc(WebCollectSource::getCreatedAt);
        return sourceMapper.selectList(wrapper);
    }

    @Override
    public List<WebCollectSource> findActiveSources() {
        LambdaQueryWrapper<WebCollectSource> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(WebCollectSource::getIsActive, true)
               .eq(WebCollectSource::getIsDeleted, false)
               .orderByAsc(WebCollectSource::getName);
        return sourceMapper.selectList(wrapper);
    }

    @Override
    public void deleteById(Long id) {
        sourceMapper.deleteById(id);
    }

    @Override
    public boolean existsByNameAndIdNot(String name, Long excludeId) {
        LambdaQueryWrapper<WebCollectSource> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(WebCollectSource::getName, name)
               .eq(WebCollectSource::getIsDeleted, false)
               .ne(excludeId != null, WebCollectSource::getId, excludeId);
        return sourceMapper.selectCount(wrapper) > 0;
    }
}
