/**
 * 技术日报（Digest）相关常量
 */

/** 日报分类边框颜色映射 */
export const DIGEST_CATEGORY_COLORS: Record<string, string> = {
  hot_trend: '#ef4444',
  open_source: '#f59e0b',
  tech_article: '#3b82f6',
  dev_tool: '#10b981',
  creative: '#8b5cf6',
  paper: '#6366f1',
}

/** 默认分类颜色（未匹配时使用） */
export const DIGEST_CATEGORY_DEFAULT_COLOR = '#6b7280'

/** 获取日报分类颜色 */
export function getDigestCategoryColor(category: string): string {
  return DIGEST_CATEGORY_COLORS[category] || DIGEST_CATEGORY_DEFAULT_COLOR
}
