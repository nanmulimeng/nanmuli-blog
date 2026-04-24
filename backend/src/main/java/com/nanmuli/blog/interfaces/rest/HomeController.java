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

        dto.setLatestArticles(articleAppService.listTop(5));
        dto.setTopArticles(articleAppService.listTop(3));
        dto.setHotArticles(articleAppService.listTop(5));
        dto.setCategories(categoryAppService.listAllActive());
        dto.setSkills(skillAppService.listAllVisible());
        dto.setProjects(projectAppService.listAllVisible());

        HomeAggregatedDTO.SiteStatsDTO stats = new HomeAggregatedDTO.SiteStatsDTO();
        stats.setArticleCount(articleAppService.countPublished());
        stats.setProjectCount((long) dto.getProjects().size());
        stats.setDailyLogCount(dailyLogAppService.count());
        dto.setStats(stats);

        return Result.success(dto);
    }
}
