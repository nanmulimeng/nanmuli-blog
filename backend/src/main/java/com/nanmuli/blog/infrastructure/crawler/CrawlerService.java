package com.nanmuli.blog.infrastructure.crawler;

import java.util.List;

/**
 * 爬虫服务接口
 *
 * 调用 Python Crawl4AI 服务执行网页爬取
 */
public interface CrawlerService {

    /**
     * 单页爬取
     *
     * @param url    目标 URL
     * @param config 爬取配置（可选）
     * @return 爬取结果
     */
    CrawlResult crawlSingle(String url, CrawlConfig config);

    /**
     * 深度爬取
     *
     * @param url       起始 URL
     * @param maxDepth  最大深度
     * @param maxPages  最大页面数
     * @param config    爬取配置（可选）
     * @return 多页爬取结果
     */
    List<CrawlResult> crawlDeep(String url, int maxDepth, int maxPages, CrawlConfig config);

    /**
     * 关键词搜索爬取
     *
     * @param keyword     搜索关键词
     * @param engine      搜索引擎
     * @param maxResults  最大结果数
     * @param config      爬取配置（可选）
     * @return 搜索结果爬取列表
     */
    List<CrawlResult> crawlByKeyword(String keyword, String engine, int maxResults, CrawlConfig config);

    /**
     * 健康检查
     *
     * @return 服务是否可用
     */
    boolean healthCheck();

    /**
     * 爬取配置
     */
    class CrawlConfig {
        private boolean textMode = true;
        private boolean lightMode = true;
        private int wordCountThreshold = 15;
        private List<String> excludedTags;
        private String waitUntil = "load";
        private int pageTimeout = 60000;
        private String timeRange = "week"; // day / week / month / year / all

        public CrawlConfig() {
            this.excludedTags = List.of("nav", "footer", "aside", "header", "script", "style");
        }

        // Getters and Setters
        public boolean isTextMode() { return textMode; }
        public void setTextMode(boolean textMode) { this.textMode = textMode; }
        public boolean isLightMode() { return lightMode; }
        public void setLightMode(boolean lightMode) { this.lightMode = lightMode; }
        public int getWordCountThreshold() { return wordCountThreshold; }
        public void setWordCountThreshold(int wordCountThreshold) { this.wordCountThreshold = wordCountThreshold; }
        public List<String> getExcludedTags() { return excludedTags; }
        public void setExcludedTags(List<String> excludedTags) { this.excludedTags = excludedTags; }
        public String getWaitUntil() { return waitUntil; }
        public void setWaitUntil(String waitUntil) { this.waitUntil = waitUntil; }
        public int getPageTimeout() { return pageTimeout; }
        public void setPageTimeout(int pageTimeout) { this.pageTimeout = pageTimeout; }
        public String getTimeRange() { return timeRange; }
        public void setTimeRange(String timeRange) { this.timeRange = timeRange; }
    }
}
