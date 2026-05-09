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
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.concurrent.CompletableFuture;

@Tag(name = "首页聚合")
@RestController
@RequestMapping("/api")
@RequiredArgsConstructor
public class HomeController {

    private final ArticleAppService articleAppService;
    private final CategoryAppService categoryAppService;
    private final SkillAppService skillAppService;
    private final ProjectAppService projectAppService;
    private final DailyLogAppService dailyLogAppService;

    @GetMapping("/home/aggregated")
    public Result<HomeAggregatedDTO> aggregated() {
        HomeAggregatedDTO dto = new HomeAggregatedDTO();

        // 并行执行独立查询，避免串行阻塞
        CompletableFuture<List<ArticleDTO>> topArticlesFuture = CompletableFuture.supplyAsync(() -> articleAppService.listTop(3));
        CompletableFuture<List<CategoryDTO>> categoriesFuture = CompletableFuture.supplyAsync(() -> categoryAppService.listAllActive());
        CompletableFuture<List<SkillDTO>> skillsFuture = CompletableFuture.supplyAsync(() -> skillAppService.listAllVisible());
        CompletableFuture<List<ProjectDTO>> projectsFuture = CompletableFuture.supplyAsync(() -> projectAppService.listAllVisible());
        CompletableFuture<Long> articleCountFuture = CompletableFuture.supplyAsync(() -> articleAppService.countPublished());
        CompletableFuture<Long> dailyLogCountFuture = CompletableFuture.supplyAsync(() -> dailyLogAppService.count());

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
