package com.nanmuli.blog.infrastructure.persistence.friendlink;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.nanmuli.blog.domain.friendlink.FriendLink;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface FriendLinkMapper extends BaseMapper<FriendLink> {
}
