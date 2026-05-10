package com.nanmuli.blog.application.article;

import cn.dev33.satoken.stp.StpUtil;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.nanmuli.blog.application.article.command.CreateArticleCommand;
import com.nanmuli.blog.application.article.command.UpdateArticleCommand;
import com.nanmuli.blog.application.article.dto.ArticleArchiveDTO;
import com.nanmuli.blog.application.article.dto.ArticleDTO;
import com.nanmuli.blog.application.article.dto.ArticleStatsDTO;
import com.nanmuli.blog.application.article.query.ArticlePageQuery;
import com.nanmuli.blog.application.category.dto.CategoryDTO;
import com.nanmuli.blog.domain.article.Article;
import com.nanmuli.blog.domain.article.ArticleId;
import com.nanmuli.blog.domain.article.ArticleRepository;
import com.nanmuli.blog.domain.article.ArticleViewRecord;
import com.nanmuli.blog.domain.article.ArticleViewRecordRepository;
import com.nanmuli.blog.domain.article.ArticleVisitLog;
import com.nanmuli.blog.domain.article.ArticleVisitLogRepository;
import com.nanmuli.blog.application.article.command.RecordArticleViewCommand;
import com.nanmuli.blog.domain.article.event.ArticleCreatedEvent;
import com.nanmuli.blog.domain.article.event.ArticlePublishedEvent;
import com.nanmuli.blog.domain.category.Category;
import com.nanmuli.blog.domain.category.CategoryRepository;
import com.nanmuli.blog.shared.exception.BusinessException;
import com.nanmuli.blog.shared.result.PageResult;
import com.nanmuli.blog.shared.util.MarkdownUtil;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.BeanUtils;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.dao.OptimisticLockingFailureException;
import org.springframework.util.StringUtils;
import org.springframework.cache.annotation.CacheConfig;
import org.springframework.web.util.HtmlUtils;
import org.springframework.cache.annotation.CacheEvict;
import org.springframework.cache.annotation.Caching;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.stream.Collectors;

@Slf4j
@Service
@RequiredArgsConstructor
@CacheConfig(cacheNames = "article")
@Transactional(readOnly = true)
public class ArticleAppService {

    private final ArticleRepository articleRepository;
    private final ArticleViewRecordRepository articleViewRecordRepository;
    private final ArticleVisitLogRepository articleVisitLogRepository;
    private final CategoryRepository categoryRepository;
    private final ApplicationEventPublisher eventPublisher;
    private final MarkdownUtil markdownUtil;

    @Transactional
    @Caching(evict = {
        @CacheEvict(cacheNames = "article", allEntries = true),
        @CacheEvict(cacheNames = "article:list", allEntries = true),
        @CacheEvict(cacheNames = "article:top", allEntries = true),
        @CacheEvict(cacheNames = "article:archive", allEntries = true),
        @CacheEvict(cacheNames = "category", allEntries = true)
    })
    public Long create(CreateArticleCommand command) {
        // 验证分类是否为叶子节点
        validateLeafCategory(command.getCategoryId());

        Article article = new Article();
        BeanUtils.copyProperties(command, article);

        // 使用UUID作为slug，一次性保存，避免INSERT后再UPDATE的双重操作
        article.setSlug(java.util.UUID.randomUUID().toString().replace("-", "").substring(0, 16));
        article.calculateWordCount();

        // 设置当前登录用户
        try {
            Long userId = StpUtil.getLoginIdAsLong();
            article.setUserId(userId);
        } catch (Exception e) {
            log.warn("无法获取当前登录用户，使用默认用户ID=1");
            article.setUserId(1L); // 默认管理员ID
        }

        // 生成HTML内容
        article.setContentHtml(markdownUtil.toHtml(command.getContent()));

        // 如果没有提供摘要，自动生成
        if (article.getSummary() == null || article.getSummary().isEmpty()) {
            article.setSummary(markdownUtil.generateSummary(command.getContent(), 200));
        }

        // 根据状态设置发布信息
        if (command.getStatus() != null && command.getStatus() == 1) {
            article.publish();
        } else if (command.getStatus() != null && command.getStatus() == 2) {
            article.draft();
        } else {
            article.publish(); // 默认发布
        }

        // TODO: 数据库层应添加 slug 唯一索引（如 ALTER TABLE article ADD UNIQUE INDEX uk_slug (slug)）
        // UUID slug 碰撞概率极低，但仍需防御性处理
        try {
            articleRepository.save(article);
        } catch (DuplicateKeyException e) {
            log.warn("slug冲突，重新生成: articleId={}", article.getId());
            article.setSlug(java.util.UUID.randomUUID().toString().replace("-", "").substring(0, 16));
            articleRepository.save(article);
        }

        // 更新分类文章数
        if (article.getCategoryId() != null) {
            refreshCategoryArticleCount(article.getCategoryId());
        }

        // 发布文章创建事件
        eventPublisher.publishEvent(new ArticleCreatedEvent(article.getId(), article.getTitle()));

        // 如果是已发布状态，触发AI生成
        if (article.isPublished()) {
            eventPublisher.publishEvent(new ArticlePublishedEvent(
                    article.getId(),
                    article.getTitle(),
                    article.getSlug(),
                    article.getContent(),
                    article.getCategoryId()
            ));
        }

        return article.getId();
    }

