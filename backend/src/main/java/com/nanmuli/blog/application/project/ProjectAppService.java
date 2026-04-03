package com.nanmuli.blog.application.project;

import com.nanmuli.blog.application.project.dto.ProjectDTO;
import com.nanmuli.blog.domain.project.Project;
import com.nanmuli.blog.domain.project.ProjectRepository;
import com.nanmuli.blog.shared.exception.BusinessException;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.BeanUtils;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
@RequiredArgsConstructor
public class ProjectAppService {

    private final ProjectRepository projectRepository;

    @Transactional
    public Long create(ProjectDTO dto) {
        Project project = new Project();
        BeanUtils.copyProperties(dto, project);
        projectRepository.save(project);
        return project.getId();
    }

    @Transactional
    public void update(Long id, ProjectDTO dto) {
        Project project = projectRepository.findById(id)
                .orElseThrow(() -> new BusinessException("项目不存在"));
        BeanUtils.copyProperties(dto, project);
        project.setId(id);
        projectRepository.save(project);
    }

    @Transactional(readOnly = true)
    public List<ProjectDTO> listAllVisible() {
        return projectRepository.findAllVisible().stream().map(this::toDTO).toList();
    }

    @Transactional(readOnly = true)
    public ProjectDTO getById(Long id) {
        Project project = projectRepository.findById(id)
                .orElseThrow(() -> new BusinessException("项目不存在"));
        return toDTO(project);
    }

    @Transactional
    public void delete(Long id) {
        projectRepository.deleteById(id);
    }

    private ProjectDTO toDTO(Project project) {
        ProjectDTO dto = new ProjectDTO();
        BeanUtils.copyProperties(project, dto);
        return dto;
    }
}
