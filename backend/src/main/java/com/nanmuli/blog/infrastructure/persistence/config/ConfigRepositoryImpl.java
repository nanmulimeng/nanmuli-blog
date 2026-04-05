package com.nanmuli.blog.infrastructure.persistence.config;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.nanmuli.blog.domain.config.Config;
import com.nanmuli.blog.domain.config.ConfigRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
@RequiredArgsConstructor
public class ConfigRepositoryImpl implements ConfigRepository {

    private final ConfigMapper configMapper;

    @Override
    public Config save(Config config) {
        if (config.isNew()) {
            configMapper.insert(config);
        } else {
            configMapper.updateById(config);
        }
        return config;
    }

    @Override
    public Optional<Config> findByKey(String key) {
        LambdaQueryWrapper<Config> wrapper = Wrappers.lambdaQuery();
        wrapper.eq(Config::getConfigKey, key);
        return Optional.ofNullable(configMapper.selectOne(wrapper));
    }

    @Override
    public List<Config> findByGroup(String groupName) {
        LambdaQueryWrapper<Config> wrapper = Wrappers.lambdaQuery();
        wrapper.eq(Config::getGroupName, groupName);
        return configMapper.selectList(wrapper);
    }

    @Override
    public List<Config> findAllPublic() {
        LambdaQueryWrapper<Config> wrapper = Wrappers.lambdaQuery();
        wrapper.eq(Config::getIsPublic, true);
        return configMapper.selectList(wrapper);
    }

    @Override
    public List<Config> findAll() {
        return configMapper.selectList(null);
    }

    @Override
    public void deleteById(Long id) {
        configMapper.deleteById(id);
    }
}