    @Transactional
    @Caching(evict = {
        @CacheEvict(cacheNames = "article", allEntries = true),
        @CacheEvict(cacheNames = "article:list", allEntries = true),
        @CacheEvict(cacheNames = "article:top", allEntries = true),
        @CacheEvict(cacheNames = "article:archive", allEntries = true),
        @CacheEvict(cacheNames = "article:stats", key = "#command.articleId"),
        @CacheEvict(cacheNames = "category", allEntries = true)
    })
    public void update(UpdateArticleCommand command) {
        // 验证分类是否为叶子节点
        validateLeafCategory(command.getCategoryId());

        Article article = articleRepository.findById(new ArticleId(command.getArticleId()))
                .orElseThrow(() -> new BusinessException("文章不存在"));

        // 添加归属校验
        Long currentUserId = StpUtil.getLoginIdAsLong();
        if (!currentUserId.equals(article.getUserId())) {
            throw new BusinessException("无权修改他人文章");
        }

        // 保存原有分类ID，用于后续更新文章数
        Long oldCategoryId = article.getCategoryId();

        // 保存原有状态
        boolean wasPublished = article.isPublished();

        BeanUtils.copyProperties(command, article);
        article.calculateWordCount();

        // 重新生成HTML内容
        article.setContentHtml(markdownUtil.toHtml(command.getContent()));

        // 如果没有提供摘要，自动生成
        if (article.getSummary() == null || article.getSummary().isEmpty()) {
            article.setSummary(markdownUtil.generateSummary(command.getContent(), 200));
        }

        // 根据状态字段更新文章状态
        if (command.getStatus() != null) {
            if (command.getStatus() == 1) {
                // 如果之前不是已发布状态，现在改为发布，设置发布时间
                if (!wasPublished) {
                    article.setPublishTime(java.time.LocalDateTime.now());
                }
                article.setStatus(1);
            } else if (command.getStatus() == 2) {
                article.setStatus(2);
            }
        }

        try {
            articleRepository.save(article);
        } catch (OptimisticLockingFailureException e) {
            throw new BusinessException("文章已被他人修改，请刷新后重试");
        }

        // 更新分类文章数（新旧分类都更新）
        Long newCategoryId = article.getCategoryId();
        if (!java.util.Objects.equals(oldCategoryId, newCategoryId)) {
            if (oldCategoryId != null) {
                refreshCategoryArticleCount(oldCategoryId);
            }
            if (newCategoryId != null) {
                refreshCategoryArticleCount(newCategoryId);
            }
        }
    }

    @Transactional(readOnly = true)
    @Cacheable(key = "#slug", unless = "#result == null")
    public ArticleDTO getBySlug(String slug) {
        return articleRepository.findBySlug(slug)
                .map(this::toDTO)
                .orElse(null);
    }

    @Transactional(readOnly = true)
    public ArticleDTO getById(Long id) {
        Article article = articleRepository.findById(new ArticleId(id))
                .orElseThrow(() -> new BusinessException("文章不存在"));
        return toDTO(article);
    }

    @Transactional(readOnly = true)
    public PageResult<ArticleDTO> listAll(ArticlePageQuery query) {
        IPage<Article> page = new Page<>(query.getCurrent(), query.getSize());
        IPage<Article> result;

        // 优先处理关键词搜索
        if (StringUtils.hasText(query.getKeyword())) {
            // 先查询匹配关键词的分类ID
            List<Long> matchingCategoryIds = findCategoryIdsByKeyword(query.getKeyword());
            result = articleRepository.findAllByKeyword(query.getKeyword(), matchingCategoryIds, page);
        } else {
            result = articleRepository.findAllPage(page);
        }

        // 批量查询分类，避免N+1问题
        List<ArticleDTO> records = batchConvertToDTO(result.getRecords());
        return new PageResult<>(result.getTotal(), result.getCurrent(), result.getSize(), records);
    }

