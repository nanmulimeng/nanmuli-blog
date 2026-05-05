package com.nanmuli.blog.domain.webcollector;

import java.util.List;
import java.util.concurrent.CompletableFuture;

/**
 * AI 内容整理服务接口（领域层定义）
 *
 * 职责：将爬取的原始内容整理为结构化知识
 * 注意：与 AiService 职责分离，AiService 服务文章聚合
 */
public interface AiContentOrganizer {

    /**
     * 单页内容整理
     *
     * @param rawMarkdown 爬取的 Markdown 内容
     * @param template    AI 整理模板
     * @return 整理结果
     */
    CompletableFuture<OrganizedContent> organize(String rawMarkdown, AiTemplate template);

    /**
     * 多页/多源内容汇总整理
     *
     * @param pages    多个页面的内容
     * @param template AI 整理模板
     * @return 整理结果
     */
    CompletableFuture<OrganizedContent> organizeMultiple(List<PageContent> pages, AiTemplate template);

    /**
     * 多页/多源内容汇总整理（带搜索关键词上下文）
     * <p>实现类可覆写此方法以利用关键词优化整理策略；默认忽略关键词委托给 {@link #organizeMultiple}</p>
     *
     * @param pages    多个页面的内容
     * @param template AI 整理模板
     * @param keyword  搜索关键词（可为 null）
     * @return 整理结果
     */
    default CompletableFuture<OrganizedContent> organizeMultiple(
            List<PageContent> pages, AiTemplate template, String keyword) {
        return organizeMultiple(pages, template);
    }

    /**
     * 关键词优化（搜索前）
     * <p>将用户输入的关键词优化为更精准的搜索引擎查询词。</p>
     * <p>默认实现直接返回原关键词，不做任何修改。</p>
     *
     * @param keyword 用户输入的关键词
     * @return 优化后的关键词（失败时回退到原关键词）
     */
    default CompletableFuture<String> optimizeKeyword(String keyword) {
        return CompletableFuture.completedFuture(keyword);
    }

    /**
     * 关键词扩展（搜索前）
     * <p>将用户输入的关键词扩展为多个相关搜索词变体，用于多路并行爬取。</p>
     * <p>默认实现返回包含原关键词的单元素列表。</p>
     *
     * @param keyword 用户输入的关键词
     * @return 扩展后的关键词列表（失败时回退到单元素列表）
     */
    default CompletableFuture<List<String>> expandKeywords(String keyword) {
        return CompletableFuture.completedFuture(List.of(keyword));
    }

    /**
     * 每日日报生成
     *
     * @param pages 当日收集的所有页面内容
     * @param date  日报日期
     * @return 日报内容
     */
    CompletableFuture<DigestContent> generateDigest(List<DigestPageContent> pages, String date);

    /**
     * 整理结果数据类
     */
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

    /**
     * 页面内容（用于多源整理）
     */
    class PageContent {
        public String url;
        public String title;
        public String markdown;
        public int wordCount;
        public int depth;
    }

    /**
     * 日报页面内容（带分类）
     */
    class DigestPageContent {
        public String url;
        public String title;
        public String markdown;
        public String summary;
        public ContentCategory category;
        public String sourceName;
    }

    /**
     * 日报内容
     */
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

    /**
     * 日报章节
     */
    class DigestSection {
        public String category;
        public String categoryName;
        public String emoji;
        public List<DigestItem> items;
    }

    /**
     * 日报条目
     */
    class DigestItem {
        public String title;
        public String oneLiner;
        public String sourceUrl;
        public String sourceName;
    }
}
