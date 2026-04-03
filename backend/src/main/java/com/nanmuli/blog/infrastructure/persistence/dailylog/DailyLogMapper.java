package com.nanmuli.blog.infrastructure.persistence.dailylog;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.nanmuli.blog.domain.dailylog.DailyLog;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface DailyLogMapper extends BaseMapper<DailyLog> {
}
