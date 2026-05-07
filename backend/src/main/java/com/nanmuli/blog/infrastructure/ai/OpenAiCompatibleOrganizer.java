package com.nanmuli.blog.infrastructure.ai;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.nanmuli.blog.domain.webcollector.AiContentOrganizer;
import com.nanmuli.blog.domain.webcollector.AiOrganizerException;
import com.nanmuli.blog.domain.webcollector.AiTemplate;
import com.nanmuli.blog.domain.webcollector.ContentCategory;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;

import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.TreeMap;
import java.util.concurrent.CompletableFuture;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * OpenAI 兼容端点内容整理器。
 * 支持任意 OpenAI 兼容 API，例如 DashScope、DeepSeek、OpenAI 等。
 */
@Slf4j
@Service
public class OpenAiCompatibleOrganizer implements AiContentOrganizer {

    private final AiConfig aiConfig;
    private final ObjectMapper objectMapper;

    private volatile RestClient cachedRestClient;
    private volatile String cachedConfigHash;

    private static final int SINGLE_PAGE_MAX_CHARS = 80_000;
    private static final int MULTI_PAGE_PER_MAX_CHARS = 20_000;
    private static final int MULTI_PAGE_TOTAL_BUDGET = 150_000;
    private static final int MIN_SUMMARY_LENGTH = 10;
    private static final int MIN_FULL_CONTENT_LENGTH = 20;
    private static final int MAX_KEY_POINTS = 10;
    private static final int MAX_TAGS = 10;

    private static final Set<String> ALLOWED_ORGANIZED_CATEGORIES = Set.of(
            "后端开发", "前端开发", "移动开发", "数据库", "DevOps",
            "云计算", "AI与机器学习", "安全", "区块链", "其他"
    );

    private static final Map<String, String> ORGANIZED_CATEGORY_ALIASES = Map.ofEntries(
            Map.entry("backend", "后端开发"),
            Map.entry("frontend", "前端开发"),
            Map.entry("mobile", "移动开发"),
            Map.entry("database", "数据库"),
            Map.entry("devops", "DevOps"),
            Map.entry("cloud", "云计算"),
            Map.entry("ai", "AI与机器学习"),
            Map.entry("ai/ml", "AI与机器学习"),
            Map.entry("machine learning", "AI与机器学习"),
            Map.entry("security", "安全"),
            Map.entry("blockchain", "区块链"),
            Map.entry("other", "其他")
    );

    private static final String SYSTEM_PROMPT = """
            你是一位资深技术内容编辑，擅长从网页原始内容中提取、整理并重组为高质量技术文章。
            ## 输出规则
            1. 严格输出 JSON，不要包裹在 markdown 代码块中
            2. fullContent 使用 Markdown 格式，代码块请使用 ```language 标记，正文建议 1000-5000 字
            3. 保留原文中有价值的代码示例，不要丢弃关键信息
            4. 英文内容翻译为中文，保留专有名词原文，例如 React、Kubernetes
            5. tags 必须是具体技术关键词，建议 3-7 个，避免过泛标签
            6. category 必须是以下之一：后端开发、前端开发、移动开发、数据库、DevOps、云计算、AI与机器学习、安全、区块链、其他
            7. 如果输入不是有效技术内容，例如登录页、错误页、空白页，请返回一个明确的无效结果，而不是胡乱总结
            8. 忽略导航、Cookie 提示、评论区、分享按钮、广告等与正文无关的内容
            """;

    private static final String OUTPUT_SCHEMA = """

            ## 输出格式
            {
              "title": "吸引人的中文标题（15-30字）",
              "summary": "200-300字核心摘要",
              "keyPoints": ["要点1", "要点2"],
              "tags": ["标签1", "标签2"],
              "category": "后端开发|前端开发|移动开发|数据库|DevOps|云计算|AI与机器学习|安全|区块链|其他",
              "fullContent": "完整 Markdown 格式整理文章"
            }
            """;

