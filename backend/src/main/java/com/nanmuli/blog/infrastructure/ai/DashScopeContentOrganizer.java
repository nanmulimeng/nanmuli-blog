package com.nanmuli.blog.infrastructure.ai;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.nanmuli.blog.domain.webcollector.AiContentOrganizer;
import com.nanmuli.blog.domain.webcollector.AiTemplate;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.autoconfigure.condition.ConditionalOnExpression;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.web.client.RestClient;

import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * 基于 DashScope OpenAI 兼容端点的内容整理实现
 * 使用 RestClient 直接调用 compatible-mode 端点，绕过 Spring AI Alibaba 的原生格式问题
 */
@Slf4j
@Service
@ConditionalOnExpression("!'${spring.ai.dashscope.api-key:}'.isEmpty()")
public class DashScopeContentOrganizer implements AiContentOrganizer {

    private final RestClient restClient;
    private final ObjectMapper objectMapper;

    @Value("${spring.ai.dashscope.chat.options.model:qwen3.6-plus}")
    private String model;

    @Value("${spring.ai.dashscope.chat.options.temperature:0.3}")
    private double temperature;

    public DashScopeContentOrganizer(
            @Value("${spring.ai.dashscope.api-key:}") String apiKey,
            @Value("${spring.ai.dashscope.base-url:https://dashscope.aliyuncs.com/compatible-mode/v1}") String baseUrl,
            ObjectMapper objectMapper) {
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(Duration.ofSeconds(10));
        factory.setReadTimeout(Duration.ofSeconds(90));
        this.restClient = RestClient.builder()
                .baseUrl(baseUrl)
                .defaultHeader("Authorization", "Bearer " + apiKey)
                .defaultHeader("Content-Type", "application/json")
                .requestFactory(factory)
                .build();
        this.objectMapper = objectMapper;
        log.info("[AiOrganizer] DashScopeContentOrganizer initialized, baseUrl={}", baseUrl);
    }

    @Override
    public CompletableFuture<OrganizedContent> organize(String rawMarkdown, AiTemplate template) {
        long start = System.currentTimeMillis();
        try {
            String userPrompt = buildSinglePagePrompt(rawMarkdown, template);
            AiResponse aiResponse = callAi(SYSTEM_PROMPT, userPrompt);
            OrganizedContent result = parseOrganizedContent(aiResponse.content);
            result.durationMs = (int) (System.currentTimeMillis() - start);
            result.tokensUsed = aiResponse.totalTokens;
            log.info("[AiOrganizer] Single page organized: title={}, duration={}ms, tokens={}",
                    result.title, result.durationMs, result.tokensUsed);
            return CompletableFuture.completedFuture(result);
        } catch (Exception e) {
            log.error("[AiOrganizer] organize failed, template={}", template, e);
            return CompletableFuture.failedFuture(e);
        }
    }

    @Override
    public CompletableFuture<OrganizedContent> organizeMultiple(List<PageContent> pages, AiTemplate template) {
        long start = System.currentTimeMillis();
        try {
            String userPrompt = buildMultiPagePrompt(pages, template, null);
            AiResponse aiResponse = callAi(SYSTEM_PROMPT, userPrompt);
            OrganizedContent result = parseOrganizedContent(aiResponse.content);
            result.durationMs = (int) (System.currentTimeMillis() - start);
            result.tokensUsed = aiResponse.totalTokens;
            log.info("[AiOrganizer] Multi-page organized: title={}, pages={}, duration={}ms, tokens={}",
                    result.title, pages.size(), result.durationMs, result.tokensUsed);
            return CompletableFuture.completedFuture(result);
        } catch (Exception e) {
            log.error("[AiOrganizer] organizeMultiple failed", e);
            return CompletableFuture.failedFuture(e);
        }
    }

