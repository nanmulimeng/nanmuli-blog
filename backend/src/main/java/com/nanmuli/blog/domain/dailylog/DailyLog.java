package com.nanmuli.blog.domain.dailylog;

import com.nanmuli.blog.shared.domain.BaseAggregateRoot;
import lombok.EqualsAndHashCode;
import lombok.Getter;
import lombok.Setter;

import java.time.LocalDate;

@Getter
@Setter
@EqualsAndHashCode(callSuper = false)
public class DailyLog extends BaseAggregateRoot<Long> {
    private static final long serialVersionUID = 1L;

    private String content;
    private String contentHtml;
    private String mood;
    private String weather;
    private Integer wordCount;
    private LocalDate logDate;
    private Boolean isPublic;
    private Long categoryId;

    /**
     * 是否公开分享
     */
    public boolean isPublic() {
        return isPublic != null && isPublic;
    }
}
