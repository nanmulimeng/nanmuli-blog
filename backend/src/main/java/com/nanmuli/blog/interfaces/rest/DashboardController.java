package com.nanmuli.blog.interfaces.rest;

import com.nanmuli.blog.application.article.dto.ArticleDTO;
import com.nanmuli.blog.application.dashboard.DashboardAppService;
import com.nanmuli.blog.application.dashboard.dto.DashboardStatsDTO;
import com.nanmuli.blog.shared.result.Result;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@Tag(name = "仪表盘")
@RestController
@RequestMapping("/api/admin")
@RequiredArgsConstructor
public class DashboardController {

    private final DashboardAppService dashboardAppService;

    @GetMapping("/dashboard/stats")
    public Result<DashboardStatsDTO> getStats() {
        return Result.success(dashboardAppService.getStats());
    }

    @GetMapping("/dashboard/recent-articles")
    public Result<List<ArticleDTO>> getRecentArticles(
            @RequestParam(defaultValue = "5") int limit) {
        return Result.success(dashboardAppService.getRecentArticles(limit));
    }
}
