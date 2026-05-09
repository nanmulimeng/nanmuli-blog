package com.nanmuli.blog.application.event;

import com.nanmuli.blog.domain.ai.AiService;
import com.nanmuli.blog.domain.article.ArticleId;
import com.nanmuli.blog.domain.article.ArticleRepository;
import com.nanmuli.blog.domain.article.event.ArticlePublishedEvent;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.event.EventListener;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Component;

/**
 * 文章领域事件处理器
 * 处理文章相关领域事件，如发布、创建等
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class ArticleEventHandler {

    private final AiService aiService;
    private final ArticleRepository articleRepository;

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
                            // TODO: 标签系统尚未实现，待标签模块开发后保存关联
                            log.warn("文章[{}]标签结果暂未持久化，等待标签系统实现: {}", event.getArticleId(), tags);
                        }
                    })
                    .exceptionally(ex -> {
                        log.error("文章[{}]生成标签失败: {}", event.getArticleId(), ex.getMessage());
                        return null;
                    });

            // 2. 异步生成摘要（仅在文章无摘要时更新）
            aiService.generateSummary(event.getContent(), 200)
                    .thenAccept(summary -> {
                        if (!summary.isEmpty()) {
                            log.info("文章[{}]生成摘要成功，长度: {}", event.getArticleId(), summary.length());
                            updateArticleSummaryIfNeeded(event.getArticleId(), summary);
                        }
                    })
                    .exceptionally(ex -> {
                        log.error("文章[{}]生成摘要失败: {}", event.getArticleId(), ex.getMessage());
                        return null;
                    });

            // 3. 异步生成向量嵌入（用于相似文章推荐）
            aiService.generateEmbedding(event.getContent())
                    .thenAccept(embedding -> {
                        if (embedding.length > 0) {
                            log.info("文章[{}]生成向量嵌入成功，维度: {}", event.getArticleId(), embedding.length);
                            // TODO: 向量存储模块尚未实现，待article_vector表和Repository开发后保存
                            log.warn("文章[{}]向量嵌入暂未持久化，等待向量存储实现，维度: {}", event.getArticleId(), embedding.length);
                        }
                    })
                    .exceptionally(ex -> {
                        log.error("文章[{}]生成向量嵌入失败: {}", event.getArticleId(), ex.getMessage());
                        return null;
                    });

        } catch (Exception e) {
            log.error("处理文章发布事件失败: articleId={}", event.getArticleId(), e);
        }
    }

    /**
     * 如果文章当前无摘要，使用AI生成的摘要更新
     */
    private void updateArticleSummaryIfNeeded(Long articleId, String aiSummary) {
        try {
            articleRepository.findById(new ArticleId(articleId)).ifPresent(article -> {
                if (article.getSummary() == null || article.getSummary().isBlank()) {
                    article.setSummary(aiSummary);
                    articleRepository.save(article);
                    log.info("文章[{}]摘要已通过AI生成并更新", articleId);
                }
            });
        } catch (Exception e) {
            log.error("更新文章[{}]AI摘要失败: {}", articleId, e.getMessage());
        }
    }
}
