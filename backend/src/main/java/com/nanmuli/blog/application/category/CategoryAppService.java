package com.nanmuli.blog.application.category;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.nanmuli.blog.application.category.command.CreateCategoryCommand;
import com.nanmuli.blog.application.category.command.UpdateCategoryCommand;
import com.nanmuli.blog.application.category.dto.CategoryDTO;
import com.nanmuli.blog.application.category.query.CategoryPageQuery;
import com.nanmuli.blog.domain.article.ArticleRepository;
import com.nanmuli.blog.domain.category.Category;
import com.nanmuli.blog.domain.category.CategoryRepository;
import com.nanmuli.blog.shared.exception.BusinessException;
import com.nanmuli.blog.shared.result.PageResult;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.BeanUtils;
import org.springframework.cache.annotation.CacheConfig;
import org.springframework.cache.annotation.CacheEvict;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;

/**
 * 分类应用服务
 */
@Service
@RequiredArgsConstructor
@CacheConfig(cacheNames = "category")
@Transactional(readOnly = true)
public class CategoryAppService {

    private final CategoryRepository categoryRepository;
    private final ArticleRepository articleRepository;

    /**
     * 创建分类
     */
    @Transactional
    @CacheEvict(allEntries = true)
    public Long create(CreateCategoryCommand command) {
        // 清理slug（去除前后空格并转为小写）
        String slug = command.getSlug() != null ? command.getSlug().trim().toLowerCase() : null;
        command.setSlug(slug);

        // 检查slug唯一性
        if (categoryRepository.existsBySlug(slug)) {
            throw new BusinessException("分类标识已存在");
        }

        Category category = new Category();
        BeanUtils.copyProperties(command, category);

        // 设置颜色默认值
        if (category.getColor() == null || category.getColor().isBlank()) {
            category.setColor("#409EFF");
        }

        // 验证父分类合法性
        validateParentCategory(category.getParentId(), null);

        try {
            categoryRepository.save(category);
        } catch (DataIntegrityViolationException e) {
            if (e.getMessage() != null && e.getMessage().contains("category_slug_key")) {
                throw new BusinessException("分类标识已存在");
            }
            throw e;
        }
        return category.getId();
    }

    /**
     * 更新分类
     */
    @Transactional
    @CacheEvict(allEntries = true)
    public void update(Long id, UpdateCategoryCommand command) {
        Category category = categoryRepository.findById(id)
                .orElseThrow(() -> new BusinessException("分类不存在"));

        // 清理slug（去除前后空格并转为小写）
        String slug = command.getSlug() != null ? command.getSlug().trim().toLowerCase() : null;
        command.setSlug(slug);

        // 检查slug唯一性（排除自身）
        if (!slug.equals(category.getSlug()) && categoryRepository.existsBySlug(slug)) {
            throw new BusinessException("分类标识已存在");
        }

        // 检查是否将父分类改为叶子分类（有子分类时不允许）
        if (Boolean.TRUE.equals(command.getIsLeaf()) && hasChildren(id)) {
            throw new BusinessException("该分类下有子分类，不能设置为叶子分类");
        }

        // 验证父分类合法性
        validateParentCategory(command.getParentId(), id);

        BeanUtils.copyProperties(command, category);
        category.setId(id);

        // 设置颜色默认值
        if (category.getColor() == null || category.getColor().isBlank()) {
            category.setColor("#409EFF");
        }

        try {
            categoryRepository.save(category);
        } catch (DataIntegrityViolationException e) {
            if (e.getMessage() != null && e.getMessage().contains("category_slug_key")) {
                throw new BusinessException("分类标识已存在");
            }
            throw e;
        }
    }

    /**
     * 获取启用的分类树（前台展示）
     */
    public List<CategoryDTO> listAllActive() {
        List<Category> categories = categoryRepository.findAllActive();
        return buildTree(categories);
    }

    /**
     * 获取所有分类树（管理后台）
     */
    @Cacheable(key = "'tree'")
    public List<CategoryDTO> listAll() {
        List<Category> categories = categoryRepository.findAll();
        return buildTree(categories);
    }

