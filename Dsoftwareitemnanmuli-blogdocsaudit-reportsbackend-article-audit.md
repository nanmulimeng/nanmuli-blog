# 文章模块排查报告

## 统计摘要
- 发现问题总数: 9
- P0: 3, P1: 3, P2: 2, P3: 1

---

## 详细问题列表

### P0: toDTO()中标签设置为单元素列表，与Tag系统设计不符
- **文件**: `backend/src/main/java/com/nanmuli/blog/application/article/ArticleAppService.java:310`
- **问题**: 
  ```java
  // 设置标签为分类名称（用于SEO关键词）
  dto.setTags(Collections.singletonList(category.getName()));
  ```
  代码将标签硬编码为包含单个分类名称的列表，与系统中独立的Tag实体和ArticleTag关联表设计不符。系统中存在完整的Tag领域模型（`domain/tag/Tag.java`）和文章-标签关联机制（`ArticleTagRepository`），但文章创建/更新时完全没有处理标签关联逻辑。
- **影响**: 
  1. 前端无法获取真实的文章标签数据
  2. 无法按标签筛选文章（虽然Repository支持`findByTagId`，但无标签数据）
  3. 标签系统成为死代码
- **修复建议**: 
  1. 在`CreateArticleCommand`和`UpdateArticleCommand`中添加`List<Long> tagIds`字段
  2. 在创建/更新文章时，调用`articleTagRepository.saveBatch(articleId, tagIds)`保存标签关联
  3. 在`toDTO()`中查询文章的真实标签列表并设置到DTO

---

### P0: getArchive()中使用原始Map转换，字段类型转换安全性
- **文件**: `backend/src/main/java/com/nanmuli/blog/application/article/ArticleAppService.java:257-271`
- **问题**: 
  ```java
  List<java.util.Map<String, Object>> rawData = articleRepository.findArchiveByYearMonth();
  for (java.util.Map<String, Object> row : rawData) {
      ArticleArchiveDTO dto = new ArticleArchiveDTO();
      dto.setYear((String) row.get("year"));
      dto.setMonth((String) row.get("month"));
      dto.setCount(((Number) row.get("count")).longValue());
      result.add(dto);
  }
  ```
  使用原始Map接收SQL查询结果并进行强制类型转换，存在以下风险：
  1. 如果数据库返回的字段名拼写错误（如`years`而非`year`），会静默返回null
  2. 类型转换失败时会在运行时抛出`ClassCastException`
  3. 数据库方言差异可能导致类型不一致（如Oracle的`TO_CHAR`返回类型与其他数据库不同）
- **修复建议**: 
  1. 创建专用的结果对象或MapStruct映射器
  2. 添加字段存在性和类型校验
  3. 或使用MyBatis的`@Result`注解将结果直接映射到DTO

---

### P0: incrementViewCount异步方法的事务控制问题
- **文件**: `backend/src/main/java/com/nanmuli/blog/application/article/ArticleAppService.java:249-255`
- **问题**: 
  ```java
  @Async
  @Transactional
  public void incrementViewCount(String slug) {
      articleRepository.findBySlug(slug).ifPresent(article -> {
          articleRepository.increaseViewCount(new ArticleId(article.getId()));
      });
  }
  ```
  1. `@Async`方法的事务传播行为特殊：默认`REQUIRED`在异步线程中可能无法正确传播事务上下文
  2. 视图计数是高频操作，使用事务可能导致数据库锁竞争
  3. 异步方法中的异常不会传播给调用者，失败时无感知
- **修复建议**: 
  1. 移除`@Transactional`注解，视图计数不需要事务保证
  2. 或改为`@Transactional(propagation = Propagation.NOT_SUPPORTED)`
  3. 添加日志记录异步操作失败情况
  4. 考虑使用Redis计数+定时同步到数据库的方案优化性能

---

### P1: ArticleAppService同时依赖CategoryRepository和CategoryAppService
- **文件**: `backend/src/main/java/com/nanmuli/blog/application/article/ArticleAppService.java:49-51`
- **问题**: 
  ```java
  private final CategoryRepository categoryRepository;
  private final CategoryAppService categoryAppService;
  ```
  应用服务层同时依赖了领域层的`CategoryRepository`和同一应用层的`CategoryAppService`，违反了分层架构原则：
  1. 应用服务之间不应直接依赖，应通过领域服务或领域对象交互
  2. 可能导致循环依赖风险
  3. 职责边界模糊：部分操作直接操作Repository，部分通过AppService
- **修复建议**: 
  1. 统一通过`CategoryAppService`访问分类相关功能
  2. 或引入领域服务`CategoryDomainService`处理跨聚合逻辑
  3. 当前`categoryAppService.refreshArticleCount()`调用是合理的，但`categoryRepository.findById()`应统一走应用服务

---

### P1: buildCategoryPath()循环查询上级分类，N+1问题
- **文件**: `backend/src/main/java/com/nanmuli/blog/application/article/ArticleAppService.java:332-350`
- **问题**: 
  ```java
  private List<CategoryDTO> buildCategoryPath(Category category) {
      List<CategoryDTO> path = new ArrayList<>();
      path.add(toCategoryDTO(category));
      Long parentId = category.getParentId();
      while (parentId != null) {
          Category parent = categoryRepository.findById(parentId).orElse(null);  // 每次循环一次查询
          if (parent == null) break;
          path.add(0, toCategoryDTO(parent));
          parentId = parent.getParentId();
      }
      return path;
  }
  ```
  每次构建分类路径都会循环查询上级分类，如果分类层级较深（如5层），则会产生5次数据库查询。在文章列表查询时，每篇文章都会触发此操作，造成严重性能问题。
