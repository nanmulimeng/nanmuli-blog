package com.nanmuli.blog.infrastructure.persistence.article;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.nanmuli.blog.domain.article.ArticleViewRecord;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.util.Collection;
import java.util.List;
import java.util.Map;

@Mapper
public interface ArticleViewRecordMapper extends BaseMapper<ArticleViewRecord> {

    @Select("SELECT COUNT(*) FROM article_view_record WHERE article_id = #{articleId} AND is_deleted = false")
    Long countByArticleId(@Param("articleId") Long articleId);

    @Select("SELECT COUNT(DISTINCT visitor_id) FROM article_view_record WHERE is_deleted = false")
    Long countTotalUniqueVisitors();

    @Select("<script>" +
            "SELECT article_id, COUNT(*) as cnt FROM article_view_record " +
            "WHERE is_deleted = false AND article_id IN " +
            "<foreach collection='ids' item='id' open='(' separator=',' close=')'>#{id}</foreach> " +
            "GROUP BY article_id" +
            "</script>")
    List<Map<String, Object>> countByArticleIds(@Param("ids") Collection<Long> articleIds);
}
