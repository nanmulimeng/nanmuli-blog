package com.nanmuli.blog.interfaces.rest;

import com.nanmuli.blog.application.tag.TagAppService;
import com.nanmuli.blog.application.tag.dto.TagDTO;
import com.nanmuli.blog.shared.result.Result;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@Tag(name = "标签管理")
@RestController
@RequestMapping("/api")
@RequiredArgsConstructor
public class TagController {

    private final TagAppService tagAppService;

    @GetMapping("/tag/list")
    public Result<List<TagDTO>> list() {
        return Result.success(tagAppService.listAllActive());
    }

    @GetMapping("/tag/cloud")
    public Result<List<TagDTO>> tagCloud() {
        return Result.success(tagAppService.listAllActive());
    }

    @GetMapping("/admin/tag/list")
    public Result<List<TagDTO>> adminList() {
        return Result.success(tagAppService.listAll());
    }

    @PostMapping("/admin/tag")
    public Result<Long> create(@Valid @RequestBody TagDTO dto) {
        return Result.success(tagAppService.create(dto));
    }

    @PutMapping("/admin/tag/{id}")
    public Result<Void> update(@PathVariable Long id, @Valid @RequestBody TagDTO dto) {
        tagAppService.update(id, dto);
        return Result.success();
    }

    @DeleteMapping("/admin/tag/{id}")
    public Result<Void> delete(@PathVariable Long id) {
        tagAppService.delete(id);
        return Result.success();
    }
}
