import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js'

/**
 * Markdown 处理工具
 */

// MarkdownIt 实例配置
const md = new MarkdownIt({
  html: true,
  linkify: true,
  typographer: true,
  highlight: (str: string, lang: string): string => {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return hljs.highlight(str, { language: lang }).value
      } catch {
        // 高亮失败，返回原始代码
      }
    }
    return md.utils.escapeHtml(str)
  },
})

/**
 * 将 Markdown 渲染为 HTML
 */
export function renderMarkdown(content: string): string {
  return md.render(content)
}
