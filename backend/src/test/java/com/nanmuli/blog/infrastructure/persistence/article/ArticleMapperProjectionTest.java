package com.nanmuli.blog.infrastructure.persistence.article;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.nanmuli.blog.domain.article.Article;
import org.apache.ibatis.annotations.Select;
import org.junit.jupiter.api.Test;

import java.lang.reflect.Method;
import java.util.List;
import java.util.Locale;

import static org.assertj.core.api.Assertions.assertThat;

class ArticleMapperProjectionTest {

    @Test
    void searchQueriesDoNotSelectFullArticleRows() throws Exception {
        assertNoSelectStar("searchPublishedByFts", IPage.class, String.class, List.class, String.class);
        assertNoSelectStar("searchAllByFts", IPage.class, String.class, List.class);
        assertNoSelectStar("searchPublishedByTrigram", IPage.class, String.class, List.class);
    }

    @Test
    void listProjectionExcludesLargeContentColumns() {
        String columns = ArticleMapper.ARTICLE_LIST_COLUMNS.toLowerCase(Locale.ROOT);

        assertThat(columns).contains("title", "summary", "created_at", "updated_at");
        assertThat(columns).doesNotContain("content,", "content_html");
    }

    private void assertNoSelectStar(String methodName, Class<?>... parameterTypes) throws Exception {
        Method method = ArticleMapper.class.getMethod(methodName, parameterTypes);
        Select select = method.getAnnotation(Select.class);
        assertThat(select).isNotNull();

        String sql = String.join("\n", select.value()).toUpperCase(Locale.ROOT);
        assertThat(sql).doesNotContain("SELECT *");
        assertThat(sql).doesNotContain("SELECT *,");
        assertThat(sql).contains("FROM ARTICLE");
    }
}
