package com.nanmuli.blog.domain.webcollector;

import java.util.Optional;

/**
 * 采集订阅源仓储接口
 */
public interface WebCollectSourceRepository {

    WebCollectSource save(WebCollectSource source);

    Optional<WebCollectSource> findById(Long id);

    java.util.List<WebCollectSource> findByUserId(Long userId);

    java.util.List<WebCollectSource> findActiveSources();

    void deleteById(Long id);

    boolean existsByNameAndIdNot(String name, Long excludeId);
}
