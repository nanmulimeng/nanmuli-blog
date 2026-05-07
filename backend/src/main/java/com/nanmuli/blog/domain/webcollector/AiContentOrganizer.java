package com.nanmuli.blog.domain.webcollector;

import java.util.List;
import java.util.concurrent.CompletableFuture;

/**
 * AI 内容整理服务接口。
 * 负责将爬取的原始内容整理为结构化结果，并提供关键词优化、扩展与日报生成能力。
 */
public interface AiContentOrganizer {

    /**
     * 单页内容整理。
     *
     * @param rawMarkdown 原始 Markdown 内容
     * @param template AI 整理模板
     * @return 整理结果
     */
    CompletableFuture<OrganizedContent> organize(String rawMarkdown, AiTemplate template);

    /**
     * 单页内容整理（带搜索上下文）。
     * 关键词搜索任务可覆盖此方法，将实际搜索上下文注入提示词；默认忽略上下文。
     *
     * @param rawMarkdown 原始 Markdown 内容
     * @param template AI 整理模板
     * @param keywordContext 搜索上下文，可为空
     * @return 整理结果
     */
    default CompletableFuture<OrganizedContent> organize(
            String rawMarkdown, AiTemplate template, String keywordContext) {
        return organize(rawMarkdown, template);
    }

    /**
     * 多页或多来源内容汇总整理。
     *
     * @param pages 页面内容列表
     * @param template AI 整理模板
     * @return 整理结果
     */
    CompletableFuture<OrganizedContent> organizeMultiple(List<PageContent> pages, AiTemplate template);

    /**
     * 多页或多来源内容汇总整理（带搜索上下文）。
     * 实现类可覆盖此方法利用关键词上下文优化整理策略；默认忽略上下文。
     *
     * @param pages 页面内容列表
     * @param template AI 整理模板
     * @param keyword 搜索关键词上下文，可为空
     * @return 整理结果
     */
    default CompletableFuture<OrganizedContent> organizeMultiple(
            List<PageContent> pages, AiTemplate template, String keyword) {
        return organizeMultiple(pages, template);
    }

    /**
     * 搜索前的关键词优化。
     *
     * @param keyword 用户原始关键词
     * @return 优化后的关键词，失败时回退原词
     */
    default CompletableFuture<String> optimizeKeyword(String keyword) {
        return CompletableFuture.completedFuture(keyword);
    }

    /**
     * 搜索前的关键词扩展。
     *
     * @param keyword 用户原始关键词
     * @return 扩展后的关键词列表，失败时回退为仅包含原词
     */
    default CompletableFuture<List<String>> expandKeywords(String keyword) {
        return CompletableFuture.completedFuture(List.of(keyword));
    }

    /**
     * 生成技术日报。
     *
     * @param pages 当日收集的页面内容
     * @param date 日报日期
     * @return 日报内容
     */
    CompletableFuture<DigestContent> generateDigest(List<DigestPageContent> pages, String date);

    class OrganizedContent {
        public String title;
        public String summary;
        public List<String> keyPoints;
        public List<String> tags;
        public String category;
        public String fullContent;
        public int tokensUsed;
        public int durationMs;
    }

    class PageContent {
        public String url;
        public String title;
        public String markdown;
        public int wordCount;
        public int depth;
    }

    class DigestPageContent {
        public String url;
        public String title;
        public String markdown;
        public String summary;
        public ContentCategory category;
        public String sourceName;
    }

    class DigestContent {
        public String title;
        public String summary;
        public List<DigestSection> sections;
        public String highlight;
        public List<String> tags;
        public String fullContent;
        public int tokensUsed;
        public int durationMs;
    }

    class DigestSection {
        public String category;
        public String categoryName;
        public String emoji;
        public List<DigestItem> items;
    }

    class DigestItem {
        public String title;
        public String oneLiner;
        public String sourceUrl;
        public String sourceName;
    }
}
