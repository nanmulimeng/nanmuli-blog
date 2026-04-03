package com.nanmuli.blog.infrastructure.persistence.ai;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.nanmuli.blog.domain.ai.AiGeneration;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface AiGenerationMapper extends BaseMapper<AiGeneration> {
}
