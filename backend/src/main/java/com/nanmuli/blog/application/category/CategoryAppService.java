package com.nanmuli.blog.application.category;

import com.nanmuli.blog.application.category.dto.CategoryDTO;
import com.nanmuli.blog.domain.article.ArticleRepository;
import com.nanmuli.blog.domain.category.Category;
import com.nanmuli.blog.domain.category.CategoryRepository;
import com.nanmuli.blog.shared.exception.BusinessException;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.BeanUtils;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class CategoryAppService {

    private final CategoryRepository categoryRepository;
    private final ArticleRepository articleRepository;

    @Transactional
    public Long create(CategoryDTO dto) {
        Category category = new Category();
        BeanUtils.copyProperties(dto, category);
        // 默认设置为叶子节点（原标签概念）
        if (category.getIsLeaf() == null) {
            category.setIsLeaf(true);
        }
        // 父分类不能设置为叶子节点
        if (category.getParentId() != null) {
            Category parent = categoryRepository.findById(category.getParentId())
                    .orElseThrow(() -> new BusinessException("父分类不存在"));
            if (parent.isLeaf()) {
                throw new BusinessException("叶子分类不能作为父分类");
            }
        }
        categoryRepository.save(category);
        return category.getId();
    }

    @Transactional
    public void update(Long id, CategoryDTO dto) {
        Category category = categoryRepository.findById(id)
                .orElseThrow(() -> new BusinessException("分类不存在"));
        // 检查是否将父分类改为叶子分类（有子分类时不允许）
        if (Boolean.TRUE.equals(dto.getIsLeaf()) && hasChildren(id)) {
            throw new BusinessException("该分类下有子分类，不能设置为叶子分类");
        }
        // 检查父分类是否合法
        if (dto.getParentId() != null) {
            Category parent = categoryRepository.findById(dto.getParentId())
                    .orElseThrow(() -> new BusinessException("父分类不存在"));
            if (parent.isLeaf()) {
                throw new BusinessException("叶子分类不能作为父分类");
            }
            // 防止循环引用
            if (dto.getParentId().equals(id)) {
                throw new BusinessException("不能将自身设置为父分类");
            }
        }
        BeanUtils.copyProperties(dto, category);
        category.setId(id);
        categoryRepository.save(category);
    }

    @Transactional(readOnly = true)
    public List<CategoryDTO> listAllActive() {
        List<Category> categories = categoryRepository.findAllActive();
        return buildTree(categories);
    }

    @Transactional(readOnly = true)
    public List<CategoryDTO> listAll() {
        List<Category> categories = categoryRepository.findAll();
        return buildTree(categories);
    }

    @Transactional(readOnly = true)
    public List<CategoryDTO> listLeafCategories() {
        return categoryRepository.findAllActive().stream()
                .filter(Category::isLeaf)
                .map(this::toDTO)
                .toList();
    }

    @Transactional(readOnly = true)
    public CategoryDTO getById(Long id) {
        Category category = categoryRepository.findById(id)
                .orElseThrow(() -> new BusinessException("分类不存在"));
        return toDTO(category);
    }

    @Transactional
    public void delete(Long id) {
        Category category = categoryRepository.findById(id)
                .orElseThrow(() -> new BusinessException("分类不存在"));

        // 检查是否有子分类
        if (hasChildren(id)) {
            throw new BusinessException("该分类下有子分类，不能删除");
        }

        // 检查是否有文章关联（只有叶子分类可能关联文章）
        if (category.isLeaf()) {
            Long articleCount = articleRepository.countByCategoryId(id);
            if (articleCount > 0) {
                throw new BusinessException("该分类下有关联文章，不能删除");
            }
        }

        categoryRepository.deleteById(id);
    }

    /**
     * 是否有子分类
     */
    private boolean hasChildren(Long parentId) {
        return categoryRepository.findAll().stream()
                .anyMatch(c -> parentId.equals(c.getParentId()));
    }

    /**
     * 构建树形结构
     */
    private List<CategoryDTO> buildTree(List<Category> categories) {
        // 转换为DTO
        List<CategoryDTO> dtoList = categories.stream()
                .map(this::toDTO)
                .toList();

        // 按parentId分组
        Map<Long, List<CategoryDTO>> parentMap = dtoList.stream()
                .filter(dto -> dto.getParentId() != null)
                .collect(Collectors.groupingBy(CategoryDTO::getParentId));

        // 设置子节点
        dtoList.forEach(dto -> dto.setChildren(parentMap.get(dto.getId())));

        // 返回根节点（parentId为null的节点）
        return dtoList.stream()
                .filter(dto -> dto.getParentId() == null)
                .sorted(Comparator.comparing(CategoryDTO::getSort, Comparator.nullsLast(Integer::compareTo)))
                .collect(Collectors.toList());
    }

    private CategoryDTO toDTO(Category category) {
        CategoryDTO dto = new CategoryDTO();
        BeanUtils.copyProperties(category, dto);
        dto.setId(category.getId());
        return dto;
    }
}
