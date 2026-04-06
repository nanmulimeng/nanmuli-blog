-- 分类文章数诊断脚本
-- 用于检查分类文章数是否与实际情况一致

-- 1. 查看所有分类及其文章数
SELECT
    c.id,
    c.name,
    c.parent_id,
    c.is_leaf,
    c.article_count as db_count,
    (SELECT COUNT(*) FROM article a
     WHERE a.category_id = c.id
     AND a.status = 1
     AND a.is_deleted = false) as actual_count
FROM category c
WHERE c.is_deleted = false
ORDER BY c.parent_id NULLS FIRST, c.sort;

-- 2. 查看父分类（包含子分类文章总数）
WITH RECURSIVE category_tree AS (
    -- 基础：叶子分类
    SELECT
        id,
        name,
        parent_id,
        is_leaf,
        article_count,
        id as root_id
    FROM category
    WHERE is_deleted = false AND is_leaf = true

    UNION ALL

    -- 递归：父分类
    SELECT
        c.id,
        c.name,
        c.parent_id,
        c.is_leaf,
        c.article_count,
        ct.root_id
    FROM category c
    JOIN category_tree ct ON c.id = ct.parent_id
    WHERE c.is_deleted = false
)
SELECT
    c.id,
    c.name,
    c.article_count as db_count,
    COALESCE(SUM(leaf.actual_count), 0) as actual_total_count,
    c.article_count - COALESCE(SUM(leaf.actual_count), 0) as diff
FROM category c
LEFT JOIN (
    SELECT
        ct.root_id,
        ct.id as leaf_id,
        (SELECT COUNT(*) FROM article a
         WHERE a.category_id = ct.id
         AND a.status = 1
         AND a.is_deleted = false) as actual_count
    FROM category_tree ct
    WHERE ct.is_leaf = true
) leaf ON c.id = leaf.root_id
WHERE c.is_deleted = false AND c.is_leaf = false
GROUP BY c.id, c.name, c.article_count
ORDER BY diff DESC;

-- 3. 查看文章状态分布（检查是否有未发布或被删除的文章）
SELECT
    c.name as category_name,
    a.status,
    CASE a.status
        WHEN 1 THEN '已发布'
        WHEN 2 THEN '草稿'
        WHEN 3 THEN '回收站'
        ELSE '未知'
    END as status_name,
    COUNT(*) as count
FROM article a
JOIN category c ON a.category_id = c.id
WHERE a.is_deleted = false
GROUP BY c.name, a.status
ORDER BY c.name, a.status;

-- 4. 修复叶子分类的文章数（使其与实际情况一致）
-- UPDATE category c
-- SET article_count = (
--     SELECT COUNT(*) FROM article a
--     WHERE a.category_id = c.id
--     AND a.status = 1
--     AND a.is_deleted = false
-- )
-- WHERE c.is_deleted = false AND c.is_leaf = true;

-- 5. 修复父分类的文章数（累加子分类）
-- WITH RECURSIVE category_tree AS (
--     SELECT id, parent_id, is_leaf, article_count, id as root_id
--     FROM category
--     WHERE is_deleted = false AND is_leaf = true
--     UNION ALL
--     SELECT c.id, c.parent_id, c.is_leaf, c.article_count, ct.root_id
--     FROM category c
--     JOIN category_tree ct ON c.id = ct.parent_id
--     WHERE c.is_deleted = false
-- )
-- UPDATE category c
-- SET article_count = (
--     SELECT COALESCE(SUM(leaf.actual_count), 0)
--     FROM (
--         SELECT
--             ct.root_id,
--             (SELECT COUNT(*) FROM article a
--              WHERE a.category_id = ct.id
--              AND a.status = 1
--              AND a.is_deleted = false) as actual_count
--         FROM category_tree ct
--         WHERE ct.is_leaf = true
--     ) leaf
--     WHERE leaf.root_id = c.id
-- )
-- WHERE c.is_deleted = false AND c.is_leaf = false;
