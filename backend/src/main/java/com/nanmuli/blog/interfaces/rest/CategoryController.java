package com.nanmuli.blog.interfaces.rest;

import cn.dev33.satoken.annotation.SaCheckPermission;
import com.nanmuli.blog.application.category.CategoryAppService;
import com.nanmuli.blog.application.category.command.CreateCategoryCommand;
import com.nanmuli.blog.application.category.command.UpdateCategoryCommand;
import com.nanmuli.blog.application.category.dto.CategoryDTO;
import com.nanmuli.blog.application.category.query.CategoryPageQuery;
import com.nanmuli.blog.shared.result.PageResult;
import com.nanmuli.blog.shared.result.Result;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * 分类管理控制器
 */
@Tag(name = "分类管理")
@RestController
@RequestMapping("/api")
@RequiredArgsConstructor
public class CategoryController {

    private final CategoryAppService categoryAppService;

    @Operation(summary = "获取分类树（前台）")
    @GetMapping("/category/list")
    public Result<List<CategoryDTO>> list() {
        return Result.success(categoryAppService.listAllActive());
    }

    @Operation(summary = "获取叶子分类列表")
    @GetMapping("/category/leaf")
    public Result<List<CategoryDTO>> listLeaf() {
        return Result.success(categoryAppService.listLeafCategories());
    }

    @Operation(summary = "获取所有分类树（管理后台）")
    @SaCheckPermission("category:list")
    @GetMapping("/admin/category/list")
    public Result<List<CategoryDTO>> adminList() {
        return Result.success(categoryAppService.listAll());
    }

    @Operation(summary = "分页查询分类列表（管理后台）")
    @SaCheckPermission("category:list")
    @GetMapping("/admin/category/page")
    public Result<PageResult<CategoryDTO>> adminPage(CategoryPageQuery query) {
        return Result.success(categoryAppService.listPage(query));
    }

    @Operation(summary = "获取分类详情")
    @SaCheckPermission("category:list")
    @GetMapping("/admin/category/{id}")
    public Result<CategoryDTO> getById(@PathVariable Long id) {
        return Result.success(categoryAppService.getById(id));
    }

    @Operation(summary = "获取分类路径")
    @SaCheckPermission("category:list")
    @GetMapping("/admin/category/{id}/path")
    public Result<List<CategoryDTO>> getCategoryPath(@PathVariable Long id) {
        return Result.success(categoryAppService.getCategoryPath(id));
    }

    @Operation(summary = "创建分类")
    @SaCheckPermission("category:create")
    @PostMapping("/admin/category")
    public Result<Long> create(@Valid @RequestBody CreateCategoryCommand command) {
        return Result.success(categoryAppService.create(command));
    }

    @Operation(summary = "更新分类")
    @SaCheckPermission("category:update")
    @PutMapping("/admin/category/{id}")
    public Result<Void> update(
            @PathVariable Long id,
            @Valid @RequestBody UpdateCategoryCommand command) {
        categoryAppService.update(id, command);
        return Result.success();
    }

    @Operation(summary = "删除分类")
    @SaCheckPermission("category:delete")
    @DeleteMapping("/admin/category/{id}")
    public Result<Void> delete(@PathVariable Long id) {
        categoryAppService.delete(id);
        return Result.success();
    }
}
