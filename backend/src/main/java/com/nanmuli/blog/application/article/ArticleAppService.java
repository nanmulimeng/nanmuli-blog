package com.nanmuli.blog.application.article;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.nanmuli.blog.application.article.command.CreateArticleCommand;
import com.nanmuli.blog.application.article.command.UpdateArticleCommand;
import com.nanmuli.blog.application.article.dto.ArticleDTO;
import com.nanmuli.blog.application.article.query.ArticlePageQuery;
import com.nanmuli.blog.domain.article.Article;
import com.nanmuli.blog.domain.article.ArticleId;
import com.nanmuli.blog.domain.article.ArticleRepository;
import com.nanmuli.blog.domain.category.CategoryRepository;
import com.nanmuli.blog.domain.tag.TagRepository;
import com.nanmuli.blog.shared.exception.BusinessException;
import com.nanmuli.blog.shared.result.PageResult;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.BeanUtils;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
@RequiredArgsConstructor
public class ArticleAppService {

    private final ArticleRepository articleRepository;
    private final CategoryRepository categoryRepository;
    private final TagRepository tagRepository;

    @Transactional
    public Long create(CreateArticleCommand command) {
        Article article = new Article();
        BeanUtils.copyProperties(command, article);
        article.calculateWordCount();
        article.publish();
        articleRepository.save(article);
        return article.getId();
    }

    @Transactional
    public void update(UpdateArticleCommand command) {
        Article article = articleRepository.findById(new ArticleId(command.getArticleId()))
                .orElseThrow(() -> new BusinessException("文章不存在"));
        BeanUtils.copyProperties(command, article);
        article.calculateWordCount();
        articleRepository.save(article);
    }

    @Transactional(readOnly = true)
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
    public PageResult<ArticleDTO> listPublished(ArticlePageQuery query) {
        IPage<Article> page = new Page<>(query.getCurrent(), query.getSize());
        IPage<Article> result = articleRepository.findPublishedPage(page);
        List<ArticleDTO> records = result.getRecords().stream().map(this::toDTO).toList();
        return new PageResult<>(result.getTotal(), result.getCurrent(), result.getSize(), records);
    }

    @Transactional(readOnly = true)
    public List<ArticleDTO> listTop(int limit) {
        return articleRepository.findTopArticles(limit).stream().map(this::toDTO).toList();
    }

    @Transactional
    public void delete(Long id) {
        articleRepository.deleteById(new ArticleId(id));
    }

    private ArticleDTO toDTO(Article article) {
        ArticleDTO dto = new ArticleDTO();
        BeanUtils.copyProperties(article, dto);
        dto.setId(article.getId());
        return dto;
    }
}
