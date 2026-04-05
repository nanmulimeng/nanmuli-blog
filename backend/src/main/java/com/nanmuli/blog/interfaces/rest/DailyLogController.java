package com.nanmuli.blog.interfaces.rest;

import com.nanmuli.blog.application.dailylog.DailyLogAppService;
import com.nanmuli.blog.application.dailylog.command.CreateDailyLogCommand;
import com.nanmuli.blog.application.dailylog.dto.DailyLogDTO;
import com.nanmuli.blog.shared.result.PageResult;
import com.nanmuli.blog.shared.result.Result;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

@Tag(name = "技术日志")
@RestController
@RequestMapping("/api")
@RequiredArgsConstructor
public class DailyLogController {

    private final DailyLogAppService dailyLogAppService;

    @GetMapping("/daily-log/list")
    public Result<PageResult<DailyLogDTO>> list(
            @RequestParam(defaultValue = "1") int current,
            @RequestParam(defaultValue = "10") int size) {
        return Result.success(dailyLogAppService.listPublicPage(current, size));
    }

    @GetMapping("/daily-log/{id}")
    public Result<DailyLogDTO> detail(@PathVariable Long id) {
        return Result.success(dailyLogAppService.getPublicById(id));
    }

    @PostMapping("/admin/daily-log")
    public Result<Long> create(@Valid @RequestBody CreateDailyLogCommand command) {
        return Result.success(dailyLogAppService.create(command));
    }

    @PutMapping("/admin/daily-log/{id}")
    public Result<Void> update(@PathVariable Long id, @Valid @RequestBody CreateDailyLogCommand command) {
        dailyLogAppService.update(id, command);
        return Result.success();
    }

    @DeleteMapping("/admin/daily-log/{id}")
    public Result<Void> delete(@PathVariable Long id) {
        dailyLogAppService.delete(id);
        return Result.success();
    }

    @GetMapping("/admin/daily-log/list")
    public Result<PageResult<DailyLogDTO>> adminList(
            @RequestParam(defaultValue = "1") int current,
            @RequestParam(defaultValue = "10") int size) {
        return Result.success(dailyLogAppService.listPage(current, size));
    }

    @GetMapping("/admin/daily-log/{id}")
    public Result<DailyLogDTO> adminDetail(@PathVariable Long id) {
        return Result.success(dailyLogAppService.getById(id));
    }
}
