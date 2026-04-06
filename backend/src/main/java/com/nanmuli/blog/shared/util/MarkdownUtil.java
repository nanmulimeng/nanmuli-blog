package com.nanmuli.blog.shared.util;

import com.vladsch.flexmark.html.HtmlRenderer;
import com.vladsch.flexmark.parser.Parser;
import com.vladsch.flexmark.util.ast.Node;
import com.vladsch.flexmark.util.data.MutableDataSet;
import org.jsoup.Jsoup;
import org.jsoup.safety.Safelist;
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
        // 启用GitHub风格Markdown扩展
        options.set(Parser.EXTENSIONS, java.util.Arrays.asList(
            com.vladsch.flexmark.ext.tables.TablesExtension.create(),
            com.vladsch.flexmark.ext.gfm.strikethrough.StrikethroughExtension.create(),
            com.vladsch.flexmark.ext.gfm.tasklist.TaskListExtension.create(),
            com.vladsch.flexmark.ext.toc.TocExtension.create()
        ));
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
        String html = renderer.render(document);
        return sanitizeHtml(html);
    }

    /**
     * 净化HTML，过滤危险标签和属性（XSS防护）
     */
    public String sanitizeHtml(String html) {
        if (html == null || html.isEmpty()) {
            return html;
        }
        Safelist safelist = Safelist.basic()
            // 链接只允许http/https/mailto，禁止javascript/data
            .removeProtocols("a", "href", "ftp", "http", "https", "mailto")
            .addProtocols("a", "href", "http", "https", "mailto")
            // 只允许target和title属性，强制添加rel="noopener noreferrer"
            .addAttributes("a", "target", "title")
            .addEnforcedAttribute("a", "rel", "noopener noreferrer")
            // 图片只允许http/https，禁止data:协议
            .addAttributes("img", "src", "alt", "title", "loading", "width", "height")
            .addProtocols("img", "src", "http", "https")
            // 标题标签
            .addTags("h1", "h2", "h3", "h4", "h5", "h6")
            // 代码和引用
            .addTags("pre", "code", "blockquote", "hr", "br")
            // 表格
            .addTags("table", "thead", "tbody", "tr", "th", "td")
            // 列表
            .addTags("ul", "ol", "li")
            // 任务列表（Markdown任务列表生成）
            .addTags("input")
            .addAttributes("input", "type", "checked", "disabled")
            .addAttributes("code", "class")
            .addAttributes("pre", "class");
        return Jsoup.clean(html, safelist);
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
