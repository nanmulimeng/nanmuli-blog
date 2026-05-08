package com.nanmuli.blog.application.webcollector;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.nanmuli.blog.application.article.ArticleAppService;
import com.nanmuli.blog.application.article.command.CreateArticleCommand;
import com.nanmuli.blog.application.dailylog.DailyLogAppService;
import com.nanmuli.blog.application.dailylog.command.CreateDailyLogCommand;
import com.nanmuli.blog.application.webcollector.command.ConvertToArticleCommand;
import com.nanmuli.blog.application.webcollector.command.ConvertToDailyLogCommand;
import com.nanmuli.blog.application.webcollector.command.CreateCollectTaskCommand;
import com.nanmuli.blog.application.webcollector.dto.CollectTaskDTO;
import com.nanmuli.blog.application.webcollector.dto.CollectTaskListDTO;
import com.nanmuli.blog.application.webcollector.query.CollectTaskPageQuery;
import com.nanmuli.blog.domain.webcollector.CollectTaskStatus;
import com.nanmuli.blog.domain.webcollector.WebCollectPageRepository;
import com.nanmuli.blog.domain.webcollector.WebCollectTask;
import com.nanmuli.blog.domain.webcollector.WebCollectTaskRepository;
import com.nanmuli.blog.infrastructure.crawler.CrawlerTaskClient;
import com.nanmuli.blog.shared.exception.BusinessException;
import com.nanmuli.blog.shared.result.PageResult;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.MockedStatic;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;

import java.time.LocalDate;
import java.util.*;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

/**
 * WebCollectorAppService comprehensive unit tests.
 *
 * Uses Mockito to mock: taskRepository, pageRepository, crawlerTaskClient,
 * articleAppService, dailyLogAppService, objectMapper, and the self-proxy.
 *
 * Uses mockStatic for TransactionSynchronizationManager since the AppService
 * registers afterCommit callbacks via that static API.
 */
@ExtendWith(MockitoExtension.class)
class WebCollectorAppServiceTest {

    @Mock
    private WebCollectTaskRepository taskRepository;
    @Mock
    private WebCollectPageRepository pageRepository;
    @Mock
    private CrawlerTaskClient crawlerTaskClient;
    @Mock
    private ArticleAppService articleAppService;
    @Mock
    private DailyLogAppService dailyLogAppService;
    @Mock
    private ObjectMapper objectMapper;
    @Mock
    private WebCollectorAppService self;

    @InjectMocks
    private WebCollectorAppService service;

    private MockedStatic<TransactionSynchronizationManager> tsmMock;

    private static final Long USER_ID = 1L;
    private static final Long TASK_ID = 100L;

    @BeforeEach
    void setUp() {
        tsmMock = mockStatic(TransactionSynchronizationManager.class);
        tsmMock.when(() -> TransactionSynchronizationManager.registerSynchronization(any()))
                .thenAnswer(invocation -> {
                    // Do nothing - afterCommit callbacks are tested separately
                    return null;
                });
    }

    @AfterEach
    void tearDown() {
        tsmMock.close();
    }

    // ============== Helper methods ==============

    private WebCollectTask buildCompletedTask() {
        return buildTask(CollectTaskStatus.COMPLETED.getValue());
    }

    private WebCollectTask buildTask(Integer status) {
        WebCollectTask task = new WebCollectTask();
        task.setId(TASK_ID);
        task.setUserId(USER_ID);
        task.setTaskType("single");
        task.setSourceUrl("https://example.com/article");
        task.setStatus(status);
        task.setTotalPages(1);
        task.setCompletedPages(1);
        task.setVersion(0);
        // createdAt/updatedAt are set by MyBatis-Plus field fill, not settable directly
        task.setTriggerType("manual");
        task.setAiFullContent("# Hello\n\nAI generated content");
        task.setAiTitle("Test AI Title");
        task.setAiSummary("Test AI Summary");
        task.setAiKeyPoints("[\"point1\",\"point2\"]");
        task.setAiTags("[\"tag1\",\"tag2\"]");
        task.setAiCategory("Java");
        return task;
    }

    private CreateCollectTaskCommand buildSingleCommand() {
        CreateCollectTaskCommand cmd = new CreateCollectTaskCommand();
        cmd.setTaskType("single");
        cmd.setSourceUrl("https://example.com/test");
        return cmd;
    }

    private CreateCollectTaskCommand buildKeywordCommand() {
        CreateCollectTaskCommand cmd = new CreateCollectTaskCommand();
        cmd.setTaskType("keyword");
        cmd.setKeyword("Spring Boot");
        return cmd;
    }

    private CreateCollectTaskCommand buildDigestCommand() {
        CreateCollectTaskCommand cmd = new CreateCollectTaskCommand();
        cmd.setTaskType("digest");
        return cmd;
    }

    /**
     * Helper: capture the TransactionSynchronization registered by the service,
     * then invoke its afterCommit() to simulate Spring transaction commit.
     */
    private TransactionSynchronization captureAndInvokeAfterCommit() {
        ArgumentCaptor<TransactionSynchronization> syncCaptor =
                ArgumentCaptor.forClass(TransactionSynchronization.class);
        tsmMock.verify(() -> TransactionSynchronizationManager.registerSynchronization(syncCaptor.capture()));
        TransactionSynchronization sync = syncCaptor.getValue();
        sync.afterCommit();
        return sync;
    }

    // ============== createTask ==============

    @Nested
    @DisplayName("createTask")
    class CreateTaskTests {

        @Test
        @DisplayName("single type - creates task with correct fields")
        void createTask_singleType_success() {
            CreateCollectTaskCommand cmd = buildSingleCommand();

            when(taskRepository.save(any(WebCollectTask.class))).thenAnswer(invocation -> {
                WebCollectTask t = invocation.getArgument(0);
                t.setId(TASK_ID);
                return t;
            });

            Long result = service.createTask(cmd, USER_ID);

            assertThat(result).isEqualTo(TASK_ID);

            ArgumentCaptor<WebCollectTask> captor = ArgumentCaptor.forClass(WebCollectTask.class);
            verify(taskRepository).save(captor.capture());
            WebCollectTask saved = captor.getValue();
            assertThat(saved.getTaskType()).isEqualTo("single");
            assertThat(saved.getSourceUrl()).isEqualTo("https://example.com/test");
            assertThat(saved.getUserId()).isEqualTo(USER_ID);
            assertThat(saved.getStatus()).isEqualTo(CollectTaskStatus.PENDING.getValue());
            assertThat(saved.getTriggerType()).isEqualTo("manual");
            assertThat(saved.getTotalPages()).isEqualTo(1);
            assertThat(saved.getCompletedPages()).isEqualTo(0);
        }

