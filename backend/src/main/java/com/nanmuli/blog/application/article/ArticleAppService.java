package com.nanmuli.blog.application.article;

import cn.dev33.satoken.stp.StpUtil;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.nanmuli.blog.application.article.command.CreateArticleCommand;
import com.nanmuli.blog.application.article.command.UpdateArticleCommand;
import com.nanmuli.blog.application.article.dto.ArticleArchiveDTO;
import com.nanmuli.blog.application.article.dto.ArticleDTO;
import com.nanmuli.blog.application.article.query.ArticlePageQuery;
import com.nanmuli.blog.application.category.dto.CategoryDTO;
import com.nanmuli.blog.domain.article.Article;
import com.nanmuli.blog.domain.article.ArticleId;
import com.nanmuli.blog.domain.article.ArticleRepository;
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
import org.springframework.cache.annotation.CacheConfig;
import org.springframework.cache.annotation.CacheEvict;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@Slf4j
@Service
@RequiredArgsConstructor
@CacheConfig(cacheNames = "article")
public class ArticleAppService {

    private final ArticleRepository articleRepository;
    private final CategoryRepository categoryRepository;
    private final ApplicationEventPublisher eventPublisher;
    private final MarkdownUtil markdownUtil;

    @Transactional
    @CacheEvict(cacheNames = "article:list", allEntries = true)
    public Long create(CreateArticleCommand command) {
        // 验证分类是否为叶子节点
        validateLeafCategory(command.getCategoryId());

        Article article = new Article();
        BeanUtils.copyProperties(command, article);
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

        articleRepository.save(article);

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
    @CacheEvict(allEntries = true)
    public void update(UpdateArticleCommand command) {
        // 验证分类是否为叶子节点
        validateLeafCategory(command.getCategoryId());

        Article article = articleRepository.findById(new ArticleId(command.getArticleId()))
                .orElseThrow(() -> new BusinessException("文章不存在"));

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

        articleRepository.save(article);
    }

    @Transactional(readOnly = true)
    @Cacheable(key = "#slug")
    public ArticleDTO getBySlug(String slug) {
        Article article = articleRepository.findBySlug(slug)
                .orElseThrow(() -> new BusinessException("文章不存在"));
        return toDTO(article);
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
        IPage<Article> result = articleRepository.findAllPage(page);
        List<ArticleDTO> records = result.getRecords().stream().map(this::toDTO).toList();
        return new PageResult<>(result.getTotal(), result.getCurrent(), result.getSize(), records);
    }

    @Transactional(readOnly = true)
    @Cacheable(cacheNames = "article:list", key = "#query.current + '-' + #query.size")
    public PageResult<ArticleDTO> listPublished(ArticlePageQuery query) {
        IPage<Article> page = new Page<>(query.getCurrent(), query.getSize());
        IPage<Article> result;

        // 根据查询条件选择不同的查询方法
        if (query.getCategoryId() != null) {
            result = articleRepository.findByCategoryId(query.getCategoryId(), page);
        } else {
            result = articleRepository.findPublishedPage(page, query.getSort());
        }

        List<ArticleDTO> records = result.getRecords().stream().map(this::toDTO).toList();
        return new PageResult<>(result.getTotal(), result.getCurrent(), result.getSize(), records);
    }

    @Transactional(readOnly = true)
    @Cacheable(cacheNames = "article", key = "'top-' + #limit")
    public List<ArticleDTO> listTop(int limit) {
        return articleRepository.findTopArticles(limit).stream().map(this::toDTO).toList();
    }

    @Transactional
    @CacheEvict(allEntries = true)
    public void delete(Long id) {
        articleRepository.deleteById(new ArticleId(id));
    }

    @Async
    @Transactional
    public void incrementViewCount(String slug) {
        articleRepository.findBySlug(slug).ifPresent(article -> {
            articleRepository.increaseViewCount(new ArticleId(article.getId()));
        });
    }

    @Transactional(readOnly = true)
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

    private ArticleDTO toDTO(Article article) {
        ArticleDTO dto = new ArticleDTO();
        BeanUtils.copyProperties(article, dto);
        dto.setId(article.getId());
        // 显式映射时间字段（字段名不一致）
        dto.setCreateTime(article.getCreatedAt());
        dto.setUpdateTime(article.getUpdatedAt());

        // 填充分类信息和分类路径
        if (article.getCategoryId() != null) {
            Category category = categoryRepository.findById(article.getCategoryId()).orElse(null);
            if (category != null) {
                dto.setCategory(toCategoryDTO(category));

                // 构建分类层级路径
                dto.setCategoryPath(buildCategoryPath(category));

                // 设置标签为分类名称（用于SEO关键词）
                dto.setTags(Collections.singletonList(category.getName()));
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
        dto.setId(category.getId());
        dto.setCreateTime(category.getCreatedAt());
        dto.setUpdateTime(category.getUpdatedAt());
        return dto;
    }

    /**
     * 构建分类层级路径（从根到当前分类）
     */
    private List<CategoryDTO> buildCategoryPath(Category category) {
        List<CategoryDTO> path = new ArrayList<>();

        // 添加当前分类
        path.add(toCategoryDTO(category));

        // 递归添加上级分类
        Long parentId = category.getParentId();
        while (parentId != null) {
            Category parent = categoryRepository.findById(parentId).orElse(null);
            if (parent == null) {
                break;
            }
            path.add(0, toCategoryDTO(parent));  // 插入到开头
            parentId = parent.getParentId();
        }

        return path;
    }
}
