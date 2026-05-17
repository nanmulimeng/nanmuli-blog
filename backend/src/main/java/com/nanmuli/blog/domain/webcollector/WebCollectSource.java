package com.nanmuli.blog.domain.webcollector;

import com.baomidou.mybatisplus.annotation.TableName;
import com.nanmuli.blog.shared.domain.BaseAggregateRoot;
import lombok.EqualsAndHashCode;
import lombok.Getter;
import lombok.Setter;

import java.time.LocalDateTime;

/**
 * 采集订阅源聚合根
 */
@Getter
@Setter
@EqualsAndHashCode(callSuper = false)
@TableName("web_collect_source")
public class WebCollectSource extends BaseAggregateRoot<Long> {
    private static final long serialVersionUID = 1L;

    private String name;            // 来源名称
    private String type;            // url / keyword / rss
    private String value;           // URL / 关键词文本 / RSS 地址
    private String contentCategory; // hot_trend / open_source / tech_article / dev_tool / creative / paper
    private String crawlMode;       // single / deep
    private Integer maxDepth;
    private Integer maxPages;
    private String cssSelector;
    private String aiTemplate;
    private String scheduleCron;
    private Integer freshnessHours;
    private Boolean isActive;
    private LocalDateTime lastRunAt;
    private String lastRunStatus;   // success / failed
    private Integer runCount;
    private Integer successCount;
    private Integer failCount;
    private Double avgQualityScore;
    private Integer lastResultCount;
    private String lastError;
    private Long userId;

    public boolean isActive() {
        return Boolean.TRUE.equals(isActive);
    }
}
