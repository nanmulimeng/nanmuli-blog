package com.nanmuli.blog.infrastructure.persistence.webcollector;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.nanmuli.blog.domain.webcollector.WebCollectSource;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.util.List;

/**
 * 订阅源 Mapper
 */
@Mapper
public interface WebCollectSourceMapper extends BaseMapper<WebCollectSource> {

    @Select("SELECT * FROM web_collect_source WHERE user_id = #{userId} AND is_deleted = false ORDER BY created_at DESC")
    List<WebCollectSource> selectByUserId(@Param("userId") Long userId);

    @Select("SELECT * FROM web_collect_source WHERE user_id = #{userId} AND is_active = true AND is_deleted = false ORDER BY created_at DESC")
    List<WebCollectSource> selectActiveByUserId(@Param("userId") Long userId);

    @Select("SELECT * FROM web_collect_source WHERE is_active = true AND schedule_cron IS NOT NULL AND is_deleted = false")
    List<WebCollectSource> selectActiveScheduledSources();

    @Select("SELECT COUNT(*) FROM web_collect_source WHERE user_id = #{userId} AND value = #{value} AND is_deleted = false")
    long countByUserIdAndValue(@Param("userId") Long userId, @Param("value") String value);

    @Select("SELECT COUNT(*) FROM web_collect_source WHERE user_id = #{userId} AND is_deleted = false")
    long countByUserId(@Param("userId") Long userId);

    @Select("SELECT COUNT(*) FROM web_collect_source WHERE user_id = #{userId} AND is_active = true AND is_deleted = false")
    long countActiveByUserId(@Param("userId") Long userId);
}
