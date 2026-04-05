-- ============================================
-- 分类标签合并迁移脚本
-- 将标签(tag)数据迁移到分类(category)表
-- ============================================

-- 1. 确保 category 表有 is_leaf 字段
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'category' AND column_name = 'is_leaf'
    ) THEN
        ALTER TABLE category ADD COLUMN is_leaf BOOLEAN NOT NULL DEFAULT TRUE;
        COMMENT ON COLUMN category.is_leaf IS '是否为叶子节点：true-可关联文章（原标签概念），false-父分类（容器）';
    END IF;
END $$;

-- 2. 更新现有分类：将已有分类设置为父分类（容器）
UPDATE category SET is_leaf = FALSE WHERE is_leaf IS NULL OR is_leaf = TRUE;

-- 3. 将标签数据迁移到分类表（作为叶子分类）
-- 注意：这里假设标签的slug不会与分类slug冲突，如有冲突需要手动处理
INSERT INTO category (name, slug, description, color, icon, article_count, status, is_leaf, created_at, updated_at)
SELECT
    t.name,
    t.slug,
    t.description,
    t.color,
    t.icon,
    t.article_count,
    t.status,
    TRUE,  -- 迁移的标签设置为叶子分类
    t.created_at,
    t.updated_at
FROM tag t
WHERE NOT EXISTS (
    SELECT 1 FROM category c WHERE c.slug = t.slug
)
ON CONFLICT (slug) DO NOTHING;

-- 4. 更新文章关联关系
-- 将原来的 article_tag 关联转换为 category_id
-- 注意：一篇文章原来可以有多个标签，现在只能有一个分类
-- 这里取文章的最后一个标签作为主分类，其他标签忽略（或需要手动处理）

-- 4.1 创建临时表存储文章-标签映射
CREATE TEMP TABLE IF NOT EXISTS temp_article_category AS
SELECT DISTINCT ON (at.article_id)
    at.article_id,
    c.id as category_id
FROM article_tag at
JOIN tag t ON at.tag_id = t.id
JOIN category c ON t.slug = c.slug AND c.is_leaf = TRUE
ORDER BY at.article_id, at.created_at DESC;

-- 4.2 更新文章表的 category_id（仅更新没有分类的文章）
UPDATE article a
SET category_id = t.category_id
FROM temp_article_category t
WHERE a.id = t.article_id
AND (a.category_id IS NULL OR a.category_id NOT IN (
    SELECT id FROM category WHERE is_leaf = TRUE
));

-- 4.3 清理临时表
DROP TABLE IF EXISTS temp_article_category;

-- 5. 创建视图：用于兼容旧代码（如果需要查询原来的标签列表）
-- 这个视图可以在过渡期间使用，之后可以删除
CREATE OR REPLACE VIEW v_leaf_category AS
SELECT * FROM category WHERE is_leaf = TRUE;

-- 6. 添加索引（如果不存在）
CREATE INDEX IF NOT EXISTS idx_category_is_leaf ON category(is_leaf);

-- 7. 验证数据
-- SELECT '迁移完成统计' as info;
-- SELECT '父分类数量' as item, COUNT(*) as count FROM category WHERE is_leaf = FALSE;
-- SELECT '叶子分类数量（原标签）' as item, COUNT(*) as count FROM category WHERE is_leaf = TRUE;
-- SELECT '已关联文章数量' as item, COUNT(*) as count FROM article WHERE category_id IS NOT NULL;
