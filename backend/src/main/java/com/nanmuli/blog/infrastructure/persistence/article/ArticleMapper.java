package com.nanmuli.blog.infrastructure.persistence.article;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.nanmuli.blog.domain.article.Article;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Update;

@Mapper
public interface ArticleMapper extends BaseMapper<Article> {

    @Update("UPDATE article SET view_count = view_count + 1 WHERE id = #{id}")
    void increaseViewCount(@Param("id") Long id);
}