    private static final String FEW_SHOT_EXAMPLE = """

            ## 输出示例
            {
              "title": "Spring Boot 3 优雅停机配置详解",
              "summary": "本文讲解 Spring Boot 3 的优雅停机机制，包括 server.shutdown=graceful 配置、SmartLifecycle 资源释放，以及在 Docker 和 Kubernetes 环境中的协同策略。通过合理配置，可以让应用在关闭时安全释放资源并尽可能完成正在处理的请求。",
              "keyPoints": [
                "通过 server.shutdown=graceful 开启内置优雅停机",
                "使用 SmartLifecycle 处理线程池和连接等资源释放",
                "在 Kubernetes 中需要配合 terminationGracePeriodSeconds"
              ],
              "tags": ["Spring Boot 3", "优雅停机", "Kubernetes", "微服务"],
              "category": "后端开发",
              "fullContent": "## Spring Boot 3 优雅停机\\n\\n### 开启优雅停机\\n\\n在 application.yml 中配置：\\n\\n```yaml\\nserver:\\n  shutdown: graceful\\nspring:\\n  lifecycle:\\n    timeout-per-shutdown-phase: 30s\\n```\\n\\n启用后，应用关闭时 Web 服务器会拒绝新的请求，并等待正在处理的请求完成。\\n\\n### 使用 SmartLifecycle 释放资源\\n\\n对于需要自定义清理逻辑的组件，可以实现 SmartLifecycle 接口：\\n\\n```java\\n@Component\\npublic class ResourceCleanup implements SmartLifecycle {\\n    private volatile boolean running = false;\\n\\n    @Override\\n    public void start() {\\n        running = true;\\n    }\\n\\n    @Override\\n    public void stop() {\\n        running = false;\\n    }\\n\\n    @Override\\n    public boolean isRunning() {\\n        return running;\\n    }\\n}\\n```\\n\\n### Kubernetes 中的配合\\n\\n需要在 Pod 配置中预留足够的终止窗口，避免流量仍然打到即将下线的实例。"
            }
            """;

    private static final String DIGEST_SYSTEM_PROMPT_CLEAN = """
            你是一位资深技术资讯编辑，负责生成每日技术日报。
            ## 任务
            根据提供的多个来源内容，生成一份结构化、可读性强的中文技术日报。
            ## 输出规则
            1. 严格输出 JSON，不要包裹在 markdown 代码块中
            2. fullContent 使用 Markdown 格式，包含标题、列表和链接
            3. 每个条目必须压缩为一句话摘要，突出核心信息
            4. 对重复报道进行合并，优先保留信息更完整的来源
            5. 使用中文表达，保留必要的技术专有名词原文
            6. tags 使用具体技术关键词，建议 5-10 个
            ## 输出格式
            {
              "title": "日报标题（含日期）",
              "summary": "200-300 字今日摘要",
              "sections": [
                {
                  "category": "分类代码",
                  "categoryName": "分类显示名",
                  "emoji": "emoji",
                  "items": [
                    {
                      "title": "文章标题",
                      "oneLiner": "一句话摘要",
                      "sourceUrl": "原文链接",
                      "sourceName": "来源域名"
                    }
                  ]
                }
              ],
              "highlight": "今日最值得关注的一条亮点（100 字内）",
              "tags": ["标签1", "标签2"],
              "fullContent": "完整 Markdown 日报正文"
            }

            ## 分类代码对照
            - hot_trend -> 热点动态 -> 🔥
            - open_source -> 开源项目 -> 🌟
            - tech_article -> 技术文章 -> 📖
            - dev_tool -> 开发工具 -> 🔧
            - creative -> 创意发现 -> 💡
            - paper -> 技术论文 -> 📄
            """;

    private static final Pattern JSON_BLOCK = Pattern.compile("```(?:json)?\\s*\\n?([\\s\\S]*?)```");

    public OpenAiCompatibleOrganizer(AiConfig aiConfig, ObjectMapper objectMapper) {
        this.aiConfig = aiConfig;
        this.objectMapper = objectMapper;
    }

    @Override
    public CompletableFuture<OrganizedContent> organize(String rawMarkdown, AiTemplate template) {
        return organize(rawMarkdown, template, null);
    }

    @Override
    public CompletableFuture<OrganizedContent> organize(String rawMarkdown, AiTemplate template, String keywordContext) {
        long start = System.currentTimeMillis();
        try {
            ensureConfigured();
            String userPrompt = buildSinglePagePrompt(rawMarkdown, template, keywordContext);
            AiResponse aiResponse = callAi(SYSTEM_PROMPT, userPrompt);
            OrganizedContent result = parseOrganizedContent(aiResponse.content);
            result.durationMs = (int) (System.currentTimeMillis() - start);
            result.tokensUsed = aiResponse.totalTokens;
            log.info("[AiOrganizer] Single page organized: title={}, provider={}, model={}, duration={}ms, tokens={}",
                    result.title, aiConfig.getProvider(), aiConfig.getModel(), result.durationMs, result.tokensUsed);
            return CompletableFuture.completedFuture(result);
        } catch (Exception e) {
            log.error("[AiOrganizer] organize failed, template={}, provider={}, model={}",
                    template, aiConfig.getProvider(), aiConfig.getModel(), e);
            return CompletableFuture.failedFuture(e);
        }
    }

