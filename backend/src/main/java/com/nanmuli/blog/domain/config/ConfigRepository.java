package com.nanmuli.blog.domain.config;

import java.util.List;
import java.util.Optional;

public interface ConfigRepository {
    Config save(Config config);

    Optional<Config> findByKey(String key);

    List<Config> findByGroup(String groupName);

    List<Config> findAllPublic();

    List<Config> findAll();

    void deleteById(Long id);
}
