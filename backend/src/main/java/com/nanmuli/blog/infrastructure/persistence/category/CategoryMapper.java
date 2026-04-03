package com.nanmuli.blog.infrastructure.persistence.category;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.nanmuli.blog.domain.category.Category;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface CategoryMapper extends BaseMapper<Category> {
}