        @Test
        @DisplayName("keyword type - sets totalPages from maxPages")
        void createTask_keywordType_success() {
            CreateCollectTaskCommand cmd = buildKeywordCommand();
            cmd.setMaxPages(5);

            when(taskRepository.save(any(WebCollectTask.class))).thenAnswer(invocation -> {
                WebCollectTask t = invocation.getArgument(0);
                t.setId(TASK_ID);
                return t;
            });

            Long result = service.createTask(cmd, USER_ID);
            assertThat(result).isEqualTo(TASK_ID);

            ArgumentCaptor<WebCollectTask> captor = ArgumentCaptor.forClass(WebCollectTask.class);
            verify(taskRepository).save(captor.capture());
            WebCollectTask saved = captor.getValue();
            assertThat(saved.getTaskType()).isEqualTo("keyword");
            assertThat(saved.getKeyword()).isEqualTo("Spring Boot");
            assertThat(saved.getTotalPages()).isEqualTo(5);
        }

        @Test
        @DisplayName("digest type - rejected with BusinessException")
        void createTask_digestType_rejected() {
            CreateCollectTaskCommand cmd = buildDigestCommand();

            assertThatThrownBy(() -> service.createTask(cmd, USER_ID))
                    .isInstanceOf(BusinessException.class)
                    .hasMessageContaining("日报任务");

            verify(taskRepository, never()).save(any());
        }

        @Test
        @DisplayName("invalid command (no URL for single) - rejected")
        void createTask_invalidCommand_rejected() {
            CreateCollectTaskCommand cmd = new CreateCollectTaskCommand();
            cmd.setTaskType("single");
            // sourceUrl is null => invalid

            assertThatThrownBy(() -> service.createTask(cmd, USER_ID))
                    .isInstanceOf(BusinessException.class)
                    .hasMessageContaining("URL 或关键词不能为空");

            verify(taskRepository, never()).save(any());
        }

        @Test
        @DisplayName("afterCommit - creates Python task and calls self.updatePythonTaskId")
        void createTask_afterCommit_callsPythonAndSelfUpdate() {
            CreateCollectTaskCommand cmd = buildSingleCommand();
            when(taskRepository.save(any(WebCollectTask.class))).thenAnswer(invocation -> {
                WebCollectTask t = invocation.getArgument(0);
                t.setId(TASK_ID);
                return t;
            });
            when(crawlerTaskClient.createTask(anyString(), any(), any(), any(), any(), any(), any(), any()))
                    .thenReturn(42);

            service.createTask(cmd, USER_ID);

            // Simulate afterCommit
            captureAndInvokeAfterCommit();

            // Verify Python client was called
            verify(crawlerTaskClient).createTask(
                    eq("single"), eq("https://example.com/test"), isNull(),
                    anyString(), any(), any(), anyString(), anyString());

            // Verify self.updatePythonTaskId was called
            verify(self).updatePythonTaskId(TASK_ID, 42);
        }

        @Test
        @DisplayName("afterCommit - Python failure calls self.markTaskFailed")
        void createTask_afterCommit_pythonFailure_callsMarkFailed() {
            CreateCollectTaskCommand cmd = buildSingleCommand();
            when(taskRepository.save(any(WebCollectTask.class))).thenAnswer(invocation -> {
                WebCollectTask t = invocation.getArgument(0);
                t.setId(TASK_ID);
                return t;
            });
            when(crawlerTaskClient.createTask(anyString(), any(), any(), any(), any(), any(), any(), any()))
                    .thenThrow(new RuntimeException("Python unavailable"));

            service.createTask(cmd, USER_ID);

            // Simulate afterCommit - should not throw, should call self.markTaskFailed
            assertThatCode(() -> captureAndInvokeAfterCommit()).doesNotThrowAnyException();

            verify(self).markTaskFailed(eq(TASK_ID), contains("Python 服务调用失败"));
        }

        @Test
        @DisplayName("deep type - totalPages defaults to 10 when maxPages is null")
        void createTask_deepType_defaultMaxPages() {
            CreateCollectTaskCommand cmd = new CreateCollectTaskCommand();
            cmd.setTaskType("deep");
            cmd.setSourceUrl("https://example.com");
            // maxPages is null, should default to 10

            when(taskRepository.save(any(WebCollectTask.class))).thenAnswer(invocation -> {
                WebCollectTask t = invocation.getArgument(0);
                t.setId(TASK_ID);
                return t;
            });

            service.createTask(cmd, USER_ID);

            ArgumentCaptor<WebCollectTask> captor = ArgumentCaptor.forClass(WebCollectTask.class);
            verify(taskRepository).save(captor.capture());
            assertThat(captor.getValue().getTotalPages()).isEqualTo(10);
        }

        @Test
        @DisplayName("deep type - uses explicit maxPages")
        void createTask_deepType_explicitMaxPages() {
            CreateCollectTaskCommand cmd = new CreateCollectTaskCommand();
            cmd.setTaskType("deep");
            cmd.setSourceUrl("https://example.com");
            cmd.setMaxPages(3);

            when(taskRepository.save(any(WebCollectTask.class))).thenAnswer(invocation -> {
                WebCollectTask t = invocation.getArgument(0);
                t.setId(TASK_ID);
                return t;
            });

            service.createTask(cmd, USER_ID);

            ArgumentCaptor<WebCollectTask> captor = ArgumentCaptor.forClass(WebCollectTask.class);
            verify(taskRepository).save(captor.capture());
            assertThat(captor.getValue().getTotalPages()).isEqualTo(3);
        }
    }

    // ============== getTask ==============

    @Nested
    @DisplayName("getTask")
    class GetTaskTests {

        @Test
        @DisplayName("completed task - returns DTO without syncing from Python")
        void getTask_completed_returnsDTO() {
            WebCollectTask task = buildCompletedTask();
            when(taskRepository.findById(TASK_ID)).thenReturn(Optional.of(task));

            CollectTaskDTO dto = service.getTask(TASK_ID, USER_ID);

            assertThat(dto).isNotNull();
            assertThat(dto.getId()).isEqualTo(String.valueOf(TASK_ID));
            assertThat(dto.getStatus()).isEqualTo(CollectTaskStatus.COMPLETED.getValue());
            assertThat(dto.getTaskType()).isEqualTo("single");
            // No Python sync for completed tasks
            verify(crawlerTaskClient, never()).getTask(anyInt());
        }

        @Test
        @DisplayName("active task - syncs from Python before returning")
        void getTask_activeTask_syncsFromPython() {
            WebCollectTask task = buildTask(CollectTaskStatus.CRAWLING.getValue());
            task.setPythonTaskId(42);
            when(taskRepository.findById(TASK_ID)).thenReturn(Optional.of(task));

            Map<String, Object> pythonData = new HashMap<>();
            pythonData.put("status", 3);
            pythonData.put("ai_title", "Synced Title");
            pythonData.put("total_pages", 5);
            pythonData.put("completed_pages", 5);
            when(crawlerTaskClient.getTask(42)).thenReturn(Optional.of(pythonData));

            CollectTaskDTO dto = service.getTask(TASK_ID, USER_ID);

            assertThat(dto).isNotNull();
            verify(crawlerTaskClient).getTask(42);
            // syncFromPythonSilent delegates to self.syncPythonTaskToDb
            verify(self).syncPythonTaskToDb(eq(TASK_ID), eq(pythonData));
        }

