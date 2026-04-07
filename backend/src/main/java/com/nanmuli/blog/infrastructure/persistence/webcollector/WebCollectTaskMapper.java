package com.nanmuli.blog.infrastructure.persistence.webcollector;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.nanmuli.blog.domain.webcollector.WebCollectTask;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.util.List;

/**
 * 采集任务 Mapper
 */
@Mapper
public interface WebCollectTaskMapper extends BaseMapper<WebCollectTask> {

    @Select("SELECT * FROM web_collect_task WHERE status = 0 AND is_deleted = false ORDER BY created_at ASC LIMIT #{limit}")
    List<WebCollectTask> selectPendingTasks(@Param("limit") int limit);

    @Select("SELECT * FROM web_collect_task WHERE source_id = #{sourceId} AND is_deleted = false ORDER BY created_at DESC")
    List<WebCollectTask> selectBySourceId(@Param("sourceId") Long sourceId);

    @Select("SELECT COUNT(*) FROM web_collect_task WHERE user_id = #{userId} AND is_deleted = false")
    long countByUserId(@Param("userId") Long userId);

    @Select("SELECT COUNT(*) FROM web_collect_task WHERE status = #{status} AND is_deleted = false")
    long countByStatus(@Param("status") Integer status);
}
