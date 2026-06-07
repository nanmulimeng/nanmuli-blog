package com.nanmuli.blog.application.article;

import com.nanmuli.blog.application.article.command.RecordArticleViewCommand;
import com.nanmuli.blog.domain.article.Article;
import com.nanmuli.blog.domain.article.ArticleId;
import com.nanmuli.blog.domain.article.ArticleRepository;
import com.nanmuli.blog.domain.article.ArticleStatus;
import com.nanmuli.blog.domain.article.ArticleViewRecordRepository;
import com.nanmuli.blog.domain.article.ArticleVisitLogRepository;
import com.nanmuli.blog.domain.category.CategoryRepository;
import com.nanmuli.blog.shared.exception.BusinessException;
import com.nanmuli.blog.shared.util.MarkdownUtil;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.context.ApplicationEventPublisher;

import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class ArticleAppServicePublicAccessTest {

    @Mock
    private ArticleRepository articleRepository;

    @Mock
    private ArticleViewRecordRepository articleViewRecordRepository;

    @Mock
    private ArticleVisitLogRepository articleVisitLogRepository;

    @Mock
    private CategoryRepository categoryRepository;

    @Mock
    private ApplicationEventPublisher eventPublisher;

    @Mock
    private MarkdownUtil markdownUtil;

    @Test
    void publicSlugLookupDoesNotExposeDraftArticle() {
        ArticleAppService service = service();
        Article draft = article(1L, ArticleStatus.DRAFT.getCode());
        when(articleRepository.findBySlug("draft-slug")).thenReturn(Optional.of(draft));

        assertNull(service.getBySlug("draft-slug"));
    }

    @Test
    void publicStatsRejectDraftArticle() {
        ArticleAppService service = service();
        Article draft = article(1L, ArticleStatus.DRAFT.getCode());
        when(articleRepository.findById(new ArticleId(1L))).thenReturn(Optional.of(draft));

        assertThrows(BusinessException.class, () -> service.getArticleStats(1L));
    }

    @Test
    void publicViewRecordRejectsDraftArticleBeforeWritingLogs() {
        ArticleAppService service = service();
        Article draft = article(1L, ArticleStatus.DRAFT.getCode());
        when(articleRepository.findById(new ArticleId(1L))).thenReturn(Optional.of(draft));

        RecordArticleViewCommand command = new RecordArticleViewCommand();
        command.setArticleId(1L);
        command.setVisitorId("visitor-1");

        assertThrows(BusinessException.class, () -> service.recordView(command, "127.0.0.1", "JUnit"));
        verify(articleVisitLogRepository, never()).save(any());
        verify(articleViewRecordRepository, never()).save(any());
        verify(articleRepository, never()).increaseViewCount(any());
    }

    private ArticleAppService service() {
        return new ArticleAppService(
                articleRepository,
                articleViewRecordRepository,
                articleVisitLogRepository,
                categoryRepository,
                eventPublisher,
                markdownUtil
        );
    }

    private Article article(Long id, int status) {
        Article article = new Article();
        article.setId(id);
        article.setSlug("draft-slug");
        article.setTitle("Draft");
        article.setStatus(status);
        return article;
    }
}
