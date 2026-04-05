package com.nanmuli.blog.infrastructure.persistence.tag;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.nanmuli.blog.domain.tag.Tag;
import com.nanmuli.blog.domain.tag.TagRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;
import java.util.Set;

@Repository
@RequiredArgsConstructor
public class TagRepositoryImpl implements TagRepository {

    private final TagMapper tagMapper;

    @Override
    public Tag save(Tag tag) {
        if (tag.isNew()) {
            tagMapper.insert(tag);
        } else {
            tagMapper.updateById(tag);
        }
        return tag;
    }

    @Override
    public Optional<Tag> findById(Long id) {
        return Optional.ofNullable(tagMapper.selectById(id));
    }

    @Override
    public Optional<Tag> findByName(String name) {
        LambdaQueryWrapper<Tag> wrapper = Wrappers.lambdaQuery();
        wrapper.eq(Tag::getName, name);
        return Optional.ofNullable(tagMapper.selectOne(wrapper));
    }

    @Override
    public List<Tag> findByIds(Set<Long> ids) {
        return tagMapper.selectBatchIds(ids);
    }

    @Override
    public List<Tag> findAllActive() {
        LambdaQueryWrapper<Tag> wrapper = Wrappers.lambdaQuery();
        wrapper.eq(Tag::getStatus, 1).orderByDesc(Tag::getArticleCount);
        return tagMapper.selectList(wrapper);
    }

    @Override
    public List<Tag> findAll() {
        LambdaQueryWrapper<Tag> wrapper = Wrappers.lambdaQuery();
        wrapper.orderByDesc(Tag::getArticleCount);
        return tagMapper.selectList(wrapper);
    }

    @Override
    public void deleteById(Long id) {
        tagMapper.deleteById(id);
    }
}