    @Override
    public CompletableFuture<OrganizedContent> organizeMultiple(List<PageContent> pages, AiTemplate template) {
        return organizeMultiple(pages, template, null);
    }

    @Override
    public CompletableFuture<OrganizedContent> organizeMultiple(List<PageContent> pages, AiTemplate template, String keyword) {
        long start = System.currentTimeMillis();
        try {
            ensureConfigured();
            String userPrompt = buildMultiPagePrompt(pages, template, keyword);
            AiResponse aiResponse = callAi(SYSTEM_PROMPT, userPrompt);
            OrganizedContent result = parseOrganizedContent(aiResponse.content);
            result.durationMs = (int) (System.currentTimeMillis() - start);
            result.tokensUsed = aiResponse.totalTokens;
            log.info("[AiOrganizer] Multi-page organized: title={}, pages={}, provider={}, model={}, duration={}ms, tokens={}",
                    result.title, pages.size(), aiConfig.getProvider(), aiConfig.getModel(), result.durationMs, result.tokensUsed);
            return CompletableFuture.completedFuture(result);
        } catch (Exception e) {
            log.error("[AiOrganizer] organizeMultiple failed", e);
            return CompletableFuture.failedFuture(e);
        }
    }

    @Override
    public CompletableFuture<String> optimizeKeyword(String keyword) {
        if (!aiConfig.isConfigured()) {
            return CompletableFuture.completedFuture(keyword);
        }
        try {
            String systemPrompt = """
                    你是一名搜索关键词优化专家。
                    任务：将用户输入的技术主题优化为更适合搜索引擎查询的关键词。
                    规则：
                    1. 补充必要的技术限定词，减少歧义
                    2. 将口语化表达改写为专业术语
                    3. 保持中文表达，长度尽量控制在 30 字内
                    4. 不要输出解释、引号或代码块，只输出关键词本身
                    """;
            String userPrompt = "用户关键词：" + keyword + "\n优化结果：";

            AiResponse response = callAi(systemPrompt, userPrompt);
            String optimized = response.content != null ? response.content.trim() : keyword;
            optimized = optimized.replaceAll("^```\\w*\\s*", "")
                    .replaceAll("\\s*```$", "")
                    .replaceAll("^[\"']|[\"']$", "")
                    .trim();

            if (optimized.isBlank() || optimized.length() > 100 || optimized.length() < 2) {
                log.warn("[AiKeywordOptimizer] fallback reason=invalid_output original='{}' candidate='{}'",
                        keyword, optimized);
                optimized = keyword;
            }

            if (!optimized.equals(keyword)) {
                log.info("[AiKeywordOptimizer] '{}' -> '{}'", keyword, optimized);
            }
            return CompletableFuture.completedFuture(optimized);
        } catch (Exception e) {
            log.warn("[AiKeywordOptimizer] fallback reason=exception original='{}' message={}",
                    keyword, e.getMessage());
            return CompletableFuture.completedFuture(keyword);
        }
    }

    @Override
    public CompletableFuture<List<String>> expandKeywords(String keyword) {
        if (!aiConfig.isConfigured()) {
            return CompletableFuture.completedFuture(List.of(keyword));
        }
        try {
            String systemPrompt = """
                    你是一名搜索关键词扩展专家。
                    场景：用户在技术博客系统中使用网页采集器，希望获取高质量技术资料。
                    任务：基于输入关键词生成 2-3 个不同的搜索变体。
                    规则：
                    1. 优先保持技术语境，不要偏向泛化搜索
                    2. 对多义词补足技术限定词，例如产品名、厂商名、技术领域
                    3. 不要生成只有“介绍”“功能”之类的宽泛查询
                    4. 严格输出 JSON 数组，不要包裹在 markdown 中
                    5. 每个变体不超过 30 个字，变体之间要有明显差异
                    """;
            String userPrompt = "用户关键词：" + keyword + "\n输出：";

            AiResponse response = callAi(systemPrompt, userPrompt);
            String content = response.content != null ? response.content.trim() : "[]";
            content = content.replaceAll("^```(?:json)?\\s*", "")
                    .replaceAll("\\s*```$", "")
                    .trim();

            @SuppressWarnings("unchecked")
            List<Object> rawList = objectMapper.readValue(content, List.class);
            List<String> keywords = rawList.stream()
                    .map(Object::toString)
                    .map(String::trim)
                    .filter(s -> !s.isBlank() && s.length() <= 100)
                    .filter(s -> !s.equalsIgnoreCase(keyword))
                    .distinct()
                    .limit(3)
                    .toList();

            if (keywords.isEmpty()) {
                log.warn("[AiKeywordExpander] fallback reason=empty_result original='{}'", keyword);
                return CompletableFuture.completedFuture(List.of(keyword));
            }

            log.info("[AiKeywordExpander] '{}' -> {}", keyword, keywords);
            return CompletableFuture.completedFuture(keywords);
        } catch (Exception e) {
            log.warn("[AiKeywordExpander] fallback reason=exception original='{}' message={}",
                    keyword, e.getMessage());
            return CompletableFuture.completedFuture(List.of(keyword));
        }
    }

