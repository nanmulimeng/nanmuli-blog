package com.nanmuli.blog.infrastructure.persistence.webcollector;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.nanmuli.blog.domain.webcollector.WebCollectSource;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface WebCollectSourceMapper extends BaseMapper<WebCollectSource> {
}
