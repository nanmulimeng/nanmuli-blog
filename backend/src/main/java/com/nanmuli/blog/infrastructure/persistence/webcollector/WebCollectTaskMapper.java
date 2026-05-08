package com.nanmuli.blog.infrastructure.persistence.webcollector;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.nanmuli.blog.domain.webcollector.WebCollectTask;
import org.apache.ibatis.annotations.Mapper;

/**
 * 采集任务 Mapper
 */
@Mapper
public interface WebCollectTaskMapper extends BaseMapper<WebCollectTask> {
}
