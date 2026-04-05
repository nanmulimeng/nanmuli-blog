package com.nanmuli.blog.domain.article;

import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 文章-标签关联实体
 * 使用复合主键 (article_id, tag_id)
 */
@Data
@TableName("article_tag")
public class ArticleTag {

    private Long articleId;

    private Long tagId;

    private LocalDateTime createdAt;
}
