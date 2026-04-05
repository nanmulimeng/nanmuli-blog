package com.nanmuli.blog.interfaces.rest;

import com.nanmuli.blog.application.skill.SkillAppService;
import com.nanmuli.blog.application.skill.dto.SkillDTO;
import com.nanmuli.blog.shared.result.Result;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@Tag(name = "技能展示")
@RestController
@RequestMapping("/api")
@RequiredArgsConstructor
public class SkillController {

    private final SkillAppService skillAppService;

    @GetMapping("/skill/list")
    public Result<List<SkillDTO>> list() {
        return Result.success(skillAppService.listAllVisible());
    }

    @GetMapping("/admin/skill/list")
    public Result<List<SkillDTO>> adminList() {
        return Result.success(skillAppService.listAll());
    }

    @GetMapping("/skill/{id}")
    public Result<SkillDTO> detail(@PathVariable Long id) {
        return Result.success(skillAppService.getById(id));
    }

    @PostMapping("/admin/skill")
    public Result<Long> create(@Valid @RequestBody SkillDTO dto) {
        return Result.success(skillAppService.create(dto));
    }

    @PutMapping("/admin/skill/{id}")
    public Result<Void> update(@PathVariable Long id, @Valid @RequestBody SkillDTO dto) {
        skillAppService.update(id, dto);
        return Result.success();
    }

    @DeleteMapping("/admin/skill/{id}")
    public Result<Void> delete(@PathVariable Long id) {
        skillAppService.delete(id);
        return Result.success();
    }
}
