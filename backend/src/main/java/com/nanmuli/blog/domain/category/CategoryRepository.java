package com.nanmuli.blog.domain.category;

import java.util.List;
import java.util.Optional;

public interface CategoryRepository {
    Category save(Category category);

    Optional<Category> findById(Long id);

    Optional<Category> findBySlug(String slug);

    List<Category> findAllActive();

    List<Category> findAll();

    void deleteById(Long id);

    /**
     * 检查是否存在指定父分类的子分类
     */
    boolean existsByParentId(Long parentId);
}
