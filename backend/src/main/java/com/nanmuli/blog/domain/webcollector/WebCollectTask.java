package com.nanmuli.blog.domain.webcollector;

import com.baomidou.mybatisplus.annotation.TableName;
import com.nanmuli.blog.shared.domain.BaseAggregateRoot;
import lombok.EqualsAndHashCode;
import lombok.Getter;
import lombok.Setter;

/**
 * 采集任务聚合根实体
 */
@Getter
@Setter
@EqualsAndHashCode(callSuper = false)
@TableName("web_collect_task")
public class WebCollectTask extends BaseAggregateRoot<Long> {
    private static final long serialVersionUID = 1L;

    // 任务类型与输入
    private String taskType; // single / deep / keyword / digest
    private String sourceUrl;
    private String keyword;
    private String searchEngine; // bing / duckduckgo
    private String triggerType; // manual / scheduled

    // 关联
    private Long sourceId;
    private Long articleId;
    private Long dailyLogId;
    private Long userId;

    // AI 整理结果
    private String aiTitle;
    private String aiSummary;
    private String aiKeyPoints; // JSON
    private String aiTags; // JSON
    private String aiCategory;
    private String aiFullContent;

    // 任务状态
    private Integer status; // 0=待处理 1=爬取中 2=整理中 3=已完成 4=失败
    private String errorMessage;

    // 配置
    private String crawlMode;
    private String aiTemplate;
    private Integer maxDepth;
    private Integer maxPages;

    // 进度追踪
    private Integer totalPages;
    private Integer completedPages;

    // 统计
    private Integer crawlDuration;
    private Integer aiDuration;
    private Integer tokensUsed;
    private Integer totalWordCount;

    // 领域方法

    public CollectTaskStatus getStatusEnum() {
        return CollectTaskStatus.of(this.status);
    }

    public void updateStatus(CollectTaskStatus status) {
        this.status = status.getValue();
    }

    public boolean isTerminal() {
        return getStatusEnum().isTerminal();
    }

    public void initProgress(int totalPages) {
        this.totalPages = totalPages;
        this.completedPages = 0;
        updateStatus(CollectTaskStatus.CRAWLING);
    }

    public void updateProgress(int completedPages) {
        this.completedPages = completedPages;
    }

    public void markCrawlCompleted(int duration, int totalWordCount) {
        this.crawlDuration = duration;
        this.totalWordCount = totalWordCount;
        updateStatus(CollectTaskStatus.PROCESSING);
    }

    public void markAiCompleted(String title, String summary, String keyPoints,
                                 String tags, String category, String fullContent,
                                 int aiDuration, int tokensUsed) {
        this.aiTitle = title;
        this.aiSummary = summary;
        this.aiKeyPoints = keyPoints;
        this.aiTags = tags;
        this.aiCategory = category;
        this.aiFullContent = fullContent;
        this.aiDuration = aiDuration;
        this.tokensUsed = tokensUsed;
        updateStatus(CollectTaskStatus.COMPLETED);
    }

    public void markFailed(String errorMessage) {
        this.errorMessage = errorMessage;
        updateStatus(CollectTaskStatus.FAILED);
    }

    public void markArticleCreated(Long articleId) {
        this.articleId = articleId;
    }

    public void markDailyLogCreated(Long dailyLogId) {
        this.dailyLogId = dailyLogId;
    }

    public String getDisplayStatus() {
        return getStatusEnum().getDisplayText();
    }
}
