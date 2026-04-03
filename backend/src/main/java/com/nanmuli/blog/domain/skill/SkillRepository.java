package com.nanmuli.blog.domain.skill;

import java.util.List;
import java.util.Optional;

public interface SkillRepository {
    Skill save(Skill skill);

    Optional<Skill> findById(Long id);

    List<Skill> findAllVisibleByCategory(String category);

    List<Skill> findAllVisible();

    void deleteById(Long id);
}
