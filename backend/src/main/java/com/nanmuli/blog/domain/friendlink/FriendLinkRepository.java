package com.nanmuli.blog.domain.friendlink;

import java.util.List;
import java.util.Optional;

public interface FriendLinkRepository {
    FriendLink save(FriendLink friendLink);

    Optional<FriendLink> findById(Long id);

    List<FriendLink> findAllActive();

    void deleteById(Long id);
}
