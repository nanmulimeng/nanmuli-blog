/**
 * 全局常量定义
 */

export const ArticleStatusMap: Record<number, { label: string; type: 'success' | 'warning' | 'danger' | 'info' }> = {
  1: { label: '已发布', type: 'success' },
  2: { label: '草稿', type: 'warning' },
  3: { label: '回收站', type: 'danger' },
}