    @Override
    public CompletableFuture<DigestContent> generateDigest(List<DigestPageContent> pages, String date) {
        long start = System.currentTimeMillis();
        try {
            ensureConfigured();
            String userPrompt = buildDigestPromptClean(pages, date);
            AiResponse aiResponse = callAi(DIGEST_SYSTEM_PROMPT_CLEAN, userPrompt);
            DigestContent result = parseDigestContent(aiResponse.content);
            result.durationMs = (int) (System.currentTimeMillis() - start);
            result.tokensUsed = aiResponse.totalTokens;
            log.info("[AiOrganizer] Digest generated: title={}, provider={}, model={}, duration={}ms, tokens={}",
                    result.title, aiConfig.getProvider(), aiConfig.getModel(), result.durationMs, result.tokensUsed);
            return CompletableFuture.completedFuture(result);
        } catch (Exception e) {
            log.error("[AiOrganizer] generateDigest failed", e);
            return CompletableFuture.failedFuture(e);
        }
    }

    private void ensureConfigured() {
        if (!aiConfig.isConfigured()) {
            throw new AiOrganizerException.UnrecoverableException(
                    "AI not configured: enabled=" + aiConfig.isEnabled()
                            + ", hasKey=" + !aiConfig.getApiKey().isBlank()
                            + ", hasBaseUrl=" + !aiConfig.getBaseUrl().isBlank()
                            + ", hasModel=" + !aiConfig.getModel().isBlank());
        }
    }

    private String buildSinglePagePrompt(String rawMarkdown, AiTemplate template, String keywordContext) {
        String truncated = truncateAtParagraphBoundary(rawMarkdown, SINGLE_PAGE_MAX_CHARS);

        String roleInstruction = switch (template) {
            case TECH_SUMMARY -> """
                    请对以下网页内容进行深度阅读和结构化整理。
                    重点：提炼核心技术要点，梳理逻辑脉络，补充必要背景，输出一篇结构清晰的技术摘要。
                    """;
            case TUTORIAL -> """
                    请将以下内容整理为循序渐进的 step-by-step 教程。
                    重点：拆解学习路径，明确每一步的操作、代码和预期结果，并提示常见坑点。
                    """;
            case COMPARISON -> """
                    请对以下内容进行分析，提取技术方案对比信息。
                    重点：总结方案差异、适用场景、优缺点，并尽量形成可读的对比结构。
                    """;
            default -> """
                    请对以下网页内容进行深度阅读和结构化整理。
                    根据内容所属技术领域，自动选择最合适的分类和标签。
                    """;
        };

        StringBuilder sb = new StringBuilder(roleInstruction).append('\n');
        appendKeywordContextSection(sb, keywordContext);
        sb.append("## 原始内容\n")
                .append(truncated)
                .append("\n")
                .append(OUTPUT_SCHEMA)
                .append(FEW_SHOT_EXAMPLE);
        return sb.toString();
    }

