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

    IPage<WebCollectTask> findPageFiltered(IPage<WebCollectTask> page, Long userId, Integer status, String taskType, String keyword);

    void deleteById(Long id);
}
