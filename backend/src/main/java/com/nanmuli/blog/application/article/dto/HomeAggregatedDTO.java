package com.nanmuli.blog.application.article.dto;

import com.nanmuli.blog.application.category.dto.CategoryDTO;
import com.nanmuli.blog.application.project.dto.ProjectDTO;
import com.nanmuli.blog.application.skill.dto.SkillDTO;
import com.nanmuli.blog.application.tag.dto.TagDTO;
import lombok.Data;

import java.util.List;

/**
 * 首页聚合数据 DTO
 */
@Data
public class HomeAggregatedDTO {

    /** 最新文章列表 */
    private List<ArticleDTO> latestArticles;

    /** 置顶文章列表 */
    private List<ArticleDTO> topArticles;

    /** 热门文章列表（按浏览量） */
    private List<ArticleDTO> hotArticles;

    /** 分类列表 */
    private List<CategoryDTO> categories;

    /** 标签云 */
    private List<TagDTO> tags;

    /** 技能展示 */
    private List<SkillDTO> skills;

    /** 项目展示 */
    private List<ProjectDTO> projects;

    /** 站点统计 */
    private SiteStatsDTO stats;

    @Data
    public static class SiteStatsDTO {
        private Long articleCount;
        private Long categoryCount;
        private Long tagCount;
        private Long dailyLogCount;
    }
}