    /**
     * 多页整理（带关键词上下文）
     * 供 AsyncExecutor 调用时注入 keyword
     */
    public CompletableFuture<OrganizedContent> organizeMultiple(List<PageContent> pages, AiTemplate template, String keyword) {
        long start = System.currentTimeMillis();
        try {
            String userPrompt = buildMultiPagePrompt(pages, template, keyword);
            AiResponse aiResponse = callAi(SYSTEM_PROMPT, userPrompt);
            OrganizedContent result = parseOrganizedContent(aiResponse.content);
            result.durationMs = (int) (System.currentTimeMillis() - start);
            result.tokensUsed = aiResponse.totalTokens;
            log.info("[AiOrganizer] Multi-page organized: title={}, pages={}, keyword={}, duration={}ms, tokens={}",
                    result.title, pages.size(), keyword, result.durationMs, result.tokensUsed);
            return CompletableFuture.completedFuture(result);
        } catch (Exception e) {
            log.error("[AiOrganizer] organizeMultiple failed", e);
            return CompletableFuture.failedFuture(e);
        }
    }

    @Override
    public CompletableFuture<DigestContent> generateDigest(List<DigestPageContent> pages, String date) {
        log.warn("[AiOrganizer] generateDigest not yet implemented (Phase 5)");
        DigestContent content = new DigestContent();
        content.title = "技术日报 " + date;
        content.sections = Collections.emptyList();
        content.tags = Collections.emptyList();
        return CompletableFuture.completedFuture(content);
    }

    // ============== Prompt 构建 ==============

    private static final String SYSTEM_PROMPT = """
            你是一位资深技术内容编辑，擅长从网页原始内容中提取、整理、重组高质量技术文章。

            ## 输出规则
            1. 严格输出 JSON 格式，不要包裹在 markdown 代码块中
            2. fullContent 使用 Markdown 格式，代码块用 ```language 标记，长度 1000-5000 字
            3. 保留原文有价值的代码示例，不要丢弃
            4. 英文内容翻译为中文，保留专有名词原文（如 React、Kubernetes）
            5. 标签是具体技术关键词（如 "Spring Boot 3" 而非 "Java"），3-7 个
            6. category 必须是以下之一：后端开发/前端开发/数据库/DevOps/AI与机器学习/安全/其他
            7. 如果输入内容不是技术文章（如登录页、错误页、空白页），输出：{"title":"无效内容","summary":"输入非有效技术文档","keyPoints":[],"tags":[],"category":"其他","fullContent":""}
            8. 忽略原始内容中的导航栏、Cookie 提示、评论区、分享按钮、广告等无关文本
            """;

    private static final String OUTPUT_SCHEMA = """

            ## 输出格式
            {
                "title": "吸引人的中文标题（15-30字）",
                "summary": "200-300字核心摘要",
                "keyPoints": ["要点1", "要点2", ...],
                "tags": ["标签1", ...],
                "category": "后端开发/前端开发/数据库/DevOps/AI与机器学习/安全/其他",
                "fullContent": "完整 Markdown 格式整理文章"
            }
            """;

    private static final String FEW_SHOT_EXAMPLE = """

            ## 输出示例（注意：fullContent 必须是完整文章，不要用省略号截断）
            {
                "title": "Spring Boot 3 优雅停机配置详解",
                "summary": "本文讲解 Spring Boot 3 的优雅停机机制，包括 server.shutdown=graceful 配置、SmartLifecycle 接口处理资源释放、以及 Docker/K8s 环境下的 terminationGracePeriodSeconds 配合方案。",
                "keyPoints": [
                    "server.shutdown=graceful 开启内置优雅停机",
                    "自定义 SmartLifecycle 接口处理资源释放",
                    "K8s 环境需配合 terminationGracePeriodSeconds"
                ],
                "tags": ["Spring Boot 3", "优雅停机", "Kubernetes", "微服务"],
                "category": "后端开发",
                "fullContent": "## Spring Boot 3 优雅停机\\n\\n### 开启优雅停机\\n\\n在 application.yml 中配置：\\n\\n```yaml\\nserver:\\n  shutdown: graceful\\n```\\n\\n启用后，应用关闭时会等待活跃请求完成。\\n\\n### K8s 环境配置\\n\\n需在 Pod spec 中设置：\\n\\n```yaml\\nterminationGracePeriodSeconds: 60\\n```\\n\\n确保 K8s 给予足够的停机等待时间。"
            }
            """;