    @Transactional(readOnly = true)
    @Cacheable(cacheNames = "article:list", key = "#query.current + '-' + #query.size + '-' + #query.categoryId + '-' + #query.sort + '-' + #query.keyword")
    public PageResult<ArticleDTO> listPublished(ArticlePageQuery query) {
        IPage<Article> page = new Page<>(query.getCurrent(), query.getSize());
        IPage<Article> result;

        // 优先处理关键词搜索
        if (StringUtils.hasText(query.getKeyword())) {
            // 先查询匹配关键词的分类ID
            List<Long> matchingCategoryIds = findCategoryIdsByKeyword(query.getKeyword());
            result = articleRepository.findPublishedByKeyword(query.getKeyword(), matchingCategoryIds, page, query.getSort());

            // FTS无结果时回退到pg_trgm模糊搜索（支持部分匹配和拼写容错）
            if (result.getTotal() == 0) {
                result = articleRepository.findPublishedByTrigram(query.getKeyword(), matchingCategoryIds, page);
            }
        } else if (query.getCategoryId() != null) {
            // 获取该分类及其所有子分类的ID
            List<Long> categoryIds = getCategoryAndChildrenIds(query.getCategoryId());
            result = articleRepository.findByCategoryIds(categoryIds, page, query.getSort());
        } else {
            result = articleRepository.findPublishedPage(page, query.getSort());
        }

        // 批量查询分类，避免N+1问题
        List<ArticleDTO> records = batchConvertToDTO(result.getRecords());
        return new PageResult<>(result.getTotal(), result.getCurrent(), result.getSize(), records);
    }

    /**
     * 根据关键词查找匹配的分类ID（使用SQL LIKE查询，避免全表加载）
     */
    private List<Long> findCategoryIdsByKeyword(String keyword) {
        return categoryRepository.findIdsByNameLike(keyword);
    }

    @Transactional(readOnly = true)
    @Cacheable(cacheNames = "article", key = "'top-' + #limit")
    public List<ArticleDTO> listTop(int limit) {
        return batchConvertToDTO(articleRepository.findTopArticles(limit));
    }

    @Transactional
    @Caching(evict = {
        @CacheEvict(cacheNames = "article", allEntries = true),
        @CacheEvict(cacheNames = "article:list", allEntries = true),
        @CacheEvict(cacheNames = "article:top", allEntries = true),
        @CacheEvict(cacheNames = "article:archive", allEntries = true),
        @CacheEvict(cacheNames = "article:stats", key = "#id"),
        @CacheEvict(cacheNames = "category", allEntries = true)
    })
    public void delete(Long id) {
        Article article = articleRepository.findById(new ArticleId(id))
                .orElseThrow(() -> new BusinessException("文章不存在或已被删除"));

        // 添加归属校验
        Long currentUserId = StpUtil.getLoginIdAsLong();
        if (!currentUserId.equals(article.getUserId())) {
            throw new BusinessException("无权删除他人文章");
        }

        Long categoryId = article.getCategoryId();

        articleRepository.deleteById(new ArticleId(id));

        // 更新分类文章数
        if (categoryId != null) {
            refreshCategoryArticleCount(categoryId);
        }
    }

    /**
     * 记录文章阅读用户（UV统计）和访问日志（PV统计）
     */
    @Transactional
    public void recordView(RecordArticleViewCommand command, String ipAddress, String userAgent) {
        Long articleId = command.getArticleId();
        String visitorId = command.getVisitorId();

        // 1. 记录访问日志（PV统计 - 每次访问都记录）
        ArticleVisitLog visitLog = new ArticleVisitLog();
        visitLog.setArticleId(articleId);
        visitLog.setVisitorId(visitorId);
        visitLog.setIpAddress(ipAddress);
        visitLog.setUserAgent(userAgent);
        visitLog.setVisitTime(java.time.LocalDateTime.now());
        articleVisitLogRepository.save(visitLog);

        // 2. 更新或创建独立访客记录（UV统计）
        ArticleViewRecord record = articleViewRecordRepository
                .findByArticleIdAndVisitorId(articleId, visitorId)
                .orElse(null);

        if (record == null) {
            // 新访客，创建记录
            record = new ArticleViewRecord();
            record.setArticleId(articleId);
            record.setVisitorId(visitorId);
            record.setIpAddress(ipAddress);
            record.setUserAgent(userAgent);
            record.setFirstViewTime(java.time.LocalDateTime.now());
            record.setLastViewTime(java.time.LocalDateTime.now());
            record.setViewCount(1);
            articleViewRecordRepository.save(record);

            // 同时更新文章表的viewCount字段（保持兼容性）
            articleRepository.increaseViewCount(new ArticleId(articleId));
        } else {
            // 已有记录，更新访问时间和次数
            record.setLastViewTime(java.time.LocalDateTime.now());
            record.setViewCount(record.getViewCount() + 1);
            articleViewRecordRepository.save(record);
        }
    }