    private String buildMultiPagePrompt(List<PageContent> pages, AiTemplate template, String keywordContext) {
        String roleInstruction = switch (template) {
            case TECH_SUMMARY -> """
                    以下是从多个来源收集的技术内容，请进行综合分析和结构化整理。
                    重点：提炼共识，去重合并重复信息，保留互补细节，并形成一篇可直接沉淀的技术总结。
                    """;
            case TUTORIAL -> """
                    以下是从多个来源收集的教程相关内容，请整合为一篇循序渐进的教程。
                    重点：统一步骤顺序，补足缺失环节，去除重复说明，保留关键代码与注意事项。
                    """;
            case COMPARISON -> """
                    以下是从多个来源收集的内容，请进行横向技术方案对比。
                    重点：总结差异、适用场景和推荐建议，尽量用结构化方式呈现。
                    """;
            case KNOWLEDGE_REPORT -> """
                    以下是从多个来源收集的内容，请生成一份综合性的知识报告。
                    重点：包含背景概览、核心原理、现状分析、趋势判断和主要参考来源。
                    """;
            default -> """
                    以下是从多个来源收集的内容，请进行综合分析整理，去重合并并输出结构化文章。
                    """;
        };

        StringBuilder sb = new StringBuilder(roleInstruction).append('\n');
        appendKeywordContextSection(sb, keywordContext);
        sb.append("## 来源内容\n\n");

        List<PageContent> sortedPages = pages.stream()
                .sorted((a, b) -> Integer.compare(
                        b.markdown != null ? b.markdown.length() : 0,
                        a.markdown != null ? a.markdown.length() : 0))
                .toList();

        int remainingBudget = MULTI_PAGE_TOTAL_BUDGET;
        for (int i = 0; i < sortedPages.size(); i++) {
            PageContent page = sortedPages.get(i);
            sb.append("### 来源 ").append(i + 1).append(": ")
                    .append(page.title != null ? page.title : "未知标题").append('\n');
            sb.append("URL: ").append(page.url != null ? page.url : "未知").append("\n\n");

            String markdown = page.markdown != null ? page.markdown : "";
            int perPageBudget = Math.min(MULTI_PAGE_PER_MAX_CHARS, remainingBudget);
            if (perPageBudget <= 0) {
                sb.append("[已达到总输入预算上限，后续来源已省略]\n\n");
                continue;
            }
            markdown = truncateAtParagraphBoundary(markdown, perPageBudget);
            sb.append(markdown).append("\n\n---\n\n");
            remainingBudget -= markdown.length();
        }

        sb.append(OUTPUT_SCHEMA).append(FEW_SHOT_EXAMPLE);
        return sb.toString();
    }

    private void appendKeywordContextSection(StringBuilder sb, String keywordContext) {
        if (keywordContext == null || keywordContext.isBlank()) {
            return;
        }
        sb.append("## 搜索上下文\n");
        sb.append(keywordContext.trim()).append("\n");
        sb.append("请优先围绕以上实际搜索意图组织内容，避免被来源页面中的旁支主题带偏。\n\n");
    }

    private static class AiResponse {
        String content;
        int totalTokens;
        String finishReason;
    }

    private AiResponse callAi(String systemPrompt, String userPrompt) {
        RestClient restClient = getRestClient();

        Map<String, Object> requestBody = new LinkedHashMap<>();
        requestBody.put("model", aiConfig.getModel());
        requestBody.put("temperature", aiConfig.getTemperature());
        requestBody.put("messages", List.of(
                Map.of("role", "system", "content", systemPrompt),
                Map.of("role", "user", "content", userPrompt)
        ));

        String response = restClient.post()
                .uri("/chat/completions")
                .body(requestBody)
                .retrieve()
                .onStatus(status -> status.is4xxClientError() && status.value() != 429,
                        (req, resp) -> {
                            String body = new String(resp.getBody().readAllBytes(), StandardCharsets.UTF_8);
                            log.error("[AiOrganizer] Unrecoverable API error: status={}, body={}", resp.getStatusCode(), body);
                            throw new AiOrganizerException.UnrecoverableException(
                                    "API client error " + resp.getStatusCode() + ": " + body);
                        })
                .onStatus(status -> status.value() == 429,
                        (req, resp) -> {
                            String body = new String(resp.getBody().readAllBytes(), StandardCharsets.UTF_8);
                            log.warn("[AiOrganizer] Rate limited by API: {}", body);
                            throw new AiOrganizerException.RateLimitException("Rate limited");
                        })
                .onStatus(status -> status.is5xxServerError(),
                        (req, resp) -> {
                            String body = new String(resp.getBody().readAllBytes(), StandardCharsets.UTF_8);
                            log.warn("[AiOrganizer] API server error: status={}, body={}", resp.getStatusCode(), body);
                            throw new RuntimeException("API server error " + resp.getStatusCode());
                        })
                .body(String.class);

        try {
            @SuppressWarnings("unchecked")
            Map<String, Object> respMap = objectMapper.readValue(response, Map.class);

            AiResponse aiResponse = new AiResponse();
            @SuppressWarnings("unchecked")
            List<Map<String, Object>> choices = (List<Map<String, Object>>) respMap.get("choices");
            if (choices != null && !choices.isEmpty()) {
                for (Map<String, Object> choice : choices) {
                    @SuppressWarnings("unchecked")
                    Map<String, Object> message = (Map<String, Object>) choice.get("message");
                    String content = extractMessageContent(message != null ? message.get("content") : null);
                    if (!content.isBlank()) {
                        aiResponse.content = content;
                        Object finishReason = choice.get("finish_reason");
                        aiResponse.finishReason = finishReason != null ? finishReason.toString() : "unknown";
                        break;
                    }
                }
            }

            if (aiResponse.content == null) {
                throw new RuntimeException("Unexpected API response format: no content");
            }
            if (aiResponse.finishReason == null) {
                aiResponse.finishReason = "unknown";
            }

            @SuppressWarnings("unchecked")
            Map<String, Object> usage = (Map<String, Object>) respMap.get("usage");
            if (usage != null && usage.get("total_tokens") != null) {
                aiResponse.totalTokens = ((Number) usage.get("total_tokens")).intValue();
            }

            if ("length".equals(aiResponse.finishReason)) {
                log.warn("[AiOrganizer] finish_reason=length, output truncated, tokens={}", aiResponse.totalTokens);
                throw new AiOrganizerException.TruncatedException(
                        "AI output truncated (finish_reason=length), tokens=" + aiResponse.totalTokens);
            }

            return aiResponse;
        } catch (RuntimeException e) {
            throw e;
        } catch (Exception e) {
            throw new RuntimeException("Failed to parse AI response: " + e.getMessage(), e);
        }
    }

