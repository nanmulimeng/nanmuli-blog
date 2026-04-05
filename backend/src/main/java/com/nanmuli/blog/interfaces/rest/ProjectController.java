package com.nanmuli.blog.interfaces.rest;

import com.nanmuli.blog.application.project.ProjectAppService;
import com.nanmuli.blog.application.project.dto.ProjectDTO;
import com.nanmuli.blog.shared.result.Result;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@Tag(name = "项目展示")
@RestController
@RequestMapping("/api")
@RequiredArgsConstructor
public class ProjectController {

    private final ProjectAppService projectAppService;

    @GetMapping("/project/list")
    public Result<List<ProjectDTO>> list() {
        return Result.success(projectAppService.listAllVisible());
    }

    @GetMapping("/project/{id}")
    public Result<ProjectDTO> detail(@PathVariable Long id) {
        return Result.success(projectAppService.getById(id));
    }

    @PostMapping("/admin/project")
    public Result<Long> create(@Valid @RequestBody ProjectDTO dto) {
        return Result.success(projectAppService.create(dto));
    }

    @PutMapping("/admin/project/{id}")
    public Result<Void> update(@PathVariable Long id, @Valid @RequestBody ProjectDTO dto) {
        projectAppService.update(id, dto);
        return Result.success();
    }

    @DeleteMapping("/admin/project/{id}")
    public Result<Void> delete(@PathVariable Long id) {
        projectAppService.delete(id);
        return Result.success();
    }
}