    /**
     * 批量刷新所有分类的文章数
     * 先刷新叶子分类，然后重新计算父分类的文章数（包含子分类）
     */
    @Transactional
    @CacheEvict(allEntries = true)
    public void refreshAllCategoryArticleCounts() {
        // 第一步：刷新所有叶子分类的文章数
        List<Category> allCategories = categoryRepository.findAll();
        for (Category category : allCategories) {
            if (category.isLeaf()) {
                // 只有叶子分类直接关联文章
                refreshArticleCount(category.getId());
            }
        }

        // 第二步：重新计算父分类的文章数（从底层向上计算）
        // 按层级深度降序排序，先处理最底层的分类，再处理上层
        Map<Long, Category> categoryMap = allCategories.stream()
                .collect(Collectors.toMap(Category::getId, c -> c));

        // 获取所有父分类（非叶子分类），按深度降序排序
        List<Category> parentCategories = allCategories.stream()
                .filter(c -> !c.isLeaf())
                .sorted((c1, c2) -> getCategoryDepth(c2, categoryMap) - getCategoryDepth(c1, categoryMap))
                .toList();

        // 计算每个父分类的文章数（包含所有子分类）
        // 由于已经按深度降序排序，最深的分类会先被处理
        for (Category parent : parentCategories) {
            int totalCount = calculateTotalArticleCountForCategory(parent.getId(), categoryMap);
            parent.setArticleCount(totalCount);
            categoryRepository.save(parent);
            // 更新Map中的值，以便上层分类计算时使用
            categoryMap.get(parent.getId()).setArticleCount(totalCount);
        }
    }

    /**
     * 获取分类的层级深度
     */
    private int getCategoryDepth(Category category, Map<Long, Category> categoryMap) {
        int depth = 0;
        Long parentId = category.getParentId();
        while (parentId != null) {
            depth++;
            Category parent = categoryMap.get(parentId);
            if (parent == null) {
                break;
            }
            parentId = parent.getParentId();
        }
        return depth;
    }

    /**
     * 递归计算分类的总文章数（包含所有子分类）
     */
    private int calculateTotalArticleCountForCategory(Long categoryId, Map<Long, Category> categoryMap) {
        Category category = categoryMap.get(categoryId);
        if (category == null) {
            return 0;
        }

        // 如果是叶子分类，直接返回文章数
        if (category.isLeaf()) {
            return category.getArticleCount() != null ? category.getArticleCount() : 0;
        }

        // 获取所有子分类
        List<Category> children = categoryMap.values().stream()
                .filter(c -> categoryId.equals(c.getParentId()))
                .toList();

        // 累加所有子分类的文章数
        int totalCount = 0;
        for (Category child : children) {
            totalCount += calculateTotalArticleCountForCategory(child.getId(), categoryMap);
        }

        return totalCount;
    }

    /**
     * 分页查询分类列表（平铺结构，支持筛选）
     */
    public PageResult<CategoryDTO> listPage(CategoryPageQuery query) {
        IPage<Category> page = new Page<>(query.getCurrent(), query.getSize());
        IPage<Category> result = categoryRepository.findPage(
                page,
                query.getParentId(),
                query.getIsLeaf(),
                query.getStatus(),
                query.getKeyword()
        );

        List<CategoryDTO> records = result.getRecords().stream()
                .map(this::toDTO)
                .toList();

        return new PageResult<>(result.getTotal(), result.getCurrent(), result.getSize(), records);
    }

    /**
     * 获取分类路径（从根到当前分类）
     */
    public List<CategoryDTO> getCategoryPath(Long categoryId) {
        List<CategoryDTO> path = new ArrayList<>();
        if (categoryId == null) {
            return path;
        }

        Category current = categoryRepository.findById(categoryId).orElse(null);
        while (current != null) {
            path.add(0, toDTO(current));
            if (current.getParentId() == null) {
                break;
            }
            current = categoryRepository.findById(current.getParentId()).orElse(null);
        }

        return path;
    }