    private String extractMessageContent(Object content) {
        if (content instanceof String str) {
            return str.trim();
        }
        if (content instanceof List<?> parts) {
            StringBuilder sb = new StringBuilder();
            for (Object part : parts) {
                if (part instanceof Map<?, ?> map) {
                    Object text = map.get("text");
                    if (text != null) {
                        if (sb.length() > 0) {
                            sb.append('\n');
                        }
                        sb.append(text);
                    }
                } else if (part != null) {
                    if (sb.length() > 0) {
                        sb.append('\n');
                    }
                    sb.append(part);
                }
            }
            return sb.toString().trim();
        }
        return "";
    }

    private RestClient getRestClient() {
        String currentHash = buildConfigHash();
        if (cachedRestClient == null || !currentHash.equals(cachedConfigHash)) {
            synchronized (this) {
                if (cachedRestClient == null || !currentHash.equals(cachedConfigHash)) {
                    cachedRestClient = buildRestClient();
                    cachedConfigHash = currentHash;
                    log.info("[AiOrganizer] RestClient rebuilt for provider={}, model={}, baseUrl={}",
                            aiConfig.getProvider(), aiConfig.getModel(), aiConfig.getBaseUrl());
                }
            }
        }
        return cachedRestClient;
    }

    private String buildConfigHash() {
        return aiConfig.getBaseUrl() + "|"
                + aiConfig.getApiKey().hashCode() + "|"
                + aiConfig.getModel() + "|"
                + aiConfig.getConnectTimeoutSeconds() + "|"
                + aiConfig.getReadTimeoutSeconds();
    }

    private RestClient buildRestClient() {
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(Duration.ofSeconds(aiConfig.getConnectTimeoutSeconds()));
        factory.setReadTimeout(Duration.ofSeconds(aiConfig.getReadTimeoutSeconds()));
        return RestClient.builder()
                .baseUrl(aiConfig.getBaseUrl())
                .defaultHeader("Authorization", "Bearer " + aiConfig.getApiKey())
                .defaultHeader("Content-Type", "application/json")
                .requestFactory(factory)
                .build();
    }

    @SuppressWarnings("unchecked")
    private OrganizedContent parseOrganizedContent(String response) throws Exception {
        String json = extractJson(response);
        try {
            Map<String, Object> map = objectMapper.readValue(json, Map.class);

            OrganizedContent content = new OrganizedContent();
            content.title = normalizeText(map.get("title"));
            content.summary = normalizeText(map.get("summary"));
            content.keyPoints = normalizeStringList(map.get("keyPoints"), MAX_KEY_POINTS);
            content.tags = normalizeStringList(map.get("tags"), MAX_TAGS);
            content.category = normalizeOrganizedCategory(map.get("category"));
            content.fullContent = normalizeText(map.get("fullContent"));
            validateOrganizedContent(content);
            return content;
        } catch (Exception e) {
            log.error("[AiOrganizer] JSON parse failed. Raw (first 500): {}",
                    json.substring(0, Math.min(500, json.length())));
            throw e;
        }
    }

