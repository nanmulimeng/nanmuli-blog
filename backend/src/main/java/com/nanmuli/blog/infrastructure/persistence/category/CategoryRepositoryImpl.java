package com.nanmuli.blog.infrastructure.persistence.category;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.core.toolkit.StringUtils;
import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.nanmuli.blog.domain.category.Category;
import com.nanmuli.blog.domain.category.CategoryRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Repository;

import java.util.Collection;
import java.util.List;
import java.util.Optional;

@Repository
@RequiredArgsConstructor
public class CategoryRepositoryImpl implements CategoryRepository {

    private final CategoryMapper categoryMapper;

    @Override
    public Category save(Category category) {
        if (category.isNew()) {
            categoryMapper.insert(category);
        } else {
            categoryMapper.updateById(category);
        }
        return category;
    }

    @Override
    public Optional<Category> findById(Long id) {
        return Optional.ofNullable(categoryMapper.selectById(id));
    }

    @Override
    public Optional<Category> findBySlug(String slug) {
        LambdaQueryWrapper<Category> wrapper = Wrappers.lambdaQuery();
        wrapper.eq(Category::getSlug, slug)
               .eq(Category::getIsDeleted, false);
        return Optional.ofNullable(categoryMapper.selectOne(wrapper));
    }

    @Override
    public List<Category> findAllActive() {
        LambdaQueryWrapper<Category> wrapper = Wrappers.lambdaQuery();
        wrapper.eq(Category::getStatus, 1)
               .eq(Category::getIsDeleted, false)
               .orderByAsc(Category::getSort);
        return categoryMapper.selectList(wrapper);
    }

    @Override
    public List<Category> findAll() {
        LambdaQueryWrapper<Category> wrapper = Wrappers.lambdaQuery();
        wrapper.eq(Category::getIsDeleted, false)
               .orderByAsc(Category::getSort);
        return categoryMapper.selectList(wrapper);
    }

    @Override
    public Long countAll() {
        LambdaQueryWrapper<Category> wrapper = Wrappers.lambdaQuery();
        wrapper.eq(Category::getIsDeleted, false);
        return categoryMapper.selectCount(wrapper);
    }

    @Override
    public void deleteById(Long id) {
        categoryMapper.deleteById(id);
    }

    @Override
    public boolean existsByParentId(Long parentId) {
        LambdaQueryWrapper<Category> wrapper = Wrappers.lambdaQuery();
        wrapper.eq(Category::getParentId, parentId)
               .eq(Category::getIsDeleted, false);
        return categoryMapper.selectCount(wrapper) > 0;
    }

    @Override
    public List<Category> findByParentId(Long parentId) {
        LambdaQueryWrapper<Category> wrapper = Wrappers.lambdaQuery();
        wrapper.eq(Category::getParentId, parentId)
               .eq(Category::getIsDeleted, false)
               .orderByAsc(Category::getSort);
        return categoryMapper.selectList(wrapper);
    }

    @Override
    public boolean existsBySlug(String slug) {
        LambdaQueryWrapper<Category> wrapper = Wrappers.lambdaQuery();
        wrapper.eq(Category::getSlug, slug)
               .eq(Category::getIsDeleted, false);
        return categoryMapper.selectCount(wrapper) > 0;
    }

    @Override
    public IPage<Category> findPage(IPage<Category> page, Long parentId, Boolean isLeaf, Integer status, String keyword) {
        LambdaQueryWrapper<Category> wrapper = Wrappers.lambdaQuery();
        wrapper.eq(Category::getIsDeleted, false);

        // 父分类筛选
        if (parentId != null) {
            wrapper.eq(Category::getParentId, parentId);
        } else {
            // parentId为null表示查询根分类
            wrapper.isNull(Category::getParentId);
        }

        // 类型筛选
        if (isLeaf != null) {
            wrapper.eq(Category::getIsLeaf, isLeaf);
        }

        // 状态筛选
        if (status != null) {
            wrapper.eq(Category::getStatus, status);
        }

        // 关键词搜索（匹配名称或slug）
        if (StringUtils.isNotBlank(keyword)) {
            String escapedKeyword = escapeLikeKeyword(keyword);
            wrapper.and(w -> w.like(Category::getName, escapedKeyword)
                              .or()
                              .like(Category::getSlug, escapedKeyword));
        }

        // 默认按排序号升序
        wrapper.orderByAsc(Category::getSort);

        return categoryMapper.selectPage(page, wrapper);
    }

    @Override
    public List<Category> findAllById(Collection<Long> ids) {
        if (ids == null || ids.isEmpty()) {
            return List.of();
        }
        LambdaQueryWrapper<Category> wrapper = Wrappers.lambdaQuery();
        wrapper.in(Category::getId, ids)
               .eq(Category::getIsDeleted, false);
        return categoryMapper.selectList(wrapper);
    }

    /**
     * 转义LIKE查询中的特殊字符，并添加通配符
     */
    private String escapeLikeKeyword(String keyword) {
        if (keyword == null) {
            return null;
        }
        String escaped = keyword.replace("\\", "\\\\")
                                .replace("%", "\\%")
                                .replace("_", "\\_");
        return "%" + escaped + "%";
    }
}
