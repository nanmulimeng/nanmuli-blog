package com.nanmuli.blog.interfaces.rest;

import com.nanmuli.blog.application.config.ConfigAppService;
import com.nanmuli.blog.application.config.dto.ConfigDTO;
import com.nanmuli.blog.shared.result.Result;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

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

    @GetMapping("/admin/config/{key}")
    public Result<ConfigDTO> getByKey(@PathVariable String key) {
        return Result.success(configAppService.getByKey(key));
    }

    @PutMapping("/admin/config/{key}")
    public Result<Void> update(@PathVariable String key, @RequestBody Map<String, String> body) {
        configAppService.update(key, body.get("value"));
        return Result.success();
    }
}
