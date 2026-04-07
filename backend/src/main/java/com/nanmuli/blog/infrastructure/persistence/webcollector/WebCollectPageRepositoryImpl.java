package com.nanmuli.blog.infrastructure.persistence.webcollector;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.nanmuli.blog.domain.webcollector.WebCollectPage;
import com.nanmuli.blog.domain.webcollector.WebCollectPageRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

/**
 * 爬取页面仓储实现
 */
@Repository
@RequiredArgsConstructor
public class WebCollectPageRepositoryImpl implements WebCollectPageRepository {

    private final WebCollectPageMapper pageMapper;

    @Override
    public WebCollectPage save(WebCollectPage page) {
        if (page.isNew()) {
            pageMapper.insert(page);
        } else {
            pageMapper.updateById(page);
        }
        return page;
    }

    @Override
    public Optional<WebCollectPage> findById(Long id) {
        return Optional.ofNullable(pageMapper.selectById(id));
    }

    @Override
    public List<WebCollectPage> findByTaskId(Long taskId) {
        return pageMapper.selectByTaskId(taskId);
    }

    @Override
    public List<WebCollectPage> findByTaskIdOrderBySortOrder(Long taskId) {
        return pageMapper.selectByTaskIdOrderBySortOrder(taskId);
    }

    @Override
    public IPage<WebCollectPage> findPageByTaskId(IPage<WebCollectPage> page, Long taskId) {
        return pageMapper.selectPage(page,
            new com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper<WebCollectPage>()
                .eq(WebCollectPage::getTaskId, taskId)
                .orderByAsc(WebCollectPage::getSortOrder));
    }

    @Override
    public Optional<WebCollectPage> findByUrlHash(String urlHash) {
        return Optional.ofNullable(pageMapper.selectByUrlHash(urlHash));
    }

    @Override
    public boolean existsByUrlHash(String urlHash) {
        return pageMapper.countByUrlHash(urlHash) > 0;
    }

    @Override
    public long countByTaskId(Long taskId) {
        return pageMapper.countByTaskId(taskId);
    }

    @Override
    public long countByTaskIdAndCrawlStatus(Long taskId, Integer crawlStatus) {
        return pageMapper.countByTaskIdAndCrawlStatus(taskId, crawlStatus);
    }

    @Override
    public void deleteByTaskId(Long taskId) {
        pageMapper.deleteByTaskId(taskId);
    }

    @Override
    public void deleteById(Long id) {
        pageMapper.deleteById(id);
    }
}
