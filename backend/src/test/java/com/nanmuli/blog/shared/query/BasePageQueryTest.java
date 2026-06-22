package com.nanmuli.blog.shared.query;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class BasePageQueryTest {

    @Test
    void gettersNormalizeUnsafePageValuesForServiceLayerCalls() {
        BasePageQuery query = new BasePageQuery();
        query.setCurrent(0L);
        query.setSize(10_000L);

        assertThat(query.getCurrent()).isEqualTo(1L);
        assertThat(query.getSize()).isEqualTo(100L);
    }

    @Test
    void staticNormalizeHelpersHandleNullAndNegativeValues() {
        assertThat(BasePageQuery.normalizeCurrent(null)).isEqualTo(1L);
        assertThat(BasePageQuery.normalizeCurrent(-10)).isEqualTo(1L);
        assertThat(BasePageQuery.normalizeSize(null)).isEqualTo(10L);
        assertThat(BasePageQuery.normalizeSize(-10)).isEqualTo(1L);
        assertThat(BasePageQuery.normalizeSize(101)).isEqualTo(100L);
    }
}
