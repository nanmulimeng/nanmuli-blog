package com.nanmuli.blog.application.webcollector.command;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import lombok.Data;

@Data
public class UpdateSourceCommand {

    @NotBlank(message = "名称不能为空")
    @Size(max = 200, message = "名称长度不能超过200字符")
    private String name;

    @NotBlank(message = "类型不能为空")
    @Pattern(regexp = "^(url|keyword|rss)$", message = "类型必须为 url/keyword/rss")
    private String type;

    @NotBlank(message = "值不能为空")
    @Size(max = 2048, message = "值长度不能超过2048字符")
    private String value;

    @Pattern(regexp = "^(hot_trend|open_source|tech_article|dev_tool|creative|paper)?$", message = "内容分类无效")
    private String contentCategory;

    @Pattern(regexp = "^(single|deep)?$", message = "爬取模式必须为 single/deep")
    private String crawlMode;
    private Integer maxDepth;
    private Integer maxPages;
    private String cssSelector;

    @Pattern(regexp = "^(tech_summary|tutorial|comparison|knowledge_report|daily_digest)?$", message = "AI模板无效")
    private String aiTemplate;

    private String scheduleCron;
    private Integer freshnessHours;
    private Boolean isActive;
}
