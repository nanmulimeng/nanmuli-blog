package com.nanmuli.blog.infrastructure.persistence.dailylog;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.nanmuli.blog.domain.dailylog.DailyLog;
import com.nanmuli.blog.domain.dailylog.DailyLogRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Repository;

import java.time.LocalDate;
import java.util.Optional;

@Repository
@RequiredArgsConstructor
public class DailyLogRepositoryImpl implements DailyLogRepository {

    private final DailyLogMapper dailyLogMapper;

    @Override
    public DailyLog save(DailyLog dailyLog) {
        if (dailyLog.isNew()) {
            dailyLogMapper.insert(dailyLog);
        } else {
            dailyLogMapper.updateById(dailyLog);
        }
        return dailyLog;
    }

    @Override
    public Optional<DailyLog> findById(Long id) {
        return Optional.ofNullable(dailyLogMapper.selectById(id));
    }

    @Override
    public Optional<DailyLog> findByLogDate(LocalDate logDate) {
        LambdaQueryWrapper<DailyLog> wrapper = Wrappers.lambdaQuery();
        wrapper.eq(DailyLog::getLogDate, logDate);
        return Optional.ofNullable(dailyLogMapper.selectOne(wrapper));
    }

    @Override
    public IPage<DailyLog> findPage(IPage<DailyLog> page) {
        LambdaQueryWrapper<DailyLog> wrapper = Wrappers.lambdaQuery();
        wrapper.orderByDesc(DailyLog::getLogDate);
        return dailyLogMapper.selectPage(page, wrapper);
    }

    @Override
    public void deleteById(Long id) {
        dailyLogMapper.deleteById(id);
    }
}
