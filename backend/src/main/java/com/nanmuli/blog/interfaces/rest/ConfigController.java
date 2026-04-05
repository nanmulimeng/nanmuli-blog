package com.nanmuli.blog.interfaces.rest;

import com.nanmuli.blog.application.config.ConfigAppService;
import com.nanmuli.blog.application.config.command.UpdateConfigCommand;
import com.nanmuli.blog.application.config.dto.ConfigDTO;
import com.nanmuli.blog.shared.result.Result;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@Tag(name = "系统配置")
@RestController
@RequestMapping("/api")
@RequiredArgsConstructor
public class ConfigController {

    private final ConfigAppService configAppService;

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
        return Result.success();
    }
}
