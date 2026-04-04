package com.nanmuli.blog.domain.dailylog;

import com.baomidou.mybatisplus.core.metadata.IPage;

import java.time.LocalDate;
import java.util.Optional;

public interface DailyLogRepository {
    DailyLog save(DailyLog dailyLog);

    Optional<DailyLog> findById(Long id);

    Optional<DailyLog> findByLogDate(LocalDate logDate);

    IPage<DailyLog> findPage(IPage<DailyLog> page);

    Long count();

    void deleteById(Long id);
}
