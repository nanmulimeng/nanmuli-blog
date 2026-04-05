package com.nanmuli.blog.application.tag;

import com.nanmuli.blog.application.tag.dto.TagDTO;
import com.nanmuli.blog.domain.tag.Tag;
import com.nanmuli.blog.domain.tag.TagRepository;
import com.nanmuli.blog.shared.exception.BusinessException;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.BeanUtils;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
@RequiredArgsConstructor
public class TagAppService {

    private final TagRepository tagRepository;

    @Transactional
    public Long create(TagDTO dto) {
        Tag tag = new Tag();
        BeanUtils.copyProperties(dto, tag);
        tagRepository.save(tag);
        return tag.getId();
    }

    @Transactional
    public void update(Long id, TagDTO dto) {
        Tag tag = tagRepository.findById(id)
                .orElseThrow(() -> new BusinessException("标签不存在"));
        BeanUtils.copyProperties(dto, tag);
        tag.setId(id);
        tagRepository.save(tag);
    }

    @Transactional(readOnly = true)
    public List<TagDTO> listAllActive() {
        return tagRepository.findAllActive().stream().map(this::toDTO).toList();
    }

    @Transactional(readOnly = true)
    public List<TagDTO> listAll() {
        return tagRepository.findAll().stream().map(this::toDTO).toList();
    }

    @Transactional(readOnly = true)
    public TagDTO getById(Long id) {
        Tag tag = tagRepository.findById(id)
                .orElseThrow(() -> new BusinessException("标签不存在"));
        return toDTO(tag);
    }

    @Transactional
    public void delete(Long id) {
        tagRepository.deleteById(id);
    }

    private TagDTO toDTO(Tag tag) {
        TagDTO dto = new TagDTO();
        BeanUtils.copyProperties(tag, dto);
        dto.setId(tag.getId());
        return dto;
    }
}
