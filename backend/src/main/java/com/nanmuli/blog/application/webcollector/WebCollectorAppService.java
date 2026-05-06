package com.nanmuli.blog.application.webcollector;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.nanmuli.blog.application.article.ArticleAppService;
import com.nanmuli.blog.application.article.command.CreateArticleCommand;
import com.nanmuli.blog.application.dailylog.DailyLogAppService;
import com.nanmuli.blog.application.dailylog.command.CreateDailyLogCommand;
import com.nanmuli.blog.application.webcollector.command.ConvertToArticleCommand;
import com.nanmuli.blog.application.webcollector.command.ConvertToDailyLogCommand;
import com.nanmuli.blog.application.webcollector.command.CreateCollectTaskCommand;
import com.nanmuli.blog.application.webcollector.dto.CollectPageDTO;
import com.nanmuli.blog.application.webcollector.dto.CollectTaskDTO;
import com.nanmuli.blog.application.webcollector.dto.CollectTaskListDTO;
import com.nanmuli.blog.application.webcollector.query.CollectTaskPageQuery;
import com.nanmuli.blog.domain.webcollector.*;
import com.nanmuli.blog.infrastructure.crawler.CrawlerService;
import com.nanmuli.blog.shared.exception.BusinessException;
import com.nanmuli.blog.shared.result.PageResult;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.BeanUtils;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.LocalDate;
import java.util.*;

/**
 * Web Collector 应用服务
 */
