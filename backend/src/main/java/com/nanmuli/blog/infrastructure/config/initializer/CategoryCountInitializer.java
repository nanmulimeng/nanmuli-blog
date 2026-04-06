package com.nanmuli.blog.infrastructure.config.initializer;

import com.nanmuli.blog.application.category.CategoryAppService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;

/**
 * 应用启动时初始化分类文章数
 * 确保数据库中的文章计数与实际一致
 */
@Slf4j
@Component
@RequiredArgsConstructor
@Order(100)
public class CategoryCountInitializer implements ApplicationRunner {

    private final CategoryAppService categoryAppService;

    @Override
    public void run(ApplicationArguments args) {
        log.info("开始刷新分类文章数...");
        try {
            categoryAppService.refreshAllCategoryArticleCounts();
            log.info("分类文章数刷新完成");
        } catch (Exception e) {
            log.error("刷新分类文章数失败", e);
        }
    }
}