        @Test
        @DisplayName("task not found - throws BusinessException")
        void getTask_notFound_throws() {
            when(taskRepository.findById(999L)).thenReturn(Optional.empty());

            assertThatThrownBy(() -> service.getTask(999L, USER_ID))
                    .isInstanceOf(BusinessException.class)
                    .hasMessageContaining("任务不存在");
        }

        @Test
        @DisplayName("wrong user - throws BusinessException")
        void getTask_wrongUser_throws() {
            WebCollectTask task = buildCompletedTask();
            when(taskRepository.findById(TASK_ID)).thenReturn(Optional.of(task));

            assertThatThrownBy(() -> service.getTask(TASK_ID, 999L))
                    .isInstanceOf(BusinessException.class)
                    .hasMessageContaining("无权操作此任务");
        }

        @Test
        @DisplayName("old task without pythonTaskId - returns DTO directly")
        void getTask_oldTask_noPythonSync() {
            WebCollectTask task = buildCompletedTask();
            task.setPythonTaskId(null);
            when(taskRepository.findById(TASK_ID)).thenReturn(Optional.of(task));

            CollectTaskDTO dto = service.getTask(TASK_ID, USER_ID);

            assertThat(dto).isNotNull();
            verify(crawlerTaskClient, never()).getTask(anyInt());
        }

        @Test
        @DisplayName("Python sync failure is silently handled")
        void getTask_pythonSyncFailure_handledGracefully() {
            WebCollectTask task = buildTask(CollectTaskStatus.CRAWLING.getValue());
            task.setPythonTaskId(42);
            when(taskRepository.findById(TASK_ID)).thenReturn(Optional.of(task));
            when(crawlerTaskClient.getTask(42)).thenThrow(new RuntimeException("Network error"));

            // Should not throw - syncFromPythonSilent swallows exceptions
            CollectTaskDTO dto = service.getTask(TASK_ID, USER_ID);

            assertThat(dto).isNotNull();
            assertThat(dto.getStatus()).isEqualTo(CollectTaskStatus.CRAWLING.getValue());
        }
    }

    // ============== listTasks ==============

    @Nested
    @DisplayName("listTasks")
    class ListTasksTests {

        @Test
        @DisplayName("returns PageResult with DTOs")
        void listTasks_returnsPageResult() {
            CollectTaskPageQuery query = new CollectTaskPageQuery();
            query.setCurrent(1L);
            query.setSize(10L);

            Page<WebCollectTask> page = new Page<>(1, 10);
            WebCollectTask task = buildCompletedTask();
            page.setRecords(List.of(task));
            page.setTotal(1);

            when(taskRepository.findPageFiltered(any(IPage.class), eq(USER_ID), any(), any(), any()))
                    .thenReturn(page);

            PageResult<CollectTaskListDTO> result = service.listTasks(query, USER_ID);

            assertThat(result).isNotNull();
            assertThat(result.getTotal()).isEqualTo(1);
            assertThat(result.getRecords()).hasSize(1);
            assertThat(result.getRecords().get(0).getId()).isEqualTo(String.valueOf(TASK_ID));
        }

        @Test
        @DisplayName("empty result returns empty records")
        void listTasks_emptyResult() {
            CollectTaskPageQuery query = new CollectTaskPageQuery();
            Page<WebCollectTask> page = new Page<>(1, 10);
            page.setRecords(Collections.emptyList());
            page.setTotal(0);

            when(taskRepository.findPageFiltered(any(IPage.class), eq(USER_ID), any(), any(), any()))
                    .thenReturn(page);

            PageResult<CollectTaskListDTO> result = service.listTasks(query, USER_ID);

            assertThat(result.getRecords()).isEmpty();
            assertThat(result.getTotal()).isEqualTo(0);
        }
    }

    // ============== deleteTask ==============

    @Nested
    @DisplayName("deleteTask")
    class DeleteTaskTests {

        @Test
        @DisplayName("running task - rejected")
        void deleteTask_runningTask_rejected() {
            WebCollectTask task = buildTask(CollectTaskStatus.CRAWLING.getValue());
            when(taskRepository.findById(TASK_ID)).thenReturn(Optional.of(task));

            assertThatThrownBy(() -> service.deleteTask(TASK_ID, USER_ID))
                    .isInstanceOf(BusinessException.class)
                    .hasMessageContaining("正在处理中");

            verify(taskRepository, never()).deleteById(any());
        }

        @Test
        @DisplayName("processing task - rejected")
        void deleteTask_processingTask_rejected() {
            WebCollectTask task = buildTask(CollectTaskStatus.PROCESSING.getValue());
            when(taskRepository.findById(TASK_ID)).thenReturn(Optional.of(task));

            assertThatThrownBy(() -> service.deleteTask(TASK_ID, USER_ID))
                    .isInstanceOf(BusinessException.class)
                    .hasMessageContaining("正在处理中");
        }

        @Test
        @DisplayName("completed task with pythonTaskId - deletes and registers Python delete in afterCommit")
        void deleteTask_completedTask_success() {
            WebCollectTask task = buildCompletedTask();
            task.setPythonTaskId(42);
            when(taskRepository.findById(TASK_ID)).thenReturn(Optional.of(task));

            service.deleteTask(TASK_ID, USER_ID);

            verify(pageRepository).deleteByTaskId(TASK_ID);
            verify(taskRepository).deleteById(TASK_ID);

            // Simulate afterCommit - Python delete should be called
            captureAndInvokeAfterCommit();
            verify(crawlerTaskClient).deleteTask(42);
        }

        @Test
        @DisplayName("completed task without pythonTaskId - no Python delete call")
        void deleteTask_noPythonTaskId_noPythonDelete() {
            WebCollectTask task = buildCompletedTask();
            task.setPythonTaskId(null);
            when(taskRepository.findById(TASK_ID)).thenReturn(Optional.of(task));

            service.deleteTask(TASK_ID, USER_ID);

            verify(pageRepository).deleteByTaskId(TASK_ID);
            verify(taskRepository).deleteById(TASK_ID);
            // No synchronization registered => no afterCommit needed
            tsmMock.verify(() -> TransactionSynchronizationManager.registerSynchronization(any()), never());
        }

        @Test
        @DisplayName("failed task - deletes successfully")
        void deleteTask_failedTask_success() {
            WebCollectTask task = buildTask(CollectTaskStatus.FAILED.getValue());
            when(taskRepository.findById(TASK_ID)).thenReturn(Optional.of(task));

            service.deleteTask(TASK_ID, USER_ID);

            verify(taskRepository).deleteById(TASK_ID);
        }
    }

