package com.nanmuli.blog.domain.tag;

import java.util.List;
import java.util.Optional;
import java.util.Set;

public interface TagRepository {
    Tag save(Tag tag);

    Optional<Tag> findById(Long id);

    Optional<Tag> findByName(String name);

    List<Tag> findByIds(Set<Long> ids);

    List<Tag> findAllActive();

    void deleteById(Long id);
}
