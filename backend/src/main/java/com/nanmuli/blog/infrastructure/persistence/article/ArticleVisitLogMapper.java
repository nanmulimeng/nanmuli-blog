package com.nanmuli.blog.infrastructure.persistence.article;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.nanmuli.blog.domain.article.ArticleVisitLog;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.time.LocalDate;

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
}