    /**
     * 获取叶子分类列表（可关联文章）
     */
    public List<CategoryDTO> listLeafCategories() {
        return categoryRepository.findAllActive().stream()
                .filter(Category::isLeaf)
                .map(this::toDTO)
                .toList();
    }

    /**
     * 根据ID获取分类详情
     */
    public CategoryDTO getById(Long id) {
        Category category = categoryRepository.findById(id)
                .orElseThrow(() -> new BusinessException("分类不存在"));
        return toDTO(category);
    }

    /**
     * 删除分类
     */
    @Transactional
    @CacheEvict(allEntries = true)
    public void delete(Long id) {
        Category category = categoryRepository.findById(id)
                .orElseThrow(() -> new BusinessException("分类不存在"));

        // 检查是否有子分类
        if (hasChildren(id)) {
            throw new BusinessException("该分类下有子分类，不能删除");
        }

        // 检查是否有文章关联（只有叶子分类可能关联文章）
        if (category.isLeaf()) {
            Long articleCount = articleRepository.countByCategoryId(id);
            if (articleCount > 0) {
                throw new BusinessException("该分类下有关联文章，不能删除");
            }
        }

        categoryRepository.deleteById(id);
    }

    /**
     * 刷新指定分类的文章数量
     * 在文章创建、更新分类、删除时调用
     */
    @Transactional
    public void refreshArticleCount(Long categoryId) {
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

    private static final int MAX_CATEGORY_DEPTH = 5;

    /**
     * 验证父分类的合法性
     * 包含直接循环检测（A->A）和间接循环检测（A->B->C->A）
     */
    private void validateParentCategory(Long parentId, Long currentId) {
        if (parentId == null) {
            return;
        }

        // 不能将自身设置为父分类（直接循环检测）
        if (currentId != null && parentId.equals(currentId)) {
            throw new BusinessException("不能将自身设置为父分类");
        }

        // 验证父分类存在性
        Category parent = categoryRepository.findById(parentId)
                .orElseThrow(() -> new BusinessException("父分类不存在"));

        if (parent.isLeaf()) {
            throw new BusinessException("叶子分类不能作为父分类");
        }

        // 间接循环检测：检查父分类链是否包含当前分类（避免 A->B->C->A）
        if (currentId != null) {
            detectCircularReference(currentId, parentId);
        }

        // 层数限制检测：防止嵌套过深导致性能问题
        validateCategoryDepth(parentId);
    }

    /**
     * 验证分类嵌套层数不超过最大限制
     */
    private void validateCategoryDepth(Long parentId) {
        int depth = 1; // 当前要创建的分类算第1层
        Long currentParentId = parentId;

        while (currentParentId != null) {
            depth++;
            if (depth > MAX_CATEGORY_DEPTH) {
                throw new BusinessException("分类嵌套层数不能超过" + MAX_CATEGORY_DEPTH + "层");
            }
            Category currentParent = categoryRepository.findById(currentParentId).orElse(null);
            if (currentParent == null) {
                break;
            }
            currentParentId = currentParent.getParentId();
        }
    }

    /**
     * 检测分类循环引用
     * 使用Set记录已访问的分类ID，遍历父分类链
     */
    private void detectCircularReference(Long categoryId, Long parentId) {
        Set<Long> visited = new HashSet<>();
        visited.add(categoryId);

        Long currentParentId = parentId;
        while (currentParentId != null) {
            if (visited.contains(currentParentId)) {
                throw new BusinessException("检测到分类循环引用，请检查父分类设置");
            }
            visited.add(currentParentId);

            Category currentParent = categoryRepository.findById(currentParentId)
                    .orElse(null);
            if (currentParent == null) {
                break;
            }
            currentParentId = currentParent.getParentId();
        }
    }

    /**
     * 是否有子分类
     */
    private boolean hasChildren(Long parentId) {
        return categoryRepository.existsByParentId(parentId);
    }

    /**
     * 构建树形结构
     */
    private List<CategoryDTO> buildTree(List<Category> categories) {
        // 批量获取文章数（避免N+1查询）
        Map<Long, Integer> articleCountMap = batchGetArticleCounts(categories);

        // 转换为DTO（使用预计算的文章数）
        List<CategoryDTO> dtoList = categories.stream()
                .map(cat -> toDTO(cat, articleCountMap))
                .toList();

        // 按parentId分组，并对每个分组内的子节点按sort排序
        Map<Long, List<CategoryDTO>> parentMap = dtoList.stream()
                .filter(dto -> dto.getParentId() != null)
                .collect(Collectors.groupingBy(
                        CategoryDTO::getParentId,
                        Collectors.collectingAndThen(
                                Collectors.toList(),
                                list -> list.stream()
                                        .sorted(Comparator.comparing(CategoryDTO::getSort, Comparator.nullsLast(Integer::compareTo)))
                                        .collect(Collectors.toList())
                        )
                ));

        // 设置子节点（已排序）
        dtoList.forEach(dto -> dto.setChildren(parentMap.get(dto.getId())));

        // 获取根节点列表
        List<CategoryDTO> rootList = dtoList.stream()
                .filter(dto -> dto.getParentId() == null)
                .sorted(Comparator.comparing(CategoryDTO::getSort, Comparator.nullsLast(Integer::compareTo)))
                .collect(Collectors.toList());

        // 递归计算每个父分类的总文章数（包含所有子分类）
        rootList.forEach(this::calculateTotalArticleCount);

        return rootList;
    }

    /**
     * 递归计算分类的总文章数（包含所有子分类）
     */
    private int calculateTotalArticleCount(CategoryDTO category) {
        if (category.getChildren() == null || category.getChildren().isEmpty()) {
            // 叶子节点，返回自身的文章数
            return category.getArticleCount() != null ? category.getArticleCount() : 0;
        }

        // 父节点，累加所有子节点的文章数
        int totalChildrenCount = category.getChildren().stream()
                .mapToInt(this::calculateTotalArticleCount)
                .sum();

        // 更新父分类的文章数（自身文章数 + 子分类文章数之和）
        int totalCount = (category.getArticleCount() != null ? category.getArticleCount() : 0) + totalChildrenCount;
        category.setArticleCount(totalCount);

        return totalCount;
    }

    /**
     * 转换为DTO（实时查询文章数）
     */
    private CategoryDTO toDTO(Category category) {
        CategoryDTO dto = new CategoryDTO();
        BeanUtils.copyProperties(category, dto);
        dto.setId(category.getId());
        // 显式映射时间字段（字段名不一致）
        dto.setCreateTime(category.getCreatedAt());
        dto.setUpdateTime(category.getUpdatedAt());
        // 实时统计文章数（只统计已发布且未删除的文章）
        Long count = articleRepository.countByCategoryId(category.getId());
        dto.setArticleCount(count.intValue());
        return dto;
    }

    /**
     * 转换为DTO（使用预计算的批量文章数）
     */
    private CategoryDTO toDTO(Category category, Map<Long, Integer> articleCountMap) {
        CategoryDTO dto = new CategoryDTO();
        BeanUtils.copyProperties(category, dto);
        dto.setId(category.getId());
        // 显式映射时间字段（字段名不一致）
        dto.setCreateTime(category.getCreatedAt());
        dto.setUpdateTime(category.getUpdatedAt());
        // 使用预计算的文章数（只统计已发布且未删除的文章）
        dto.setArticleCount(articleCountMap.getOrDefault(category.getId(), 0));
        return dto;
    }

    /**
     * 批量获取分类文章数
     * 只统计已发布(status=1)且未删除的文章
     */
    private Map<Long, Integer> batchGetArticleCounts(List<Category> categories) {
        if (categories.isEmpty()) {
            return Map.of();
        }

        List<Long> categoryIds = categories.stream()
                .map(Category::getId)
                .toList();

        // 批量查询文章数
        return articleRepository.countByCategoryIds(categoryIds);
    }
}
