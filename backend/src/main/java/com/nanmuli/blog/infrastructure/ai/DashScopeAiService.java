package com.nanmuli.blog.infrastructure.ai;

import com.nanmuli.blog.domain.ai.AiService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.metadata.Usage;
import org.springframework.ai.chat.model.ChatResponse;
import org.springframework.ai.chat.prompt.Prompt;
import org.springframework.ai.embedding.EmbeddingClient;
import org.springframework.ai.embedding.EmbeddingResponse;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;

import java.util.Arrays;
import java.util.Collections;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.stream.Collectors;

/**
 * 阿里云DashScope AI服务实现
 * 基础设施层，实现领域层定义的AI服务接口
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class DashScopeAiService implements AiService {

    private final ChatClient chatClient;
    private final EmbeddingClient embeddingClient;

    @Override
    @Async("taskExecutor")
    public CompletableFuture<List<String>> generateTags(String content) {
        try {
            String truncatedContent = content.substring(0, Math.min(content.length(), 500));
            String prompt = String.format(
                "请为以下文章生成5-8个标签，用逗号分隔。标签应该简洁、相关、热门。\n\n文章内容：\n%s",
                truncatedContent
            );

            ChatResponse response = chatClient.prompt(new Prompt(prompt)).call().chatResponse();

            String result = response.getResult().getOutput().getContent();
            List<String> tags = Arrays.stream(result.split("[,，、]"))
                    .map(String::trim)
                    .filter(s -> !s.isEmpty() && s.length() <= 20)
                    .limit(8)
                    .collect(Collectors.toList());

            log.debug("生成标签成功，文章长度：{}，生成标签：{}", content.length(), tags);
            return CompletableFuture.completedFuture(tags);
        } catch (Exception e) {
            log.error("生成标签失败", e);
            return CompletableFuture.completedFuture(Collections.emptyList());
        }
    }

    @Override
    @Async("taskExecutor")
    public CompletableFuture<String> generateSummary(String content, int maxLength) {
        try {
            String truncatedContent = content.substring(0, Math.min(content.length(), 1000));
            String prompt = String.format(
                "请为以下文章生成%d字以内的摘要，要求简洁明了，突出重点。\n\n文章内容：\n%s",
                maxLength, truncatedContent
            );

            ChatResponse response = chatClient.prompt(new Prompt(prompt)).call().chatResponse();
            String summary = response.getResult().getOutput().getContent();

            if (summary.length() > maxLength) {
                summary = summary.substring(0, maxLength);
            }

            log.debug("生成摘要成功，原文长度：{}，摘要长度：{}", content.length(), summary.length());
            return CompletableFuture.completedFuture(summary);
        } catch (Exception e) {
            log.error("生成摘要失败", e);
            return CompletableFuture.completedFuture("");
        }
    }

    @Override
    @Async("taskExecutor")
    public CompletableFuture<float[]> generateEmbedding(String content) {
        try {
            String truncatedContent = content.substring(0, Math.min(content.length(), 2000));
            EmbeddingResponse response = embeddingClient.embedForResponse(List.of(truncatedContent));

            float[] embedding = response.getResult().getOutput();
            log.debug("生成向量嵌入成功，维度：{}", embedding.length);
            return CompletableFuture.completedFuture(embedding);
        } catch (Exception e) {
            log.error("生成向量嵌入失败", e);
            return CompletableFuture.completedFuture(new float[0]);
        }
    }

    @Override
    @Async("taskExecutor")
    public CompletableFuture<String> optimizeTitle(String title, String content) {
        try {
            String prompt = String.format(
                "请优化以下文章标题，要求：1）保持原意；2）更具吸引力；3）不超过20个字。\n" +
                "原标题：%s\n文章内容摘要：%s\n\n只返回优化后的标题，不要解释。",
                title,
                content.substring(0, Math.min(content.length(), 300))
            );

            ChatResponse response = chatClient.prompt(new Prompt(prompt)).call().chatResponse();
            String optimizedTitle = response.getResult().getOutput().getContent().trim();

            // 清理可能的引号
            optimizedTitle = optimizedTitle.replaceAll("^[" + '"' + "'" + "]|[" + '"' + "'" + "]$", "");

            if (optimizedTitle.length() > 30) {
                optimizedTitle = optimizedTitle.substring(0, 30);
            }

            log.debug("优化标题成功：{} -> {}", title, optimizedTitle);
            return CompletableFuture.completedFuture(optimizedTitle);
        } catch (Exception e) {
            log.error("优化标题失败", e);
            return CompletableFuture.completedFuture(title);
        }
    }
}