@Slf4j
@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class WebCollectorAppService {

    private final WebCollectTaskRepository taskRepository;
    private final WebCollectPageRepository pageRepository;
    private final WebCollectorAsyncExecutor asyncExecutor;
    private final ArticleAppService articleAppService;
    private final DailyLogAppService dailyLogAppService;
    private final CrawlerService crawlerService;
    private final ObjectMapper objectMapper;

    /**
     * 创建采集任务
     */
    @Transactional
    public Long createTask(CreateCollectTaskCommand command, Long userId) {
        log.info("[CreateTask] type={}, userId={}", command.getTaskType(), userId);

        if (!command.isValid()) {
            throw new BusinessException("请求参数错误：URL 或关键词不能为空");
        }

        // Level 1 去重：检查 URL 是否在 30 天内已被爬取（仅 single/deep 模式）
        if (("single".equals(command.getTaskType()) || "deep".equals(command.getTaskType()))
                && command.getSourceUrl() != null) {
            String urlHash = hashUrl(command.getSourceUrl());
            if (pageRepository.existsByUrlHash(urlHash)) {
                throw new BusinessException("该 URL 在 30 天内已被采集过，请勿重复提交");
            }
        }

        // 创建任务实体
        WebCollectTask task = new WebCollectTask();
        task.setUserId(userId);
        task.setTaskType(command.getTaskType());
        task.setSourceUrl(command.getSourceUrl());
        task.setKeyword(command.getKeyword());
        task.setSearchEngine(command.getSearchEngine());
        task.setCrawlMode(command.getCrawlMode());
        task.setMaxDepth(command.getMaxDepth());
        task.setMaxPages(command.getMaxPages());
        task.setTimeRange(command.getTimeRange());
        task.setAiTemplate(command.getAiTemplate());
        task.setTriggerType("manual");
        task.updateStatus(CollectTaskStatus.PENDING);
        task.setTotalPages(switch (command.getTaskType()) {
            case "deep" -> command.getMaxPages() != null ? command.getMaxPages() : 10;
            case "keyword" -> command.getMaxPages() != null ? command.getMaxPages() : 10;
            default -> 1;
        });
        task.setCompletedPages(0);

        taskRepository.save(task);

        // 事务提交后再触发异步爬取，避免异步线程读不到未提交的数据
        final Long taskId = task.getId();
        log.info("[CreateTask] Registering afterCommit hook for taskId={}", taskId);
        TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
            @Override
            public void afterCommit() {
                log.info("[CreateTask] Transaction committed, triggering async crawl for taskId={}", taskId);
                asyncExecutor.executeCrawlAsync(taskId);
            }

            @Override
            public void afterCompletion(int status) {
                if (status != STATUS_COMMITTED) {
                    log.warn("[CreateTask] Transaction completed with status={}, taskId={}", status, taskId);
                }
            }
        });

        return task.getId();
    }

    /**
     * 查询任务详情
     */
    public CollectTaskDTO getTask(Long taskId, Long userId) {
        WebCollectTask task = taskRepository.findById(taskId)
                .orElseThrow(() -> new BusinessException("任务不存在"));

        if (!task.getUserId().equals(userId)) {
            throw new BusinessException("无权访问此任务");
        }

        return convertToDTO(task);
    }

    /**
     * 分页查询任务列表
     */
    public PageResult<CollectTaskListDTO> listTasks(CollectTaskPageQuery query, Long userId) {
        IPage<WebCollectTask> page = new Page<>(query.getCurrent(), query.getSize());

        IPage<WebCollectTask> result = taskRepository.findPageFiltered(
                page, userId, query.getStatus(), query.getTaskType(), query.getKeyword());

        List<CollectTaskListDTO> records = result.getRecords().stream()
                .map(this::convertToListDTO)
                .toList();

        return new PageResult<>(result.getTotal(), result.getCurrent(), result.getSize(), records);
    }

    /**
     * 查询任务的页面列表
     */
    public List<CollectPageDTO> listTaskPages(Long taskId, Long userId) {
        WebCollectTask task = taskRepository.findById(taskId)
                .orElseThrow(() -> new BusinessException("任务不存在"));

        if (!task.getUserId().equals(userId)) {
            throw new BusinessException("无权访问此任务");
        }

        return pageRepository.findByTaskIdOrderBySortOrder(taskId).stream()
                .map(this::convertToPageDTO)
                .toList();
    }

    /**
     * 删除任务（级联清理关联的页面数据）
     */
    @Transactional
    public void deleteTask(Long taskId, Long userId) {
        WebCollectTask task = taskRepository.findById(taskId)
                .orElseThrow(() -> new BusinessException("任务不存在"));

        if (!task.getUserId().equals(userId)) {
            throw new BusinessException("无权删除此任务");
        }

        // PENDING 任务可删除（尚未开始爬取），CRAWLING/PROCESSING 禁止删除
        if (task.getStatus() == CollectTaskStatus.CRAWLING.getValue()
                || task.getStatus() == CollectTaskStatus.PROCESSING.getValue()) {
            throw new BusinessException("任务正在处理中，无法删除，请等待完成后再试");
        }

        // 先清理关联的页面数据（物理删除，非逻辑删除）
        pageRepository.deleteByTaskId(taskId);

        // 再逻辑删除任务（@Version 乐观锁保护）
        taskRepository.deleteById(taskId);

        log.info("[DeleteTask] taskId={}, userId={}, pages cleaned", taskId, userId);
    }

    /**
     * 将采集任务转为文章草稿
     */
    @Transactional
    public Long convertToArticle(Long taskId, ConvertToArticleCommand command, Long userId) {
        WebCollectTask task = loadTaskForUser(taskId, userId);

        if (task.getArticleId() != null) {
            throw new BusinessException("该任务已转为文章，articleId=" + task.getArticleId());
        }

        String content = getTaskContent(task);
        if (content == null || content.isBlank()) {
            throw new BusinessException("任务内容为空，无法转为文章");
        }

        // 将 AI keyPoints/tags 作为结构化元数据插入内容头部
        content = prependAiMetadata(task, content);

        // 构建文章创建命令
        CreateArticleCommand articleCommand = new CreateArticleCommand();
        // 标题：用户覆盖 > AI 生成 > URL 摘要
        articleCommand.setTitle(command.getTitle() != null && !command.getTitle().isBlank()
                ? command.getTitle()
                : (task.getAiTitle() != null ? task.getAiTitle() : "采集: " + truncateUrl(task.getSourceUrl())));
        articleCommand.setContent(content);
        articleCommand.setSummary(task.getAiSummary());
        articleCommand.setCategoryId(command.getCategoryId());
        articleCommand.setIsOriginal(false);
        articleCommand.setOriginalUrl(task.getSourceUrl());
        articleCommand.setIsTop(false);
        articleCommand.setStatus(2); // 草稿

        Long articleId = articleAppService.create(articleCommand);

        // 回写关联
        task.markArticleCreated(articleId);
        taskRepository.save(task);

        log.info("[ConvertToArticle] taskId={} -> articleId={}", taskId, articleId);
        return articleId;
    }

    /**
     * 将采集任务转为技术日志
     */
    @Transactional
    public Long convertToDailyLog(Long taskId, ConvertToDailyLogCommand command, Long userId) {
        WebCollectTask task = loadTaskForUser(taskId, userId);

        if (task.getDailyLogId() != null) {
            throw new BusinessException("该任务已转为日志，dailyLogId=" + task.getDailyLogId());
        }

        String content = getTaskContent(task);
        if (content == null || content.isBlank()) {
            throw new BusinessException("任务内容为空，无法转为日志");
        }

        // 将 AI keyPoints/tags 作为结构化元数据插入内容头部
        content = prependAiMetadata(task, content);

        // 构建日志创建命令
        CreateDailyLogCommand logCommand = new CreateDailyLogCommand();
        logCommand.setContent(content);
        logCommand.setMood(command.getMood());
        logCommand.setWeather(command.getWeather());
        logCommand.setLogDate(command.getLogDate() != null ? command.getLogDate() : LocalDate.now());
        logCommand.setIsPublic(command.getIsPublic() != null ? command.getIsPublic() : false);
        logCommand.setCategoryId(command.getCategoryId());

        Long dailyLogId = dailyLogAppService.create(logCommand);

        // 回写关联
        task.markDailyLogCreated(dailyLogId);
        taskRepository.save(task);

        log.info("[ConvertToDailyLog] taskId={} -> dailyLogId={}", taskId, dailyLogId);
        return dailyLogId;
    }

    /**
     * 爬虫服务健康检查
     */
    public boolean isCrawlerAvailable() {
        return crawlerService.healthCheck();
    }

    /**
     * 重试失败的任务
     * 清除旧的页面数据和错误信息，重置状态后重新触发异步爬取
     */
    @Transactional
    public Long retryTask(Long taskId, Long userId) {
        WebCollectTask task = loadTaskForUser(taskId, userId);

        // 只有失败状态才允许重试
        if (task.getStatus() != CollectTaskStatus.FAILED.getValue()) {
            throw new BusinessException("只有失败的任务才能重试");
        }

        // 清除旧的页面数据
        pageRepository.deleteByTaskId(taskId);

        // 重置任务状态
        task.setErrorMessage(null);
        task.setCrawlDuration(null);
        task.setAiDuration(null);
        task.setTotalWordCount(null);
        task.setCompletedPages(0);
        task.updateStatus(CollectTaskStatus.PENDING);
        taskRepository.save(task);

        // 事务提交后再触发异步爬取
        TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
            @Override
            public void afterCommit() {
                asyncExecutor.executeCrawlAsync(taskId);
            }
        });

        log.info("[RetryTask] taskId={}, type={}, userId={}", taskId, task.getTaskType(), userId);
        return taskId;
    }

    // ============== 辅助方法 ==============

    private WebCollectTask loadTaskForUser(Long taskId, Long userId) {
        WebCollectTask task = taskRepository.findById(taskId)
                .orElseThrow(() -> new BusinessException("任务不存在"));
        if (!task.getUserId().equals(userId)) {
            throw new BusinessException("无权操作此任务");
        }
        return task;
    }

    /**
     * 将 AI 整理的 keyPoints/tags/category 作为结构化摘要插入内容头部
     */
    private String prependAiMetadata(WebCollectTask task, String content) {
        StringBuilder header = new StringBuilder();
        List<String> keyPoints = null;
        List<String> tags = null;

        try {
            if (task.getAiKeyPoints() != null && !task.getAiKeyPoints().isBlank()) {
                keyPoints = objectMapper.readValue(task.getAiKeyPoints(), new TypeReference<List<String>>() {});
            }
        } catch (Exception e) {
            log.warn("[prependAiMetadata] Failed to parse aiKeyPoints for task {}: {}", task.getId(), e.getMessage());
        }
        try {
            if (task.getAiTags() != null && !task.getAiTags().isBlank()) {
                tags = objectMapper.readValue(task.getAiTags(), new TypeReference<List<String>>() {});
            }
        } catch (Exception e) {
            log.warn("[prependAiMetadata] Failed to parse aiTags for task {}: {}", task.getId(), e.getMessage());
        }

        if ((keyPoints != null && !keyPoints.isEmpty()) || (tags != null && !tags.isEmpty())) {
            header.append("## AI 摘要\n\n");
            if (task.getAiCategory() != null) {
                header.append("> 分类：").append(task.getAiCategory()).append("\n\n");
            }
            if (tags != null && !tags.isEmpty()) {
                header.append("> 标签：").append(String.join("、", tags)).append("\n\n");
            }
            if (keyPoints != null && !keyPoints.isEmpty()) {
                header.append("**关键要点：**\n\n");
                for (Object point : keyPoints) {
                    header.append("- ").append(point).append("\n");
                }
                header.append("\n---\n\n");
            }
        }

        return header.isEmpty() ? content : header.append(content).toString();
    }

    /**
     * 获取任务的可用内容
     * 优先使用 AI 整理结果，否则拼接所有成功 page 的原始 Markdown
     */
    private String getTaskContent(WebCollectTask task) {
        // 1. 优先使用 AI 整理的完整内容
        if (task.getAiFullContent() != null && !task.getAiFullContent().isBlank()) {
            return task.getAiFullContent();
        }

        // 2. 拼接所有成功页面的原始 Markdown
        List<WebCollectPage> pages = pageRepository.findByTaskIdOrderBySortOrder(task.getId());
        StringBuilder sb = new StringBuilder();
        for (WebCollectPage page : pages) {
            if (page.getRawMarkdown() != null && !page.getRawMarkdown().isBlank()) {
                if (!sb.isEmpty()) {
                    sb.append("\n\n---\n\n");
                }
                sb.append(page.getRawMarkdown());
            }
        }
        return sb.isEmpty() ? null : sb.toString();
    }

    private String truncateUrl(String url) {
        if (url == null) return "未知来源";
        return url.length() > 60 ? url.substring(0, 60) + "..." : url;
    }

    // ============== DTO 转换方法 ==============

    private CollectTaskDTO convertToDTO(WebCollectTask task) {
        CollectTaskDTO dto = new CollectTaskDTO();
        BeanUtils.copyProperties(task, dto);
        dto.setId(String.valueOf(task.getId()));
        dto.setTaskTypeLabel(getTaskTypeLabel(task.getTaskType()));
        dto.setStatusLabel(getStatusLabel(task.getStatus()));
        dto.setStatusDisplay(getStatusDisplay(task.getStatus()));

        // 解析 JSON 字段
        if (task.getAiKeyPoints() != null) {
            try {
                dto.setAiKeyPoints(objectMapper.readValue(task.getAiKeyPoints(), List.class));
            } catch (Exception e) {
                dto.setAiKeyPoints(Collections.emptyList());
            }
        }
        if (task.getAiTags() != null) {
            try {
                dto.setAiTags(objectMapper.readValue(task.getAiTags(), List.class));
            } catch (Exception e) {
                dto.setAiTags(Collections.emptyList());
            }
        }

        // 计算进度
        if (task.getTotalPages() != null && task.getTotalPages() > 0) {
            dto.setProgressPercent((task.getCompletedPages() * 100) / task.getTotalPages());
        } else {
            dto.setProgressPercent(0);
        }

        return dto;
    }

    private CollectTaskListDTO convertToListDTO(WebCollectTask task) {
        CollectTaskListDTO dto = new CollectTaskListDTO();
        BeanUtils.copyProperties(task, dto);
        dto.setId(String.valueOf(task.getId()));
        dto.setTaskTypeLabel(getTaskTypeLabel(task.getTaskType()));
        dto.setStatusLabel(getStatusLabel(task.getStatus()));
        dto.setStatusDisplay(getStatusDisplay(task.getStatus()));

        // AI 结果摘要
        dto.setAiTitle(task.getAiTitle());
        if (task.getAiSummary() != null && task.getAiSummary().length() > 200) {
            dto.setAiSummary(task.getAiSummary().substring(0, 200) + "...");
        } else {
            dto.setAiSummary(task.getAiSummary());
        }

        // 计算进度
        if (task.getTotalPages() != null && task.getTotalPages() > 0) {
            dto.setProgressPercent((task.getCompletedPages() * 100) / task.getTotalPages());
        } else {
            dto.setProgressPercent(0);
        }

        return dto;
    }

    private CollectPageDTO convertToPageDTO(WebCollectPage page) {
        CollectPageDTO dto = new CollectPageDTO();
        BeanUtils.copyProperties(page, dto);
        dto.setId(String.valueOf(page.getId()));
        dto.setTaskId(String.valueOf(page.getTaskId()));
        dto.setCrawlStatusLabel(getPageStatusLabel(page.getCrawlStatus()));

        // 解析元数据
        if (page.getPageMetadata() != null) {
            try {
                dto.setPageMetadata(objectMapper.readValue(page.getPageMetadata(), new TypeReference<Map<String, Object>>() {}));
            } catch (Exception e) {
                dto.setPageMetadata(Collections.emptyMap());
            }
        }

        return dto;
    }

    private String getTaskTypeLabel(String type) {
        try {
            return CollectTaskType.of(type).getLabel();
        } catch (Exception e) {
            return type;
        }
    }

    private String getStatusLabel(Integer status) {
        try {
            return CollectTaskStatus.of(status).getLabel();
        } catch (Exception e) {
            return "未知";
        }
    }

    private String getStatusDisplay(Integer status) {
        try {
            return CollectTaskStatus.of(status).getDisplayText();
        } catch (Exception e) {
            return "未知";
        }
    }

    private String getPageStatusLabel(Integer status) {
        try {
            return PageCrawlStatus.of(status).getLabel();
        } catch (Exception e) {
            return "未知";
        }
    }

    // ============== 工具方法（public 供 AsyncExecutor 复用） ==============

    /**
     * URL 标准化哈希（去追踪参数、统一小写、去尾部斜杠）
     * 符合设计文档 Level 1 去重策略
     */
    public static String hashUrl(String url) {
        if (url == null) {
            return sha256("");
        }
        String normalized = url.toLowerCase().trim();
        // 去除常见追踪参数
        normalized = normalized.replaceAll("([?&])(utm_[^&=]*=[^&]*&?)+", "$1");
        // 去除尾部斜杠
        normalized = normalized.replaceAll("/+$", "");
        // 去除空的 query 参数
        normalized = normalized.replaceAll("[?&]+$", "");
        return sha256(normalized);
    }

    /**
     * 内容哈希（前 500 字标准化）
     */
    public static String hashContent(String content) {
        if (content == null) {
            return sha256("");
        }
        return sha256(content);
    }

    /**
     * SHA-256 哈希计算
     * 失败时抛出 RuntimeException 而非降级为 hashCode（hashCode 碰撞率过高）
     */
    public static String sha256(String input) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hash = digest.digest(input.getBytes(StandardCharsets.UTF_8));
            StringBuilder hexString = new StringBuilder();
            for (byte b : hash) {
                String hex = Integer.toHexString(0xff & b);
                if (hex.length() == 1) hexString.append('0');
                hexString.append(hex);
            }
            return hexString.toString();
        } catch (NoSuchAlgorithmException e) {
            // SHA-256 在所有现代 JVM 中都可用，若不可用说明环境有严重问题
            throw new RuntimeException("SHA-256 algorithm not available", e);
        }
    }
}
