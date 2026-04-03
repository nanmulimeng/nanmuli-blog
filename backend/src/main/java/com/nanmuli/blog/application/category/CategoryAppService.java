package com.nanmuli.blog.application.category;

import com.nanmuli.blog.application.category.dto.CategoryDTO;
import com.nanmuli.blog.domain.category.Category;
import com.nanmuli.blog.domain.category.CategoryRepository;
import com.nanmuli.blog.shared.exception.BusinessException;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.BeanUtils;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
@RequiredArgsConstructor
public class CategoryAppService {

    private final CategoryRepository categoryRepository;

    @Transactional
    public Long create(CategoryDTO dto) {
        Category category = new Category();
        BeanUtils.copyProperties(dto, category);
        categoryRepository.save(category);
        return category.getId();
    }

    @Transactional
    public void update(Long id, CategoryDTO dto) {
        Category category = categoryRepository.findById(id)
                .orElseThrow(() -> new BusinessException("分类不存在"));
        BeanUtils.copyProperties(dto, category);
        category.setId(id);
        categoryRepository.save(category);
    }

    @Transactional(readOnly = true)
    public List<CategoryDTO> listAllActive() {
        return categoryRepository.findAllActive().stream().map(this::toDTO).toList();
    }

    @Transactional(readOnly = true)
    public CategoryDTO getById(Long id) {
        Category category = categoryRepository.findById(id)
                .orElseThrow(() -> new BusinessException("分类不存在"));
        return toDTO(category);
    }

    @Transactional
    public void delete(Long id) {
        categoryRepository.deleteById(id);
    }

    private CategoryDTO toDTO(Category category) {
        CategoryDTO dto = new CategoryDTO();
        BeanUtils.copyProperties(category, dto);
        return dto;
    }
}
