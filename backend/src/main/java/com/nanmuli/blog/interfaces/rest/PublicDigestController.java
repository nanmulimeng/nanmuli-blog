package com.nanmuli.blog.interfaces.rest;

import com.nanmuli.blog.infrastructure.crawler.CrawlerTaskClient;
import com.nanmuli.blog.shared.exception.BusinessException;
import com.nanmuli.blog.shared.result.Result;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.constraints.Pattern;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;

/**
 * 公开日报接口（无需登录）
 */
@Slf4j
@Tag(name = "技术日报（公开）")
@RestController
@RequestMapping("/api/digest")
@RequiredArgsConstructor
@Validated
public class PublicDigestController {

    private final CrawlerTaskClient crawlerTaskClient;

    @Operation(summary = "日报列表")
    @GetMapping
    public Result<Object> listDigests(
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "10") int size) {
        if (size < 1 || size > 50) size = 10;
        if (page < 1) page = 1;
        try {
            return Result.success(crawlerTaskClient.proxyGet("/api/v1/digests?page=" + page + "&size=" + size));
        } catch (Exception e) {
            log.warn("[DigestProxy] listDigests failed: {}", e.getMessage());
            throw new BusinessException(503, "服务暂时不可用");
        }
    }

    @Operation(summary = "最近一期日报")
    @GetMapping("/latest")
    public Result<Object> getLatestDigest() {
        try {
            return Result.success(crawlerTaskClient.proxyGet("/api/v1/digests/latest"));
        } catch (Exception e) {
            log.warn("[DigestProxy] getLatestDigest failed: {}", e.getMessage());
            throw new BusinessException(503, "服务暂时不可用");
        }
    }

    @Operation(summary = "按日期查询日报")
    @GetMapping("/{date}")
    public Result<Object> getDigestByDate(
            @PathVariable @Pattern(regexp = "^\\d{4}-\\d{2}-\\d{2}$", message = "日期格式不正确") String date) {
        try {
            return Result.success(crawlerTaskClient.proxyGet("/api/v1/digests/" + date));
        } catch (Exception e) {
            log.warn("[DigestProxy] getDigestByDate({}) failed: {}", date, e.getMessage());
            throw new BusinessException(503, "服务暂时不可用");
        }
    }
}
