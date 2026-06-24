package com.nanmuli.blog.infrastructure.persistence.webcollector;

import org.apache.ibatis.annotations.Select;
import org.junit.jupiter.api.Test;

import java.lang.reflect.Method;
import java.util.Locale;

import static org.assertj.core.api.Assertions.assertThat;

class WebCollectPageMapperProjectionTest {

    @Test
    void pageQueriesDoNotUseSelectStar() throws Exception {
        assertNoSelectStar("selectByTaskIdOrderBySortOrder", Long.class);
        assertNoSelectStar("selectByTaskId", Long.class);
        assertNoSelectStar("selectByUrlHash", String.class);
    }

    @Test
    void pageProjectionUsesExplicitKnownColumns() {
        String columns = WebCollectPageMapper.WEB_COLLECT_PAGE_COLUMNS.toLowerCase(Locale.ROOT);

        assertThat(columns).contains("task_id", "url", "page_title", "raw_markdown", "crawl_status");
        assertThat(columns).doesNotContain("*");
    }

    private void assertNoSelectStar(String methodName, Class<?>... parameterTypes) throws Exception {
        Method method = WebCollectPageMapper.class.getMethod(methodName, parameterTypes);
        Select select = method.getAnnotation(Select.class);
        assertThat(select).isNotNull();

        String sql = String.join("\n", select.value()).toUpperCase(Locale.ROOT);
        assertThat(sql).doesNotContain("SELECT *");
        assertThat(sql).doesNotContain("SELECT *,");
        assertThat(sql).contains("FROM WEB_COLLECT_PAGE");
    }
}
