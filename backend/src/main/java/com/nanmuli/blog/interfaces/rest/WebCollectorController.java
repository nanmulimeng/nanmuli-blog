package com.nanmuli.blog.interfaces.rest;

import com.nanmuli.blog.application.webcollector.WebCollectorAppService;
import com.nanmuli.blog.application.webcollector.command.ConvertToArticleCommand;
import com.nanmuli.blog.application.webcollector.command.ConvertToDailyLogCommand;
import com.nanmuli.blog.application.webcollector.command.CreateCollectTaskCommand;
import com.nanmuli.blog.application.webcollector.dto.CollectPageDTO;
import com.nanmuli.blog.application.webcollector.dto.CollectTaskDTO;
import com.nanmuli.blog.application.webcollector.dto.CollectTaskListDTO;
import com.nanmuli.blog.application.webcollector.query.CollectTaskPageQuery;
import com.nanmuli.blog.shared.exception.BusinessException;
import com.nanmuli.blog.shared.result.PageResult;
import com.nanmuli.blog.shared.result.Result;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.*;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.client.RestTemplate;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Web Collector REST 控制器
 */
@Slf4j
@Tag(name = "内容采集管理")
@RestController
@RequestMapping("/api/admin/collector")
public class WebCollectorController {

    private final WebCollectorAppService collectorAppService;

    @Value("${crawler.service.base-url:http://localhost:8500}")
    private String crawlerBaseUrl;

    private final RestTemplate digestRestTemplate;

    public WebCollectorController(WebCollectorAppService collectorAppService) {
        this.collectorAppService = collectorAppService;
        var factory = new org.springframework.http.client.SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(java.time.Duration.ofSeconds(5));
        factory.setReadTimeout(java.time.Duration.ofSeconds(30));
        this.digestRestTemplate = new RestTemplate(factory);
    }

    /**
     * 提交采集任务
     */
    @Operation(summary = "提交采集任务")
    @PostMapping("/task")
    public Result<Map<String, Object>> createTask(@Valid @RequestBody CreateCollectTaskCommand command) {
        Long userId = getCurrentUserId();
        Long taskId = collectorAppService.createTask(command, userId);

        Map<String, Object> data = new HashMap<>();
        data.put("taskId", String.valueOf(taskId));
        data.put("status", 0);
        data.put("message", "任务已创建，正在处理中");

        return Result.success(data);
    }

    /**
     * 查询任务详情
     */
    @Operation(summary = "查询任务详情")
    @GetMapping("/task/{taskId}")
    public Result<CollectTaskDTO> getTask(
            @Parameter(description = "任务ID") @PathVariable Long taskId) {
        Long userId = getCurrentUserId();
        CollectTaskDTO dto = collectorAppService.getTask(taskId, userId);
        return Result.success(dto);
    }

    /**
     * 查询任务列表
     */
    @Operation(summary = "查询任务列表")
    @GetMapping("/task/list")
    public Result<PageResult<CollectTaskListDTO>> listTasks(CollectTaskPageQuery query) {
        Long userId = getCurrentUserId();
        PageResult<CollectTaskListDTO> result = collectorAppService.listTasks(query, userId);
        return Result.success(result);
    }

    /**
     * 查询任务页面列表
     */
    @Operation(summary = "查询任务页面列表")
    @GetMapping("/task/{taskId}/pages")
    public Result<List<CollectPageDTO>> listTaskPages(
            @Parameter(description = "任务ID") @PathVariable Long taskId) {
        Long userId = getCurrentUserId();
        List<CollectPageDTO> pages = collectorAppService.listTaskPages(taskId, userId);
        return Result.success(pages);
    }

    /**
     * 删除任务
     */
    @Operation(summary = "删除任务")
    @DeleteMapping("/task/{taskId}")
    public Result<Void> deleteTask(
            @Parameter(description = "任务ID") @PathVariable Long taskId) {
        Long userId = getCurrentUserId();
        collectorAppService.deleteTask(taskId, userId);
        return Result.success();
    }

    /**
     * 将采集任务转为文章草稿
     */
    @Operation(summary = "转为文章草稿")
    @PostMapping("/task/{taskId}/to-article")
    public Result<String> convertToArticle(
            @Parameter(description = "任务ID") @PathVariable Long taskId,
            @RequestBody @Valid ConvertToArticleCommand command) {
        Long userId = getCurrentUserId();
        Long articleId = collectorAppService.convertToArticle(taskId, command, userId);
        return Result.success(String.valueOf(articleId));
    }

