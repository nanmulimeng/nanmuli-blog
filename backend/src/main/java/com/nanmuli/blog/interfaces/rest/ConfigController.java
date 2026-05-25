package com.nanmuli.blog.interfaces.rest;

import com.nanmuli.blog.application.config.ConfigAppService;
import com.nanmuli.blog.application.config.command.CreateConfigCommand;
import com.nanmuli.blog.application.config.command.UpdateConfigCommand;
import com.nanmuli.blog.application.config.dto.ConfigDTO;
import com.nanmuli.blog.infrastructure.config.ConfigService;
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
    private final ConfigService configService;
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

        if (key.startsWith("crawler.")) {
            // 1. 先用旧 ConfigService 通知 Python（避免 callback key 变更后认证死锁）
            crawlerTaskClient.reloadPool();
            crawlerTaskClient.refreshConfig();

            // 2. 再刷新 Java ConfigService（Java 侧开始使用新值）
            configService.reload();

            // 3. 用新 ConfigService 重建连接池（后续请求使用新地址/密钥）
            crawlerTaskClient.reloadPool();
        } else {
            configService.reload();
        }

        return Result.success();
    }

    @PostMapping("/admin/config/{key}")
    public Result<Void> create(@PathVariable String key,
                               @Valid @RequestBody CreateConfigCommand command) {
        configAppService.set(key, command.getValue(), command.getDescription(),
                command.getGroupName(), command.getInputType(), command.getIsPublic());

        if (key.startsWith("crawler.")) {
            crawlerTaskClient.reloadPool();
            crawlerTaskClient.refreshConfig();
            configService.reload();
            crawlerTaskClient.reloadPool();
        } else {
            configService.reload();
        }

        return Result.success();
    }

    @PostMapping("/admin/config/refresh")
    public Result<Map<String, Object>> refreshAll() {
        log.info("[ConfigRefresh] Triggered by admin");
        configAppService.refreshCache();
        // 全局刷新同样：先通知 Python，再刷新 Java
        crawlerTaskClient.refreshConfig();
        configService.reload();
        crawlerTaskClient.reloadPool();
        return Result.success(Map.of(
                "message", "所有配置已刷新",
                "components", List.of("Spring Cache", "Python Crawler", "ConfigService", "CrawlerTaskClient Pool")
        ));
    }

}
