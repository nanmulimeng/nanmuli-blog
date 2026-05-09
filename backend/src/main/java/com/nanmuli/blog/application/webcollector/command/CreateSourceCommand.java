package com.nanmuli.blog.application.webcollector.command;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import lombok.Data;

@Data
public class CreateSourceCommand {

    @NotBlank(message = "名称不能为空")
    @Size(max = 200, message = "名称长度不能超过200字符")
    private String name;

    @NotBlank(message = "类型不能为空")
    @Pattern(regexp = "^(url|keyword|rss)$", message = "类型必须为 url/keyword/rss")
    private String type;

    @NotBlank(message = "值不能为空")
    @Size(max = 2048, message = "值长度不能超过2048字符")
    private String value;

    private String contentCategory;
    private String crawlMode;
    private Integer maxDepth;
    private Integer maxPages;
    private String cssSelector;
    private String aiTemplate;
    private String scheduleCron;
    private Integer freshnessHours;
}
