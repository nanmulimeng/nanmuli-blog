package com.nanmuli.blog.application.skill;

import com.nanmuli.blog.application.skill.dto.SkillDTO;
import com.nanmuli.blog.domain.skill.Skill;
import com.nanmuli.blog.domain.skill.SkillRepository;
import com.nanmuli.blog.shared.exception.BusinessException;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.BeanUtils;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
@RequiredArgsConstructor
public class SkillAppService {

    private final SkillRepository skillRepository;

    @Transactional
    public Long create(SkillDTO dto) {
        Skill skill = new Skill();
        BeanUtils.copyProperties(dto, skill);
        skillRepository.save(skill);
        return skill.getId();
    }

    @Transactional
    public void update(Long id, SkillDTO dto) {
        Skill skill = skillRepository.findById(id)
                .orElseThrow(() -> new BusinessException("技能不存在"));
        BeanUtils.copyProperties(dto, skill);
        skill.setId(id);
        skillRepository.save(skill);
    }

    @Transactional(readOnly = true)
    public List<SkillDTO> listAllVisible() {
        return skillRepository.findAllVisible().stream().map(this::toDTO).toList();
    }

    @Transactional(readOnly = true)
    public SkillDTO getById(Long id) {
        Skill skill = skillRepository.findById(id)
                .orElseThrow(() -> new BusinessException("技能不存在"));
        return toDTO(skill);
    }

    @Transactional
    public void delete(Long id) {
        skillRepository.deleteById(id);
    }

    private SkillDTO toDTO(Skill skill) {
        SkillDTO dto = new SkillDTO();
        BeanUtils.copyProperties(skill, dto);
        dto.setId(skill.getId());
        return dto;
    }
}
