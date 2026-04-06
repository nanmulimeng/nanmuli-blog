package com.nanmuli.blog.infrastructure.persistence.project;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.nanmuli.blog.domain.project.Project;
import com.nanmuli.blog.domain.project.ProjectRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
@RequiredArgsConstructor
public class ProjectRepositoryImpl implements ProjectRepository {

    private final ProjectMapper projectMapper;

    @Override
    public Project save(Project project) {
        if (project.isNew()) {
            projectMapper.insert(project);
        } else {
            projectMapper.updateById(project);
        }
        return project;
    }

    @Override
    public Optional<Project> findById(Long id) {
        return Optional.ofNullable(projectMapper.selectById(id));
    }

    @Override
    public Optional<Project> findBySlug(String slug) {
        LambdaQueryWrapper<Project> wrapper = Wrappers.lambdaQuery();
        wrapper.eq(Project::getSlug, slug);
        return Optional.ofNullable(projectMapper.selectOne(wrapper));
    }

    @Override
    public boolean existsBySlug(String slug) {
        LambdaQueryWrapper<Project> wrapper = Wrappers.lambdaQuery();
        wrapper.eq(Project::getSlug, slug);
        return projectMapper.selectCount(wrapper) > 0;
    }

    @Override
    public List<Project> findAllVisible() {
        LambdaQueryWrapper<Project> wrapper = Wrappers.lambdaQuery();
        wrapper.eq(Project::getStatus, 1).orderByAsc(Project::getSort);
        return projectMapper.selectList(wrapper);
    }

    @Override
    public List<Project> findAll() {
        LambdaQueryWrapper<Project> wrapper = Wrappers.lambdaQuery();
        wrapper.orderByAsc(Project::getSort);
        return projectMapper.selectList(wrapper);
    }

    @Override
    public Long countAll() {
        LambdaQueryWrapper<Project> wrapper = Wrappers.lambdaQuery();
        wrapper.eq(Project::getIsDeleted, false);
        return projectMapper.selectCount(wrapper);
    }

    @Override
    public void deleteById(Long id) {
        projectMapper.deleteById(id);
    }
}
