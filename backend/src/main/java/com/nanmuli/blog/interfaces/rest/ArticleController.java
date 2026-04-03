package com.nanmuli.blog.interfaces.rest;

import com.nanmuli.blog.application.article.ArticleAppService;
import com.nanmuli.blog.application.article.command.CreateArticleCommand;
import com.nanmuli.blog.application.article.command.UpdateArticleCommand;
import com.nanmuli.blog.application.article.dto.ArticleDTO;
import com.nanmuli.blog.application.article.query.ArticlePageQuery;
import com.nanmuli.blog.shared.result.PageResult;
import com.nanmuli.blog.shared.result.Result;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@Tag(name = "文章管理")
@RestController
@RequestMapping("/api")
@RequiredArgsConstructor
public class ArticleController {

    private final ArticleAppService articleAppService;

    @GetMapping("/article/list")
    public Result<PageResult<ArticleDTO>> list(ArticlePageQuery query) {
        return Result.success(articleAppService.listPublished(query));
    }

    @GetMapping("/article/{slug}")
    public Result<ArticleDTO> detail(@PathVariable String slug) {
        return Result.success(articleAppService.getBySlug(slug));
    }

    @GetMapping("/article/top")
    public Result<List<ArticleDTO>> top(@RequestParam(defaultValue = "5") int limit) {
        return Result.success(articleAppService.listTop(limit));
    }

    @PostMapping("/admin/article")
    public Result<Long> create(@Valid @RequestBody CreateArticleCommand command) {
        return Result.success(articleAppService.create(command));
    }

    @PutMapping("/admin/article/{id}")
    public Result<Void> update(@PathVariable Long id, @Valid @RequestBody UpdateArticleCommand command) {
        command.setArticleId(id);
        articleAppService.update(command);
        return Result.success();
    }

    @DeleteMapping("/admin/article/{id}")
    public Result<Void> delete(@PathVariable Long id) {
        articleAppService.delete(id);
        return Result.success();
    }
}
