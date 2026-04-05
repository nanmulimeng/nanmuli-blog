package com.nanmuli.blog.application.project;

import com.nanmuli.blog.application.project.command.CreateProjectCommand;
import com.nanmuli.blog.application.project.command.UpdateProjectCommand;
import com.nanmuli.blog.application.project.dto.ProjectDTO;
import com.nanmuli.blog.domain.project.Project;
import com.nanmuli.blog.domain.project.ProjectRepository;
import com.nanmuli.blog.shared.exception.BusinessException;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.BeanUtils;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.regex.Pattern;

@Service
@RequiredArgsConstructor
public class ProjectAppService {

    private final ProjectRepository projectRepository;

    // URL白名单：只允许http://和https://协议
    private static final Pattern ALLOWED_URL_PATTERN = Pattern.compile("^https?://.*$", Pattern.CASE_INSENSITIVE);

    /**
     * 验证URL协议是否安全（防御纵深）
     */
    private void validateUrlProtocol(String url, String fieldName) {
        if (url != null && !url.isEmpty() && !ALLOWED_URL_PATTERN.matcher(url).matches()) {
            throw new BusinessException(400, fieldName + "只能使用http或https协议");
        }
    }

    /**
     * 验证所有URL字段
     */
    private void validateUrls(CreateProjectCommand command) {
        validateUrlProtocol(command.getGithubUrl(), "GitHub链接");
        validateUrlProtocol(command.getDemoUrl(), "演示链接");
        validateUrlProtocol(command.getDocUrl(), "文档链接");
    }

    @Transactional
    public Long create(CreateProjectCommand command) {
        // 防御纵深：后端再次校验URL协议
        validateUrls(command);

        Project project = new Project();
        BeanUtils.copyProperties(command, project);
        // 将列表转换为逗号分隔的字符串
        project.setScreenshots(parseListToString(command.getScreenshots()));
        project.setTechStack(parseListToString(command.getTechStack()));
        projectRepository.save(project);

        // 如果没有提供slug，使用ID自动生成
        if (project.getSlug() == null || project.getSlug().isEmpty()) {
            project.setSlug(String.valueOf(project.getId()));
            projectRepository.save(project);
        } else {
            // 检查slug唯一性
            if (projectRepository.existsBySlug(project.getSlug())) {
                throw new BusinessException("项目标识已存在");
            }
        }

        return project.getId();
    }

    @Transactional
    public void update(Long id, UpdateProjectCommand command) {
        // 防御纵深：后端再次校验URL协议
        validateUrls(command);

        Project project = projectRepository.findById(id)
                .orElseThrow(() -> new BusinessException("项目不存在"));

        // 检查slug唯一性（排除自身）
        if (command.getSlug() != null && !command.getSlug().isEmpty()) {
            if (!command.getSlug().equals(project.getSlug()) && projectRepository.existsBySlug(command.getSlug())) {
                throw new BusinessException("项目标识已存在");
            }
        }

        BeanUtils.copyProperties(command, project);
        // 将列表转换为逗号分隔的字符串
        project.setScreenshots(parseListToString(command.getScreenshots()));
        project.setTechStack(parseListToString(command.getTechStack()));
        project.setId(id);
        projectRepository.save(project);
    }

    @Transactional(readOnly = true)
    public List<ProjectDTO> listAllVisible() {
        return projectRepository.findAllVisible().stream().map(this::toDTO).toList();
    }

    @Transactional(readOnly = true)
    public List<ProjectDTO> listAll() {
        return projectRepository.findAll().stream().map(this::toDTO).toList();
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
        dto.setId(project.getId());
        // 显式映射时间字段（字段名不一致）
        dto.setCreateTime(project.getCreatedAt());
        dto.setUpdateTime(project.getUpdatedAt());
        // 将逗号分隔的字符串转换为列表
        dto.setScreenshots(parseStringToList(project.getScreenshots()));
        dto.setTechStack(parseStringToList(project.getTechStack()));
        return dto;
    }

    /**
     * 将逗号分隔的字符串转换为列表
     */
    private List<String> parseStringToList(String str) {
        if (str == null || str.isEmpty()) {
            return java.util.Collections.emptyList();
        }
        return java.util.Arrays.asList(str.split(","));
    }

    /**
     * 将列表转换为逗号分隔的字符串
     */
    private String parseListToString(List<String> list) {
        if (list == null || list.isEmpty()) {
            return "";
        }
        return String.join(",", list);
    }
}
