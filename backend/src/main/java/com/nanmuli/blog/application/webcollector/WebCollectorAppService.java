package com.nanmuli.blog.application.webcollector;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.nanmuli.blog.application.webcollector.command.CreateCollectTaskCommand;
import com.nanmuli.blog.application.webcollector.dto.CollectPageDTO;
import com.nanmuli.blog.application.webcollector.dto.CollectTaskDTO;
import com.nanmuli.blog.application.webcollector.dto.CollectTaskListDTO;
import com.nanmuli.blog.application.webcollector.query.CollectTaskPageQuery;
import com.nanmuli.blog.domain.webcollector.*;
import com.nanmuli.blog.infrastructure.crawler.CrawlResult;
import com.nanmuli.blog.infrastructure.crawler.CrawlerService;
import com.nanmuli.blog.infrastructure.persistence.webcollector.WebCollectTaskMapper;
import com.nanmuli.blog.shared.exception.BusinessException;
import com.nanmuli.blog.shared.result.PageResult;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.BeanUtils;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.*;

/**
 * Web Collector 应用服务
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class WebCollectorAppService {

    private final WebCollectTaskRepository taskRepository;
    private final WebCollectPageRepository pageRepository;
    private final WebCollectTaskMapper taskMapper;
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
        task.setAiTemplate(command.getAiTemplate());
        task.setTriggerType("manual");
        task.setStatus(CollectTaskStatus.PENDING);
        task.setTotalPages(1);
        task.setCompletedPages(0);

        taskRepository.save(task);

        // 异步执行爬取
        executeCrawlAsync(task.getId());

        return task.getId();
    }

    /**
     * 异步执行爬取
     */
    @Async("crawlerTaskExecutor")
    public void executeCrawlAsync(Long taskId) {
        log.info("[CrawlAsync] Starting taskId={}", taskId);

        WebCollectTask task = taskRepository.findById(taskId)
                .orElseThrow(() -> new BusinessException("任务不存在"));

        try {
            // 更新状态为爬取中
            task.setStatus(CollectTaskStatus.CRAWLING);
            taskRepository.save(task);

            long crawlStartTime = System.currentTimeMillis();
            List<CrawlResult> crawlResults;

            // 根据任务类型执行不同的爬取策略
            CrawlerService.CrawlConfig config = new CrawlerService.CrawlConfig();
            config.setTextMode(true);
            config.setLightMode(true);

            switch (CollectTaskType.of(task.getTaskType())) {
                case SINGLE -> {
                    task.setTotalPages(1);
                    CrawlResult result = crawlerService.crawlSingle(task.getSourceUrl(), config);
                    crawlResults = Collections.singletonList(result);
                }
                case DEEP -> {
                    crawlResults = crawlerService.crawlDeep(
                            task.getSourceUrl(),
                            task.getMaxDepth(),
                            task.getMaxPages(),
                            config
                    );
                    task.setTotalPages(crawlResults.size());
                }
                case KEYWORD -> {
                    crawlResults = crawlerService.crawlByKeyword(
                            task.getKeyword(),
                            task.getSearchEngine(),
                            task.getMaxPages(),
                            config
                    );
                    task.setTotalPages(crawlResults.size());
                }
                default -> throw new BusinessException("不支持的任务类型");
            }

            int crawlDuration = (int) (System.currentTimeMillis() - crawlStartTime);

            // 保存页面结果
            int totalWordCount = saveCrawlResults(task.getId(), crawlResults);

            // 更新任务状态
            task.setCompletedPages((int) crawlResults.stream().filter(CrawlResult::isSuccess).count());
            task.setCrawlDuration(crawlDuration);
            task.setTotalWordCount(totalWordCount);
            task.setStatus(CollectTaskStatus.COMPLETED); // Phase 1 先直接完成，Phase 2 加入 AI 整理
            taskRepository.save(task);

            log.info("[CrawlAsync] Completed taskId={}, pages={}, words={}",
                    taskId, crawlResults.size(), totalWordCount);

        } catch (Exception e) {
            log.error("[CrawlAsync] Failed taskId={}", taskId, e);
            task.markFailed(e.getMessage());
            taskRepository.save(task);
        }
    }

    /**
     * 保存爬取结果到页面表
     */
    private int saveCrawlResults(Long taskId, List<CrawlResult> results) {
        int totalWordCount = 0;
        int sortOrder = 0;

        for (CrawlResult result : results) {
            WebCollectPage page = new WebCollectPage();
            page.setTaskId(taskId);
            page.setUrl(result.getUrl());
            page.setPageTitle(result.getTitle());
            page.setUrlHash(hashUrl(result.getUrl()));
            page.setSortOrder(sortOrder++);
            page.setDepth(result.getDepth());

            if (result.isSuccess()) {
                page.setRawMarkdown(result.getMarkdown());
                page.setCrawlStatus(PageCrawlStatus.COMPLETED.getValue());
                page.setWordCount(result.getWordCount());
                page.setCrawlDuration((int) result.getCrawlTimeMs());
                totalWordCount += result.getWordCount();

                // 保存元数据
                if (result.getMetadata() != null) {
                    try {
                        page.setPageMetadata(objectMapper.writeValueAsString(result.getMetadata()));
                    } catch (JsonProcessingException e) {
                        log.warn("Failed to serialize metadata: {}", e.getMessage());
                    }
                }

                // 计算内容哈希（前500字）
                if (result.getMarkdown() != null) {
                    String contentPreview = result.getMarkdown().replaceAll("\\s+", "")
                            .substring(0, Math.min(500, result.getMarkdown().length()));
                    page.setContentHash(hashContent(contentPreview));
                }
            } else {
                page.setCrawlStatus(PageCrawlStatus.FAILED.getValue());
                page.setErrorMessage(result.getErrorMessage());
            }

            pageRepository.save(page);
        }

        return totalWordCount;
    }

    /**
     * 查询任务详情
     */
    @Transactional(readOnly = true)
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
    @Transactional(readOnly = true)
    public PageResult<CollectTaskListDTO> listTasks(CollectTaskPageQuery query, Long userId) {
        IPage<WebCollectTask> page = new Page<>(query.getCurrent(), query.getSize());

        // 构建查询条件
        LambdaQueryWrapper<WebCollectTask> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(WebCollectTask::getUserId, userId)
               .eq(WebCollectTask::getIsDeleted, false);

        if (query.getStatus() != null) {
            wrapper.eq(WebCollectTask::getStatus, query.getStatus());
        }
        if (query.getTaskType() != null) {
            wrapper.eq(WebCollectTask::getTaskType, query.getTaskType());
        }
        wrapper.orderByDesc(WebCollectTask::getCreatedAt);

        IPage<WebCollectTask> result = taskMapper.selectPage(page, wrapper);

        List<CollectTaskListDTO> records = result.getRecords().stream()
                .map(this::convertToListDTO)
                .toList();

        return new PageResult<>(result.getTotal(), result.getCurrent(), result.getSize(), records);
    }

    /**
     * 查询任务的页面列表
     */
    @Transactional(readOnly = true)
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
     * 删除任务
     */
    @Transactional
    public void deleteTask(Long taskId, Long userId) {
        WebCollectTask task = taskRepository.findById(taskId)
                .orElseThrow(() -> new BusinessException("任务不存在"));

        if (!task.getUserId().equals(userId)) {
            throw new BusinessException("无权删除此任务");
        }

        // MyBatis Plus 逻辑删除
        taskRepository.deleteById(taskId);

        log.info("[DeleteTask] taskId={}, userId={}", taskId, userId);
    }

    // ============== 转换方法 ==============

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
                dto.setPageMetadata(objectMapper.readValue(page.getPageMetadata(), Map.class));
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

    // ============== 工具方法 ==============

    private String hashUrl(String url) {
        return sha256(url.toLowerCase().trim());
    }

    private String hashContent(String content) {
        return sha256(content);
    }

    private String sha256(String input) {
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
            return String.valueOf(input.hashCode());
        }
    }
}
