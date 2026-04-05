package com.nanmuli.blog.shared.util;

import com.vladsch.flexmark.html.HtmlRenderer;
import com.vladsch.flexmark.parser.Parser;
import com.vladsch.flexmark.util.ast.Node;
import com.vladsch.flexmark.util.data.MutableDataSet;
import org.springframework.stereotype.Component;

/**
 * Markdown工具类
 */
@Component
public class MarkdownUtil {

    private final Parser parser;
    private final HtmlRenderer renderer;

    public MarkdownUtil() {
        MutableDataSet options = new MutableDataSet();
        // 启用GitHub风格Markdown
        options.set(Parser.EXTENSIONS, java.util.Arrays.asList(
            com.vladsch.flexmark.ext.tables.TablesExtension.create(),
            com.vladsch.flexmark.ext.gfm.strikethrough.StrikethroughExtension.create(),
            com.vladsch.flexmark.ext.gfm.tasklist.TaskListExtension.create(),
            com.vladsch.flexmark.ext.anchorlink.AnchorLinkExtension.create(),
            com.vladsch.flexmark.ext.toc.TocExtension.create()
        ));
        // 启用自动链接
        options.set(Parser.AUTOLINK_WWW_PREFIX, "http://");
        // 启用表格
        options.set(TablesExtension.TRIM_CELL_WHITESPACE, true);
        options.set(TablesExtension.DISCARD_EXTRA_COLUMNS, true);
        // 代码高亮
        options.set(HtmlRenderer.FENCED_CODE_LANGUAGE_CLASS_PREFIX, "language-");

        this.parser = Parser.builder(options).build();
        this.renderer = HtmlRenderer.builder(options).build();
    }

    /**
     * 将Markdown转换为HTML
     */
    public String toHtml(String markdown) {
        if (markdown == null || markdown.isEmpty()) {
            return "";
        }
        Node document = parser.parse(markdown);
        return renderer.render(document);
    }

    /**
     * 提取纯文本（用于生成摘要）
     */
    public String extractText(String markdown) {
        if (markdown == null || markdown.isEmpty()) {
            return "";
        }
        // 移除Markdown标记
        String text = markdown
            .replaceAll("#+\\s*", "") // 标题
            .replaceAll("\\*\\*([^\\*]+)\\*\\*", "$1") // 粗体
            .replaceAll("\\*([^\\*]+)\\*", "$1") // 斜体
            .replaceAll("`([^`]+)`", "$1") // 行内代码
            .replaceAll("\\[([^\\]]+)\\]\\([^\\)]+\\)", "$1") // 链接
            .replaceAll("!\\[[^\\]]*\\]\\([^\\)]+\\)", "") // 图片
            .replaceAll(">\\s*", "") // 引用
            .replaceAll("-\\s*", "") // 列表
            .replaceAll("\\d+\\.\\s*", "") // 有序列表
            .replaceAll("\\|", " ") // 表格
            .replaceAll("-{3,}", "") // 分隔线
            .replaceAll("\\s+", " ") // 合并空白
            .trim();
        return text;
    }

    /**
     * 生成摘要
     */
    public String generateSummary(String markdown, int maxLength) {
        String text = extractText(markdown);
        if (text.length() <= maxLength) {
            return text;
        }
        return text.substring(0, maxLength) + "...";
    }
}