    private void validateOrganizedContent(OrganizedContent content) {
        if (content.title.isBlank()) {
            throw new AiOrganizerException.InvalidOutputException("AI organized content missing title");
        }
        if (content.summary.isBlank() || content.summary.length() < MIN_SUMMARY_LENGTH) {
            throw new AiOrganizerException.InvalidOutputException("AI organized content summary too short");
        }
        if (content.fullContent.isBlank() || content.fullContent.length() < MIN_FULL_CONTENT_LENGTH) {
            throw new AiOrganizerException.InvalidOutputException("AI organized content fullContent too short");
        }
        if (content.keyPoints == null || content.keyPoints.isEmpty()) {
            throw new AiOrganizerException.InvalidOutputException("AI organized content missing keyPoints");
        }
        if (content.tags == null || content.tags.isEmpty()) {
            throw new AiOrganizerException.InvalidOutputException("AI organized content missing tags");
        }
        if (!ALLOWED_ORGANIZED_CATEGORIES.contains(content.category)) {
            throw new AiOrganizerException.InvalidOutputException("AI organized content category invalid");
        }
    }

    private String extractJson(String response) {
        Matcher matcher = JSON_BLOCK.matcher(response);
        if (matcher.find()) {
            String candidate = matcher.group(1).trim();
            try {
                objectMapper.readValue(candidate, Map.class);
                return candidate;
            } catch (Exception ignored) {
            }
        }
        int start = response.indexOf('{');
        if (start < 0) {
            throw new RuntimeException("No JSON found in AI response");
        }
        int depth = 0;
        boolean inString = false;
        boolean escape = false;
        for (int i = start; i < response.length(); i++) {
            char c = response.charAt(i);
            if (escape) {
                escape = false;
                continue;
            }
            if (c == '\\' && inString) {
                escape = true;
                continue;
            }
            if (c == '"') {
                inString = !inString;
                continue;
            }
            if (inString) {
                continue;
            }
            if (c == '{') {
                depth++;
            } else if (c == '}') {
                depth--;
                if (depth == 0) {
                    return response.substring(start, i + 1);
                }
            }
        }
        throw new RuntimeException("No balanced JSON found in AI response");
    }

    private String asString(Object value) {
        return value == null ? "" : value.toString();
    }

    private String normalizeText(Object value) {
        return asString(value).trim();
    }

    private List<String> normalizeStringList(Object obj, int maxItems) {
        if (!(obj instanceof List<?> list)) {
            return Collections.emptyList();
        }
        return list.stream()
                .map(this::normalizeText)
                .filter(s -> !s.isBlank())
                .distinct()
                .limit(maxItems)
                .toList();
    }

    private String normalizeOrganizedCategory(Object value) {
        String raw = normalizeText(value);
        if (raw.isBlank()) {
            return raw;
        }
        return ORGANIZED_CATEGORY_ALIASES.getOrDefault(raw.toLowerCase(Locale.ROOT), raw);
    }

    private String normalizeDigestCategory(Object value) {
        String raw = normalizeText(value);
        if (raw.isBlank()) {
            return raw;
        }
        ContentCategory category = ContentCategory.of(raw.toLowerCase(Locale.ROOT));
        return category != null ? category.getCode() : raw;
    }

    private static String truncateAtParagraphBoundary(String text, int maxLen) {
        if (text.length() <= maxLen) {
            return text;
        }
        int cutPos = text.lastIndexOf("\n\n", maxLen);
        if (cutPos < maxLen * 0.8) {
            cutPos = text.lastIndexOf('\n', maxLen);
        }
        if (cutPos < maxLen * 0.5) {
            cutPos = maxLen;
        }
        return text.substring(0, cutPos) + "\n\n[...内容过长已截断]";
    }

    private String buildDigestPrompt(List<DigestPageContent> pages, String date) {
        return buildDigestPromptClean(pages, date);
    }

    private String buildDigestPromptClean(List<DigestPageContent> pages, String date) {
        StringBuilder sb = new StringBuilder();
        sb.append("## 日报日期\n").append(date).append("\n\n");
        sb.append("## 来源内容\n\n");

        Map<String, List<DigestPageContent>> byCategory = pages.stream()
                .filter(p -> p.markdown != null && !p.markdown.isBlank())
                .collect(java.util.stream.Collectors.groupingBy(p ->
                                p.category != null ? p.category.getCode() : "tech_article",
                        TreeMap::new,
                        java.util.stream.Collectors.collectingAndThen(
                                java.util.stream.Collectors.toList(),
                                list -> list.stream()
                                        .sorted(Comparator
                                                .comparing((DigestPageContent p) -> asString(p.title))
                                                .thenComparing(p -> asString(p.url)))
                                        .toList()
                        )));

        int remainingBudget = MULTI_PAGE_TOTAL_BUDGET;
        for (Map.Entry<String, List<DigestPageContent>> entry : byCategory.entrySet()) {
            sb.append("### 分类: ").append(entry.getKey()).append("\n\n");
            for (int i = 0; i < entry.getValue().size(); i++) {
                DigestPageContent page = entry.getValue().get(i);
                sb.append("#### 来源 ").append(i + 1).append(": ")
                        .append(page.title != null ? page.title : "未知标题").append('\n');
                sb.append("URL: ").append(page.url != null ? page.url : "未知").append('\n');
                if (page.summary != null && !page.summary.isBlank()) {
                    sb.append("摘要: ").append(page.summary).append('\n');
                }

                String markdown = page.markdown != null ? page.markdown : "";
                int budget = Math.min(MULTI_PAGE_PER_MAX_CHARS, remainingBudget);
                if (budget <= 0) {
                    sb.append("[已达到总输入预算上限，后续来源已省略]\n\n");
                    continue;
                }
                markdown = truncateAtParagraphBoundary(markdown, budget);
                sb.append(markdown).append("\n\n---\n\n");
                remainingBudget -= markdown.length();
            }
        }

        sb.append("\n请根据以上内容生成结构化技术日报。");
        return sb.toString();
    }

