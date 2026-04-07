package com.nanmuli.blog.application.webcollector.command;

import jakarta.validation.constraints.*;
import lombok.Data;

/**
 * 创建采集任务命令
 */
@Data
public class CreateCollectTaskCommand {

    @NotBlank(message = "任务类型不能为空")
    @Pattern(regexp = "^(single|deep|keyword)$", message = "任务类型必须是 single、deep 或 keyword")
    private String taskType;

    // URL（single/deep 模式必填）
    @Size(max = 2048, message = "URL 长度不能超过 2048")
    private String sourceUrl;

    // 关键词（keyword 模式必填）
    @Size(max = 500, message = "关键词长度不能超过 500")
    private String keyword;

    // 搜索引擎（keyword 模式可选，默认 bing）
    @Pattern(regexp = "^(bing|duckduckgo)?$", message = "搜索引擎必须是 bing 或 duckduckgo")
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

    // 校验：single/deep 模式必须提供 URL
    public boolean isValid() {
        if ("single".equals(taskType) || "deep".equals(taskType)) {
            return sourceUrl != null && !sourceUrl.isBlank();
        }
        if ("keyword".equals(taskType)) {
            return keyword != null && !keyword.isBlank();
        }
        return true;
    }
}
