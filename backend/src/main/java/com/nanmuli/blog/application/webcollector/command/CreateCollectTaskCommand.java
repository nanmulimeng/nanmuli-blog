package com.nanmuli.blog.application.webcollector.command;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import lombok.Data;

/**
 * 创建采集任务命令
 */
@Data
public class CreateCollectTaskCommand {

    @NotBlank(message = "任务类型不能为空")
    @Pattern(regexp = "^(single|deep|keyword|digest)$", message = "任务类型必须是 single、deep、keyword 或 digest")
    private String taskType;

    @Size(max = 2048, message = "URL 长度不能超过 2048")
    private String sourceUrl;

    @Size(max = 500, message = "关键词长度不能超过 500")
    private String keyword;

    @Pattern(regexp = "^(sogou|bing|baidu|google)?$", message = "搜索引擎必须是 sogou、bing、baidu 或 google")
    private String searchEngine = "bing";

    @Pattern(regexp = "^(single|deep)?$", message = "爬取模式必须是 single 或 deep")
    private String crawlMode = "single";

    @Min(value = 1, message = "深度最小为 1")
    @Max(value = 3, message = "深度最大为 3")
    private Integer maxDepth = 1;

    @Min(value = 1, message = "最大页面数最小为 1")
    @Max(value = 20, message = "最大页面数最大为 20")
    private Integer maxPages = 10;

    @Size(max = 50, message = "AI 模板长度不能超过 50")
    private String aiTemplate = "tech_summary";

    @Pattern(regexp = "^(day|week|month|year|all)?$", message = "时间范围必须是 day、week、month、year 或 all")
    private String timeRange = "week";

    public boolean isValid() {
        if ("single".equals(taskType) || "deep".equals(taskType)) {
            return sourceUrl != null && !sourceUrl.isBlank();
        }
        if ("keyword".equals(taskType)) {
            return keyword != null && !keyword.isBlank();
        }
        // digest 类型通过 /digest/trigger 端点触发，不走 createTask
        return true;
    }
}
