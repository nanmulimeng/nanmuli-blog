package com.nanmuli.blog.infrastructure.ai;

import com.nanmuli.blog.domain.ai.AiService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;

import java.util.Collections;
import java.util.List;
import java.util.concurrent.CompletableFuture;

/**
 * 空AI服务实现
 * 当未配置真实AI服务时使用，仅记录日志不执行实际AI操作
 */
@Slf4j
@Service
@ConditionalOnMissingBean(name = "dashScopeAiService")
public class NoOpAiService implements AiService {

    @Override
    @Async("taskExecutor")
    public CompletableFuture<List<String>> generateTags(String content) {
        log.debug("[NoOp] 跳过标签生成，内容长度: {}", content != null ? content.length() : 0);
        return CompletableFuture.completedFuture(Collections.emptyList());
    }

    @Override
    @Async("taskExecutor")
    public CompletableFuture<String> generateSummary(String content, int maxLength) {
        log.debug("[NoOp] 跳过摘要生成，内容长度: {}", content != null ? content.length() : 0);
        return CompletableFuture.completedFuture("");
    }

    @Override
    @Async("taskExecutor")
    public CompletableFuture<float[]> generateEmbedding(String content) {
        log.debug("[NoOp] 跳过向量嵌入生成，内容长度: {}", content != null ? content.length() : 0);
        return CompletableFuture.completedFuture(new float[0]);
    }

    @Override
    @Async("taskExecutor")
    public CompletableFuture<String> optimizeTitle(String title, String content) {
        log.debug("[NoOp] 跳过标题优化: {}", title);
        return CompletableFuture.completedFuture(title);
    }
}
