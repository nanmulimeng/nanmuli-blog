package com.nanmuli.blog.infrastructure.persistence.article;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.nanmuli.blog.domain.article.Article;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

import java.util.List;
import java.util.Map;

@Mapper
public interface ArticleMapper extends BaseMapper<Article> {

    @Update("UPDATE article SET view_count = view_count + 1 WHERE id = #{id}")
    void increaseViewCount(@Param("id") Long id);

    @Select("""
            SELECT
                TO_CHAR(publish_time, 'YYYY') as year,
                TO_CHAR(publish_time, 'MM') as month,
                COUNT(*) as count
            FROM article
            WHERE status = 1 AND is_deleted = false
            GROUP BY TO_CHAR(publish_time, 'YYYY'), TO_CHAR(publish_time, 'MM')
            ORDER BY year DESC, month DESC
            """)
    List<Map<String, Object>> selectArchiveByYearMonth();

    /**
     * 批量查询多个分类的文章数量
     * 只统计已发布(status=1)且未删除的文章
     */
    @Select("<script>SELECT category_id, COUNT(*) as count FROM article WHERE category_id IN <foreach collection='categoryIds' item='id' open='(' separator=',' close=')'>#{id}</foreach> AND status = 1 AND is_deleted = false GROUP BY category_id</script>")
    List<Map<String, Object>> selectCategoryArticleCounts(@Param("categoryIds") List<Long> categoryIds);

    /**
     * zhparser 中文全文搜索 - 已发布文章
     * 通过 GIN 索引 idx_article_fts 加速,扫描合并 title+summary+content 的 tsvector
     * categoryIds 非空时使用 OR 条件扩展匹配范围
     */
    @Select("""
            <script>
            SELECT * FROM article
            WHERE status = 1 AND is_deleted = false
              AND (
                to_tsvector('chinese_zh',
                    coalesce(title, '') || ' ' || coalesce(summary, '') || ' ' || coalesce(content, '')
                ) @@ plainto_tsquery('chinese_zh', #{keyword})
                <if test="categoryIds != null and categoryIds.size() > 0">
                  OR category_id IN
                  <foreach collection="categoryIds" item="id" open="(" separator="," close=")">
                    #{id}
                  </foreach>
                </if>
              )
            ORDER BY is_top DESC,
              ts_rank(
                to_tsvector('chinese_zh',
                    coalesce(title, '') || ' ' || coalesce(summary, '') || ' ' || coalesce(content, '')
                ),
                plainto_tsquery('chinese_zh', #{keyword})
              ) DESC
              <choose>
                <when test='"oldest".equals(sort)'>, publish_time ASC</when>
                <when test='"popular".equals(sort)'>, view_count DESC</when>
                <otherwise>, publish_time DESC</otherwise>
              </choose>
            </script>
            """)
    IPage<Article> searchPublishedByFts(IPage<Article> page,
                                        @Param("keyword") String keyword,
                                        @Param("categoryIds") List<Long> categoryIds,
                                        @Param("sort") String sort);

    /**
     * zhparser 中文全文搜索 - 全部文章(不限状态),用于管理后台
     */
    @Select("""
            <script>
            SELECT * FROM article
            WHERE is_deleted = false
              AND (
                to_tsvector('chinese_zh',
                    coalesce(title, '') || ' ' || coalesce(summary, '') || ' ' || coalesce(content, '')
                ) @@ plainto_tsquery('chinese_zh', #{keyword})
                <if test="categoryIds != null and categoryIds.size() > 0">
                  OR category_id IN
                  <foreach collection="categoryIds" item="id" open="(" separator="," close=")">
                    #{id}
                  </foreach>
                </if>
              )
            ORDER BY
              ts_rank(
                to_tsvector('chinese_zh',
                    coalesce(title, '') || ' ' || coalesce(summary, '') || ' ' || coalesce(content, '')
                ),
                plainto_tsquery('chinese_zh', #{keyword})
              ) DESC,
              created_at DESC
            </script>
            """)
    IPage<Article> searchAllByFts(IPage<Article> page,
                                  @Param("keyword") String keyword,
                                  @Param("categoryIds") List<Long> categoryIds);

    /**
     * pg_trgm 模糊搜索 - 已发布文章
     * word_similarity 比较查询词与文档中任意连续子串的相似度，支持部分匹配和拼写容错
     * 用于 FTS 精确搜索无结果时的后备
     */
    @Select("""
            <script>
            SELECT *, word_similarity(#{keyword},
                coalesce(title, '') || ' ' || coalesce(summary, '') || ' ' || coalesce(content, '')
            ) AS trgm_sim
            FROM article
            WHERE status = 1 AND is_deleted = false
              AND word_similarity(#{keyword},
                  coalesce(title, '') || ' ' || coalesce(summary, '') || ' ' || coalesce(content, '')
              ) &gt; 0.15
              <if test="categoryIds != null and categoryIds.size() > 0">
                AND category_id IN
                <foreach collection="categoryIds" item="id" open="(" separator="," close=")">
                  #{id}
                </foreach>
              </if>
            ORDER BY trgm_sim DESC
            </script>
            """)
    IPage<Article> searchPublishedByTrigram(IPage<Article> page,
                                            @Param("keyword") String keyword,
                                            @Param("categoryIds") List<Long> categoryIds);
}
