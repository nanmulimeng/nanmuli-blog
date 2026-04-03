package com.nanmuli.blog.domain.article;

import lombok.Getter;

@Getter
public enum ArticleStatus {
    PUBLISHED(1, "已发布"),
    DRAFT(2, "草稿"),
    RECYCLED(3, "回收站");

    private final int code;
    private final String desc;

    ArticleStatus(int code, String desc) {
        this.code = code;
        this.desc = desc;
    }

    public static ArticleStatus of(Integer code) {
        if (code == null) return null;
        for (ArticleStatus status : values()) {
            if (status.code == code) return status;
        }
        return null;
    }
}
