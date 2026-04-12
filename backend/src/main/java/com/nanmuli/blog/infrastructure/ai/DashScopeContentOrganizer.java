package com.nanmuli.blog.infrastructure.ai;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.nanmuli.blog.domain.webcollector.AiContentOrganizer;
import com.nanmuli.blog.domain.webcollector.AiTemplate;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;

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
        this.restClient = RestClient.builder()
                .baseUrl(baseUrl)
                .defaultHeader("Authorization", "Bearer " + apiKey)
                .defaultHeader("Content-Type", "application/json")
                .build();
        this.objectMapper = objectMapper;
        log.info("[AiOrganizer] DashScopeContentOrganizer initialized, baseUrl={}", baseUrl);
    }

    @Override
    public CompletableFuture<OrganizedContent> organize(String rawMarkdown, AiTemplate template) {
        long start = System.currentTimeMillis();
        try {
            String prompt = buildSinglePagePrompt(rawMarkdown, template);
            String response = callAi(prompt);
            OrganizedContent result = parseOrganizedContent(response);
            result.durationMs = (int) (System.currentTimeMillis() - start);
            log.info("[AiOrganizer] Single page organized: title={}, duration={}ms",
                    result.title, result.durationMs);
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
            String prompt = buildMultiPagePrompt(pages);
            String response = callAi(prompt);
            OrganizedContent result = parseOrganizedContent(response);
            result.durationMs = (int) (System.currentTimeMillis() - start);
            log.info("[AiOrganizer] Multi-page organized: title={}, pages={}, duration={}ms",
                    result.title, pages.size(), result.durationMs);
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

    private static final String OUTPUT_FORMAT = """

            ## 输出要求（严格 JSON 格式，不要包裹在代码块中）
            {
                "title": "吸引人的中文标题（15-30字）",
                "summary": "200-300字核心摘要",
                "keyPoints": ["要点1", "要点2", ...],
                "tags": ["标签1", ...],
                "category": "后端开发/前端开发/数据库/DevOps/AI与机器学习/安全/其他",
                "fullContent": "完整 Markdown 格式整理文章"
            }

            ## 规则
            1. 输出合法 JSON，fullContent 中代码块用 ```language 标记
            2. 保留原文有价值的代码示例
            3. 英文内容翻译为中文，保留专有名词原文
            4. 标签是技术关键词，不要太泛也不要太窄
            """;

    private String buildSinglePagePrompt(String rawMarkdown, AiTemplate template) {
        String truncated = rawMarkdown.length() > 80000
                ? rawMarkdown.substring(0, 80000) + "\n\n[...内容过长已截断]"
                : rawMarkdown;

        String rolePrompt = switch (template) {
            case TUTORIAL -> "你是一位技术教育专家。请将以下内容整理为 step-by-step 教程。\n"
                    + "重点：循序渐进的学习路径、每步配代码和预期结果、常见坑和注意事项。\n";
            case COMPARISON -> "你是一位技术选型顾问。请对以下内容进行分析，提取技术方案对比信息。\n"
                    + "输出包含：技术方案概述、对比表格（功能/性能/适用场景）、推荐场景。\n";
            default -> "你是一位资深技术内容编辑。请对以下网页内容进行深度阅读和结构化整理。\n";
        };

        return rolePrompt + "\n## 原始内容\n" + truncated + "\n" + OUTPUT_FORMAT;
    }

    private String buildMultiPagePrompt(List<PageContent> pages) {
        StringBuilder sb = new StringBuilder();
        sb.append("你是一位技术研究专家。以下是从多个来源收集的内容，请进行综合分析整理。\n\n");
        sb.append("## 来源内容\n\n");

        for (int i = 0; i < pages.size(); i++) {
            PageContent page = pages.get(i);
            sb.append("### 来源 ").append(i + 1).append(": ")
                    .append(page.title != null ? page.title : "未知标题").append("\n");
            sb.append("URL: ").append(page.url != null ? page.url : "未知").append("\n\n");
            String md = page.markdown != null ? page.markdown : "";
            if (md.length() > 20000) md = md.substring(0, 20000) + "\n[...截断]";
            sb.append(md).append("\n\n---\n\n");
        }

        sb.append(OUTPUT_FORMAT);
        return sb.toString();
    }

    // ============== AI 调用（OpenAI 兼容格式） ==============

    private String callAi(String prompt) {
        Map<String, Object> requestBody = new LinkedHashMap<>();
        requestBody.put("model", model);
        requestBody.put("temperature", temperature);
        requestBody.put("messages", List.of(
                Map.of("role", "user", "content", prompt)
        ));

        String response = restClient.post()
                .uri("/chat/completions")
                .body(requestBody)
                .retrieve()
                .body(String.class);

        // 解析 OpenAI 格式响应：choices[0].message.content
        try {
            Map<String, Object> respMap = objectMapper.readValue(response, Map.class);
            List<Map<String, Object>> choices = (List<Map<String, Object>>) respMap.get("choices");
            if (choices != null && !choices.isEmpty()) {
                Map<String, Object> message = (Map<String, Object>) choices.get(0).get("message");
                if (message != null) {
                    return (String) message.get("content");
                }
            }
            throw new RuntimeException("Unexpected API response format");
        } catch (Exception e) {
            throw new RuntimeException("Failed to parse AI response: " + e.getMessage(), e);
        }
    }

    // ============== 响应解析 ==============

    private static final Pattern JSON_BLOCK = Pattern.compile("```(?:json)?\\s*\\n?([\\s\\S]*?)```");

    @SuppressWarnings("unchecked")
    private OrganizedContent parseOrganizedContent(String response) throws Exception {
        String json = extractJson(response);
        Map<String, Object> map = objectMapper.readValue(json, Map.class);

        OrganizedContent content = new OrganizedContent();
        content.title = (String) map.getOrDefault("title", "");
        content.summary = (String) map.getOrDefault("summary", "");
        content.keyPoints = toStringList(map.get("keyPoints"));
        content.tags = toStringList(map.get("tags"));
        content.category = (String) map.getOrDefault("category", "");
        content.fullContent = (String) map.getOrDefault("fullContent", "");
        content.tokensUsed = 0;
        return content;
    }

    private String extractJson(String response) {
        Matcher matcher = JSON_BLOCK.matcher(response);
        if (matcher.find()) {
            return matcher.group(1).trim();
        }
        int start = response.indexOf('{');
        int end = response.lastIndexOf('}');
        if (start >= 0 && end > start) {
            return response.substring(start, end + 1);
        }
        throw new RuntimeException("No JSON found in AI response");
    }

    private List<String> toStringList(Object obj) {
        if (obj instanceof List<?> list) {
            return list.stream().map(Object::toString).toList();
        }
        return Collections.emptyList();
    }
}
