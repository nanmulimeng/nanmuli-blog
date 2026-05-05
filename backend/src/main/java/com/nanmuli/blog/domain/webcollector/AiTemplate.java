package com.nanmuli.blog.domain.webcollector;

import lombok.Getter;
import lombok.extern.slf4j.Slf4j;

/**
 * AI 整理模板枚举
 */
@Slf4j
@Getter
public enum AiTemplate {
    TECH_SUMMARY("tech_summary", "技术文档摘要"),
    TUTORIAL("tutorial", "教程提炼"),
    COMPARISON("comparison", "对比分析"),
    KNOWLEDGE_REPORT("knowledge_report", "知识报告（多源）"),
    DAILY_DIGEST("daily_digest", "每日技术日报"),
    CUSTOM("custom", "自定义");

    private final String code;
    private final String label;

    AiTemplate(String code, String label) {
        this.code = code;
        this.label = label;
    }

    public static AiTemplate of(String code) {
        if (code == null || code.isBlank()) {
            return TECH_SUMMARY;
        }
        for (AiTemplate template : values()) {
            if (template.code.equalsIgnoreCase(code)) {
                return template;
            }
        }
        log.warn("[AiTemplate] Unknown template code '{}', falling back to TECH_SUMMARY", code);
        return TECH_SUMMARY;
    }
}