    // ============== retryTask ==============

    @Nested
    @DisplayName("retryTask")
    class RetryTaskTests {

        @Test
        @DisplayName("non-failed task - rejected")
        void retryTask_nonFailed_rejected() {
            WebCollectTask task = buildCompletedTask();
            when(taskRepository.findById(TASK_ID)).thenReturn(Optional.of(task));

            assertThatThrownBy(() -> service.retryTask(TASK_ID, USER_ID))
                    .isInstanceOf(BusinessException.class)
                    .hasMessageContaining("只有失败的任务才能重试");

            verify(taskRepository, never()).save(any());
        }

        @Test
        @DisplayName("pending task - rejected")
        void retryTask_pending_rejected() {
            WebCollectTask task = buildTask(CollectTaskStatus.PENDING.getValue());
            when(taskRepository.findById(TASK_ID)).thenReturn(Optional.of(task));

            assertThatThrownBy(() -> service.retryTask(TASK_ID, USER_ID))
                    .isInstanceOf(BusinessException.class)
                    .hasMessageContaining("只有失败的任务才能重试");
        }

        @Test
        @DisplayName("failed task - resets fields and returns taskId")
        void retryTask_failedTask_resetsFields() {
            WebCollectTask task = buildTask(CollectTaskStatus.FAILED.getValue());
            task.setErrorMessage("Previous error");
            task.setAiTitle("Old Title");
            task.setAiSummary("Old Summary");
            task.setAiFullContent("Old Content");
            task.setTokensUsed(100);
            task.setCompletedPages(2);
            task.setPythonTaskId(42);

            when(taskRepository.findById(TASK_ID)).thenReturn(Optional.of(task));
            when(taskRepository.save(any(WebCollectTask.class))).thenReturn(task);

            Long result = service.retryTask(TASK_ID, USER_ID);

            assertThat(result).isEqualTo(TASK_ID);

            ArgumentCaptor<WebCollectTask> captor = ArgumentCaptor.forClass(WebCollectTask.class);
            verify(taskRepository).save(captor.capture());
            WebCollectTask saved = captor.getValue();
            assertThat(saved.getStatus()).isEqualTo(CollectTaskStatus.PENDING.getValue());
            assertThat(saved.getErrorMessage()).isNull();
            assertThat(saved.getAiTitle()).isNull();
            assertThat(saved.getAiSummary()).isNull();
            assertThat(saved.getAiFullContent()).isNull();
            assertThat(saved.getTokensUsed()).isNull();
            assertThat(saved.getCompletedPages()).isEqualTo(0);

            verify(pageRepository).deleteByTaskId(TASK_ID);
        }

        @Test
        @DisplayName("afterCommit - retries Python task via crawlerTaskClient")
        void retryTask_afterCommit_retriesPythonTask() {
            WebCollectTask task = buildTask(CollectTaskStatus.FAILED.getValue());
            task.setPythonTaskId(42);

            when(taskRepository.findById(TASK_ID)).thenReturn(Optional.of(task));
            when(taskRepository.save(any(WebCollectTask.class))).thenReturn(task);

            service.retryTask(TASK_ID, USER_ID);

            // Simulate afterCommit
            captureAndInvokeAfterCommit();

            verify(crawlerTaskClient).retryTask(42);
        }

        @Test
        @DisplayName("afterCommit - retry fails, creates new Python task")
        void retryTask_afterCommit_retryFails_createsNewTask() {
            WebCollectTask task = buildTask(CollectTaskStatus.FAILED.getValue());
            task.setPythonTaskId(42);
            task.setTaskType("single");
            task.setSourceUrl("https://example.com");
            task.setSearchEngine("bing");
            task.setMaxDepth(1);
            task.setMaxPages(10);
            task.setAiTemplate("tech_summary");
            task.setTimeRange("week");

            when(taskRepository.findById(TASK_ID)).thenReturn(Optional.of(task));
            when(taskRepository.save(any(WebCollectTask.class))).thenReturn(task);
            doThrow(new RuntimeException("retry failed")).when(crawlerTaskClient).retryTask(42);
            when(crawlerTaskClient.createTask(anyString(), any(), any(), any(), any(), any(), any(), any()))
                    .thenReturn(99);

            service.retryTask(TASK_ID, USER_ID);

            captureAndInvokeAfterCommit();

            verify(crawlerTaskClient).retryTask(42); // First attempt
            verify(crawlerTaskClient).createTask( // Fallback: create new
                    eq("single"), eq("https://example.com"), isNull(),
                    eq("bing"), eq(1), eq(10), eq("tech_summary"), eq("week"));
            verify(self).updatePythonTaskId(TASK_ID, 99);
        }

        @Test
        @DisplayName("afterCommit - no pythonTaskId, creates new Python task directly")
        void retryTask_afterCommit_noPythonTaskId_createsNewTask() {
            WebCollectTask task = buildTask(CollectTaskStatus.FAILED.getValue());
            task.setPythonTaskId(null);
            task.setTaskType("keyword");
            task.setKeyword("test query");
            // buildTask sets sourceUrl to "https://example.com/article"

            when(taskRepository.findById(TASK_ID)).thenReturn(Optional.of(task));
            when(taskRepository.save(any(WebCollectTask.class))).thenReturn(task);
            when(crawlerTaskClient.createTask(anyString(), any(), any(), any(), any(), any(), any(), any()))
                    .thenReturn(55);

            service.retryTask(TASK_ID, USER_ID);

            captureAndInvokeAfterCommit();

            verify(crawlerTaskClient, never()).retryTask(anyInt());
            // The retry afterCommit uses the task's field values, including sourceUrl from buildTask
            verify(crawlerTaskClient).createTask(
                    eq("keyword"),
                    eq("https://example.com/article"),
                    eq("test query"),
                    any(), any(), any(), any(), any());
            verify(self).updatePythonTaskId(TASK_ID, 55);
        }
    }

    // ============== convertToArticle ==============

    @Nested
    @DisplayName("convertToArticle")
    class ConvertToArticleTests {

        @Test
        @DisplayName("non-terminal task - rejected")
        void convertToArticle_activeTask_rejected() {
            WebCollectTask task = buildTask(CollectTaskStatus.CRAWLING.getValue());
            when(taskRepository.findById(TASK_ID)).thenReturn(Optional.of(task));

            ConvertToArticleCommand cmd = new ConvertToArticleCommand();

            assertThatThrownBy(() -> service.convertToArticle(TASK_ID, cmd, USER_ID))
                    .isInstanceOf(BusinessException.class)
                    .hasMessageContaining("任务尚未完成");
        }

