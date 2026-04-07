package com.nanmuli.blog.domain.webcollector;

import com.baomidou.mybatisplus.annotation.TableName;
import com.nanmuli.blog.shared.domain.BaseAggregateRoot;
import lombok.EqualsAndHashCode;
import lombok.Getter;
import lombok.Setter;

import java.time.LocalDateTime;

/**
 * 订阅源聚合根实体
 */
@Getter
@Setter
@EqualsAndHashCode(callSuper = false)
@TableName("web_collect_source")
public class WebCollectSource extends BaseAggregateRoot<Long> {
    private static final long serialVersionUID = 1L;

    // 基本信息
    private String name;
    private String type; // url / keyword / rss
    private String value; // URL / 关键词 / RSS地址

    // 内容分类
    private String contentCategory; // hot_trend / open_source / tech_article / dev_tool / creative

    // 爬取配置
    private String crawlMode;
    private Integer maxDepth;
    private Integer maxPages;
    private String cssSelector;
    private String aiTemplate;

    // 调度配置
    private String scheduleCron;
    private Integer freshnessHours;

    // 状态
    private Boolean isActive;
    private LocalDateTime lastRunAt;
    private String lastRunStatus;
    private Integer runCount;

    // 审计
    private Long userId;

    // 领域方法

    public ContentCategory getContentCategoryEnum() {
        return ContentCategory.of(this.contentCategory);
    }

    public AiTemplate getAiTemplateEnum() {
        return AiTemplate.of(this.aiTemplate);
    }

    public boolean shouldRun() {
        if (!isActive) {
            return false;
        }
        // 如果没有配置 cron，只能手动触发
        if (scheduleCron == null || scheduleCron.isBlank()) {
            return false;
        }
        // TODO: 检查 cron 表达式是否到期
        return true;
    }

    public void markRun(String status) {
        this.lastRunAt = LocalDateTime.now();
        this.lastRunStatus = status;
        if ("success".equals(status)) {
            this.runCount = (this.runCount == null ? 0 : this.runCount) + 1;
        }
    }

    public void enable() {
        this.isActive = true;
    }

    public void disable() {
        this.isActive = false;
    }
}
