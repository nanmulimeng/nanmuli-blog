package com.nanmuli.blog.domain.article;

import com.nanmuli.blog.shared.domain.Identifier;
import lombok.EqualsAndHashCode;
import lombok.Getter;

import java.io.Serializable;

@Getter
@EqualsAndHashCode
public class ArticleId implements Identifier {
    private final Long value;

    public ArticleId(Long value) {
        this.value = value;
    }

    @Override
    public Serializable value() {
        return value;
    }
}