    /**
     * 获取文章阅读用户数量（UV）
     */
    @Transactional(readOnly = true)
    public Long getArticleViewCount(Long articleId) {
        return articleViewRecordRepository.countUniqueVisitorsByArticleId(articleId);
    }

    /**
     * 获取文章完整访问统计（PV/UV/今日）
     */
    @Transactional(readOnly = true)
    @Cacheable(cacheNames = "article:stats", key = "#articleId")
    public ArticleStatsDTO getArticleStats(Long articleId) {
        Article article = articleRepository.findById(new ArticleId(articleId))
                .orElseThrow(() -> new BusinessException("文章不存在"));

        ArticleStatsDTO stats = new ArticleStatsDTO();
        stats.setArticleId(articleId);
        stats.setSlug(article.getSlug());
        stats.setTitle(article.getTitle());
        stats.setVisitCount(articleVisitLogRepository.countByArticleId(articleId));
        stats.setVisitorCount(articleViewRecordRepository.countUniqueVisitorsByArticleId(articleId));
        stats.setTodayCount(articleVisitLogRepository.countTodayByArticleId(articleId));

        return stats;
    }

    @Transactional(readOnly = true)
    @Cacheable(cacheNames = "article:archive", key = "'all'")
    public List<ArticleArchiveDTO> getArchive() {
        List<java.util.Map<String, Object>> rawData = articleRepository.findArchiveByYearMonth();
        List<ArticleArchiveDTO> result = new ArrayList<>();

        for (java.util.Map<String, Object> row : rawData) {
            ArticleArchiveDTO dto = new ArticleArchiveDTO();
            dto.setYear((String) row.get("year"));
            dto.setMonth((String) row.get("month"));
            dto.setCount(((Number) row.get("count")).longValue());
            result.add(dto);
        }

        return result;
    }

    @Transactional(readOnly = true)
    public Long countPublished() {
        return articleRepository.countPublished();
    }

    /**
     * 获取分类及其所有子分类的ID列表
     */
    private List<Long> getCategoryAndChildrenIds(Long categoryId) {
        List<Long> result = new ArrayList<>();
        result.add(categoryId);

        // 递归获取所有子分类
        addChildrenIds(categoryId, result);

        return result;
    }

    /**
     * 递归添加子分类ID
     */
    private void addChildrenIds(Long parentId, List<Long> result) {
        List<Category> children = categoryRepository.findByParentId(parentId);
        for (Category child : children) {
            result.add(child.getId());
            addChildrenIds(child.getId(), result);
        }
    }

    /**
     * 验证分类是否为叶子节点（只有叶子分类才能关联文章）
     */
    private void validateLeafCategory(Long categoryId) {
        if (categoryId == null) {
            return;
        }
        Category category = categoryRepository.findById(categoryId)
                .orElseThrow(() -> new BusinessException("分类不存在"));
        if (!category.isLeaf()) {
            throw new BusinessException("只能选择叶子分类关联文章");
        }
    }

    /**
     * 刷新指定分类的文章数量
     * 原 CategoryAppService.refreshArticleCount() 的内联实现，避免 AppService 跨调用耦合
     */
    private void refreshCategoryArticleCount(Long categoryId) {
        if (categoryId == null) {
            return;
        }
        Category category = categoryRepository.findById(categoryId).orElse(null);
        if (category == null) {
            return;
        }
        Long count = articleRepository.countByCategoryId(categoryId);
        category.setArticleCount(count.intValue());
        categoryRepository.save(category);
    }

