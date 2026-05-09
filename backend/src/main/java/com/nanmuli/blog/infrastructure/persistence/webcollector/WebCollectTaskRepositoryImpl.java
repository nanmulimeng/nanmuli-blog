package com.nanmuli.blog.infrastructure.persistence.webcollector;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.nanmuli.blog.domain.webcollector.WebCollectTask;
import com.nanmuli.blog.domain.webcollector.WebCollectTaskRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

/**
 * 采集任务仓储实现
 */
@Repository
@RequiredArgsConstructor
public class WebCollectTaskRepositoryImpl implements WebCollectTaskRepository {

    private final WebCollectTaskMapper taskMapper;

    @Override
    public WebCollectTask save(WebCollectTask task) {
        if (task.isNew()) {
            taskMapper.insert(task);
        } else {
            taskMapper.updateById(task);
        }
        return task;
    }

    @Override
    public Optional<WebCollectTask> findById(Long id) {
        return Optional.ofNullable(taskMapper.selectById(id));
    }

    @Override
    public List<WebCollectTask> findByUserId(Long userId) {
        LambdaQueryWrapper<WebCollectTask> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(WebCollectTask::getUserId, userId)
               .eq(WebCollectTask::getIsDeleted, false)
               .orderByDesc(WebCollectTask::getCreatedAt);
        return taskMapper.selectList(wrapper);
    }

    @Override
    public IPage<WebCollectTask> findPage(IPage<WebCollectTask> page, Long userId) {
        LambdaQueryWrapper<WebCollectTask> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(WebCollectTask::getUserId, userId)
               .eq(WebCollectTask::getIsDeleted, false)
               .orderByDesc(WebCollectTask::getCreatedAt);
        return taskMapper.selectPage(page, wrapper);
    }

    @Override
    public IPage<WebCollectTask> findPageFiltered(IPage<WebCollectTask> page, Long userId, Integer status, String taskType, String keyword) {
        LambdaQueryWrapper<WebCollectTask> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(WebCollectTask::getUserId, userId)
               .eq(WebCollectTask::getIsDeleted, false);
        if (status != null) {
            wrapper.eq(WebCollectTask::getStatus, status);
        }
        if (taskType != null && !taskType.isBlank()) {
            wrapper.eq(WebCollectTask::getTaskType, taskType);
        }
        if (keyword != null && !keyword.isBlank()) {
            wrapper.and(w -> w.like(WebCollectTask::getSourceUrl, keyword)
                             .or()
                             .like(WebCollectTask::getKeyword, keyword));
        }
        wrapper.orderByDesc(WebCollectTask::getCreatedAt);
        return taskMapper.selectPage(page, wrapper);
    }

    @Override
    public Optional<WebCollectTask> findByPythonTaskId(Integer pythonTaskId) {
        LambdaQueryWrapper<WebCollectTask> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(WebCollectTask::getPythonTaskId, pythonTaskId)
               .eq(WebCollectTask::getIsDeleted, false)
               .last("LIMIT 1");
        return Optional.ofNullable(taskMapper.selectOne(wrapper));
    }

    @Override
    public void deleteById(Long id) {
        taskMapper.deleteById(id);
    }
}
