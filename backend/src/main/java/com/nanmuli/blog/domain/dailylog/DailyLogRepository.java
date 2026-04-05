package com.nanmuli.blog.domain.dailylog;

import com.baomidou.mybatisplus.core.metadata.IPage;

import java.time.LocalDate;
import java.util.Optional;

public interface DailyLogRepository {
    DailyLog save(DailyLog dailyLog);

    Optional<DailyLog> findById(Long id);

    Optional<DailyLog> findByLogDate(LocalDate logDate);

    IPage<DailyLog> findPage(IPage<DailyLog> page);

    /**
     * 查询公开的日志列表（仅isPublic=true）
     */
    IPage<DailyLog> findPublicPage(IPage<DailyLog> page);

    /**
     * 根据ID查询公开的日志
     */
    Optional<DailyLog> findPublicById(Long id);

    Long count();

    void deleteById(Long id);
}
