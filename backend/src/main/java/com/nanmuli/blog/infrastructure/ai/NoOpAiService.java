package com.nanmuli.blog.infrastructure.ai;

import com.nanmuli.blog.domain.ai.AiService;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

/**
 * AI服务空实现 — AI模块预留，当前禁用
 * 所有方法返回空结果，不执行实际AI调用
 */
@Slf4j
@Service
public class NoOpAiService implements AiService {

    @Override
    public CompletableFuture<List<String>> generateTags(String content) {
        log.debug("AI标签生成已禁用，跳过");
        return CompletableFuture.completedFuture(List.of());
    }

    @Override
    public CompletableFuture<String> generateSummary(String content, int maxLength) {
        log.debug("AI摘要生成已禁用，跳过");
        return CompletableFuture.completedFuture("");
    }

    @Override
    public CompletableFuture<float[]> generateEmbedding(String content) {
        log.debug("AI向量嵌入已禁用，跳过");
        return CompletableFuture.completedFuture(new float[0]);
    }

    @Override
    public CompletableFuture<String> optimizeTitle(String title, String content) {
        log.debug("AI标题优化已禁用，跳过");
        return CompletableFuture.completedFuture("");
    }
}
