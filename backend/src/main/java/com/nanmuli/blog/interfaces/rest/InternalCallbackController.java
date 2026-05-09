package com.nanmuli.blog.interfaces.rest;

import com.nanmuli.blog.application.webcollector.WebCollectorAppService;
import com.nanmuli.blog.application.webcollector.WebCollectSourceAppService;
import com.nanmuli.blog.application.webcollector.dto.SourceDTO;
import com.nanmuli.blog.shared.result.Result;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/**
 * 内部端点（供 Python 爬虫服务调用，不走 Sa-Token 认证）
 */
@Slf4j
@RestController
@RequestMapping("/api/internal/collector")
@RequiredArgsConstructor
public class InternalCallbackController {

    private final WebCollectorAppService collectorAppService;
    private final WebCollectSourceAppService sourceAppService;

    @Value("${crawler.callback.api-key:}")
    private String callbackApiKey;

    @PostMapping("/callback")
    public Result<Void> handleCallback(
            @RequestHeader(value = "X-Callback-Key", required = false) String callbackKey,
            @RequestBody Map<String, Object> payload) {

        if (callbackApiKey == null || callbackApiKey.isBlank() || !callbackApiKey.equals(callbackKey)) {
            log.warn("[Callback] Unauthorized: apiKey is {}configured, requestKey={}",
                    (callbackApiKey == null || callbackApiKey.isBlank()) ? "not " : "", callbackKey);
            return Result.error(403, "Invalid callback key");
        }

        Object pythonTaskIdObj = payload.get("python_task_id");
        if (!(pythonTaskIdObj instanceof Number num)) {
            return Result.error(400, "Missing or invalid python_task_id");
        }

        int pythonTaskId = num.intValue();
        log.info("[Callback] Received: pythonTaskId={}, status={}", pythonTaskId, payload.get("status"));

        collectorAppService.handleCallback(pythonTaskId);
        return Result.success();
    }

    /**
     * 获取活跃订阅源列表（供 Python 日报构建 section 配置）
     */
    @GetMapping("/sources")
    public Result<List<SourceDTO>> listActiveSources(
            @RequestHeader(value = "X-Callback-Key", required = false) String callbackKey) {
        if (callbackApiKey == null || callbackApiKey.isBlank() || !callbackApiKey.equals(callbackKey)) {
            log.warn("[Sources] Unauthorized: apiKey is {}configured, requestKey={}",
                    (callbackApiKey == null || callbackApiKey.isBlank()) ? "not " : "", callbackKey);
            return Result.error(403, "Invalid callback key");
        }
        return Result.success(sourceAppService.listActive());
    }
}
