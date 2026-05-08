package com.nanmuli.blog.application.webcollector;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.nanmuli.blog.domain.webcollector.*;
import com.nanmuli.blog.infrastructure.crawler.CrawlResult;
import com.nanmuli.blog.infrastructure.crawler.CrawlerService;
import com.nanmuli.blog.shared.exception.BusinessException;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.*;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

import java.time.LocalDate;
import java.util.*;

/**
 * 爬取异步执行器。
 * 编排爬取（调用 Python 爬虫服务）+ AI 整理（调用 Python AI 端点）。
 * AI 整理逻辑已迁移到 Python 服务，Java 仅做 HTTP 调用。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class WebCollectorAsyncExecutor {

    private final WebCollectTaskRepository taskRepository;
    private final WebCollectPageRepository pageRepository;
    private final CrawlerService crawlerService;
    private final ObjectMapper objectMapper;

    @Value("${crawler.service.base-url:http://localhost:8500}")
    private String crawlerBaseUrl;

    @Value("${blog.ai.organizer.max-retries:2}")
    private int maxRetries;

    private final RestTemplate organizeRestTemplate = new RestTemplate();

    /**
     * 异步执行爬取任务
     */
    @Async("crawlerTaskExecutor")
    public void executeCrawlAsync(Long taskId) {
        log.info("[CrawlAsync] Starting taskId={}", taskId);

        WebCollectTask task = taskRepository.findById(taskId)
                .orElseThrow(() -> new BusinessException("任务不存在"));

        try {
            task.updateStatus(CollectTaskStatus.CRAWLING);
            taskRepository.save(task);

            long crawlStartTime = System.currentTimeMillis();
            List<CrawlResult> crawlResults;
            String aiSearchContext = null;

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
                            task.getSourceUrl(), task.getMaxDepth(), task.getMaxPages(), config
                    );
                    task.setTotalPages(crawlResults.size());
                }
                case KEYWORD -> {
                    config.setTimeRange(task.getTimeRange() != null ? task.getTimeRange() : "week");

                    // AI 关键词优化 + 扩展（调用 Python 端点）
                    String optimizedKeyword = callKeywordOptimize(task.getKeyword());
                    List<String> keywords = new ArrayList<>();
                    keywords.add(optimizedKeyword);
                    keywords.addAll(callKeywordExpand(optimizedKeyword));
                    keywords = keywords.stream().distinct().limit(4).toList();

                    aiSearchContext = buildKeywordAiContext(task.getKeyword(), optimizedKeyword, keywords);
                    task.setAiSearchMetadata(buildKeywordAiMetadata(task.getKeyword(), optimizedKeyword, keywords));
                    taskRepository.save(task);

                    // 对每个关键词搜索爬取，合并去重
                    Set<String> seenUrls = new HashSet<>();
                    crawlResults = new ArrayList<>();
                    int maxPagesPerKeyword = Math.max(8, task.getMaxPages());
                    int consecutiveNoNew = 0;

                    for (int i = 0; i < keywords.size(); i++) {
                        String kw = keywords.get(i);
                        int beforeSize = crawlResults.size();
                        try {
                            List<CrawlResult> results = crawlerService.crawlByKeyword(
                                    kw, task.getSearchEngine(), maxPagesPerKeyword, config
                            );
                            for (CrawlResult r : results) {
                                if (r.getUrl() != null && !r.getUrl().isBlank()
                                        && !seenUrls.contains(r.getUrl())) {
                                    seenUrls.add(r.getUrl());
                                    crawlResults.add(r);
                                }
                            }
                            int newUrls = crawlResults.size() - beforeSize;

                            if (i > 0 && newUrls == 0) {
                                consecutiveNoNew++;
                                if (consecutiveNoNew >= 2) break;
                            } else {
                                consecutiveNoNew = 0;
                            }

                            if (crawlResults.size() >= task.getMaxPages()) break;
                            if (i < keywords.size() - 1) Thread.sleep(2000);
                        } catch (Exception e) {
                            log.warn("[CrawlAsync] Keyword search failed for '{}': {}", kw, e.getMessage());
                        }
                    }
                    task.setTotalPages(crawlResults.size());
                }
                case DIGEST -> throw new BusinessException("日报任务请通过 /api/admin/collector/digest/trigger 触发");
                default -> throw new BusinessException("不支持的任务类型");
            }

            int crawlDuration = (int) (System.currentTimeMillis() - crawlStartTime);
            int totalWordCount = saveCrawlResults(task, crawlResults);
            task.setCrawlDuration(crawlDuration);
            task.setTotalWordCount(totalWordCount);

            if (task.getCompletedPages() == null || task.getCompletedPages() == 0) {
                String errorMsg = crawlResults.stream()
                        .filter(r -> r.getErrorMessage() != null)
                        .map(CrawlResult::getErrorMessage)
                        .findFirst()
                        .orElse("所有页面爬取失败，未获取到有效内容");
                task.markFailed(errorMsg);
                taskRepository.save(task);
                return;
            }

            // Phase 2: AI 整理（调用 Python 端点）
            task.updateStatus(CollectTaskStatus.PROCESSING);
            taskRepository.save(task);

            boolean aiSuccess = organizeWithPython(task, crawlResults, aiSearchContext);
            if (!aiSuccess) {
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

    // ============== AI Organization via Python ==============

    /**
     * 调用 Python 的 /crawl/organize 端点进行 AI 整理
     */
    private boolean organizeWithPython(WebCollectTask task, List<CrawlResult> crawlResults, String keywordContext) {
        for (int attempt = 0; attempt <= maxRetries; attempt++) {
            try {
                String template = task.getAiTemplate() != null ? task.getAiTemplate() : "tech_summary";

                // 构建请求体
                List<Map<String, Object>> pages = new ArrayList<>();
                for (CrawlResult r : crawlResults) {
                    if (!r.isSuccess()) continue;
                    Map<String, Object> page = new LinkedHashMap<>();
                    page.put("url", r.getUrl());
                    page.put("title", r.getTitle());
                    page.put("markdown", r.getMarkdown());
                    page.put("word_count", r.getWordCount());
                    pages.add(page);
                }

                if (pages.isEmpty()) {
                    log.warn("[AiOrganizer] No successful pages to organize. taskId={}", task.getId());
                    return false;
                }

                Map<String, Object> requestBody = new LinkedHashMap<>();
                requestBody.put("pages", pages);
                requestBody.put("template", template);
                requestBody.put("keyword_context", keywordContext);

                HttpHeaders headers = new HttpHeaders();
                headers.setContentType(MediaType.APPLICATION_JSON);

                ResponseEntity<JsonNode> response = organizeRestTemplate.exchange(
                        crawlerBaseUrl + "/crawl/organize",
                        HttpMethod.POST,
                        new HttpEntity<>(requestBody, headers),
                        JsonNode.class
                );

                JsonNode body = response.getBody();
                if (body == null || !body.path("success").asBoolean(false)) {
                    String error = body != null ? body.path("error_message").asText("Unknown error") : "Empty response";
                    throw new RuntimeException("AI organization failed: " + error);
                }

                // 解析并保存结果
                task.markAiCompleted(
                        body.path("title").asText(""),
                        body.path("summary").asText(""),
                        objectMapper.writeValueAsString(
                                objectMapper.convertValue(body.path("key_points"), List.class)),
                        objectMapper.writeValueAsString(
                                objectMapper.convertValue(body.path("tags"), List.class)),
                        body.path("category").asText(""),
                        body.path("full_content").asText(""),
                        body.path("duration_ms").asInt(0),
                        body.path("tokens_used").asInt(0)
                );
                taskRepository.save(task);
                log.info("[AiOrganizer] AI organized via Python. taskId={}, title={}, duration={}ms",
                        task.getId(), body.path("title").asText(), body.path("duration_ms").asInt());
                return true;

            } catch (Exception e) {
                if (attempt < maxRetries) {
                    long backoffMs = (long) Math.pow(2, attempt) * 1000;
                    log.warn("[AiOrganizer] Attempt {}/{} failed, retrying in {}ms. taskId={}",
                            attempt + 1, maxRetries + 1, backoffMs, task.getId(), e);
                    try {
                        Thread.sleep(backoffMs);
                    } catch (InterruptedException ie) {
                        Thread.currentThread().interrupt();
                        break;
                    }
                } else {
                    log.error("[AiOrganizer] AI organization failed after {} attempts. taskId={}",
                            maxRetries + 1, task.getId(), e);
                }
            }
        }
        return false;
    }

    /**
     * 调用 Python 的 /crawl/keyword 端点进行关键词优化
     */
    private String callKeywordOptimize(String keyword) {
        try {
            Map<String, Object> request = Map.of("keyword", keyword, "action", "optimize");
            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.APPLICATION_JSON);
            ResponseEntity<JsonNode> response = organizeRestTemplate.exchange(
                    crawlerBaseUrl + "/crawl/keyword",
                    HttpMethod.POST, new HttpEntity<>(request, headers), JsonNode.class
            );
            JsonNode body = response.getBody();
            if (body != null && body.path("success").asBoolean(false)) {
                String optimized = body.path("optimized").asText(keyword);
                if (!optimized.isBlank() && !optimized.equalsIgnoreCase(keyword)) {
                    log.info("[KeywordOptimize] '{}' -> '{}'", keyword, optimized);
                    return optimized;
                }
            }
        } catch (Exception e) {
            log.warn("[KeywordOptimize] Failed, using original: '{}'", keyword);
        }
        return keyword;
    }

    /**
     * 调用 Python 的 /crawl/keyword 端点进行关键词扩展
     */
    private List<String> callKeywordExpand(String keyword) {
        try {
            Map<String, Object> request = Map.of("keyword", keyword, "action", "expand");
            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.APPLICATION_JSON);
            ResponseEntity<JsonNode> response = organizeRestTemplate.exchange(
                    crawlerBaseUrl + "/crawl/keyword",
                    HttpMethod.POST, new HttpEntity<>(request, headers), JsonNode.class
            );
            JsonNode body = response.getBody();
            if (body != null && body.path("success").asBoolean(false)) {
                List<String> variants = new ArrayList<>();
                JsonNode arr = body.path("variants");
                if (arr.isArray()) {
                    for (JsonNode item : arr) {
                        String v = item.asText().trim();
                        if (!v.isBlank() && !v.equalsIgnoreCase(keyword)) {
                            variants.add(v);
                        }
                    }
                }
                if (!variants.isEmpty()) {
                    log.info("[KeywordExpand] '{}' -> {}", keyword, variants);
                    return variants.stream().limit(3).toList();
                }
            }
        } catch (Exception e) {
            log.warn("[KeywordExpand] Failed for '{}'", keyword);
        }
        return List.of();
    }

    // ============== Save Results ==============

    private int saveCrawlResults(WebCollectTask task, List<CrawlResult> results) {
        Long taskId = task.getId();
        int totalWordCount = 0;
        int completedPages = 0;
        int sortOrder = 0;
        Set<String> savedUrlHashes = new HashSet<>();

        for (CrawlResult result : results) {
            if (result.getUrl() == null || result.getUrl().isBlank()) continue;

            String urlHash = WebCollectorAppService.hashUrl(result.getUrl());
            if (savedUrlHashes.contains(urlHash)) continue;
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

                if (result.getMetadata() != null) {
                    try {
                        page.setPageMetadata(objectMapper.writeValueAsString(result.getMetadata()));
                    } catch (JsonProcessingException e) {
                        log.warn("Failed to serialize metadata: {}", e.getMessage());
                    }
                }
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
            task.setCompletedPages(completedPages);
            taskRepository.save(task);
        }
        return totalWordCount;
    }

    // ============== Keyword Helpers ==============

    private String buildKeywordAiContext(String originalKeyword, String optimizedKeyword, List<String> keywords) {
        LinkedHashSet<String> normalized = new LinkedHashSet<>();
        if (keywords != null) keywords.stream().filter(k -> k != null && !k.isBlank()).map(String::trim).forEach(normalized::add);
        if (normalized.isEmpty()) {
            if (optimizedKeyword != null && !optimizedKeyword.isBlank()) normalized.add(optimizedKeyword.trim());
            else if (originalKeyword != null && !originalKeyword.isBlank()) normalized.add(originalKeyword.trim());
        }

        List<String> lines = new ArrayList<>();
        if (originalKeyword != null && !originalKeyword.isBlank()) lines.add("原始关键词：" + originalKeyword.trim());
        if (optimizedKeyword != null && !optimizedKeyword.isBlank()
                && (originalKeyword == null || !optimizedKeyword.equalsIgnoreCase(originalKeyword.trim()))) {
            lines.add("优化关键词：" + optimizedKeyword.trim());
        }
        if (!normalized.isEmpty()) lines.add("实际搜索词变体：" + String.join(" | ", normalized));
        return lines.isEmpty() ? null : String.join("\n", lines);
    }

    private String buildKeywordAiMetadata(String originalKeyword, String optimizedKeyword, List<String> keywords) {
        LinkedHashSet<String> normalized = new LinkedHashSet<>();
        if (keywords != null) keywords.stream().filter(k -> k != null && !k.isBlank()).map(String::trim).forEach(normalized::add);

        LinkedHashMap<String, Object> metadata = new LinkedHashMap<>();
        if (originalKeyword != null && !originalKeyword.isBlank()) metadata.put("originalKeyword", originalKeyword.trim());
        if (optimizedKeyword != null && !optimizedKeyword.isBlank()) metadata.put("optimizedKeyword", optimizedKeyword.trim());
        metadata.put("searchVariants", new ArrayList<>(normalized));

        try {
            return objectMapper.writeValueAsString(metadata);
        } catch (JsonProcessingException e) {
            log.warn("[CrawlAsync] Failed to serialize keyword AI metadata: {}", e.getMessage());
            return null;
        }
    }
}
