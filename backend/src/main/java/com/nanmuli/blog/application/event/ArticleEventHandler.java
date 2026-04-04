package com.nanmuli.blog.application.event;

import com.nanmuli.blog.domain.ai.AiService;
import com.nanmuli.blog.domain.article.event.ArticlePublishedEvent;
import com.nanmuli.blog.infrastructure.persistence.ai.AiGenerationMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.event.EventListener;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Component;

import java.util.List;

/**
 * 文章领域事件处理器
 * 处理文章相关领域事件，如发布、创建等
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class ArticleEventHandler {

    private final AiService aiService;
    private final AiGenerationMapper aiGenerationMapper;

    /**
     * 处理文章发布事件
     * 异步生成标签、摘要、向量嵌入
     */
    @EventListener
    @Async("aiTaskExecutor")
    public void handleArticlePublished(ArticlePublishedEvent event) {
        log.info("处理文章发布事件: articleId={}, title={}", event.getArticleId(), event.getTitle());

        try {
            // 1. 异步生成标签
            aiService.generateTags(event.getContent())
                    .thenAccept(tags -> {
                        if (!tags.isEmpty()) {
                            log.info("文章[{}]生成标签成功: {}", event.getArticleId(), tags);
                            // TODO: 保存标签关联
                        }
                    });

            // 2. 异步生成摘要
            aiService.generateSummary(event.getContent(), 200)
                    .thenAccept(summary -> {
                        if (!summary.isEmpty()) {
                            log.info("文章[{}]生成摘要成功，长度: {}", event.getArticleId(), summary.length());
                            // TODO: 更新文章摘要字段
                        }
                    });

            // 3. 异步生成向量嵌入（用于相似文章推荐）
            aiService.generateEmbedding(event.getContent())
                    .thenAccept(embedding -> {
                        if (embedding.length > 0) {
                            log.info("文章[{}]生成向量嵌入成功，维度: {}", event.getArticleId(), embedding.length);
                            // TODO: 保存到article_vector表
                        }
                    });

        } catch (Exception e) {
            log.error("处理文章发布事件失败: articleId={}", event.getArticleId(), e);
        }
    }
}