    private String buildSinglePagePrompt(String rawMarkdown, AiTemplate template) {
        String truncated = truncateAtParagraphBoundary(rawMarkdown, 80000);

        String roleInstruction = switch (template) {
            case TECH_SUMMARY -> "请对以下网页内容进行深度阅读和结构化整理。"
                    + "重点：提炼核心技术要点、梳理逻辑脉络、补充必要的技术背景、生成结构清晰的技术摘要。\n";
            case TUTORIAL -> "请将以下内容整理为 step-by-step 教程。"
                    + "重点：循序渐进的学习路径、每步配代码和预期结果、常见坑和注意事项。\n";
            case COMPARISON -> "请对以下内容进行分析，提取技术方案对比信息。"
                    + "输出包含：技术方案概述、对比表格（功能/性能/适用场景）、推荐场景。\n";
            default -> "请对以下网页内容进行深度阅读和结构化整理。\n";
        };

        return roleInstruction + "\n## 原始内容\n" + truncated + "\n" + OUTPUT_SCHEMA + FEW_SHOT_EXAMPLE;
    }

    private String buildMultiPagePrompt(List<PageContent> pages, AiTemplate template, String keyword) {
        StringBuilder sb = new StringBuilder();

        String roleInstruction = switch (template) {
            case TUTORIAL -> "以下是从多个来源收集的教程相关内容，请整合为一篇循序渐进的 step-by-step 教程。"
                    + "重点：统一学习路径、去重合并相同步骤、补充缺失环节、标注各来源差异。\n";
            case COMPARISON -> "以下是从多个来源收集的内容，请进行横向技术方案对比分析。"
                    + "重点：提取各方案优缺点、制作对比表格、给出不同场景下的推荐。\n";
            case KNOWLEDGE_REPORT -> "以下是从多个来源收集的内容，请生成一份综合性知识报告。"
                    + "重点：背景概述、技术原理、现状分析、趋势预测、参考来源。\n";
            default -> "以下是从多个来源收集的内容，请进行综合分析整理，去重合并，生成结构化的技术文章。\n";
        };
        sb.append(roleInstruction).append("\n");

        if (keyword != null && !keyword.isBlank()) {
            sb.append("## 搜索关键词\n");
            sb.append("用户通过搜索引擎搜索「").append(keyword).append("」找到了以下页面。");
            sb.append("请围绕该关键词组织内容，重点关注与关键词直接相关的技术信息。\n\n");
        }

        sb.append("## 来源内容\n\n");

        for (int i = 0; i < pages.size(); i++) {
            PageContent page = pages.get(i);
            sb.append("### 来源 ").append(i + 1).append(": ")
                    .append(page.title != null ? page.title : "未知标题").append("\n");
            sb.append("URL: ").append(page.url != null ? page.url : "未知").append("\n\n");
            String md = page.markdown != null ? page.markdown : "";
            md = truncateAtParagraphBoundary(md, 20000);
            sb.append(md).append("\n\n---\n\n");
        }

        sb.append(OUTPUT_SCHEMA);
        sb.append(FEW_SHOT_EXAMPLE);
        return sb.toString();
    }

    // ============== AI 调用（OpenAI 兼容格式） ==============

    /**
     * AI 响应数据：包含内容文本和 token 使用量
     */
    private static class AiResponse {
        String content;
        int totalTokens;
        String finishReason;
    }

