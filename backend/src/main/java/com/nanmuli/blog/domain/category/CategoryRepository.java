package com.nanmuli.blog.domain.category;

import java.util.List;
import java.util.Optional;

public interface CategoryRepository {
    Category save(Category category);

    Optional<Category> findById(Long id);

    Optional<Category> findBySlug(String slug);

    List<Category> findAllActive();

    void deleteById(Long id);
}
