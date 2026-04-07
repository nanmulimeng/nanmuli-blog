package com.nanmuli.blog.domain.webcollector;

import com.baomidou.mybatisplus.annotation.TableName;
import com.nanmuli.blog.shared.domain.BaseAggregateRoot;
import lombok.EqualsAndHashCode;
import lombok.Getter;
import lombok.Setter;

import java.time.LocalDateTime;

/**
 * 爬取页面实体
 * 属于 WebCollectTask 聚合的一部分
 */
@Getter
@Setter
@EqualsAndHashCode(callSuper = false)
@TableName("web_collect_page")
public class WebCollectPage extends BaseAggregateRoot<Long> {
    private static final long serialVersionUID = 1L;

    private Long taskId;

    // 页面信息
    private String url;
    private String pageTitle;
    private String rawMarkdown;
    private String pageMetadata; // JSON 字符串

    // 爬取状态
    private Integer crawlStatus; // 0=待爬取 1=爬取中 2=已完成 3=失败
    private String errorMessage;
    private Integer crawlDuration; // 毫秒
    private Integer wordCount;

    // 去重字段
    private String urlHash; // SHA-256
    private String contentHash; // SHA-256

    // 排序
    private Integer sortOrder;
    private Integer depth;

    // 时效性
    private LocalDateTime publishedAt;

    // 领域方法
    public boolean isCrawlCompleted() {
        return crawlStatus != null && (crawlStatus == 2 || crawlStatus == 3);
    }

    public boolean isCrawlSuccess() {
        return crawlStatus != null && crawlStatus == 2;
    }

    public void markCrawling() {
        this.crawlStatus = 1;
    }

    public void markCompleted(String markdown, String metadata, int wordCount, int duration) {
        this.rawMarkdown = markdown;
        this.pageMetadata = metadata;
        this.wordCount = wordCount;
        this.crawlDuration = duration;
        this.crawlStatus = 2;
    }

    public void markFailed(String error) {
        this.errorMessage = error;
        this.crawlStatus = 3;
    }
}
