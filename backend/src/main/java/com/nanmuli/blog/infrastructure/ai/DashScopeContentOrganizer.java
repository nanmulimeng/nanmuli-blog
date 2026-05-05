package com.nanmuli.blog.infrastructure.ai;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.nanmuli.blog.domain.webcollector.AiContentOrganizer;
import com.nanmuli.blog.domain.webcollector.AiOrganizerException;
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

    @Value("${blog.ai.organizer.single-page-max-chars:80000}")
    private int singlePageMaxChars;

    @Value("${blog.ai.organizer.multi-page-per-max-chars:20000}")
    private int multiPagePerMaxChars;

    @Value("${blog.ai.organizer.multi-page-total-budget:150000}")
    private int multiPageTotalBudget;

    private final RestClient restClient;
    private final ObjectMapper objectMapper;

    @Value("${spring.ai.dashscope.chat.options.model:qwen3.6-plus}")
    private String model;

    @Value("${spring.ai.dashscope.chat.options.temperature:0.3}")
    private double temperature;

    public DashScopeContentOrganizer(
            @Value("${spring.ai.dashscope.api-key:}") String apiKey,
            @Value("${spring.ai.dashscope.base-url:https://dashscope.aliyuncs.com/compatible-mode/v1}") String baseUrl,
            @Value("${blog.ai.organizer.connect-timeout-seconds:10}") int connectTimeoutSeconds,
            @Value("${blog.ai.organizer.read-timeout-seconds:90}") int readTimeoutSeconds,
            ObjectMapper objectMapper) {
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(Duration.ofSeconds(connectTimeoutSeconds));
        factory.setReadTimeout(Duration.ofSeconds(readTimeoutSeconds));
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
        return organizeMultiple(pages, template, null);
    }

    /**
     * 多页整理（带关键词上下文）
     * 覆写接口 default 方法，注入 keyword 到 prompt
     */
    @Override
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
        return CompletableFuture.failedFuture(
                new UnsupportedOperationException("generateDigest not implemented yet"));
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
                "summary": "本文讲解 Spring Boot 3 的优雅停机机制，包括 server.shutdown=graceful 配置、SmartLifecycle 接口处理资源释放、以及 Docker/K8s 环境下的 terminationGracePeriodSeconds 配合方案。通过合理配置，可以确保应用在关闭时安全释放资源并完成正在处理的请求。",
                "keyPoints": [
                    "server.shutdown=graceful 开启内置优雅停机",
                    "自定义 SmartLifecycle 接口处理资源释放",
                    "K8s 环境需配合 terminationGracePeriodSeconds"
                ],
                "tags": ["Spring Boot 3", "优雅停机", "Kubernetes", "微服务"],
                "category": "后端开发",
                "fullContent": "## Spring Boot 3 优雅停机\\n\\n### 开启优雅停机\\n\\n在 application.yml 中配置：\\n\\n```yaml\\nserver:\\n  shutdown: graceful\\nspring:\\n  lifecycle:\\n    timeout-per-shutdown-phase: 30s\\n```\\n\\n启用后，应用关闭时 Web 服务器会拒绝新请求并等待活跃请求完成，超时后强制关闭。\\n\\n### SmartLifecycle 资源释放\\n\\n对于需要自定义清理逻辑的组件（如线程池、缓存连接），实现 SmartLifecycle 接口：\\n\\n```java\\n@Component\\npublic class ResourceCleanup implements SmartLifecycle {\\n    private volatile boolean running = false;\\n\\n    @Override\\n    public void start() { running = true; }\\n\\n    @Override\\n    public void stop() {\\n        // 关闭线程池、释放连接\\n        running = false;\\n    }\\n\\n    @Override\\n    public boolean isRunning() { return running; }\\n}\\n```\\n\\n### K8s 环境配置\\n\\n需在 Pod spec 中设置：\\n\\n```yaml\\nspec:\\n  terminationGracePeriodSeconds: 60\\n  containers:\\n    - name: app\\n      lifecycle:\\n        preStop:\\n          exec:\\n            command: [\\"sh\\", \\"-c\\", \\"sleep 10\\"]\\n```\\n\\npreStop hook 给 kubelet 发送 SIGTERM 之前留出时间让 Pod 从 Service 中摘除，避免流量打到已停止的实例。"
            }
            """;

    private String buildSinglePagePrompt(String rawMarkdown, AiTemplate template) {
        String truncated = truncateAtParagraphBoundary(rawMarkdown, singlePageMaxChars);

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

        // [B3] 多页总输入预算上限：先截断每页，再按总预算裁剪后面的页面
        int remainingBudget = multiPageTotalBudget;
        for (int i = 0; i < pages.size(); i++) {
            PageContent page = pages.get(i);
            sb.append("### 来源 ").append(i + 1).append(": ")
                    .append(page.title != null ? page.title : "未知标题").append("\n");
            sb.append("URL: ").append(page.url != null ? page.url : "未知").append("\n\n");

            String md = page.markdown != null ? page.markdown : "";
            int perPageBudget = Math.min(multiPagePerMaxChars, remainingBudget);
            if (perPageBudget <= 0) {
                sb.append("[已达到总输入预算上限，后续来源已省略]\n\n");
                continue;
            }
            md = truncateAtParagraphBoundary(md, perPageBudget);
            sb.append(md).append("\n\n---\n\n");
            remainingBudget -= md.length();
        }

        sb.append(OUTPUT_SCHEMA);
        sb.append(FEW_SHOT_EXAMPLE);
        return sb.toString();
    }

    // ============== AI 调用（OpenAI 兼容格式） ==============

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

            // [B2] 先提取 finish_reason 和 usage，再做截断检查
            if (choices != null && !choices.isEmpty()) {
                Object fr = choices.get(0).get("finish_reason");
                aiResponse.finishReason = fr != null ? fr.toString() : "unknown";
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

    /**
     * [B1] 增强版 JSON 提取：正确处理字符串内的大括号
     * 1. 先尝试 markdown 代码块提取（验证为合法 JSON 后返回）
     * 2. 代码块内容不是合法 JSON 时（fullContent 内含代码块导致误匹配），回退到状态机
     * 3. 状态机跟踪引号和转义状态，字符串内的大括号不参与深度计数
     */
    private String extractJson(String response) {
        // 尝试 markdown 代码块：regex 匹配后验证是否为合法 JSON
        Matcher matcher = JSON_BLOCK.matcher(response);
        if (matcher.find()) {
            String candidate = matcher.group(1).trim();
            try {
                objectMapper.readValue(candidate, Map.class);
                return candidate;
            } catch (Exception ignored) {
                // regex 误匹配了 fullContent 内部的代码块，回退到状态机
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
            if (inString) continue;
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
        int cutPos = text.lastIndexOf("\n\n", maxLen);
        if (cutPos < maxLen * 0.8) {
            cutPos = text.lastIndexOf('\n', maxLen);
        }
        if (cutPos < maxLen * 0.5) {
            cutPos = maxLen;
        }
        return text.substring(0, cutPos) + "\n\n[...内容过长已截断]";
    }
}
