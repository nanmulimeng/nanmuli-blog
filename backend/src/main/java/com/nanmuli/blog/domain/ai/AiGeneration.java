package com.nanmuli.blog.domain.ai;

import com.nanmuli.blog.shared.domain.BaseAggregateRoot;
import lombok.EqualsAndHashCode;
import lombok.Getter;
import lombok.Setter;

@Getter
@Setter
@EqualsAndHashCode(callSuper = false)
public class AiGeneration extends BaseAggregateRoot<Long> {
    private static final long serialVersionUID = 1L;

    private Long articleId;
    private String type;
    private String prompt;
    private String content;
    private Integer tokensUsed;
    private String model;
    private Integer status;
    private String errorMsg;
}
