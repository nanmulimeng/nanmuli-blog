package com.nanmuli.blog.infrastructure.persistence.ai;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.nanmuli.blog.domain.ai.AiGeneration;
import com.nanmuli.blog.domain.ai.AiGenerationRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
@RequiredArgsConstructor
public class AiGenerationRepositoryImpl implements AiGenerationRepository {

    private final AiGenerationMapper aiGenerationMapper;

    @Override
    public AiGeneration save(AiGeneration generation) {
        if (generation.isNew()) {
            aiGenerationMapper.insert(generation);
        } else {
            aiGenerationMapper.updateById(generation);
        }
        return generation;
    }

    @Override
    public Optional<AiGeneration> findById(Long id) {
        return Optional.ofNullable(aiGenerationMapper.selectById(id));
    }

    @Override
    public List<AiGeneration> findByArticleId(Long articleId) {
        LambdaQueryWrapper<AiGeneration> wrapper = Wrappers.lambdaQuery();
        wrapper.eq(AiGeneration::getArticleId, articleId);
        return aiGenerationMapper.selectList(wrapper);
    }

    @Override
    public void deleteById(Long id) {
        aiGenerationMapper.deleteById(id);
    }
}