        @Test
        @DisplayName("completed task - converts to article successfully")
        void convertToArticle_completedTask_success() {
            WebCollectTask task = buildCompletedTask();
            when(taskRepository.findById(TASK_ID)).thenReturn(Optional.of(task));
            when(articleAppService.create(any(CreateArticleCommand.class))).thenReturn(500L);

            ConvertToArticleCommand cmd = new ConvertToArticleCommand();
            cmd.setTitle("My Article");
            cmd.setCategoryId(10L);

            Long articleId = service.convertToArticle(TASK_ID, cmd, USER_ID);

            assertThat(articleId).isEqualTo(500L);

            ArgumentCaptor<CreateArticleCommand> articleCaptor = ArgumentCaptor.forClass(CreateArticleCommand.class);
            verify(articleAppService).create(articleCaptor.capture());
            CreateArticleCommand articleCmd = articleCaptor.getValue();
            assertThat(articleCmd.getTitle()).isEqualTo("My Article");
            assertThat(articleCmd.getIsOriginal()).isEqualTo(false);
            assertThat(articleCmd.getOriginalUrl()).isEqualTo("https://example.com/article");
            assertThat(articleCmd.getStatus()).isEqualTo(2); // draft
            assertThat(articleCmd.getSummary()).isEqualTo("Test AI Summary");

            ArgumentCaptor<WebCollectTask> taskCaptor = ArgumentCaptor.forClass(WebCollectTask.class);
            verify(taskRepository).save(taskCaptor.capture());
            assertThat(taskCaptor.getValue().getArticleId()).isEqualTo(500L);
        }

        @Test
        @DisplayName("completed task with no custom title - uses aiTitle")
        void convertToArticle_usesAiTitle_whenNoCustomTitle() {
            WebCollectTask task = buildCompletedTask();
            when(taskRepository.findById(TASK_ID)).thenReturn(Optional.of(task));
            when(articleAppService.create(any(CreateArticleCommand.class))).thenReturn(501L);

            ConvertToArticleCommand cmd = new ConvertToArticleCommand();
            // title is null, should use aiTitle

            Long articleId = service.convertToArticle(TASK_ID, cmd, USER_ID);

            ArgumentCaptor<CreateArticleCommand> articleCaptor = ArgumentCaptor.forClass(CreateArticleCommand.class);
            verify(articleAppService).create(articleCaptor.capture());
            assertThat(articleCaptor.getValue().getTitle()).isEqualTo("Test AI Title");
        }

        @Test
        @DisplayName("blank custom title falls back to aiTitle")
        void convertToArticle_blankTitle_fallsBackToAiTitle() {
            WebCollectTask task = buildCompletedTask();
            when(taskRepository.findById(TASK_ID)).thenReturn(Optional.of(task));
            when(articleAppService.create(any(CreateArticleCommand.class))).thenReturn(700L);

            ConvertToArticleCommand cmd = new ConvertToArticleCommand();
            cmd.setTitle("   "); // blank

            service.convertToArticle(TASK_ID, cmd, USER_ID);

            ArgumentCaptor<CreateArticleCommand> captor = ArgumentCaptor.forClass(CreateArticleCommand.class);
            verify(articleAppService).create(captor.capture());
            assertThat(captor.getValue().getTitle()).isEqualTo("Test AI Title");
        }

        @Test
        @DisplayName("already converted task - rejected")
        void convertToArticle_alreadyConverted_rejected() {
            WebCollectTask task = buildCompletedTask();
            task.setArticleId(500L);
            when(taskRepository.findById(TASK_ID)).thenReturn(Optional.of(task));

            ConvertToArticleCommand cmd = new ConvertToArticleCommand();

            assertThatThrownBy(() -> service.convertToArticle(TASK_ID, cmd, USER_ID))
                    .isInstanceOf(BusinessException.class)
                    .hasMessageContaining("已转为文章");
        }

        @Test
        @DisplayName("empty content task - rejected")
        void convertToArticle_emptyContent_rejected() {
            WebCollectTask task = buildCompletedTask();
            task.setAiFullContent("");
            task.setPythonTaskId(null);
            when(taskRepository.findById(TASK_ID)).thenReturn(Optional.of(task));
            when(pageRepository.findByTaskIdOrderBySortOrder(TASK_ID)).thenReturn(Collections.emptyList());

            ConvertToArticleCommand cmd = new ConvertToArticleCommand();

            assertThatThrownBy(() -> service.convertToArticle(TASK_ID, cmd, USER_ID))
                    .isInstanceOf(BusinessException.class)
                    .hasMessageContaining("内容为空");
        }

        @Test
        @DisplayName("failed task - can still convert to article")
        void convertToArticle_failedTask_success() {
            WebCollectTask task = buildTask(CollectTaskStatus.FAILED.getValue());
            task.setAiFullContent("Some content despite failure");
            when(taskRepository.findById(TASK_ID)).thenReturn(Optional.of(task));
            when(articleAppService.create(any(CreateArticleCommand.class))).thenReturn(502L);

            ConvertToArticleCommand cmd = new ConvertToArticleCommand();

            Long articleId = service.convertToArticle(TASK_ID, cmd, USER_ID);
            assertThat(articleId).isEqualTo(502L);
        }

        @Test
        @DisplayName("uses URL as fallback title when aiTitle is null")
        void convertToArticle_fallbackTitle_fromUrl() {
            WebCollectTask task = buildCompletedTask();
            task.setAiTitle(null);
            when(taskRepository.findById(TASK_ID)).thenReturn(Optional.of(task));
            when(articleAppService.create(any(CreateArticleCommand.class))).thenReturn(600L);

            ConvertToArticleCommand cmd = new ConvertToArticleCommand();

            service.convertToArticle(TASK_ID, cmd, USER_ID);

            ArgumentCaptor<CreateArticleCommand> captor = ArgumentCaptor.forClass(CreateArticleCommand.class);
            verify(articleAppService).create(captor.capture());
            String title = captor.getValue().getTitle();
            assertThat(title).startsWith("采集: https://example.com/article");
        }

        @Test
        @DisplayName("truncates long URL in fallback title")
        void convertToArticle_truncatesLongUrl() {
            WebCollectTask task = buildCompletedTask();
            task.setAiTitle(null);
            task.setSourceUrl("https://example.com/" + "a".repeat(100));
            when(taskRepository.findById(TASK_ID)).thenReturn(Optional.of(task));
            when(articleAppService.create(any(CreateArticleCommand.class))).thenReturn(601L);

            ConvertToArticleCommand cmd = new ConvertToArticleCommand();

            service.convertToArticle(TASK_ID, cmd, USER_ID);

            ArgumentCaptor<CreateArticleCommand> captor = ArgumentCaptor.forClass(CreateArticleCommand.class);
            verify(articleAppService).create(captor.capture());
            String title = captor.getValue().getTitle();
            assertThat(title).contains("...");
            assertThat(title.length()).isLessThanOrEqualTo(100);
        }
    }

