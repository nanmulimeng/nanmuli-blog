package com.nanmuli.blog.application.webcollector;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.nanmuli.blog.domain.webcollector.*;
import com.nanmuli.blog.infrastructure.crawler.CrawlResult;
import com.nanmuli.blog.infrastructure.crawler.CrawlerService;
import com.nanmuli.blog.shared.exception.BusinessException;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;

import java.util.Collections;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.concurrent.TimeUnit;

/**
 * 爬取异步执行器
 * 独立 Service 确保 @Async 通过 Spring 代理正确生效（避免自调用失效）
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class WebCollectorAsyncExecutor {

    private final WebCollectTaskRepository taskRepository;
    private final WebCollectPageRepository pageRepository;
    private final CrawlerService crawlerService;
    private final ObjectMapper objectMapper;

    @Autowired(required = false)
    private AiContentOrganizer aiContentOrganizer;

    /**
     * 异步执行爬取任务
     * 必须通过 Spring 代理调用（不能自调用），否则 @Async 不生效
     */
    @Async("crawlerTaskExecutor")
    public void executeCrawlAsync(Long taskId) {
        log.info("[CrawlAsync] Starting taskId={}", taskId);

        WebCollectTask task = taskRepository.findById(taskId)
                .orElseThrow(() -> new BusinessException("任务不存在"));

        try {
            // 更新状态为爬取中
            task.updateStatus(CollectTaskStatus.CRAWLING);
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

            // 保存页面结果（逐页更新进度）
            int totalWordCount = saveCrawlResults(task, crawlResults);

            // 更新任务统计
            task.setCrawlDuration(crawlDuration);
            task.setTotalWordCount(totalWordCount);

            // 检查是否有成功爬取的页面，全部失败则直接标记 FAILED
            if (task.getCompletedPages() == null || task.getCompletedPages() == 0) {
                String errorMsg = crawlResults.stream()
                        .filter(r -> r.getErrorMessage() != null)
                        .map(CrawlResult::getErrorMessage)
                        .findFirst()
                        .orElse("所有页面爬取失败，未获取到有效内容");
                task.markFailed(errorMsg);
                taskRepository.save(task);
                log.warn("[CrawlAsync] All pages failed, taskId={}, total={}, error={}", taskId, crawlResults.size(), errorMsg);
                return;
            }

            // Phase 2: 爬取完成后进入 AI 整理阶段
            task.updateStatus(CollectTaskStatus.PROCESSING);
            taskRepository.save(task);

            log.info("[CrawlAsync] Crawl completed taskId={}, pages={}, words={}. Starting AI organization.",
                    taskId, crawlResults.size(), totalWordCount);

            // AI 内容整理
            boolean aiSuccess = organizeWithAi(task, crawlResults);
            if (!aiSuccess) {
                // AI 失败时仍标记完成，convertToArticle 会使用原始 Markdown
                log.warn("[CrawlAsync] AI organization failed, task will use raw content. taskId={}", taskId);
            }

            task.updateStatus(CollectTaskStatus.COMPLETED);
            taskRepository.save(task);

        } catch (Exception e) {
            log.error("[CrawlAsync] Failed taskId={}", taskId, e);
            task.markFailed(e.getMessage());
            taskRepository.save(task);
        }
    }

    /**
     * AI 内容整理（含重试：2次重试 + 指数退避）
     * @return true=AI 整理成功，false=失败或不可用
     */
    private boolean organizeWithAi(WebCollectTask task, List<CrawlResult> crawlResults) {
        if (aiContentOrganizer == null) {
            log.info("[AiOrganizer] No AiContentOrganizer bean available, skipping AI organization");
            return false;
        }

        int maxRetries = 2;
        Exception lastException = null;

        for (int attempt = 0; attempt <= maxRetries; attempt++) {
            try {
                AiContentOrganizer.OrganizedContent organized = callAiOrganize(task, crawlResults);

                // 写回 AI 整理结果
                task.markAiCompleted(
                        organized.title,
                        organized.summary,
                        objectMapper.writeValueAsString(organized.keyPoints),
                        objectMapper.writeValueAsString(organized.tags),
                        organized.category,
                        organized.fullContent,
                        organized.durationMs,
                        organized.tokensUsed
                );
                taskRepository.save(task);
                log.info("[AiOrganizer] AI organization completed. taskId={}, title={}, aiDuration={}ms",
                        task.getId(), organized.title, organized.durationMs);
                return true;

            } catch (Exception e) {
                lastException = e;
                // 不可恢复错误：token 截断、API 客户端错误（401/403），直接失败
                if (e instanceof AiOrganizerException.TruncatedException
                        || e instanceof AiOrganizerException.UnrecoverableException) {
                    log.warn("[AiOrganizer] Unrecoverable error ({}), skipping retry. taskId={}",
                            e.getClass().getSimpleName(), task.getId());
                    break;
                }
                if (attempt < maxRetries) {
                    // 429 限速用更长退避（10s），其他错误用指数退避
                    long backoffMs = e instanceof AiOrganizerException.RateLimitException
                            ? 10000 : (long) Math.pow(2, attempt) * 1000;
                    log.warn("[AiOrganizer] Attempt {}/{} failed, retrying in {}ms. taskId={}",
                            attempt + 1, maxRetries + 1, backoffMs, task.getId(), e);
                    try {
                        Thread.sleep(backoffMs);
                    } catch (InterruptedException ie) {
                        Thread.currentThread().interrupt();
                        break;
                    }
                }
            }
        }

        log.error("[AiOrganizer] AI organization failed after {} attempts. taskId={}",
                maxRetries + 1, task.getId(), lastException);
        return false;
    }

    /**
     * 执行一次 AI 整理调用
     */
    private AiContentOrganizer.OrganizedContent callAiOrganize(WebCollectTask task, List<CrawlResult> crawlResults) throws Exception {
        AiTemplate template = AiTemplate.of(task.getAiTemplate());
        CollectTaskType taskType = CollectTaskType.of(task.getTaskType());

        boolean useSinglePage = (taskType != CollectTaskType.KEYWORD) && (crawlResults.size() == 1);

        if (useSinglePage) {
            String rawMarkdown = crawlResults.get(0).getMarkdown();
            if (rawMarkdown == null || rawMarkdown.isBlank()) {
                throw new RuntimeException("No markdown content to organize");
            }
            return aiContentOrganizer.organize(rawMarkdown, template)
                    .get(120, TimeUnit.SECONDS);
        }

        List<AiContentOrganizer.PageContent> pages = crawlResults.stream()
                .filter(CrawlResult::isSuccess)
                .map(r -> {
                    AiContentOrganizer.PageContent pc = new AiContentOrganizer.PageContent();
                    pc.url = r.getUrl();
                    pc.title = r.getTitle();
                    pc.markdown = r.getMarkdown();
                    pc.wordCount = r.getWordCount();
                    pc.depth = r.getDepth();
                    return pc;
                }).toList();
        if (pages.isEmpty()) {
            throw new RuntimeException("No successful pages to organize");
        }

        return aiContentOrganizer.organizeMultiple(pages, template, task.getKeyword())
                .get(180, TimeUnit.SECONDS);
    }

    /**
     * 保存爬取结果到页面表（逐页更新进度）
     */
    private int saveCrawlResults(WebCollectTask task, List<CrawlResult> results) {
        Long taskId = task.getId();
        int totalWordCount = 0;
        int completedPages = 0;
        int sortOrder = 0;
        Set<String> savedUrlHashes = new HashSet<>();

        for (CrawlResult result : results) {
            String urlHash = WebCollectorAppService.hashUrl(result.getUrl());

            // 同任务内 URL 去重：跳过重复页面
            if (savedUrlHashes.contains(urlHash)) {
                log.info("[SaveCrawl] Skipping duplicate URL in task: {}", result.getUrl());
                continue;
            }
            savedUrlHashes.add(urlHash);

            WebCollectPage page = new WebCollectPage();
            page.setTaskId(taskId);
            page.setUrl(result.getUrl());
            page.setPageTitle(result.getTitle());
            page.setUrlHash(urlHash);
            page.setSortOrder(sortOrder++);
            page.setDepth(result.getDepth());

            if (result.isSuccess()) {
                page.setRawMarkdown(result.getMarkdown());
                page.setCrawlStatus(PageCrawlStatus.COMPLETED.getValue());
                page.setWordCount(result.getWordCount());
                page.setCrawlDuration((int) result.getCrawlTimeMs());
                totalWordCount += result.getWordCount();
                completedPages++;

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
                    String normalized = result.getMarkdown().replaceAll("\\s+", "");
                    String contentPreview = normalized.substring(0, Math.min(500, normalized.length()));
                    page.setContentHash(WebCollectorAppService.hashContent(contentPreview));
                }
            } else {
                page.setCrawlStatus(PageCrawlStatus.FAILED.getValue());
                page.setErrorMessage(result.getErrorMessage());
            }

            pageRepository.save(page);

            // 逐页更新进度
            task.setCompletedPages(completedPages);
            taskRepository.save(task);
        }

        return totalWordCount;
    }
}
