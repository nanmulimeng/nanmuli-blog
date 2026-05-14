-- 为 article.slug 添加唯一索引，防止并发创建时产生重复 slug
-- 仅对未删除记录生效（配合逻辑删除）

CREATE UNIQUE INDEX IF NOT EXISTS idx_article_slug_unique
    ON article(slug)
    WHERE is_deleted = false;
