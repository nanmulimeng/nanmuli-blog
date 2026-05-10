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
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.Executor;

@Tag(name = "首页聚合")
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
        CompletableFuture<List<ArticleDTO>> topArticlesFuture = CompletableFuture.supplyAsync(() -> articleAppService.listTop(3), taskExecutor);
        CompletableFuture<List<CategoryDTO>> categoriesFuture = CompletableFuture.supplyAsync(() -> categoryAppService.listAllActive(), taskExecutor);
        CompletableFuture<List<SkillDTO>> skillsFuture = CompletableFuture.supplyAsync(() -> skillAppService.listAllVisible(), taskExecutor);
        CompletableFuture<List<ProjectDTO>> projectsFuture = CompletableFuture.supplyAsync(() -> projectAppService.listAllVisible(), taskExecutor);
        CompletableFuture<Long> articleCountFuture = CompletableFuture.supplyAsync(() -> articleAppService.countPublished(), taskExecutor);
        CompletableFuture<Long> dailyLogCountFuture = CompletableFuture.supplyAsync(() -> dailyLogAppService.countPublic(), taskExecutor);

        // 等待所有查询完成
        CompletableFuture.allOf(
                topArticlesFuture, categoriesFuture, skillsFuture,
                projectsFuture, articleCountFuture, dailyLogCountFuture
        ).join();

        // latestArticles 和 hotArticles 复用 listTop(5) 的缓存结果
        List<ArticleDTO> latestAndHot = articleAppService.listTop(5);
        dto.setLatestArticles(latestAndHot);
        dto.setHotArticles(latestAndHot);
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
}
