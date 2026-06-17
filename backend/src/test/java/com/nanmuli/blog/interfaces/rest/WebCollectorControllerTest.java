package com.nanmuli.blog.interfaces.rest;

import cn.dev33.satoken.stp.StpUtil;
import com.nanmuli.blog.application.webcollector.WebCollectSourceAppService;
import com.nanmuli.blog.application.webcollector.WebCollectorAppService;
import com.nanmuli.blog.infrastructure.crawler.CrawlerTaskClient;
import com.nanmuli.blog.shared.exception.BusinessException;
import com.nanmuli.blog.shared.result.Result;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.MockedStatic;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.mockito.Mockito.mockStatic;

@ExtendWith(MockitoExtension.class)
class WebCollectorControllerTest {

    @Mock
    private WebCollectorAppService collectorAppService;
    @Mock
    private WebCollectSourceAppService sourceAppService;
    @Mock
    private CrawlerTaskClient crawlerTaskClient;

    @InjectMocks
    private WebCollectorController controller;

    @Test
    void getDigestOptimizationTrendClampsLimitAndProxiesToCrawler() {
        Map<String, Object> upstream = Map.of("trend", List.of());
        when(crawlerTaskClient.proxyGet("/api/v1/optimization/digest-trend?limit=50"))
                .thenReturn(upstream);

        Result<Object> result = controller.getDigestOptimizationTrend(999);

        assertThat(result.getCode()).isEqualTo(200);
        assertThat(result.getData()).isSameAs(upstream);
        verify(crawlerTaskClient).proxyGet("/api/v1/optimization/digest-trend?limit=50");
    }

    @Test
    void getDigestOptimizationTrendWrapsCrawlerFailure() {
        when(crawlerTaskClient.proxyGet("/api/v1/optimization/digest-trend?limit=1"))
                .thenThrow(new RuntimeException("crawler down"));

        assertThatThrownBy(() -> controller.getDigestOptimizationTrend(0))
                .isInstanceOf(BusinessException.class)
                .hasMessageContaining("crawler down");
    }

    @Test
    void getSearchFeedbackClampsLimitAndProxiesToCrawler() {
        Map<String, Object> upstream = Map.of("records", List.of(), "total", 0);
        when(crawlerTaskClient.proxyGet("/api/v1/optimization/search-feedback?limit=50"))
                .thenReturn(upstream);

        Result<Object> result = controller.getSearchFeedback(999);

        assertThat(result.getCode()).isEqualTo(200);
        assertThat(result.getData()).isSameAs(upstream);
        verify(crawlerTaskClient).proxyGet("/api/v1/optimization/search-feedback?limit=50");
    }

    @Test
    void getSearchFeedbackWrapsCrawlerFailure() {
        when(crawlerTaskClient.proxyGet("/api/v1/optimization/search-feedback?limit=1"))
                .thenThrow(new RuntimeException("crawler down"));

        assertThatThrownBy(() -> controller.getSearchFeedback(0))
                .isInstanceOf(BusinessException.class)
                .hasMessageContaining("crawler down");
    }

    @Test
    void testSourceDelegatesToSourceAppService() {
        Map<String, Object> upstream = Map.of("crawlable", true, "success_count", 1);

        try (MockedStatic<StpUtil> stp = mockStatic(StpUtil.class)) {
            stp.when(StpUtil::getLoginIdAsLong).thenReturn(1L);
            when(sourceAppService.testSource(10L, 1L)).thenReturn(upstream);

            Result<Object> result = controller.testSource(10L);

            assertThat(result.getCode()).isEqualTo(200);
            assertThat(result.getData()).isSameAs(upstream);
            verify(sourceAppService).testSource(10L, 1L);
        }
    }
}
