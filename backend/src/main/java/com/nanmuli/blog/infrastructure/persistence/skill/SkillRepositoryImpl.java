package com.nanmuli.blog.infrastructure.persistence.skill;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.nanmuli.blog.domain.skill.Skill;
import com.nanmuli.blog.domain.skill.SkillRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
@RequiredArgsConstructor
public class SkillRepositoryImpl implements SkillRepository {

    private final SkillMapper skillMapper;

    @Override
    public Skill save(Skill skill) {
        if (skill.isNew()) {
            skillMapper.insert(skill);
        } else {
            skillMapper.updateById(skill);
        }
        return skill;
    }

    @Override
    public Optional<Skill> findById(Long id) {
        return Optional.ofNullable(skillMapper.selectById(id));
    }

    @Override
    public List<Skill> findAllVisibleByCategory(String category) {
        LambdaQueryWrapper<Skill> wrapper = Wrappers.lambdaQuery();
        wrapper.eq(Skill::getCategory, category)
                .eq(Skill::getStatus, 1)
                .orderByDesc(Skill::getProficiency);
        return skillMapper.selectList(wrapper);
    }

    @Override
    public List<Skill> findAllVisible() {
        LambdaQueryWrapper<Skill> wrapper = Wrappers.lambdaQuery();
        wrapper.eq(Skill::getStatus, 1).orderByDesc(Skill::getSort);
        return skillMapper.selectList(wrapper);
    }

    @Override
    public List<Skill> findAll() {
        LambdaQueryWrapper<Skill> wrapper = Wrappers.lambdaQuery();
        wrapper.orderByDesc(Skill::getSort);
        return skillMapper.selectList(wrapper);
    }

    @Override
    public void deleteById(Long id) {
        skillMapper.deleteById(id);
    }
}
