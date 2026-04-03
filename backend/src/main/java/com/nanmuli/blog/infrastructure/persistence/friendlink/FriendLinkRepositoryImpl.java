package com.nanmuli.blog.infrastructure.persistence.friendlink;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.nanmuli.blog.domain.friendlink.FriendLink;
import com.nanmuli.blog.domain.friendlink.FriendLinkRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
@RequiredArgsConstructor
public class FriendLinkRepositoryImpl implements FriendLinkRepository {

    private final FriendLinkMapper friendLinkMapper;

    @Override
    public FriendLink save(FriendLink friendLink) {
        if (friendLink.isNew()) {
            friendLinkMapper.insert(friendLink);
        } else {
            friendLinkMapper.updateById(friendLink);
        }
        return friendLink;
    }

    @Override
    public Optional<FriendLink> findById(Long id) {
        return Optional.ofNullable(friendLinkMapper.selectById(id));
    }

    @Override
    public List<FriendLink> findAllActive() {
        LambdaQueryWrapper<FriendLink> wrapper = Wrappers.lambdaQuery();
        wrapper.eq(FriendLink::getStatus, 1).orderByAsc(FriendLink::getSort);
        return friendLinkMapper.selectList(wrapper);
    }

    @Override
    public void deleteById(Long id) {
        friendLinkMapper.deleteById(id);
    }
}
