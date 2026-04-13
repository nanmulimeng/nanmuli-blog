package com.nanmuli.blog.infrastructure.config.ai;

import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.annotation.AsyncConfigurer;
import org.springframework.scheduling.annotation.EnableAsync;
import org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor;

import java.util.concurrent.Executor;
import java.util.concurrent.ThreadPoolExecutor;

/**
 * 异步任务配置
 * 从 application.yml 读取线程池参数，支持 dev/prod 差异化配置
 */
@Slf4j
@Configuration
@EnableAsync
public class AsyncConfig implements AsyncConfigurer {

    @Value("${async.executor.ai.core-pool-size:2}")
    private int aiCorePoolSize;
    @Value("${async.executor.ai.max-pool-size:5}")
    private int aiMaxPoolSize;
    @Value("${async.executor.ai.queue-capacity:50}")
    private int aiQueueCapacity;

    @Value("${async.executor.task.core-pool-size:3}")
    private int taskCorePoolSize;
    @Value("${async.executor.task.max-pool-size:8}")
    private int taskMaxPoolSize;
    @Value("${async.executor.task.queue-capacity:100}")
    private int taskQueueCapacity;

    @Value("${async.executor.crawler.core-pool-size:1}")
    private int crawlerCorePoolSize;
    @Value("${async.executor.crawler.max-pool-size:2}")
    private int crawlerMaxPoolSize;
    @Value("${async.executor.crawler.queue-capacity:20}")
    private int crawlerQueueCapacity;
    @Value("${async.executor.crawler.thread-name-prefix:crawler-}")
    private String crawlerThreadPrefix;

    @Bean(name = "aiTaskExecutor")
    public Executor aiTaskExecutor() {
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        executor.setCorePoolSize(aiCorePoolSize);
        executor.setMaxPoolSize(aiMaxPoolSize);
        executor.setQueueCapacity(aiQueueCapacity);
        executor.setThreadNamePrefix("ai-task-");
        executor.setRejectedExecutionHandler(new ThreadPoolExecutor.CallerRunsPolicy());
        executor.setWaitForTasksToCompleteOnShutdown(true);
        executor.setAwaitTerminationSeconds(60);
        executor.initialize();
        log.info("AI任务执行器初始化完成: core={}, max={}, queue={}", aiCorePoolSize, aiMaxPoolSize, aiQueueCapacity);
        return executor;
    }

    @Bean(name = "taskExecutor")
    public Executor taskExecutor() {
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        executor.setCorePoolSize(taskCorePoolSize);
        executor.setMaxPoolSize(taskMaxPoolSize);
        executor.setQueueCapacity(taskQueueCapacity);
        executor.setThreadNamePrefix("async-task-");
        executor.setRejectedExecutionHandler(new ThreadPoolExecutor.CallerRunsPolicy());
        executor.initialize();
        log.info("通用任务执行器初始化完成: core={}, max={}, queue={}", taskCorePoolSize, taskMaxPoolSize, taskQueueCapacity);
        return executor;
    }

    @Bean(name = "crawlerTaskExecutor")
    public Executor crawlerTaskExecutor() {
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        executor.setCorePoolSize(crawlerCorePoolSize);
        executor.setMaxPoolSize(crawlerMaxPoolSize);
        executor.setQueueCapacity(crawlerQueueCapacity);
        executor.setThreadNamePrefix(crawlerThreadPrefix);
        executor.setRejectedExecutionHandler(new ThreadPoolExecutor.CallerRunsPolicy());
        executor.setWaitForTasksToCompleteOnShutdown(true);
        executor.setAwaitTerminationSeconds(120);
        executor.initialize();
        log.info("爬虫任务执行器初始化完成: core={}, max={}, queue={}", crawlerCorePoolSize, crawlerMaxPoolSize, crawlerQueueCapacity);
        return executor;
    }

    @Override
    public Executor getAsyncExecutor() {
        return taskExecutor();
    }
}
