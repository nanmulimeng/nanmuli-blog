package com.nanmuli.blog.interfaces.rest;

import com.nanmuli.blog.application.category.CategoryAppService;
import com.nanmuli.blog.application.category.dto.CategoryDTO;
import com.nanmuli.blog.shared.result.Result;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@Tag(name = "分类管理")
@RestController
@RequestMapping("/api")
@RequiredArgsConstructor
public class CategoryController {

    private final CategoryAppService categoryAppService;

    @GetMapping("/category/list")
    public Result<List<CategoryDTO>> list() {
        return Result.success(categoryAppService.listAllActive());
    }

    @GetMapping("/category/leaf")
    public Result<List<CategoryDTO>> listLeaf() {
        return Result.success(categoryAppService.listLeafCategories());
    }

    @GetMapping("/admin/category/list")
    public Result<List<CategoryDTO>> adminList() {
        return Result.success(categoryAppService.listAll());
    }

    @PostMapping("/admin/category")
    public Result<Long> create(@Valid @RequestBody CategoryDTO dto) {
        return Result.success(categoryAppService.create(dto));
    }

    @PutMapping("/admin/category/{id}")
    public Result<Void> update(@PathVariable Long id, @Valid @RequestBody CategoryDTO dto) {
        categoryAppService.update(id, dto);
        return Result.success();
    }

    @DeleteMapping("/admin/category/{id}")
    public Result<Void> delete(@PathVariable Long id) {
        categoryAppService.delete(id);
        return Result.success();
    }
}
