package com.nanmuli.blog.application.article;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.nanmuli.blog.application.article.command.CreateArticleCommand;
import com.nanmuli.blog.application.article.command.UpdateArticleCommand;
import com.nanmuli.blog.application.article.dto.ArticleArchiveDTO;
import com.nanmuli.blog.application.article.dto.ArticleDTO;
import com.nanmuli.blog.application.article.query.ArticlePageQuery;
import com.nanmuli.blog.application.category.dto.CategoryDTO;
import com.nanmuli.blog.application.tag.dto.TagDTO;
import com.nanmuli.blog.domain.article.Article;
import com.nanmuli.blog.domain.article.ArticleId;
import com.nanmuli.blog.domain.article.ArticleRepository;
import com.nanmuli.blog.domain.article.ArticleTagRepository;
import com.nanmuli.blog.domain.article.event.ArticleCreatedEvent;
import com.nanmuli.blog.domain.article.event.ArticlePublishedEvent;
import com.nanmuli.blog.domain.category.Category;
import com.nanmuli.blog.domain.category.CategoryRepository;
import com.nanmuli.blog.domain.tag.Tag;
import com.nanmuli.blog.domain.tag.TagRepository;
import com.nanmuli.blog.shared.exception.BusinessException;
import com.nanmuli.blog.shared.result.PageResult;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.BeanUtils;
import org.springframework.cache.annotation.CacheConfig;
import org.springframework.cache.annotation.CacheEvict;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.CollectionUtils;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
@CacheConfig(cacheNames = "article")
public class ArticleAppService {

    private final ArticleRepository articleRepository;
    private final ArticleTagRepository articleTagRepository;
    private final CategoryRepository categoryRepository;
    private final TagRepository tagRepository;
    private final ApplicationEventPublisher eventPublisher;

    @Transactional
    @CacheEvict(cacheNames = "article:list", allEntries = true)
    public Long create(CreateArticleCommand command) {
        Article article = new Article();
        BeanUtils.copyProperties(command, article);
        article.calculateWordCount();
        article.publish();
        articleRepository.save(article);

        // 保存标签关联
        if (!CollectionUtils.isEmpty(command.getTagIds())) {
            articleTagRepository.saveBatch(article.getId(), command.getTagIds());
        }

        // 发布文章创建事件
        eventPublisher.publishEvent(new ArticleCreatedEvent(article.getId(), article.getTitle()));
        // 发布文章发布事件（触发AI生成）
        eventPublisher.publishEvent(new ArticlePublishedEvent(
                article.getId(),
                article.getTitle(),
                article.getSlug(),
                article.getContent(),
                article.getCategoryId()
        ));

        return article.getId();
    }

    @Transactional
    @CacheEvict(allEntries = true)
    public void update(UpdateArticleCommand command) {
        Article article = articleRepository.findById(new ArticleId(command.getArticleId()))
                .orElseThrow(() -> new BusinessException("文章不存在"));
        BeanUtils.copyProperties(command, article);
        article.calculateWordCount();
        articleRepository.save(article);

        // 更新标签关联：先删除旧关联，再添加新关联
        articleTagRepository.deleteByArticleId(article.getId());
        if (!CollectionUtils.isEmpty(command.getTagIds())) {
            articleTagRepository.saveBatch(article.getId(), command.getTagIds());
        }
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
    @Cacheable(cacheNames = "article:list", key = "#query.current + '-' + #query.size")
    public PageResult<ArticleDTO> listPublished(ArticlePageQuery query) {
        IPage<Article> page = new Page<>(query.getCurrent(), query.getSize());
        IPage<Article> result;

        // 根据查询条件选择不同的查询方法
        if (query.getTagId() != null) {
            result = articleRepository.findByTagId(query.getTagId(), page);
        } else if (query.getCategoryId() != null) {
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

    @Transactional(readOnly = true)
    public PageResult<ArticleDTO> listByTagId(Long tagId, int current, int size) {
        IPage<Article> page = new Page<>(current, size);
        IPage<Article> result = articleRepository.findByTagId(tagId, page);
        List<ArticleDTO> records = result.getRecords().stream().map(this::toDTO).toList();
        return new PageResult<>(result.getTotal(), result.getCurrent(), result.getSize(), records);
    }

    private ArticleDTO toDTO(Article article) {
        ArticleDTO dto = new ArticleDTO();
        BeanUtils.copyProperties(article, dto);
        dto.setId(article.getId());

        // 填充分类信息
        if (article.getCategoryId() != null) {
            categoryRepository.findById(article.getCategoryId())
                    .ifPresent(category -> {
                        CategoryDTO categoryDTO = new CategoryDTO();
                        BeanUtils.copyProperties(category, categoryDTO);
                        dto.setCategory(categoryDTO);
                    });
        }

        // 填充标签信息
        List<Long> tagIds = articleTagRepository.findTagIdsByArticleId(article.getId());
        if (!tagIds.isEmpty()) {
            List<TagDTO> tagDTOs = tagRepository.findByIds(new java.util.HashSet<>(tagIds)).stream()
                    .map(tag -> {
                        TagDTO tagDTO = new TagDTO();
                        BeanUtils.copyProperties(tag, tagDTO);
                        return tagDTO;
                    })
                    .collect(Collectors.toList());
            dto.setTags(tagDTOs);
        } else {
            dto.setTags(new ArrayList<>());
        }

        return dto;
    }
}
