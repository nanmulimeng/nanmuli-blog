package com.nanmuli.blog.domain.project;

import java.util.List;
import java.util.Optional;

public interface ProjectRepository {
    Project save(Project project);

    Optional<Project> findById(Long id);

    Optional<Project> findBySlug(String slug);

    boolean existsBySlug(String slug);

    List<Project> findAllVisible();

    List<Project> findAll();

    void deleteById(Long id);
}
