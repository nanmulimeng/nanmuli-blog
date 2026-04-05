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

/**
 * 提取纯文本（去除 Markdown 标记）
 */
export function extractText(content: string): string {
  return content
    .replace(/[#*_`~\[\]\(\)!]/g, '')
    .replace(/\n+/g, ' ')
    .trim()
}

/**
 * 生成摘要
 * @param content Markdown 内容
 * @param length 摘要长度
 */
export function generateSummary(content: string, length: number = 200): string {
  const text = extractText(content)
  if (text.length <= length) {
    return text
  }
  return text.slice(0, length) + '...'
}

/**
 * 统计字数
 */
export function countWords(content: string): number {
  // 移除 Markdown 标记后统计中文字符和英文单词
  const text = extractText(content)
  const chineseChars = (text.match(/[\u4e00-\u9fa5]/g) || []).length
  const englishWords = (text.match(/[a-zA-Z]+/g) || []).length
  return chineseChars + englishWords
}

/**
 * 估算阅读时间（分钟）
 */
export function estimateReadingTime(content: string, wordsPerMinute: number = 300): number {
  const words = countWords(content)
  return Math.ceil(words / wordsPerMinute)
}

/**
 * 提取标题列表（用于生成目录）
 */
export function extractHeadings(content: string): Array<{ level: number; text: string; id: string }> {
  const headings: Array<{ level: number; text: string; id: string }> = []
  const lines = content.split('\n')

  lines.forEach((line) => {
    const match = line.match(/^(#{1,6})\s+(.+)$/)
    if (match && match[1] && match[2]) {
      const level = match[1].length
      const text = match[2].trim()
      const id = text.toLowerCase().replace(/\s+/g, '-').replace(/[^\w\u4e00-\u9fa5-]/g, '')
      headings.push({ level, text, id })
    }
  })

  return headings
}

/**
 * 代码块语言映射
 */
export const CODE_LANGUAGES: Record<string, string> = {
  js: 'JavaScript',
  ts: 'TypeScript',
  jsx: 'React JSX',
  tsx: 'React TSX',
  vue: 'Vue',
  html: 'HTML',
  css: 'CSS',
  scss: 'SCSS',
  sass: 'Sass',
  less: 'Less',
  json: 'JSON',
  xml: 'XML',
  yaml: 'YAML',
  md: 'Markdown',
  sql: 'SQL',
  java: 'Java',
  kotlin: 'Kotlin',
  groovy: 'Groovy',
  py: 'Python',
  rb: 'Ruby',
  php: 'PHP',
  go: 'Go',
  rust: 'Rust',
  c: 'C',
  cpp: 'C++',
  csharp: 'C#',
  swift: 'Swift',
  dart: 'Dart',
  shell: 'Shell',
  bash: 'Bash',
  powershell: 'PowerShell',
  dockerfile: 'Dockerfile',
  nginx: 'Nginx',
}
