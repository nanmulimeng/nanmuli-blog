package com.nanmuli.blog.domain.webcollector;

import com.baomidou.mybatisplus.core.metadata.IPage;

import java.util.List;
import java.util.Optional;

/**
 * 爬取页面仓储接口
 */
public interface WebCollectPageRepository {

    WebCollectPage save(WebCollectPage page);

    Optional<WebCollectPage> findById(Long id);

    List<WebCollectPage> findByTaskId(Long taskId);

    List<WebCollectPage> findByTaskIdOrderBySortOrder(Long taskId);

    IPage<WebCollectPage> findPageByTaskId(IPage<WebCollectPage> page, Long taskId);

    Optional<WebCollectPage> findByUrlHash(String urlHash);

    boolean existsByUrlHash(String urlHash);

    long countByTaskId(Long taskId);

    long countByTaskIdAndCrawlStatus(Long taskId, Integer crawlStatus);

    void deleteByTaskId(Long taskId);

    void deleteById(Long id);
}
