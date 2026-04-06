package com.nanmuli.blog.application.dashboard;

import com.nanmuli.blog.application.article.dto.ArticleDTO;
import com.nanmuli.blog.application.dashboard.dto.DashboardStatsDTO;
import com.nanmuli.blog.domain.article.Article;
import com.nanmuli.blog.domain.article.ArticleRepository;
import com.nanmuli.blog.domain.article.ArticleViewRecordRepository;
import com.nanmuli.blog.domain.article.ArticleVisitLogRepository;
import com.nanmuli.blog.domain.project.ProjectRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.BeanUtils;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
@RequiredArgsConstructor
public class DashboardAppService {

    private final ArticleRepository articleRepository;
    private final ArticleViewRecordRepository articleViewRecordRepository;
    private final ArticleVisitLogRepository articleVisitLogRepository;
    private final ProjectRepository projectRepository;

    @Transactional(readOnly = true)
    public DashboardStatsDTO getStats() {
        DashboardStatsDTO stats = new DashboardStatsDTO();

        // 统计文章总数（所有未删除的）
        stats.setArticleCount(articleRepository.countAll());

        // 统计项目总数
        stats.setProjectCount(projectRepository.countAll());

        // 统计总访问量（PV）
        stats.setVisitCount(articleVisitLogRepository.countTotalVisits());

        // 统计总访客数（UV）
        stats.setVisitorCount(articleViewRecordRepository.countTotalUniqueVisitors());

        return stats;
    }

    @Transactional(readOnly = true)
    public List<ArticleDTO> getRecentArticles(int limit) {
        return articleRepository.findLatestArticles(limit).stream()
                .map(this::toArticleDTO)
                .toList();
    }

    private ArticleDTO toArticleDTO(Article article) {
        ArticleDTO dto = new ArticleDTO();
        BeanUtils.copyProperties(article, dto);
        dto.setId(article.getId());
        dto.setCreateTime(article.getCreatedAt());
        dto.setUpdateTime(article.getUpdatedAt());
        return dto;
    }
}
