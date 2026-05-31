package com.nanmuli.blog.application.webcollector;

import com.nanmuli.blog.application.webcollector.command.CreateSourceCommand;
import com.nanmuli.blog.domain.webcollector.WebCollectSource;
import com.nanmuli.blog.domain.webcollector.WebCollectSourceRepository;
import com.nanmuli.blog.infrastructure.crawler.CrawlerTaskClient;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.MockedStatic;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;

import java.util.Map;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mockStatic;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class WebCollectSourceAppServiceTest {

    @Mock
    private WebCollectSourceRepository sourceRepository;
    @Mock
    private CrawlerTaskClient crawlerTaskClient;

    private WebCollectSourceAppService service;
    private MockedStatic<TransactionSynchronizationManager> tsmMock;

    @BeforeEach
    void setUp() {
        service = new WebCollectSourceAppService(sourceRepository, crawlerTaskClient);
        tsmMock = mockStatic(TransactionSynchronizationManager.class);
        tsmMock.when(TransactionSynchronizationManager::isSynchronizationActive).thenReturn(true);
        tsmMock.when(() -> TransactionSynchronizationManager.registerSynchronization(any()))
                .thenAnswer(invocation -> null);
    }

    @AfterEach
    void tearDown() {
        tsmMock.close();
    }

    @Test
    void createSourceRegistersCrawlerRefreshAfterCommit() {
        when(sourceRepository.existsByNameAndIdNot("HN", null)).thenReturn(false);
        when(sourceRepository.save(any(WebCollectSource.class))).thenAnswer(invocation -> {
            WebCollectSource source = invocation.getArgument(0);
            source.setId(100L);
            return source;
        });

        Long id = service.create(createCommand(), 1L);

        assertThat(id).isEqualTo(100L);
        ArgumentCaptor<TransactionSynchronization> syncCaptor =
                ArgumentCaptor.forClass(TransactionSynchronization.class);
        tsmMock.verify(() -> TransactionSynchronizationManager.registerSynchronization(syncCaptor.capture()));

        syncCaptor.getValue().afterCommit();

        verify(crawlerTaskClient).refreshConfig();
        ArgumentCaptor<WebCollectSource> sourceCaptor = ArgumentCaptor.forClass(WebCollectSource.class);
        verify(sourceRepository).save(sourceCaptor.capture());
        WebCollectSource saved = sourceCaptor.getValue();
        assertThat(saved.getIsActive()).isTrue();
        assertThat(saved.getCrawlMode()).isEqualTo("single");
        assertThat(saved.getMaxPages()).isEqualTo(10);
        assertThat(saved.getFreshnessHours()).isEqualTo(24);
    }

    @Test
    void testSourceSendsCappedPreviewConfigToCrawler() {
        WebCollectSource source = new WebCollectSource();
        source.setId(123L);
        source.setUserId(1L);
        source.setName("GitHub Blog");
        source.setType("rss");
        source.setValue("https://github.blog/feed/");
        source.setContentCategory("hot_trend");
        source.setCrawlMode("single");
        source.setMaxDepth(2);
        source.setMaxPages(20);
        source.setFreshnessHours(168);

        when(sourceRepository.findById(123L)).thenReturn(Optional.of(source));
        when(crawlerTaskClient.testSource(any())).thenReturn(Map.of("crawlable", true));

        Map<String, Object> result = service.testSource(123L, 1L);

        assertThat(result).containsEntry("crawlable", true);
        ArgumentCaptor<Map<String, Object>> bodyCaptor = ArgumentCaptor.forClass(Map.class);
        verify(crawlerTaskClient).testSource(bodyCaptor.capture());
        Map<String, Object> body = bodyCaptor.getValue();
        assertThat(body)
                .containsEntry("type", "rss")
                .containsEntry("value", "https://github.blog/feed/")
                .containsEntry("content_category", "hot_trend")
                .containsEntry("source_id", "123")
                .containsEntry("source_name", "GitHub Blog")
                .containsEntry("max_pages", 3);
    }

    private CreateSourceCommand createCommand() {
        CreateSourceCommand command = new CreateSourceCommand();
        command.setName("HN");
        command.setType("rss");
        command.setValue("https://hnrss.org/newest");
        command.setContentCategory("hot_trend");
        return command;
    }
}
