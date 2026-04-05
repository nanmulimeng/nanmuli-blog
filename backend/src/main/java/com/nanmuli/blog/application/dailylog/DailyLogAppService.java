package com.nanmuli.blog.application.dailylog;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.nanmuli.blog.application.dailylog.command.CreateDailyLogCommand;
import com.nanmuli.blog.application.dailylog.dto.DailyLogDTO;
import com.nanmuli.blog.domain.dailylog.DailyLog;
import com.nanmuli.blog.domain.dailylog.DailyLogRepository;
import com.nanmuli.blog.shared.exception.BusinessException;
import com.nanmuli.blog.shared.result.PageResult;
import com.nanmuli.blog.shared.util.MarkdownUtil;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.BeanUtils;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
@RequiredArgsConstructor
public class DailyLogAppService {

    private final DailyLogRepository dailyLogRepository;
    private final MarkdownUtil markdownUtil;

    @Transactional
    public Long create(CreateDailyLogCommand command) {
        DailyLog dailyLog = new DailyLog();
        BeanUtils.copyProperties(command, dailyLog);
        dailyLog.setTags(parseListToString(command.getTags()));

        // 生成HTML内容和字数统计
        dailyLog.setContentHtml(markdownUtil.toHtml(command.getContent()));
        dailyLog.setWordCount(markdownUtil.extractText(command.getContent()).length());

        dailyLogRepository.save(dailyLog);
        return dailyLog.getId();
    }

    @Transactional
    public void update(Long id, CreateDailyLogCommand command) {
        DailyLog dailyLog = dailyLogRepository.findById(id)
                .orElseThrow(() -> new BusinessException("日志不存在"));
        BeanUtils.copyProperties(command, dailyLog);
        dailyLog.setTags(parseListToString(command.getTags()));
        dailyLog.setId(id);

        // 重新生成HTML内容和字数统计
        dailyLog.setContentHtml(markdownUtil.toHtml(command.getContent()));
        dailyLog.setWordCount(markdownUtil.extractText(command.getContent()).length());

        dailyLogRepository.save(dailyLog);
    }

    @Transactional(readOnly = true)
    public DailyLogDTO getById(Long id) {
        DailyLog dailyLog = dailyLogRepository.findById(id)
                .orElseThrow(() -> new BusinessException("日志不存在"));
        return toDTO(dailyLog);
    }

    @Transactional(readOnly = true)
    public PageResult<DailyLogDTO> listPage(int current, int size) {
        IPage<DailyLog> page = new Page<>(current, size);
        IPage<DailyLog> result = dailyLogRepository.findPage(page);
        List<DailyLogDTO> records = result.getRecords().stream().map(this::toDTO).toList();
        return new PageResult<>(result.getTotal(), result.getCurrent(), result.getSize(), records);
    }

    @Transactional
    public void delete(Long id) {
        dailyLogRepository.deleteById(id);
    }

    private DailyLogDTO toDTO(DailyLog dailyLog) {
        DailyLogDTO dto = new DailyLogDTO();
        BeanUtils.copyProperties(dailyLog, dto);
        dto.setId(dailyLog.getId());
        // 显式映射时间字段（字段名不一致）
        dto.setCreateTime(dailyLog.getCreatedAt());
        dto.setUpdateTime(dailyLog.getUpdatedAt());
        // 将逗号分隔的字符串转换为列表
        dto.setTags(parseStringToList(dailyLog.getTags()));
        return dto;
    }

    /**
     * 将逗号分隔的字符串转换为列表
     */
    private List<String> parseStringToList(String str) {
        if (str == null || str.isEmpty()) {
            return java.util.Collections.emptyList();
        }
        return java.util.Arrays.asList(str.split(","));
    }

    /**
     * 将列表转换为逗号分隔的字符串
     */
    private String parseListToString(List<String> list) {
        if (list == null || list.isEmpty()) {
            return "";
        }
        return String.join(",", list);
    }
}
