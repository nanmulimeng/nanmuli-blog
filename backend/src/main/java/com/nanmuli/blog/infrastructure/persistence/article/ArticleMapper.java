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
     * 根据标签ID分页查询文章
     */
    @Select("""
            SELECT a.* FROM article a
            INNER JOIN article_tag at ON a.id = at.article_id
            WHERE at.tag_id = #{tagId}
            AND a.status = 1 AND a.is_deleted = false
            ORDER BY a.is_top DESC, a.publish_time DESC
            """)
    IPage<Article> selectByTagId(IPage<Article> page, @Param("tagId") Long tagId);
}
