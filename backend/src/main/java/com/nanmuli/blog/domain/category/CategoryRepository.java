package com.nanmuli.blog.domain.category;

import com.baomidou.mybatisplus.core.metadata.IPage;

import java.util.List;
import java.util.Optional;

public interface CategoryRepository {
    Category save(Category category);

    Optional<Category> findById(Long id);

    Optional<Category> findBySlug(String slug);

    List<Category> findAllActive();

    List<Category> findAll();

    Long countAll();

    void deleteById(Long id);

    /**
     * 检查是否存在指定父分类的子分类
     */
    boolean existsByParentId(Long parentId);

    /**
     * 检查是否存在指定slug的分类
     */
    boolean existsBySlug(String slug);

    /**
     * 分页查询分类列表
     */
    IPage<Category> findPage(IPage<Category> page, Long parentId, Boolean isLeaf, Integer status, String keyword);
}
