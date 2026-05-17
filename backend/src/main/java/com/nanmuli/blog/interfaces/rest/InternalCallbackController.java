package com.nanmuli.blog.interfaces.rest;

import com.nanmuli.blog.application.webcollector.WebCollectorAppService;
import com.nanmuli.blog.application.webcollector.WebCollectSourceAppService;
import com.nanmuli.blog.application.webcollector.dto.SourceDTO;
import com.nanmuli.blog.domain.config.ConfigRepository;
import com.nanmuli.blog.domain.webcollector.DigestFingerprint;
import com.nanmuli.blog.domain.webcollector.SourceAuthority;
import com.nanmuli.blog.infrastructure.config.ConfigService;
import com.nanmuli.blog.infrastructure.config.security.AesEncryptor;
import com.nanmuli.blog.infrastructure.persistence.webcollector.DigestFingerprintRepositoryImpl;
import com.nanmuli.blog.infrastructure.persistence.webcollector.SourceAuthorityMapper;
import com.nanmuli.blog.shared.result.Result;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDate;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

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
    private final ConfigRepository configRepository;
    private final AesEncryptor aesEncryptor;
    private final ConfigService configService;
    private final DigestFingerprintRepositoryImpl fingerprintRepository;
    private final SourceAuthorityMapper sourceAuthorityMapper;

    private volatile boolean apiKeyBlankWarned = false;

    /** 认证失败时返回 true，成功时返回 false */
    private boolean authRequired(String callbackKey) {
        String expectedKey = configService.get("crawler.callback.api-key", "");
        if (expectedKey.isBlank()) {
            if (!apiKeyBlankWarned) {
                log.warn("[Auth] crawler.callback.api-key is blank — callback endpoints are unauthenticated");
                apiKeyBlankWarned = true;
            }
            return false;
        }
        apiKeyBlankWarned = false;
        return !expectedKey.equals(callbackKey);
    }

    @PostMapping("/callback")
    public Result<Void> handleCallback(
            @RequestHeader(value = "X-Callback-Key", required = false) String callbackKey,
            @RequestBody Map<String, Object> payload) {

        if (authRequired(callbackKey)) {
            log.warn("[Callback] Unauthorized: requestKey={}", callbackKey);
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
        if (authRequired(callbackKey)) {
            log.warn("[Sources] Unauthorized: requestKey={}", callbackKey);
            return Result.error(403, "Invalid callback key");
        }
        return Result.success(sourceAppService.listActive());
    }

    /**
     * 获取爬虫服务配置（供 Python 服务启动时拉取/刷新）
     */
    @GetMapping("/config")
    public Result<Map<String, String>> getCrawlerConfig(
            @RequestHeader(value = "X-Callback-Key", required = false) String callbackKey) {
        if (authRequired(callbackKey)) {
            log.warn("[Config] Unauthorized: requestKey={}", callbackKey);
            return Result.error(403, "Invalid callback key");
        }

        Map<String, String> configMap = configRepository.findByGroup("crawler").stream()
                .collect(Collectors.toMap(
                        c -> c.getConfigKey().replace("crawler.", ""),
                        c -> {
                            String val = c.getConfigValue() != null ? c.getConfigValue() : "";
                            return Boolean.TRUE.equals(c.getIsEncrypted()) ? aesEncryptor.decrypt(val) : val;
                        },
                        (a, b) -> b,
                        LinkedHashMap::new));

        log.info("[Config] Returning {} crawler configs", configMap.size());
        return Result.success(configMap);
    }

    /**
     * 更新信息源运行状态（供 Python 定时任务完成后回调）
     */
    @PostMapping("/sources/{sourceId}/run-status")
    public Result<Void> updateSourceRunStatus(
            @RequestHeader(value = "X-Callback-Key", required = false) String callbackKey,
            @PathVariable Long sourceId,
            @RequestBody Map<String, Object> payload) {

        if (authRequired(callbackKey)) {
            log.warn("[SourceStatus] Unauthorized: requestKey={}", callbackKey);
            return Result.error(403, "Invalid callback key");
        }

        String status = (String) payload.get("status");
        if (status == null || status.isBlank()) {
            return Result.error(400, "Missing 'status' field");
        }

        String error = (String) payload.get("error");
        Double qualityScore = payload.get("qualityScore") instanceof Number n ? n.doubleValue() : null;
        Integer resultCount = payload.get("resultCount") instanceof Number n ? n.intValue() : null;

        sourceAppService.updateSourceRunStatus(sourceId, status, error, qualityScore, resultCount);
        return Result.success();
    }

    /**
     * 查询最近 N 天的日报去重指纹（供 Python 跨日去重）
     */
    @GetMapping("/digest/fingerprints")
    public Result<List<DigestFingerprint>> getDigestFingerprints(
            @RequestHeader(value = "X-Callback-Key", required = false) String callbackKey,
            @RequestParam(defaultValue = "3") int days) {

        if (authRequired(callbackKey)) {
            return Result.error(403, "Invalid callback key");
        }

        LocalDate since = LocalDate.now().minusDays(days);
        List<DigestFingerprint> fingerprints = fingerprintRepository.findByDigestDateAfter(since);
        return Result.success(fingerprints);
    }

    /**
     * 批量保存日报去重指纹（供 Python 日报生成完成后回调）
     */
    @PostMapping("/digest/fingerprints")
    public Result<Void> saveDigestFingerprints(
            @RequestHeader(value = "X-Callback-Key", required = false) String callbackKey,
            @RequestBody List<Map<String, Object>> payload) {

        if (authRequired(callbackKey)) {
            return Result.error(403, "Invalid callback key");
        }

        List<DigestFingerprint> fingerprints = payload.stream().map(m -> {
            DigestFingerprint fp = new DigestFingerprint();
            fp.setTaskId(m.get("taskId") instanceof Number n ? n.longValue() : null);
            fp.setUrlHash((String) m.getOrDefault("urlHash", ""));
            fp.setUrl((String) m.getOrDefault("url", ""));
            fp.setTitle((String) m.getOrDefault("title", ""));
            fp.setSimhash(m.get("simhash") instanceof Number n ? n.longValue() : null);
            String dateStr = (String) m.getOrDefault("digestDate", "");
            if (!dateStr.isBlank()) {
                fp.setDigestDate(LocalDate.parse(dateStr));
            }
            return fp;
        }).toList();

        fingerprintRepository.saveAll(fingerprints);
        log.info("[Fingerprints] Saved {} digest fingerprints", fingerprints.size());
        return Result.success();
    }

    /**
     * 查询来源可信度（供 Python 评分时优先查库）
     */
    @GetMapping("/source-authority")
    public Result<SourceAuthority> getSourceAuthority(
            @RequestHeader(value = "X-Callback-Key", required = false) String callbackKey,
            @RequestParam String domain) {

        if (authRequired(callbackKey)) {
            return Result.error(403, "Invalid callback key");
        }

        com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper<SourceAuthority> wrapper =
                new com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper<>();
        wrapper.eq(SourceAuthority::getDomain, domain)
               .eq(SourceAuthority::getIsActive, true)
               .eq(SourceAuthority::getIsDeleted, false)
               .last("LIMIT 1");
        SourceAuthority authority = sourceAuthorityMapper.selectOne(wrapper);
        if (authority == null) {
            return Result.success();
        }
        return Result.success(authority);
    }

    /**
     * 批量获取所有活跃来源可信度（供 Python 预热缓存）
     */
    @GetMapping("/source-authority/all")
    public Result<List<SourceAuthority>> getAllSourceAuthorities(
            @RequestHeader(value = "X-Callback-Key", required = false) String callbackKey) {

        if (authRequired(callbackKey)) {
            return Result.error(403, "Invalid callback key");
        }

        com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper<SourceAuthority> wrapper =
                new com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper<>();
        wrapper.eq(SourceAuthority::getIsActive, true)
               .eq(SourceAuthority::getIsDeleted, false);
        return Result.success(sourceAuthorityMapper.selectList(wrapper));
    }
}