    /**
     * 将采集任务转为技术日志
     */
    @Operation(summary = "转为技术日志")
    @PostMapping("/task/{taskId}/to-daily-log")
    public Result<String> convertToDailyLog(
            @Parameter(description = "任务ID") @PathVariable Long taskId,
            @RequestBody @Valid ConvertToDailyLogCommand command) {
        Long userId = getCurrentUserId();
        Long dailyLogId = collectorAppService.convertToDailyLog(taskId, command, userId);
        return Result.success(String.valueOf(dailyLogId));
    }

    /**
     * 爬虫服务健康检查
     */
    @Operation(summary = "爬虫服务健康检查")
    @GetMapping("/crawler/health")
    public Result<Map<String, Object>> crawlerHealth() {
        boolean available = collectorAppService.isCrawlerAvailable();
        Map<String, Object> data = new HashMap<>();
        data.put("available", available);
        data.put("service", "crawl4ai");
        return Result.success(data);
    }

    /**
     * 重试失败的任务
     */
    @Operation(summary = "重试失败的任务")
    @PostMapping("/task/{taskId}/retry")
    public Result<String> retryTask(
            @Parameter(description = "任务ID") @PathVariable Long taskId) {
        Long userId = getCurrentUserId();
        Long retriedId = collectorAppService.retryTask(taskId, userId);
        return Result.success(String.valueOf(retriedId));
    }

    private Long getCurrentUserId() {
        return cn.dev33.satoken.stp.StpUtil.getLoginIdAsLong();
    }

    // ============== Digest Proxy ==============

    /**
     * 日报列表（代理 Python /api/v1/digests）
     */
    @Operation(summary = "日报列表")
    @GetMapping("/digest")
    public Result<Object> listDigests(
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "10") int size) {
        String url = crawlerBaseUrl + "/api/v1/digests?page=" + page + "&size=" + size;
        return Result.success(proxyGet(url));
    }

    /**
     * 最近一期日报
     */
    @Operation(summary = "最近一期日报")
    @GetMapping("/digest/latest")
    public Result<Object> getLatestDigest() {
        String url = crawlerBaseUrl + "/api/v1/digests/latest";
        return Result.success(proxyGet(url));
    }

    /**
     * 按日期查询日报
     */
    @Operation(summary = "按日期查询日报")
    @GetMapping("/digest/{date}")
    public Result<Object> getDigestByDate(@PathVariable String date) {
        String url = crawlerBaseUrl + "/api/v1/digests/" + date;
        return Result.success(proxyGet(url));
    }

    /**
     * 手动触发日报生成
     */
    @Operation(summary = "手动触发日报生成")
    @PostMapping("/digest/trigger")
    public Result<Object> triggerDigest(@RequestParam(defaultValue = "false") boolean force) {
        String url = crawlerBaseUrl + "/api/v1/digests/trigger?force=" + force;
        try {
            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.APPLICATION_JSON);
            HttpEntity<Void> entity = new HttpEntity<>(headers);
            ResponseEntity<Object> response = digestRestTemplate.postForEntity(url, entity, Object.class);
            return Result.success(response.getBody());
        } catch (Exception e) {
            log.warn("[DigestProxy] Trigger failed: {}", e.getMessage());
            throw new BusinessException(503, "Python 爬虫服务不可用: " + e.getMessage());
        }
    }

    /**
     * 获取调度器状态
     */
    @Operation(summary = "获取日报调度器状态")
    @GetMapping("/digest/scheduler/status")
    public Result<Object> getDigestSchedulerStatus() {
        String url = crawlerBaseUrl + "/api/v1/digests/scheduler/status";
        return Result.success(proxyGet(url));
    }

    /**
     * 获取日报板块配置
     */
    @Operation(summary = "获取日报板块配置")
    @GetMapping("/digest/config/sections")
    public Result<Object> getDigestSectionConfig() {
        String url = crawlerBaseUrl + "/api/v1/digests/config/sections";
        return Result.success(proxyGet(url));
    }

    private Object proxyGet(String url) {
        try {
            ResponseEntity<Object> response = digestRestTemplate.getForEntity(url, Object.class);
            return response.getBody();
        } catch (Exception e) {
            log.warn("[DigestProxy] Proxy GET failed: {} - {}", url, e.getMessage());
            throw new BusinessException(503, "Python 爬虫服务不可用: " + e.getMessage());
        }
    }
}
