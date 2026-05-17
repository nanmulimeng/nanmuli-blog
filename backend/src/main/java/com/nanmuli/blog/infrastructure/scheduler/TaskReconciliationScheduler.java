package com.nanmuli.blog.infrastructure.scheduler;

import com.nanmuli.blog.application.webcollector.WebCollectorAppService;
import com.nanmuli.blog.domain.webcollector.WebCollectTask;
import com.nanmuli.blog.domain.webcollector.WebCollectTaskRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.autoconfigure.condition.ConditionalOnExpression;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.time.LocalDateTime;
import java.util.List;

/**
 * 定时对账调度器：检测并修复 Java/Python 间任务状态不一致。
 *
 * <p>当 Python 回调因网络故障等原因失败时，MySQL 中的任务可能长期停留在
 * PENDING/CRAWLING/PROCESSING 状态。此调度器定期扫描超过 30 分钟仍非终态的任务，
 * 主动从 Python 同步最新状态。</p>
 */
@Slf4j
@Component
@RequiredArgsConstructor
@ConditionalOnExpression("!'${crawler.service.base-url:}'.isEmpty()")
public class TaskReconciliationScheduler {

    private static final List<Integer> NON_TERMINAL_STATUSES = List.of(0, 1, 2);
    private static final int STALE_THRESHOLD_MINUTES = 30;

    private final WebCollectTaskRepository taskRepository;
    private final WebCollectorAppService appService;

    @Scheduled(fixedDelayString = "${crawler.reconciliation.interval-ms:600000}")
    public void reconcileStaleTasks() {
        LocalDateTime threshold = LocalDateTime.now().minusMinutes(STALE_THRESHOLD_MINUTES);
        List<WebCollectTask> staleTasks = taskRepository.findStaleNonTerminal(NON_TERMINAL_STATUSES, threshold);

        if (staleTasks.isEmpty()) {
            return;
        }

        log.info("[Reconciliation] Found {} stale tasks to reconcile", staleTasks.size());

        int synced = 0;
        int failed = 0;
        for (WebCollectTask task : staleTasks) {
            try {
                appService.syncFromPythonSilent(task);
                synced++;
            } catch (Exception e) {
                failed++;
                log.warn("[Reconciliation] Failed to sync task {}: {}", task.getId(), e.getMessage());
            }
        }

        log.info("[Reconciliation] Done: synced={}, failed={}", synced, failed);
    }
}
