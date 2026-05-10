package com.nanmuli.blog.infrastructure.persistence.article;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.nanmuli.blog.domain.article.ArticleVisitLog;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.util.Collection;
import java.util.List;
import java.util.Map;

@Mapper
public interface ArticleVisitLogMapper extends BaseMapper<ArticleVisitLog> {

    @Select("SELECT COUNT(*) FROM article_visit_log WHERE article_id = #{articleId}")
    Long countByArticleId(@Param("articleId") Long articleId);

    @Select("SELECT COUNT(*) FROM article_visit_log WHERE article_id = #{articleId} AND DATE(visit_time) = CURRENT_DATE")
    Long countTodayByArticleId(@Param("articleId") Long articleId);

    @Select("SELECT COUNT(*) FROM article_visit_log")
    Long countTotalVisits();

    @Select("SELECT COUNT(*) FROM article_visit_log WHERE DATE(visit_time) = CURRENT_DATE")
    Long countTodayVisits();

    @Select("<script>SELECT article_id, COUNT(*) as count FROM article_visit_log WHERE article_id IN <foreach collection='ids' item='id' open='(' separator=',' close=')'>#{id}</foreach> GROUP BY article_id</script>")
    List<Map<String, Object>> countByArticleIds(@Param("ids") Collection<Long> articleIds);
}