- **修复建议**: 
  1. 使用缓存：对分类数据进行Redis缓存（`@Cacheable`）
  2. 批量查询：先一次性加载所有分类，在内存中构建父子关系
  3. 使用递归CTE查询一次性获取完整路径（数据库层面优化）
  4. 在`Category`实体中冗余存储`path`字段，维护时更新

---

### P1: ArticleTagRepositoryImpl.saveBatch()使用循环插入
- **文件**: `backend/src/main/java/com/nanmuli/blog/infrastructure/persistence/article/ArticleTagRepositoryImpl.java:33-40`
- **问题**: 
  ```java
  @Override
  public void saveBatch(Long articleId, List<Long> tagIds) {
      if (CollectionUtils.isEmpty(tagIds)) return;
      for (Long tagId : tagIds) {
          save(articleId, tagId);  // 循环单条插入
      }
  }
  ```
  批量保存标签关联时使用循环单条插入，如果文章关联大量标签（如20个），会产生20次数据库往返。
- **修复建议**: 
  1. 使用MyBatis-Plus的`insertBatch`或`saveBatch`方法
  2. 或手写批量插入SQL：`INSERT INTO article_tag (article_id, tag_id) VALUES (?, ?), (?, ?), ...`

---

### P2: 缓存策略不合理
- **文件**: `backend/src/main/java/com/nanmuli/blog/application/article/ArticleAppService.java`
- **问题**: 
  1. `listPublished`使用`query.current + '-' + query.size`作为缓存key，但忽略了`categoryId`和`sort`参数，不同筛选条件会命中错误缓存
  2. `getBySlug`使用slug作为缓存key，但文章更新时仅通过`@CacheEvict(allEntries = true)`清除，无法精准清除
  3. 缺少缓存过期时间配置
- **修复建议**: 
  ```java
  // 应包含所有查询参数
  @Cacheable(cacheNames = "article:list", 
      key = "#query.current + '-' + #query.size + '-' + #query.categoryId + '-' + #query.sort")
  
  // 更新时精准清除
  @CacheEvict(key = "#command.slug")
  public void update(UpdateArticleCommand command) { ... }
  ```

---

### P2: 分类路径查询未缓存
- **文件**: `backend/src/main/java/com/nanmuli/blog/application/article/ArticleAppService.java:332-350`
- **问题**: `buildCategoryPath()`方法没有使用缓存，每次构建路径都需要多次查询数据库。分类数据是相对稳定的数据，适合缓存。
- **修复建议**: 
  1. 在`CategoryAppService.getCategoryPath()`上添加`@Cacheable`
  2. 或直接在`buildCategoryPath()`方法内使用Spring Cache
  3. 分类更新时清除相关缓存

---

### P3: Markdown内容XSS过滤缺失
- **文件**: `backend/src/main/java/com/nanmuli/blog/shared/util/MarkdownUtil.java:38-44`
- **问题**: 
  ```java
  public String toHtml(String markdown) {
      if (markdown == null || markdown.isEmpty()) return "";
      Node document = parser.parse(markdown);
      return renderer.render(document);  // 直接渲染，无XSS过滤
  }
  ```
  Markdown转换为HTML时没有进行XSS过滤，如果用户输入包含恶意脚本：
  ```markdown
  <script>alert('XSS')</script>
  [点击](javascript:alert('XSS'))
  ```
  会被直接渲染到页面。
- **修复建议**: 
  1. 配置Flexmark的HTML过滤器
  2. 或使用JSoup对生成的HTML进行白名单过滤
  3. 前端渲染时也需做XSS防护（双重保障）

---

## 正向发现

### 1. 领域模型设计规范
- `Article`聚合根封装了业务方法（`publish()`, `draft()`, `recycle()`, `calculateWordCount()`）
- 使用了值对象`ArticleId`和枚举`ArticleStatus`，符合DDD实践
- 逻辑删除通过`BaseAggregateRoot`统一处理

### 2. 命令模式应用
- 使用`CreateArticleCommand`和`UpdateArticleCommand`封装入参，配合JSR-303校验注解
- 命令与查询分离（CQRS初步实践）

### 3. slug生成逻辑完善
- 支持中文转拼音（使用Hutool的PinyinUtil）
- 自动处理唯一性冲突（添加数字后缀）
- 格式校验和清理（正则替换）

### 4. 事件驱动设计
- 发布`ArticleCreatedEvent`和`ArticlePublishedEvent`支持后续扩展（如AI生成、消息通知）

### 5. 分类循环引用检测
- `CategoryAppService.detectCircularReference()`使用Set检测直接和间接循环引用

### 6. 视图计数优化
- 使用`@Async`异步处理视图计数，避免阻塞主流程
- 数据库层面使用原子更新（`UPDATE article SET view_count = view_count + 1`）

---

## 整体评估

| 维度 | 评分 | 说明 |
|------|------|------|
| 架构规范 | 7/10 | 分层清晰，但存在应用服务间依赖和Repository/AppService混用问题 |
| 功能完整性 | 6/10 | 核心CRUD完整，但标签系统未实际接入 |
| 性能优化 | 5/10 | 存在明显的N+1查询问题，缓存策略不完善 |
| 安全性 | 6/10 | 基础校验完善，但XSS过滤缺失，异步事务处理不当 |
| 代码质量 | 7/10 | 命名规范，注释清晰，但部分代码存在重复（如分类路径构建） |

### 优先修复建议
1. **立即修复（P0）**: 标签系统接入、异步事务问题
2. **短期修复（P1）**: 解决N+1查询、统一分层依赖
3. **中期优化（P2/P3）**: 完善缓存策略、添加XSS过滤