    // ============== convertToDailyLog ==============

    @Nested
    @DisplayName("convertToDailyLog")
    class ConvertToDailyLogTests {

        @Test
        @DisplayName("non-terminal task - rejected")
        void convertToDailyLog_activeTask_rejected() {
            WebCollectTask task = buildTask(CollectTaskStatus.PROCESSING.getValue());
            when(taskRepository.findById(TASK_ID)).thenReturn(Optional.of(task));

            ConvertToDailyLogCommand cmd = new ConvertToDailyLogCommand();

            assertThatThrownBy(() -> service.convertToDailyLog(TASK_ID, cmd, USER_ID))
                    .isInstanceOf(BusinessException.class)
                    .hasMessageContaining("任务尚未完成");
        }

        @Test
        @DisplayName("completed task - converts to daily log successfully")
        void convertToDailyLog_completedTask_success() {
            WebCollectTask task = buildCompletedTask();
            when(taskRepository.findById(TASK_ID)).thenReturn(Optional.of(task));
            when(dailyLogAppService.create(any(CreateDailyLogCommand.class))).thenReturn(300L);

            ConvertToDailyLogCommand cmd = new ConvertToDailyLogCommand();
            cmd.setMood("happy");
            cmd.setWeather("sunny");
            cmd.setLogDate(LocalDate.of(2026, 5, 1));
            cmd.setIsPublic(true);

            Long dailyLogId = service.convertToDailyLog(TASK_ID, cmd, USER_ID);

            assertThat(dailyLogId).isEqualTo(300L);

            ArgumentCaptor<CreateDailyLogCommand> logCaptor = ArgumentCaptor.forClass(CreateDailyLogCommand.class);
            verify(dailyLogAppService).create(logCaptor.capture());
            CreateDailyLogCommand logCmd = logCaptor.getValue();
            assertThat(logCmd.getMood()).isEqualTo("happy");
            assertThat(logCmd.getWeather()).isEqualTo("sunny");
            assertThat(logCmd.getLogDate()).isEqualTo(LocalDate.of(2026, 5, 1));
            assertThat(logCmd.getIsPublic()).isEqualTo(true);

            ArgumentCaptor<WebCollectTask> taskCaptor = ArgumentCaptor.forClass(WebCollectTask.class);
            verify(taskRepository).save(taskCaptor.capture());
            assertThat(taskCaptor.getValue().getDailyLogId()).isEqualTo(300L);
        }

        @Test
        @DisplayName("null logDate - defaults to today")
        void convertToDailyLog_nullLogDate_defaultsToToday() {
            WebCollectTask task = buildCompletedTask();
            when(taskRepository.findById(TASK_ID)).thenReturn(Optional.of(task));
            when(dailyLogAppService.create(any(CreateDailyLogCommand.class))).thenReturn(301L);

            ConvertToDailyLogCommand cmd = new ConvertToDailyLogCommand();
            cmd.setLogDate(null);

            service.convertToDailyLog(TASK_ID, cmd, USER_ID);

            ArgumentCaptor<CreateDailyLogCommand> logCaptor = ArgumentCaptor.forClass(CreateDailyLogCommand.class);
            verify(dailyLogAppService).create(logCaptor.capture());
            assertThat(logCaptor.getValue().getLogDate()).isEqualTo(LocalDate.now());
        }

        @Test
        @DisplayName("already converted task - rejected")
        void convertToDailyLog_alreadyConverted_rejected() {
            WebCollectTask task = buildCompletedTask();
            task.setDailyLogId(300L);
            when(taskRepository.findById(TASK_ID)).thenReturn(Optional.of(task));

            ConvertToDailyLogCommand cmd = new ConvertToDailyLogCommand();

            assertThatThrownBy(() -> service.convertToDailyLog(TASK_ID, cmd, USER_ID))
                    .isInstanceOf(BusinessException.class)
                    .hasMessageContaining("已转为日志");
        }

        @Test
        @DisplayName("empty content - rejected")
        void convertToDailyLog_emptyContent_rejected() {
            WebCollectTask task = buildCompletedTask();
            task.setAiFullContent("   ");
            task.setPythonTaskId(null);
            when(taskRepository.findById(TASK_ID)).thenReturn(Optional.of(task));
            when(pageRepository.findByTaskIdOrderBySortOrder(TASK_ID)).thenReturn(Collections.emptyList());

            ConvertToDailyLogCommand cmd = new ConvertToDailyLogCommand();

            assertThatThrownBy(() -> service.convertToDailyLog(TASK_ID, cmd, USER_ID))
                    .isInstanceOf(BusinessException.class)
                    .hasMessageContaining("内容为空");
        }

        @Test
        @DisplayName("null isPublic - defaults to false")
        void convertToDailyLog_nullIsPublic_defaultsToFalse() {
            WebCollectTask task = buildCompletedTask();
            when(taskRepository.findById(TASK_ID)).thenReturn(Optional.of(task));
            when(dailyLogAppService.create(any(CreateDailyLogCommand.class))).thenReturn(302L);

            ConvertToDailyLogCommand cmd = new ConvertToDailyLogCommand();
            cmd.setIsPublic(null);

            service.convertToDailyLog(TASK_ID, cmd, USER_ID);

            ArgumentCaptor<CreateDailyLogCommand> logCaptor = ArgumentCaptor.forClass(CreateDailyLogCommand.class);
            verify(dailyLogAppService).create(logCaptor.capture());
            assertThat(logCaptor.getValue().getIsPublic()).isEqualTo(false);
        }
    }

    // ============== DTO conversion ==============

    @Nested
    @DisplayName("DTO conversion")
    class DtoConversionTests {

        @Test
        @DisplayName("convertToDTO - Long articleId/dailyLogId mapped to String")
        void convertToDTO_longIds_mappedToStrings() {
            WebCollectTask task = buildCompletedTask();
            task.setArticleId(500L);
            task.setDailyLogId(300L);
            when(taskRepository.findById(TASK_ID)).thenReturn(Optional.of(task));

            CollectTaskDTO dto = service.getTask(TASK_ID, USER_ID);

            assertThat(dto.getArticleId()).isEqualTo("500");
            assertThat(dto.getDailyLogId()).isEqualTo("300");
            assertThat(dto.getId()).isEqualTo(String.valueOf(TASK_ID));
        }

        @Test
        @DisplayName("convertToDTO - null articleId/dailyLogId stays null")
        void convertToDTO_nullIds_stayNull() {
            WebCollectTask task = buildCompletedTask();
            task.setArticleId(null);
            task.setDailyLogId(null);
            when(taskRepository.findById(TASK_ID)).thenReturn(Optional.of(task));

            CollectTaskDTO dto = service.getTask(TASK_ID, USER_ID);

            assertThat(dto.getArticleId()).isNull();
            assertThat(dto.getDailyLogId()).isNull();
        }