    @SuppressWarnings("unchecked")
    private DigestContent parseDigestContent(String response) throws Exception {
        String json = extractJson(response);
        try {
            Map<String, Object> map = objectMapper.readValue(json, Map.class);

            DigestContent content = new DigestContent();
            content.title = normalizeText(map.get("title"));
            content.summary = normalizeText(map.get("summary"));
            content.highlight = normalizeText(map.get("highlight"));
            content.tags = normalizeStringList(map.get("tags"), MAX_TAGS);
            content.fullContent = normalizeText(map.get("fullContent"));

            Object sectionsObj = map.get("sections");
            if (sectionsObj instanceof List<?> sectionsRaw) {
                content.sections = new ArrayList<>();
                for (Object secObj : sectionsRaw) {
                    if (!(secObj instanceof Map<?, ?> secMap)) {
                        continue;
                    }
                    DigestSection section = new DigestSection();
                    section.category = normalizeDigestCategory(secMap.get("category"));
                    section.categoryName = normalizeText(secMap.get("categoryName"));
                    section.emoji = normalizeText(secMap.get("emoji"));

                    Object itemsObj = secMap.get("items");
                    if (itemsObj instanceof List<?> itemsRaw) {
                        section.items = new ArrayList<>();
                        for (Object itemObj : itemsRaw) {
                            if (!(itemObj instanceof Map<?, ?> itemMap)) {
                                continue;
                            }
                            DigestItem item = new DigestItem();
                            item.title = normalizeText(itemMap.get("title"));
                            item.oneLiner = normalizeText(itemMap.get("oneLiner"));
                            item.sourceUrl = normalizeText(itemMap.get("sourceUrl"));
                            item.sourceName = normalizeText(itemMap.get("sourceName"));
                            section.items.add(item);
                        }
                    } else {
                        section.items = Collections.emptyList();
                    }
                    content.sections.add(section);
                }
            } else {
                content.sections = Collections.emptyList();
            }

            validateDigestContent(content);
            return content;
        } catch (Exception e) {
            log.error("[AiOrganizer] Digest JSON parse failed. Raw (first 500): {}",
                    json.substring(0, Math.min(500, json.length())));
            throw e;
        }
    }

    private void validateDigestContent(DigestContent content) {
        if (content.title.isBlank()) {
            throw new AiOrganizerException.InvalidOutputException("AI digest content missing title");
        }
        if (content.summary.isBlank() || content.summary.length() < MIN_SUMMARY_LENGTH) {
            throw new AiOrganizerException.InvalidOutputException("AI digest content summary too short");
        }
        if (content.fullContent.isBlank() || content.fullContent.length() < MIN_FULL_CONTENT_LENGTH) {
            throw new AiOrganizerException.InvalidOutputException("AI digest content fullContent too short");
        }
        if (content.tags == null || content.tags.isEmpty()) {
            throw new AiOrganizerException.InvalidOutputException("AI digest content missing tags");
        }
        boolean hasValidItem = content.sections != null && content.sections.stream()
                .filter(Objects::nonNull)
                .anyMatch(section -> {
                    if (section.category.isBlank() || ContentCategory.of(section.category) == null) {
                        return false;
                    }
                    if (section.categoryName.isBlank()) {
                        return false;
                    }
                    return section.items != null && section.items.stream()
                            .filter(Objects::nonNull)
                            .anyMatch(item -> !item.title.isBlank()
                                    && !item.oneLiner.isBlank()
                                    && !item.sourceUrl.isBlank()
                                    && !item.sourceName.isBlank());
                });
        if (!hasValidItem) {
            throw new AiOrganizerException.InvalidOutputException("AI digest content missing valid items");
        }
    }
}