    private AiResponse callAi(String systemPrompt, String userPrompt) {
        Map<String, Object> requestBody = new LinkedHashMap<>();
        requestBody.put("model", model);
        requestBody.put("temperature", temperature);
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
                            throw new AiUnrecoverableException("API client error " + resp.getStatusCode() + ": " + body);
                        })
                .onStatus(status -> status.value() == 429,
                        (req, resp) -> {
                            String body = new String(resp.getBody().readAllBytes(), StandardCharsets.UTF_8);
                            log.warn("[AiOrganizer] Rate limited by API: {}", body);
                            throw new AiRateLimitException("Rate limited");
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

            // 提取内容：choices[0].message.content
            @SuppressWarnings("unchecked")
            List<Map<String, Object>> choices = (List<Map<String, Object>>) respMap.get("choices");
            if (choices != null && !choices.isEmpty()) {
                @SuppressWarnings("unchecked")
                Map<String, Object> message = (Map<String, Object>) choices.get(0).get("message");
                if (message != null) {
                    aiResponse.content = (String) message.get("content");
                }
            }
            if (aiResponse.content == null) {
                throw new RuntimeException("Unexpected API response format: no content");
            }

            // 检查 finish_reason：如果为 "length" 说明输出被截断，不应重试
            if (choices != null && !choices.isEmpty()) {
                Object fr = choices.get(0).get("finish_reason");
                aiResponse.finishReason = fr != null ? fr.toString() : "unknown";
            }
            if ("length".equals(aiResponse.finishReason)) {
                log.warn("[AiOrganizer] finish_reason=length, output truncated, tokens={}", aiResponse.totalTokens);
                throw new AiTruncatedException("AI output truncated (finish_reason=length), tokens=" + aiResponse.totalTokens);
            }

            // 提取 token 使用量：usage.total_tokens
            @SuppressWarnings("unchecked")
            Map<String, Object> usage = (Map<String, Object>) respMap.get("usage");
            if (usage != null && usage.get("total_tokens") != null) {
                aiResponse.totalTokens = ((Number) usage.get("total_tokens")).intValue();
            }

            return aiResponse;
        } catch (RuntimeException e) {
            throw e;
        } catch (Exception e) {
            throw new RuntimeException("Failed to parse AI response: " + e.getMessage(), e);
        }
    }

    // ============== 响应解析 ==============

    private static final Pattern JSON_BLOCK = Pattern.compile("```(?:json)?\\s*\\n?([\\s\\S]*?)```");

    @SuppressWarnings("unchecked")
    private OrganizedContent parseOrganizedContent(String response) throws Exception {
        String json = extractJson(response);
        try {
            Map<String, Object> map = objectMapper.readValue(json, Map.class);

            OrganizedContent content = new OrganizedContent();
            content.title = (String) map.getOrDefault("title", "");
            content.summary = (String) map.getOrDefault("summary", "");
            content.keyPoints = toStringList(map.get("keyPoints"));
            content.tags = toStringList(map.get("tags"));
            content.category = (String) map.getOrDefault("category", "");
            content.fullContent = (String) map.getOrDefault("fullContent", "");
            return content;
        } catch (Exception e) {
            log.error("[AiOrganizer] JSON parse failed. Raw (first 500): {}",
                    json.substring(0, Math.min(500, json.length())));
            throw e;
        }
    }

    private String extractJson(String response) {
        Matcher matcher = JSON_BLOCK.matcher(response);
        if (matcher.find()) {
            return matcher.group(1).trim();
        }
        // 大括号计数法：从第一个 { 找到最外层平衡的 JSON
        int start = response.indexOf('{');
        if (start < 0) {
            throw new RuntimeException("No JSON found in AI response");
        }
        int depth = 0;
        for (int i = start; i < response.length(); i++) {
            char c = response.charAt(i);
            if (c == '{') depth++;
            else if (c == '}') {
                depth--;
                if (depth == 0) return response.substring(start, i + 1);
            }
        }
        throw new RuntimeException("No balanced JSON found in AI response");
    }

    private List<String> toStringList(Object obj) {
        if (obj instanceof List<?> list) {
            return list.stream().map(Object::toString).toList();
        }
        return Collections.emptyList();
    }

    /**
     * 按段落边界截断，避免切断代码块或表格
     */
    private static String truncateAtParagraphBoundary(String text, int maxLen) {
        if (text.length() <= maxLen) return text;
        // 在 maxLen 附近找最近的双换行（段落边界）
        int cutPos = text.lastIndexOf("\n\n", maxLen);
        if (cutPos < maxLen * 0.8) {
            // 如果最近的段落边界太靠前，退而求其次找单换行
            cutPos = text.lastIndexOf('\n', maxLen);
        }
        if (cutPos < maxLen * 0.5) {
            // 连单换行都太靠前，暴力截断
            cutPos = maxLen;
        }
        return text.substring(0, cutPos) + "\n\n[...内容过长已截断]";
    }

    /**
     * AI 输出被 token 限制截断，重试无意义
     */
    static class AiTruncatedException extends RuntimeException {
        AiTruncatedException(String message) { super(message); }
    }

    /**
     * API 客户端错误（401/403/400），重试无法恢复
     */
    static class AiUnrecoverableException extends RuntimeException {
        AiUnrecoverableException(String message) { super(message); }
    }

    /**
     * API 限速（429），需更长退避
     */
    static class AiRateLimitException extends RuntimeException {
        AiRateLimitException(String message) { super(message); }
    }
}
