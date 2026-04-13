package com.nanmuli.blog.infrastructure.ai;

import com.nanmuli.blog.domain.webcollector.AiContentOrganizer;
import com.nanmuli.blog.domain.webcollector.AiTemplate;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.stereotype.Service;

import java.util.Collections;
import java.util.List;
import java.util.concurrent.CompletableFuture;

/**
 * AI 内容整理服务的空实现（Fallback）
 * 当 DashScope 未配置或不可用时自动激活，跳过所有 AI 操作
 */
@Slf4j
@Service
@ConditionalOnMissingBean(AiContentOrganizer.class)
public class NoOpContentOrganizer implements AiContentOrganizer {

    @Override
    public CompletableFuture<OrganizedContent> organize(String rawMarkdown, AiTemplate template) {
        log.debug("[NoOpContentOrganizer] 跳过 AI 整理，内容长度: {}",
                rawMarkdown != null ? rawMarkdown.length() : 0);
        return CompletableFuture.failedFuture(
                new UnsupportedOperationException("AI content organizer not available"));
    }

    @Override
    public CompletableFuture<OrganizedContent> organizeMultiple(List<PageContent> pages, AiTemplate template) {
        log.debug("[NoOpContentOrganizer] 跳过多页 AI 整理，页面数: {}", pages != null ? pages.size() : 0);
        return CompletableFuture.failedFuture(
                new UnsupportedOperationException("AI content organizer not available"));
    }

    @Override
    public CompletableFuture<DigestContent> generateDigest(List<DigestPageContent> pages, String date) {
        log.debug("[NoOpContentOrganizer] 跳过日报生成，日期: {}", date);
        return CompletableFuture.failedFuture(
                new UnsupportedOperationException("AI content organizer not available"));
    }
}