        @Test
        @DisplayName("convertToDTO - status labels populated correctly")
        void convertToDTO_statusLabels_populated() {
            WebCollectTask task = buildCompletedTask();
            when(taskRepository.findById(TASK_ID)).thenReturn(Optional.of(task));

            CollectTaskDTO dto = service.getTask(TASK_ID, USER_ID);

            assertThat(dto.getStatusLabel()).isEqualTo("已完成");
            assertThat(dto.getStatusDisplay()).isEqualTo("查看结果");
            assertThat(dto.getTaskTypeLabel()).isEqualTo("单页爬取");
        }

        @Test
        @DisplayName("convertToDTO - invalid status value gets fallback label")
        void convertToDTO_invalidStatus_unknownLabel() {
            WebCollectTask task = buildCompletedTask();
            task.setStatus(99); // invalid status
            when(taskRepository.findById(TASK_ID)).thenReturn(Optional.of(task));

            CollectTaskDTO dto = service.getTask(TASK_ID, USER_ID);

            assertThat(dto.getStatusLabel()).isEqualTo("未知");
            assertThat(dto.getStatusDisplay()).isEqualTo("未知");
        }

        @Test
        @DisplayName("convertToDTO - progress percent calculated correctly")
        void convertToDTO_progressPercent_calculated() {
            WebCollectTask task = buildCompletedTask();
            task.setTotalPages(10);
            task.setCompletedPages(7);
            when(taskRepository.findById(TASK_ID)).thenReturn(Optional.of(task));

            CollectTaskDTO dto = service.getTask(TASK_ID, USER_ID);

            assertThat(dto.getProgressPercent()).isEqualTo(70);
        }

        @Test
        @DisplayName("convertToDTO - zero totalPages gives 0 progress")
        void convertToDTO_zeroTotalPages_zeroProgress() {
            WebCollectTask task = buildCompletedTask();
            task.setTotalPages(0);
            task.setCompletedPages(0);
            when(taskRepository.findById(TASK_ID)).thenReturn(Optional.of(task));

            CollectTaskDTO dto = service.getTask(TASK_ID, USER_ID);

            assertThat(dto.getProgressPercent()).isEqualTo(0);
        }

        @Test
        @DisplayName("convertToDTO - null totalPages gives 0 progress")
        void convertToDTO_nullTotalPages_zeroProgress() {
            WebCollectTask task = buildCompletedTask();
            task.setTotalPages(null);
            when(taskRepository.findById(TASK_ID)).thenReturn(Optional.of(task));

            CollectTaskDTO dto = service.getTask(TASK_ID, USER_ID);

            assertThat(dto.getProgressPercent()).isEqualTo(0);
        }

        @Test
        @DisplayName("convertToListDTO - Long articleId/dailyLogId mapped to String")
        void convertToListDTO_longIds_mappedToStrings() {
            WebCollectTask task = buildCompletedTask();
            task.setArticleId(500L);
            task.setDailyLogId(300L);

            CollectTaskPageQuery query = new CollectTaskPageQuery();
            Page<WebCollectTask> page = new Page<>(1, 10);
            page.setRecords(List.of(task));
            page.setTotal(1);

            when(taskRepository.findPageFiltered(any(IPage.class), eq(USER_ID), any(), any(), any()))
                    .thenReturn(page);

            PageResult<CollectTaskListDTO> result = service.listTasks(query, USER_ID);

            CollectTaskListDTO listDto = result.getRecords().get(0);
            assertThat(listDto.getArticleId()).isEqualTo("500");
            assertThat(listDto.getDailyLogId()).isEqualTo("300");
            assertThat(listDto.getId()).isEqualTo(String.valueOf(TASK_ID));
        }

        @Test
        @DisplayName("convertToListDTO - long aiSummary truncated to 200 chars")
        void convertToListDTO_longSummary_truncated() {
            WebCollectTask task = buildCompletedTask();
            String longSummary = "A".repeat(250);
            task.setAiSummary(longSummary);

            CollectTaskPageQuery query = new CollectTaskPageQuery();
            Page<WebCollectTask> page = new Page<>(1, 10);
            page.setRecords(List.of(task));
            page.setTotal(1);

            when(taskRepository.findPageFiltered(any(IPage.class), eq(USER_ID), any(), any(), any()))
                    .thenReturn(page);

            PageResult<CollectTaskListDTO> result = service.listTasks(query, USER_ID);

            String summary = result.getRecords().get(0).getAiSummary();
            assertThat(summary).hasSize(203); // 200 + "..."
            assertThat(summary).endsWith("...");
        }

        @Test
        @DisplayName("convertToListDTO - short aiSummary not truncated")
        void convertToListDTO_shortSummary_notTruncated() {
            WebCollectTask task = buildCompletedTask();
            task.setAiSummary("Short summary");

            CollectTaskPageQuery query = new CollectTaskPageQuery();
            Page<WebCollectTask> page = new Page<>(1, 10);
            page.setRecords(List.of(task));
            page.setTotal(1);

            when(taskRepository.findPageFiltered(any(IPage.class), eq(USER_ID), any(), any(), any()))
                    .thenReturn(page);

            PageResult<CollectTaskListDTO> result = service.listTasks(query, USER_ID);

            assertThat(result.getRecords().get(0).getAiSummary()).isEqualTo("Short summary");
        }
    }

    // ============== BeanUtils type mismatch verification ==============

    @Nested
    @DisplayName("BeanUtils type mismatch safety")
    class BeanUtilsTypeMismatchTests {

        @Test
        @DisplayName("DTO articleId/dailyLogId - Long to String conversion works correctly")
        void beanUtils_longToString_conversionWorks() {
            // Verifies that the explicit post-copy assignments correctly convert
            // Long articleId/dailyLogId to String in the DTO.
            // BeanUtils.copyProperties skips Long->String (type mismatch),
            // so the explicit String.valueOf() calls are essential.
            WebCollectTask task = buildCompletedTask();
            task.setArticleId(999L);
            task.setDailyLogId(888L);
            when(taskRepository.findById(TASK_ID)).thenReturn(Optional.of(task));

            CollectTaskDTO dto = service.getTask(TASK_ID, USER_ID);

            assertThat(dto.getArticleId()).isEqualTo("999");
            assertThat(dto.getDailyLogId()).isEqualTo("888");
        }

