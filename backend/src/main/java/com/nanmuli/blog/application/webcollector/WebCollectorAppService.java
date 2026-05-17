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
import com.nanmuli.blog.infrastructure.crawler.CrawlerTaskClient;
import com.nanmuli.blog.shared.exception.BusinessException;
import com.nanmuli.blog.shared.result.PageResult;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.BeanUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.annotation.Lazy;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Propagation;
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
 *
 * 新任务通过 CrawlerTaskClient 委托 Python 服务执行（爬取 + AI 整理），
 * Java 侧保留 MySQL 记录用于转换文章/日志的关联追踪。
 * 旧任务（无 pythonTaskId）仍从 MySQL 读取数据，向后兼容。
 */
@Slf4j
@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class WebCollectorAppService {

    private final WebCollectTaskRepository taskRepository;
    private final WebCollectPageRepository pageRepository;
    private final CrawlerTaskClient crawlerTaskClient;
    private final ArticleAppService articleAppService;
    private final DailyLogAppService dailyLogAppService;
    private final ObjectMapper objectMapper;

    @Autowired
    @Lazy
    private WebCollectorAppService self;

    // ============== 任务 CRUD ==============

    @Transactional
    public Long createTask(CreateCollectTaskCommand command, Long userId) {
        log.info("[CreateTask] type={}, userId={}", command.getTaskType(), userId);

        if (!command.isValid()) {
            throw new BusinessException("请求参数错误：URL 或关键词不能为空");
        }

        if ("digest".equals(command.getTaskType())) {
            throw new BusinessException("日报任务请通过 /api/admin/collector/digest/trigger 端点触发");
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

        // 事务提交后调用 Python 任务 API
        final Long taskId = task.getId();
        TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
            @Override
            public void afterCommit() {
                try {
                    int pythonTaskId = crawlerTaskClient.createTask(
                            command.getTaskType(), command.getSourceUrl(), command.getKeyword(),
                            command.getSearchEngine(), command.getMaxDepth(), command.getMaxPages(),
                            command.getAiTemplate(), command.getTimeRange());
                    self.updatePythonTaskId(taskId, pythonTaskId);
                    log.info("[CreateTask] taskId={}, pythonTaskId={}", taskId, pythonTaskId);
                } catch (Exception e) {
                    log.error("[CreateTask] Failed to create Python task for taskId={}: {}", taskId, e.getMessage());
                    self.markTaskFailed(taskId, "Python 服务调用失败: " + safeErrMsg(e));
                }
            }
        });

        return task.getId();
    }

    public CollectTaskDTO getTask(Long taskId, Long userId) {
        WebCollectTask task = loadTaskForUser(taskId, userId);
        if (syncFromPythonIfNeeded(task)) {
            task = loadTaskForUser(taskId, userId);
        }
        return convertToDTO(task);
    }

    public PageResult<CollectTaskListDTO> listTasks(CollectTaskPageQuery query, Long userId) {
        IPage<WebCollectTask> page = new Page<>(query.getCurrent(), query.getSize());

        IPage<WebCollectTask> result = taskRepository.findPageFiltered(
                page, userId, query.getStatus(), query.getTaskType(), query.getKeyword());

        // 列表查询不触发 Python sync，避免 N+1 HTTP 调用
        // 活跃任务的实时状态在 getTask() 详情接口中按需同步

        List<CollectTaskListDTO> records = result.getRecords().stream()
                .map(this::convertToListDTO)
                .toList();

        return new PageResult<>(result.getTotal(), result.getCurrent(), result.getSize(), records);
    }

    public List<CollectPageDTO> listTaskPages(Long taskId, Long userId) {
        WebCollectTask task = loadTaskForUser(taskId, userId);

        // 新任务：从 Python 获取页面数据
        if (task.getPythonTaskId() != null) {
            return fetchPagesFromPython(task.getPythonTaskId());
        }

        // 旧任务：从 MySQL 获取
        return pageRepository.findByTaskIdOrderBySortOrder(taskId).stream()
                .map(this::convertToPageDTO)
                .toList();
    }

    @Transactional
    public void deleteTask(Long taskId, Long userId) {
        WebCollectTask task = loadTaskForUser(taskId, userId);

        if (task.getStatus() == CollectTaskStatus.CRAWLING.getValue()
                || task.getStatus() == CollectTaskStatus.PROCESSING.getValue()) {
            throw new BusinessException("任务正在处理中，无法删除，请等待完成后再试");
        }

        Integer pythonTaskId = task.getPythonTaskId();

        pageRepository.deleteByTaskId(taskId);
        taskRepository.deleteById(taskId);

        // DB 删除成功后通知 Python（best-effort）
        if (pythonTaskId != null) {
            TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
                @Override
                public void afterCommit() {
                    crawlerTaskClient.deleteTask(pythonTaskId);
                }
            });
        }
        log.info("[DeleteTask] taskId={}, userId={}", taskId, userId);
    }

    @Transactional
    public Long retryTask(Long taskId, Long userId) {
        WebCollectTask task = loadTaskForUser(taskId, userId);

        if (task.getStatus() != CollectTaskStatus.FAILED.getValue()) {
            throw new BusinessException("只有失败的任务才能重试");
        }

        pageRepository.deleteByTaskId(taskId);

        // 重置任务状态
        task.setErrorMessage(null);
        task.setCrawlDuration(null);
        task.setAiDuration(null);
        task.setTotalWordCount(null);
        task.setAiTitle(null);
        task.setAiSummary(null);
        task.setAiKeyPoints(null);
        task.setAiTags(null);
        task.setAiCategory(null);
        task.setAiFullContent(null);
        task.setAiSearchMetadata(null);
        task.setTokensUsed(null);
        task.setCompletedPages(0);
        task.setStatus(CollectTaskStatus.PENDING.getValue());
        taskRepository.save(task);

        // 事务提交后触发 Python 重试或新建
        final Long tid = taskId;
        final Integer oldPythonTaskId = task.getPythonTaskId();
        final String taskType = task.getTaskType();
        final String sourceUrl = task.getSourceUrl();
        final String keyword = task.getKeyword();
        final String searchEngine = task.getSearchEngine();
        final Integer maxDepth = task.getMaxDepth();
        final Integer maxPages = task.getMaxPages();
        final String aiTemplate = task.getAiTemplate();
        final String timeRange = task.getTimeRange();

        TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
            @Override
            public void afterCommit() {
                try {
                    if (oldPythonTaskId != null) {
                        try {
                            crawlerTaskClient.retryTask(oldPythonTaskId);
                            log.info("[RetryTask] taskId={}, pythonTaskId={}", tid, oldPythonTaskId);
                            return;
                        } catch (Exception retryError) {
                            log.warn("[RetryTask] Retry failed for pythonTaskId={}, creating new task: {}",
                                    oldPythonTaskId, retryError.getMessage());
                        }
                    }
                    // 无 pythonTaskId 或 retry 失败，创建新 Python 任务
                    int pythonTaskId = crawlerTaskClient.createTask(
                            taskType, sourceUrl, keyword,
                            searchEngine, maxDepth, maxPages, aiTemplate, timeRange);
                    self.updatePythonTaskId(tid, pythonTaskId);
                    log.info("[RetryTask] taskId={}, new pythonTaskId={}", tid, pythonTaskId);
                } catch (Exception e) {
                    log.error("[RetryTask] Failed for taskId={}: {}", tid, e.getMessage());
                    self.markTaskFailed(tid, "Python 服务调用失败: " + safeErrMsg(e));
                }
            }
        });

        return taskId;
    }

    public boolean isCrawlerAvailable() {
        return crawlerTaskClient.healthCheck();
    }

    // ============== 转换操作 ==============

    @Transactional
    public Long convertToArticle(Long taskId, ConvertToArticleCommand command, Long userId) {
        WebCollectTask task = loadTaskForUser(taskId, userId);

        if (!isTerminal(task.getStatus())) {
            throw new BusinessException("任务尚未完成，无法转换");
        }

        // 转换前先同步最新 AI 结果
        if (syncFromPythonIfNeeded(task)) {
            task = loadTaskForUser(taskId, userId);
        };

        if (task.getArticleId() != null) {
            throw new BusinessException("该任务已转为文章，articleId=" + task.getArticleId());
        }

        String content = getTaskContent(task);
        if (content == null || content.isBlank()) {
            throw new BusinessException("任务内容为空，无法转为文章");
        }

        content = prependAiMetadata(task, content);

        CreateArticleCommand articleCommand = new CreateArticleCommand();
        articleCommand.setTitle(command.getTitle() != null && !command.getTitle().isBlank()
                ? command.getTitle()
                : (task.getAiTitle() != null ? task.getAiTitle() : "采集: " + truncateUrl(task.getSourceUrl())));
        articleCommand.setContent(content);
        articleCommand.setSummary(task.getAiSummary());
        articleCommand.setCategoryId(command.getCategoryId());
        articleCommand.setIsOriginal(false);
        articleCommand.setOriginalUrl(task.getSourceUrl());
        articleCommand.setIsTop(false);
        articleCommand.setStatus(2);

        Long articleId = articleAppService.create(articleCommand);
        task.markArticleCreated(articleId);
        taskRepository.save(task);

        log.info("[ConvertToArticle] taskId={} -> articleId={}", taskId, articleId);
        return articleId;
    }

    @Transactional
    public Long convertToDailyLog(Long taskId, ConvertToDailyLogCommand command, Long userId) {
        WebCollectTask task = loadTaskForUser(taskId, userId);

        if (!isTerminal(task.getStatus())) {
            throw new BusinessException("任务尚未完成，无法转换");
        }

        if (syncFromPythonIfNeeded(task)) {
            task = loadTaskForUser(taskId, userId);
        }

        if (task.getDailyLogId() != null) {
            throw new BusinessException("该任务已转为日志，dailyLogId=" + task.getDailyLogId());
        }

        String content = getTaskContent(task);
        if (content == null || content.isBlank()) {
            throw new BusinessException("任务内容为空，无法转为日志");
        }

        content = prependAiMetadata(task, content);

        CreateDailyLogCommand logCommand = new CreateDailyLogCommand();
        logCommand.setContent(content);
        logCommand.setMood(command.getMood());
        logCommand.setWeather(command.getWeather());
        logCommand.setLogDate(command.getLogDate() != null ? command.getLogDate() : LocalDate.now());
        logCommand.setIsPublic(command.getIsPublic() != null ? command.getIsPublic() : false);
        logCommand.setCategoryId(command.getCategoryId());

        Long dailyLogId = dailyLogAppService.create(logCommand);
        task.markDailyLogCreated(dailyLogId);
        taskRepository.save(task);

        log.info("[ConvertToDailyLog] taskId={} -> dailyLogId={}", taskId, dailyLogId);
        return dailyLogId;
    }

    // ============== Python 同步 ==============

    /**
     * afterCommit 中调用的 DB 操作，独立事务保证原子性
     */
    @Transactional(propagation = Propagation.REQUIRES_NEW, readOnly = false)
    public void updatePythonTaskId(Long taskId, int pythonTaskId) {
        taskRepository.findById(taskId).ifPresent(t -> {
            t.setPythonTaskId(pythonTaskId);
            taskRepository.save(t);
        });
    }

    @Transactional(propagation = Propagation.REQUIRES_NEW, readOnly = false)
    public void markTaskFailed(Long taskId, String errorMessage) {
        taskRepository.findById(taskId).ifPresent(t -> {
            t.markFailed(errorMessage);
            taskRepository.save(t);
        });
    }

    /**
     * 从 Python 同步任务状态和 AI 结果到 MySQL（仅在任务非终态时）
     */
    private boolean syncFromPythonIfNeeded(WebCollectTask task) {
        if (task.getPythonTaskId() != null && !isTerminal(task.getStatus())) {
            syncFromPythonSilent(task);
            return true;
        }
        return false;
    }

    public void syncFromPythonSilent(WebCollectTask task) {
        try {
            crawlerTaskClient.getTask(task.getPythonTaskId()).ifPresent(pythonTask -> {
                self.syncPythonTaskToDb(task.getId(), pythonTask);
            });
        } catch (org.springframework.dao.OptimisticLockingFailureException e) {
            log.info("[syncFromPython] Concurrent sync detected for taskId={}, another callback already processed it",
                    task.getId());
        } catch (Exception e) {
            log.warn("[syncFromPython] Failed for taskId={}, pythonTaskId={}: {}",
                    task.getId(), task.getPythonTaskId(), e.getMessage());
        }
    }

    @Transactional(propagation = Propagation.REQUIRES_NEW, readOnly = false)
    public void syncPythonTaskToDb(Long taskId, Map<String, Object> pythonTask) {
        taskRepository.findById(taskId).ifPresent(t -> {
            updateTaskFromPython(t, pythonTask);
            taskRepository.save(t);
        });
    }

    /**
     * 处理 Python 回调：按 pythonTaskId 找到 Java 任务并同步状态
     */
    public void handleCallback(Integer pythonTaskId) {
        Optional<WebCollectTask> opt = taskRepository.findByPythonTaskId(pythonTaskId);
        if (opt.isEmpty()) {
            log.warn("[Callback] No Java task found for pythonTaskId={}", pythonTaskId);
            return;
        }
        WebCollectTask task = opt.get();
        if (isTerminal(task.getStatus())) {
            log.debug("[Callback] Task {} already terminal, skipping", task.getId());
            return;
        }
        log.info("[Callback] Syncing task {} from pythonTaskId={}", task.getId(), pythonTaskId);
        syncFromPythonSilent(task);
    }

    /**
     * 将 Python 任务 API 响应同步到 MySQL 实体
     */
    private void updateTaskFromPython(WebCollectTask task, Map<String, Object> pythonTask) {
        // 状态同步
        Object statusObj = pythonTask.get("status");
        if (statusObj instanceof Number num) {
            task.updateStatus(CollectTaskStatus.of(num.intValue()));
        }

        // 错误信息 — 确保 FAILED 状态不显示空错误
        String errMsg = getStr(pythonTask, "error_message");
        if (errMsg == null || errMsg.isBlank()) {
            Object st = pythonTask.get("status");
            if (st instanceof Number num && num.intValue() == CollectTaskStatus.FAILED.getValue()) {
                errMsg = "任务执行失败，未收到详细错误信息";
            }
        }
        task.setErrorMessage(errMsg);

        // 进度
        Object totalPages = pythonTask.get("total_pages");
        if (totalPages instanceof Number num) task.setTotalPages(num.intValue());
        Object completedPages = pythonTask.get("completed_pages");
        if (completedPages instanceof Number num) task.setCompletedPages(num.intValue());

        // 统计
        Object crawlDuration = pythonTask.get("crawl_duration");
        if (crawlDuration instanceof Number num) task.setCrawlDuration(num.intValue());
        Object totalWordCount = pythonTask.get("total_word_count");
        if (totalWordCount instanceof Number num) task.setTotalWordCount(num.intValue());

        // AI 结果
        task.setAiTitle(getStr(pythonTask, "ai_title"));
        task.setAiSummary(getStr(pythonTask, "ai_summary"));
        task.setAiCategory(getStr(pythonTask, "ai_category"));
        task.setAiFullContent(getStr(pythonTask, "ai_full_content"));

        Object aiKeyPoints = pythonTask.get("ai_key_points");
        if (aiKeyPoints != null) {
            task.setAiKeyPoints(aiKeyPoints instanceof String s ? s : safeToJson(aiKeyPoints));
        }
        Object aiTags = pythonTask.get("ai_tags");
        if (aiTags != null) {
            task.setAiTags(aiTags instanceof String s ? s : safeToJson(aiTags));
        }
        Object aiSearchMetadata = pythonTask.get("ai_search_metadata");
        if (aiSearchMetadata != null) {
            task.setAiSearchMetadata(aiSearchMetadata instanceof String s ? s : safeToJson(aiSearchMetadata));
        }
        Object aiDuration = pythonTask.get("ai_duration");
        if (aiDuration instanceof Number num) task.setAiDuration(num.intValue());
        Object tokensUsed = pythonTask.get("ai_tokens_used");
        if (tokensUsed instanceof Number num) task.setTokensUsed(num.intValue());
    }

    /**
     * 从 Python 获取任务页面列表并转为 DTO
     */
    @SuppressWarnings("unchecked")
    private List<CollectPageDTO> fetchPagesFromPython(int pythonTaskId) {
        return crawlerTaskClient.getTaskPages(pythonTaskId)
                .map(resp -> {
                    List<Map<String, Object>> pages = (List<Map<String, Object>>) resp.get("pages");
                    if (pages == null) return Collections.<CollectPageDTO>emptyList();
                    return pages.stream().map(p -> {
                        CollectPageDTO dto = new CollectPageDTO();
                        dto.setId(String.valueOf(p.get("id")));
                        dto.setTaskId(String.valueOf(p.get("task_id")));
                        dto.setUrl(getStr(p, "url"));
                        dto.setPageTitle(getStr(p, "page_title"));
                        dto.setRawMarkdown(getStr(p, "raw_markdown"));
                        dto.setErrorMessage(getStr(p, "error_message"));
                        dto.setCrawlStatusLabel(getStr(p, "status_label"));
                        Object cs = p.get("crawl_status");
                        if (cs instanceof Number num) dto.setCrawlStatus(num.intValue());
                        Object wc = p.get("word_count");
                        if (wc instanceof Number num) dto.setWordCount(num.intValue());
                        Object cd = p.get("crawl_duration");
                        if (cd instanceof Number num) dto.setCrawlDuration(num.intValue());
                        Object so = p.get("sort_order");
                        if (so instanceof Number num) dto.setSortOrder(num.intValue());
                        Object depth = p.get("depth");
                        if (depth instanceof Number num) dto.setDepth(num.intValue());
                        return dto;
                    }).toList();
                })
                .orElse(Collections.emptyList());
    }

    // ============== 辅助方法 ==============

    private boolean isTerminal(Integer status) {
        return status != null
                && (status == CollectTaskStatus.COMPLETED.getValue()
                || status == CollectTaskStatus.FAILED.getValue());
    }

    private String safeToJson(Object value) {
        try { return objectMapper.writeValueAsString(value); }
        catch (Exception e) { log.debug("[DTO] JSON serialization failed: {}", e.getMessage()); return null; }
    }

    private WebCollectTask loadTaskForUser(Long taskId, Long userId) {
        WebCollectTask task = taskRepository.findById(taskId)
                .orElseThrow(() -> new BusinessException("任务不存在"));
        if (!task.getUserId().equals(userId)) {
            throw new BusinessException("无权操作此任务");
        }
        return task;
    }

    private String getStr(Map<String, Object> map, String key) {
        Object val = map.get(key);
        return val != null ? val.toString() : null;
    }

    private String prependAiMetadata(WebCollectTask task, String content) {
        StringBuilder header = new StringBuilder();
        List<String> keyPoints = null;
        List<String> tags = null;

        try {
            if (task.getAiKeyPoints() != null && !task.getAiKeyPoints().isBlank()) {
                keyPoints = objectMapper.readValue(task.getAiKeyPoints(), new TypeReference<List<String>>() {});
            }
        } catch (Exception e) {
            log.warn("[prependAiMetadata] Failed to parse aiKeyPoints: {}", e.getMessage());
        }
        try {
            if (task.getAiTags() != null && !task.getAiTags().isBlank()) {
                tags = objectMapper.readValue(task.getAiTags(), new TypeReference<List<String>>() {});
            }
        } catch (Exception e) {
            log.warn("[prependAiMetadata] Failed to parse aiTags: {}", e.getMessage());
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

    private String getTaskContent(WebCollectTask task) {
        if (task.getAiFullContent() != null && !task.getAiFullContent().isBlank()) {
            return task.getAiFullContent();
        }

        // 新任务：从 Python 获取页面 markdown
        if (task.getPythonTaskId() != null) {
            return fetchPagesFromPython(task.getPythonTaskId()).stream()
                    .map(CollectPageDTO::getRawMarkdown)
                    .filter(md -> md != null && !md.isBlank())
                    .reduce((a, b) -> a + "\n\n---\n\n" + b)
                    .orElse(null);
        }

        // 旧任务：从 MySQL 获取
        List<WebCollectPage> pages = pageRepository.findByTaskIdOrderBySortOrder(task.getId());
        StringBuilder sb = new StringBuilder();
        for (WebCollectPage page : pages) {
            if (page.getRawMarkdown() != null && !page.getRawMarkdown().isBlank()) {
                if (!sb.isEmpty()) sb.append("\n\n---\n\n");
                sb.append(page.getRawMarkdown());
            }
        }
        return sb.isEmpty() ? null : sb.toString();
    }

    private static String safeErrMsg(Exception e) {
        String msg = e.getMessage();
        return (msg != null && !msg.isBlank()) ? msg : "未知错误";
    }

    private String truncateUrl(String url) {
        if (url == null) return "未知来源";
        return url.length() > 60 ? url.substring(0, 60) + "..." : url;
    }

    // ============== DTO 转换 ==============

    private CollectTaskDTO convertToDTO(WebCollectTask task) {
        CollectTaskDTO dto = new CollectTaskDTO();
        BeanUtils.copyProperties(task, dto);
        dto.setId(String.valueOf(task.getId()));
        if (task.getArticleId() != null) dto.setArticleId(String.valueOf(task.getArticleId()));
        if (task.getDailyLogId() != null) dto.setDailyLogId(String.valueOf(task.getDailyLogId()));
        dto.setTaskTypeLabel(getTaskTypeLabel(task.getTaskType()));
        dto.setStatusLabel(getStatusLabel(task.getStatus()));
        dto.setStatusDisplay(getStatusDisplay(task.getStatus()));
        if (task.getAiSearchMetadata() != null && !task.getAiSearchMetadata().isBlank()) {
            try {
                dto.setAiSearchMetadata(objectMapper.readValue(
                        task.getAiSearchMetadata(), new TypeReference<Map<String, Object>>() {}));
            } catch (Exception e) {
                log.debug("[DTO] Failed to parse aiSearchMetadata for taskId={}: {}", task.getId(), e.getMessage());
                dto.setAiSearchMetadata(Collections.emptyMap());
            }
        }

        if (task.getAiKeyPoints() != null) {
            try { dto.setAiKeyPoints(objectMapper.readValue(task.getAiKeyPoints(), List.class)); }
            catch (Exception e) { log.debug("[DTO] Failed to parse aiKeyPoints: {}", e.getMessage()); dto.setAiKeyPoints(Collections.emptyList()); }
        }
        if (task.getAiTags() != null) {
            try { dto.setAiTags(objectMapper.readValue(task.getAiTags(), List.class)); }
            catch (Exception e) { log.debug("[DTO] Failed to parse aiTags: {}", e.getMessage()); dto.setAiTags(Collections.emptyList()); }
        }

        if (task.getTotalPages() != null && task.getTotalPages() > 0
                && task.getCompletedPages() != null) {
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
        if (task.getArticleId() != null) dto.setArticleId(String.valueOf(task.getArticleId()));
        if (task.getDailyLogId() != null) dto.setDailyLogId(String.valueOf(task.getDailyLogId()));
        dto.setTaskTypeLabel(getTaskTypeLabel(task.getTaskType()));
        dto.setStatusLabel(getStatusLabel(task.getStatus()));
        dto.setStatusDisplay(getStatusDisplay(task.getStatus()));

        dto.setAiTitle(task.getAiTitle());
        if (task.getAiSummary() != null && task.getAiSummary().length() > 200) {
            dto.setAiSummary(task.getAiSummary().substring(0, 200) + "...");
        } else {
            dto.setAiSummary(task.getAiSummary());
        }

        if (task.getTotalPages() != null && task.getTotalPages() > 0
                && task.getCompletedPages() != null) {
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

        if (page.getPageMetadata() != null) {
            try {
                dto.setPageMetadata(objectMapper.readValue(page.getPageMetadata(), new TypeReference<Map<String, Object>>() {}));
            } catch (Exception e) {
                log.debug("[DTO] Failed to parse pageMetadata for pageId={}: {}", page.getId(), e.getMessage());
                dto.setPageMetadata(Collections.emptyMap());
            }
        }

        return dto;
    }

    private String getTaskTypeLabel(String type) {
        try { return CollectTaskType.of(type).getLabel(); }
        catch (Exception e) { log.debug("[DTO] Unknown task type: {}", type); return type; }
    }

    private String getStatusLabel(Integer status) {
        try { return CollectTaskStatus.of(status).getLabel(); }
        catch (Exception e) { log.debug("[DTO] Unknown status: {}", status); return "未知"; }
    }

    private String getStatusDisplay(Integer status) {
        try { return CollectTaskStatus.of(status).getDisplayText(); }
        catch (Exception e) { log.debug("[DTO] Unknown status: {}", status); return "未知"; }
    }

    private String getPageStatusLabel(Integer status) {
        try { return PageCrawlStatus.of(status).getLabel(); }
        catch (Exception e) { log.debug("[DTO] Unknown page status: {}", status); return "未知"; }
    }

    // ============== 工具方法 ==============

    public static String hashUrl(String url) {
        if (url == null) return sha256("");
        String normalized = url.toLowerCase().trim();
        normalized = normalized.replaceAll("([?&])(utm_[^&=]*=[^&]*&?)+", "$1");
        normalized = normalized.replaceAll("/+$", "");
        normalized = normalized.replaceAll("[?&]+$", "");
        return sha256(normalized);
    }

    public static String hashContent(String content) {
        return sha256(content == null ? "" : content);
    }

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
            throw new RuntimeException("SHA-256 algorithm not available", e);
        }
    }
}
