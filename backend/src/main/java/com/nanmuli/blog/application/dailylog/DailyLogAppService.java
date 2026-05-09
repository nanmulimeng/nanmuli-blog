package com.nanmuli.blog.application.dailylog;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.nanmuli.blog.application.dailylog.command.CreateDailyLogCommand;
import com.nanmuli.blog.application.dailylog.dto.DailyLogDTO;
import com.nanmuli.blog.application.category.dto.CategoryDTO;
import com.nanmuli.blog.domain.category.Category;
import com.nanmuli.blog.domain.category.CategoryRepository;
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
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class DailyLogAppService {

    private final DailyLogRepository dailyLogRepository;
    private final CategoryRepository categoryRepository;
    private final MarkdownUtil markdownUtil;

    @Transactional
    public Long create(CreateDailyLogCommand command) {
        DailyLog dailyLog = new DailyLog();
        BeanUtils.copyProperties(command, dailyLog);

        // 默认为私有日志
        if (dailyLog.getIsPublic() == null) {
            dailyLog.setIsPublic(false);
        }

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
        List<DailyLogDTO> records = batchConvertToDTO(result.getRecords());
        return new PageResult<>(result.getTotal(), result.getCurrent(), result.getSize(), records);
    }

    @Transactional(readOnly = true)
    public PageResult<DailyLogDTO> listPublicPage(int current, int size) {
        IPage<DailyLog> page = new Page<>(current, size);
        IPage<DailyLog> result = dailyLogRepository.findPublicPage(page);
        List<DailyLogDTO> records = batchConvertToDTO(result.getRecords());
        return new PageResult<>(result.getTotal(), result.getCurrent(), result.getSize(), records);
    }

    @Transactional(readOnly = true)
    public DailyLogDTO getPublicById(Long id) {
        DailyLog dailyLog = dailyLogRepository.findPublicById(id)
                .orElseThrow(() -> new BusinessException("日志不存在或未公开"));
        return toDTO(dailyLog);
    }

    @Transactional
    public void delete(Long id) {
        dailyLogRepository.deleteById(id);
    }

    /**
     * 批量转换日志列表为DTO，使用批量查询避免N+1问题
     */
    private List<DailyLogDTO> batchConvertToDTO(List<DailyLog> dailyLogs) {
        if (dailyLogs.isEmpty()) {
            return List.of();
        }

        // 1. 收集所有分类ID
        Set<Long> categoryIds = dailyLogs.stream()
                .map(DailyLog::getCategoryId)
                .filter(Objects::nonNull)
                .collect(Collectors.toSet());

        // 2. 批量查询所有分类
        Map<Long, Category> categoryMap = categoryIds.isEmpty()
                ? Map.of()
                : categoryRepository.findAllById(categoryIds)
                        .stream().collect(Collectors.toMap(Category::getId, c -> c));

        // 3. 内存组装DTO
        return dailyLogs.stream()
                .map(dailyLog -> toDTO(dailyLog, categoryMap))
                .toList();
    }

    private DailyLogDTO toDTO(DailyLog dailyLog) {
        return toDTO(dailyLog, Map.of());
    }

    private DailyLogDTO toDTO(DailyLog dailyLog, Map<Long, Category> categoryMap) {
        DailyLogDTO dto = new DailyLogDTO();
        BeanUtils.copyProperties(dailyLog, dto);
        dto.setId(dailyLog.getId());
        // 显式映射时间字段（字段名不一致）
        dto.setCreateTime(dailyLog.getCreatedAt());
        dto.setUpdateTime(dailyLog.getUpdatedAt());
        // 设置公开状态
        dto.setIsPublic(dailyLog.isPublic());
        // 填充分类信息（优先从批量查询的Map中获取，回退到单独查询）
        if (dailyLog.getCategoryId() != null) {
            Category category = categoryMap.get(dailyLog.getCategoryId());
            if (category == null && categoryMap.isEmpty()) {
                category = categoryRepository.findById(dailyLog.getCategoryId()).orElse(null);
            }
            if (category != null) {
                dto.setCategory(toCategoryDTO(category));
            }
        }
        return dto;
    }

    private CategoryDTO toCategoryDTO(Category category) {
        CategoryDTO dto = new CategoryDTO();
        BeanUtils.copyProperties(category, dto);
        dto.setId(category.getId());
        dto.setCreateTime(category.getCreatedAt());
        dto.setUpdateTime(category.getUpdatedAt());
        return dto;
    }

    public Long count() {
        return dailyLogRepository.count();
    }
}
