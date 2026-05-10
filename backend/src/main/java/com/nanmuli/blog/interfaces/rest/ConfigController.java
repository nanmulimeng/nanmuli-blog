package com.nanmuli.blog.interfaces.rest;

import com.nanmuli.blog.application.config.ConfigAppService;
import com.nanmuli.blog.application.config.command.UpdateConfigCommand;
import com.nanmuli.blog.application.config.dto.ConfigDTO;
import com.nanmuli.blog.infrastructure.crawler.CrawlerTaskClient;
import com.nanmuli.blog.shared.result.Result;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@Slf4j
@Tag(name = "系统配置")
@RestController
@RequestMapping("/api")
@RequiredArgsConstructor
public class ConfigController {

    private final ConfigAppService configAppService;
    private final CrawlerTaskClient crawlerTaskClient;

    @GetMapping("/config/public")
    public Result<Map<String, String>> publicConfigs() {
        return Result.success(configAppService.getPublicConfigs());
    }

    @GetMapping("/config/list")
    public Result<List<ConfigDTO>> listConfigs() {
        return Result.success(configAppService.getPublicConfigsForList());
    }

    @GetMapping("/admin/config/list")
    public Result<List<ConfigDTO>> listAllConfigs() {
        return Result.success(configAppService.getAllConfigsForAdmin());
    }

    @GetMapping("/admin/config/{key}")
    public Result<ConfigDTO> getByKey(@PathVariable String key) {
        return Result.success(configAppService.getByKey(key));
    }

    @PutMapping("/admin/config/{key}")
    public Result<Void> update(@PathVariable String key,
                               @Valid @RequestBody UpdateConfigCommand command) {
        configAppService.update(key, command.getValue());

        // 如果修改的是爬虫相关配置，通知 Python 服务刷新
        if (key.startsWith("crawler.")) {
            crawlerTaskClient.refreshConfig();
        }

        return Result.success();
    }
}
