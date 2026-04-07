package com.nanmuli.blog.interfaces.rest;

import com.nanmuli.blog.application.webcollector.WebCollectorAppService;
import com.nanmuli.blog.application.webcollector.command.CreateCollectTaskCommand;
import com.nanmuli.blog.application.webcollector.dto.CollectPageDTO;
import com.nanmuli.blog.application.webcollector.dto.CollectTaskDTO;
import com.nanmuli.blog.application.webcollector.dto.CollectTaskListDTO;
import com.nanmuli.blog.application.webcollector.query.CollectTaskPageQuery;
import com.nanmuli.blog.shared.result.PageResult;
import com.nanmuli.blog.shared.result.Result;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;

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
@RequiredArgsConstructor
public class WebCollectorController {

    private final WebCollectorAppService collectorAppService;

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

    private Long getCurrentUserId() {
        try {
            return cn.dev33.satoken.stp.StpUtil.getLoginIdAsLong();
        } catch (Exception e) {
            log.warn("无法获取当前登录用户，使用默认用户ID=1");
            return 1L;
        }
    }
}
