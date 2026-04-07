package com.nanmuli.blog.domain.webcollector;

import com.baomidou.mybatisplus.core.metadata.IPage;

import java.util.List;
import java.util.Optional;

/**
 * 采集任务仓储接口
 */
public interface WebCollectTaskRepository {

    WebCollectTask save(WebCollectTask task);

    Optional<WebCollectTask> findById(Long id);

    List<WebCollectTask> findByUserId(Long userId);

    IPage<WebCollectTask> findPage(IPage<WebCollectTask> page, Long userId);

    IPage<WebCollectTask> findPageByStatus(IPage<WebCollectTask> page, Long userId, Integer status);

    List<WebCollectTask> findPendingTasks(int limit);

    List<WebCollectTask> findBySourceId(Long sourceId);

    void deleteById(Long id);

    long countByUserId(Long userId);

    long countByStatus(Integer status);
}