        @Test
        @DisplayName("listDTO - Long to String conversion works correctly")
        void listDTO_longToString_conversionWorks() {
            WebCollectTask task = buildCompletedTask();
            task.setArticleId(777L);
            task.setDailyLogId(666L);

            CollectTaskPageQuery query = new CollectTaskPageQuery();
            Page<WebCollectTask> page = new Page<>(1, 10);
            page.setRecords(List.of(task));
            page.setTotal(1);

            when(taskRepository.findPageFiltered(any(IPage.class), eq(USER_ID), any(), any(), any()))
                    .thenReturn(page);

            PageResult<CollectTaskListDTO> result = service.listTasks(query, USER_ID);

            assertThat(result.getRecords().get(0).getArticleId()).isEqualTo("777");
            assertThat(result.getRecords().get(0).getDailyLogId()).isEqualTo("666");
        }
    }

    // ============== REQUIRES_NEW methods ==============

    @Nested
    @DisplayName("REQUIRES_NEW self-proxy methods")
    class RequiresNewMethodsTests {

        @Test
        @DisplayName("updatePythonTaskId - finds task and updates pythonTaskId")
        void updatePythonTaskId_updatesField() {
            WebCollectTask task = buildCompletedTask();
            when(taskRepository.findById(TASK_ID)).thenReturn(Optional.of(task));

            service.updatePythonTaskId(TASK_ID, 42);

            ArgumentCaptor<WebCollectTask> captor = ArgumentCaptor.forClass(WebCollectTask.class);
            verify(taskRepository).save(captor.capture());
            assertThat(captor.getValue().getPythonTaskId()).isEqualTo(42);
        }

        @Test
        @DisplayName("updatePythonTaskId - task not found, does nothing")
        void updatePythonTaskId_notFound_noError() {
            when(taskRepository.findById(TASK_ID)).thenReturn(Optional.empty());

            assertThatCode(() -> service.updatePythonTaskId(TASK_ID, 42)).doesNotThrowAnyException();
            verify(taskRepository, never()).save(any());
        }

        @Test
        @DisplayName("markTaskFailed - sets errorMessage and status to FAILED")
        void markTaskFailed_setsErrorAndStatus() {
            WebCollectTask task = buildCompletedTask();
            when(taskRepository.findById(TASK_ID)).thenReturn(Optional.of(task));

            service.markTaskFailed(TASK_ID, "Something went wrong");

            ArgumentCaptor<WebCollectTask> captor = ArgumentCaptor.forClass(WebCollectTask.class);
            verify(taskRepository).save(captor.capture());
            WebCollectTask saved = captor.getValue();
            assertThat(saved.getStatus()).isEqualTo(CollectTaskStatus.FAILED.getValue());
            assertThat(saved.getErrorMessage()).isEqualTo("Something went wrong");
        }

        @Test
        @DisplayName("markTaskFailed - task not found, does nothing")
        void markTaskFailed_notFound_noError() {
            when(taskRepository.findById(TASK_ID)).thenReturn(Optional.empty());

            assertThatCode(() -> service.markTaskFailed(TASK_ID, "error")).doesNotThrowAnyException();
            verify(taskRepository, never()).save(any());
        }

        @Test
        @DisplayName("syncPythonTaskToDb - updates task from Python data")
        void syncPythonTaskToDb_updatesFromPython() {
            WebCollectTask task = buildTask(CollectTaskStatus.CRAWLING.getValue());
            when(taskRepository.findById(TASK_ID)).thenReturn(Optional.of(task));

            Map<String, Object> pythonData = new HashMap<>();
            pythonData.put("status", 3);
            pythonData.put("ai_title", "Python Title");
            pythonData.put("ai_summary", "Python Summary");
            pythonData.put("total_pages", 5);
            pythonData.put("completed_pages", 3);
            pythonData.put("error_message", null);

            service.syncPythonTaskToDb(TASK_ID, pythonData);

            ArgumentCaptor<WebCollectTask> captor = ArgumentCaptor.forClass(WebCollectTask.class);
            verify(taskRepository).save(captor.capture());
            WebCollectTask saved = captor.getValue();
            assertThat(saved.getStatus()).isEqualTo(CollectTaskStatus.COMPLETED.getValue());
            assertThat(saved.getAiTitle()).isEqualTo("Python Title");
            assertThat(saved.getTotalPages()).isEqualTo(5);
            assertThat(saved.getCompletedPages()).isEqualTo(3);
        }

        @Test
        @DisplayName("syncPythonTaskToDb - task not found, does nothing")
        void syncPythonTaskToDb_notFound_noError() {
            when(taskRepository.findById(TASK_ID)).thenReturn(Optional.empty());

            assertThatCode(() -> service.syncPythonTaskToDb(TASK_ID, Map.of())).doesNotThrowAnyException();
            verify(taskRepository, never()).save(any());
        }
    }

    // ============== Utility methods ==============

    @Nested
    @DisplayName("Utility methods")
    class UtilityTests {

        @Test
        @DisplayName("hashUrl - produces consistent SHA-256 hash")
        void hashUrl_consistent() {
            String hash1 = WebCollectorAppService.hashUrl("https://example.com");
            String hash2 = WebCollectorAppService.hashUrl("https://example.com");
            assertThat(hash1).isEqualTo(hash2);
            assertThat(hash1).hasSize(64); // SHA-256 hex length
        }

        @Test
        @DisplayName("hashUrl - normalizes case and trailing slashes")
        void hashUrl_normalizes() {
            String hash1 = WebCollectorAppService.hashUrl("https://Example.COM/path/");
            String hash2 = WebCollectorAppService.hashUrl("https://example.com/path");
            assertThat(hash1).isEqualTo(hash2);
        }

        @Test
        @DisplayName("hashUrl - strips UTM parameters")
        void hashUrl_stripsUtm() {
            String hash1 = WebCollectorAppService.hashUrl("https://example.com?utm_source=twitter&id=1");
            String hash2 = WebCollectorAppService.hashUrl("https://example.com?id=1");
            assertThat(hash1).isEqualTo(hash2);
        }

        @Test
        @DisplayName("hashUrl - null input returns hash of empty string")
        void hashUrl_nullInput() {
            String hash = WebCollectorAppService.hashUrl(null);
            assertThat(hash).isNotNull();
            assertThat(hash).hasSize(64);
        }

        @Test
        @DisplayName("hashContent - produces SHA-256 hash")
        void hashContent_producesHash() {
            String hash = WebCollectorAppService.hashContent("test content");
            assertThat(hash).isNotNull();
            assertThat(hash).hasSize(64);
        }

        @Test
        @DisplayName("sha256 - empty string produces valid hash")
        void sha256_emptyString() {
            String hash = WebCollectorAppService.sha256("");
            assertThat(hash).hasSize(64);
        }

        @Test
        @DisplayName("isCrawlerAvailable - delegates to crawlerTaskClient")
        void isCrawlerAvailable_delegates() {
            when(crawlerTaskClient.healthCheck()).thenReturn(true);
            assertThat(service.isCrawlerAvailable()).isTrue();

            when(crawlerTaskClient.healthCheck()).thenReturn(false);
            assertThat(service.isCrawlerAvailable()).isFalse();
        }
    }
}
