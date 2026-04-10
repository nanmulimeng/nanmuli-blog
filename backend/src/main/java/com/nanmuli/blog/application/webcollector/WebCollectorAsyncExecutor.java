package com.nanmuli.blog.application.webcollector;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.nanmuli.blog.domain.webcollector.*;
import com.nanmuli.blog.infrastructure.crawler.CrawlResult;
import com.nanmuli.blog.infrastructure.crawler.CrawlerService;
import com.nanmuli.blog.shared.exception.BusinessException;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;

import java.util.Collections;
import java.util.List;

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

            // Phase 1: 爬取完成后设为 PROCESSING（AI 整理步骤待 Phase 2 实现）
            task.setStatus(CollectTaskStatus.PROCESSING);
            taskRepository.save(task);

            log.info("[CrawlAsync] Crawl completed taskId={}, pages={}, words={}. AI processing pending.",
                    taskId, crawlResults.size(), totalWordCount);

            // TODO: Phase 2 - 调用 AiContentOrganizer 进行 AI 整理
            // organizedContent = aiContentOrganizer.organize(...)
            // task.markAiCompleted(...)

            // Phase 1 临时：AI 整理未实现时直接标记完成
            task.setStatus(CollectTaskStatus.COMPLETED);
            taskRepository.save(task);

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
            page.setUrlHash(WebCollectorAppService.hashUrl(result.getUrl()));
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
                    String normalized = result.getMarkdown().replaceAll("\\s+", "");
                    String contentPreview = normalized.substring(0, Math.min(500, normalized.length()));
                    page.setContentHash(WebCollectorAppService.hashContent(contentPreview));
                }
            } else {
                page.setCrawlStatus(PageCrawlStatus.FAILED.getValue());
                page.setErrorMessage(result.getErrorMessage());
            }

            pageRepository.save(page);
        }

        return totalWordCount;
    }
}
