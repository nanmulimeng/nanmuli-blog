package com.nanmuli.blog.infrastructure.persistence.user;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.nanmuli.blog.domain.user.User;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface UserMapper extends BaseMapper<User> {
}
