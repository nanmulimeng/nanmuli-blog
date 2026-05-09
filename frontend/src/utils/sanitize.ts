import DOMPurify from 'dompurify'

// 配置 DOMPurify 允许的标签和属性（保留 Markdown 渲染所需）
DOMPurify.addHook('uponSanitizeAttribute', (node, data) => {
  // 保留 code 标签的 class（用于语法高亮）
  if (data.attrName === 'class' && node.tagName === 'CODE') {
    data.forceKeepAttr = true
  }
})

export function sanitize(html: string): string {
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS: [
      'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'br', 'hr',
      'div', 'span', 'blockquote', 'pre', 'code',
      'ul', 'ol', 'li', 'table', 'thead', 'tbody', 'tr', 'th', 'td',
      'a', 'strong', 'em', 'del', 's', 'img',
      'input', 'details', 'summary', 'sup', 'sub',
    ],
    ALLOWED_ATTR: [
      'href', 'target', 'rel', 'src', 'alt', 'title',
      'class', 'id', 'width', 'height', 'align',
      'checked', 'disabled', 'type',
    ],
    ALLOW_DATA_ATTR: false,
  })
}
