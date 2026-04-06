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

    @Select("SELECT COALESCE(SUM(view_count), 0) FROM article WHERE is_deleted = false")
    Long sumViewCount();

    /**
     * 批量查询多个分类的文章数量
     * 只统计已发布(status=1)且未删除的文章
     */
    @Select("<script>SELECT category_id, COUNT(*) as count FROM article WHERE category_id IN <foreach collection='categoryIds' item='id' open='(' separator=',' close=')'>#{id}</foreach> AND status = 1 AND is_deleted = false GROUP BY category_id</script>")
    List<Map<String, Object>> selectCategoryArticleCounts(@Param("categoryIds") List<Long> categoryIds);
}
