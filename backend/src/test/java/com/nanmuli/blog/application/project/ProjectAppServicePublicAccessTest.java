package com.nanmuli.blog.application.project;

import com.nanmuli.blog.domain.project.Project;
import com.nanmuli.blog.domain.project.ProjectRepository;
import com.nanmuli.blog.shared.exception.BusinessException;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class ProjectAppServicePublicAccessTest {

    @Mock
    private ProjectRepository projectRepository;

    @Test
    void publicDetailDoesNotExposeHiddenProject() {
        Project hidden = new Project();
        hidden.setId(1L);
        hidden.setName("Hidden");
        hidden.setStatus(0);
        when(projectRepository.findById(1L)).thenReturn(Optional.of(hidden));

        ProjectAppService service = new ProjectAppService(projectRepository);

        assertThrows(BusinessException.class, () -> service.getVisibleById(1L));
    }
}
