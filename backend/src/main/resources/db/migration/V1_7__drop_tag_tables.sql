-- 删除未使用的标签系统(tag/article_tag 两表)
-- 决策依据(2026-05-05):
--   1. domain/application/interfaces 三层零 Java 代码,前端无入口
--   2. category 表已通过 is_leaf 机制覆盖标签语义(叶子分类即标签)
--   3. 保留双轨标签设计是冗余,清理后简化模型

-- 1. 先删关联表(被外键引用,必须先删)
DROP TABLE IF EXISTS article_tag CASCADE;

-- 2. 删除标签主表
DROP TABLE IF EXISTS tag CASCADE;

-- 3. 清理可能残留的部分唯一索引(若已随表删除则 IF EXISTS 静默跳过)
DROP INDEX IF EXISTS idx_tag_slug_active;
