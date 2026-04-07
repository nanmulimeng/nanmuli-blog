package com.nanmuli.blog.domain.webcollector;

import com.baomidou.mybatisplus.core.metadata.IPage;

import java.util.List;
import java.util.Optional;

/**
 * 订阅源仓储接口
 */
public interface WebCollectSourceRepository {

    WebCollectSource save(WebCollectSource source);

    Optional<WebCollectSource> findById(Long id);

    List<WebCollectSource> findByUserId(Long userId);

    List<WebCollectSource> findActiveByUserId(Long userId);

    IPage<WebCollectSource> findPage(IPage<WebCollectSource> page, Long userId);

    List<WebCollectSource> findActiveScheduledSources();

    boolean existsByUserIdAndValue(Long userId, String value);

    void deleteById(Long id);

    long countByUserId(Long userId);

    long countActiveByUserId(Long userId);
}
