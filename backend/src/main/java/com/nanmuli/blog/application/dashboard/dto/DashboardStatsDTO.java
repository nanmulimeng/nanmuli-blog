package com.nanmuli.blog.application.dashboard.dto;

import lombok.Data;

@Data
public class DashboardStatsDTO {
    private Long articleCount;
    private Long projectCount;  // 项目数量
    private Long visitCount;    // 访问量（PV）
    private Long visitorCount;  // 访客数（UV）
}
