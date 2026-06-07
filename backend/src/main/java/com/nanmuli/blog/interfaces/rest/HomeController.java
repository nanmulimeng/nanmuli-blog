package com.nanmuli.blog.interfaces.rest;

import com.nanmuli.blog.application.article.ArticleAppService;
import com.nanmuli.blog.application.article.dto.ArticleDTO;
import com.nanmuli.blog.application.article.dto.HomeAggregatedDTO;
import com.nanmuli.blog.application.category.CategoryAppService;
import com.nanmuli.blog.application.category.dto.CategoryDTO;
import com.nanmuli.blog.application.dailylog.DailyLogAppService;
import com.nanmuli.blog.application.project.ProjectAppService;
import com.nanmuli.blog.application.project.dto.ProjectDTO;
import com.nanmuli.blog.application.skill.SkillAppService;
import com.nanmuli.blog.application.skill.dto.SkillDTO;
import com.nanmuli.blog.shared.result.Result;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.Executor;
import java.util.function.Supplier;

@Tag(name = "首页聚合")
@Slf4j
@RestController
@RequestMapping("/api")
public class HomeController {

    private final ArticleAppService articleAppService;
    private final CategoryAppService categoryAppService;
    private final SkillAppService skillAppService;
    private final ProjectAppService projectAppService;
    private final DailyLogAppService dailyLogAppService;
    private final Executor taskExecutor;

    public HomeController(ArticleAppService articleAppService,
                          CategoryAppService categoryAppService,
                          SkillAppService skillAppService,
                          ProjectAppService projectAppService,
                          DailyLogAppService dailyLogAppService,
                          @Qualifier("taskExecutor") Executor taskExecutor) {
        this.articleAppService = articleAppService;
        this.categoryAppService = categoryAppService;
        this.skillAppService = skillAppService;
        this.projectAppService = projectAppService;
        this.dailyLogAppService = dailyLogAppService;
        this.taskExecutor = taskExecutor;
    }

    @GetMapping("/home/aggregated")
    public Result<HomeAggregatedDTO> aggregated() {
        HomeAggregatedDTO dto = new HomeAggregatedDTO();

        // 并行执行独立查询，使用 taskExecutor 避免 ForkJoinPool 线程饥饿
        CompletableFuture<List<ArticleDTO>> topArticlesFuture = safeAsync("topArticles", () -> articleAppService.listTop(3), List.of());
        CompletableFuture<List<ArticleDTO>> latestArticlesFuture = safeAsync("latestArticles", () -> articleAppService.listLatest(5), List.of());
        CompletableFuture<List<ArticleDTO>> hotArticlesFuture = safeAsync("hotArticles", () -> articleAppService.listHot(5), List.of());
        CompletableFuture<List<CategoryDTO>> categoriesFuture = safeAsync("categories", () -> categoryAppService.listAllActive(), List.of());
        CompletableFuture<List<SkillDTO>> skillsFuture = safeAsync("skills", () -> skillAppService.listAllVisible(), List.of());
        CompletableFuture<List<ProjectDTO>> projectsFuture = safeAsync("projects", () -> projectAppService.listAllVisible(), List.of());
        CompletableFuture<Long> articleCountFuture = safeAsync("articleCount", () -> articleAppService.countPublished(), 0L);
        CompletableFuture<Long> dailyLogCountFuture = safeAsync("dailyLogCount", () -> dailyLogAppService.countPublic(), 0L);

        // 等待所有查询完成
        CompletableFuture.allOf(
                topArticlesFuture, latestArticlesFuture, hotArticlesFuture, categoriesFuture, skillsFuture,
                projectsFuture, articleCountFuture, dailyLogCountFuture
        ).join();

        dto.setLatestArticles(latestArticlesFuture.join());
        dto.setHotArticles(hotArticlesFuture.join());
        dto.setTopArticles(topArticlesFuture.join());
        dto.setCategories(categoriesFuture.join());
        dto.setSkills(skillsFuture.join());
        dto.setProjects(projectsFuture.join());

        HomeAggregatedDTO.SiteStatsDTO stats = new HomeAggregatedDTO.SiteStatsDTO();
        stats.setArticleCount(articleCountFuture.join());
        stats.setProjectCount((long) dto.getProjects().size());
        stats.setDailyLogCount(dailyLogCountFuture.join());
        dto.setStats(stats);

        return Result.success(dto);
    }

    private <T> CompletableFuture<T> safeAsync(String name, Supplier<T> supplier, T fallback) {
        return CompletableFuture.supplyAsync(supplier, taskExecutor)
                .exceptionally(ex -> {
                    log.warn("Homepage aggregated section failed: {}", name, ex);
                    return fallback;
                });
    }
}
