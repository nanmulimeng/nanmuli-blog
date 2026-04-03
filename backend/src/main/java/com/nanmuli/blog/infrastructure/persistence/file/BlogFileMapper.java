package com.nanmuli.blog.infrastructure.persistence.file;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.nanmuli.blog.domain.file.BlogFile;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface BlogFileMapper extends BaseMapper<BlogFile> {
}
