package com.nanmuli.blog.application.dashboard.dto;

import lombok.Data;

@Data
public class DashboardStatsDTO {
    private Long articleCount;
    private Long categoryCount;
    private Long tagCount;
    private Long viewCount;
}
