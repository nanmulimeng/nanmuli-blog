package com.nanmuli.blog.infrastructure.persistence.article;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.nanmuli.blog.domain.article.ArticleViewRecord;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

@Mapper
public interface ArticleViewRecordMapper extends BaseMapper<ArticleViewRecord> {

    @Select("SELECT COUNT(*) FROM article_view_record WHERE article_id = #{articleId} AND is_deleted = false")
    Long countByArticleId(@Param("articleId") Long articleId);

    @Select("SELECT COUNT(DISTINCT visitor_id) FROM article_view_record WHERE is_deleted = false")
    Long countTotalUniqueVisitors();
}
