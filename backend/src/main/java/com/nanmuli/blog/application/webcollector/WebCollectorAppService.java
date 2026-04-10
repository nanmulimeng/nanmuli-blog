package com.nanmuli.blog.application.webcollector;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.nanmuli.blog.application.webcollector.command.CreateCollectTaskCommand;
import com.nanmuli.blog.application.webcollector.dto.CollectPageDTO;
import com.nanmuli.blog.application.webcollector.dto.CollectTaskDTO;
import com.nanmuli.blog.application.webcollector.dto.CollectTaskListDTO;
import com.nanmuli.blog.application.webcollector.query.CollectTaskPageQuery;
import com.nanmuli.blog.domain.webcollector.*;
import com.nanmuli.blog.infrastructure.persistence.webcollector.WebCollectTaskMapper;
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
    private final WebCollectorAsyncExecutor asyncExecutor;
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
        task.setAiTemplate(command.getAiTemplate());
        task.setTriggerType("manual");
        task.setStatus(CollectTaskStatus.PENDING);
        task.setTotalPages(1);
        task.setCompletedPages(0);

        taskRepository.save(task);

        // 事务提交后再触发异步爬取，避免异步线程读不到未提交的数据
        final Long taskId = task.getId();
        TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
            @Override
            public void afterCommit() {
                asyncExecutor.executeCrawlAsync(taskId);
            }
        });

        return task.getId();
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
     * 删除任务（级联清理关联的页面数据）
     */
    @Transactional
    public void deleteTask(Long taskId, Long userId) {
        WebCollectTask task = taskRepository.findById(taskId)
                .orElseThrow(() -> new BusinessException("任务不存在"));

        if (!task.getUserId().equals(userId)) {
            throw new BusinessException("无权删除此任务");
        }

        // 先清理关联的页面数据（逻辑删除不会触发 DB CASCADE）
        pageRepository.deleteByTaskId(taskId);

        // 再逻辑删除任务
        taskRepository.deleteById(taskId);

        log.info("[DeleteTask] taskId={}, userId={}, pages cleaned", taskId, userId);
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
