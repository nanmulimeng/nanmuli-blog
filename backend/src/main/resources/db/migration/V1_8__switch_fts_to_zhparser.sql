-- 全文搜索切换至 zhparser 中文分词
-- 决策依据(2026-05-05):
--   1. 原 'simple' tokenizer 按空格分词,中文搜索几乎不可用
--   2. ArticleRepositoryImpl 当前使用 LIKE '%kw%' 全表扫描,无 FTS 收益
--   3. zhparser 基于 SCWS 提供准确的中文分词,GIN 索引可达毫秒级响应
--
-- 前置条件: PostgreSQL 容器必须已安装 zhparser 扩展
--   生产环境需先重建 deploy/db/Dockerfile 镜像并替换容器
--
-- 影响:
--   - 删除旧的 simple tokenizer GIN 索引(2个)
--   - 创建新的 zhparser GIN 索引(1个,合并 title/summary/content)
--   - 索引重建需要时间,数据量大时考虑 CONCURRENTLY

-- 1. 启用 zhparser 扩展(幂等)
CREATE EXTENSION IF NOT EXISTS zhparser;

-- 2. 创建中文文本搜索配置(若不存在)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_ts_config WHERE cfgname = 'chinese_zh') THEN
        CREATE TEXT SEARCH CONFIGURATION chinese_zh (PARSER = zhparser);
        ALTER TEXT SEARCH CONFIGURATION chinese_zh
            ADD MAPPING FOR n,v,a,i,e,l WITH simple;
    END IF;
END
$$;

-- 3. 删除旧的 simple tokenizer FTS 索引
DROP INDEX IF EXISTS idx_article_content_search;
DROP INDEX IF EXISTS idx_article_title_search;

-- 4. 创建新的 zhparser FTS 索引(部分索引,仅覆盖已发布未删除文章)
CREATE INDEX IF NOT EXISTS idx_article_fts ON article USING GIN (
    to_tsvector('chinese_zh',
        coalesce(title, '') || ' ' || coalesce(summary, '') || ' ' || coalesce(content, '')
    )
) WHERE status = 1 AND is_deleted = FALSE;
