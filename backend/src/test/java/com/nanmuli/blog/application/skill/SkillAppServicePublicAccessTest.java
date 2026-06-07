package com.nanmuli.blog.application.skill;

import com.nanmuli.blog.domain.skill.Skill;
import com.nanmuli.blog.domain.skill.SkillRepository;
import com.nanmuli.blog.shared.exception.BusinessException;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class SkillAppServicePublicAccessTest {

    @Mock
    private SkillRepository skillRepository;

    @Test
    void publicDetailDoesNotExposeHiddenSkill() {
        Skill hidden = new Skill();
        hidden.setId(1L);
        hidden.setName("Hidden");
        hidden.setStatus(0);
        when(skillRepository.findById(1L)).thenReturn(Optional.of(hidden));

        SkillAppService service = new SkillAppService(skillRepository);

        assertThrows(BusinessException.class, () -> service.getVisibleById(1L));
    }
}
