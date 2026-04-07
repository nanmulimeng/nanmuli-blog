package com.nanmuli.blog.infrastructure.crawler;

import lombok.Data;

import java.util.List;
import java.util.Map;

/**
 * 爬取结果 DTO
 */
@Data
public class CrawlResult {
    private boolean success;
    private String url;
    private String title;
    private String markdown;
    private Map<String, Object> metadata;
    private int wordCount;
    private long crawlTimeMs;
    private String errorMessage;
    private int depth; // 深度爬取用
    private int searchRank; // 关键词搜索用

    // 多页结果
    private List<CrawlResult> pages;
    private int totalPages;
    private long totalCrawlTimeMs;
    private String keyword;
}
