package com.nanmuli.blog.application.webcollector;

import com.nanmuli.blog.application.webcollector.command.CreateSourceCommand;
import com.nanmuli.blog.application.webcollector.command.UpdateSourceCommand;
import com.nanmuli.blog.application.webcollector.dto.SourceDTO;
import com.nanmuli.blog.domain.webcollector.WebCollectSource;
import com.nanmuli.blog.domain.webcollector.WebCollectSourceRepository;
import com.nanmuli.blog.shared.exception.BusinessException;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.BeanUtils;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Slf4j
@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class WebCollectSourceAppService {

    private final WebCollectSourceRepository sourceRepository;

    @Transactional
    public Long create(CreateSourceCommand command, Long userId) {
        if (sourceRepository.existsByNameAndIdNot(command.getName(), null)) {
            throw new BusinessException("订阅源名称已存在: " + command.getName());
        }

        WebCollectSource source = new WebCollectSource();
        BeanUtils.copyProperties(command, source);
        source.setUserId(userId);
        source.setIsActive(true);
        source.setRunCount(0);
        applyDefaults(source);

        sourceRepository.save(source);
        log.info("[Source] Created: id={}, name={}, type={}", source.getId(), source.getName(), source.getType());
        return source.getId();
    }

    @Transactional
    public void update(Long id, UpdateSourceCommand command, Long userId) {
        WebCollectSource source = getSourceOrThrow(id, userId);

        if (sourceRepository.existsByNameAndIdNot(command.getName(), id)) {
            throw new BusinessException("订阅源名称已存在: " + command.getName());
        }

        source.setName(command.getName());
        source.setType(command.getType());
        source.setValue(command.getValue());
        source.setContentCategory(command.getContentCategory());
        source.setCrawlMode(command.getCrawlMode());
        source.setMaxDepth(command.getMaxDepth());
        source.setMaxPages(command.getMaxPages());
        source.setCssSelector(command.getCssSelector());
        source.setAiTemplate(command.getAiTemplate());
        source.setScheduleCron(command.getScheduleCron());
        source.setFreshnessHours(command.getFreshnessHours());
        if (command.getIsActive() != null) {
            source.setIsActive(command.getIsActive());
        }

        sourceRepository.save(source);
        log.info("[Source] Updated: id={}", id);
    }

    public SourceDTO getById(Long id, Long userId) {
        WebCollectSource source = getSourceOrThrow(id, userId);
        return toDTO(source);
    }

    public List<SourceDTO> listByUser(Long userId) {
        return sourceRepository.findByUserId(userId).stream()
                .map(this::toDTO)
                .toList();
    }

    /**
     * 获取所有活跃订阅源（供日报集成使用）
     */
    public List<SourceDTO> listActive() {
        return sourceRepository.findActiveSources().stream()
                .map(this::toDTO)
                .toList();
    }

    @Transactional
    public void delete(Long id, Long userId) {
        WebCollectSource source = getSourceOrThrow(id, userId);
        sourceRepository.deleteById(source.getId());
        log.info("[Source] Deleted: id={}", id);
    }

    @Transactional
    public void toggleActive(Long id, Long userId) {
        WebCollectSource source = getSourceOrThrow(id, userId);
        source.setIsActive(!source.isActive());
        sourceRepository.save(source);
        log.info("[Source] Toggled: id={}, isActive={}", id, source.isActive());
    }

    private WebCollectSource getSourceOrThrow(Long id, Long userId) {
        return sourceRepository.findById(id)
                .filter(s -> s.getUserId().equals(userId))
                .orElseThrow(() -> new BusinessException("订阅源不存在"));
    }

    private void applyDefaults(WebCollectSource source) {
        if (source.getCrawlMode() == null) source.setCrawlMode("single");
        if (source.getMaxDepth() == null) source.setMaxDepth(1);
        if (source.getMaxPages() == null) source.setMaxPages(10);
        if (source.getAiTemplate() == null) source.setAiTemplate("tech_summary");
        if (source.getFreshnessHours() == null) source.setFreshnessHours(24);
    }

    private SourceDTO toDTO(WebCollectSource source) {
        SourceDTO dto = new SourceDTO();
        BeanUtils.copyProperties(source, dto);
        return dto;
    }
}