    /**
     * 批量转换文章列表为DTO，使用批量查询避免N+1问题
     */
    private List<ArticleDTO> batchConvertToDTO(List<Article> articles) {
        if (articles.isEmpty()) {
            return List.of();
        }

        // 1. 收集所有分类ID
        Set<Long> categoryIds = articles.stream()
                .map(Article::getCategoryId)
                .filter(Objects::nonNull)
                .collect(Collectors.toSet());

        // 2. 批量查询所有分类
        Map<Long, Category> categoryMap = categoryRepository.findAllById(categoryIds)
                .stream().collect(Collectors.toMap(Category::getId, c -> c));

        // 3. 收集所有父分类ID
        Set<Long> parentIds = categoryMap.values().stream()
                .map(Category::getParentId)
                .filter(Objects::nonNull)
                .collect(Collectors.toSet());

        // 4. 批量查询所有父分类
        Map<Long, Category> parentMap = categoryRepository.findAllById(parentIds)
                .stream().collect(Collectors.toMap(Category::getId, c -> c));

        // 5. 批量查询 UV 统计（避免 N+1）
        Set<Long> articleIds = articles.stream().map(Article::getId).collect(Collectors.toSet());
        Map<Long, Long> visitorCountMap = articleViewRecordRepository.countUniqueVisitorsByArticleIds(articleIds);

        // 6. 批量查询 PV 统计（避免 N+1）
        Map<Long, Long> visitCountMap = articleVisitLogRepository.countByArticleIds(articleIds);

        // 7. 内存组装DTO
        return articles.stream()
                .map(article -> toDTO(article, categoryMap, parentMap, visitorCountMap, visitCountMap))
                .toList();
    }

    private ArticleDTO toDTO(Article article) {
        return toDTO(article, Map.of(), Map.of(), Map.of(), Map.of());
    }

    private ArticleDTO toDTO(Article article, Map<Long, Category> categoryMap,
                             Map<Long, Category> parentMap, Map<Long, Long> visitorCountMap,
                             Map<Long, Long> visitCountMap) {
        ArticleDTO dto = new ArticleDTO();
        BeanUtils.copyProperties(article, dto);
        // XSS防护：转义标题中的HTML
        if (article.getTitle() != null) {
            dto.setTitle(HtmlUtils.htmlEscape(article.getTitle()));
        }
        dto.setId(article.getId());
        // 显式映射时间字段（字段名不一致）
        dto.setCreateTime(article.getCreatedAt());
        dto.setUpdateTime(article.getUpdatedAt());

        // UV 统计（访客数）：优先从批量查询 map 中获取，回退到单条查询
        if (!visitorCountMap.isEmpty() && visitorCountMap.containsKey(article.getId())) {
            Long count = visitorCountMap.get(article.getId());
            dto.setVisitorCount(count != null ? count.intValue() : 0);
        } else {
            Long uv = articleViewRecordRepository.countUniqueVisitorsByArticleId(article.getId());
            dto.setVisitorCount(uv != null ? uv.intValue() : 0);
        }

        // PV 统计（访问次数）：优先从批量查询 map 中获取，回退到单条查询
        if (!visitCountMap.isEmpty() && visitCountMap.containsKey(article.getId())) {
            Long count = visitCountMap.get(article.getId());
            dto.setVisitCount(count != null ? count.intValue() : 0);
        } else {
            Long pv = articleVisitLogRepository.countByArticleId(article.getId());
            dto.setVisitCount(pv != null ? pv.intValue() : 0);
        }

        // 填充分类信息和分类路径
        if (article.getCategoryId() != null) {
            Category category = categoryMap.get(article.getCategoryId());
            // 如果Map中没有，回退到单独查询（兼容单条查询场景）
            if (category == null && categoryMap.isEmpty()) {
                category = categoryRepository.findById(article.getCategoryId()).orElse(null);
            }
            if (category != null) {
                dto.setCategory(toCategoryDTO(category));
                // 构建分类层级路径
                dto.setCategoryPath(buildCategoryPath(category, parentMap));
            }
        }

        return dto;
    }

    /**
     * 将 Category 转换为 CategoryDTO
     */
    private CategoryDTO toCategoryDTO(Category category) {
        CategoryDTO dto = new CategoryDTO();
        BeanUtils.copyProperties(category, dto);
        // XSS963262a4Ff1a5bf952067c7b540d79f08fdb884cHTML8f6c4e49
        if (category.getName() != null) {
            dto.setName(HtmlUtils.htmlEscape(category.getName()));
        }
        dto.setId(category.getId());
        dto.setCreateTime(category.getCreatedAt());
        dto.setUpdateTime(category.getUpdatedAt());
        return dto;
    }

    /**
     * 构建分类层级路径（从根到当前分类）- 使用批量查询的Map
     */
    private List<CategoryDTO> buildCategoryPath(Category category, Map<Long, Category> parentMap) {
        List<CategoryDTO> path = new ArrayList<>();

        // 添加当前分类
        path.add(toCategoryDTO(category));

        // 递归添加上级分类（从Map中获取）
        Long parentId = category.getParentId();
        while (parentId != null) {
            Category parent = parentMap.get(parentId);
            if (parent == null) {
                break;
            }
            path.add(0, toCategoryDTO(parent));  // 插入到开头
            parentId = parent.getParentId();
        }

        return path;
    }
}
